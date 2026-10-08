"""Cache-first deterministic street exposure snapshots for Prompt 3."""

from __future__ import annotations

import json
import logging
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

from app.config import AppConfig, get_config
from app.repositories.cache import load_cached_geojson, load_shadow_snapshot
from app.services.shadow_engine import time_slug


LOGGER = logging.getLogger(__name__)

GeoJsonLoader = Callable[..., dict[str, Any]]


def temperature_factor(config: AppConfig, canonical_time: str) -> float:
    """Normalize the configured prototype temperature curve to [0, 1]."""
    if canonical_time not in config.temperature_proxy_c:
        raise ValueError(f"No configured temperature proxy for {canonical_time}.")
    temperatures = tuple(config.temperature_proxy_c.values())
    minimum, maximum = min(temperatures), max(temperatures)
    if maximum == minimum:
        return 0.0
    return (config.temperature_proxy_c[canonical_time] - minimum) / (maximum - minimum)


def geometric_exposure_value(direct_exposure_fraction: float, normalized_temperature_factor: float, config: AppConfig) -> float:
    """Return the bounded SRS 61 geometric exposure proxy."""
    direct = max(0.0, min(1.0, direct_exposure_fraction))
    temperature = max(0.0, min(1.0, normalized_temperature_factor))
    value = direct * (
        config.exposure_direct_weight + config.exposure_temperature_weight * temperature
    ) * config.exposure_duration_factor
    return max(0.0, min(1.0, value))


def fallback_exposure_value(normalized_temperature_factor: float, config: AppConfig) -> float:
    """Return the bounded non-geometric fallback; it never uses shadow data."""
    base_direct_fraction = 1.0 - config.static_fallback_shade_factor
    value = base_direct_fraction * (
        config.exposure_direct_weight + config.exposure_temperature_weight * normalized_temperature_factor
    ) * config.exposure_duration_factor
    return max(0.0, min(1.0, value))


def _metadata(config: AppConfig, canonical_time: str, mode: str, fallback_reason: str | None = None) -> dict[str, Any]:
    metadata = {
        "canonical_time": canonical_time,
        "computation_mode": mode,
        "modelled_or_interpolated": "MODELLED",
        "observed_or_estimated": "ESTIMATED",
        "config_version": config.version,
        "temperature_proxy_c": config.temperature_proxy_c[canonical_time],
        "normalized_temperature_factor": temperature_factor(config, canonical_time),
        "temperature_proxy_label": config.temperature_proxy_label,
        "exposure_duration_factor": config.exposure_duration_factor,
        "formula": (
            "clip(direct_exposure_fraction * (direct_weight + temperature_weight * "
            "normalized_temperature_factor) * exposure_duration_factor, 0, 1)"
            if mode == "geometric"
            else "clip((1 - static_fallback_shade_factor) * (direct_weight + temperature_weight * normalized_temperature_factor) * exposure_duration_factor, 0, 1)"
        ),
    }
    if fallback_reason:
        metadata["fallback_reason"] = fallback_reason
    return metadata


def _exposure_feature(
    source_feature: dict[str, Any],
    canonical_time: str,
    config: AppConfig,
    mode: str,
    exposure_value: float,
) -> dict[str, Any]:
    properties = source_feature.get("properties", {})
    result = {
        "segment_id": properties["segment_id"],
        "length_m": properties.get("length_m"),
        "canonical_time": canonical_time,
        "exposure_value": exposure_value,
        "temperature_proxy_c": config.temperature_proxy_c[canonical_time],
        "normalized_temperature_factor": temperature_factor(config, canonical_time),
        "source_type": "derived",
        "source_reference": (
            "Cached geometric shade snapshot and configured prototype temperature curve"
            if mode == "geometric"
            else "Cached OSM streets and configured prototype temperature curve/static fallback factor"
        ),
        "observed_or_estimated": "ESTIMATED",
        "modelled_or_interpolated": "MODELLED",
        "timestamp": datetime.now(UTC).isoformat(),
        "assumptions_version": config.version,
        "computation_mode": mode,
    }
    if mode == "geometric":
        shade_fraction = max(0.0, min(1.0, float(properties["shade_fraction"])))
        result["shade_fraction"] = shade_fraction
        result["direct_exposure_fraction"] = 1.0 - shade_fraction
    else:
        result["static_fallback_shade_factor"] = config.static_fallback_shade_factor
        result["base_direct_fraction"] = 1.0 - config.static_fallback_shade_factor
        result["fallback_description"] = "Estimated exposure mode; no shadow simulation was used."
    return {"type": "Feature", "properties": result, "geometry": source_feature["geometry"]}


