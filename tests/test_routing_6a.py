from __future__ import annotations

import json
import logging
from dataclasses import replace

import pytest

from app.config import get_config
from app.services import routing_engine
from app.services.data_engine import classify_stop
from app.services.routing_engine import PathResult, RouteGraph, RoutingError, _balanced_path, _dijkstra, _heat_aware_path, _path_result, _unique_paths, build_route_graph, route_request, routing_snapshot, snap_endpoint
from app.services.stop_finder import find_safe_stops


def _feature(segment_id: str, start: tuple[float, float], end: tuple[float, float], length_m: float) -> dict:
    return {
        "type": "Feature",
        "properties": {"segment_id": segment_id, "length_m": length_m},
        "geometry": {"type": "LineString", "coordinates": [start, end]},
    }


def _synthetic_graph() -> tuple[RouteGraph, dict[str, dict[str, float]]]:
    source = (75.8550, 22.7170)
    fast = (75.8560, 22.7170)
    cool = (75.8550, 22.7180)
    target = (75.8560, 22.7180)
    streets = {
        "type": "FeatureCollection",
        "features": [
            _feature("fast-1", source, fast, 100),
            _feature("fast-2", fast, target, 100),
            _feature("cool-1", source, cool, 120),
            _feature("cool-2", cool, target, 120),
        ],
    }
    return build_route_graph(streets), {
        "fast-1": {"exposure_value": 0.9, "shade_fraction": 0.1, "access_penalty": 0.4},
        "fast-2": {"exposure_value": 0.9, "shade_fraction": 0.1, "access_penalty": 0.4},
        "cool-1": {"exposure_value": 0.2, "shade_fraction": 0.8, "access_penalty": 0.1},
        "cool-2": {"exposure_value": 0.2, "shade_fraction": 0.8, "access_penalty": 0.1},
    }


def _synthetic_paths() -> tuple[RouteGraph, PathResult, PathResult, PathResult]:
    graph, values = _synthetic_graph()
    config = get_config()
    source = next(start for start, _end, _key, edge in graph.graph.edges(keys=True, data=True) if edge["segment_id"] == "fast-1")
    target = next(end for _start, end, _key, edge in graph.graph.edges(keys=True, data=True) if edge["segment_id"] == "fast-2")
    nodes, segment_ids = _dijkstra(graph, source, target, lambda edge: float(edge["length_m"]))
    fastest = _path_result("FASTEST", graph, nodes, segment_ids, values, config)
    heat_aware = _heat_aware_path(graph, source, target, values, fastest, config)
    if heat_aware is fastest:
        heat_aware = replace(fastest, route_type="HEAT_AWARE")
    balanced = _balanced_path(graph, source, target, values, fastest, heat_aware, config)
    return graph, fastest, heat_aware, balanced


def test_synthetic_fastest_heat_aware_and_balanced_paths_are_constrained_and_deterministic():
    _graph, fastest, heat_aware, balanced = _synthetic_paths()
    config = get_config()

    assert fastest.segment_ids == ("fast-1", "fast-2")
    assert fastest.time_s == pytest.approx(150)
    assert heat_aware.heat_cost <= fastest.heat_cost
    assert heat_aware.time_s <= fastest.time_s * (1 + config.heat_aware_max_detour_ratio)
    assert min(fastest.time_s, heat_aware.time_s) <= balanced.time_s <= max(fastest.time_s, heat_aware.time_s)
    assert min(fastest.heat_cost, heat_aware.heat_cost) <= balanced.heat_cost <= max(fastest.heat_cost, heat_aware.heat_cost)
    assert _synthetic_paths()[2].segment_ids == heat_aware.segment_ids


def test_duplicate_routes_are_returned_once_with_same_as(monkeypatch):
    graph, fastest, _heat_aware, _balanced = _synthetic_paths()
    monkeypatch.setattr(routing_engine, "find_safe_stops", lambda *_args: {"status": "No stop data available", "items": []})
    routes = _unique_paths(
        [fastest, replace(fastest, route_type="HEAT_AWARE"), replace(fastest, route_type="BALANCED")],
        graph,
        fastest,
        {"modelled_or_interpolated": "MODELLED", "computation_mode": "FULL"},
        False,
        get_config(),
    )

    assert len(routes) == 1
    assert routes[0]["route_type"] == "FASTEST"
    assert routes[0]["same_as"] == ["HEAT_AWARE", "BALANCED"]


def test_no_path_and_outside_area_errors_are_explicit():
    graph, _values = _synthetic_graph()
    nodes = sorted(graph.graph.nodes)
    with pytest.raises(RoutingError, match="No walking path"):
        _dijkstra(graph, nodes[-1], nodes[0], lambda edge: float(edge["length_m"]))
    with pytest.raises(RoutingError, match="outside"):
        snap_endpoint(0.0, 0.0, graph, get_config(), "origin")


