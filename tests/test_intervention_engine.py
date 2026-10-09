"""Prompt 5A intervention-candidate, optimizer, and impact contracts."""

from __future__ import annotations

import json

import pytest

from app.config import get_config
from app.repositories.cache import load_cached_geojson
from app.services.intervention_engine import (
    get_optimization_context,
    list_candidates,
    optimize_resources,
    validate_resource_counts,
)


def _plan(values: dict[str, int]) -> dict:
    return optimize_resources(values)


def test_candidates_are_proposed_stable_and_separate_from_osm_facilities():
    config = get_config()
    payload = list_candidates()
    facilities = load_cached_geojson("facilities")
    facility_ids = {feature["properties"].get("facility_id") for feature in facilities["features"]}
    candidates = payload["candidates"]

    assert payload["config_version"] == config.version
    assert candidates == sorted(candidates, key=lambda candidate: candidate["candidate_id"])
    assert all(candidate["provenance"]["source_type"] == "proposed candidate" for candidate in candidates)
    assert not {candidate["candidate_id"] for candidate in candidates} & facility_ids

    context = get_optimization_context()
    for candidate in candidates:
        street = context.streets[candidate["street_canonical_key"]]
        if candidate["type"] in {"water_points", "cooling_centres"}:
            assert street["length_m"] >= config.candidate_min_street_length_m
    assert {candidate["street_canonical_key"] for candidate in candidates if candidate["type"] == "shade_structures"} == set(context.streets)


def test_zero_resources_preserve_before_scenario_and_limits_are_validated(client):
    zero = _plan({"water_points": 0, "cooling_centres": 0, "shade_structures": 0})
    assert zero["priorities"] == []
    assert zero["objective"]["before"] == zero["objective"]["modelled_after"]
    assert zero["objective"]["total_reduction"] == 0
    assert validate_resource_counts({"water_points": 10, "cooling_centres": 10, "shade_structures": 10}) == {
        "water_points": 10, "cooling_centres": 10, "shade_structures": 10,
    }
    for snapshot in zero["after_snapshots"].values():
        assert snapshot["metadata"]["config_version"] == get_config().version

    assert client.post("/api/optimize", json={"water_points": -1}).status_code == 422
    assert client.post("/api/optimize", json={"cooling_centres": 11}).status_code == 422
    assert client.post("/api/optimize", json={"shade_structures": 1.5}).status_code == 422


def test_greedy_plan_is_deterministic_and_objective_accounting_is_exact(client):
    requested = {"water_points": 2, "cooling_centres": 1, "shade_structures": 2}
    first, second = _plan(requested), _plan(requested)
    assert first["plan_id"] == second["plan_id"] == f"w2-c1-s2-{get_config().version}"
    assert first["priorities"] == second["priorities"]
    assert all(choice["marginal_benefit"] > 0 for choice in first["priorities"])
    assert sum(choice["marginal_benefit"] for choice in first["priorities"]) == pytest.approx(first["objective"]["total_reduction"])
    assert first["objective"]["modelled_after"] <= first["objective"]["before"]
    assert not {"medical", "heatstroke", "degree", "°c"} & set(json.dumps(first).lower().split())
    for resource_type in ("water_points", "cooling_centres", "shade_structures"):
        benefits = [choice["marginal_benefit"] for choice in first["priorities"] if choice["type"] == resource_type]
        assert benefits == sorted(benefits, reverse=True)

    response = client.post("/api/optimize", json=requested)
    assert response.status_code == 200
    assert response.json()["label"] == "Modelled"
    assert client.get(f"/api/plans/{first['plan_id']}").status_code == 200
    after = client.get(f"/api/risk?time=14:00&plan_id={first['plan_id']}")
    assert after.status_code == 200
    assert after.json()["metadata"]["interpolated"] is True
    assert after.json()["metadata"]["plan_id"] == first["plan_id"]


def test_effects_are_monotonic_and_coefficient_changes_the_result():
    shade_plan = _plan({"water_points": 0, "cooling_centres": 0, "shade_structures": 1})
    before = _plan({"water_points": 0, "cooling_centres": 0, "shade_structures": 0})
    for canonical_time, snapshot in shade_plan["after_snapshots"].items():
        baseline = {feature["properties"]["canonical_street_key"]: feature for feature in before["after_snapshots"][canonical_time]["features"]}
        for feature in snapshot["features"]:
            old = baseline[feature["properties"]["canonical_street_key"]]["properties"]
            new = feature["properties"]
            assert new["exposure_value"] <= old["exposure_value"]
            assert new["final_risk_raw"] <= old["final_risk_raw"]
            assert new["distance_to_water_m"] == old["distance_to_water_m"]
            assert new["distance_to_cooling_m"] == old["distance_to_cooling_m"]

    config = get_config()
    no_shade_effect = config.model_copy(
        update={
            "version": f"{config.version}-coefficient-test",
            "intervention_effect_coefficients": {**config.intervention_effect_coefficients, "shade_structure": 0.0},
        },
        deep=True,
    )
    changed = optimize_resources({"water_points": 0, "cooling_centres": 0, "shade_structures": 1}, no_shade_effect)
    assert changed["objective"]["total_reduction"] == 0
    assert shade_plan["objective"]["total_reduction"] > changed["objective"]["total_reduction"]


def test_larger_budget_is_not_worse_and_impact_metrics_keep_required_labels():
    small = _plan({"water_points": 2, "cooling_centres": 1, "shade_structures": 2})
    large = _plan({"water_points": 4, "cooling_centres": 2, "shade_structures": 4})
    assert large["objective"]["total_reduction"] >= small["objective"]["total_reduction"]
    assert large["objective"]["modelled_after"] <= small["objective"]["modelled_after"]
    expected = {
        "high_risk_vulnerable_exposure", "cooling_coverage", "water_coverage",
        "average_network_distance_to_cooling", "average_network_distance_to_water",
        "intervention_coverage", "streets_per_risk_class_15_00",
    }
    assert set(small["metrics"]) == expected
    assert all(metric["label"] == "Modelled Impact" for metric in small["metrics"].values())
