"""Offline contracts for the stops/facilities Overpass refresh tools."""

from __future__ import annotations

import json

import pytest

from app.config import get_config
from app.services import data_engine


def _payload() -> dict:
    return {
        "version": 0.6,
        "elements": [
            {"type": "node", "id": 1, "lat": 22.7177, "lon": 75.8550, "tags": {"amenity": "drinking_water", "name": "Public tap"}},
            {"type": "way", "id": 2, "center": {"lat": 22.7178, "lon": 75.8551}, "tags": {"amenity": "cafe"}},
            {"type": "relation", "id": 3, "center": {"lat": 22.7179, "lon": 75.8552}, "tags": {"leisure": "park", "name": "Garden"}},
            {"type": "node", "id": 4, "lat": 22.7180, "lon": 75.8553, "tags": {"amenity": "clinic", "name": "Excluded clinic"}},
        ],
    }


def _temporary_config(tmp_path):
    return get_config().model_copy(update={"cache_data_dir": tmp_path / "cache"})


def test_overpass_import_classifies_centers_names_and_provenance():
    records = data_engine.stops_from_overpass_json(_payload())

    assert set(records["stop_type"]) == {"water", "business", "shaded_public"}
    assert "osm-node-1" in set(records["stop_id"])
    cafe = records.loc[records["stop_type"] == "business"].iloc[0]
    assert cafe["name"] == "Unnamed business"
    assert cafe.geometry.geom_type == "Point"
    assert records.to_crs("EPSG:4326").loc[records["stop_type"] == "business"].iloc[0].geometry.x == pytest.approx(75.8551)
    assert cafe["source_type"] == "osm"
    assert cafe["observed_or_estimated"] == "OBSERVED"
    assert cafe["modelled_or_interpolated"] == "NOT_APPLICABLE"
    assert "clinic" not in " ".join(records["name"])


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"elements": []},
        {"elements": [{"type": "way", "id": 1, "tags": {"amenity": "cafe"}}]},
        {"elements": [{"type": "node", "id": 1, "lat": "bad", "lon": 75.0, "tags": {"amenity": "cafe"}}]},
    ],
)
def test_overpass_parser_rejects_empty_or_malformed_input(payload):
    with pytest.raises(ValueError):
        data_engine.stops_from_overpass_json(payload)


def test_import_rejects_bad_input_without_touching_existing_cache(tmp_path):
    config = _temporary_config(tmp_path)
    stops_path = config.cache_data_dir / "stops.geojson"
    stops_path.parent.mkdir(parents=True)
    stops_path.write_text('{"existing": true}', encoding="utf-8")
    source = tmp_path / "bad.json"
    source.write_text('{"elements": []}', encoding="utf-8")

    with pytest.raises(ValueError, match="non-empty"):
        data_engine.import_overpass_stops(source, config)

    assert stops_path.read_text(encoding="utf-8") == '{"existing": true}'


def test_import_writes_atomic_valid_stops_and_reports_counts(tmp_path):
    config = _temporary_config(tmp_path)
    source = tmp_path / "overpass.json"
    source.write_text(json.dumps(_payload()), encoding="utf-8")

    report = data_engine.import_overpass_stops(source, config)
    cached = json.loads((config.cache_data_dir / "stops.geojson").read_text(encoding="utf-8"))

    assert report["stop_count"] == 3
    assert report["types"] == {"water": 1, "cooling": 0, "shaded_public": 1, "business": 1}
    assert len(cached["features"]) == 3


def test_endpoint_fallback_retries_then_uses_next_endpoint(monkeypatch):
    calls = []
    monkeypatch.setattr(data_engine, "overpass_endpoints", lambda: ("https://one.example/api", "https://two.example/api"))

    def request(endpoint, _query):
        calls.append(endpoint)
        if endpoint.startswith("https://one"):
            raise OSError("unavailable")
        return _payload()

    monkeypatch.setattr(data_engine, "_post_overpass_query", request)
    payload, endpoint = data_engine.fetch_overpass_json("query", sleep=lambda _seconds: None)

    assert payload == _payload()
    assert endpoint == "https://two.example/api"
    assert calls == ["https://one.example/api"] * 3 + ["https://two.example/api"]


def test_stop_refresh_failure_leaves_cache_unchanged(tmp_path, monkeypatch):
    config = _temporary_config(tmp_path)
    stops_path = config.cache_data_dir / "stops.geojson"
    stops_path.parent.mkdir(parents=True)
    stops_path.write_text('{"existing": true}', encoding="utf-8")
    monkeypatch.setattr(data_engine, "fetch_overpass_json", lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("offline")))

    with pytest.raises(RuntimeError, match="left unchanged"):
        data_engine.precompute_stops(config, sleep=lambda _seconds: None)

    assert stops_path.read_text(encoding="utf-8") == '{"existing": true}'


def test_stop_query_is_configured_for_nodes_ways_relations_and_browser_url():
    query = data_engine.stop_overpass_query()

    assert "node[" in query and "way[" in query and "relation[" in query
    assert "out center;" in query
    assert "drinking_water" in query and "library" in query and "park" in query and "cafe" in query
    assert data_engine.overpass_browser_url(query).startswith("https://overpass-turbo.eu/?Q=")


def test_overpass_url_override_is_tried_before_public_fallbacks(monkeypatch):
    monkeypatch.setenv("OVERPASS_URL", "https://override.example/api/interpreter")

    assert data_engine.overpass_endpoints() == (
        "https://override.example/api/interpreter",
        "https://overpass.private.coffee/api/interpreter",
        "https://overpass.kumi.systems/api/interpreter",
        "https://overpass-api.de/api/interpreter",
    )
