"""Deterministic cache-record explainability and undirected street presentation helpers."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from app.config import AppConfig, get_config


RISK_VALUE_FIELDS = (
    "exposure_value",
    "shade_fraction",
    "vulnerability_value",
    "access_penalty",
    "final_risk_raw",
    "risk_score",
)


def canonical_street_key(segment_id: str) -> str:
    """Return the stable undirected identity from a directed ID or canonical key.

    OSMnx segment IDs are ``osm-{u}-{v}-{edge_key}``.  Sorting ``u`` and ``v``
    collapses both directions (and any parallel directed edges) into the one
    presentation street used by the map, ranking, selection, and comparison.
    The original directed IDs remain available in ``directed_segment_ids`` for
    later routing work.
    """
    if not segment_id.startswith("osm-"):
        raise ValueError(f"Unsupported segment ID '{segment_id}'.")
    parts = segment_id.removeprefix("osm-").rsplit("-", 2)
    if len(parts) == 2:
        start, end = parts
    elif len(parts) == 3:
        start, end, _edge_key = parts
    else:
        raise ValueError(f"Unsupported segment ID '{segment_id}'.")
    first, second = sorted((start, end), key=lambda value: (not value.isdigit(), int(value) if value.isdigit() else value))
    return f"osm-{first}-{second}"


def _parallel_edge_key(segment_id: str) -> str:
    """Return the canonical node pair plus OSM edge key for diagnostics only."""
    try:
        _start, _end, edge_key = segment_id.removeprefix("osm-").rsplit("-", 2)
    except ValueError as exc:
        raise ValueError(f"Unsupported segment ID '{segment_id}'.") from exc
    return f"{canonical_street_key(segment_id)}-{edge_key}"


def _features_differ(features: list[dict[str, Any]]) -> bool:
    reference = features[0]["properties"]
    return any(
        any(
            field not in feature["properties"]
            or field not in reference
            or abs(float(feature["properties"][field]) - float(reference[field])) > 1e-12
            for field in RISK_VALUE_FIELDS
        )
        for feature in features[1:]
    )


def _consistency_report(groups: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    parallel_differences: list[str] = []
    paired_canonical_streets = 0
    directional_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for key, features in groups.items():
        if len(features) < 2:
            pass
        else:
            paired_canonical_streets += 1
            if _features_differ(features):
                parallel_differences.append(key)
        for feature in features:
            directional_groups[_parallel_edge_key(feature["properties"]["segment_id"])].append(feature)

    directional_differences: list[str] = []
    paired_directional_streets = 0
    for key, features in directional_groups.items():
        if len(features) < 2:
            continue
        paired_directional_streets += 1
        if _features_differ(features):
            directional_differences.append(key)
    return {
        "paired_undirected_streets": paired_canonical_streets,
        "paired_directional_streets": paired_directional_streets,
        "differing_undirected_streets": len(directional_differences),
        "differing_directional_edge_keys": directional_differences,
        "parallel_edge_difference_count": len(parallel_differences),
        "parallel_edge_difference_canonical_keys": parallel_differences,
    }


def deduplicate_risk_features(features: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Choose one deterministic representative for every undirected street."""
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for feature in features:
        groups[canonical_street_key(feature["properties"]["segment_id"])].append(feature)
    output: list[dict[str, Any]] = []
    for key in sorted(groups):
        candidates = sorted(groups[key], key=lambda feature: feature["properties"]["segment_id"])
        representative = candidates[0]
        properties = {
            **representative["properties"],
            "canonical_street_key": key,
            "directed_segment_ids": [feature["properties"]["segment_id"] for feature in candidates],
        }
        output.append({"type": "Feature", "properties": properties, "geometry": representative["geometry"]})
    report = _consistency_report(groups)
    report["unique_street_count"] = len(output)
    return output, report


def find_canonical_feature(features: list[dict[str, Any]], requested_segment_id: str) -> dict[str, Any] | None:
    """Resolve either directed ID (or the canonical key) to its presentation street."""
    requested_key = canonical_street_key(requested_segment_id) if requested_segment_id.startswith("osm-") else requested_segment_id
    for feature in features:
        properties = feature["properties"]
        if requested_segment_id in properties.get("directed_segment_ids", ()) or requested_key == properties.get("canonical_street_key"):
            return feature
    return None


def _level(value: float, thresholds: tuple[float, float]) -> str:
    if value < thresholds[0]:
        return "LOW"
    if value < thresholds[1]:
        return "MODERATE"
    return "HIGH"


def _cooling_access_level(access_penalty: float, thresholds: tuple[float, float]) -> str:
    """Translate penalty direction into user-facing access quality."""
    if access_penalty < thresholds[0]:
        return "GOOD"
    if access_penalty < thresholds[1]:
        return "MODERATE"
    return "POOR"


