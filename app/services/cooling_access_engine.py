"""Cache-based water/cooling access penalties with no invented facilities."""

from __future__ import annotations

from heapq import heappop, heappush
from typing import Any

import geopandas as gpd
from shapely.geometry import Point

from app.config import AppConfig, get_config
from app.services.data_engine import project_to_metric_crs


def bounded_distance_penalty(distance_m: float | None, service_radius_m: float) -> float:
    """Convert a walking distance to a monotonic bounded access penalty."""
    if distance_m is None:
        return 1.0
    return max(0.0, min(1.0, distance_m / service_radius_m))


def _line_endpoints(geometry: Any) -> tuple[Point, Point, float]:
    """Return endpoints for a line, choosing the longest part if it is multi-part."""
    line = max(geometry.geoms, key=lambda part: part.length) if geometry.geom_type == "MultiLineString" else geometry
    coordinates = list(line.coords)
    return Point(coordinates[0]), Point(coordinates[-1]), float(line.length)


def _node_key(point: Point) -> tuple[float, float]:
    # Projected OSM endpoints use stable two-decimal metre coordinates.
    return (round(point.x, 2), round(point.y, 2))


def _walking_distances_to_facilities(streets: gpd.GeoDataFrame, facilities: gpd.GeoDataFrame) -> list[float | None]:
    """Find nearest-facility walking paths on the cached street-segment graph.

    A facility is snapped to its nearest observed network endpoint. A segment is
    evaluated from its midpoint, with half its observed length added before the
    shortest graph path. A disconnected path is unavailable rather than guessed.
    """
    if facilities.empty:
        return [None] * len(streets)

    adjacency: dict[tuple[float, float], list[tuple[tuple[float, float], float]]] = {}
    node_points: dict[tuple[float, float], Point] = {}
    segment_endpoints: list[tuple[tuple[float, float], tuple[float, float], float]] = []
    for geometry in streets.geometry:
        start, end, length = _line_endpoints(geometry)
        start_key, end_key = _node_key(start), _node_key(end)
        node_points[start_key], node_points[end_key] = start, end
        adjacency.setdefault(start_key, []).append((end_key, length))
        adjacency.setdefault(end_key, []).append((start_key, length))
        segment_endpoints.append((start_key, end_key, length))

    distances = {node: float("inf") for node in adjacency}
    queue: list[tuple[float, tuple[float, float]]] = []
    for facility_geometry in facilities.geometry:
        facility_point = facility_geometry.centroid if facility_geometry.geom_type != "Point" else facility_geometry
        nearest_node = min(node_points, key=lambda node: facility_point.distance(node_points[node]))
        initial_distance = float(facility_point.distance(node_points[nearest_node]))
        if initial_distance < distances[nearest_node]:
            distances[nearest_node] = initial_distance
            heappush(queue, (initial_distance, nearest_node))
    while queue:
        current_distance, node = heappop(queue)
        if current_distance != distances[node]:
            continue
        for neighbour, edge_length in adjacency[node]:
            candidate = current_distance + edge_length
            if candidate < distances[neighbour]:
                distances[neighbour] = candidate
                heappush(queue, (candidate, neighbour))

    result: list[float | None] = []
    for start, end, length in segment_endpoints:
        best = min(distances[start], distances[end])
        result.append(None if best == float("inf") else best + (length / 2))
    return result


def build_cooling_access_records(config: AppConfig | None = None) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    """Calculate straight-line-derived walking distances for water and cooling only."""
    active_config = config or get_config()
    streets = project_to_metric_crs(gpd.read_file(active_config.cache_data_dir / "streets.geojson"))
    facilities = gpd.read_file(active_config.cache_data_dir / "facilities.geojson").to_crs(streets.crs)
    water = facilities[facilities.get("facility_type").eq("water")].copy()
    cooling = facilities[facilities.get("facility_type").eq("cooling")].copy()

    water_distances = _walking_distances_to_facilities(streets, water)
    cooling_distances = _walking_distances_to_facilities(streets, cooling)

    records: dict[str, dict[str, Any]] = {}
    for position, (_, street) in enumerate(streets.iterrows()):
        water_distance = water_distances[position]
        cooling_distance = cooling_distances[position]
        water_penalty = bounded_distance_penalty(water_distance, active_config.water_service_radius_m)
        cooling_penalty = bounded_distance_penalty(cooling_distance, active_config.cooling_service_radius_m)
        access_penalty = max(0.0, min(1.0, (
            active_config.access_penalty_weights["water"] * water_penalty
            + active_config.access_penalty_weights["cooling"] * cooling_penalty
        )))
        records[street["segment_id"]] = {
            "distance_to_water_m": water_distance,
            "distance_to_cooling_m": cooling_distance,
            "water_access_penalty": water_penalty,
            "cooling_access_penalty": cooling_penalty,
            "access_penalty": access_penalty,
            "water_available": water_distance is not None,
            "cooling_available": cooling_distance is not None,
            "source_type": "derived",
            "source_reference": "Cached OSM water/cooling facilities only; healthcare excluded.",
            "observed_or_estimated": "ESTIMATED",
        }
    return records, {
        "water_facility_count": len(water),
        "cooling_facility_count": len(cooling),
        "healthcare_facility_count": int(facilities.get("facility_type").eq("healthcare").sum()),
        "walking_distance_factor": active_config.walking_distance_factor,
        "walking_distance_label": active_config.walking_distance_label,
    }
