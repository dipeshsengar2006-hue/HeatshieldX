"""Deterministic proposed-intervention, greedy-plan, and impact calculations."""

from __future__ import annotations

import json
import math
import time
from dataclasses import dataclass
from typing import Any

import geopandas as gpd
import numpy as np
from shapely.geometry import Point, shape

from app.config import AppConfig, get_config
from app.repositories.cache import load_cached_geojson, load_cached_plan, load_risk_snapshot, store_cached_plan
from app.services.cooling_access_engine import (
    WalkingNetwork,
    bounded_distance_penalty,
    build_walking_network,
    walking_distances_from_points,
)
from app.services.data_engine import project_to_metric_crs
from app.services.explainability_engine import deduplicate_risk_features
from app.services.exposure_engine import geometric_exposure_value, temperature_factor
from app.services.risk_engine import baseline_risk, final_risk_raw, normalize_with_bounds, risk_class


RESOURCE_TYPES = ("water_points", "cooling_centres", "shade_structures")
_TYPE_LABELS = {
    "water_points": "Water point",
    "cooling_centres": "Cooling centre",
    "shade_structures": "Shade structure",
}


@dataclass
class OptimizationContext:
    config: AppConfig
    streets: dict[str, dict[str, Any]]
    snapshots: dict[str, dict[str, Any]]
    baseline_min: float
    baseline_max: float
    candidates: dict[str, dict[str, Any]]
    location_distances: dict[str, dict[str, float | None]]


_CONTEXTS: dict[tuple[str, float], OptimizationContext] = {}
_PLAN_CACHE: dict[str, dict[str, Any]] = {}


def _config_key(config: AppConfig) -> str:
    """Return a stable key for reusable coverage structures.

    Candidate coverage is geometry-dependent, but a context also retains the
    configuration consumed by scenario evaluation.  Include the full
    serialised configuration so a caller changing a documented coefficient
    cannot accidentally reuse a context with stale assumptions.
    """
    return json.dumps(config.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))


def _is_current_plan_cache(plan: dict[str, Any]) -> bool:
    """Reject older on-disk plan payloads after a backwards-compatible schema addition."""
    return isinstance(plan.get("metrics"), dict) and all(
        "share_of_total_reduction" in priority for priority in plan.get("priorities", [])
    )


def _street_name_map() -> dict[str, str | None]:
    names: dict[str, str | None] = {}
    for feature in load_cached_geojson("streets")["features"]:
        properties = feature["properties"]
        try:
            value = json.loads(properties.get("road_metadata", "{}"))
            name = value.get("name")
        except (TypeError, json.JSONDecodeError):
            name = None
        names[properties["segment_id"]] = name.strip() if isinstance(name, str) and name.strip() else None
    return names


def _candidate_id(resource_type: str, canonical_key: str) -> str:
    return f"{resource_type}:{canonical_key}"


