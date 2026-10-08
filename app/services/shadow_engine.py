"""Cache-first geometric shadow validation for the five canonical demo times."""

from __future__ import annotations

import json
import logging
import math
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, time as clock_time
from pathlib import Path
from typing import Any, Iterator
from zoneinfo import ZoneInfo

import geopandas as gpd
import pvlib
from shapely import affinity, make_valid
from shapely.geometry import Polygon
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union
from shapely.strtree import STRtree

from app.config import AppConfig, get_config
from app.services.data_engine import project_to_metric_crs


LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class SolarPosition:
    """Solar values used by one canonical snapshot."""

    canonical_time: str
    azimuth_deg: float
    elevation_deg: float
    timestamp: str


@dataclass
class GeometryStats:
    """Diagnostics for skipped or repaired source geometry."""

    invalid_buildings_repaired: int = 0
    invalid_buildings_skipped: int = 0
    shadow_buildings_skipped: int = 0
    invalid_streets_repaired: int = 0
    invalid_streets_skipped: int = 0


def _canonical_datetime(config: AppConfig, canonical_time: str) -> datetime:
    if canonical_time not in config.canonical_times:
        raise ValueError(f"Unsupported shadow time '{canonical_time}'. Use one of: {', '.join(config.canonical_times)}.")
    local_time = clock_time.fromisoformat(canonical_time)
    return datetime.combine(
        config.representative_heatwave_date,
        local_time,
        tzinfo=ZoneInfo(config.representative_timezone),
    )


def solar_position(config: AppConfig, canonical_time: str) -> SolarPosition:
    """Calculate a deterministic pvlib solar position for the configured centroid."""
    timestamp = _canonical_datetime(config, canonical_time)
    position = pvlib.solarposition.get_solarposition(
        time=timestamp,
        latitude=config.demo_area.center_lat,
        longitude=config.demo_area.center_lon,
        method=config.solar_position_method,
    ).iloc[0]
    return SolarPosition(
        canonical_time=canonical_time,
        azimuth_deg=float(position["azimuth"]),
        elevation_deg=float(position["apparent_elevation"]),
        timestamp=timestamp.isoformat(),
    )


def shadow_length_m(height_m: float, elevation_deg: float, max_length_m: float) -> float:
    """Calculate and cap the ground-projected shadow length for a building."""
    if height_m <= 0 or elevation_deg <= 0:
        return 0.0
    tangent = math.tan(math.radians(elevation_deg))
    if tangent <= 0:
        return 0.0
    return min(height_m / tangent, max_length_m)


def _repair_geometry(geometry: BaseGeometry, label: str, stats: GeometryStats) -> BaseGeometry | None:
    if geometry is None or geometry.is_empty:
        setattr(stats, f"invalid_{label}_skipped", getattr(stats, f"invalid_{label}_skipped") + 1)
        LOGGER.warning("Skipping empty %s geometry.", label)
        return None
    if geometry.is_valid:
        return geometry
    try:
        repaired = make_valid(geometry)
    except Exception as exc:
        setattr(stats, f"invalid_{label}_skipped", getattr(stats, f"invalid_{label}_skipped") + 1)
        LOGGER.warning("Skipping invalid %s geometry because repair failed: %s", label, exc)
        return None
    if repaired.is_empty or not repaired.is_valid:
        setattr(stats, f"invalid_{label}_skipped", getattr(stats, f"invalid_{label}_skipped") + 1)
        LOGGER.warning("Skipping invalid %s geometry because repair produced no valid geometry.", label)
        return None
    setattr(stats, f"invalid_{label}_repaired", getattr(stats, f"invalid_{label}_repaired") + 1)
    LOGGER.warning("Repaired invalid %s geometry.", label)
    return repaired


def _polygon_parts(geometry: BaseGeometry) -> Iterator[Polygon]:
    if geometry.geom_type == "Polygon":
        yield geometry
    elif geometry.geom_type == "MultiPolygon":
        yield from geometry.geoms


