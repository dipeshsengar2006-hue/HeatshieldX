"""Deterministic, cache-only heat-aware routing over directed OSM street segments."""

from __future__ import annotations

import json
import logging
import math
import time
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from heapq import heappop, heappush
from typing import Any, Callable

import geopandas as gpd
import networkx as nx
from shapely.geometry import LineString, Point, shape

from app.config import AppConfig, get_config
from app.i18n import CITIZEN_EN
from app.repositories.cache import load_cached_geojson, load_risk_snapshot
from app.services.data_engine import project_to_metric_crs
from app.services.stop_finder import find_safe_stops


LOGGER = logging.getLogger(__name__)
Node = tuple[float, float]


class RoutingError(ValueError):
    """A route request cannot be fulfilled from the fixed cached demo graph."""


@dataclass(frozen=True)
class RouteGraph:
    """Largest connected directed component of the cached OSM walking graph."""

    graph: nx.MultiDiGraph
    metric_nodes: dict[Node, Point]
    wgs84_nodes: dict[Node, Point]
    metric_crs: str
    outside_node_count: int
    outside_segment_count: int


@dataclass(frozen=True)
class PathResult:
    """Internal route result, retained only for the duration of one request."""

    route_type: str
    nodes: tuple[Node, ...]
    segment_ids: tuple[str, ...]
    length_m: float
    time_s: float
    heat_cost: float
    average_exposure: float
    weighted_shade: float
    average_access_penalty: float
    coordinates: tuple[tuple[float, float], ...]


_GRAPH_CACHE: dict[str, RouteGraph] = {}
_FIRST_ROUTE_REQUEST = True


def _node_key(point: Point) -> Node:
    """Use metric OSM endpoints as stable directed-graph node identities."""
    return (round(float(point.x), 3), round(float(point.y), 3))


def _line_coordinates(geometry: Any) -> list[tuple[float, float]]:
    line = max(geometry.geoms, key=lambda part: part.length) if geometry.geom_type == "MultiLineString" else geometry
    return [(float(x), float(y)) for x, y in line.coords]


def _metric_point_to_wgs84(point: Point, metric_crs: str) -> Point:
    return gpd.GeoSeries([point], crs=metric_crs).to_crs("EPSG:4326").iloc[0]


def build_route_graph(streets: dict[str, Any]) -> RouteGraph:
    """Build a directed graph from cached *directed* streets, keeping no canonical collapse."""
    features = streets.get("features", [])
    if not features:
        raise RoutingError("Cached street data is unavailable for routing.")
    source = gpd.GeoDataFrame.from_features(features, crs="EPSG:4326")
    metric = project_to_metric_crs(source)
    graph = nx.MultiDiGraph()
    metric_nodes: dict[Node, Point] = {}
    for (_, source_row), (_, metric_row) in zip(source.iterrows(), metric.iterrows(), strict=True):
        segment_id = str(source_row["segment_id"])
        metric_coordinates = _line_coordinates(metric_row.geometry)
        if len(metric_coordinates) < 2:
            continue
        start_metric, end_metric = Point(metric_coordinates[0]), Point(metric_coordinates[-1])
        start, end = _node_key(start_metric), _node_key(end_metric)
        metric_nodes[start], metric_nodes[end] = start_metric, end_metric
        length_m = float(source_row.get("length_m") or metric_row.geometry.length)
        graph.add_edge(
            start,
            end,
            key=segment_id,
            segment_id=segment_id,
            length_m=length_m,
            coordinates_wgs84=tuple(_line_coordinates(source_row.geometry)),
        )
    if not graph.edges:
        raise RoutingError("Cached street data has no routable directed segments.")

    components = list(nx.weakly_connected_components(graph))
    largest = min(
        (component for component in components if component),
        key=lambda component: (-len(component), tuple(sorted(component))),
    )
    outside_nodes = set(graph.nodes) - set(largest)
    outside_segments = sum(1 for start, end in graph.edges() if start in outside_nodes or end in outside_nodes)
    component_graph = graph.subgraph(largest).copy()
    component_metric_nodes = {node: metric_nodes[node] for node in component_graph.nodes}
    metric_crs = str(metric.crs)
    wgs84_nodes = {node: _metric_point_to_wgs84(point, metric_crs) for node, point in component_metric_nodes.items()}
    return RouteGraph(
        graph=component_graph,
        metric_nodes=component_metric_nodes,
        wgs84_nodes=wgs84_nodes,
        metric_crs=metric_crs,
        outside_node_count=len(outside_nodes),
        outside_segment_count=outside_segments,
    )


