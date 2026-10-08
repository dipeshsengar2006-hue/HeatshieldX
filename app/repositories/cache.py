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
