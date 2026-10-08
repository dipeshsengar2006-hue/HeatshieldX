from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.routes import planner


@pytest.fixture
def preloaded_api(monkeypatch):
    street = {"type": "FeatureCollection", "features": [{"type": "Feature", "properties": {"segment_id": "osm-1-2-0"}, "geometry": {"type": "LineString", "coordinates": [[75.855, 22.7177], [75.856, 22.718]]}}]}
    building = {"type": "FeatureCollection", "features": [{"type": "Feature", "properties": {"building_id": "osm-way-1"}, "geometry": {"type": "Polygon", "coordinates": [[[75.855, 22.7177], [75.8551, 22.7177], [75.8551, 22.7178], [75.855, 22.7177]]]}}]}
    facility = {"type": "FeatureCollection", "features": []}
    datasets = {"streets": street, "buildings": building, "facilities": facility}

    def load(name):
        if name not in datasets:
            raise FileNotFoundError("Preloaded data unavailable. Run `python scripts/precompute_demo_area.py`.")
        return datasets[name]

    monkeypatch.setattr(planner, "load_cached_geojson", load)
    monkeypatch.setattr(planner, "cache_status", lambda config=None: {"streets": "streets" in datasets, "buildings": "buildings" in datasets, "facilities": "facilities" in datasets})
    return datasets


@pytest.fixture
def client(preloaded_api):
    return TestClient(app)
