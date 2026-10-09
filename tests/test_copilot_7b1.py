from __future__ import annotations

import logging
import re

import pytest
from fastapi.testclient import TestClient

from app.config import get_config
from app.i18n import CITIZEN_EN, CITIZEN_HI
from app.main import app
from app.repositories.cache import load_risk_snapshot
from app.services import copilot_service
from app.services.copilot_templates import COPILOT_LABELS, COPILOT_TEMPLATES
from app.services.intervention_engine import optimize_resources
from app.services.routing_engine import normalize_place_name, route_request, search_places


CLIENT = TestClient(app)


@pytest.mark.parametrize("language,examples", [
    ("en", {
        "platform_guide": "How do I use the time slider?",
        "risk_explanation": "Why is this street high risk?",
        "route_assistant": "From Kadavghat road to M.G.ROAD",
        "safe_stop_assistant": "I need a break on my route",
        "planner_assistant": "I have 2 water points and 1 cooling centre",
        "data_transparency": "How was building height estimated?",
        "heat_safety": "What are the heat safety tips?",
        "unknown": "Tell me about the moon",
    }),
    ("hi", {
        "platform_guide": "मानचित्र कैसे उपयोग करें?",
        "risk_explanation": "इस सड़क का जोखिम अधिक क्यों है?",
        "route_assistant": "कड़ावघाट से एम.जी. रोड जाना है",
        "safe_stop_assistant": "मुझे रास्ते में विराम लेना है",
        "planner_assistant": "मेरे पास 2 पानी के स्थान और 1 शीतलन केंद्र हैं",
        "data_transparency": "इमारत की ऊँचाई का अनुमान कैसे हुआ?",
        "heat_safety": "गर्मी के सुझाव बताएं",
        "unknown": "चंद्रमा के बारे में बताएं",
    }),
    ("en", {
        "platform_guide": "Map kaise use karun?",
        "risk_explanation": "Is street ka risk kyon high hai?",
        "route_assistant": "Kadavghat se M.G. Road jaana hai",
        "safe_stop_assistant": "Mujhe raste mein break lena hai",
        "planner_assistant": "Mere paas 2 water points aur 1 cooling centre hain",
        "data_transparency": "Building height kaise estimate hui?",
        "heat_safety": "Garmi se bachne ke tips?",
        "unknown": "Tell me about moon",
    }),
])
def test_all_intents_classify_in_english_hindi_and_hinglish(language, examples):
    for intent, question in examples.items():
        assert copilot_service.classify_intent(question) == intent
        expected_language = "hi" if language == "hi" or re.search(r"[\u0900-\u097f]", question) or any(
            re.search(rf"\b{re.escape(marker)}\b", f" {question.casefold()} ")
            for marker in get_config().copilot_hinglish_markers
        ) else language
        assert copilot_service.detect_language(question, language) == expected_language


def test_route_question_resolves_places_calls_route_engine_and_returns_api_facts():
    question = "Kadavghat road se M.G. Road jaana hai"
    response = CLIENT.post("/api/copilot", json={"message": question, "ui_language": "en", "context": {"time": "09:00"}})
    assert response.status_code == 200
    result = response.json()
    expected = route_request((22.7146202, 75.8542367), (22.7188165, 75.8553691), "09:00")
    assert result["intent"] == "route_assistant"
    assert result["language"] == "hi"  # Hinglish markers select Devanagari.
    assert result["data_unavailable"] is False
    assert result["facts_used"]["routes"][0]["time_minutes"] == round(expected["routes"][0]["total_time_s"] / 60, 1)
    assert result["facts_used"]["routes"][0]["distance_m"] == round(expected["routes"][0]["total_distance_m"], 1)
    assert result["facts_used"]["recommendation"]["message_id"] == expected["recommendation_message_id"]
    assert all("lat" not in source and "lon" not in source for source in result["sources"])
    assert copilot_service._parse_place_pair("Kadavghat road से M.G. Road जाना है") == ("Kadavghat road", "M.G. Road")
    assert copilot_service._parse_place_pair("मार्ग में गर्मी से बचने के लिए क्या करूँ?") is None


@pytest.mark.parametrize("start,end", [
    ("M.G. Road", "River Side Road"), ("MG Road", "River Side Road"),
    ("mg road", "River Side Road"), ("M G Road", "River Side Road"),
    ("Kadavghat road", "M.G. Road"), ("kadavghat rd", "M.G. Road"),
    ("Kadavghat marg", "M.G. Road"),
    ("Yashwant Road", "River Side Road"), ("River Side Road", "Kadavghat road"),
])
@pytest.mark.parametrize("language", ["en", "hi", "hinglish"])
def test_place_aliases_are_resolved_from_the_cached_index_in_all_languages(start, end, language):
    if language == "en":
        query = f"from {start} to {end}"
    elif language == "hi":
        query = f"{start} से {end} जाना है"
    else:
        query = f"{start} se {end} jaana hai"
    assert copilot_service._parse_place_pair(query) == (start, end)
    for name in (start, end):
        expected = normalize_place_name(name)
        assert expected in {normalize_place_name(place["name"]) for place in search_places(name, limit=3)}