def get_route_graph(config: AppConfig | None = None) -> RouteGraph:
    """Reuse a process-local graph constructed only from the cached street file."""
    active_config = config or get_config()
    key = str(active_config.cache_data_dir / "streets.geojson")
    if key not in _GRAPH_CACHE:
        _GRAPH_CACHE[key] = build_route_graph(load_cached_geojson("streets", active_config))
    return _GRAPH_CACHE[key]


def _parse_time(value: str, config: AppConfig) -> tuple[int, bool, str | None, str | None, float]:
    try:
        hour, minute = (int(part) for part in value.split(":"))
    except (AttributeError, ValueError) as exc:
        raise RoutingError("time must use 24-hour HH:MM format.") from exc
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise RoutingError("time must use 24-hour HH:MM format.")
    requested = hour * 60 + minute
    canonical_minutes = [int(item[:2]) * 60 + int(item[3:]) for item in config.canonical_times]
    if requested < canonical_minutes[0] or requested > canonical_minutes[-1]:
        raise RoutingError("time must be between 09:00 and 17:00.")
    if value in config.canonical_times:
        return requested, False, value, value, 0.0
    upper_index = next(index for index, item in enumerate(canonical_minutes) if item > requested)
    lower, upper = config.canonical_times[upper_index - 1], config.canonical_times[upper_index]
    ratio = (requested - canonical_minutes[upper_index - 1]) / (canonical_minutes[upper_index] - canonical_minutes[upper_index - 1])
    return requested, True, lower, upper, ratio


def routing_snapshot(time_value: str, config: AppConfig | None = None) -> tuple[dict[str, dict[str, float]], dict[str, Any]]:
    """Return cached/interpolated routing attributes without recalculating risk or GIS data."""
    active_config = config or get_config()
    _requested, interpolated, lower_time, upper_time, ratio = _parse_time(time_value, active_config)
    assert lower_time and upper_time
    lower = load_risk_snapshot(lower_time, active_config)
    lower_by_segment = {feature["properties"]["segment_id"]: feature["properties"] for feature in lower["features"]}
    if not interpolated:
        values = {
            segment_id: {
                "exposure_value": float(properties["exposure_value"]),
                "shade_fraction": float(properties["shade_fraction"]),
                "access_penalty": float(properties["access_penalty"]),
            }
            for segment_id, properties in lower_by_segment.items()
        }
        metadata = lower["metadata"]
    else:
        upper = load_risk_snapshot(upper_time, active_config)
        upper_by_segment = {feature["properties"]["segment_id"]: feature["properties"] for feature in upper["features"]}
        if set(lower_by_segment) != set(upper_by_segment):
            raise RoutingError("Cached risk snapshots have inconsistent street segments. Rerun `python scripts/precompute_risk.py`.")
        values = {
            segment_id: {
                field: float(properties[field]) + (float(upper_by_segment[segment_id][field]) - float(properties[field])) * ratio
                for field in ("exposure_value", "shade_fraction", "access_penalty")
            }
            for segment_id, properties in lower_by_segment.items()
        }
        metadata = {**lower["metadata"], "interpolation_lower_time": lower_time, "interpolation_upper_time": upper_time}
    return values, {
        "requested_time": time_value,
        "interpolated": interpolated,
        "modelled_or_interpolated": "INTERPOLATED" if interpolated else "MODELLED",
        "modelled_or_interpolated_message_id": "summary_status_interpolated" if interpolated else "summary_status_modelled",
        "modelled_or_interpolated_message_params": {},
        "observed_or_estimated": "ESTIMATED",
        "observed_or_estimated_message_id": "summary_status_estimated",
        "observed_or_estimated_message_params": {},
        "computation_mode": metadata["computation_mode"],
        "computation_mode_message_id": "mode_estimated" if metadata["computation_mode"] == "FALLBACK" else "mode_geometric",
        "computation_mode_message_params": {},
        "config_version": metadata["config_version"],
    }


