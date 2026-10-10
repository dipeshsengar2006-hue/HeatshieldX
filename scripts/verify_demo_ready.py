"""Read-only readiness checks for the fixed preloaded HeatShield X demo."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Callable


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.config import get_config  # noqa: E402
from app.repositories.cache import load_cached_geojson  # noqa: E402
from app.services.copilot_service import answer_copilot  # noqa: E402
from app.services.explainability_engine import deduplicate_risk_features  # noqa: E402
from app.services.routing_engine import build_route_graph  # noqa: E402


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _cache_version(path: Path) -> str | None:
    document = _read_json(path)
    return document.get("metadata", {}).get("config_version") or document.get("config_version")


def _check(label: str, operation: Callable[[], str]) -> bool:
    try:
        print(f"PASS | {label} | {operation()}")
        return True
    except Exception as exc:  # The script must report every readiness failure.
        print(f"FAIL | {label} | {exc}")
        return False


def _cache_versions() -> str:
    config = get_config()
    paths = []
    for canonical_time in config.canonical_times:
        slug = canonical_time.replace(":", "-")
        paths.extend((
            config.cache_data_dir / f"shade_fractions_{slug}.geojson",
            config.cache_data_dir / f"exposure_{slug}.geojson",
            config.cache_data_dir / f"risk_{slug}.geojson",
        ))
    plan_paths = sorted((config.cache_data_dir / "plans").glob("*.json"))
    if not plan_paths:
        raise RuntimeError("No cached plans found. Run `python scripts/precompute_plans.py`.")
    paths.extend(plan_paths)
    absent = [str(path) for path in paths if not path.exists()]
    if absent:
        raise RuntimeError(f"Required caches are missing: {', '.join(absent)}")
    versions = {str(path.relative_to(config.cache_data_dir)): _cache_version(path) for path in paths}
    inconsistent = {path: version for path, version in versions.items() if version != config.version}
    if inconsistent:
        raise RuntimeError(f"Config versions differ from {config.version}: {inconsistent}")
    return f"config_version={config.version}; {len(paths)} shadow/exposure/risk/plan assets"


def _counts() -> str:
    streets = load_cached_geojson("streets")
    buildings = load_cached_geojson("buildings")
    risk = _read_json(get_config().cache_data_dir / "risk_09-00.geojson")
    directed = len(streets.get("features", []))
    canonical = len(deduplicate_risk_features(risk.get("features", []))[0])
    building_count = len(buildings.get("features", []))
    if (directed, canonical, building_count) != (940, 467, 3793):
        raise RuntimeError(f"expected 940 directed / 467 canonical streets and 3793 buildings; got {directed} / {canonical} / {building_count}")
    return f"940 directed / 467 canonical streets; 3793 buildings"


def _stops() -> str:
    path = get_config().cache_data_dir / "stops.geojson"
    if not path.exists():
        return "No stop data"
    return f"{len(_read_json(path).get('features', []))} cached stops"


def _plans() -> str:
    config = get_config()
    required = ((2, 1, 2), (1, 1, 1), (3, 2, 3), (4, 2, 4))
    missing = [
        f"w{water}-c{cooling}-s{shade}-{config.version}.json"
        for water, cooling, shade in required
        if not (config.cache_data_dir / "plans" / f"w{water}-c{cooling}-s{shade}-{config.version}.json").exists()
    ]
    if missing:
        raise RuntimeError(f"Missing preset plans: {', '.join(missing)}")
    return "four preset plans cached"


def _routing() -> str:
    graph = build_route_graph(load_cached_geojson("streets"))
    if graph.graph.number_of_edges() == 0:
        raise RuntimeError("Routing graph has no edges")
    return f"{graph.graph.number_of_nodes()} nodes; {graph.graph.number_of_edges()} directed segments"


def _copilot() -> str:
    result = answer_copilot("How do I compare route options?", "en", {"view": "planner"})
    if result["mode"] != "template" or not result["answer"]:
        raise RuntimeError("Template answer unavailable")
    return "template answer returned"


def _llm_disabled() -> str:
    if get_config().feature_flags.get("copilot_llm"):
        raise RuntimeError("Optional LLM must be disabled for the offline demo")
    return "optional LLM disabled"


def _imports() -> str:
    from app.main import app  # noqa: PLC0415

    return f"FastAPI app imported ({app.title})"


def main() -> int:
    checks = (
        ("required caches and config versions", _cache_versions),
        ("demo cache counts", _counts),
        ("stop cache state", _stops),
        ("preset plans", _plans),
        ("routing graph", _routing),
        ("Copilot template mode", _copilot),
        ("optional LLM", _llm_disabled),
        ("app import", _imports),
    )
    passed = [_check(label, operation) for label, operation in checks]
    return 0 if all(passed) else 1


if __name__ == "__main__":
    raise SystemExit(main())