def shadow_polygon(
    footprint: BaseGeometry,
    height_m: float,
    solar_azimuth_deg: float,
    solar_elevation_deg: float,
    max_length_m: float,
    min_elevation_deg: float,
) -> BaseGeometry | None:
    """Sweep each footprint edge opposite the sun and exclude the building itself."""
    if solar_elevation_deg <= min_elevation_deg:
        return None
    length_m = shadow_length_m(height_m, solar_elevation_deg, max_length_m)
    if length_m <= 0:
        return None
    shadow_azimuth = math.radians((solar_azimuth_deg + 180.0) % 360.0)
    offset_x = length_m * math.sin(shadow_azimuth)
    offset_y = length_m * math.cos(shadow_azimuth)
    translated = affinity.translate(footprint, xoff=offset_x, yoff=offset_y)
    swept_parts: list[BaseGeometry] = [footprint, translated]
    for polygon in _polygon_parts(footprint):
        coordinates = list(polygon.exterior.coords)
        for start, end in zip(coordinates, coordinates[1:]):
            swept_parts.append(
                Polygon(
                    [
                        start,
                        end,
                        (end[0] + offset_x, end[1] + offset_y),
                        (start[0] + offset_x, start[1] + offset_y),
                    ]
                )
            )
    try:
        shadow = unary_union(swept_parts).difference(footprint)
        return make_valid(shadow) if not shadow.is_valid else shadow
    except Exception as exc:
        LOGGER.warning("Skipping shadow geometry after a Shapely operation failed: %s", exc)
        return None


def build_shadow_polygons(
    buildings: gpd.GeoDataFrame, solar: SolarPosition, config: AppConfig
) -> tuple[gpd.GeoDataFrame, GeometryStats]:
    """Create building shadows in a projected metric CRS without failing on bad input."""
    stats = GeometryStats()
    records: list[dict[str, Any]] = []
    computed_at = datetime.now(UTC).isoformat()
    for _, row in buildings.iterrows():
        footprint = _repair_geometry(row.geometry, "buildings", stats)
        if footprint is None:
            continue
        shadow = shadow_polygon(
            footprint,
            float(row["height_m"]),
            solar.azimuth_deg,
            solar.elevation_deg,
            config.shadow_max_length_m,
            config.shadow_min_solar_elevation_deg,
        )
        if shadow is None or shadow.is_empty:
            stats.shadow_buildings_skipped += 1
            continue
        if not shadow.is_valid:
            try:
                shadow = make_valid(shadow)
            except Exception as exc:
                stats.shadow_buildings_skipped += 1
                LOGGER.warning("Skipping invalid shadow for %s: %s", row.get("building_id"), exc)
                continue
        records.append(
            {
                "building_id": row["building_id"],
                "height_m": float(row["height_m"]),
                "height_source": row.get("height_source", "unknown"),
                "estimated_flag": bool(row.get("estimated_flag", False)),
                "canonical_time": solar.canonical_time,
                "solar_azimuth_deg": solar.azimuth_deg,
                "solar_elevation_deg": solar.elevation_deg,
                "shadow_length_m": shadow_length_m(float(row["height_m"]), solar.elevation_deg, config.shadow_max_length_m),
                "source_type": "derived",
                "source_reference": "OpenStreetMap building footprint and configured height hierarchy",
                "observed_or_estimated": "ESTIMATED" if bool(row.get("estimated_flag", False)) else "OBSERVED",
                "modelled_or_interpolated": "MODELLED",
                "timestamp": computed_at,
                "assumptions_version": config.version,
                "computation_mode": config.shadow_computation_mode,
                "geometry": shadow,
            }
        )
    return gpd.GeoDataFrame(records, geometry="geometry", crs=buildings.crs), stats


