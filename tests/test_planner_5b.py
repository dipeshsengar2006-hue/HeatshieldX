"""Prompt 5B planner cache, endpoint, and HTML contracts."""

from app.config import get_config
from app.repositories.cache import load_cached_plan
from app.services.intervention_engine import plan_id_for


def test_precomputed_plan_is_available_on_disk():
    resources = {"water_points": 2, "cooling_centres": 1, "shade_structures": 2}
    config = get_config()
    cached = load_cached_plan(plan_id_for(resources, config), config)
    assert cached is not None
    assert cached["config_version"] == config.version
    assert cached["objective"]["before"] == 62860.209799467986
    assert cached["objective"]["modelled_after"] == 54063.57492919198


def test_plan_endpoints_and_422_path_return_expected_fields(client):
    response = client.post("/api/optimize", json={"water_points": 2, "cooling_centres": 1, "shade_structures": 2})
    assert response.status_code == 200
    payload = response.json()
    assert {"plan_id", "priorities", "objective", "metrics", "config_version"} <= set(payload)
    assert {"priority", "type", "street_canonical_key", "share_of_total_reduction", "explanation"} <= set(payload["priorities"][0])
    assert all(metric["definition"] and metric["label"] == "Modelled Impact" for metric in payload["metrics"].values())
    assert client.get(f"/api/plans/{payload['plan_id']}").status_code == 200

    invalid = client.post("/api/optimize", json={"water_points": 11, "cooling_centres": 1, "shade_structures": 2})
    assert invalid.status_code == 422
    assert "water_points must be an integer from 0 to 10" in invalid.json()["detail"]


def test_planner_html_contains_response_and_impact_controls(client):
    response = client.get("/")
    assert response.status_code == 200
    for expected in ("water-points", "cooling-centres", "shade-structures", "Optimize Response", "Modelled After", "Before", "Observed OSM facility"):
        assert expected in response.text
