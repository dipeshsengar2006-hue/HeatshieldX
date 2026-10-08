from datetime import UTC, datetime

from app.contracts import Building, Provenance, StreetSegment


def provenance() -> Provenance:
    return Provenance(
        source_type="osm",
        source_reference="OpenStreetMap via OSMnx",
        observed_or_estimated="OBSERVED",
        modelled_or_interpolated="NOT_APPLICABLE",
        timestamp=datetime.now(UTC),
        assumptions_version="test",
        computation_mode="FULL",
    )


def test_segment_and_building_contracts_accept_valid_geometry():
    segment = StreetSegment(
        segment_id="osm-1-2-0",
        geometry={"type": "LineString", "coordinates": [[75.855, 22.7177], [75.856, 22.718]]},
        length_m=120,
        road_metadata={"highway": "residential"},
        provenance=provenance(),
    )
    building = Building(
        building_id="osm-way-1",
        footprint={"type": "Polygon", "coordinates": [[[75.855, 22.7177], [75.856, 22.7177], [75.856, 22.718], [75.855, 22.7177]]]},
        height_m=6,
        height_source="fallback",
        estimated_flag=True,
        provenance=provenance().model_copy(update={"observed_or_estimated": "ESTIMATED"}),
    )
    assert segment.length_m == 120
    assert building.estimated_flag is True
