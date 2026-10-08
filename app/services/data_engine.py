"""OSM acquisition, geometry cleaning, metric projection, and cache precomputation."""

from __future__ import annotations

import json
import logging
import math
import re
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import geopandas as gpd
import osmnx as ox
from shapely.geometry.base import BaseGeometry

from app.config import AppConfig, get_config
from app.contracts import Building, Provenance, StreetSegment


LOGGER = logging.getLogger(__name__)


class CoverageGateError(RuntimeError):
    """Raised when the configured area is not dense enough for the shadow workflow."""


def project_to_metric_crs(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Project a WGS84 GeoDataFrame to a local metric CRS for geometry work."""
    if gdf.empty:
        return gdf
    projected = gdf.estimate_utm_crs()
    if projected is None:
        raise ValueError("Could not determine a suitable local metric CRS for the demo area.")
    return gdf.to_crs(projected)


def repair_and_filter_geometries(
    gdf: gpd.GeoDataFrame, allowed_types: set[str], label: str
) -> gpd.GeoDataFrame:
    """Repair invalid geometries where possible, logging each discarded record class."""
    if gdf.empty:
        return gdf.copy()
    cleaned = gdf[gdf.geometry.notna()].copy()
    missing_count = len(gdf) - len(cleaned)
    invalid = ~cleaned.geometry.is_valid
    invalid_count = int(invalid.sum())
    if invalid_count:
        cleaned.loc[invalid, "geometry"] = cleaned.loc[invalid, "geometry"].make_valid()
    type_mask = cleaned.geometry.geom_type.isin(allowed_types)
    dropped_count = int((~type_mask).sum())
    if missing_count or invalid_count or dropped_count:
        LOGGER.warning(
            "%s geometry cleanup: missing=%s repaired=%s skipped_after_type_check=%s",
            label,
            missing_count,
            invalid_count,
            dropped_count,
        )
    return cleaned.loc[type_mask].copy()


def _number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    match = re.search(r"[-+]?\\d*\\.?\\d+", str(value))
    if not match:
        return None
    parsed = float(match.group())
    return parsed if parsed > 0 else None


def _safe_identifier(value: Any) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "-", str(value)).strip("-") or "unknown"


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, float) and math.isnan(value):
        return None
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    return str(value)


def _provenance(config: AppConfig, estimated: bool) -> Provenance:
    return Provenance(
        source_type="osm",
        source_reference="OpenStreetMap via OSMnx",
        observed_or_estimated="ESTIMATED" if estimated else "OBSERVED",
        modelled_or_interpolated="NOT_APPLICABLE",
        timestamp=datetime.now(UTC),
        assumptions_version=config.version,
        computation_mode=config.computation_mode,
    )


def _height_details(row: Any, config: AppConfig) -> tuple[float, float | None, str, bool]:
    actual_height = _number(row.get("height"))
    if actual_height is not None:
        return actual_height, _number(row.get("building:levels")), "actual", False
    levels = _number(row.get("building:levels"))
    if levels is not None:
        return levels * config.building_height_per_floor, levels, "levels", True
    return (
        config.fallback_building_floors * config.building_height_per_floor,
        None,
        "fallback",
        True,
    )


def _write_geojson(path: Path, gdf: gpd.GeoDataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(gdf.to_json(), encoding="utf-8")


def _normalize_streets(edges: gpd.GeoDataFrame, config: AppConfig) -> gpd.GeoDataFrame:
    projected = project_to_metric_crs(repair_and_filter_geometries(edges, {"LineString", "MultiLineString"}, "streets"))
    records: list[dict[str, Any]] = []
    metadata_columns = ("osmid", "name", "highway", "maxspeed", "oneway")
    for index, row in projected.iterrows():
        index_parts = index if isinstance(index, tuple) else (index,)
        segment = StreetSegment(
            segment_id="osm-" + "-".join(_safe_identifier(part) for part in index_parts),
            geometry=row.geometry.__geo_interface__,
            length_m=float(row.geometry.length),
            road_metadata={column: _json_safe(row.get(column)) for column in metadata_columns if column in row},
            provenance=_provenance(config, estimated=False),
        )
        records.append({
            "segment_id": segment.segment_id,
            "length_m": segment.length_m,
            "road_metadata": json.dumps(segment.road_metadata),
            "source_type": segment.provenance.source_type,
            "source_reference": segment.provenance.source_reference,
            "observed_or_estimated": segment.provenance.observed_or_estimated,
            "modelled_or_interpolated": segment.provenance.modelled_or_interpolated,
            "timestamp": segment.provenance.timestamp.isoformat(),
            "assumptions_version": segment.provenance.assumptions_version,
            "computation_mode": segment.provenance.computation_mode,
            "geometry": row.geometry,
        })
    return gpd.GeoDataFrame(records, geometry="geometry", crs=projected.crs)


def _normalize_buildings(buildings: gpd.GeoDataFrame, config: AppConfig) -> gpd.GeoDataFrame:
    projected = project_to_metric_crs(repair_and_filter_geometries(buildings, {"Polygon", "MultiPolygon"}, "buildings"))
    records: list[dict[str, Any]] = []
    for index, row in projected.iterrows():
        index_parts = index if isinstance(index, tuple) else (index,)
        height_m, levels, height_source, estimated = _height_details(row, config)
        building = Building(
            building_id="osm-" + "-".join(_safe_identifier(part) for part in index_parts),
            footprint=row.geometry.__geo_interface__,
            height_m=height_m,
            height_source=height_source,
            estimated_flag=estimated,
            levels=levels,
            provenance=_provenance(config, estimated=estimated),
        )
        if estimated:
            LOGGER.warning("Estimated building height for %s using %s", building.building_id, height_source)
        records.append({
            "building_id": building.building_id,
            "height_m": building.height_m,
            "height_source": building.height_source,
            "estimated_flag": building.estimated_flag,
            "levels": building.levels,
            "source_type": building.provenance.source_type,
            "source_reference": building.provenance.source_reference,
            "observed_or_estimated": building.provenance.observed_or_estimated,
            "modelled_or_interpolated": building.provenance.modelled_or_interpolated,
            "timestamp": building.provenance.timestamp.isoformat(),
            "assumptions_version": building.provenance.assumptions_version,
            "computation_mode": building.provenance.computation_mode,
            "geometry": row.geometry,
        })
    return gpd.GeoDataFrame(records, geometry="geometry", crs=projected.crs)


def facility_query_tags(config: AppConfig) -> dict[str, list[str]]:
    """Build the OSM query exclusively from centrally configured facility tags."""
    tags: dict[str, set[str]] = {}
    for type_rules in config.facility_tag_rules.values():
        for tag_key, values in type_rules.items():
            tags.setdefault(tag_key, set()).update(values)
    return {tag_key: sorted(values) for tag_key, values in tags.items()}


def classify_facility(row: Any, config: AppConfig) -> tuple[str, str, str] | None:
    """Return facility type and matching OSM tag; healthcare never counts as cooling."""
    for facility_type in config.facility_classification_order:
        for tag_key, values in config.facility_tag_rules[facility_type].items():
            value = row.get(tag_key)
            if value is not None and str(value) in values:
                return facility_type, tag_key, str(value)
    return None


def _normalize_facilities(facilities: gpd.GeoDataFrame, config: AppConfig) -> gpd.GeoDataFrame:
    projected = project_to_metric_crs(repair_and_filter_geometries(facilities, {"Point", "Polygon", "MultiPolygon"}, "facilities"))
    records: list[dict[str, Any]] = []
    for index, row in projected.iterrows():
        classification = classify_facility(row, config)
        if classification is None:
            LOGGER.warning("Skipping facility with no configured classification: %s", index)
            continue
        facility_type, osm_tag_key, osm_tag_value = classification
        geometry: BaseGeometry = row.geometry.centroid if row.geometry.geom_type != "Point" else row.geometry
        index_parts = index if isinstance(index, tuple) else (index,)
        records.append({
            "facility_id": "osm-" + "-".join(_safe_identifier(part) for part in index_parts),
            "facility_type": facility_type,
            "name": _json_safe(row.get("name")),
            "osm_tag_key": osm_tag_key,
            "osm_tag_value": osm_tag_value,
            "existing_facility": True,
            "source_type": "osm",
            "source_reference": "OpenStreetMap via OSMnx",
            "observed_or_estimated": "OBSERVED",
            "modelled_or_interpolated": "NOT_APPLICABLE",
            "timestamp": datetime.now(UTC).isoformat(),
            "assumptions_version": config.version,
            "computation_mode": config.computation_mode,
            "geometry": geometry,
        })
    return gpd.GeoDataFrame(records, geometry="geometry", crs=projected.crs)


def _to_wgs84(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    return gdf.to_crs("EPSG:4326") if not gdf.empty else gdf.set_crs("EPSG:4326", allow_override=True)


def _raw_from_normalized(gdf: gpd.GeoDataFrame, keep_columns: list[str]) -> gpd.GeoDataFrame:
    available = [column for column in keep_columns if column in gdf.columns]
    return gdf[available + ["geometry"]].copy()


def precompute_demo_area(config: AppConfig | None = None) -> dict[str, int | bool | str]:
    """Download OSM data once, validate coverage, and write raw + cached GeoJSON files."""
    active_config = config or get_config()
    started = time.perf_counter()
    active_config.raw_data_dir.mkdir(parents=True, exist_ok=True)
    active_config.cache_data_dir.mkdir(parents=True, exist_ok=True)
    point = (active_config.demo_area.center_lat, active_config.demo_area.center_lon)
    LOGGER.info("Loading OSM data for %s", active_config.demo_area.name)
    try:
        ox.settings.requests_timeout = active_config.osm_request_timeout_s
        ox.settings.overpass_rate_limit = False
        graph = ox.graph_from_point(point, dist=active_config.demo_area.radius_m, dist_type="bbox", network_type="walk")
        edges = ox.graph_to_gdfs(graph, nodes=False, fill_edge_geometry=True)
        buildings = ox.features_from_point(point, tags={"building": True}, dist=active_config.demo_area.radius_m)
        facilities = ox.features_from_point(point, tags=facility_query_tags(active_config), dist=active_config.demo_area.radius_m)
    except Exception as exc:  # OSM/network exceptions vary by provider and library version.
        message = (
            "Unable to load OpenStreetMap data for the configured demo area. "
            "Check network/Overpass availability, then rerun `python scripts/precompute_demo_area.py`; "
            "the web app can use an existing preloaded cache."
        )
        LOGGER.exception(message)
        raise RuntimeError(message) from exc

    street_records = _normalize_streets(edges, active_config)
    building_records = _normalize_buildings(buildings, active_config)
    facility_records = _normalize_facilities(facilities, active_config)

    # Raw files retain only directly downloaded/observed normalized OSM fields in WGS84.
    _write_geojson(active_config.raw_data_dir / "streets_osm.geojson", _to_wgs84(_raw_from_normalized(street_records, ["segment_id", "road_metadata"])))
    _write_geojson(active_config.raw_data_dir / "buildings_osm.geojson", _to_wgs84(_raw_from_normalized(building_records, ["building_id", "height_source", "levels"])))
    _write_geojson(active_config.raw_data_dir / "facilities_osm.geojson", _to_wgs84(_raw_from_normalized(facility_records, ["facility_id", "facility_type", "name", "osm_tag_key", "osm_tag_value", "existing_facility"])))

    facility_type_counts = {
        facility_type: int((facility_records.get("facility_type") == facility_type).sum()) if not facility_records.empty else 0
        for facility_type in active_config.facility_classification_order
    }
    facility_tag_counts = {
        f"{tag_key}={tag_value}": int(
            ((facility_records.get("osm_tag_key") == tag_key) & (facility_records.get("osm_tag_value") == tag_value)).sum()
        ) if not facility_records.empty else 0
        for type_rules in active_config.facility_tag_rules.values()
        for tag_key, values in type_rules.items()
        for tag_value in values
    }
    tagged_height_or_levels = int(
        ((building_records["height_source"] == "actual") | (building_records["height_source"] == "levels")).sum()
    ) if not building_records.empty else 0
    coverage = {
        "demo_area": active_config.demo_area.name,
        "streets": len(street_records),
        "buildings": len(building_records),
        "buildings_with_height_or_levels_tags": tagged_height_or_levels,
        "facilities_by_type": facility_type_counts,
        "facilities_by_osm_tag": facility_tag_counts,
        "water_facilities": facility_type_counts["water"],
        "cooling_facilities": facility_type_counts["cooling"],
        "healthcare_facilities": facility_type_counts["healthcare"],
        "minimum_buildings_for_shadow": active_config.minimum_building_count_for_shadow,
        "shadow_ready": len(building_records) >= active_config.minimum_building_count_for_shadow,
        "metric_crs": str(street_records.crs),
        "config_version": active_config.version,
    }
    (active_config.cache_data_dir / "coverage_report.json").write_text(json.dumps(coverage, indent=2), encoding="utf-8")

    if not coverage["shadow_ready"]:
        raise CoverageGateError(
            f"OSM found {coverage['buildings']} valid buildings, below the configured "
            f"minimum of {active_config.minimum_building_count_for_shadow} for shadow processing. "
            "Stop here and propose another dense approximately 1 km2 Indore area; do not silently change it."
        )

    _write_geojson(active_config.cache_data_dir / "streets.geojson", _to_wgs84(street_records))
    _write_geojson(active_config.cache_data_dir / "buildings.geojson", _to_wgs84(building_records))
    _write_geojson(active_config.cache_data_dir / "facilities.geojson", _to_wgs84(facility_records))
    LOGGER.info("OSM precompute completed in %.2fs: %s", time.perf_counter() - started, coverage)
    return coverage