def _outside_demo_area(latitude: float, longitude: float, graph: RouteGraph, config: AppConfig) -> bool:
    center_wgs84 = Point(config.demo_area.center_lon, config.demo_area.center_lat)
    center_metric = gpd.GeoSeries([center_wgs84], crs="EPSG:4326").to_crs(graph.metric_crs).iloc[0]
    requested_metric = gpd.GeoSeries([Point(longitude, latitude)], crs="EPSG:4326").to_crs(graph.metric_crs).iloc[0]
    return requested_metric.distance(center_metric) > config.demo_area.radius_m


def snap_endpoint(latitude: float, longitude: float, graph: RouteGraph, config: AppConfig, label: str) -> tuple[Node, dict[str, Any]]:
    """Snap a transient request coordinate to the nearest graph node within the configured distance."""
    if _outside_demo_area(latitude, longitude, graph, config):
        raise RoutingError(f"{label} is outside the configured demo area.")
    point = gpd.GeoSeries([Point(longitude, latitude)], crs="EPSG:4326").to_crs(graph.metric_crs).iloc[0]
    node = min(graph.metric_nodes, key=lambda item: point.distance(graph.metric_nodes[item]))
    distance_m = float(point.distance(graph.metric_nodes[node]))
    if distance_m > config.snap_max_distance_m:
        raise RoutingError(f"{label} is more than {config.snap_max_distance_m:.0f} m from the cached walking network.")
    snapped = graph.wgs84_nodes[node]
    return node, {
        "lat": float(snapped.y),
        "lon": float(snapped.x),
        "snap_distance_m": distance_m,
    }


def _dijkstra(
    graph: RouteGraph,
    source: Node,
    target: Node,
    weight: Callable[[dict[str, Any]], float],
) -> tuple[tuple[Node, ...], tuple[str, ...]]:
    queue: list[tuple[float, tuple[str, ...], Node, tuple[Node, ...]]] = [(0.0, (), source, (source,))]
    best: dict[Node, tuple[float, tuple[str, ...]]] = {source: (0.0, ())}
    while queue:
        cost, segment_ids, node, nodes = heappop(queue)
        if best.get(node) != (cost, segment_ids):
            continue
        if node == target:
            return nodes, segment_ids
        edges = sorted(graph.graph.out_edges(node, keys=True, data=True), key=lambda item: str(item[3]["segment_id"]))
        for _start, neighbour, _key, data in edges:
            candidate_segments = (*segment_ids, str(data["segment_id"]))
            candidate = cost + weight(data)
            previous = best.get(neighbour)
            if previous is None or candidate < previous[0] - 1e-9 or (math.isclose(candidate, previous[0], abs_tol=1e-9) and candidate_segments < previous[1]):
                best[neighbour] = (candidate, candidate_segments)
                heappush(queue, (candidate, candidate_segments, neighbour, (*nodes, neighbour)))
    raise RoutingError("No walking path exists between the snapped origin and destination.")


