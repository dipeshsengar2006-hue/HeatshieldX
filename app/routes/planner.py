"""Cache-only endpoints and the Prompt 1 planner page."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.config import get_config
from app.repositories.cache import cache_status, load_cached_geojson, load_exposure_snapshot, load_shadow_snapshot


router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


def _load_or_503(name: str) -> dict:
    try:
        return load_cached_geojson(name)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


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
            "load_error": load_error,
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
