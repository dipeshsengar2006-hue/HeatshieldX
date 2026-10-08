"""Prompt 3 SRS 60-61 cache-first exposure validation."""

from __future__ import annotations

from app.config import get_config
from app.services.exposure_engine import (
    build_canonical_exposure_snapshot,
    fallback_exposure_value,
    geometric_exposure_value,
    temperature_factor,
)


def _street_collection() -> dict:
    return {
        "type": "FeatureCollection",
        "features": [{
            "type": "Feature",
            "properties": {"segment_id": "synthetic-1", "length_m": 10.0},
            "geometry": {"type": "LineString", "coordinates": [[75.0, 22.0], [75.001, 22.001]]},
        }],
    }


def test_exposure_values_are_bounded_and_deterministic():
    config = get_config()
    factor = temperature_factor(config, "15:00")
    values = [geometric_exposure_value(direct, factor, config) for direct in (0.0, 0.25, 0.5, 1.0)]
    assert all(0.0 <= value <= 1.0 for value in values)
    assert geometric_exposure_value(0.5, factor, config) == geometric_exposure_value(0.5, factor, config)
    assert 0.0 <= fallback_exposure_value(factor, config) <= 1.0


def test_geometric_exposure_is_monotonic_for_direct_exposure_and_shade():
    config = get_config()
    factor = temperature_factor(config, "13:00")
    low_direct = geometric_exposure_value(0.2, factor, config)
    high_direct = geometric_exposure_value(0.8, factor, config)
    assert high_direct >= low_direct
    assert geometric_exposure_value(1.0 - 0.8, factor, config) <= geometric_exposure_value(1.0 - 0.2, factor, config)


def test_geometric_shadow_failure_uses_non_shadow_fallback():
    config = get_config().model_copy(update={"exposure_computation_mode": "geometric"})

    def missing_shadow(*_args, **_kwargs):
        raise FileNotFoundError("synthetic missing shadow snapshot")

    snapshot = build_canonical_exposure_snapshot(
        "11:00", config, shadow_loader=missing_shadow, street_loader=lambda *_args: _street_collection()
    )
    assert snapshot["metadata"]["computation_mode"] == "estimated"
    assert "missing shadow snapshot" in snapshot["metadata"]["fallback_reason"]
    assert snapshot["features"][0]["properties"]["fallback_description"].startswith("Estimated exposure mode")


def test_explicit_estimated_mode_never_loads_shadow_data():
    config = get_config().model_copy(update={"exposure_computation_mode": "estimated"})

    def should_not_run(*_args, **_kwargs):
        raise AssertionError("Shadow data must not be used by estimated mode")

    snapshot = build_canonical_exposure_snapshot(
        "11:00", config, shadow_loader=should_not_run, street_loader=lambda *_args: _street_collection()
    )
    assert snapshot["metadata"]["computation_mode"] == "estimated"
    assert snapshot["features"][0]["properties"]["exposure_value"] == fallback_exposure_value(temperature_factor(config, "11:00"), config)