def _path_result(
    route_type: str,
    graph: RouteGraph,
    nodes: tuple[Node, ...],
    segment_ids: tuple[str, ...],
    values: dict[str, dict[str, float]],
    config: AppConfig,
) -> PathResult:
    speed_mps = config.walking_speed_kmh * 1000 / 3600
    if not segment_ids:
        point = graph.wgs84_nodes[nodes[0]]
        coordinate = (float(point.x), float(point.y))
        return PathResult(
            route_type=route_type,
            nodes=nodes,
            segment_ids=segment_ids,
            length_m=0.0,
            time_s=0.0,
            heat_cost=0.0,
            average_exposure=0.0,
            weighted_shade=0.0,
            average_access_penalty=0.0,
            coordinates=(coordinate, coordinate),
        )
    length_m = heat_cost = shade_sum = access_sum = 0.0
    coordinates: list[tuple[float, float]] = []
    if len(nodes) != len(segment_ids) + 1:
        raise RoutingError("Routing graph returned an invalid path.")
    for start, end, segment_id in zip(nodes, nodes[1:], segment_ids):
        data = graph.graph.get_edge_data(start, end, key=segment_id)
        if data is None or segment_id not in values:
            raise RoutingError("Cached risk data does not match the routing graph. Rerun `python scripts/precompute_risk.py`.")
        length = float(data["length_m"])
        exposure = values[segment_id]["exposure_value"]
        length_m += length
        heat_cost += length * exposure
        shade_sum += length * values[segment_id]["shade_fraction"]
        access_sum += length * values[segment_id]["access_penalty"]
        edge_coordinates = list(data["coordinates_wgs84"])
        start_point = graph.wgs84_nodes[start]
        first = Point(edge_coordinates[0])
        if first.distance(start_point) > Point(edge_coordinates[-1]).distance(start_point):
            edge_coordinates.reverse()
        coordinates.extend(edge_coordinates if not coordinates else edge_coordinates[1:])
    return PathResult(
        route_type=route_type,
        nodes=nodes,
        segment_ids=segment_ids,
        length_m=length_m,
        time_s=length_m / speed_mps,
        heat_cost=heat_cost,
        average_exposure=heat_cost / length_m if length_m else 0.0,
        weighted_shade=shade_sum / length_m if length_m else 0.0,
        average_access_penalty=access_sum / length_m if length_m else 0.0,
        coordinates=tuple(coordinates),
    )


def _heat_aware_path(graph: RouteGraph, source: Node, target: Node, values: dict[str, dict[str, float]], fastest: PathResult, config: AppConfig) -> PathResult:
    """Minimize heat exactly among labels that satisfy the configured time cap."""
    cap = fastest.time_s * (1 + config.heat_aware_max_detour_ratio)
    speed_mps = config.walking_speed_kmh * 1000 / 3600
    labels: dict[Node, list[tuple[float, float, tuple[str, ...]]]] = {source: [(0.0, 0.0, ())]}
    queue: list[tuple[float, float, tuple[str, ...], Node, tuple[Node, ...]]] = [(0.0, 0.0, (), source, (source,))]
    candidates: list[PathResult] = [fastest]

    while queue:
        heat_cost, time_s, segment_ids, node, nodes = heappop(queue)
        if (time_s, heat_cost, segment_ids) not in labels.get(node, []):
            continue
        if node == target:
            candidates.append(_path_result("HEAT_AWARE", graph, nodes, segment_ids, values, config))
            continue
        edges = sorted(graph.graph.out_edges(node, keys=True, data=True), key=lambda item: str(item[3]["segment_id"]))
        for _start, neighbour, _key, data in edges:
            segment_id = str(data["segment_id"])
            length_m = float(data["length_m"])
            candidate_time = time_s + length_m / speed_mps
            if candidate_time > cap + 1e-9:
                continue
            candidate_heat = heat_cost + length_m * values[segment_id]["exposure_value"]
            candidate_segments = (*segment_ids, segment_id)
            candidate_label = (candidate_time, candidate_heat, candidate_segments)
            existing = labels.setdefault(neighbour, [])
            if any(
                known_time <= candidate_time + 1e-9
                and known_heat <= candidate_heat + 1e-9
                and (
                    known_time < candidate_time - 1e-9
                    or known_heat < candidate_heat - 1e-9
                    or known_segments <= candidate_segments
                )
                for known_time, known_heat, known_segments in existing
            ):
                continue
            labels[neighbour] = [
                known
                for known in existing
                if not (
                    candidate_time <= known[0] + 1e-9
                    and candidate_heat <= known[1] + 1e-9
                    and (
                        candidate_time < known[0] - 1e-9
                        or candidate_heat < known[1] - 1e-9
                        or candidate_segments <= known[2]
                    )
                )
            ]
            labels[neighbour].append(candidate_label)
            heappush(queue, (candidate_heat, candidate_time, candidate_segments, neighbour, (*nodes, neighbour)))

    best = min(candidates, key=lambda item: (item.heat_cost, item.time_s, item.segment_ids))
    return fastest if best.heat_cost >= fastest.heat_cost - 1e-9 else best


