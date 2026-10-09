from __future__ import annotations

import logging
import re

from fastapi.testclient import TestClient

from app.config import get_config
from app.i18n import CITIZEN_EN, CITIZEN_HI, validate_citizen_i18n
from app.main import app
from app.repositories.cache import load_exposure_snapshot


def test_bilingual_catalogs_are_complete_safe_and_placeholder_compatible():
    validate_citizen_i18n()
    assert CITIZEN_EN.keys() == CITIZEN_HI.keys()
    forbidden_english = ("heatstroke", "prevent", "safe route")
    forbidden_hindi = ("सुरक्षित मार्ग", "सुरक्षित रास्ता", "हीटस्ट्रोक", "बचाव की गारंटी", "इलाज", "दवा", "निदान")
    for message_id, english in CITIZEN_EN.items():
        hindi = CITIZEN_HI[message_id]
        assert english.strip() and hindi.strip()
        assert set(re.findall(r"\{([a-zA-Z0-9_]+)\}", english)) == set(re.findall(r"\{([a-zA-Z0-9_]+)\}", hindi))
        assert not any(term in english.casefold() for term in forbidden_english)
        assert not any(term in hindi.casefold() for term in forbidden_hindi)


def test_citizen_page_contains_both_language_controls_and_embedded_dictionaries():
    response = TestClient(app).get("/citizen")
    assert response.status_code == 200
    assert 'data-language="en"' in response.text
    assert 'data-language="hi"' in response.text
    assert 'id="citizen-catalogs"' in response.text
    assert "हिन्दी" in response.text
    assert "© OpenStreetMap contributors" in response.text


def test_public_summary_uses_cached_area_peak_and_unavailable_facility_messages(caplog):
    client = TestClient(app)
    lat, lon = 22.7177, 75.855
    with caplog.at_level(logging.INFO):
        response = client.post("/api/public/summary", json={"lat": lat, "lon": lon, "time": "09:00"})
    assert response.status_code == 200
    result = response.json()
    means = {}
    config = get_config()
    for canonical_time in config.canonical_times:
        features = load_exposure_snapshot(canonical_time, config)["features"]
        means[canonical_time] = sum(float(item["properties"]["exposure_value"]) for item in features) / len(features)
    maximum = max(means.values())
    expected = [time for time, value in means.items() if value >= maximum * config.peak_window_ratio]
    peak = result["peak_window"]
    assert peak["value"] == {"start_time": expected[0], "end_time": expected[-1]}
    assert peak["message_id"] == "summary_peak_window"
    assert peak["english_text"] == f"Highest modelled exposure {expected[0]}-{expected[-1]}"
    assert peak["status"] == "MODELLED"
    assert result["exposure_level"]["message_id"].startswith("summary_level_")
    assert result["exposure_level"]["status_message_id"] == "summary_status_modelled"
    for field in ("distance_to_water", "distance_to_cooling"):
        assert result[field]["message_id"] == "summary_data_unavailable"
        assert result[field]["english_text"] == "Data unavailable (no recorded facility)"
        assert result[field]["status_message_id"] == "summary_status_estimated"
    assert str(lat) not in caplog.text and str(lon) not in caplog.text


def test_public_summary_rejects_invalid_and_out_of_area_locations():
    client = TestClient(app)
    invalid_time = client.post("/api/public/summary", json={"lat": 22.7177, "lon": 75.855, "time": "08:30"})
    assert invalid_time.status_code == 422
    assert invalid_time.json()["message_id"] == "route_error_422"
    outside = client.post("/api/public/summary", json={"lat": 0, "lon": 0, "time": "09:00"})
    assert outside.status_code == 422
    assert outside.json()["message_id"] == "summary_error_area"


def test_route_api_keeps_english_text_and_supplies_message_ids_for_citizen_fields():
    response = TestClient(app).post(
        "/api/routes",
        json={
            "origin": {"lat": 22.7146202, "lon": 75.8542367},
            "destination": {"lat": 22.7188165, "lon": 75.8553691},
            "time": "09:00",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["recommendation_message_id"] in CITIZEN_EN
    assert payload["recommendation"] == CITIZEN_EN[payload["recommendation_message_id"]].format(**payload["recommendation_message_params"])
    for route in payload["routes"]:
        assert route["route_type_message_id"] in CITIZEN_EN
        assert route["cooling_access_message_id"] in CITIZEN_EN
        assert route["modelled_or_interpolated_message_id"] in CITIZEN_EN
        stops = route["stops"]
        assert stops["status_message_id"] in CITIZEN_EN
        if stops["items"]:
            for stop in stops["items"]:
                assert stop["stop_type_message_id"] in CITIZEN_EN
                assert stop["verified_status_message_id"] in CITIZEN_EN
                assert stop["rating_message_id"] in CITIZEN_EN
    assert payload["routes"][0]["stops"]["status"] == "No stop data available"