def _build_context(config: AppConfig) -> OptimizationContext:
    snapshots: dict[str, dict[str, Any]] = {}
    streets: dict[str, dict[str, Any]] = {}
    for canonical_time in config.canonical_times:
        source = load_risk_snapshot(canonical_time, config)
        features, _report = deduplicate_risk_features(source["features"])
        snapshots[canonical_time] = {feature["properties"]["canonical_street_key"]: feature for feature in features}
        if canonical_time == config.canonical_times[0]:
            for feature in features:
                properties = feature["properties"]
                streets[properties["canonical_street_key"]] = {
                    "canonical_street_key": properties["canonical_street_key"],
                    "segment_id": properties["segment_id"],
                    "directed_segment_ids": properties["directed_segment_ids"],
                    "length_m": float(properties["length_m"]),
                    "geometry": feature["geometry"],
                }
    metadata = load_risk_snapshot(config.canonical_times[0], config)["metadata"]
    baseline_min = float(metadata["global_final_risk_raw_min"])
    baseline_max = float(metadata["global_final_risk_raw_max"])
    names = _street_name_map()

    # Water and cooling proposals need a sufficiently long street midpoint;
    # shade is a direct street intervention and remains available on every
    # canonical street under the explicit prototype assumption.
    facility_candidate_keys = {
        key for key, street in streets.items() if street["length_m"] >= config.candidate_min_street_length_m
    }
    candidate_streets = sorted(streets.values(), key=lambda street: street["canonical_street_key"])
    candidate_gdf = gpd.GeoDataFrame(
        candidate_streets,
        geometry=[shape(street["geometry"]) for street in candidate_streets],
        crs="EPSG:4326",
    ).to_crs("EPSG:32643")
    candidates: dict[str, dict[str, Any]] = {}
    points_metric: dict[str, Point] = {}
    for (_, row), street in zip(candidate_gdf.iterrows(), candidate_streets, strict=True):
        midpoint = row.geometry.interpolate(0.5, normalized=True)
        point_wgs84 = gpd.GeoSeries([midpoint], crs=candidate_gdf.crs).to_crs("EPSG:4326").iloc[0]
        location_id = f"location:{street['canonical_street_key']}"
        points_metric[location_id] = midpoint
        resource_types = ("shade_structures",)
        if street["canonical_street_key"] in facility_candidate_keys:
            resource_types = RESOURCE_TYPES
        for resource_type in resource_types:
            candidate_id = _candidate_id(resource_type, street["canonical_street_key"])
            candidates[candidate_id] = {
                "candidate_id": candidate_id,
                "type": resource_type,
                "street_canonical_key": street["canonical_street_key"],
                "street_name": next((names.get(segment_id) for segment_id in street["directed_segment_ids"] if names.get(segment_id)), None),
                "lat": float(point_wgs84.y),
                "lon": float(point_wgs84.x),
                "location_id": location_id,
                "provenance": {
                    "source_type": "proposed candidate",
                    "source_reference": "Midpoint of a cached canonical street; not an existing OSM facility.",
                    "observed_or_estimated": "ESTIMATED",
                    "modelled_or_interpolated": "MODELLED",
                    "assumptions_version": config.version,
                    "label": config.optimization_assumption_label,
                },
            }

    directed_streets = project_to_metric_crs(gpd.read_file(config.cache_data_dir / "streets.geojson"))
    network: WalkingNetwork = build_walking_network(directed_streets)
    directed_positions = {str(segment_id): position for position, segment_id in enumerate(directed_streets["segment_id"])}
    location_distances: dict[str, dict[str, float | None]] = {}
    for location_id, point in points_metric.items():
        directed_distances = walking_distances_from_points(network, [point])
        location_distances[location_id] = {
            key: directed_distances[directed_positions[street["segment_id"]]]
            for key, street in streets.items()
        }
    return OptimizationContext(config, streets, snapshots, baseline_min, baseline_max, candidates, location_distances)


def get_optimization_context(config: AppConfig | None = None) -> OptimizationContext:
    active_config = config or get_config()
    key = _config_key(active_config)
    if key not in _CONTEXTS:
        _CONTEXTS[key] = _build_context(active_config)
    return _CONTEXTS[key]


def list_candidates(config: AppConfig | None = None) -> dict[str, Any]:
    context = get_optimization_context(config)
    return {
        "label": "Modelled proposed candidates; not existing facilities.",
        "config_version": context.config.version,
        "candidate_count": len(context.candidates),
        "candidates": [context.candidates[candidate_id] for candidate_id in sorted(context.candidates)],
    }


def validate_resource_counts(values: dict[str, int | None], config: AppConfig | None = None) -> dict[str, int]:
    active_config = config or get_config()
    resolved: dict[str, int] = {}
    for resource_type in RESOURCE_TYPES:
        value = values.get(resource_type)
        value = active_config.default_resource_counts[resource_type] if value is None else value
        if isinstance(value, bool) or not isinstance(value, int) or value < 0 or value > active_config.max_resource_count_per_type:
            raise ValueError(
                f"{resource_type} must be an integer from 0 to {active_config.max_resource_count_per_type}."
            )
        resolved[resource_type] = value
    return resolved


def plan_id_for(counts: dict[str, int], config: AppConfig | None = None) -> str:
    active_config = config or get_config()
    return f"w{counts['water_points']}-c{counts['cooling_centres']}-s{counts['shade_structures']}-{active_config.version}"


