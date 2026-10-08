def test_cached_geojson_endpoints_return_feature_collections(client):
    for path in ("/api/street-segments", "/api/buildings", "/api/facilities"):
        response = client.get(path)
        assert response.status_code == 200
        assert response.json()["type"] == "FeatureCollection"


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
