"""Cache-only endpoints and the Prompt 1 planner page."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.config import get_config
from app.repositories.cache import cache_status, load_cached_geojson, load_shadow_snapshot


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
