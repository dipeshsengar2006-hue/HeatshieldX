"""Cache-only safe-stop selection for a computed route."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import geopandas as gpd
import networkx as nx
from shapely.geometry import LineString, Point, shape

from app.config import AppConfig
from app.repositories.cache import load_cached_geojson

if TYPE_CHECKING:
    from app.services.routing_engine import PathResult, RouteGraph


def _metric_geometry(geometry: Any, metric_crs: str) -> Any:
    return gpd.GeoSeries([geometry], crs="EPSG:4326").to_crs(metric_crs).iloc[0]


def _amenities(properties: dict[str, Any]) -> list[str]:
    value = properties.get("amenities", "[]")
    try:
        parsed = json.loads(value) if isinstance(value, str) else value
    except json.JSONDecodeError:
        return []
    return [str(item) for item in parsed] if isinstance(parsed, list) else []


def find_safe_stops(graph: RouteGraph, path: PathResult, config: AppConfig) -> dict[str, Any]:
    """Return eligible cached OSM stops without contacting external services."""
    try:
        features = load_cached_geojson("stops", config).get("features", [])
    except FileNotFoundError:
        return {"status": "No stop data available", "items": []}

    route_points = [graph.metric_nodes[node] for node in path.nodes]
    route_geometry = LineString(route_points) if len(route_points) > 1 else route_points[0]
    route_node_set = set(path.nodes)
    undirected_graph = graph.graph.to_undirected()
    candidates: list[dict[str, Any]] = []

    for feature in features:
        properties = feature.get("properties", {})
        if properties.get("stop_type") not in config.stop_type_priority:
            continue
        source_geometry = shape(feature["geometry"])
        source_point = source_geometry if source_geometry.geom_type == "Point" else source_geometry.centroid
        metric_point = _metric_geometry(source_point, graph.metric_crs)
        route_distance = float(metric_point.distance(route_geometry))
        if route_distance > config.stop_max_route_distance_m:
            continue
        stop_node = min(graph.metric_nodes, key=lambda node: metric_point.distance(graph.metric_nodes[node]))
        distances = nx.single_source_dijkstra_path_length(undirected_graph, stop_node, weight="length_m")
        route_distances = [distances[node] for node in route_node_set if node in distances]
        if not route_distances:
            continue
        network_distance = min(route_distances)
        stop_type = str(properties["stop_type"])
        name = properties.get("name")
        display_name = name.strip() if isinstance(name, str) and name.strip() else f"Unnamed {stop_type}"
        relevance = max(0.0, min(1.0, 1 - route_distance / config.stop_max_route_distance_m))
        candidates.append({
            "stop_id": str(properties["stop_id"]),
            "stop_type": stop_type,
            "name": display_name,
            "location": {"type": "Point", "coordinates": [float(source_point.x), float(source_point.y)]},
            "route_distance": route_distance,
            "detour_distance": 2 * float(network_distance),
            "verified_status": "Unverified (OSM)",
            "amenities": _amenities(properties),
            "rating": None,
            "rating_label": "Rating unavailable",
            "sponsored_status": properties.get("sponsored_status") is True,
            "route_relevance": relevance,
            "provenance": {
                "source_type": properties.get("source_type", "osm"),
                "source_reference": properties.get("source_reference", "OpenStreetMap via OSMnx"),
                "observed_or_estimated": properties.get("observed_or_estimated", "OBSERVED"),
                "modelled_or_interpolated": "MODELLED",
                "assumptions_version": config.version,
                "computation_mode": config.computation_mode,
            },
        })

    candidates.sort(
        key=lambda item: (
            -item["route_relevance"],
            config.stop_type_priority[item["stop_type"]],
            item["detour_distance"],
            item["stop_id"],
        )
    )
    return {
        "status": "Available" if candidates else "No eligible stops recorded in OSM along this route",
        "items": candidates[: config.stop_max_results],
    }
