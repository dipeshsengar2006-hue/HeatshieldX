"""Grounded, cache-backed Copilot retrieval and safe answer rendering."""

from __future__ import annotations

import json
import logging
import os
import re
import time
import urllib.error
import urllib.request
from decimal import Decimal, InvalidOperation
from typing import Any

from app.config import AppConfig, get_config
from app.i18n import CITIZEN_EN, CITIZEN_HI
from app.repositories.cache import load_cached_geojson, load_risk_snapshot
from app.services.copilot_templates import COPILOT_LABELS, COPILOT_TEMPLATES
from app.services.explainability_engine import explain_segment_snapshot
from app.services.intervention_engine import get_plan, optimize_resources
from app.services.routing_engine import RoutingError, nearest_named_place, ranked_place_matches, route_request
from shapely.geometry import shape


LOGGER = logging.getLogger(__name__)
_RESOURCE_TYPES = ("water_points", "cooling_centres", "shade_structures")
_NUMBER_WORDS = {
    "ek": 1, "एक": 1, "do": 2, "दो": 2, "teen": 3, "तीन": 3,
    "char": 4, "chaar": 4, "चार": 4, "paanch": 5, "panch": 5, "पाँच": 5, "पांच": 5,
}
_DIGIT_TRANSLATION = str.maketrans("०१२३४५६७८९", "0123456789")
_SYMPTOM_TERMS = (
    "dizzy", "dizziness", "fainted", "fainting", "behosh", "बेहोश", "chakkar", "चक्कर",
    "vomit", "vomiting", "ulti", "उल्टी", "confused", "confusion", "उलझन",
)
_FORBIDDEN_OUTPUT = (
    "heatstroke", "prevent", "safe route", "diagnose", "diagnosis", "treatment",
    "सुरक्षित मार्ग", "सुरक्षित रास्ता", "हीटस्ट्रोक", "बचाव की गारंटी", "निदान", "इलाज", "दवा",
)


def _contains_any(text: str, values: tuple[str, ...] | list[str]) -> bool:
    return any(value.casefold() in text for value in values if value)


def detect_language(message: str, ui_language: str, config: AppConfig | None = None) -> str:
    active = config or get_config()
    if re.search(r"[\u0900-\u097f]", message):
        return "hi"
    folded = f" {message.casefold()} "
    if any(re.search(rf"\b{re.escape(marker)}\b", folded) for marker in active.copilot_hinglish_markers):
        return "hi"
    return ui_language


def classify_intent(message: str, config: AppConfig | None = None) -> str:
    """Classify from configured multilingual keyword groups, without external models."""
    active = config or get_config()
    folded = message.casefold()
    if _contains_any(folded, _SYMPTOM_TERMS):
        return "heat_safety"
    groups = active.copilot_intent_keywords
    order = (
        "planner_assistant", "data_transparency", "platform_guide", "risk_explanation",
        "safe_stop_assistant", "heat_safety", "route_assistant",
    )
    for intent in order:
        keywords = groups.get(intent, {})
        if any(_contains_any(folded, tuple(values)) for values in keywords.values()):
            return intent
    return "unknown"


def _template(language: str, key: str, **params: Any) -> str:
    return COPILOT_TEMPLATES[language][key].format(**params)


def _citizen(language: str, message_id: str, **params: Any) -> str:
    catalog = CITIZEN_HI if language == "hi" else CITIZEN_EN
    return catalog[message_id].format(**params)


def _source(source_type: str, identifier: Any, label: str) -> dict[str, str]:
    return {"type": source_type, "id": str(identifier), "label": label}


def _duration_label(value: Any, language: str) -> str:
    minutes = _format_number(value, 1)
    if language == "hi":
        unit = "मिनट"
    else:
        unit = "minute" if float(value) == 1 else "minutes"
    return f"{minutes} {unit}"


def _recommendation_text(recommendation: dict[str, Any], language: str) -> str:
    text = _citizen(language, recommendation["message_id"], **recommendation["message_params"])
    minutes = recommendation["message_params"].get("minutes")
    if language == "en" and minutes == 1:
        text = text.replace("1 minutes", "1 minute")
    return text


def _resource_name(resource_type: str, count: int, language: str) -> str:
    labels = {
        "en": {
            "water_points": ("water point", "water points"),
            "cooling_centres": ("cooling centre", "cooling centres"),
            "shade_structures": ("shade structure", "shade structures"),
        },
        "hi": {
            "water_points": ("पानी का स्थान", "पानी के स्थान"),
            "cooling_centres": ("ठंडक केंद्र", "ठंडक केंद्र"),
            "shade_structures": ("छाया संरचना", "छाया संरचनाएँ"),
        },
    }
    return labels[language][resource_type][0 if count == 1 else 1]


def _unnamed_street_label(
    identifier: str,
    latitude: float | None,
    longitude: float | None,
    language: str,
    config: AppConfig,
) -> str:
    if latitude is not None and longitude is not None:
        nearby = nearest_named_place(latitude, longitude, config, max_distance_m=150)
        if nearby is not None:
            return _template(language, "unnamed_street_near", name=nearby[0])
    return _template(language, "unnamed_street_id", id=identifier)


def _empty_result(language: str, intent: str, answer: str | None = None) -> dict[str, Any]:
    return {
        "answer": answer or _template(language, "unavailable"),
        "language": language,
        "intent": intent,
        "mode": "template",
        "data_unavailable": answer is None,
        "sources": [],
        "facts_used": {},
        "assumptions": [],
        "context_entity": None,
    }


