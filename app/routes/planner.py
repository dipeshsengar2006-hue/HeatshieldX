"""Cache-only endpoints and the Prompt 1 planner page."""

from __future__ import annotations

import json
import math
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from app.config import get_config
from app.i18n import CITIZEN_EN, CITIZEN_HI, validate_citizen_i18n
from app.repositories.cache import cache_status, load_cached_geojson, load_exposure_snapshot, load_risk_snapshot, load_shadow_snapshot
from app.services.explainability_engine import build_risk_drivers, deduplicate_risk_features, explain_segment_snapshot, find_canonical_feature, rank_hottest_and_highest_risk, street_summary
from app.services.intervention_engine import get_plan, list_candidates, optimize_resources
from app.services.risk_engine import normalize_with_bounds, risk_class
from app.services.public_summary import PublicSummaryError, public_summary as build_public_summary
from app.services.routing_engine import RoutingError, route_request, search_places


router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


class OptimizeRequest(BaseModel):
    water_points: int | None = None
    cooling_centres: int | None = None
    shade_structures: int | None = None


class RouteCoordinate(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)


class RouteRequest(BaseModel):
    origin: RouteCoordinate
    destination: RouteCoordinate
    time: str


class PublicSummaryRequest(BaseModel):
    lat: float = Field(ge=-90, le=90, allow_inf_nan=False)
    lon: float = Field(ge=-180, le=180, allow_inf_nan=False)
    time: str = Field(min_length=5, max_length=5)


def _load_or_503(name: str) -> dict:
    try:
        return load_cached_geojson(name)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


def _data_download_date() -> str:
    """Return the date of the preloaded OSM snapshot when it is available."""
    try:
        timestamp = load_cached_geojson("streets")["features"][0]["properties"].get("timestamp", "")
        return str(timestamp)[:10] or "Unavailable"
    except (FileNotFoundError, IndexError, KeyError):
        return "Unavailable"


def _street_name(directed_segment_ids: list[str]) -> str | None:
    """Get only an observed OSM road name; absent tags remain absent."""
    try:
        streets = load_cached_geojson("streets")["features"]
    except FileNotFoundError:
        return None
    for feature in streets:
        properties = feature["properties"]
        if properties.get("segment_id") not in directed_segment_ids:
            continue
        try:
            name = json.loads(properties.get("road_metadata", "{} ")).get("name")
        except (TypeError, json.JSONDecodeError):
            continue
        if isinstance(name, str) and name.strip():
            return name.strip()
        if isinstance(name, float) and math.isnan(name):
            continue
    return None


def _stop_cache_summary() -> dict[str, object]:
    """Expose cache availability for the citizen view without fabricating stops."""
    counts = {stop_type: 0 for stop_type in get_config().stop_type_priority}
    try:
        features = load_cached_geojson("stops").get("features", [])
    except FileNotFoundError:
        return {"available": False, "counts": counts}
    for feature in features:
        stop_type = feature.get("properties", {}).get("stop_type")
        if stop_type in counts:
            counts[stop_type] += 1
    return {"available": True, "counts": counts}


@router.get("/", response_class=HTMLResponse)
def planner(request: Request) -> HTMLResponse:
    config = get_config()
    status = cache_status(config)
    load_error = None
    if not status["streets"] or not status["buildings"]:
        load_error = (
            "Preloaded map data is unavailable. Run `python scripts/precompute_demo_area.py` "
            "when OpenStreetMap is reachable, then restart the app."
        )
    return templates.TemplateResponse(
        request,
        "planner.html",
        {
            "demo_area": config.demo_area,
            "config_version": config.version,
            "shadow_times": config.canonical_times,
            "exposure_mode": config.exposure_computation_mode,
            "resource_defaults": config.default_resource_counts,
            "data_download_date": _data_download_date(),
            "load_error": load_error,
        },
    )


