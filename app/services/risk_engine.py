"""Cache-first Prompt 4A risk records with one global normalization scope."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from app.config import AppConfig, get_config
from app.repositories.cache import load_exposure_snapshot
from app.services.cooling_access_engine import build_cooling_access_records
from app.services.shadow_engine import time_slug
from app.services.vulnerability_engine import build_vulnerability_records


def baseline_risk(exposure_value: float, vulnerability_value: float) -> float:
    return max(0.0, min(1.0, exposure_value)) * max(0.0, min(1.0, vulnerability_value))


def final_risk_raw(baseline: float, access_penalty: float) -> float:
    return baseline * (1.0 + max(0.0, min(1.0, access_penalty)))


def normalize_global(raw_values: list[float]) -> list[float]:
    """Apply the sole risk-score normalization over all five canonical snapshots."""
    if not raw_values:
        return []
    minimum, maximum = min(raw_values), max(raw_values)
    if minimum == maximum:
        return [50.0] * len(raw_values)
    return [max(0.0, min(100.0, 100.0 * (value - minimum) / (maximum - minimum))) for value in raw_values]


def normalization_bounds(raw_values: list[float]) -> tuple[float, float]:
    """Return the global bounds used by the sole score-normalization step."""
    return (min(raw_values), max(raw_values)) if raw_values else (0.0, 0.0)


def normalize_with_bounds(raw_value: float, minimum: float, maximum: float) -> float:
    """Normalize one value using the already-selected global cache scope."""
    if minimum == maximum:
        return 50.0
    return max(0.0, min(100.0, 100.0 * (raw_value - minimum) / (maximum - minimum)))


def risk_class(score: float) -> str:
    if score <= 25:
        return "LOW"
    if score <= 50:
        return "MODERATE"
    if score <= 75:
        return "HIGH"
    return "CRITICAL"


def _write_snapshot(path: Path, snapshot: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(snapshot), encoding="utf-8")


def precompute_risk(config: AppConfig | None = None) -> dict[str, Any]:
    """Combine cached exposure with estimated vulnerability/access into five risk caches."""
    active_config = config or get_config()
    started = time.perf_counter()
    vulnerability, vulnerability_metadata = build_vulnerability_records(active_config)
    access, access_metadata = build_cooling_access_records(active_config)
    pending: list[tuple[str, dict[str, Any], dict[str, Any], dict[str, Any], float, float]] = []
    for canonical_time in active_config.canonical_times:
        exposure_snapshot = load_exposure_snapshot(canonical_time, active_config)
        for feature in exposure_snapshot["features"]:
            exposure_properties = feature["properties"]
            segment_id = exposure_properties["segment_id"]
            vulnerability_record = vulnerability[segment_id]
            access_record = access[segment_id]
            baseline = baseline_risk(exposure_properties["exposure_value"], vulnerability_record["vulnerability_value"])
            raw = final_risk_raw(baseline, access_record["access_penalty"])
            pending.append((canonical_time, feature, vulnerability_record, access_record, baseline, raw))
    raw_values = [item[-1] for item in pending]
    scores = normalize_global(raw_values)
    global_raw_min, global_raw_max = normalization_bounds(raw_values)
    snapshots: dict[str, list[dict[str, Any]]] = {canonical_time: [] for canonical_time in active_config.canonical_times}
    for (canonical_time, feature, vulnerability_record, access_record, baseline, raw), score in zip(pending, scores, strict=True):
        exposure_properties = feature["properties"]
        properties = {
            "segment_id": exposure_properties["segment_id"],
            "length_m": exposure_properties.get("length_m"),
            "canonical_time": canonical_time,
            "exposure_value": exposure_properties["exposure_value"],
            "elderly_component": vulnerability_record["elderly_component"],
            "outdoor_worker_component": vulnerability_record["outdoor_worker_component"],
            "vulnerability_value": vulnerability_record["vulnerability_value"],
            "estimated_elderly_exposure": vulnerability_record["estimated_elderly_exposure"],
            "estimated_outdoor_worker_exposure": vulnerability_record["estimated_outdoor_worker_exposure"],
            "estimated_vulnerability": vulnerability_record["estimated_vulnerability"],
            "distance_to_water_m": access_record["distance_to_water_m"],
            "distance_to_cooling_m": access_record["distance_to_cooling_m"],
            "water_access_penalty": access_record["water_access_penalty"],
            "cooling_access_penalty": access_record["cooling_access_penalty"],
            "access_penalty": access_record["access_penalty"],
            "water_available": access_record["water_available"],
            "cooling_available": access_record["cooling_available"],
            "baseline_risk": baseline,
            "final_risk_raw": raw,
            "risk_score": score,
            "risk_class": risk_class(score),
            "estimated_flag": True,
            "source_type": "derived",
            "source_reference": "Modelled exposure plus estimated cached-OSM vulnerability proxies and cached OSM access data.",
            "observed_or_estimated": "ESTIMATED",
            "modelled_or_interpolated": "MODELLED",
            "timestamp": exposure_properties.get("timestamp"),
            "assumptions_version": active_config.version,
            "computation_mode": exposure_properties["computation_mode"],
        }
        snapshots[canonical_time].append({"type": "Feature", "properties": properties, "geometry": feature["geometry"]})
    report: dict[str, Any] = {
        "config_version": active_config.version,
        "normalization_method": active_config.risk_normalization_method,
        "normalization_scope": active_config.risk_normalization_scope,
        "vulnerability": vulnerability_metadata,
        "access": access_metadata,
        "snapshots": {},
    }
    for canonical_time, features in snapshots.items():
        snapshot_started = time.perf_counter()
        snapshot = {
            "type": "FeatureCollection",
            "features": features,
            "metadata": {
                "canonical_time": canonical_time,
                "computation_mode": features[0]["properties"]["computation_mode"] if features else active_config.exposure_computation_mode,
                "modelled_or_interpolated": "MODELLED",
                "observed_or_estimated": "ESTIMATED",
                "estimated_flag": True,
                "config_version": active_config.version,
                "normalization_method": active_config.risk_normalization_method,
                "normalization_scope": active_config.risk_normalization_scope,
                "global_final_risk_raw_min": global_raw_min,
                "global_final_risk_raw_max": global_raw_max,
                "vulnerability_proxy": vulnerability_metadata,
                "cooling_access": access_metadata,
            },
        }
        _write_snapshot(active_config.cache_data_dir / f"risk_{time_slug(canonical_time)}.geojson", snapshot)
        risk_scores = [feature["properties"]["risk_score"] for feature in features]
        report["snapshots"][canonical_time] = {
            "segment_count": len(features),
            "risk_score_min": min(risk_scores) if risk_scores else 0.0,
            "risk_score_mean": sum(risk_scores) / len(risk_scores) if risk_scores else 0.0,
            "risk_score_max": max(risk_scores) if risk_scores else 0.0,
            "class_counts": {name: sum(feature["properties"]["risk_class"] == name for feature in features) for name in active_config.risk_class_ranges},
            "duration_seconds": time.perf_counter() - snapshot_started,
        }
    vulnerability_values = [record["vulnerability_value"] for record in vulnerability.values()]
    report["vulnerability_stats"] = {
        "min": min(vulnerability_values) if vulnerability_values else 0.0,
        "mean": sum(vulnerability_values) / len(vulnerability_values) if vulnerability_values else 0.0,
        "max": max(vulnerability_values) if vulnerability_values else 0.0,
    }
    report["duration_seconds"] = time.perf_counter() - started
    (active_config.cache_data_dir / "risk_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report
