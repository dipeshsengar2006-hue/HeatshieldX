"""Prompt 4B undirected-street and cache-grounded explainability contracts."""

from __future__ import annotations

from app.routes import planner
from app.services.explainability_engine import build_risk_drivers, canonical_street_key, deduplicate_risk_features


def _feature(segment_id: str, *, exposure: float = 0.8, risk: float = 70.0) -> dict:
    return {
        "type": "Feature",
        "properties": {
            "segment_id": segment_id,
            "exposure_value": exposure,
            "shade_fraction": 0.2,
            "vulnerability_value": 0.7,
            "access_penalty": 1.0,
            "water_available": False,
            "cooling_available": False,
            "final_risk_raw": 1.12,
            "risk_score": risk,
            "risk_class": "HIGH",
            "observed_or_estimated": "ESTIMATED",
            "modelled_or_interpolated": "MODELLED",
            "computation_mode": "geometric",
            "assumptions_version": "test",
        },
        "geometry": {"type": "LineString", "coordinates": [[75.85, 22.71], [75.86, 22.72]]},
    }


def test_canonical_street_key_is_stable_symmetric_and_keeps_directed_ids():
    forward, backward = _feature("osm-20-10-0"), _feature("osm-10-20-0")
    assert canonical_street_key("osm-20-10-0") == canonical_street_key("osm-10-20-0") == "osm-10-20"
    unique, report = deduplicate_risk_features([forward, backward])
    assert len(unique) == 1
    assert unique[0]["properties"]["directed_segment_ids"] == ["osm-10-20-0", "osm-20-10-0"]
    assert report["differing_undirected_streets"] == 0
    assert report["parallel_edge_difference_count"] == 0


def test_driver_values_and_contributions_come_from_risk_record_only():
    record = _feature("osm-10-20-0")["properties"]
    drivers = build_risk_drivers(record)
    by_id = {driver["id"]: driver for driver in drivers["drivers"]}
    assert by_id["solar_exposure"]["value"] == record["exposure_value"]
    assert by_id["shade"]["value"] == record["shade_fraction"]
    assert by_id["vulnerability"]["value"] == record["vulnerability_value"]
    assert by_id["cooling_access_penalty"]["value"] == record["access_penalty"]
    assert round(sum(driver["relative_contribution"] for driver in drivers["drivers"]), 12) == 1.0
    forbidden = ("diagnos", "patient", "disease", "illness", "heatstroke")
    assert not any(term in drivers["primary_drivers_sentence"].lower() for term in forbidden)


def test_why_endpoint_resolves_both_directions_and_updates_labels(client):
    risk = client.get("/api/risk?time=09:00")
    assert risk.status_code == 200
    assert risk.json()["metadata"]["street_deduplication"]["differing_undirected_streets"] == 0
    feature = next(item for item in risk.json()["features"] if len(item["properties"]["directed_segment_ids"]) > 1)
    first, second = feature["properties"]["directed_segment_ids"][:2]
    first_response = client.get(f"/api/segments/{first}/why?time=09:00")
    second_response = client.get(f"/api/segments/{second}/why?time=09:00")
    assert first_response.status_code == second_response.status_code == 200
    assert first_response.json()["street"] == second_response.json()["street"]
    assert first_response.json()["status_labels"] == ["Observed", "Estimated", "Modelled"]

    interpolated = client.get(f"/api/segments/{first}/why?time=10:00")
    assert interpolated.status_code == 200
    assert interpolated.json()["status_labels"] == ["Observed", "Estimated", "Interpolated"]


def test_compare_hottest_endpoint_reports_ties_and_uses_deterministic_breaking(client, monkeypatch):
    first = _feature("osm-10-20-0", exposure=0.9, risk=65.0)
    second = _feature("osm-30-40-0", exposure=0.9, risk=90.0)
    for feature in (first, second):
        properties = feature["properties"]
        properties["canonical_street_key"] = canonical_street_key(properties["segment_id"])
        properties["directed_segment_ids"] = [properties["segment_id"]]
    snapshot = {"type": "FeatureCollection", "features": [second, first], "metadata": {"modelled_or_interpolated": "MODELLED"}}
    monkeypatch.setattr(planner, "_risk_snapshot_or_503", lambda _time: snapshot)

    response = client.get("/api/compare/hottest?time=09:00")
    assert response.status_code == 200
    payload = response.json()
    assert payload["hottest_tie_count"] == 2
    assert payload["highest_risk_tie_count"] == 1
    assert payload["hottest"]["canonical_street_key"] == "osm-10-20"
    assert payload["highest_risk"]["canonical_street_key"] == "osm-30-40"