@router.get("/citizen", response_class=HTMLResponse)
def citizen(request: Request) -> HTMLResponse:
    """Render the English cache-only citizen routing view."""
    validate_citizen_i18n()
    config = get_config()
    stop_summary = _stop_cache_summary()
    demo_pairs = [
        {"id": "kadavghat", "origin": {"lat": 22.7146202, "lon": 75.8542367}, "destination": {"lat": 22.7188165, "lon": 75.8553691}, "time": "09:00"},
        {"id": "yashwant", "origin": {"lat": 22.7148593, "lon": 75.8549381}, "destination": {"lat": 22.7188165, "lon": 75.8553691}, "time": "09:00"},
        {"id": "riverside", "origin": {"lat": 22.7188165, "lon": 75.8553691}, "destination": {"lat": 22.7189579, "lon": 75.8590870}, "time": "17:00"},
    ]
    return templates.TemplateResponse(
        request,
        "citizen.html",
        {
            "demo_area": config.demo_area,
            "config_version": config.version,
            "data_download_date": _data_download_date(),
            "computation_mode": config.computation_mode,
            "strings": CITIZEN_EN,
            "hindi_strings": CITIZEN_HI,
            "demo_pairs": demo_pairs,
            "stop_summary": stop_summary,
            "min_heat_reduction_pct": config.min_heat_reduction_pct,
        },
    )


@router.get("/api/street-segments")
def street_segments() -> dict:
    return _load_or_503("streets")


@router.get("/api/buildings")
def buildings() -> dict:
    return _load_or_503("buildings")


@router.get("/api/facilities")
def facilities() -> dict:
    return _load_or_503("facilities")


@router.get("/api/places")
def places(q: str = Query(..., min_length=1, max_length=100)) -> dict:
    """Search only named streets, buildings, and amenities in the local cache."""
    try:
        return {"query": q, "places": search_places(q)}
    except FileNotFoundError:
        return JSONResponse(
            status_code=503,
            content={"detail": CITIZEN_EN["places_error"], "message_id": "places_error", "message_params": {}},
        )


@router.post("/api/routes")
def routes(payload: RouteRequest) -> dict:
    """Generate cache-only route alternatives; request coordinates are not persisted."""
    try:
        return route_request(
            (payload.origin.lat, payload.origin.lon),
            (payload.destination.lat, payload.destination.lon),
            payload.time,
        )
    except (RoutingError, FileNotFoundError) as exc:
        detail = str(exc)
        lowered = detail.casefold()
        if "outside" in lowered or "from the cached walking network" in lowered:
            message_id = "route_error_area"
        elif "no walking path" in lowered:
            message_id = "route_error_path"
        else:
            message_id = "route_error_generic"
        return JSONResponse(status_code=422, content={"detail": detail, "message_id": message_id, "message_params": {}})


@router.post("/api/public/summary")
def public_summary(payload: PublicSummaryRequest):
    """Return a transient, cache-only public summary for one snapped street."""
    try:
        return build_public_summary(payload.lat, payload.lon, payload.time)
    except PublicSummaryError as exc:
        return JSONResponse(
            status_code=422,
            content={"detail": exc.english_text, "message_id": exc.message_id, "message_params": exc.message_params},
        )
    except FileNotFoundError as exc:
        return JSONResponse(
            status_code=503,
            content={"detail": str(exc), "message_id": "summary_error", "message_params": {}},
        )


@router.get("/api/status")
def status() -> dict:
    config = get_config()
    return {
        "demo_area": config.demo_area.model_dump(),
        "config_version": config.version,
        "computation_mode": config.computation_mode,
        "cache": cache_status(config),
    }


def _shadow_snapshot_or_503(kind: str, canonical_time: str) -> dict:
    config = get_config()
    if canonical_time not in config.canonical_times:
        raise HTTPException(
            status_code=422,
            detail=f"Unsupported shadow time '{canonical_time}'. Use one of: {', '.join(config.canonical_times)}.",
        )
    try:
        return load_shadow_snapshot(kind, canonical_time, config)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/api/shadows/{canonical_time}/polygons")
def shadow_polygons(canonical_time: str) -> dict:
    return _shadow_snapshot_or_503("shadow_polygons", canonical_time)


@router.get("/api/shadows/{canonical_time}/shade-fractions")
def shade_fractions(canonical_time: str) -> dict:
    return _shadow_snapshot_or_503("shade_fractions", canonical_time)


def _minutes_since_midnight(value: str) -> int:
    try:
        parsed = datetime.strptime(value, "%H:%M")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Time must use 24-hour HH:MM format.") from exc
    return parsed.hour * 60 + parsed.minute


