"""Freeze-stage failure, privacy, provenance, and cache-contract checks."""

from __future__ import annotations

import json
import logging
import re
import shutil
import subprocess
from pathlib import Path

import geopandas as gpd
import pytest
from fastapi.testclient import TestClient
from shapely.geometry import LineString

from app.config import get_config
from app.i18n import CITIZEN_EN, CITIZEN_HI
from app.main import app
from app.presentation import display_osm_name
from app.repositories import cache
from app.repositories.cache import store_cached_plan
from app.services import copilot_service
from app.services.cooling_access_engine import build_cooling_access_records
from app.services.data_engine import _height_details, repair_and_filter_geometries
from app.services.exposure_engine import build_canonical_exposure_snapshot
from app.services.exposure_engine import precompute_exposure
from app.services.intervention_engine import optimize_resources
from app.services.risk_engine import precompute_risk
from app.services.shadow_engine import precompute_shadows
from app.services.stop_finder import find_safe_stops


ROOT = Path(__file__).resolve().parents[1]
CLIENT = TestClient(app)
PROVENANCE = {"source_type", "observed_or_estimated", "modelled_or_interpolated", "timestamp", "assumptions_version", "computation_mode"}


def _temporary_config(tmp_path: Path):
    source = get_config().cache_data_dir
    target = tmp_path / "cache"
    shutil.copytree(source, target)
    return get_config().model_copy(update={"cache_data_dir": target})


def test_missing_cache_errors_are_actionable_and_never_500(tmp_path, monkeypatch):
    config = _temporary_config(tmp_path)
    (config.cache_data_dir / "streets.geojson").unlink()
    with pytest.raises(FileNotFoundError, match="Preloaded streets data is unavailable"):
        cache.load_cached_geojson("streets", config)
    (config.cache_data_dir / "exposure_09-00.geojson").unlink()
    with pytest.raises(FileNotFoundError, match="precompute_exposure.py"):
        cache.load_exposure_snapshot("09:00", config)

    from app.routes import planner

    monkeypatch.setattr(planner, "load_cached_geojson", lambda *_args: (_ for _ in ()).throw(FileNotFoundError("Run precompute_demo_area.py")))
    response = CLIENT.get("/api/street-segments")
    assert response.status_code == 503
    assert "precompute" in response.json()["detail"].casefold()


def test_geometry_height_shadow_and_no_facility_failures_are_explicit(tmp_path, caplog, monkeypatch):
    caplog.set_level(logging.WARNING)
    invalid = gpd.GeoDataFrame(geometry=[LineString() ], crs="EPSG:4326")
    assert repair_and_filter_geometries(invalid, {"LineString"}, "streets").empty
    assert "geometry cleanup" in "\n".join(record.getMessage() for record in caplog.records)
    config = get_config()
    assert _height_details({"height": "12"}, config)[2:] == ("actual", False)
    assert _height_details({"building:levels": "3"}, config)[2:] == ("levels", True)
    assert _height_details({}, config)[2:] == ("fallback", True)

    fallback = build_canonical_exposure_snapshot(
        "09:00", config,
        shadow_loader=lambda *_args: (_ for _ in ()).throw(RuntimeError("shadow failed")),
        street_loader=lambda *_args: {"type": "FeatureCollection", "features": [{"type": "Feature", "properties": {"segment_id": "s"}, "geometry": {"type": "LineString", "coordinates": [[75, 22], [75.01, 22.01]]}}]},
    )
    assert fallback["metadata"]["computation_mode"] == "estimated"
    assert fallback["features"][0]["properties"]["fallback_description"].startswith("Estimated exposure mode")

    temporary = _temporary_config(tmp_path)
    (temporary.cache_data_dir / "facilities.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": []}), encoding="utf-8")
    records, _metadata = build_cooling_access_records(temporary)
    assert records and all(record["cooling_available"] is False and record["cooling_access_penalty"] == 1 for record in records.values())


def test_copilot_degrades_to_template_without_logging_message_or_coordinates(monkeypatch, caplog):
    config = get_config().model_copy(update={"feature_flags": {**get_config().feature_flags, "copilot_llm": True}})
    monkeypatch.setattr(copilot_service, "get_config", lambda: config)
    monkeypatch.setattr(copilot_service, "_call_llm", lambda *_args: (_ for _ in ()).throw(TimeoutError("timeout")))
    caplog.set_level(logging.INFO, logger="app.services.copilot_service")
    message = "Why is this street high risk?"
    result = copilot_service.answer_copilot(message, "en", {"time": "09:00", "selected_segment_id": "missing"})
    assert result["mode"] == "template"
    logged = "\n".join(record.getMessage() for record in caplog.records)
    assert message not in logged and "22.7146202" not in logged


def test_stops_missing_does_not_block_routing_and_display_names_are_cosmetic(monkeypatch):
    response = CLIENT.post("/api/routes", json={"origin": {"lat": 22.7146202, "lon": 75.8542367}, "destination": {"lat": 22.7188165, "lon": 75.8553691}, "time": "09:00"})
    assert response.status_code == 200
    assert display_osm_name("M.G.ROAD") == "M.G.Road"
    assert display_osm_name("Kadavghat road") == "Kadavghat road"
    from app.routes.planner import _display_geojson_names

    cached = {"type": "FeatureCollection", "features": [{"type": "Feature", "properties": {"name": "M.G.ROAD"}, "geometry": None}]}
    assert _display_geojson_names(cached)["features"][0]["properties"]["name"] == "M.G.Road"
    assert cached["features"][0]["properties"]["name"] == "M.G.ROAD"


