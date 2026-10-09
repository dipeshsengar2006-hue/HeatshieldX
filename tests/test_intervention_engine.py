"""Prompt 5A intervention-candidate, optimizer, and impact contracts."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.config import get_config
from app.repositories.cache import load_cached_geojson
from app.services.intervention_engine import (
    get_optimization_context,
    list_candidates,
    optimize_resources,
    validate_resource_counts,
)


@pytest.fixture(scope="module")
def full_area_plans():
    """Reuse deterministic full-area plans across the expensive regression module."""
    return {
        "zero": optimize_resources({"water_points": 0, "cooling_centres": 0, "shade_structures": 0}),
        "small": optimize_resources({"water_points": 2, "cooling_centres": 1, "shade_structures": 2}),
        "shade": optimize_resources({"water_points": 0, "cooling_centres": 0, "shade_structures": 1}),
        "large": optimize_resources({"water_points": 4, "cooling_centres": 2, "shade_structures": 4}),
    }


def _plan(values: dict[str, int]) -> dict:
    return optimize_resources(values)


@pytest.mark.slow
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


def test_resource_limits_return_readable_422_errors(client):
    assert validate_resource_counts({"water_points": 10, "cooling_centres": 10, "shade_structures": 10}) == {
        "water_points": 10, "cooling_centres": 10, "shade_structures": 10,
    }
    assert client.post("/api/optimize", json={"water_points": -1}).status_code == 422
    assert client.post("/api/optimize", json={"cooling_centres": 11}).status_code == 422
    assert client.post("/api/optimize", json={"shade_structures": 1.5}).status_code == 422


@pytest.mark.slow
def test_zero_resources_preserve_before_scenario(full_area_plans):
    zero = full_area_plans["zero"]
    assert zero["priorities"] == []
    assert zero["objective"]["before"] == zero["objective"]["modelled_after"]
    assert zero["objective"]["total_reduction"] == 0
    for snapshot in zero["after_snapshots"].values():
        assert snapshot["metadata"]["config_version"] == get_config().version


@pytest.mark.slow
def test_greedy_plan_is_deterministic_and_objective_accounting_is_exact(client, full_area_plans):
    requested = {"water_points": 2, "cooling_centres": 1, "shade_structures": 2}
    first, second = full_area_plans["small"], _plan(requested)
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


@pytest.mark.slow
def test_effects_are_monotonic_and_coefficient_changes_the_result(full_area_plans):
    shade_plan = full_area_plans["shade"]
    before = full_area_plans["zero"]
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


@pytest.mark.slow
def test_larger_budget_is_not_worse_and_impact_metrics_keep_required_labels(full_area_plans):
    small = full_area_plans["small"]
    large = full_area_plans["large"]
    assert large["objective"]["total_reduction"] >= small["objective"]["total_reduction"]
    assert large["objective"]["modelled_after"] <= small["objective"]["modelled_after"]
    expected = {
        "high_risk_vulnerable_exposure", "cooling_coverage", "water_coverage",
        "average_network_distance_to_cooling", "average_network_distance_to_water",
        "intervention_coverage", "streets_per_risk_class_15_00",
    }
    assert set(small["metrics"]) == expected
    assert all(metric["label"] == "Modelled Impact" for metric in small["metrics"].values())


@pytest.mark.parametrize(
    ("fixture_key", "resources"),
    [
        ("2-1-2", {"water_points": 2, "cooling_centres": 1, "shade_structures": 2}),
        ("4-2-4", {"water_points": 4, "cooling_centres": 2, "shade_structures": 4}),
    ],
)
@pytest.mark.slow
def test_vectorized_optimizer_matches_5a_regression_fixture(fixture_key, resources):
    fixtures = json.loads((Path(__file__).parent / "fixtures" / "optimizer_5a_regression.json").read_text(encoding="utf-8"))
    expected = fixtures[fixture_key]
    # Supplying config deliberately bypasses disk/memory plans and exercises NumPy scoring.
    plan = optimize_resources(resources, get_config())
    assert [choice["candidate_id"] for choice in plan["priorities"]] == expected["candidate_ids"]
    assert plan["objective"]["before"] == pytest.approx(expected["before"], rel=1e-6)
    assert plan["objective"]["modelled_after"] == pytest.approx(expected["after"], rel=1e-6)
    for metric, expected_value in expected["metric_after"].items():
        assert plan["metrics"][metric]["modelled_after"] == pytest.approx(expected_value, rel=1e-6)


@pytest.mark.slow
def test_vectorized_optimizer_full_area_performance_is_lenient():
    import time

    started = time.perf_counter()
    optimize_resources({"water_points": 4, "cooling_centres": 2, "shade_structures": 4}, get_config())
    assert time.perf_counter() - started < 15


@pytest.mark.slow
def test_disk_cached_plan_equals_a_fresh_computation():
    resources = {"water_points": 1, "cooling_centres": 1, "shade_structures": 1}
    cached = optimize_resources(resources)
    computed = optimize_resources(resources, get_config())
    assert {key: value for key, value in cached.items() if key != "runtime_seconds"} == {
        key: value for key, value in computed.items() if key != "runtime_seconds"
    }
