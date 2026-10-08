"""Prompt 4A deterministic vulnerability, access, and risk contracts."""

from app.config import get_config
from app.services.cooling_access_engine import _walking_distances_to_facilities, bounded_distance_penalty, build_cooling_access_records
from app.services.risk_engine import baseline_risk, final_risk_raw, normalize_global, risk_class
from app.services.vulnerability_engine import build_vulnerability_records


def test_access_penalty_is_bounded_monotonic_and_missing_facility_is_worst():
    assert bounded_distance_penalty(0.0, 300.0) == 0.0
    assert bounded_distance_penalty(150.0, 300.0) == 0.5
    assert bounded_distance_penalty(900.0, 300.0) == 1.0
    assert bounded_distance_penalty(None, 300.0) == 1.0


def test_walking_distance_uses_the_cached_street_network_not_direct_distance():
    import geopandas as gpd
    from shapely.geometry import LineString, Point

    streets = gpd.GeoDataFrame(geometry=[LineString([(0, 0), (100, 0)]), LineString([(100, 0), (100, 100)])], crs="EPSG:32643")
    facilities = gpd.GeoDataFrame(geometry=[Point(100, 100)], crs="EPSG:32643")
    # The first segment midpoint is 150 m by the street network, not the
    # approximately 112 m direct-line distance to the facility.
    assert _walking_distances_to_facilities(streets, facilities) == [150.0, 50.0]


def test_cached_healthcare_is_not_counted_as_cooling_or_water():
    access, metadata = build_cooling_access_records()
    assert metadata["healthcare_facility_count"] > 0
    assert metadata["water_facility_count"] == 0
    assert metadata["cooling_facility_count"] == 0
    assert access
    assert all(record["access_penalty"] == 1.0 for record in access.values())


def test_risk_is_monotonic_in_exposure_vulnerability_and_access():
    baseline = baseline_risk(0.4, 0.5)
    assert baseline_risk(0.6, 0.5) > baseline
    assert baseline_risk(0.4, 0.7) > baseline
    assert final_risk_raw(baseline, 1.0) > final_risk_raw(baseline, 0.0)


def test_global_normalization_and_zero_variance_are_deterministic():
    assert normalize_global([2.0, 3.0, 4.0]) == [0.0, 50.0, 100.0]
    assert normalize_global([2.0, 2.0, 2.0]) == [50.0, 50.0, 50.0]
    assert normalize_global([2.0, 3.0, 4.0]) == normalize_global([2.0, 3.0, 4.0])


def test_risk_class_boundaries_are_modelled_priority_labels():
    assert risk_class(0.0) == "LOW"
    assert risk_class(25.0) == "LOW"
    assert risk_class(25.1) == "MODERATE"
    assert risk_class(50.0) == "MODERATE"
    assert risk_class(50.1) == "HIGH"
    assert risk_class(75.0) == "HIGH"
    assert risk_class(75.1) == "CRITICAL"
    assert risk_class(100.0) == "CRITICAL"


def test_vulnerability_records_are_estimated_osm_proxies_with_levels_only():
    records, metadata = build_vulnerability_records(get_config())
    assert records
    assert metadata["assumption_label"]
    assert "available_proxy_tags" in metadata
    for record in records.values():
        assert 0.0 <= record["elderly_component"] <= 1.0
        assert 0.0 <= record["outdoor_worker_component"] <= 1.0
        assert 0.0 <= record["vulnerability_value"] <= 1.0
        assert record["estimated_flag"] is True
        assert record["estimated_vulnerability"] in {"low", "moderate", "high"}