def test_cached_route_totals_interpolation_and_logs_do_not_contain_request_coordinates(caplog):
    caplog.set_level(logging.INFO, logger="app.services.routing_engine")
    result = route_request((22.7148593, 75.8549381), (22.7188165, 75.8553691), "10:00")
    snapshot, metadata = routing_snapshot("10:00")

    assert metadata["interpolated"] is True
    assert result["metadata"]["modelled_or_interpolated"] == "INTERPOLATED"
    for route in result["routes"]:
        assert route["total_distance_m"] == pytest.approx(sum(
            float(next(edge["length_m"] for _start, _end, edge in routing_engine.get_route_graph().graph.edges(data=True) if edge["segment_id"] == segment_id))
            for segment_id in route["segment_ids"]
        ))
        assert all(word not in json.dumps(route).lower() for word in ("heatstroke", "prevents", "safe route"))
    assert snapshot
    logged = "\n".join(record.getMessage() for record in caplog.records)
    assert "22.7148593" not in logged
    assert "75.8549381" not in logged


def test_stop_finder_uses_only_cached_osm_stops_and_network_detour(monkeypatch):
    graph, fastest, _heat_aware, _balanced = _synthetic_paths()
    route_node = fastest.nodes[1]
    branch_node = next(node for node in graph.graph.nodes if node not in fastest.nodes)
    route_point = graph.wgs84_nodes[route_node]
    branch_point = graph.wgs84_nodes[branch_node]
    stops = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"stop_id": "osm-near", "stop_type": "business", "name": "Near cafe", "amenities": "[\"amenity=cafe\"]", "sponsored_status": True},
                "geometry": {"type": "Point", "coordinates": [route_point.x, route_point.y]},
            },
            {
                "type": "Feature",
                "properties": {"stop_id": "osm-branch", "stop_type": "water", "name": None, "amenities": "[\"amenity=drinking_water\"]"},
                "geometry": {"type": "Point", "coordinates": [branch_point.x, branch_point.y]},
            },
        ],
    }
    monkeypatch.setattr("app.services.stop_finder.load_cached_geojson", lambda name, _config: stops if name == "stops" else pytest.fail("unexpected cache"))

    result = find_safe_stops(graph, fastest, get_config())

    assert result["status"] == "Available"
    assert result["items"][0]["stop_id"] == "osm-near"
    assert result["items"][0]["rating"] is None
    assert result["items"][0]["sponsored_status"] is False
    branch = next(stop for stop in result["items"] if stop["stop_id"] == "osm-branch")
    assert branch["name"] == "Unnamed water"
    assert branch["detour_distance"] == pytest.approx(240)
    assert 0 <= branch["route_relevance"] <= 1


def test_stop_finder_missing_and_empty_cache_states(monkeypatch):
    graph, fastest, _heat_aware, _balanced = _synthetic_paths()
    monkeypatch.setattr("app.services.stop_finder.load_cached_geojson", lambda *_args: {"type": "FeatureCollection", "features": []})
    assert find_safe_stops(graph, fastest, get_config())["status"] == "No eligible stops recorded in OSM along this route"
    monkeypatch.setattr("app.services.stop_finder.load_cached_geojson", lambda *_args: (_ for _ in ()).throw(FileNotFoundError()))
    assert find_safe_stops(graph, fastest, get_config())["status"] == "No stop data available"


def test_stop_type_mapping_excludes_healthcare():
    config = get_config()
    assert classify_stop({"amenity": "drinking_water"}, config) == ("water", ["amenity=drinking_water"])
    assert classify_stop({"amenity": "cafe"}, config) == ("business", ["amenity=cafe"])
    assert classify_stop({"amenity": "clinic"}, config) is None


def test_route_and_place_endpoints_validate_and_return_cached_results(client):
    places = client.get("/api/places?q=road")
    assert places.status_code == 200
    assert places.json()["places"]
    response = client.post(
        "/api/routes",
        json={"origin": {"lat": 22.7148593, "lon": 75.8549381}, "destination": {"lat": 22.7188165, "lon": 75.8553691}, "time": "09:00"},
    )
    assert response.status_code == 200
    assert response.json()["routes"][0]["geometry"]["type"] == "LineString"
    assert response.json()["routes"][0]["labels"]["impact"] == "MODELLED"
    assert client.post("/api/routes", json={"origin": {"lat": 0, "lon": 0}, "destination": {"lat": 0, "lon": 0}, "time": "09:00"}).status_code == 422
    interpolated = client.post("/api/routes", json={"origin": {"lat": 22.7148593, "lon": 75.8549381}, "destination": {"lat": 22.7188165, "lon": 75.8553691}, "time": "10:15"})
    assert interpolated.status_code == 200
    assert interpolated.json()["metadata"]["interpolated"] is True
    assert client.post("/api/routes", json={"origin": {"lat": 22.7148593, "lon": 75.8549381}, "destination": {"lat": 22.7188165, "lon": 75.8553691}, "time": "08:00"}).status_code == 422