def _interpolated_exposure_snapshot(requested_time: str, lower: dict, upper: dict, ratio: float) -> dict:
    """Interpolate cached fields only; this deliberately performs no GIS work."""
    upper_by_segment = {feature["properties"]["segment_id"]: feature for feature in upper["features"]}
    features = []
    for lower_feature in lower["features"]:
        lower_properties = lower_feature["properties"]
        upper_feature = upper_by_segment.get(lower_properties["segment_id"])
        if upper_feature is None:
            raise HTTPException(
                status_code=503,
                detail="Exposure cache snapshots have inconsistent street segments. Rerun `python scripts/precompute_exposure.py`.",
            )
        lower_value = float(lower_properties["exposure_value"])
        upper_value = float(upper_feature["properties"]["exposure_value"])
        properties = {
            **lower_properties,
            "canonical_time": requested_time,
            "exposure_value": lower_value + (upper_value - lower_value) * ratio,
            "modelled_or_interpolated": "INTERPOLATED",
            "observed_or_estimated": "ESTIMATED",
            "interpolation_lower_time": lower["metadata"]["canonical_time"],
            "interpolation_upper_time": upper["metadata"]["canonical_time"],
        }
        features.append({"type": "Feature", "properties": properties, "geometry": lower_feature["geometry"]})
    mode = lower["metadata"]["computation_mode"]
    return {
        "type": "FeatureCollection",
        "features": features,
        "metadata": {
            "requested_time": requested_time,
            "canonical_time": None,
            "computation_mode": mode,
            "modelled_or_interpolated": "INTERPOLATED",
            "observed_or_estimated": "ESTIMATED",
            "interpolated": True,
            "interpolation_lower_time": lower["metadata"]["canonical_time"],
            "interpolation_upper_time": upper["metadata"]["canonical_time"],
            "config_version": lower["metadata"]["config_version"],
            "temperature_proxy_label": lower["metadata"]["temperature_proxy_label"],
        },
    }


def _interpolated_risk_snapshot(requested_time: str, lower: dict, upper: dict, ratio: float) -> dict:
    """Interpolate cached risk inputs and retain the canonical global score scope."""
    upper_by_segment = {feature["properties"]["segment_id"]: feature for feature in upper["features"]}
    metadata = lower["metadata"]
    raw_min = float(metadata["global_final_risk_raw_min"])
    raw_max = float(metadata["global_final_risk_raw_max"])
    features = []
    for lower_feature in lower["features"]:
        lower_properties = lower_feature["properties"]
        upper_feature = upper_by_segment.get(lower_properties["segment_id"])
        if upper_feature is None:
            raise HTTPException(status_code=503, detail="Risk cache snapshots have inconsistent street segments. Rerun `python scripts/precompute_risk.py`.")
        upper_properties = upper_feature["properties"]
        raw = float(lower_properties["final_risk_raw"]) + (float(upper_properties["final_risk_raw"]) - float(lower_properties["final_risk_raw"])) * ratio
        score = normalize_with_bounds(raw, raw_min, raw_max)
        properties = {
            **lower_properties,
            "canonical_time": requested_time,
            "exposure_value": float(lower_properties["exposure_value"]) + (float(upper_properties["exposure_value"]) - float(lower_properties["exposure_value"])) * ratio,
            "shade_fraction": float(lower_properties["shade_fraction"]) + (float(upper_properties["shade_fraction"]) - float(lower_properties["shade_fraction"])) * ratio,
            "direct_exposure_fraction": float(lower_properties["direct_exposure_fraction"]) + (float(upper_properties["direct_exposure_fraction"]) - float(lower_properties["direct_exposure_fraction"])) * ratio,
            "baseline_risk": float(lower_properties["baseline_risk"]) + (float(upper_properties["baseline_risk"]) - float(lower_properties["baseline_risk"])) * ratio,
            "final_risk_raw": raw,
            "risk_score": score,
            "risk_class": risk_class(score),
            "modelled_or_interpolated": "INTERPOLATED",
            "observed_or_estimated": "ESTIMATED",
            "interpolation_lower_time": metadata["canonical_time"],
            "interpolation_upper_time": upper["metadata"]["canonical_time"],
        }
        features.append({"type": "Feature", "properties": properties, "geometry": lower_feature["geometry"]})
    return {
        "type": "FeatureCollection",
        "features": features,
        "metadata": {**metadata, "requested_time": requested_time, "canonical_time": None, "modelled_or_interpolated": "INTERPOLATED", "observed_or_estimated": "ESTIMATED", "interpolated": True, "interpolation_lower_time": metadata["canonical_time"], "interpolation_upper_time": upper["metadata"]["canonical_time"]},
    }