def _parse_place_pair(message: str) -> tuple[str, str] | None:
    patterns = (
        r"^\s*(.+?)\s*(?:->|→)\s*(.+?)\s*[?.!,]*$",
        r"^\s*(?:(?:please\s+)?(?:i\s+want\s+to\s+)?(?:go\s+)?(?:the\s+)?route\s+from\s+|(?:please\s+)?(?:i\s+want\s+to\s+)?(?:go\s+)?from\s+|(?:please\s+)?from\s+)(.+?)\s+to\s+(.+?)(?:\s+route)?\s*[?.!,]*$",
        r"^\s*(.+?)\s+to\s+(.+?)(?:\s+route)?\s*[?.!,]*$",
        r"^\s*(.+?)\s+se\s+(.+?)\s+(?:jaana|jana)(?:\s+hai)?\s*[?.!]*$",
        r"^\s*(.+?)\s+se\s+(.+?)\s+tak\s*[?.!]*$",
        r"^\s*(.+?)\s+से\s+(.+?)\s+(?:जाना\s+है|जाएँ|जाए)\s*[?.!।]*$",
        r"^\s*(.+?)\s+से\s+(.+?)\s+तक\s*[?.!।]*$",
    )
    for pattern in patterns:
        match = re.search(pattern, message.strip(), flags=re.IGNORECASE)
        if match:
            start, end = (part.strip(" \t,.;:!?।") for part in match.groups())
            start = re.sub(r"^(?:please\s+|i\s+want\s+to\s+|go\s+|the\s+)+", "", start, flags=re.IGNORECASE)
            end = re.sub(r"\s+(?:please|route)$", "", end, flags=re.IGNORECASE)
            if start and end:
                return start, end
    return None


def _resolve_place(query: str, config: AppConfig) -> list[dict[str, Any]]:
    ranked = ranked_place_matches(query, config, limit=12)
    if not ranked:
        return []
    best_score = ranked[0][1]
    margin = config.copilot_place_match_margin
    if len(ranked) == 1 or best_score - ranked[1][1] >= margin:
        return [ranked[0][0]]
    return [record for record, _score in ranked[:3]]


def _resolve_endpoints(message: str, context: dict[str, Any], config: AppConfig) -> tuple[Any, Any, str, str, list[dict[str, str]], dict[str, Any]] | dict[str, Any]:
    parsed = _parse_place_pair(message)
    if parsed:
        origin_matches = _resolve_place(parsed[0], config)
        destination_matches = _resolve_place(parsed[1], config)
        if not origin_matches or not destination_matches:
            return {"unavailable": True}
        ambiguous = []
        for role, matches in (("origin", origin_matches), ("destination", destination_matches)):
            if len(matches) > 1:
                for item in matches[:3]:
                    ambiguous.append({"role": role, "name": item["name"], "place_id": item["place_id"]})
        if ambiguous:
            return {"ambiguous": ambiguous[:3]}
        origin, destination = origin_matches[0], destination_matches[0]
        origin_xy = origin["location"]["coordinates"]
        destination_xy = destination["location"]["coordinates"]
        origin_point, destination_point = (origin_xy[1], origin_xy[0]), (destination_xy[1], destination_xy[0])
        sources = [
            _source("place", origin["place_id"], origin["name"]),
            _source("place", destination["place_id"], destination["name"]),
        ]
        facts = {"origin_name": origin["name"], "destination_name": destination["name"]}
        return origin_point, destination_point, origin["name"], destination["name"], sources, facts

    origin, destination = context.get("origin"), context.get("destination")
    if not origin or not destination:
        return {"missing": True}
    origin_point = (float(origin["lat"]), float(origin["lon"]))
    destination_point = (float(destination["lat"]), float(destination["lon"]))
    # Coordinate values are used transiently but never copied into facts, sources, or logs.
    return origin_point, destination_point, "selected origin", "selected destination", [], {}


def _route_options(message: str, context: dict[str, Any], language: str, config: AppConfig) -> dict[str, Any]:
    endpoints = _resolve_endpoints(message, context, config)
    if isinstance(endpoints, dict):
        return endpoints
    if not context.get("time"):
        return {"missing_time": True}
    origin, destination, origin_name, destination_name, place_sources, place_facts = endpoints
    payload = route_request(origin, destination, str(context["time"]), config)
    routes = []
    for route in payload["routes"]:
        comparison = route.get("classification_vs_fastest") or {}
        routes.append({
            "route_type": route["route_type"],
            "route_name": _citizen(language, route.get("route_type_message_id", "card_fastest")),
            "time_minutes": round(float(route["total_time_s"]) / 60, 1),
            "distance_m": round(float(route["total_distance_m"]), 1),
            "modelled_heat_exposure": round(float(route["modelled_heat_exposure"]), 3),
            "heat_change_percent": round(float(comparison.get("modelled_heat_exposure_change_percent", 0)), 1),
            "extra_minutes": round(float(comparison.get("extra_minutes", 0)), 1),
            "weighted_shade_percent": round(float(route.get("weighted_shade", 0)) * 100, 1),
            "cooling_access": route.get("cooling_access"),
            "cooling_access_message_id": route.get("cooling_access_message_id"),
            "source_id": route["route_type"],
        })
    recommendation = {
        "message_id": payload.get("recommendation_message_id"),
        "message_params": payload.get("recommendation_message_params", {}),
    }
    return {
        "routes": routes,
        "recommendation": recommendation,
        "origin_name": origin_name,
        "destination_name": destination_name,
        "time": str(context["time"]),
        "sources": place_sources + [_source("route", route["route_type"], route["route_name"]) for route in routes],
        "facts": {**place_facts, "time": str(context["time"]), "routes": routes, "recommendation": recommendation},
        "route_payload": payload,
    }