@pytest.mark.parametrize("query,expected", [
    ("from A to B", ("A", "B")),
    ("go from A to B", ("A", "B")),
    ("route from A to B", ("A", "B")),
    ("A to B", ("A", "B")),
    ("A to B route", ("A", "B")),
    ("route from A to B", ("A", "B")),
    ("I want to go from A to B", ("A", "B")),
    ("from the A road to B please", ("A road", "B")),
    ("A -> B", ("A", "B")),
    ("A se B jaana hai", ("A", "B")),
    ("A se B tak", ("A", "B")),
    ("A से B जाना है", ("A", "B")),
    ("A से B तक", ("A", "B")),
])
def test_route_parser_supports_english_hindi_and_hinglish_forms(query, expected):
    assert copilot_service._parse_place_pair(query) == expected


@pytest.mark.parametrize("query,normalized", [
    ("M.G. Road", "mg road"), ("MG Road", "mg road"), ("mg road", "mg road"),
    ("M G Road", "mg road"), ("Kadavghat road", "kadavghat road"),
    ("kadavghat rd", "kadavghat road"), ("Yashwant Road", "yashwant road"),
    ("River Side Road", "river side road"),
])
def test_places_endpoint_uses_normalization_without_changing_its_response_shape(query, normalized):
    response = CLIENT.get("/api/places", params={"q": query})
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"query", "places"}
    assert body["query"] == query
    assert body["places"]
    assert normalized in {normalize_place_name(place["name"]) for place in body["places"]}


def test_ambiguous_place_asks_for_choice_and_caps_options_at_three():
    response = CLIENT.post("/api/copilot", json={
        "message": "from road to MG Road", "ui_language": "en", "context": {"time": "09:00"},
    })
    assert response.status_code == 200
    result = response.json()
    assert "Which one did you mean?" in result["answer"]
    assert 1 < len(result["facts_used"]["ambiguous_place_matches"]) <= 3


def test_best_exact_place_match_wins_by_the_configured_margin():
    config = get_config()
    assert config.copilot_place_fuzzy_threshold == 0.82
    assert config.copilot_place_match_margin == 0.12
    resolved = copilot_service._resolve_place("Yashwant Road", config)
    assert len(resolved) == 1
    assert normalize_place_name(resolved[0]["name"]) == "yashwant road"
    fuzzy = copilot_service._resolve_place("Kadavgat road", config)
    assert len(fuzzy) == 1
    assert normalize_place_name(fuzzy[0]["name"]) == "kadavghat road"


def test_risk_explanation_requires_selected_street_and_matches_why_api():
    missing = CLIENT.post("/api/copilot", json={"message": "Why is this street high risk?", "ui_language": "en"}).json()
    assert "click a street" in missing["answer"].lower()
    segment_id = load_risk_snapshot("09:00")["features"][0]["properties"]["segment_id"]
    why = CLIENT.get(f"/api/segments/{segment_id}/why", params={"time": "09:00"}).json()
    answer = CLIENT.post("/api/copilot", json={
        "message": "Why is this street high risk?", "ui_language": "en",
        "context": {"selected_segment_id": segment_id, "time": "09:00"},
    }).json()
    assert answer["facts_used"]["street"]["risk_score"] == why["street"]["risk_score"]
    assert answer["facts_used"]["drivers"] == why["drivers"]


def test_unknown_place_and_safe_stops_missing_cache_return_grounded_unavailable():
    unknown = CLIENT.post("/api/copilot", json={
        "message": "from Atlantis to Moonbase", "ui_language": "en", "context": {"time": "09:00"},
    }).json()
    assert unknown["data_unavailable"] is True
    assert unknown["answer"] == "Data unavailable for this area."
    stops = CLIENT.post("/api/copilot", json={
        "message": "Mujhe raste mein break lena hai", "ui_language": "en",
        "context": {"origin": {"lat": 22.7146202, "lon": 75.8542367}, "destination": {"lat": 22.7188165, "lon": 75.8553691}, "time": "09:00"},
    }).json()
    assert stops["intent"] == "safe_stop_assistant"
    assert stops["data_unavailable"] is True
    assert CITIZEN_HI["stops_unavailable"] in stops["answer"]
    assert stops["answer"].count(CITIZEN_HI["stops_unavailable"]) == 1
    assert stops["answer"].endswith(CITIZEN_HI["stops_unavailable"] + "।")
    assert stops["facts_used"]["stops"] == []