def build_canonical_exposure_snapshot(
    canonical_time: str,
    config: AppConfig | None = None,
    shadow_loader: GeoJsonLoader = load_shadow_snapshot,
    street_loader: GeoJsonLoader = load_cached_geojson,
) -> dict[str, Any]:
    """Build one cacheable snapshot, falling back when geometry is unavailable."""
    active_config = config or get_config()
    if canonical_time not in active_config.canonical_times:
        raise ValueError(f"Unsupported exposure time '{canonical_time}'.")

    fallback_reason: str | None = None
    if active_config.exposure_computation_mode == "geometric":
        try:
            shade_snapshot = shadow_loader("shade_fractions", canonical_time, active_config)
            features = []
            factor = temperature_factor(active_config, canonical_time)
            for feature in shade_snapshot["features"]:
                shade = max(0.0, min(1.0, float(feature["properties"]["shade_fraction"])))
                features.append(
                    _exposure_feature(
                        feature,
                        canonical_time,
                        active_config,
                        "geometric",
                        geometric_exposure_value(1.0 - shade, factor, active_config),
                    )
                )
            return {"type": "FeatureCollection", "features": features, "metadata": _metadata(active_config, canonical_time, "geometric")}
        except Exception as exc:  # Cache failures must not stop the configured fallback path.
            fallback_reason = f"Geometric shadow snapshot unavailable: {exc}"
            LOGGER.warning("%s; using estimated exposure fallback for %s.", fallback_reason, canonical_time)
    else:
        fallback_reason = "Estimated exposure mode selected by central configuration."

    streets = street_loader("streets", active_config)
    factor = temperature_factor(active_config, canonical_time)
    exposure = fallback_exposure_value(factor, active_config)
    return {
        "type": "FeatureCollection",
        "features": [
            _exposure_feature(feature, canonical_time, active_config, "estimated", exposure)
            for feature in streets["features"]
        ],
        "metadata": _metadata(active_config, canonical_time, "estimated", fallback_reason),
    }


def _write_snapshot(path: Path, snapshot: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(snapshot), encoding="utf-8")


def precompute_exposure(config: AppConfig | None = None) -> dict[str, Any]:
    """Write five independently cacheable canonical exposure snapshots."""
    active_config = config or get_config()
    started = time.perf_counter()
    report: dict[str, Any] = {
        "config_version": active_config.version,
        "selected_computation_mode": active_config.exposure_computation_mode,
        "temperature_proxy_label": active_config.temperature_proxy_label,
        "snapshots": {},
    }
    for canonical_time in active_config.canonical_times:
        snapshot_started = time.perf_counter()
        snapshot = build_canonical_exposure_snapshot(canonical_time, active_config)
        _write_snapshot(active_config.cache_data_dir / f"exposure_{time_slug(canonical_time)}.geojson", snapshot)
        values = [feature["properties"]["exposure_value"] for feature in snapshot["features"]]
        report["snapshots"][canonical_time] = {
            "computation_mode": snapshot["metadata"]["computation_mode"],
            "fallback_reason": snapshot["metadata"].get("fallback_reason"),
            "segment_count": len(values),
            "exposure_min": min(values) if values else 0.0,
            "exposure_mean": sum(values) / len(values) if values else 0.0,
            "exposure_max": max(values) if values else 0.0,
            "duration_seconds": time.perf_counter() - snapshot_started,
        }
    report["duration_seconds"] = time.perf_counter() - started
    (active_config.cache_data_dir / "exposure_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    LOGGER.info("Exposure precompute completed in %.2fs using %s mode.", report["duration_seconds"], active_config.exposure_computation_mode)
    return report