def _risk_explanation(segment_id: str, time_value: str) -> dict[str, Any] | None:
    # Use the exact interpolation/cache selection used by the public WHY endpoint.
    from app.routes.planner import _risk_snapshot_or_503, _street_name

    snapshot = _risk_snapshot_or_503(time_value)
    payload = explain_segment_snapshot(snapshot, segment_id)
    if payload is None:
        return None
    street_name = _street_name(payload["street"]["directed_segment_ids"])
    payload["street"]["street_name"] = street_name
    if not street_name:
        target = next((
            feature for feature in snapshot.get("features", [])
            if segment_id == feature.get("properties", {}).get("segment_id")
            or segment_id in feature.get("properties", {}).get("directed_segment_ids", [])
        ), None)
        geometry = shape(target["geometry"]) if target else None
        if geometry is not None:
            point = geometry.centroid
            nearest = nearest_named_place(point.y, point.x, get_config(), max_distance_m=150)
            payload["street"]["nearest_named_place"] = nearest[0] if nearest else None
    payload["requested_time"] = time_value
    return payload


def _number_before(text: str) -> int | None:
    normalized = text.translate(_DIGIT_TRANSLATION).casefold()
    matches = re.findall(r"\b\d+\b|\b[a-z]+\b|[\u0900-\u097f]+", normalized)
    for token in reversed(matches):
        if token.isdigit():
            return int(token)
        if token in _NUMBER_WORDS:
            return _NUMBER_WORDS[token]
    return None


def parse_resource_counts(message: str, config: AppConfig | None = None) -> tuple[dict[str, int], bool]:
    """Parse explicitly named counts; use configured defaults if none or malformed."""
    active = config or get_config()
    patterns = {
        "water_points": r"(?:water\s+points?|water\s+point|पानी\s*(?:के\s*)?(?:पॉइंट|स्थान|केंद्र)|जल\s*स्थान)",
        "cooling_centres": r"(?:cooling\s*(?:cent(?:re|er)s?)|कूलिंग\s*(?:सेंटर|केंद्र)|शीतलन\s*केंद्र|ठंडक\s*केंद्र)",
        "shade_structures": r"(?:shade\s+structures?|छाया\s*(?:संरचनाएँ|संरचना|ढांचा|ढाँचा))",
    }
    normalized = message.translate(_DIGIT_TRANSLATION).casefold()
    counts = {resource_type: 0 for resource_type in _RESOURCE_TYPES}
    seen = False
    malformed = False
    for resource_type, pattern in patterns.items():
        for match in re.finditer(pattern, normalized, flags=re.IGNORECASE):
            seen = True
            left = normalized[max(0, match.start() - 28):match.start()]
            right = normalized[match.end():match.end() + 18]
            value = _number_before(left)
            if value is None:
                right_match = re.match(r"\s*(\d+|[a-z]+|[\u0900-\u097f]+)", right)
                value = _number_before(right_match.group(1)) if right_match else None
            if value is None:
                malformed = True
                continue
            counts[resource_type] = value
    if not seen or malformed:
        return dict(active.default_resource_counts), True
    return counts, False


def _format_number(value: Any, digits: int = 2) -> str:
    if value is None:
        return "—"
    if isinstance(value, (int, float)):
        return f"{value:.{digits}f}".rstrip("0").rstrip(".") if isinstance(value, float) else str(value)
    return str(value)


def _render_route_result(route_result: dict[str, Any], language: str, config: AppConfig) -> tuple[str, list[str]]:
    routes = []
    for route in route_result["routes"]:
        routes.append(_template(language, "route_item",
            name=route["route_name"],
            duration=_duration_label(route["time_minutes"], language),
            distance=_format_number(route["distance_m"], 1),
            heat=_format_number(route["modelled_heat_exposure"], 3),
            shade=_format_number(route["weighted_shade_percent"], 1),
        ))
    rec = route_result["recommendation"]
    recommendation = _recommendation_text(rec, language)
    answer = _template(language, "route_summary",
        origin=route_result["origin_name"],
        destination=route_result["destination_name"],
        time=route_result["time"],
        routes="; ".join(routes),
        recommendation=recommendation,
    )
    assumption = _template(language, "route_assumption")
    return answer, [assumption]


