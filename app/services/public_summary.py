"""Public citizen summary computed only from the configured cached datasets."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import geopandas as gpd
from shapely.geometry import Point

from app.config import AppConfig, get_config
from app.i18n import CITIZEN_EN
from app.repositories.cache import load_cached_geojson, load_exposure_snapshot, load_risk_snapshot
from app.services.data_engine import project_to_metric_crs


@dataclass
class PublicSummaryError(ValueError):
    """A citizen summary cannot be produced from the current cached inputs."""

    message_id: str
    english_text: str
    message_params: dict[str, Any]


def _peak_window(config: AppConfig) -> tuple[str, str]:
    means: list[tuple[str, float]] = []
    for canonical_time in config.canonical_times:
        snapshot = load_exposure_snapshot(canonical_time, config)
        values = [float(feature["properties"]["exposure_value"]) for feature in snapshot.get("features", [])]
        if not values:
            raise PublicSummaryError("summary_error", "Summary data is unavailable for this location.", {})
        means.append((canonical_time, sum(values) / len(values)))
    maximum = max(value for _, value in means)
    threshold = maximum * config.peak_window_ratio
    peak_times = [time for time, value in means if value >= threshold]
    return peak_times[0], peak_times[-1]


def _risk_values_for_time(segment_id: str, time_value: str, config: AppConfig) -> tuple[dict[str, float | None], str]:
    try:
        hour, minute = (int(part) for part in time_value.split(":"))
    except (AttributeError, ValueError) as exc:
        raise PublicSummaryError("route_error_422", "Time must use 24-hour HH:MM format.", {}) from exc
    requested = hour * 60 + minute
    canonical_minutes = [int(item[:2]) * 60 + int(item[3:]) for item in config.canonical_times]
    if not 0 <= hour <= 23 or not 0 <= minute <= 59 or requested < canonical_minutes[0] or requested > canonical_minutes[-1]:
        raise PublicSummaryError("route_error_422", "Time must be between 09:00 and 17:00 in HH:MM format.", {})
    if time_value in config.canonical_times:
        lower_time = upper_time = time_value
        ratio = 0.0
        status = "MODELLED"
    else:
        upper_index = next((i for i, value in enumerate(canonical_minutes) if value > requested), None)
        if upper_index is None:
            raise PublicSummaryError("route_error_422", "Time must be between 09:00 and 17:00.", {})
        lower_time, upper_time = config.canonical_times[upper_index - 1], config.canonical_times[upper_index]
        ratio = (requested - canonical_minutes[upper_index - 1]) / (canonical_minutes[upper_index] - canonical_minutes[upper_index - 1])
        status = "INTERPOLATED"

    def find_values(canonical_time: str) -> dict[str, Any]:
        risk = load_risk_snapshot(canonical_time, config)
        feature = next((item for item in risk.get("features", []) if item.get("properties", {}).get("segment_id") == segment_id), None)
        if feature is None:
            raise PublicSummaryError("summary_error", "Summary data is unavailable for this location.", {})
        return feature["properties"]

    lower = find_values(lower_time)
    upper = find_values(upper_time) if upper_time != lower_time else lower
    result: dict[str, float | None] = {}
    for name in ("exposure_value", "distance_to_water_m", "distance_to_cooling_m"):
        left, right = lower.get(name), upper.get(name)
        if left is None or right is None:
            result[name] = None
        else:
            left_value, right_value = float(left), float(right)
            result[name] = left_value + (right_value - left_value) * ratio
    return result, status


def _message_field(value: Any, message_id: str, params: dict[str, Any], status: str) -> dict[str, Any]:
    status_message_id = {
        "MODELLED": "summary_status_modelled",
        "ESTIMATED": "summary_status_estimated",
        "INTERPOLATED": "summary_status_interpolated",
    }[status]
    return {
        "value": value,
        "message_id": message_id,
        "message_params": params,
        "english_text": CITIZEN_EN[message_id].format(**params),
        "status": status,
        "status_message_id": status_message_id,
        "status_message_params": {},
        "status_english_text": CITIZEN_EN[status_message_id],
    }


def public_summary(latitude: float, longitude: float, time_value: str, config: AppConfig | None = None) -> dict[str, Any]:
    """Summarize one snapped street and the area peak window without retaining coordinates."""
    active_config = config or get_config()
    streets_data = load_cached_geojson("streets", active_config)
    features = streets_data.get("features", [])
    if not features:
        raise PublicSummaryError("summary_error", "Summary data is unavailable for this location.", {})

    source = gpd.GeoDataFrame.from_features(features, crs="EPSG:4326")
    metric = project_to_metric_crs(source)
    requested_wgs84 = Point(longitude, latitude)
    requested_metric = gpd.GeoSeries([requested_wgs84], crs="EPSG:4326").to_crs(metric.crs).iloc[0]
    center_metric = gpd.GeoSeries(
        [Point(active_config.demo_area.center_lon, active_config.demo_area.center_lat)], crs="EPSG:4326"
    ).to_crs(metric.crs).iloc[0]
    if requested_metric.distance(center_metric) > active_config.demo_area.radius_m:
        raise PublicSummaryError("summary_error_area", "Location is outside the configured demo area.", {})

    candidates = [
        (float(row.geometry.distance(requested_metric)), str(row.get("segment_id", "")), index)
        for index, row in metric.iterrows()
    ]
    distance_m, segment_id, _position = min(candidates, key=lambda item: (item[0], item[1]))
    if not math.isfinite(distance_m) or distance_m > active_config.snap_max_distance_m:
        raise PublicSummaryError("summary_error_area", "Location is too far from a mapped street.", {})

    values, status = _risk_values_for_time(segment_id, time_value, active_config)
    exposure_value = values["exposure_value"]
    if exposure_value is None:
        raise PublicSummaryError("summary_error", "Summary data is unavailable for this location.", {})
    exposure_score = max(0.0, min(100.0, float(exposure_value) * 100))
    low_max = active_config.risk_class_ranges["LOW"][1]
    moderate_max = active_config.risk_class_ranges["MODERATE"][1]
    if exposure_score <= low_max:
        level, level_id = "LOW", "summary_level_low"
    elif exposure_score <= moderate_max:
        level, level_id = "MODERATE", "summary_level_moderate"
    else:
        level, level_id = "HIGH", "summary_level_high"

    peak_start, peak_end = _peak_window(active_config)
    peak_status = "MODELLED"
    peak_field = _message_field(
        None,
        "summary_peak_window",
        {"start_time": peak_start, "end_time": peak_end},
        peak_status,
    )
    peak_field["value"] = {"start_time": peak_start, "end_time": peak_end}
    peak_field["english_text"] = CITIZEN_EN["summary_peak_window"].format(start_time=peak_start, end_time=peak_end)

    def distance_field(value: float | None) -> dict[str, Any]:
        if value is None:
            return _message_field(None, "summary_data_unavailable", {}, "ESTIMATED")
        rounded = int(round(value))
        return _message_field(rounded, "summary_distance", {"value": rounded}, "ESTIMATED")

    return {
        "exposure_level": _message_field(level, level_id, {}, status),
        "peak_window": peak_field,
        "distance_to_water": distance_field(values["distance_to_water_m"]),
        "distance_to_cooling": distance_field(values["distance_to_cooling_m"]),
        "street_snap": _message_field(round(distance_m, 1), "summary_distance", {"value": round(distance_m, 1)}, "ESTIMATED"),
        "time_status": _message_field(status, {
            "MODELLED": "summary_status_modelled",
            "INTERPOLATED": "summary_status_interpolated",
        }[status], {}, status),
        "metadata": {
            "computation_mode": active_config.computation_mode,
            "config_version": active_config.version,
            "source_type": "cached OSM street and exposure/risk snapshots",
            "computation_mode_message_id": "mode_estimated" if active_config.computation_mode == "FALLBACK" else "mode_geometric",
            "computation_mode_message_params": {},
        },
    }