def test_user_facing_copy_has_no_forbidden_medical_or_guarantee_wording():
    forbidden = ("heatstroke", "prevent", "safe route", "treatment", "medicine", "medication", "सुरक्षित मार्ग", "सुरक्षित रास्ता", "हीटस्ट्रोक", "इलाज", "दवा", "निदान", "बचाव की गारंटी")
    allowlisted = ("does not diagnose", "not a safety guarantee")
    paths = [ROOT / "app" / "templates", ROOT / "app" / "static" / "js", ROOT / "app" / "services" / "copilot_templates.py"]
    texts = []
    for path in paths:
        files = path.rglob("*") if path.is_dir() else [path]
        texts.extend(file.read_text(encoding="utf-8") for file in files if file.is_file())
    content = "\n".join([*texts, *CITIZEN_EN.values(), *CITIZEN_HI.values()]).casefold()
    for phrase in forbidden:
        assert not re.search(rf"(?<![a-z]){re.escape(phrase.casefold())}(?![a-z])", content)
    assert all(item in content for item in allowlisted)


def test_security_storage_and_provenance_contracts():
    assert ".env" in (ROOT / ".gitignore").read_text(encoding="utf-8")
    values = dict(
        line.split("=", 1) for line in (ROOT / ".env.example").read_text(encoding="utf-8").splitlines()
        if "=" in line and not line.lstrip().startswith("#")
    )
    assert all(values[name] == "" for name in ("LLM_PROVIDER", "LLM_API_KEY", "LLM_MODEL", "LLM_BASE_URL"))
    frontend = "\n".join(path.read_text(encoding="utf-8") for path in (ROOT / "app" / "static" / "js").glob("*.js"))
    assert "LLM_API_KEY" not in frontend and "localStorage.setItem(\"heatshield-citizen-language\"" in frontend
    assert "sessionStorage" not in frontend
    for time in get_config().canonical_times:
        for name in (f"shade_fractions_{time.replace(':', '-')}.geojson", f"exposure_{time.replace(':', '-')}.geojson", f"risk_{time.replace(':', '-')}.geojson"):
            document = json.loads((get_config().cache_data_dir / name).read_text(encoding="utf-8"))
            assert PROVENANCE <= document["features"][0]["properties"].keys()


def test_active_shadow_exposure_risk_and_plan_caches_share_the_config_version():
    config = get_config()
    paths = []
    for time in config.canonical_times:
        slug = time.replace(":", "-")
        paths.extend(config.cache_data_dir / f"{prefix}_{slug}.geojson" for prefix in ("shade_fractions", "exposure", "risk"))
    paths.extend((config.cache_data_dir / "plans").glob("*.json"))
    for path in paths:
        document = json.loads(path.read_text(encoding="utf-8"))
        assert document.get("metadata", {}).get("config_version", document.get("config_version")) == config.version, path


def _without_runtime_values(value):
    """Keep timing telemetry out of a semantic cache reproducibility comparison."""
    if isinstance(value, dict):
        return {
            key: _without_runtime_values(nested)
            for key, nested in value.items()
            if key not in {"duration_seconds", "runtime_seconds"}
        }
    if isinstance(value, list):
        return [_without_runtime_values(item) for item in value]
    return value


def _generated_cache_documents(config):
    paths = []
    for canonical_time in config.canonical_times:
        slug = canonical_time.replace(":", "-")
        paths.extend(
            config.cache_data_dir / f"{prefix}_{slug}.geojson"
            for prefix in ("shadow_polygons", "shade_fractions", "exposure", "risk")
        )
    paths.extend(sorted((config.cache_data_dir / "plans").glob("*.json")))
    return {
        str(path.relative_to(config.cache_data_dir)): _without_runtime_values(json.loads(path.read_text(encoding="utf-8")))
        for path in paths
    }


@pytest.mark.slow
def test_precompute_sequence_is_deterministic_on_an_isolated_cache_copy(tmp_path):
    """Replay the script sequence twice without ever changing the real demo cache."""
    config = _temporary_config(tmp_path)
    presets = (
        {"water_points": 2, "cooling_centres": 1, "shade_structures": 2},
        {"water_points": 1, "cooling_centres": 1, "shade_structures": 1},
        {"water_points": 3, "cooling_centres": 2, "shade_structures": 3},
        {"water_points": 4, "cooling_centres": 2, "shade_structures": 4},
    )

    def replay() -> dict:
        precompute_shadows(config)
        precompute_exposure(config)
        precompute_risk(config)
        for resources in presets:
            plan = optimize_resources(resources, config)
            store_cached_plan(plan["plan_id"], plan, config)
        return _generated_cache_documents(config)

    first, second = replay(), replay()
    differing = sorted(path for path in first.keys() | second.keys() if first.get(path) != second.get(path))
    assert not differing, f"Non-deterministic generated cache files: {', '.join(differing)}"


def test_no_hardcoded_demo_results_or_fixed_segment_ids_in_app_or_static():
    text = "\n".join(
        path.read_text(encoding="utf-8")
        for root in (ROOT / "app",)
        for path in root.rglob("*")
        if path.is_file() and path.suffix in {".py", ".js", ".html", ".css"} and "vendor" not in path.parts
    )
    assert not any(value in text for value in ("62860", "54063", "49402"))
    assert not re.search(r"osm-\d{5,}-\d{5,}-\d+", text)


def test_read_only_demo_readiness_command_passes():
    result = subprocess.run(
        ["python", "scripts/verify_demo_ready.py"], cwd=ROOT, check=False, capture_output=True, text=True
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "FAIL |" not in result.stdout
