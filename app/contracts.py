"""Validated data contracts for Prompt 1 records."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class Provenance(BaseModel):
    source_type: Literal["osm", "public", "ward_estimate", "synthetic", "derived"]
    source_reference: str
    observed_or_estimated: Literal["OBSERVED", "ESTIMATED"]
    modelled_or_interpolated: Literal["MODELLED", "INTERPOLATED", "NOT_APPLICABLE"]
    timestamp: datetime
    assumptions_version: str
    computation_mode: Literal["FULL", "SIMPLIFIED", "FALLBACK"]


class StreetSegment(BaseModel):
    segment_id: str
    geometry: dict[str, Any]
    length_m: float = Field(ge=0)
    road_metadata: dict[str, Any]
    building_context: list[str] = Field(default_factory=list)
    risk_snapshot_ids: list[str] = Field(default_factory=list)
    provenance: Provenance


class Building(BaseModel):
    building_id: str
    footprint: dict[str, Any]
    height_m: float = Field(gt=0)
    height_source: Literal["actual", "levels", "fallback"]
    estimated_flag: bool
    levels: float | None = Field(default=None, gt=0)
    provenance: Provenance