def calculate_shade_fractions(
    streets: gpd.GeoDataFrame,
    shadows: gpd.GeoDataFrame,
    solar: SolarPosition,
    config: AppConfig,
    stats: GeometryStats,
    estimated_height_building_count: int,
) -> gpd.GeoDataFrame:
    """Intersect each street only with indexed nearby shadows and clamp results to [0, 1]."""
    shadow_geometries = list(shadows.geometry)
    tree = STRtree(shadow_geometries) if shadow_geometries else None
    records: list[dict[str, Any]] = []
    computed_at = datetime.now(UTC).isoformat()
    for _, row in streets.iterrows():
        street = _repair_geometry(row.geometry, "streets", stats)
        if street is None or street.length <= 0:
            continue
        candidates = [] if tree is None else [shadow_geometries[int(index)] for index in tree.query(street)]
        shaded_length_m = 0.0
        if candidates:
            try:
                shaded_length_m = float(street.intersection(unary_union(candidates)).length)
            except Exception as exc:
                LOGGER.warning("Street %s shadow intersection failed; recording zero shade: %s", row.get("segment_id"), exc)
        shade_fraction = max(0.0, min(1.0, shaded_length_m / float(street.length)))
        records.append(
            {
                "segment_id": row["segment_id"],
                "length_m": float(street.length),
                "shade_fraction": shade_fraction,
                "exposure_fraction": 1.0 - shade_fraction,
                "canonical_time": solar.canonical_time,
                "solar_azimuth_deg": solar.azimuth_deg,
                "solar_elevation_deg": solar.elevation_deg,
                "estimated_height_building_count": estimated_height_building_count,
                "source_type": "derived",
                "source_reference": "Cached OSM streets intersected with modelled building shadows",
                "observed_or_estimated": "ESTIMATED" if estimated_height_building_count else "OBSERVED",
                "modelled_or_interpolated": "MODELLED",
                "timestamp": computed_at,
                "assumptions_version": config.version,
                "computation_mode": config.shadow_computation_mode,
                "geometry": street,
            }
        )
    return gpd.GeoDataFrame(records, geometry="geometry", crs=streets.crs)


def time_slug(canonical_time: str) -> str:
    return canonical_time.replace(":", "-")


def _write_snapshot_geojson(path: Path, gdf: gpd.GeoDataFrame, metadata: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.loads(gdf.to_crs("EPSG:4326").to_json())
    payload["metadata"] = metadata
    path.write_text(json.dumps(payload), encoding="utf-8")


def precompute_shadows(config: AppConfig | None = None) -> dict[str, Any]:
    """Write independent geometric snapshots from cached Prompt 1 buildings and streets."""
    active_config = config or get_config()
    cache_dir = active_config.cache_data_dir
    buildings_path = cache_dir / "buildings.geojson"
    streets_path = cache_dir / "streets.geojson"
    if not buildings_path.exists() or not streets_path.exists():
        raise FileNotFoundError(
            "Preloaded streets/buildings are unavailable. Run `python scripts/precompute_demo_area.py` first."
        )
    started = time.perf_counter()
    buildings = project_to_metric_crs(gpd.read_file(buildings_path))
    streets = gpd.read_file(streets_path).to_crs(buildings.crs)
    estimated_buildings = int(buildings["estimated_flag"].astype(bool).sum())
    report: dict[str, Any] = {
        "config_version": active_config.version,
        "computation_mode": active_config.shadow_computation_mode,
        "representative_date": active_config.representative_heatwave_date.isoformat(),
        "timezone": active_config.representative_timezone,
        "estimated_height_building_count": estimated_buildings,
        "snapshots": {},
    }
    for canonical_time in active_config.canonical_times:
        snapshot_started = time.perf_counter()
        solar = solar_position(active_config, canonical_time)
        shadows, stats = build_shadow_polygons(buildings, solar, active_config)
        shade_fractions = calculate_shade_fractions(
            streets, shadows, solar, active_config, stats, estimated_buildings
        )
        values = shade_fractions["shade_fraction"] if not shade_fractions.empty else []
        metadata = {
            "canonical_time": canonical_time,
            "solar": asdict(solar),
            "computation_mode": active_config.shadow_computation_mode,
            "config_version": active_config.version,
            "estimated_height_building_count": estimated_buildings,
            "has_estimated_building_heights": estimated_buildings > 0,
            "geometry_stats": asdict(stats),
            "duration_seconds": time.perf_counter() - snapshot_started,
        }
        slug = time_slug(canonical_time)
        _write_snapshot_geojson(cache_dir / f"shadow_polygons_{slug}.geojson", shadows, metadata)
        _write_snapshot_geojson(cache_dir / f"shade_fractions_{slug}.geojson", shade_fractions, metadata)
        report["snapshots"][canonical_time] = {
            **metadata,
            "shadow_count": len(shadows),
            "street_count": len(shade_fractions),
            "shade_fraction_min": float(values.min()) if len(values) else 0.0,
            "shade_fraction_mean": float(values.mean()) if len(values) else 0.0,
            "shade_fraction_max": float(values.max()) if len(values) else 0.0,
        }
    report["duration_seconds"] = time.perf_counter() - started
    (cache_dir / "shadow_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    LOGGER.info("Geometric shadow precompute completed in %.2fs", report["duration_seconds"])
    return report
