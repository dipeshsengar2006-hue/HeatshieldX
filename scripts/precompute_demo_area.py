"""Run OSM acquisition and cache creation outside the web request path."""

from __future__ import annotations

import json
import sys
from argparse import ArgumentParser
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.logging_config import configure_logging  # noqa: E402
from app.services.data_engine import (  # noqa: E402
    CoverageGateError,
    build_overpass_query,
    facility_query_tags,
    overpass_browser_url,
    precompute_demo_area,
    precompute_facilities,
    precompute_stops,
    stop_overpass_query,
)
from app.config import get_config  # noqa: E402


if __name__ == "__main__":
    parser = ArgumentParser(description="Precompute the HeatShield X cached OSM data.")
    refresh = parser.add_mutually_exclusive_group()
    refresh.add_argument("--stops-only", action="store_true", help="Refresh only data/cache/stops.geojson from Overpass.")
    refresh.add_argument("--facilities-only", action="store_true", help="Refresh only data/cache/facilities.geojson from Overpass.")
    parser.add_argument("--print-query", action="store_true", help="Print the Overpass QL query and browser URL without downloading data.")
    arguments = parser.parse_args()
    configure_logging()
    if arguments.print_query:
        query = build_overpass_query(facility_query_tags(get_config()), get_config()) if arguments.facilities_only else stop_overpass_query()
        print(query)
        print(f"\nBrowser URL:\n{overpass_browser_url(query)}")
        raise SystemExit(0)
    try:
        result = precompute_stops() if arguments.stops_only else precompute_facilities() if arguments.facilities_only else precompute_demo_area()
        print(json.dumps(result, indent=2))
    except CoverageGateError as exc:
        print(f"COVERAGE GATE FAILED: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
    except RuntimeError as exc:
        print(f"DATA LOAD FAILED: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