def _route_context_result(message: str, context: dict[str, Any], language: str, config: AppConfig) -> dict[str, Any]:
    if not context.get("time"):
        return _empty_result(language, "route_assistant", _template(language, "route_need_time"))
    try:
        retrieved = _route_options(message, context, language, config)
    except (FileNotFoundError, RoutingError, ValueError):
        return _empty_result(language, "route_assistant")
    if retrieved.get("missing"):
        return _empty_result(language, "route_assistant", _template(language, "route_need_endpoints"))
    if retrieved.get("unavailable"):
        return _empty_result(language, "route_assistant")
    if retrieved.get("ambiguous"):
        language_matches = [f"{item['role'].title()}: {item['name']}" for item in retrieved["ambiguous"]]
        return {
            "answer": _template(language, "route_ambiguous", matches="; ".join(language_matches)),
            "language": language, "intent": "route_assistant", "mode": "template", "data_unavailable": False,
            "sources": [_source("place_match", item["place_id"], item["name"]) for item in retrieved["ambiguous"]],
            "facts_used": {"ambiguous_place_matches": retrieved["ambiguous"]}, "assumptions": [], "context_entity": None,
        }
    answer, assumptions = _render_route_result(retrieved, language, config)
    return {
        "answer": answer,
        "language": language,
        "intent": "route_assistant",
        "mode": "template",
        "data_unavailable": False,
        "sources": retrieved["sources"],
        "facts_used": retrieved["facts"],
        "assumptions": assumptions,
        "context_entity": {"type": "route", "id": retrieved["routes"][0]["source_id"] if retrieved["routes"] else None},
        "_route_payload": retrieved["route_payload"],
    }


def _select_stop_route(route_payload: dict[str, Any], language: str) -> dict[str, Any] | None:
    options = route_payload.get("routes", [])
    return next((item for item in options if item.get("route_type") == "HEAT_AWARE"), None) or next(
        (item for item in options if item.get("route_type") == "FASTEST"), None
    )


def _stops_summary(route: dict[str, Any], language: str) -> tuple[str, list[dict[str, Any]], list[dict[str, str]]]:
    stop_data = route.get("stops", {})
    status_id = stop_data.get("status_message_id")
    status = _citizen(language, status_id) if status_id in (CITIZEN_HI if language == "hi" else CITIZEN_EN) else _template(language, "unavailable")
    items = stop_data.get("items", [])
    if not items:
        return status, [], []
    lines: list[str] = []
    facts: list[dict[str, Any]] = []
    sources: list[dict[str, str]] = []
    for item in items:
        type_id = item.get("stop_type_message_id", "stop_type_other")
        kind = _citizen(language, type_id)
        amenities = item.get("amenities") or []
        amenities_text = _template(language, "stop_amenities", amenities=", ".join(amenities)) if amenities else ""
        lines.append(_template(language, "stop_item",
            name=item.get("name", ""), kind=kind,
            distance=_format_number(round(float(item["route_distance"]))),
            detour=_format_number(round(float(item["detour_distance"]))),
            amenities=amenities_text,
        ))
        facts.append({
            "name": item.get("name"), "type": item.get("stop_type"),
            "distance_from_route_m": round(float(item["route_distance"])),
            "detour_m": round(float(item["detour_distance"])),
            "amenities": amenities,
            "verified_status": item.get("verified_status"),
            "rating": item.get("rating_label"),
        })
        sources.append(_source("stop", item.get("stop_id"), item.get("name", "Recorded stop")))
    return "; ".join(lines), facts, sources


def _risk_result(segment_id: str | None, time_value: str | None, language: str) -> dict[str, Any]:
    if not segment_id:
        return _empty_result(language, "risk_explanation", _template(language, "select_street"))
    if not time_value:
        return _empty_result(language, "risk_explanation", _template(language, "select_time"))
    try:
        payload = _risk_explanation(segment_id, time_value)
    except Exception:
        payload = None
    if not payload:
        return _empty_result(language, "risk_explanation")
    street = payload["street"]
    if street["street_name"]:
        label = street["street_name"]
    elif street.get("nearest_named_place"):
        label = _template(language, "unnamed_street_near", name=street["nearest_named_place"])
    else:
        label = _template(language, "unnamed_street_id", id=street["canonical_street_key"])
    driver_lines = [_template(language, "risk_driver",
        label=COPILOT_LABELS[language]["drivers"].get(item["id"], item["label"]),
        level=COPILOT_LABELS[language]["levels"].get(item["level"], item["level"]),
        value=_format_number(item["value"], 3)) for item in payload["drivers"]]
    risk_class = COPILOT_LABELS[language]["levels"].get(street["risk_class"], street["risk_class"])
    answer = _template(language, "risk_summary",
        time=time_value, street=label, score=_format_number(street["risk_score"], 1),
        risk_class=risk_class, drivers="; ".join(driver_lines),
    )
    assumptions = [_template(language, "vulnerability_assumption")]
    return {
        "answer": answer, "language": language, "intent": "risk_explanation", "mode": "template",
        "data_unavailable": False,
        "sources": [_source("risk_record", street["canonical_street_key"], label)],
        "facts_used": {"time": time_value, "street": street, "drivers": payload["drivers"], "status": payload["status_labels"]},
        "assumptions": assumptions,
        "context_entity": {"type": "street", "id": street["canonical_street_key"]},
    }


def _read_risk_report(config: AppConfig) -> dict[str, Any]:
    path = config.cache_data_dir / "risk_report.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _height_facts(config: AppConfig) -> tuple[dict[str, Any], dict[str, str]]:
    buildings = load_cached_geojson("buildings", config).get("features", [])
    counts = {"observed_height": 0, "levels_derived": 0, "fallback_estimated": 0, "other": 0}
    for feature in buildings:
        source = feature.get("properties", {}).get("height_source")
        if source == "actual":
            counts["observed_height"] += 1
        elif source == "levels":
            counts["levels_derived"] += 1
        elif source == "fallback":
            counts["fallback_estimated"] += 1
        else:
            counts["other"] += 1
    facts = {
        "height_source_counts": counts,
        "building_height_per_floor_m": config.building_height_per_floor,
        "fallback_building_height_m": config.fallback_building_floors * config.building_height_per_floor,
    }
    rendered = {}
    for language in ("en", "hi"):
        rendered_counts = ", ".join(f"{COPILOT_LABELS[language]['height_sources'][name]}: {count}" for name, count in counts.items())
        rendered[language] = _template(language, "data_height", per_floor=_format_number(config.building_height_per_floor), fallback=_format_number(facts["fallback_building_height_m"]), counts=rendered_counts)
    return facts, rendered