def build_risk_drivers(record: dict[str, Any], config: AppConfig | None = None) -> dict[str, Any]:
    """Build explainability fields exclusively from a cached risk record."""
    active_config = config or get_config()
    shade = float(record["shade_fraction"])
    raw_drivers = [
        ("solar_exposure", "Solar exposure", float(record["exposure_value"]), float(record["exposure_value"])),
        ("shade", "Shade", shade, 1.0 - shade),
        ("vulnerability", "Estimated vulnerability", float(record["vulnerability_value"]), float(record["vulnerability_value"])),
        ("cooling_access_penalty", "Cooling access", float(record["access_penalty"]), float(record["access_penalty"])),
    ]
    denominator = sum(driver[3] for driver in raw_drivers)
    drivers = []
    for identifier, label, value, explanatory_impact in raw_drivers:
        level = (
            _cooling_access_level(value, active_config.explainability_level_thresholds[identifier])
            if identifier == "cooling_access_penalty"
            else _level(value, active_config.explainability_level_thresholds[identifier])
        )
        drivers.append({
            "id": identifier,
            "label": label,
            "value": value,
            "level": level,
            "relative_contribution": explanatory_impact / denominator if denominator else 0.25,
        })
    drivers.sort(key=lambda driver: (-driver["relative_contribution"], driver["id"]))
    dominant = drivers[:active_config.explainability_dominant_driver_count]

    phrases = []
    for driver in dominant:
        if driver["id"] == "solar_exposure":
            phrases.append(f"{driver['level'].lower()} modelled solar exposure")
        elif driver["id"] == "shade":
            phrases.append(f"{driver['level'].lower()} shade")
        elif driver["id"] == "vulnerability":
            phrases.append(f"{driver['level'].lower()} estimated vulnerability")
        elif record["water_available"] or record["cooling_available"]:
            phrases.append(f"{driver['level'].lower()} cooling access")
        else:
            phrases.append("no recorded water/cooling facilities in OSM for this area")
    primary_sentence = "Primary drivers are " + ", ".join(phrases[:-1]) + (", and " if len(phrases) > 1 else "") + phrases[-1] + "."
    return {"drivers": drivers, "dominant_driver_ids": [driver["id"] for driver in dominant], "primary_drivers_sentence": primary_sentence}


def street_summary(feature: dict[str, Any], drivers: dict[str, Any]) -> dict[str, Any]:
    """Return a compact, API-ready summary without demographic counts."""
    record = feature["properties"]
    driver_by_id = {driver["id"]: driver for driver in drivers["drivers"]}
    return {
        "canonical_street_key": record["canonical_street_key"],
        "directed_segment_ids": record["directed_segment_ids"],
        "risk_score": record["risk_score"],
        "risk_class": record["risk_class"],
        "exposure_value": record["exposure_value"],
        "shade_fraction": record["shade_fraction"],
        "vulnerability_value": record["vulnerability_value"],
        "solar_exposure_level": driver_by_id["solar_exposure"]["level"],
        "shade_level": driver_by_id["shade"]["level"],
        "vulnerability_level": driver_by_id["vulnerability"]["level"],
        "cooling_access_level": driver_by_id["cooling_access_penalty"]["level"],
        "access_penalty": record["access_penalty"],
        "water_available": record["water_available"],
        "cooling_available": record["cooling_available"],
        "final_risk_raw": record["final_risk_raw"],
    }


def explain_segment_snapshot(
    snapshot: dict[str, Any],
    segment_id: str,
    street_name: str | None = None,
) -> dict[str, Any] | None:
    """Build the shared WHY payload from one already selected risk snapshot."""
    feature = find_canonical_feature(snapshot.get("features", []), segment_id)
    if feature is None:
        return None
    drivers = build_risk_drivers(feature["properties"])
    summary = street_summary(feature, drivers)
    summary["street_name"] = street_name
    status = "Interpolated" if snapshot["metadata"]["modelled_or_interpolated"] == "INTERPOLATED" else "Modelled"
    return {
        "requested_time": snapshot["metadata"].get("requested_time") or snapshot["metadata"].get("canonical_time"),
        "street": summary,
        "drivers": drivers["drivers"],
        "dominant_driver_ids": drivers["dominant_driver_ids"],
        "primary_drivers_sentence": drivers["primary_drivers_sentence"],
        "status_labels": ["Observed", "Estimated", status],
        "status_label_details": {
            "Observed": "Street geometry and any recorded OSM facility data.",
            "Estimated": "Density-based vulnerability proxy; not a population count.",
            status: "Cached model output." if status == "Modelled" else "Estimated between cached model snapshots.",
        },
        "provenance": {
            "observed_or_estimated": feature["properties"]["observed_or_estimated"],
            "modelled_or_interpolated": feature["properties"]["modelled_or_interpolated"],
            "computation_mode": feature["properties"]["computation_mode"],
            "assumptions_version": feature["properties"]["assumptions_version"],
        },
    }


def rank_hottest_and_highest_risk(features: list[dict[str, Any]]) -> dict[str, Any]:
    """Rank de-duplicated records with documented deterministic tie-breaking."""
    hottest_value = max(float(feature["properties"]["exposure_value"]) for feature in features)
    highest_risk_value = max(float(feature["properties"]["risk_score"]) for feature in features)
    hottest_ties = [feature for feature in features if abs(float(feature["properties"]["exposure_value"]) - hottest_value) <= 1e-12]
    risk_ties = [feature for feature in features if abs(float(feature["properties"]["risk_score"]) - highest_risk_value) <= 1e-12]
    hottest = sorted(hottest_ties, key=lambda feature: feature["properties"]["canonical_street_key"])[0]
    highest_risk = sorted(risk_ties, key=lambda feature: (-float(feature["properties"]["exposure_value"]), feature["properties"]["canonical_street_key"]))[0]
    hottest_scores = [float(feature["properties"]["risk_score"]) for feature in hottest_ties]
    return {
        "hottest": hottest,
        "highest_risk": highest_risk,
        "hottest_tie_count": len(hottest_ties),
        "hottest_tie_risk_score_min": min(hottest_scores),
        "hottest_tie_risk_score_max": max(hottest_scores),
        "highest_risk_tie_count": len(risk_ties),
    }
