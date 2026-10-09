"""Read cached geospatial API assets; routes never trigger GIS computation."""

from __future__ import annotations

import json
from pathlib import Path

from app.config import AppConfig, get_config


def cache_path(name: str, config: AppConfig | None = None) -> Path:
    active_config = config or get_config()
    return active_config.cache_data_dir / f"{name}.geojson"


def load_cached_geojson(name: str, config: AppConfig | None = None) -> dict:
    path = cache_path(name, config)
    if not path.exists():
        raise FileNotFoundError(
            f"Preloaded {name} data is unavailable at {path}. "
            "Run `python scripts/precompute_demo_area.py` while OSM is available."
        )
    return json.loads(path.read_text(encoding="utf-8"))


def cache_status(config: AppConfig | None = None) -> dict[str, bool]:
    return {
        "streets": cache_path("streets", config).exists(),
        "buildings": cache_path("buildings", config).exists(),
        "facilities": cache_path("facilities", config).exists(),
    }


def load_shadow_snapshot(kind: str, canonical_time: str, config: AppConfig | None = None) -> dict:
    """Load one precomputed geometric shadow asset; never calculate inside a request."""
    if kind not in {"shadow_polygons", "shade_fractions"}:
        raise ValueError(f"Unsupported shadow snapshot kind: {kind}")
    slug = canonical_time.replace(":", "-")
    active_config = config or get_config()
    path = active_config.cache_data_dir / f"{kind}_{slug}.geojson"
    if not path.exists():
        raise FileNotFoundError(
            f"Precomputed {kind.replace('_', ' ')} for {canonical_time} are unavailable at {path}. "
            "Run `python scripts/precompute_shadows.py` after Prompt 1 cache data is available."
        )
    return json.loads(path.read_text(encoding="utf-8"))


def load_exposure_snapshot(canonical_time: str, config: AppConfig | None = None) -> dict:
    """Load one canonical cache-only exposure snapshot."""
    active_config = config or get_config()
    slug = canonical_time.replace(":", "-")
    path = active_config.cache_data_dir / f"exposure_{slug}.geojson"
    if not path.exists():
        raise FileNotFoundError(
            f"Precomputed exposure for {canonical_time} is unavailable at {path}. "
            "Run `python scripts/precompute_exposure.py` after the required cache data is available."
        )
    return json.loads(path.read_text(encoding="utf-8"))


def load_risk_snapshot(canonical_time: str, config: AppConfig | None = None) -> dict:
    """Load one canonical cache-only risk snapshot."""
    active_config = config or get_config()
    slug = canonical_time.replace(":", "-")
    path = active_config.cache_data_dir / f"risk_{slug}.geojson"
    if not path.exists():
        raise FileNotFoundError(
            f"Precomputed risk for {canonical_time} is unavailable at {path}. "
            "Run `python scripts/precompute_risk.py` after the required exposure cache is available."
        )
    return json.loads(path.read_text(encoding="utf-8"))


def plan_cache_path(plan_id: str, config: AppConfig | None = None) -> Path:
    """Return the versioned, on-disk cache path for one resource plan."""
    active_config = config or get_config()
    return active_config.cache_data_dir / "plans" / f"{plan_id}.json"


def load_cached_plan(plan_id: str, config: AppConfig | None = None) -> dict | None:
    """Load a precomputed plan when present; a missing plan is a normal cache miss."""
    path = plan_cache_path(plan_id, config)
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def store_cached_plan(plan_id: str, plan: dict, config: AppConfig | None = None) -> None:
    """Persist a deterministic resource plan atomically enough for local demo use."""
    path = plan_cache_path(plan_id, config)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(plan), encoding="utf-8")