def _transparency_result(message: str, language: str, config: AppConfig) -> dict[str, Any]:
    folded = message.casefold()
    source = _source("configuration", config.version, "versioned configuration")
    try:
        risk_report = _read_risk_report(config)
    except (FileNotFoundError, json.JSONDecodeError):
        return _empty_result(language, "data_transparency")
    facts: dict[str, Any] = {}
    sources = [source]
    assumptions: list[str] = []
    height_words = ("height", "ऊँचाई", "ऊंचाई", "building", "इमारत")
    vulnerability_words = ("vulnerability", "कमज़ोरी", "कमजोरी", "proxy", "प्रॉक्सी", "population", "जनसंख्या")
    normalization_words = ("normalization", "normalize", "सामान्यीकरण", "risk score", "जोखिम स्कोर")
    temperature_words = ("temperature", "तापमान", "heat curve")
    facility_words = ("facility", "facilities", "cooling", "water", "सुविधा", "पानी", "ठंडक")
    requested = {
        "height": _contains_any(folded, height_words),
        "vulnerability": _contains_any(folded, vulnerability_words),
        "normalization": _contains_any(folded, normalization_words),
        "temperature": _contains_any(folded, temperature_words),
        "facilities": _contains_any(folded, facility_words),
    }
    if not any(requested.values()):
        requested = {key: True for key in requested}
    rendered: dict[str, str] = {}
    if requested["height"]:
        height_facts, height_rendered = _height_facts(config)
        facts.update(height_facts)
        rendered["height"] = height_rendered[language]
        sources.append(_source("cache", "buildings.geojson", "cached building records"))
    if requested["vulnerability"]:
        vulnerability = risk_report.get("vulnerability", {})
        facts["vulnerability_proxy"] = vulnerability
        facts["vulnerability_proxy_label"] = config.vulnerability_proxy_label
        buffer_size = vulnerability.get("proxy_density_buffer_m", config.vulnerability_buffer_m)
        method_label = COPILOT_LABELS[language]["vulnerability_method"].format(buffer_m=buffer_size)
        rendered["vulnerability"] = _template(language, "data_vulnerability", method=method_label)
        assumptions.append(_template(language, "vulnerability_assumption"))
        sources.append(_source("cache", "risk_report.json:vulnerability", "cached vulnerability provenance"))
    if requested["normalization"]:
        facts["normalization_method"] = config.risk_normalization_method
        facts["normalization_scope"] = config.risk_normalization_scope
        method_label = COPILOT_LABELS[language]["normalization_method"]
        scope_label = COPILOT_LABELS[language]["normalization_scope"]
        rendered["normalization"] = _template(language, "data_normalization", method=method_label, scope=scope_label)
        sources.append(_source("configuration", config.version, "risk normalization configuration"))
    if requested["temperature"]:
        facts["temperature_proxy_assumption"] = config.hourly_temperature_proxy_assumption
        facts["temperature_proxy_label"] = config.temperature_proxy_label
        facts["temperature_proxy_values_c"] = config.temperature_proxy_c
        assumption_label = COPILOT_LABELS[language]["temperature_assumption"]
        proxy_curve = ", ".join(f"{time_key}: {_format_number(value, 1)}°C" for time_key, value in config.temperature_proxy_c.items())
        rendered["temperature"] = _template(language, "data_temperature", assumption=assumption_label, curve=proxy_curve)
        assumptions.append(_template(language, "temperature_assumption"))
        sources.append(_source("cache", "exposure_report.json", "cached exposure provenance"))
    if requested["facilities"]:
        access = risk_report.get("access", {})
        facts["recorded_facility_counts"] = {
            "water": access.get("water_facility_count"),
            "cooling": access.get("cooling_facility_count"),
        }
        rendered["facilities"] = _template(language, "data_facilities",
            water=access.get("water_facility_count", 0), cooling=access.get("cooling_facility_count", 0))
        sources.append(_source("cache", "risk_report.json:access", "cached facility coverage"))
    if len(rendered) == 1:
        answer = next(iter(rendered.values()))
    elif rendered:
        answer = "; ".join(rendered.values())
    else:
        return _empty_result(language, "data_transparency")
    return {
        "answer": answer, "language": language, "intent": "data_transparency", "mode": "template",
        "data_unavailable": False, "sources": sources, "facts_used": facts,
        "assumptions": assumptions, "context_entity": {"type": "data_provenance", "id": config.version},
    }


