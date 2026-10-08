from app.routes import planner


def test_cached_geojson_endpoints_return_feature_collections(client):
    for path in ("/api/street-segments", "/api/buildings", "/api/facilities"):
        response = client.get(path)
        assert response.status_code == 200
        assert response.json()["type"] == "FeatureCollection"


def test_empty_facilities_are_a_valid_preloaded_response(client):
    response = client.get("/api/facilities")
    assert response.status_code == 200
    assert response.json()["features"] == []


def test_planner_uses_preloaded_data(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "Rajwada-Sarafa" in response.text
    assert "Preloaded map data is unavailable" not in response.text


def test_missing_preload_has_actionable_error(client, preloaded_api):
    preloaded_api.pop("streets")
    response = client.get("/api/street-segments")
    assert response.status_code == 503
    assert "Run `python scripts/precompute_demo_area.py`" in response.json()["detail"]


def test_cached_shadow_endpoints_return_geometric_feature_collections(client):
    for path in ("/api/shadows/09:00/polygons", "/api/shadows/09:00/shade-fractions"):
        response = client.get(path)
        assert response.status_code == 200
        payload = response.json()
        assert payload["type"] == "FeatureCollection"
        assert payload["metadata"]["computation_mode"] == "geometric"


def test_missing_shadow_cache_has_actionable_error(client, monkeypatch):
    def missing_snapshot(*_args, **_kwargs):
        raise FileNotFoundError("Run `python scripts/precompute_shadows.py` after Prompt 1 cache data is available.")

    monkeypatch.setattr(planner, "load_shadow_snapshot", missing_snapshot)
    response = client.get("/api/shadows/09:00/polygons")
    assert response.status_code == 503
    assert "Run `python scripts/precompute_shadows.py`" in response.json()["detail"]