def _balanced_path(graph: RouteGraph, source: Node, target: Node, values: dict[str, dict[str, float]], fastest: PathResult, heat_aware: PathResult, config: AppConfig) -> PathResult:
    alpha, beta = config.route_objective_weights["alpha"], config.route_objective_weights["beta"]
    heat_denominator = fastest.heat_cost if fastest.heat_cost > 0 else 1.0
    speed_mps = config.walking_speed_kmh * 1000 / 3600
    nodes, segment_ids = _dijkstra(
        graph,
        source,
        target,
        lambda data: alpha * (float(data["length_m"]) / speed_mps) / fastest.time_s
        + beta * (float(data["length_m"]) * values[str(data["segment_id"])]["exposure_value"]) / heat_denominator,
    )
    candidate = _path_result("BALANCED", graph, nodes, segment_ids, values, config)
    lower_heat, upper_heat = sorted((fastest.heat_cost, heat_aware.heat_cost))
    lower_time, upper_time = sorted((fastest.time_s, heat_aware.time_s))
    if lower_heat - 1e-9 <= candidate.heat_cost <= upper_heat + 1e-9 and lower_time - 1e-9 <= candidate.time_s <= upper_time + 1e-9:
        return candidate
    # A balanced option must remain interpretable between the two comparison anchors.
    return min((fastest, heat_aware), key=lambda item: (alpha * item.time_s / fastest.time_s + beta * item.heat_cost / heat_denominator, item.segment_ids))


def _recorded_access_available(config: AppConfig) -> bool:
    try:
        features = load_cached_geojson("facilities", config).get("features", [])
    except FileNotFoundError:
        return False
    return any(feature.get("properties", {}).get("facility_type") in {"water", "cooling"} for feature in features)


def _serialise_path(path: PathResult, fastest: PathResult, metadata: dict[str, Any], access_available: bool, config: AppConfig) -> dict[str, Any]:
    heat_change = 0.0 if fastest.heat_cost == 0 else ((path.heat_cost - fastest.heat_cost) / fastest.heat_cost) * 100
    route_type_message_id = {
        "FASTEST": "card_fastest",
        "HEAT_AWARE": "card_heat_aware",
        "BALANCED": "card_balanced",
    }[path.route_type]
    status_message_id = "summary_status_interpolated" if metadata["modelled_or_interpolated"] == "INTERPOLATED" else "summary_status_modelled"
    return {
        "route_type": path.route_type,
        "route_type_message_id": route_type_message_id,
        "route_type_message_params": {},
        "same_as": [],
        "geometry": {"type": "LineString", "coordinates": [list(item) for item in path.coordinates]},
        "segment_ids": list(path.segment_ids),
        "total_time_s": path.time_s,
        "total_distance_m": path.length_m,
        "modelled_heat_exposure": path.heat_cost,
        "modelled_heat_exposure_unit": "exposure-metres",
        "average_exposure": path.average_exposure,
        "weighted_shade": path.weighted_shade,
        "average_access_penalty": path.average_access_penalty,
        "cooling_access": path.average_access_penalty if access_available else "Data unavailable (no recorded facility)",
        "cooling_access_message_id": "cooling_access" if access_available else "cooling_unavailable",
        "cooling_access_message_params": {"value": path.average_access_penalty} if access_available else {},
        "classification_vs_fastest": {
            "extra_minutes": (path.time_s - fastest.time_s) / 60,
            "modelled_heat_exposure_change_percent": heat_change,
        },
        "labels": {
            "impact": "MODELLED",
            "impact_message_id": "summary_status_modelled",
            "impact_message_params": {},
            "time_status": metadata["modelled_or_interpolated"],
            "time_status_message_id": status_message_id,
            "time_status_message_params": {},
        },
        "modelled_or_interpolated_message_id": status_message_id,
        "modelled_or_interpolated_message_params": {},
        "computation_mode_message_id": "mode_estimated" if config.computation_mode == "FALLBACK" else "mode_geometric",
        "computation_mode_message_params": {},
        "computation_mode": metadata["computation_mode"],
        "provenance": {
            "source_type": "derived",
            "source_reference": "Cached directed OSM street segments and cached risk snapshot at departure time.",
            "observed_or_estimated": "ESTIMATED",
            "modelled_or_interpolated": metadata["modelled_or_interpolated"],
            "timestamp": datetime.now(UTC).isoformat(),
            "assumptions_version": config.version,
            "computation_mode": metadata["computation_mode"],
        },
    }