def _planner_result(message: str, context: dict[str, Any], language: str, config: AppConfig) -> dict[str, Any]:
    used_defaults = False
    try:
        plan = get_plan(context["plan_id"]) if context.get("plan_id") else None
    except ValueError:
        return _empty_result(language, "planner_assistant")
    if plan is None:
        counts, used_defaults = parse_resource_counts(message, config)
        try:
            plan = optimize_resources(counts)
        except (FileNotFoundError, ValueError):
            return _empty_result(language, "planner_assistant")
    priorities = []
    priority_facts = []
    priority_sources = []
    for item in plan.get("priorities", []):
        street_id = str(item.get("street_canonical_key") or item.get("candidate_id") or "unknown")
        place = item.get("street_name") or _unnamed_street_label(
            street_id, item.get("lat"), item.get("lon"), language, config,
        )
        requested_count = int(plan.get("requested_resources", {}).get(item["type"], 0))
        kind = _resource_name(item["type"], requested_count, language)
        share = round(float(item.get("share_of_total_reduction", 0)) * 100, 1)
        priorities.append(_template(language, "planner_priority", number=item["priority"], kind=kind, place=place, share=_format_number(share, 1)))
        priority_facts.append({
            "priority": item["priority"], "type": item["type"], "place": place, "street_id": street_id,
            "share_of_total_reduction_percent": share,
            "marginal_benefit": round(float(item["marginal_benefit"]), 3),
        })
        priority_sources.append(_source("street", street_id, place))
    selected_metrics: dict[str, Any] = {}
    for name in ("high_risk_vulnerable_exposure", "intervention_coverage", "water_coverage", "cooling_coverage"):
        metric = plan.get("metrics", {}).get(name)
        if metric:
            selected_metrics[name] = {
                "before": metric.get("before"), "modelled_after": metric.get("modelled_after"),
                "delta": metric.get("delta"), "label": metric.get("label"),
            }
    def metric_value(name: str, value: Any) -> str:
        if name.endswith("coverage"):
            return f"{_format_number(round(float(value or 0) * 100), 0)}%"
        return _format_number(value)

    metrics_text = "; ".join(
        f"{COPILOT_LABELS[language]['metrics'][name]} {metric_value(name, value.get('before'))} → {metric_value(name, value.get('modelled_after'))}"
        for name, value in selected_metrics.items()
    )
    counts_text = ", ".join(
        _template(language, "count_item", count=value, name=_resource_name(key, value, language))
        for key, value in plan["requested_resources"].items()
    )
    if used_defaults:
        answer = _template(language, "planner_default")
        if priorities:
            answer += " " + _template(language, "planner_summary",
                counts=counts_text, priorities="; ".join(priorities), before=_format_number(plan["objective"]["before"], 3),
                after=_format_number(plan["objective"]["modelled_after"], 3),
                reduction=_format_number(plan["objective"]["total_reduction"], 3), metrics=metrics_text)
    elif not priorities:
        answer = _template(language, "planner_no_actions")
    else:
        answer = _template(language, "planner_summary",
            counts=counts_text, priorities="; ".join(priorities), before=_format_number(plan["objective"]["before"], 3),
            after=_format_number(plan["objective"]["modelled_after"], 3),
            reduction=_format_number(plan["objective"]["total_reduction"], 3), metrics=metrics_text)
    facts = {
        "plan_id": plan["plan_id"], "requested_resources": plan["requested_resources"],
        "used_config_defaults": used_defaults, "priorities": priority_facts,
        "objective": {key: plan["objective"][key] for key in ("before", "modelled_after", "total_reduction")},
        "modelled_impact_metrics": selected_metrics,
    }
    assumptions = [_template(language, "planner_assumption")]
    return {
        "answer": answer, "language": language, "intent": "planner_assistant", "mode": "template",
        "data_unavailable": False,
        "sources": [_source("resource_plan", plan["plan_id"], "deterministic optimizer plan"), *priority_sources],
        "facts_used": facts, "assumptions": assumptions,
        "context_entity": {"type": "plan", "id": plan["plan_id"]},
    }


def _stops_result(message: str, context: dict[str, Any], language: str, config: AppConfig) -> dict[str, Any]:
    route_result = _route_context_result(message, context, language, config)
    if "_route_payload" not in route_result:
        route_result["intent"] = "safe_stop_assistant"
        return route_result
    route = _select_stop_route(route_result["_route_payload"], language)
    if route is None:
        return _empty_result(language, "safe_stop_assistant")
    items_text, stop_facts, stop_sources = _stops_summary(route, language)
    status_id = route.get("stops", {}).get("status_message_id")
    status = _citizen(language, status_id) if status_id in (CITIZEN_HI if language == "hi" else CITIZEN_EN) else _template(language, "unavailable")
    if not stop_facts:
        items_text = ""
    route_name = _citizen(language, route.get("route_type_message_id", "card_fastest"))
    answer = _template(language, "stops_summary", route_name=route_name, status=status, items=items_text).rstrip()
    base = {key: value for key, value in route_result.items() if key != "_route_payload"}
    base.update({
        "answer": answer,
        "intent": "safe_stop_assistant",
        "data_unavailable": status_id == "stops_unavailable",
        "facts_used": {**route_result["facts_used"], "selected_stop_route": route["route_type"], "stop_status": status_id, "stops": stop_facts},
        "sources": route_result["sources"] + stop_sources,
        "context_entity": {"type": "route", "id": route["route_type"]},
    })
    return base