def test_planner_numbers_and_modelled_impact_match_optimizer():
    counts, used_defaults = copilot_service.parse_resource_counts("Mere paas 2 water points aur 1 cooling centre hain")
    assert counts == {"water_points": 2, "cooling_centres": 1, "shade_structures": 0}
    assert used_defaults is False
    devanagari_counts, _ = copilot_service.parse_resource_counts("मेरे पास ३ पानी के स्थान, १ शीतलन केंद्र और दो छाया संरचनाएँ हैं")
    assert devanagari_counts == {"water_points": 3, "cooling_centres": 1, "shade_structures": 2}
    result = CLIENT.post("/api/copilot", json={"message": "Mere paas 2 water points aur 1 cooling centre hain", "ui_language": "en"}).json()
    expected = optimize_resources(counts)
    assert result["facts_used"]["objective"]["before"] == expected["objective"]["before"]
    assert result["facts_used"]["objective"]["modelled_after"] == expected["objective"]["modelled_after"]
    assert result["facts_used"]["priorities"][0]["share_of_total_reduction_percent"] == round(expected["priorities"][0]["share_of_total_reduction"] * 100, 1)


def test_copilot_wording_plural_percentages_and_hindi_terms_are_clear(monkeypatch):
    assert copilot_service._resource_name("cooling_centres", 1, "en") == "cooling centre"
    assert copilot_service._resource_name("water_points", 2, "en") == "water points"
    assert copilot_service._duration_label(1, "en") == "1 minute"
    assert copilot_service._duration_label(2, "en") == "2 minutes"
    one_minute = copilot_service._recommendation_text(
        {"message_id": "recommendation_heat", "message_params": {"minutes": 1, "percent": "5.0"}}, "en",
    )
    assert "1 minute" in one_minute and "1 minutes" not in one_minute

    english = CLIENT.post("/api/copilot", json={
        "message": "I have 2 water points and 1 cooling centre", "ui_language": "en",
    }).json()
    assert "1 cooling centre" in english["answer"]
    assert "2 water points" in english["answer"]
    assert "0% → 82%" in english["answer"]
    assert "modelled heat exposure on the streets that start as HIGH or CRITICAL" in english["answer"]
    assert "an unnamed street near " in english["answer"]
    assert "osm-" not in english["answer"].lower()
    assert any(source["type"] == "street" and source["id"].startswith("osm-") for source in english["sources"])

    hindi = CLIENT.post("/api/copilot", json={
        "message": "Mere paas 2 water points aur 1 cooling centre hain", "ui_language": "hi",
    }).json()
    assert "संसाधन योजना मॉडल" in hindi["answer"]
    assert "प्रस्तावित सुविधाओं से कवर किया गया हिस्सा" in hindi["answer"]
    assert "0% → 82%" in hindi["answer"]
    assert "अधिक जोखिम वाली सड़कों पर संवेदनशील लोगों के लिए गर्मी का मॉडल-अनुमान" in hindi["answer"]
    assert "अनुकूलक" not in hindi["answer"]
    assert "हस्तक्षेप" not in hindi["answer"]
    assert "कवरेज" not in hindi["answer"]
    assert not any(term in " ".join(CITIZEN_HI.values()) for term in ("अनुकूलक", "हस्तक्षेप"))
    hindi_templates = list(COPILOT_TEMPLATES["hi"].values())
    hindi_templates.extend(value for values in COPILOT_LABELS["hi"].values() if isinstance(values, dict) for value in values.values() if isinstance(value, str))
    assert not any(term in value for value in hindi_templates if isinstance(value, str) for term in ("अनुकूलक", "हस्तक्षेप"))

    height = CLIENT.post("/api/copilot", json={
        "message": "Building height kaise estimate hui?", "ui_language": "hi",
    }).json()
    assert "डेटा में दर्ज इमारतों की संख्या" in height["answer"]


def test_unnamed_street_uses_nearby_label_or_id_fallback(monkeypatch):
    config = get_config()
    monkeypatch.setattr(copilot_service, "nearest_named_place", lambda *_args, **_kwargs: ("Jawahar Marg", 82.0))
    assert copilot_service._unnamed_street_label("osm-123", 22.7, 75.8, "en", config) == "an unnamed street near Jawahar Marg"
    assert copilot_service._unnamed_street_label("osm-123", 22.7, 75.8, "hi", config) == "Jawahar Marg के पास बिना नाम की सड़क"
    monkeypatch.setattr(copilot_service, "nearest_named_place", lambda *_args, **_kwargs: None)
    assert copilot_service._unnamed_street_label("osm-123", 22.7, 75.8, "en", config) == "an unnamed street (ID osm-123)"


