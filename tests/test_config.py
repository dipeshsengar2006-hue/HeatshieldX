from app.config import get_config


def test_central_config_contains_prompt_one_and_srs_keys():
    config = get_config()
    assert config.demo_area.city == "Indore"
    assert config.demo_area.radius_m == 500
    assert config.canonical_times == ("09:00", "11:00", "13:00", "15:00", "17:00")
    assert config.building_height_per_floor == 3
    assert config.fallback_building_floors == 2
    assert config.data_source_metadata["facilities"].startswith("OpenStreetMap")
    assert config.risk_normalization_method
    assert config.route_objective_weights
    assert config.representative_heatwave_date.isoformat() == "2026-05-15"
    assert config.representative_timezone == "Asia/Kolkata"
    assert config.temperature_proxy_c == {"09:00": 33.0, "11:00": 38.0, "13:00": 41.0, "15:00": 42.0, "17:00": 38.0}
    assert config.exposure_direct_weight + config.exposure_temperature_weight == 1.0
    assert config.facility_tag_rules["cooling"]["amenity"] == ("library", "community_centre", "townhall")
