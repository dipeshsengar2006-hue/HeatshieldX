import geopandas as gpd
from shapely.geometry import LineString, Polygon

from app.config import get_config
from app.services.data_engine import classify_facility, facility_query_tags, project_to_metric_crs, repair_and_filter_geometries


def test_geometries_are_repaired_or_filtered_and_projected_to_metric_crs():
    gdf = gpd.GeoDataFrame(
        {"name": ["street", "invalid-building"]},
        geometry=[LineString([(75.855, 22.7177), (75.856, 22.718)]), Polygon([(0, 0), (1, 1), (1, 0), (0, 1), (0, 0)])],
        crs="EPSG:4326",
    )
    lines = repair_and_filter_geometries(gdf, {"LineString"}, "test")
    projected = project_to_metric_crs(lines)
    assert len(lines) == 1
    assert projected.crs.is_geographic is False
    assert projected.geometry.iloc[0].length > 0


def test_facility_classification_uses_central_rules_and_keeps_healthcare_out_of_cooling():
    config = get_config()
    assert classify_facility({"amenity": "clinic"}, config) == ("healthcare", "amenity", "clinic")
    assert classify_facility({"amenity": "hospital"}, config) == ("healthcare", "amenity", "hospital")
    assert classify_facility({"amenity": "library"}, config) == ("cooling", "amenity", "library")
    assert classify_facility({"shop": "mall"}, config) == ("cooling", "shop", "mall")
    assert classify_facility({"amenity": "fountain"}, config) == ("water", "amenity", "fountain")
    assert classify_facility({"man_made": "water_tap"}, config) == ("water", "man_made", "water_tap")
    assert facility_query_tags(config) == {
        "amenity": ["clinic", "community_centre", "drinking_water", "fountain", "hospital", "library", "townhall", "water_point"],
        "man_made": ["water_tap"],
        "shop": ["mall"],
    }
