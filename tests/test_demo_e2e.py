"""Network-free regression of the fixed SRS 51 demonstration narrative."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


CLIENT = TestClient(app)
ORIGIN = {"lat": 22.7146202, "lon": 75.8542367}  # Kadavghat road cache point
DESTINATION = {"lat": 22.7188165, "lon": 75.8553691}  # M.G.ROAD cache point
FORBIDDEN = ("heatstroke", "prevent", "safe route", "diagnose", "treatment")


def _response(method: str, path: str, **kwargs):
    response = getattr(CLIENT, method)(path, **kwargs)
    assert response.status_code < 500, response.text
    return response


def _assert_provenance(record: dict) -> None:
    for field in (
        "source_type", "observed_or_estimated", "modelled_or_interpolated",
        "assumptions_version", "computation_mode",
    ):
        assert record.get(field) not in (None, ""), field


def test_fixed_cache_demo_narrative_uses_only_ui_endpoints(monkeypatch):
    """The fixed narrative must remain runnable if every external connection is blocked."""
    import socket
    import urllib.request

    blocked = lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("Demo endpoint attempted network access"))
    monkeypatch.setattr(socket, "create_connection", blocked)
    monkeypatch.setattr(urllib.request, "urlopen", blocked)
    streets = _response("get", "/api/street-segments")
    buildings = _response("get", "/api/buildings")
    assert streets.status_code == buildings.status_code == 200
    assert streets.json()["features"] and buildings.json()["features"]

    risks = {}
    exposures = {}
    for time in ("09:00", "13:00", "17:00"):
        risk = _response("get", "/api/risk", params={"time": time})
        exposure = _response("get", "/api/exposure", params={"time": time})
        assert risk.status_code == exposure.status_code == 200
        risks[time] = risk.json()
        exposures[time] = exposure.json()
        assert risk.json()["metadata"]["modelled_or_interpolated"] == "MODELLED"
        assert exposure.json()["metadata"]["observed_or_estimated"] == "ESTIMATED"
        _assert_provenance(risk.json()["features"][0]["properties"])
        _assert_provenance(exposure.json()["features"][0]["properties"])
    assert [exposures[time]["features"][0]["properties"]["exposure_value"] for time in exposures] != [
        exposures["09:00"]["features"][0]["properties"]["exposure_value"]
    ] * 3

    at_fifteen = _response("get", "/api/risk", params={"time": "15:00"}).json()
    leader = max(at_fifteen["features"], key=lambda item: item["properties"]["risk_score"])
    segment_id = leader["properties"]["canonical_street_key"]
    why = _response("get", f"/api/segments/{segment_id}/why", params={"time": "15:00"})
    assert why.status_code == 200
    assert {"street", "drivers", "provenance"} <= why.json().keys()

    comparison = _response("get", "/api/compare/hottest", params={"time": "15:00"})
    assert comparison.status_code == 200
    assert {"hottest", "highest_risk", "metadata"} <= comparison.json().keys()

    plan = _response("post", "/api/optimize", json={"water_points": 2, "cooling_centres": 1, "shade_structures": 2})
    assert plan.status_code == 200
    plan_payload = plan.json()
    assert plan_payload["requested_resources"] == {"water_points": 2, "cooling_centres": 1, "shade_structures": 2}
    assert plan_payload["metrics"]
    assert _response("get", f"/api/plans/{plan_payload['plan_id']}").status_code == 200
    scenario = _response("get", "/api/risk", params={"time": "15:00", "plan_id": plan_payload["plan_id"]})
    assert scenario.status_code == 200
    assert scenario.json()["metadata"]["plan_id"] == plan_payload["plan_id"]

    route = _response("post", "/api/routes", json={"origin": ORIGIN, "destination": DESTINATION, "time": "09:00"})
    assert route.status_code == 200
    route_payload = route.json()
    assert {"FASTEST", "HEAT_AWARE", "BALANCED"} <= {item["route_type"] for item in route_payload["routes"]}
    assert route_payload["recommendation"]
    assert route_payload["metadata"]["modelled_or_interpolated"] == "MODELLED"
    for item in route_payload["routes"]:
        _assert_provenance(item["provenance"])

    summary = _response("post", "/api/public/summary", json={"lat": ORIGIN["lat"], "lon": ORIGIN["lon"], "time": "09:00"})
    assert summary.status_code == 200
    assert {"exposure_level", "peak_window", "time_status", "metadata"} <= summary.json().keys()

    scene_question = "Mujhe route mein heat se bachne ke liye kya karna chahiye?"
    copilot = _response("post", "/api/copilot", json={
        "message": scene_question, "ui_language": "hi",
        "context": {"view": "citizen", "time": "09:00", "origin": ORIGIN, "destination": DESTINATION},
    })
    risk_copilot = _response("post", "/api/copilot", json={
        "message": "Why is this street high risk?", "ui_language": "en",
        "context": {"view": "planner", "time": "15:00", "selected_segment_id": segment_id},
    })
    for payload in (copilot.json(), risk_copilot.json()):
        assert payload["mode"] == "template"
        assert payload["answer"]
        assert not any(term in payload["answer"].casefold() for term in FORBIDDEN)


def test_planner_and_citizen_html_controls_smoke():
    planner = _response("get", "/")
    assert planner.status_code == 200
    for required in ('id="exposure-slider"', 'name="water_points"', 'name="cooling_centres"', 'name="shade_structures"', 'id="optimize-response"', 'id="impact-panel"', '<th>Before</th><th>Modelled After</th>', 'id="copilot-open"'):
        assert required in planner.text

    citizen = _response("get", "/citizen")
    assert citizen.status_code == 200
    for required in ('id="origin-input"', 'id="destination-input"', 'data-language="en"', 'data-language="hi"', 'id="copilot-open"'):
        assert required in citizen.text
