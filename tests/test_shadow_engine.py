"""Prompt 2 geometric-shadow validation in the required SRS order."""

from __future__ import annotations

import json
from pathlib import Path

import geopandas as gpd
import pytest
from shapely.geometry import LineString, Polygon

from app.config import get_config
from app.services.data_engine import project_to_metric_crs
from app.services.shadow_engine import (
    SolarPosition,
    build_shadow_polygons,
    calculate_shade_fractions,
    shadow_length_m,
    shadow_polygon,
    solar_position,
)


METRIC_CRS = "EPSG:32643"


def _building_records(polygons: list[Polygon]) -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame(
        {
            "building_id": [f"synthetic-{index}" for index in range(len(polygons))],
            "height_m": [6.0] * len(polygons),
            "height_source": ["fallback"] * len(polygons),
            "estimated_flag": [True] * len(polygons),
        },
        geometry=polygons,
        crs=METRIC_CRS,
    )


def test_one_synthetic_building_shadow_length():
    """Test 1: a 6 m building at 45 degrees has a 6 m shadow."""
    assert shadow_length_m(6.0, 45.0, max_length_m=150.0) == pytest.approx(6.0)
    assert shadow_length_m(6.0, 2.0, max_length_m=10.0) == 10.0


def test_known_timestamp_solar_position_is_stable():
    """Test 2: pvlib returns stable values for the configured centroid/date/time."""
    solar = solar_position(get_config(), "09:00")
    assert solar.timestamp == "2026-05-15T09:00:00+05:30"
    assert solar.azimuth_deg == pytest.approx(84.795227, abs=0.0001)
    assert solar.elevation_deg == pytest.approx(42.654411, abs=0.0001)


def test_morning_and_afternoon_shadows_follow_sun_opposite_direction():
    """Test 3: an east sun casts west; a west sun casts east."""
    footprint = Polygon([(0, 0), (2, 0), (2, 2), (0, 2)])
    morning = shadow_polygon(footprint, 6.0, 90.0, 45.0, 150.0, 1.0)
    afternoon = shadow_polygon(footprint, 6.0, 270.0, 45.0, 150.0, 1.0)

    assert morning is not None and morning.centroid.x < footprint.centroid.x
    assert afternoon is not None and afternoon.centroid.x > footprint.centroid.x


def test_synthetic_street_shade_fraction():
    """Test 4: a nearby synthetic street is completely covered by its shadow."""
    config = get_config()
    solar = SolarPosition("09:00", azimuth_deg=90.0, elevation_deg=45.0, timestamp="synthetic")
    buildings = _building_records([Polygon([(0, 0), (2, 0), (2, 2), (0, 2)])])
    shadows, stats = build_shadow_polygons(buildings, solar, config)
    streets = gpd.GeoDataFrame(
        {"segment_id": ["synthetic-street"]},
        geometry=[LineString([(-6, 1), (0, 1)])],
        crs=METRIC_CRS,
    )

    fractions = calculate_shade_fractions(streets, shadows, solar, config, stats, 1)
    record = fractions.iloc[0]
    assert record.shade_fraction == pytest.approx(1.0)
    assert record.exposure_fraction == pytest.approx(0.0)


def test_multiple_buildings_produce_multiple_shadows():
    """Test 5: the engine retains independently generated building shadows."""
    config = get_config()
    solar = SolarPosition("09:00", azimuth_deg=90.0, elevation_deg=45.0, timestamp="synthetic")
    buildings = _building_records(
        [
            Polygon([(0, 0), (2, 0), (2, 2), (0, 2)]),
            Polygon([(10, 0), (12, 0), (12, 2), (10, 2)]),
        ]
    )

    shadows, stats = build_shadow_polygons(buildings, solar, config)
    assert len(shadows) == 2
    assert stats.shadow_buildings_skipped == 0
    assert all(shadow.is_valid for shadow in shadows.geometry)


def test_all_canonical_times_process_real_rajwada_sarafa_data():
    """Test 6: all five configured times process the fixed real demo cache."""
    config = get_config()
    buildings = project_to_metric_crs(gpd.read_file(config.cache_data_dir / "buildings.geojson"))
    streets = gpd.read_file(config.cache_data_dir / "streets.geojson").to_crs(buildings.crs)

    assert set(buildings.height_m) == {6.0}
    assert set(buildings.height_source) == {"fallback"}
    assert buildings.estimated_flag.astype(bool).all()

    for canonical_time in config.canonical_times:
        solar = solar_position(config, canonical_time)
        shadows, stats = build_shadow_polygons(buildings, solar, config)
        fractions = calculate_shade_fractions(streets, shadows, solar, config, stats, len(buildings))
        assert len(shadows) == len(buildings)
        assert len(fractions) == len(streets)
        assert stats.invalid_buildings_skipped == 0
        assert stats.invalid_streets_skipped == 0


def test_shade_fraction_bounds_for_all_canonical_snapshots():
    """Test 7: every cached real-data shade fraction remains within [0, 1]."""
    config = get_config()
    for canonical_time in config.canonical_times:
        path = config.cache_data_dir / f"shade_fractions_{canonical_time.replace(':', '-')}.geojson"
        payload = json.loads(path.read_text(encoding="utf-8"))
        fractions = [feature["properties"]["shade_fraction"] for feature in payload["features"]]
        assert fractions
        assert all(0.0 <= fraction <= 1.0 for fraction in fractions)
        assert payload["metadata"]["computation_mode"] == "geometric"
        assert payload["metadata"]["has_estimated_building_heights"] is True
        assert payload["metadata"]["config_version"] == config.version