def _unique_paths(paths: list[PathResult], graph: RouteGraph, fastest: PathResult, metadata: dict[str, Any], access_available: bool, config: AppConfig) -> list[dict[str, Any]]:
    routes: list[dict[str, Any]] = []
    seen: dict[tuple[str, ...], dict[str, Any]] = {}
    for path in paths:
        signature = path.segment_ids
        if signature in seen:
            seen[signature]["same_as"].append(path.route_type)
            continue
        record = _serialise_path(path, fastest, metadata, access_available, config)
        record["stops"] = find_safe_stops(graph, path, config)
        seen[signature] = record
        routes.append(record)
    for record in routes:
        record["same_as_messages"] = [
            {
                "route_type": route_type,
                "route_type_message_id": {
                    "FASTEST": "card_fastest",
                    "HEAT_AWARE": "card_heat_aware",
                    "BALANCED": "card_balanced",
                }[route_type],
                "text": CITIZEN_EN["same_route_fastest"],
                "message_id": "same_route_fastest",
                "message_params": {},
            }
            for route_type in record["same_as"]
        ]
    return routes


def _recommendation(fastest: PathResult, heat_aware: PathResult, config: AppConfig) -> str:
    return _recommendation_message(fastest, heat_aware, config)["text"]


def _recommendation_message(fastest: PathResult, heat_aware: PathResult, config: AppConfig) -> dict[str, Any]:
    change = (heat_aware.heat_cost - fastest.heat_cost) / fastest.heat_cost * 100 if fastest.heat_cost else 0.0
    reduction = max(0.0, -change)
    if reduction < config.min_heat_reduction_pct:
        message_id = "recommendation_small"
        params = {"percent": f"{reduction:.1f}"}
    else:
        message_id = "recommendation_heat"
        params = {
            "minutes": max(0, round((heat_aware.time_s - fastest.time_s) / 60)),
            "percent": f"{reduction:.1f}",
        }
    return {
        "text": CITIZEN_EN[message_id].format(**params),
        "message_id": message_id,
        "message_params": params,
    }


def warm_route_graph(config: AppConfig | None = None) -> float | None:
    """Construct the cache-only graph during startup so the first request is warm."""
    active_config = config or get_config()
    started = time.perf_counter()
    try:
        graph = get_route_graph(active_config)
    except (FileNotFoundError, RoutingError) as exc:
        LOGGER.warning("Routing graph warm-up unavailable: %s", exc)
        return None
    duration_s = time.perf_counter() - started
    LOGGER.info("Routing graph warmed in %.3fs: nodes=%s segments=%s", duration_s, graph.graph.number_of_nodes(), graph.graph.number_of_edges())
    return duration_s