def test_height_transparency_uses_cached_building_counts():
    result = CLIENT.post("/api/copilot", json={"message": "Building height kaise estimate hui?", "ui_language": "en"}).json()
    assert result["intent"] == "data_transparency"
    assert "fallback_estimated" in result["facts_used"]["height_source_counts"]
    assert sum(result["facts_used"]["height_source_counts"].values()) > 0
    assert "not a population count" not in result["answer"].lower()


def test_scene_11_includes_route_recommendation_stops_and_generic_tips():
    result = CLIENT.post("/api/copilot", json={
        "message": "Mujhe route mein heat se bachne ke liye kya karna chahiye?", "ui_language": "en",
        "context": {"origin": {"lat": 22.7146202, "lon": 75.8542367}, "destination": {"lat": 22.7188165, "lon": 75.8553691}, "time": "09:00"},
    }).json()
    assert result["intent"] == "heat_safety"
    assert result["language"] == "hi"
    assert "मार्ग सुझाव" in result["answer"]
    assert "ठहराव की जानकारी" in result["answer"]
    assert "पानी साथ रखें" in result["answer"]
    assert result["facts_used"]["stop_status"] == "stops_unavailable"


def test_symptoms_give_emergency_contacts_without_diagnosis_or_treatment():
    result = CLIENT.post("/api/copilot", json={"message": "I feel dizzy and fainted", "ui_language": "en"}).json()
    assert result["intent"] == "heat_safety"
    assert "108" in result["answer"] and "112" in result["answer"]
    assert not any(term in result["answer"].casefold() for term in ("diagnos", "treatment", "heatstroke", "prevent", "safe route"))


def test_llm_gate_rejects_invented_numbers_and_forbidden_wording():
    facts = {"measured_value": 12.5, "place": "Kadavghat road"}
    assert not copilot_service._passes_fact_gate("The modelled value is 99 at Cafe Moon.", "en", facts)
    assert not copilot_service._passes_fact_gate("The modelled value is 12.5 at Cafe Moon.", "en", facts)
    assert not copilot_service._passes_fact_gate("This prevents heatstroke.", "en", facts)
    assert copilot_service._passes_fact_gate("The modelled value is 12.5.", "en", facts)


def test_llm_disabled_timeout_and_rejected_rendering_fall_back_to_templates(monkeypatch):
    config = get_config()
    monkeypatch.setitem(config.feature_flags, "copilot_llm", False)
    monkeypatch.setattr(copilot_service, "_call_llm", lambda *_args: pytest.fail("LLM should be disabled"))
    disabled = CLIENT.post("/api/copilot", json={"message": "How do I use the time slider?", "ui_language": "en"}).json()
    assert disabled["mode"] == "template"

    monkeypatch.setitem(config.feature_flags, "copilot_llm", True)
    monkeypatch.setattr(copilot_service, "_call_llm", lambda *_args: (_ for _ in ()).throw(TimeoutError()))
    timeout = CLIENT.post("/api/copilot", json={"message": "How do I use the time slider?", "ui_language": "en", "context": {"view": "citizen"}}).json()
    assert timeout["mode"] == "template"

    monkeypatch.setattr(copilot_service, "_call_llm", lambda *_args: "This prevents heatstroke.")
    rejected = CLIENT.post("/api/copilot", json={"message": "How do I use the time slider?", "ui_language": "en", "context": {"view": "citizen"}}).json()
    assert rejected["mode"] == "template"

    monkeypatch.setattr(copilot_service, "_call_llm", lambda *_args: "The map has 999 streets.")
    invented_number = CLIENT.post("/api/copilot", json={"message": "How do I use the time slider?", "ui_language": "en", "context": {"view": "citizen"}}).json()
    assert invented_number["mode"] == "template"

    monkeypatch.setattr(copilot_service, "_call_llm", lambda *_args: "This view explains how to compare route options.")
    grounded = CLIENT.post("/api/copilot", json={"message": "How do I use the time slider?", "ui_language": "en", "context": {"view": "citizen"}}).json()
    assert grounded["mode"] == "llm"


def test_privacy_response_shape_and_message_limit(caplog):
    message = "Private question should not appear in logs 716c90"
    with caplog.at_level(logging.INFO, logger="app.services.copilot_service"):
        response = CLIENT.post("/api/copilot", json={
            "message": message, "ui_language": "en", "context": {
                "view": "citizen", "time": "09:00", "origin": {"lat": 22.7146202, "lon": 75.8542367},
            },
        })
    assert response.status_code == 200
    assert message not in caplog.text
    assert "22.7146202" not in caplog.text and "75.8542367" not in caplog.text
    assert set(response.json()) == {"answer", "language", "intent", "mode", "data_unavailable", "sources", "facts_used", "assumptions", "context_entity"}
    overlong = CLIENT.post("/api/copilot", json={"message": "x" * 501, "ui_language": "en"})
    assert overlong.status_code == 422
    assert message not in overlong.text

