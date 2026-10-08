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


def test_canonical_exposure_is_cached_and_modelled(client):
    response = client.get("/api/exposure?time=11:00")
    assert response.status_code == 200
    payload = response.json()
    assert payload["metadata"]["interpolated"] is False
    assert payload["metadata"]["modelled_or_interpolated"] == "MODELLED"
    assert payload["features"][0]["properties"]["modelled_or_interpolated"] == "MODELLED"


def test_between_exposure_is_interpolated_between_cached_neighbours(client):
    lower = client.get("/api/exposure?time=09:00").json()
    upper = client.get("/api/exposure?time=11:00").json()
    response = client.get("/api/exposure?time=10:00")
    assert response.status_code == 200
    payload = response.json()
    assert payload["metadata"]["interpolated"] is True
    assert payload["metadata"]["modelled_or_interpolated"] == "INTERPOLATED"
    for low, high, middle in zip(lower["features"], upper["features"], payload["features"], strict=True):
        lower_value = low["properties"]["exposure_value"]
        upper_value = high["properties"]["exposure_value"]
        middle_value = middle["properties"]["exposure_value"]
        assert min(lower_value, upper_value) <= middle_value <= max(lower_value, upper_value)


def test_exposure_api_validates_time_and_missing_cache(client, monkeypatch):
    assert client.get("/api/exposure?time=10:15").status_code == 422

    def missing_snapshot(*_args, **_kwargs):
        raise FileNotFoundError("Run `python scripts/precompute_exposure.py` after the required cache data is available.")

    monkeypatch.setattr(planner, "load_exposure_snapshot", missing_snapshot)
    response = client.get("/api/exposure?time=09:00")
    assert response.status_code == 503
    assert "Run `python scripts/precompute_exposure.py`" in response.json()["detail"]