def parse_plan_id(plan_id: str, config: AppConfig | None = None) -> dict[str, int]:
    active_config = config or get_config()
    prefix = "w"
    if not plan_id.startswith(prefix) or not plan_id.endswith(f"-{active_config.version}"):
        raise ValueError("Unknown plan_id for the active configuration.")
    counts_part = plan_id[: -(len(active_config.version) + 1)]
    try:
        water, cooling, shade = counts_part.split("-")
        counts = {
            "water_points": int(water.removeprefix("w")),
            "cooling_centres": int(cooling.removeprefix("c")),
            "shade_structures": int(shade.removeprefix("s")),
        }
    except (TypeError, ValueError) as exc:
        raise ValueError("plan_id must use w<count>-c<count>-s<count>-<config-version>.") from exc
    return validate_resource_counts(counts, active_config)


def _minimum_distance(values: list[float | None]) -> float | None:
    available = [value for value in values if value is not None]
    return min(available) if available else None


def _selected_distances(context: OptimizationContext, selected: list[str], resource_type: str, key: str, baseline_distance: float | None) -> float | None:
    proposed = [
        context.location_distances[context.candidates[candidate_id]["location_id"]][key]
        for candidate_id in selected
        if context.candidates[candidate_id]["type"] == resource_type
    ]
    return _minimum_distance([baseline_distance, *proposed])


def _scenario(context: OptimizationContext, selected: list[str], *, include_features: bool) -> dict[str, Any]:
    config = context.config
    shade_targets = {
        context.candidates[candidate_id]["street_canonical_key"]
        for candidate_id in selected
        if context.candidates[candidate_id]["type"] == "shade_structures"
    }
    shade_increase = config.shade_structure_shade_increase * config.intervention_effect_coefficients["shade_structure"]
    objective = 0.0
    snapshots: dict[str, dict[str, Any]] = {}
    access_by_street: dict[str, dict[str, float | None]] = {}
    for canonical_time, baseline_features in context.snapshots.items():
        after_features: list[dict[str, Any]] = []
        for key in sorted(context.streets):
            baseline_feature = baseline_features[key]
            baseline = baseline_feature["properties"]
            shade = float(baseline["shade_fraction"])
            exposure = float(baseline["exposure_value"])
            if key in shade_targets:
                shade = min(1.0, shade + shade_increase)
                exposure = geometric_exposure_value(1.0 - shade, temperature_factor(config, canonical_time), config)
            water_distance = _selected_distances(context, selected, "water_points", key, baseline["distance_to_water_m"])
            cooling_distance = _selected_distances(context, selected, "cooling_centres", key, baseline["distance_to_cooling_m"])
            water_penalty = bounded_distance_penalty(water_distance, config.water_service_radius_m)
            cooling_penalty = bounded_distance_penalty(cooling_distance, config.cooling_service_radius_m)
            access_penalty = max(0.0, min(1.0, (
                config.access_penalty_weights["water"] * water_penalty
                + config.access_penalty_weights["cooling"] * cooling_penalty
            )))
            vulnerability = float(baseline["vulnerability_value"])
            raw = final_risk_raw(baseline_risk(exposure, vulnerability), access_penalty)
            objective += context.streets[key]["length_m"] * raw
            if canonical_time == config.canonical_times[0]:
                access_by_street[key] = {"water": water_distance, "cooling": cooling_distance}
            if include_features:
                properties = {
                    **baseline,
                    "shade_fraction": shade,
                    "direct_exposure_fraction": 1.0 - shade,
                    "exposure_value": exposure,
                    "distance_to_water_m": water_distance,
                    "distance_to_cooling_m": cooling_distance,
                    "water_access_penalty": water_penalty,
                    "cooling_access_penalty": cooling_penalty,
                    "access_penalty": access_penalty,
                    "water_available": water_distance is not None,
                    "cooling_available": cooling_distance is not None,
                    "baseline_risk": baseline_risk(exposure, vulnerability),
                    "final_risk_raw": raw,
                    "risk_score": normalize_with_bounds(raw, context.baseline_min, context.baseline_max),
                    "risk_class": risk_class(normalize_with_bounds(raw, context.baseline_min, context.baseline_max)),
                    "modelled_or_interpolated": "MODELLED",
                    "intervention_scenario": "Modelled",
                }
                after_features.append({"type": "Feature", "properties": properties, "geometry": baseline_feature["geometry"]})
        if include_features:
            snapshots[canonical_time] = {
                "type": "FeatureCollection",
                "features": after_features,
                "metadata": {
                    "canonical_time": canonical_time,
                    "modelled_or_interpolated": "MODELLED",
                    "observed_or_estimated": "ESTIMATED",
                    "interpolated": False,
                    "config_version": config.version,
                    "normalization_method": config.risk_normalization_method,
                    "normalization_scope": config.risk_normalization_scope,
                    "global_final_risk_raw_min": context.baseline_min,
                    "global_final_risk_raw_max": context.baseline_max,
                    "intervention_scenario": "Modelled",
                },
            }
    return {"objective": objective, "snapshots": snapshots, "access_by_street": access_by_street}