def _heat_safety_result(message: str, context: dict[str, Any], language: str, config: AppConfig) -> dict[str, Any]:
    if _contains_any(message.casefold(), _SYMPTOM_TERMS):
        return {
            "answer": _template(language, "symptoms"), "language": language, "intent": "heat_safety",
            "mode": "template", "data_unavailable": False, "sources": [_source("guidance", "emergency", "India emergency contact guidance")],
            "facts_used": {"emergency_numbers": [108, 112], "ambulance_number": 108, "emergency_number": 112},
            "assumptions": [], "context_entity": None,
        }
    tips = [
        _citizen(language, "guidance_carry_water"),
        _citizen(language, "guidance_prefer_shade"),
        _citizen(language, "guidance_rest_cool"),
        _citizen(language, "guidance_avoid_hottest"),
    ]
    if context.get("origin") and context.get("destination"):
        route_result = _route_context_result(message, context, language, config)
        if "_route_payload" not in route_result:
            route_result["intent"] = "heat_safety"
            return route_result
        selected_route = _select_stop_route(route_result["_route_payload"], language)
        if selected_route is None:
            return _empty_result(language, "heat_safety")
        recommendation_info = route_result["facts_used"]["recommendation"]
        recommendation = _recommendation_text(recommendation_info, language)
        items_text, stop_facts, stop_sources = _stops_summary(selected_route, language)
        status_id = selected_route.get("stops", {}).get("status_message_id")
        status = _citizen(language, status_id) if status_id in (CITIZEN_HI if language == "hi" else CITIZEN_EN) else _template(language, "unavailable")
        if not stop_facts:
            items_text = status
        tip_text = _template(language, "tip_join").join(_template(language, "tips_item", tip=tip) for tip in tips)
        answer = _template(language, "scene_route", recommendation=recommendation, stops=items_text, tips=tip_text)
        facts = {
            **route_result["facts_used"], "selected_stop_route": selected_route["route_type"],
            "stop_status": status_id, "stops": stop_facts, "generic_tips": tips,
        }
        assumptions = route_result["assumptions"] + [_template(language, "vulnerability_assumption")]
        return {
            "answer": answer, "language": language, "intent": "heat_safety", "mode": "template",
            "data_unavailable": status_id == "stops_unavailable", "sources": route_result["sources"] + stop_sources,
            "facts_used": facts, "assumptions": assumptions,
            "context_entity": {"type": "route", "id": selected_route["route_type"]},
        }
    answer = _template(language, "tips_intro") + " " + _template(language, "tip_join").join(
        _template(language, "tips_item", tip=tip) for tip in tips
    )
    return {
        "answer": answer, "language": language, "intent": "heat_safety", "mode": "template",
        "data_unavailable": False,
        "sources": [_source("guidance", key, "approved citizen heat guidance") for key in (
            "guidance_carry_water", "guidance_prefer_shade", "guidance_rest_cool", "guidance_avoid_hottest")],
        "facts_used": {"generic_tips": tips}, "assumptions": [], "context_entity": None,
    }


def _platform_result(context: dict[str, Any], language: str) -> dict[str, Any]:
    answer = _template(language, "platform")
    view = context.get("view")
    if view in {"planner", "citizen"}:
        answer += " " + _template(language, f"platform_{view}")
    facts = {"current_view": view} if view in {"planner", "citizen"} else {}
    if context.get("time"):
        facts["selected_time"] = context["time"]
    return {
        "answer": answer, "language": language, "intent": "platform_guide", "mode": "template",
        "data_unavailable": False, "sources": [_source("help_catalog", "platform_guide", "platform help")],
        "facts_used": facts, "assumptions": [],
        "context_entity": {"type": "view", "id": view} if view in {"planner", "citizen"} else None,
    }


def _unknown_result(language: str) -> dict[str, Any]:
    return {
        "answer": _template(language, "unknown", examples=_template(language, "unknown_examples")),
        "language": language, "intent": "unknown", "mode": "template", "data_unavailable": False,
        "sources": [_source("help_catalog", "supported_intents", "Copilot help")],
        "facts_used": {"supported_intents": ["platform_guide", "risk_explanation", "route_assistant", "safe_stop_assistant", "planner_assistant", "data_transparency", "heat_safety"]},
        "assumptions": [], "context_entity": None,
    }


def _flatten_fact_numbers(value: Any) -> set[Decimal]:
    values: set[Decimal] = set()
    if isinstance(value, bool) or value is None:
        return values
    if isinstance(value, (int, float, Decimal)):
        try:
            values.add(Decimal(str(value)))
        except InvalidOperation:
            pass
    elif isinstance(value, str):
        for token in re.findall(r"(?<![A-Za-z])\d[\d,]*(?:\.\d+)?", value.translate(_DIGIT_TRANSLATION)):
            try:
                values.add(Decimal(token.replace(",", "")))
            except InvalidOperation:
                continue
    elif isinstance(value, dict):
        for nested in value.values():
            values.update(_flatten_fact_numbers(nested))
    elif isinstance(value, (list, tuple)):
        for nested in value:
            values.update(_flatten_fact_numbers(nested))
    return values


def _fact_entity_tokens(value: Any) -> set[str]:
    tokens: set[str] = set()
    if isinstance(value, dict):
        for key, nested in value.items():
            if key.casefold() in {"name", "place", "origin_name", "destination_name", "street", "stop_name"} and isinstance(nested, str):
                tokens.update(re.findall(r"[\w.-]+", nested.casefold(), flags=re.UNICODE))
            tokens.update(_fact_entity_tokens(nested))
    elif isinstance(value, (list, tuple)):
        for nested in value:
            tokens.update(_fact_entity_tokens(nested))
    return tokens


