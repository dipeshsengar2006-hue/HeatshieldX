"""The single, versioned source of HeatShield X runtime configuration."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field


PROJECT_ROOT = Path(__file__).resolve().parent.parent


class DemoArea(BaseModel):
    name: str
    city: str
    country: str
    center_lat: float
    center_lon: float
    radius_m: int = Field(gt=0)
    selection_note: str


class AppConfig(BaseModel):
    version: str
    demo_area: DemoArea
    canonical_times: tuple[str, ...]
    building_height_per_floor: float
    fallback_building_floors: int
    minimum_building_count_for_shadow: int
    computation_mode: Literal["FULL", "SIMPLIFIED", "FALLBACK"]
    feature_flags: dict[str, bool]
    data_source_metadata: dict[str, str]
    risk_normalization_method: str
    risk_class_ranges: dict[str, tuple[int, int]]
    vulnerability_weights: dict[str, float]
    cooling_service_radius_m: int
    water_service_radius_m: int
    access_penalty_weights: dict[str, float]
    intervention_effect_coefficients: dict[str, float]
    route_objective_weights: dict[str, float]
    osm_request_timeout_s: int
    raw_data_dir: Path
    cache_data_dir: Path


@lru_cache(maxsize=1)
def get_config() -> AppConfig:
    """Load the complete configuration through this module only."""
    mode = os.getenv("HEATSHIELD_COMPUTATION_MODE", "FULL").upper()
    if mode not in {"FULL", "SIMPLIFIED", "FALLBACK"}:
        raise ValueError("HEATSHIELD_COMPUTATION_MODE must be FULL, SIMPLIFIED, or FALLBACK.")

    return AppConfig(
        version="2026-10-09-prompt-1",
        demo_area=DemoArea(
            name="Rajwada-Sarafa demonstration area",
            city="Indore",
            country="India",
            center_lat=22.7177,
            center_lon=75.8550,
            radius_m=500,
            selection_note=(
                "Preferred approximately 1 km2 dense area around Rajwada-Sarafa; "
                "OSM building coverage must pass the Prompt 1 gate."
            ),
        ),
        canonical_times=("09:00", "11:00", "13:00", "15:00", "17:00"),
        building_height_per_floor=3.0,
        fallback_building_floors=2,
        minimum_building_count_for_shadow=25,
        computation_mode=mode,
        feature_flags={
            "preloaded_mode": True,
            "shadow_engine": False,
            "risk_engine": False,
            "routing": False,
            "copilot": False,
        },
        data_source_metadata={
            "streets": "OpenStreetMap via OSMnx",
            "buildings": "OpenStreetMap via OSMnx",
            "facilities": "OpenStreetMap via OSMnx; existing facilities only",
            "demographics": "Ward-level estimation planned; not loaded in Prompt 1",
        },
        # Required central placeholders for later SRS modules. They are not used in Prompt 1.
        risk_normalization_method="min_max_selected_analysis_scope",
        risk_class_ranges={"LOW": (0, 25), "MODERATE": (26, 50), "HIGH": (51, 75), "CRITICAL": (76, 100)},
        vulnerability_weights={"elderly": 0.5, "outdoor_workers": 0.5},
        cooling_service_radius_m=750,
        water_service_radius_m=400,
        access_penalty_weights={"water": 0.5, "cooling": 0.5, "availability": 1.0},
        intervention_effect_coefficients={"water_point": 0.0, "cooling_centre": 0.0, "shade_structure": 0.0},
        route_objective_weights={"alpha": 0.5, "beta": 0.5},
        osm_request_timeout_s=45,
        raw_data_dir=PROJECT_ROOT / "data" / "raw",
        cache_data_dir=PROJECT_ROOT / "data" / "cache",
    )