def route_request(origin: tuple[float, float], destination: tuple[float, float], time_value: str, config: AppConfig | None = None) -> dict[str, Any]:
    """Return deterministic unique route choices from only cached source/model data."""
    global _FIRST_ROUTE_REQUEST
    active_config = config or get_config()
    started = time.perf_counter()
    graph = get_route_graph(active_config)
    origin_node, snapped_origin = snap_endpoint(origin[0], origin[1], graph, active_config, "origin")
    destination_node, snapped_destination = snap_endpoint(destination[0], destination[1], graph, active_config, "destination")
    values, metadata = routing_snapshot(time_value, active_config)
    speed_mps = active_config.walking_speed_kmh * 1000 / 3600
    nodes, segment_ids = _dijkstra(graph, origin_node, destination_node, lambda data: float(data["length_m"]) / speed_mps)
    fastest = _path_result("FASTEST", graph, nodes, segment_ids, values, active_config)
    heat_aware = _heat_aware_path(graph, origin_node, destination_node, values, fastest, active_config)
    if heat_aware is fastest:
        heat_aware = replace(fastest, route_type="HEAT_AWARE")
    balanced = _balanced_path(graph, origin_node, destination_node, values, fastest, heat_aware, active_config)
    if balanced.route_type != "BALANCED":
        balanced = replace(balanced, route_type="BALANCED")
    routes = _unique_paths([fastest, heat_aware, balanced], graph, fastest, metadata, _recorded_access_available(active_config), active_config)
    elapsed = time.perf_counter() - started
    LOGGER.info("Routing completed in %.3fs: unique_routes=%s segments=%s interpolated=%s", elapsed, len(routes), sum(len(route["segment_ids"]) for route in routes), metadata["interpolated"])
    if _FIRST_ROUTE_REQUEST:
        LOGGER.info("First route request completed in %.3fs", elapsed)
        _FIRST_ROUTE_REQUEST = False
    recommendation = _recommendation_message(fastest, heat_aware, active_config)
    response = {
        "routes": routes,
        "recommendation": recommendation["text"],
        "recommendation_message_id": recommendation["message_id"],
        "recommendation_message_params": recommendation["message_params"],
        "requested_time": time_value,
        "snapped_endpoints": {"origin": snapped_origin, "destination": snapped_destination},
        "graph_report": {
            "directed_segment_count": graph.graph.number_of_edges(),
            "node_count": graph.graph.number_of_nodes(),
            "segments_outside_largest_component": graph.outside_segment_count,
            "nodes_outside_largest_component": graph.outside_node_count,
        },
        "assumption_label": active_config.routing_assumption_label,
        "metadata": metadata,
    }
    reduction_pct = max(0.0, (fastest.heat_cost - heat_aware.heat_cost) / fastest.heat_cost * 100) if fastest.heat_cost else 0.0
    if reduction_pct >= active_config.min_heat_reduction_pct:
        response["lower_exposure_route_available"] = {
            "value": True,
            "message_id": "summary_lower_route",
            "message_params": {},
            "english_text": CITIZEN_EN["summary_lower_route"],
            "status": "MODELLED",
            "status_message_id": "summary_status_modelled",
            "status_message_params": {},
        }
    return response


def search_places(query: str, config: AppConfig | None = None, limit: int = 10) -> list[dict[str, Any]]:
    """Search only source-provided names in the local cache; no external geocoder is used."""
    active_config = config or get_config()
    needle = query.strip().casefold()
    if not needle:
        return []
    records: list[dict[str, Any]] = []
    for feature in load_cached_geojson("streets", active_config).get("features", []):
        properties = feature.get("properties", {})
        try:
            name = json.loads(properties.get("road_metadata", "{}") or "{}").get("name")
        except (TypeError, json.JSONDecodeError):
            name = None
        if not isinstance(name, str) or not name.strip() or needle not in name.casefold():
            continue
        geometry = shape(feature["geometry"])
        point = geometry.interpolate(0.5, normalized=True)
        records.append({"place_type": "street", "place_id": properties["segment_id"], "name": name.strip(), "location": {"type": "Point", "coordinates": [point.x, point.y]}})
    for source_name, place_type, id_key in (("buildings", "building", "building_id"), ("facilities", "amenity", "facility_id")):
        try:
            features = load_cached_geojson(source_name, active_config).get("features", [])
        except FileNotFoundError:
            features = []
        for feature in features:
            properties = feature.get("properties", {})
            name = properties.get("name")
            if not isinstance(name, str) or not name.strip() or needle not in name.casefold():
                continue
            geometry = shape(feature["geometry"])
            point = geometry.centroid
            records.append({"place_type": place_type, "place_id": properties.get(id_key), "name": name.strip(), "location": {"type": "Point", "coordinates": [point.x, point.y]}})
    deduplicated: dict[tuple[str, str], dict[str, Any]] = {}
    for record in records:
        deduplicated.setdefault((record["place_type"], record["name"].casefold()), record)
    return sorted(deduplicated.values(), key=lambda item: (item["name"].casefold(), item["place_type"], str(item["place_id"])))[:limit]