def _weighted_share(context: OptimizationContext, covered: set[str]) -> float:
    denominator = sum(street["length_m"] * float(context.snapshots[context.config.canonical_times[0]][key]["properties"]["vulnerability_value"]) for key, street in context.streets.items())
    numerator = sum(context.streets[key]["length_m"] * float(context.snapshots[context.config.canonical_times[0]][key]["properties"]["vulnerability_value"]) for key in covered)
    return numerator / denominator if denominator else 0.0


def _metric(before: Any, after: Any, definition: str) -> dict[str, Any]:
    delta = after - before if isinstance(before, (int, float)) and isinstance(after, (int, float)) else None
    return {"before": before, "modelled_after": after, "delta": delta, "definition": definition, "label": "Modelled Impact"}


def _impact_metrics(context: OptimizationContext, selected: list[str], before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    config = context.config
    baseline_high_keys = {
        (canonical_time, key)
        for canonical_time, features in context.snapshots.items()
        for key, feature in features.items()
        if feature["properties"]["risk_class"] in {"HIGH", "CRITICAL"}
    }
    def high_objective(scenario: dict[str, Any]) -> float:
        return sum(
            context.streets[key]["length_m"] * float(feature["properties"]["final_risk_raw"])
            for canonical_time, snapshot in scenario["snapshots"].items()
            for feature in snapshot["features"]
            for key in [feature["properties"]["canonical_street_key"]]
            if (canonical_time, key) in baseline_high_keys
        )
    def coverage(access_key: str, radius: float, values: dict[str, dict[str, float | None]]) -> float:
        return _weighted_share(context, {key for key, record in values.items() if record[access_key] is not None and record[access_key] <= radius})
    def average(access_key: str, values: dict[str, dict[str, float | None]]) -> float | str:
        distances = [record[access_key] for record in values.values() if record[access_key] is not None]
        return sum(distances) / len(distances) if distances else "Data unavailable (no recorded facility)"

    proposed_water: dict[str, float | None] = {
        key: _minimum_distance([context.location_distances[context.candidates[candidate_id]["location_id"]][key] for candidate_id in selected if context.candidates[candidate_id]["type"] == "water_points"])
        for key in context.streets
    }
    proposed_cooling: dict[str, float | None] = {
        key: _minimum_distance([context.location_distances[context.candidates[candidate_id]["location_id"]][key] for candidate_id in selected if context.candidates[candidate_id]["type"] == "cooling_centres"])
        for key in context.streets
    }
    intervention_covered = {
        key for key in context.streets
        if (proposed_water[key] is not None and proposed_water[key] <= config.water_service_radius_m)
        or (proposed_cooling[key] is not None and proposed_cooling[key] <= config.cooling_service_radius_m)
        or any(context.candidates[candidate_id]["type"] == "shade_structures" and context.candidates[candidate_id]["street_canonical_key"] == key for candidate_id in selected)
    }
    before_counts = {name: sum(feature["properties"]["risk_class"] == name for feature in context.snapshots["15:00"].values()) for name in config.risk_class_ranges}
    after_counts = {name: sum(feature["properties"]["risk_class"] == name for feature in after["snapshots"]["15:00"]["features"]) for name in config.risk_class_ranges}
    return {
        "high_risk_vulnerable_exposure": _metric(high_objective(before), high_objective(after), "V restricted to baseline HIGH or CRITICAL streets across all five canonical times."),
        "cooling_coverage": _metric(coverage("cooling", config.cooling_service_radius_m, before["access_by_street"]), coverage("cooling", config.cooling_service_radius_m, after["access_by_street"]), "Vulnerability-weighted street length within the cooling service radius."),
        "water_coverage": _metric(coverage("water", config.water_service_radius_m, before["access_by_street"]), coverage("water", config.water_service_radius_m, after["access_by_street"]), "Vulnerability-weighted street length within the water service radius."),
        "average_network_distance_to_cooling": _metric(average("cooling", before["access_by_street"]), average("cooling", after["access_by_street"]), "Mean network distance to the nearest cooling facility; unavailable when none is recorded."),
        "average_network_distance_to_water": _metric(average("water", before["access_by_street"]), average("water", after["access_by_street"]), "Mean network distance to the nearest water facility; unavailable when none is recorded."),
        "intervention_coverage": _metric(0.0, _weighted_share(context, intervention_covered), "Vulnerability-weighted street length covered by at least one selected proposed intervention."),
        "streets_per_risk_class_15_00": _metric(before_counts, after_counts, "Canonical street counts by modelled prioritization class at 15:00, using baseline normalization bounds."),
    }


def _batch_candidate_objectives(context: OptimizationContext, selected: list[str], eligible: list[str]) -> dict[str, float]:
    """Score every next greedy choice with candidate × street × time NumPy arrays.

    This is intentionally a mathematical translation of ``_scenario``: cached
    risk inputs, configured coefficients, normalization bounds, and greedy
    ordering are unchanged.  Feature construction remains in ``_scenario`` so
    API payloads retain their established shape.
    """
    if not eligible:
        return {}
    keys = sorted(context.streets)
    key_index = {key: index for index, key in enumerate(keys)}
    times = context.config.canonical_times
    lengths = np.asarray([context.streets[key]["length_m"] for key in keys], dtype=float)
    vulnerability = np.asarray(
        [context.snapshots[times[0]][key]["properties"]["vulnerability_value"] for key in keys], dtype=float
    )
    shades = np.asarray(
        [[context.snapshots[time][key]["properties"]["shade_fraction"] for key in keys] for time in times], dtype=float
    )
    baseline_water = np.asarray(
        [context.snapshots[times[0]][key]["properties"]["distance_to_water_m"] for key in keys], dtype=object
    )
    baseline_cooling = np.asarray(
        [context.snapshots[times[0]][key]["properties"]["distance_to_cooling_m"] for key in keys], dtype=object
    )
    water_distances = np.asarray([float(value) if value is not None else np.inf for value in baseline_water], dtype=float)
    cooling_distances = np.asarray([float(value) if value is not None else np.inf for value in baseline_cooling], dtype=float)
    selected_shade_keys: set[str] = set()
    for candidate_id in selected:
        candidate = context.candidates[candidate_id]
        location_distances = np.asarray(
            [context.location_distances[candidate["location_id"]][key] for key in keys], dtype=object
        )
        proposed = np.asarray([float(value) if value is not None else np.inf for value in location_distances], dtype=float)
        if candidate["type"] == "water_points":
            water_distances = np.minimum(water_distances, proposed)
        elif candidate["type"] == "cooling_centres":
            cooling_distances = np.minimum(cooling_distances, proposed)
        else:
            selected_shade_keys.add(candidate["street_canonical_key"])
    shade_increase = context.config.shade_structure_shade_increase * context.config.intervention_effect_coefficients["shade_structure"]
    for key in selected_shade_keys:
        shades[:, key_index[key]] = np.minimum(1.0, shades[:, key_index[key]] + shade_increase)

    def raw_values(water: np.ndarray, cooling: np.ndarray, active_shades: np.ndarray) -> np.ndarray:
        water_penalty = np.clip(water / context.config.water_service_radius_m, 0.0, 1.0)
        cooling_penalty = np.clip(cooling / context.config.cooling_service_radius_m, 0.0, 1.0)
        access = np.clip(
            context.config.access_penalty_weights["water"] * water_penalty
            + context.config.access_penalty_weights["cooling"] * cooling_penalty,
            0.0,
            1.0,
        )
        factors = np.asarray([temperature_factor(context.config, time) for time in times], dtype=float)[:, None]
        exposure = np.clip(
            (1.0 - active_shades)
            * (context.config.exposure_direct_weight + context.config.exposure_temperature_weight * factors)
            * context.config.exposure_duration_factor,
            0.0,
            1.0,
        )
        return exposure * vulnerability[None, :] * (1.0 + access[None, :])

    current_raw = raw_values(water_distances, cooling_distances, shades)
    current_objective = float(np.sum(current_raw * lengths[None, :]))
    result: dict[str, float] = {}
    grouped: dict[str, list[str]] = {resource_type: [] for resource_type in RESOURCE_TYPES}
    for candidate_id in eligible:
        grouped[context.candidates[candidate_id]["type"]].append(candidate_id)

    for resource_type in ("water_points", "cooling_centres"):
        candidate_ids = grouped[resource_type]
        if not candidate_ids:
            continue
        distances = np.asarray(
            [
                [
                    float(context.location_distances[context.candidates[candidate_id]["location_id"]][key])
                    if context.location_distances[context.candidates[candidate_id]["location_id"]][key] is not None else np.inf
                    for key in keys
                ]
                for candidate_id in candidate_ids
            ],
            dtype=float,
        )
        if resource_type == "water_points":
            candidate_water = np.minimum(water_distances[None, :], distances)
            candidate_cooling = np.broadcast_to(cooling_distances, candidate_water.shape)
        else:
            candidate_cooling = np.minimum(cooling_distances[None, :], distances)
            candidate_water = np.broadcast_to(water_distances, candidate_cooling.shape)
        water_penalty = np.clip(candidate_water / context.config.water_service_radius_m, 0.0, 1.0)
        cooling_penalty = np.clip(candidate_cooling / context.config.cooling_service_radius_m, 0.0, 1.0)
        access = np.clip(
            context.config.access_penalty_weights["water"] * water_penalty
            + context.config.access_penalty_weights["cooling"] * cooling_penalty,
            0.0,
            1.0,
        )
        base_risk = np.clip(
            (1.0 - shades)
            * (context.config.exposure_direct_weight + context.config.exposure_temperature_weight * np.asarray([temperature_factor(context.config, time) for time in times])[:, None])
            * context.config.exposure_duration_factor,
            0.0,
            1.0,
        ) * vulnerability[None, :]
        objectives = np.sum(base_risk[None, :, :] * (1.0 + access[:, None, :]) * lengths[None, None, :], axis=(1, 2))
        result.update({candidate_id: float(objective) for candidate_id, objective in zip(candidate_ids, objectives, strict=True)})

    for candidate_id in grouped["shade_structures"]:
        key = context.candidates[candidate_id]["street_canonical_key"]
        index = key_index[key]
        if key in selected_shade_keys:
            result[candidate_id] = current_objective
            continue
        changed_shade = np.minimum(1.0, shades[:, index] + shade_increase)
        factors = np.asarray([temperature_factor(context.config, time) for time in times], dtype=float)
        changed_exposure = np.clip(
            (1.0 - changed_shade)
            * (context.config.exposure_direct_weight + context.config.exposure_temperature_weight * factors)
            * context.config.exposure_duration_factor,
            0.0,
            1.0,
        )
        water_penalty = np.clip(water_distances[index] / context.config.water_service_radius_m, 0.0, 1.0)
        cooling_penalty = np.clip(cooling_distances[index] / context.config.cooling_service_radius_m, 0.0, 1.0)
        access = np.clip(
            context.config.access_penalty_weights["water"] * water_penalty
            + context.config.access_penalty_weights["cooling"] * cooling_penalty,
            0.0,
            1.0,
        )
        old_total = float(np.sum(current_raw[:, index] * lengths[index]))
        new_total = float(np.sum(changed_exposure * vulnerability[index] * (1.0 + access) * lengths[index]))
        result[candidate_id] = current_objective - old_total + new_total
    return result


def optimize_resources(values: dict[str, int | None], config: AppConfig | None = None) -> dict[str, Any]:
    """Create a deterministic greedy ResourcePlan from cached baseline inputs."""
    active_config = config or get_config()
    counts = validate_resource_counts(values, active_config)
    plan_id = plan_id_for(counts, active_config)
    if config is None and plan_id in _PLAN_CACHE:
        return _PLAN_CACHE[plan_id]
    if config is None:
        cached_plan = load_cached_plan(plan_id, active_config)
        if cached_plan is not None and _is_current_plan_cache(cached_plan):
            _PLAN_CACHE[plan_id] = cached_plan
            return cached_plan
    started = time.perf_counter()
    context = get_optimization_context(active_config)
    before = _scenario(context, [], include_features=True)
    current = before
    selected: list[str] = []
    remaining = dict(counts)
    priorities: list[dict[str, Any]] = []
    while any(remaining.values()):
        eligible = [
            candidate_id for candidate_id in sorted(context.candidates)
            if remaining[context.candidates[candidate_id]["type"]] > 0 and candidate_id not in selected
        ]
        proposed_objectives = _batch_candidate_objectives(context, selected, eligible)
        evaluations = [
            (max(0.0, current["objective"] - proposed_objectives[candidate_id]), candidate_id)
            for candidate_id in eligible
        ]
        if not evaluations:
            break
        benefit, candidate_id = sorted(evaluations, key=lambda item: (-item[0], item[1]))[0]
        if benefit <= 0:
            break
        candidate = context.candidates[candidate_id]
        selected.append(candidate_id)
        remaining[candidate["type"]] -= 1
        priorities.append({
            "priority": len(priorities) + 1,
            "type": candidate["type"],
            "type_label": _TYPE_LABELS[candidate["type"]],
            "candidate_id": candidate_id,
            "street_canonical_key": candidate["street_canonical_key"],
            "street_name": candidate["street_name"],
            "lat": candidate["lat"],
            "lon": candidate["lon"],
            "marginal_benefit": benefit,
            "explanation": (
                f"Modelled {_TYPE_LABELS[candidate['type']].lower()} on {candidate['street_name'] or candidate['street_canonical_key']} "
                f"reduces the five-time vulnerable heat-exposure objective by {benefit:.3f}."
            ),
        })
        current = {"objective": proposed_objectives[candidate_id]}
    after = _scenario(context, selected, include_features=True)
    reduction = before["objective"] - after["objective"]
    for priority in priorities:
        priority["share_of_total_reduction"] = priority["marginal_benefit"] / reduction if reduction else 0.0
    plan = {
        "plan_id": plan_id,
        "label": "Modelled",
        "config_version": active_config.version,
        "scope": active_config.optimization_scope,
        "assumption_label": active_config.optimization_assumption_label,
        "requested_resources": counts,
        "remaining_resources": remaining,
        "priorities": priorities,
        "objective": {
            "before": before["objective"],
            "modelled_after": after["objective"],
            "total_reduction": reduction,
            "definition": "Sum of length_m × vulnerability × exposure × (1 + access_penalty) across canonical streets and all five canonical times.",
            "label": "Modelled",
        },
        "metrics": _impact_metrics(context, selected, before, after),
        "after_snapshots": after["snapshots"],
        "runtime_seconds": time.perf_counter() - started,
        "candidate_coverage_cached": True,
    }
    if config is None:
        _PLAN_CACHE[plan_id] = plan
        store_cached_plan(plan_id, plan, active_config)
    return plan


def get_plan(plan_id: str, config: AppConfig | None = None) -> dict[str, Any]:
    active_config = config or get_config()
    if config is None and plan_id in _PLAN_CACHE:
        return _PLAN_CACHE[plan_id]
    if config is None:
        cached_plan = load_cached_plan(plan_id, active_config)
        if cached_plan is not None and _is_current_plan_cache(cached_plan):
            _PLAN_CACHE[plan_id] = cached_plan
            return cached_plan
    return optimize_resources(parse_plan_id(plan_id, active_config), active_config if config is not None else None)
