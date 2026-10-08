"""Prompt 4A cache-only risk API behavior."""

from app.routes import planner


def test_risk_api_returns_modelled_canonical_cache_and_interpolated_between(client):
    canonical = client.get("/api/risk?time=15:00")
    assert canonical.status_code == 200
    payload = canonical.json()
    assert payload["metadata"]["interpolated"] is False
    assert payload["metadata"]["modelled_or_interpolated"] == "MODELLED"
    segment_id = payload["features"][0]["properties"]["segment_id"]

    interpolated = client.get("/api/risk?time=14:00")
    assert interpolated.status_code == 200
    assert interpolated.json()["metadata"]["interpolated"] is True
    assert interpolated.json()["metadata"]["modelled_or_interpolated"] == "INTERPOLATED"

    breakdown = client.get(f"/api/segments/{segment_id}/risk?time=15:00")
    assert breakdown.status_code == 200
    properties = breakdown.json()["risk"]["properties"]
    assert {"elderly_component", "outdoor_worker_component", "access_penalty", "baseline_risk", "final_risk_raw", "risk_score"} <= set(properties)
    assert properties["estimated_flag"] is True


def test_risk_api_validates_time_segment_and_missing_cache(client, monkeypatch):
    assert client.get("/api/risk?time=10:15").status_code == 422
    assert client.get("/api/segments/no-such-segment/risk?time=15:00").status_code == 404

    def missing_snapshot(*_args, **_kwargs):
        raise FileNotFoundError("Run `python scripts/precompute_risk.py` after the required exposure cache is available.")

    monkeypatch.setattr(planner, "load_risk_snapshot", missing_snapshot)
    response = client.get("/api/risk?time=15:00")
    assert response.status_code == 503
    assert "Run `python scripts/precompute_risk.py`" in response.json()["detail"]