def _risk_snapshot_or_503(requested_time: str, plan_id: str | None = None) -> dict:
    """Return a canonical risk cache or an explicitly flagged cached-field interpolation."""
    config = get_config()
    requested_minutes = _minutes_since_midnight(requested_time)
    start, end = _minutes_since_midnight(config.canonical_times[0]), _minutes_since_midnight(config.canonical_times[-1])
    if requested_minutes < start or requested_minutes > end or requested_minutes % 30:
        raise HTTPException(status_code=422, detail="Time must be between 09:00 and 17:00 in 30-minute increments.")
    try:
        if plan_id:
            try:
                plan = get_plan(plan_id)
            except ValueError as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc
            scenario_snapshots = plan["after_snapshots"]
            if requested_time in config.canonical_times:
                snapshot = scenario_snapshots[requested_time]
            else:
                canonical_minutes = [_minutes_since_midnight(value) for value in config.canonical_times]
                upper_index = next(index for index, minute in enumerate(canonical_minutes) if minute > requested_minutes)
                lower_time, upper_time = config.canonical_times[upper_index - 1], config.canonical_times[upper_index]
                ratio = (requested_minutes - canonical_minutes[upper_index - 1]) / (canonical_minutes[upper_index] - canonical_minutes[upper_index - 1])
                snapshot = _interpolated_risk_snapshot(requested_time, scenario_snapshots[lower_time], scenario_snapshots[upper_time], ratio)
            snapshot.setdefault("metadata", {}).update({"requested_time": requested_time, "interpolated": requested_time not in config.canonical_times, "plan_id": plan_id})
        elif requested_time in config.canonical_times:
            snapshot = load_risk_snapshot(requested_time, config)
            snapshot.setdefault("metadata", {}).update({"requested_time": requested_time, "interpolated": False})
        else:
            canonical_minutes = [_minutes_since_midnight(value) for value in config.canonical_times]
            upper_index = next(index for index, minute in enumerate(canonical_minutes) if minute > requested_minutes)
            lower_time, upper_time = config.canonical_times[upper_index - 1], config.canonical_times[upper_index]
            ratio = (requested_minutes - canonical_minutes[upper_index - 1]) / (canonical_minutes[upper_index] - canonical_minutes[upper_index - 1])
            snapshot = _interpolated_risk_snapshot(requested_time, load_risk_snapshot(lower_time, config), load_risk_snapshot(upper_time, config), ratio)
        features, consistency = deduplicate_risk_features(snapshot["features"])
        return {"type": "FeatureCollection", "features": features, "metadata": {**snapshot["metadata"], "street_deduplication": consistency}}
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/api/risk")
def risk(time: str = Query(..., description="09:00–17:00 in 30-minute increments"), plan_id: str | None = None) -> dict:
    return _risk_snapshot_or_503(time, plan_id)


def _public_plan(plan: dict) -> dict:
    """Keep in-memory after snapshots out of plan response bodies."""
    return {key: value for key, value in plan.items() if key != "after_snapshots"}


@router.get("/api/interventions/candidates")
def intervention_candidates() -> dict:
    return list_candidates()