def _passes_fact_gate(answer: str, language: str, facts_used: dict[str, Any]) -> bool:
    folded = answer.casefold()
    if any(term in folded for term in _FORBIDDEN_OUTPUT):
        return False
    if language == "hi":
        if not re.search(r"[\u0900-\u097f]", answer):
            return False
    elif re.search(r"[\u0900-\u097f]", answer):
        return False
    allowed_numbers = _flatten_fact_numbers(facts_used)
    for token in re.findall(r"(?<![A-Za-z])\d[\d,]*(?:\.\d+)?", answer.translate(_DIGIT_TRANSLATION)):
        try:
            if Decimal(token.replace(",", "")) not in allowed_numbers:
                return False
        except InvalidOperation:
            return False
    # Reject ungrounded English proper-name candidates (places/businesses) while
    # allowing common sentence openings and every entity retrieved into facts.
    allowed_entity_tokens = _fact_entity_tokens(facts_used)
    common_capitalized = {
        "I", "The", "A", "An", "At", "For", "From", "This", "That", "These", "Those",
        "Based", "Modelled", "Estimated", "Fastest", "Balanced", "Heat-aware", "Route",
        "Routes", "Risk", "Main", "Data", "Available", "Use", "In", "Please", "Water",
        "Cooling", "Shade", "Vulnerability", "Priority", "Plan", "No", "One", "Two",
    }
    for match in re.finditer(r"\b[A-Z][A-Za-z.-]*(?:\s+[A-Z][A-Za-z.-]*){0,2}\b", answer):
        phrase = match.group(0)
        words = [word.casefold().strip(".-") for word in phrase.split()]
        if phrase in common_capitalized or (len(words) == 1 and words[0] in allowed_entity_tokens):
            continue
        if all(word in allowed_entity_tokens for word in words):
            continue
        if match.start() == 0 and words[0] in {"i", "the", "a", "an", "at", "for", "from", "this", "that", "these", "those", "based", "in", "please", "no", "one", "two"}:
            continue
        # Only treat interior title-case sequences as named entities. A common
        # sentence-initial word is already handled above.
        return False
    return True


def _call_llm(question: str, language: str, facts: dict[str, Any], assumptions: list[str]) -> str:
    """Call an optional OpenAI-compatible chat endpoint without logging payloads."""
    provider = os.getenv("LLM_PROVIDER", "").strip()
    api_key = os.getenv("LLM_API_KEY", "").strip()
    model = os.getenv("LLM_MODEL", "").strip()
    base_url = os.getenv("LLM_BASE_URL", "").strip().rstrip("/")
    if not (provider and api_key and model and base_url):
        raise RuntimeError("LLM configuration is incomplete")
    endpoint = base_url if base_url.endswith("/chat/completions") else f"{base_url}/chat/completions"
    language_name = "Hindi in Devanagari" if language == "hi" else "English"
    request_body = {
        "model": model,
        "temperature": 0,
        "messages": [
            {"role": "system", "content": (
                f"Rephrase the supplied grounded facts and assumptions into {language_name}. "
                "Use only those facts. Do not add numbers, place names, stops, ratings, amenities, "
                "medical claims, or advice. Return only the answer text."
            )},
            {"role": "user", "content": json.dumps({"question": question, "facts_used": facts, "assumptions": assumptions}, ensure_ascii=False)},
        ],
    }
    body = json.dumps(request_body, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(endpoint, data=body, headers={
        "Authorization": f"Bearer {api_key}", "Content-Type": "application/json",
    }, method="POST")
    with urllib.request.urlopen(request, timeout=4.0) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return str(payload["choices"][0]["message"]["content"]).strip()


def _dispatch(message: str, language: str, intent: str, context: dict[str, Any], config: AppConfig) -> dict[str, Any]:
    if intent == "risk_explanation":
        return _risk_result(context.get("selected_segment_id"), context.get("time"), language)
    if intent == "route_assistant":
        return _route_context_result(message, context, language, config)
    if intent == "safe_stop_assistant":
        return _stops_result(message, context, language, config)
    if intent == "planner_assistant":
        return _planner_result(message, context, language, config)
    if intent == "data_transparency":
        return _transparency_result(message, language, config)
    if intent == "heat_safety":
        return _heat_safety_result(message, context, language, config)
    if intent == "platform_guide":
        return _platform_result(context, language)
    return _unknown_result(language)


def answer_copilot(message: str, ui_language: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
    """Answer one transient request; only intent, elapsed time, and mode are logged."""
    started = time.perf_counter()
    active_config = get_config()
    safe_context = context or {}
    language = detect_language(message, ui_language, active_config)
    intent = classify_intent(message, active_config)
    result = _dispatch(message, language, intent, safe_context, active_config)
    # Internal route payloads are only used for this response composition.
    result.pop("_route_payload", None)
    result["intent"] = intent
    mode = "template"
    if active_config.feature_flags.get("copilot_llm", False) and result.get("facts_used") and not result.get("data_unavailable"):
        try:
            rendered = _call_llm(message, language, result["facts_used"], result["assumptions"])
            if _passes_fact_gate(rendered, language, result["facts_used"]):
                result["answer"] = rendered
                mode = "llm"
        except Exception:
            # Optional rendering is best-effort; deterministic templates remain authoritative.
            pass
    result["mode"] = mode
    if language == "hi":
        for source in result.get("sources", []):
            source["label"] = COPILOT_LABELS[language]["sources"].get(source["label"], source["label"])
    elapsed = time.perf_counter() - started
    LOGGER.info("Copilot request intent=%s duration_s=%.3f mode=%s", intent, elapsed, mode)
    return result
