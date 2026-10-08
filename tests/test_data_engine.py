import geopandas as gpd
from shapely.geometry import LineString, Polygon

from app.services.data_engine import project_to_metric_crs, repair_and_filter_geometries


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