@router.post("/api/optimize")
def optimize(payload: OptimizeRequest) -> dict:
    try:
        plan = optimize_resources(payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _public_plan(plan)


@router.get("/api/plans/{plan_id}")
def plan(plan_id: str) -> dict:
    try:
        return _public_plan(get_plan(plan_id))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/api/segments/{segment_id}/risk")
def segment_risk(segment_id: str, time: str = Query(..., description="09:00–17:00 in 30-minute increments")) -> dict:
    snapshot = _risk_snapshot_or_503(time)
    feature = find_canonical_feature(snapshot["features"], segment_id)
    if feature is not None:
        return {"segment_id": segment_id, "requested_time": time, "risk": feature, "metadata": snapshot["metadata"]}
    raise HTTPException(status_code=404, detail=f"Segment '{segment_id}' is not present in the cached risk snapshot.")


@router.get("/api/segments/{segment_id}/why")
def segment_why(segment_id: str, time: str = Query(..., description="09:00–17:00 in 30-minute increments")) -> dict:
    """Return deterministic, source-grounded drivers for either street direction."""
    snapshot = _risk_snapshot_or_503(time)
    payload = explain_segment_snapshot(snapshot, segment_id)
    if payload is None:
        raise HTTPException(status_code=404, detail=f"Segment '{segment_id}' is not present in the cached risk snapshot.")
    payload["street"]["street_name"] = _street_name(payload["street"]["directed_segment_ids"])
    payload["requested_time"] = time
    return payload


@router.get("/api/compare/hottest")
def compare_hottest(time: str = Query(..., description="09:00–17:00 in 30-minute increments")) -> dict:
    """Compare de-duplicated exposure and modelled-priority leaders from cached records."""
    snapshot = _risk_snapshot_or_503(time)
    ranked = rank_hottest_and_highest_risk(snapshot["features"])

    def summarized(feature: dict) -> dict:
        drivers = build_risk_drivers(feature["properties"])
        summary = street_summary(feature, drivers)
        summary["street_name"] = _street_name(summary["directed_segment_ids"])
        return summary

    hottest, highest_risk = summarized(ranked["hottest"]), summarized(ranked["highest_risk"])
    if hottest["canonical_street_key"] == highest_risk["canonical_street_key"]:
        explanation = "The highest-exposure street is also the highest modelled-priority street at this time."
    else:
        explanation = (
            f"The highest-exposure street has exposure {hottest['exposure_value']:.3f} and modelled priority {hottest['risk_score']:.1f}; "
            f"the highest-priority street has exposure {highest_risk['exposure_value']:.3f}, "
            f"{highest_risk['vulnerability_level'].lower()} estimated vulnerability, "
            f"{highest_risk['cooling_access_level'].lower()} cooling access, and modelled priority {highest_risk['risk_score']:.1f}."
        )
    return {
        "requested_time": time,
        "hottest": hottest,
        "highest_risk": highest_risk,
        "hottest_tie_count": ranked["hottest_tie_count"],
        "hottest_tie_risk_score_min": ranked["hottest_tie_risk_score_min"],
        "hottest_tie_risk_score_max": ranked["hottest_tie_risk_score_max"],
        "highest_risk_tie_count": ranked["highest_risk_tie_count"],
        "explanation": explanation,
        "metadata": snapshot["metadata"],
    }


@router.get("/api/exposure")
def exposure(time: str = Query(..., description="09:00–17:00 in 30-minute increments")) -> dict:
    """Return a cached canonical exposure snapshot or cached-field interpolation."""
    config = get_config()
    requested_minutes = _minutes_since_midnight(time)
    start, end = _minutes_since_midnight(config.canonical_times[0]), _minutes_since_midnight(config.canonical_times[-1])
    if requested_minutes < start or requested_minutes > end or requested_minutes % 30:
        raise HTTPException(status_code=422, detail="Time must be between 09:00 and 17:00 in 30-minute increments.")
    try:
        if time in config.canonical_times:
            snapshot = load_exposure_snapshot(time, config)
            snapshot.setdefault("metadata", {}).update({"requested_time": time, "interpolated": False})
            return snapshot
        canonical_minutes = [_minutes_since_midnight(value) for value in config.canonical_times]
        upper_index = next(index for index, minute in enumerate(canonical_minutes) if minute > requested_minutes)
        lower_time, upper_time = config.canonical_times[upper_index - 1], config.canonical_times[upper_index]
        ratio = (requested_minutes - canonical_minutes[upper_index - 1]) / (canonical_minutes[upper_index] - canonical_minutes[upper_index - 1])
        return _interpolated_exposure_snapshot(
            time,
            load_exposure_snapshot(lower_time, config),
            load_exposure_snapshot(upper_time, config),
            ratio,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
