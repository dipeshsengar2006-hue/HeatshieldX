"""Run OSM acquisition and cache creation outside the web request path."""

from __future__ import annotations

import json
import sys
from argparse import ArgumentParser
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.logging_config import configure_logging  # noqa: E402
from app.services.data_engine import CoverageGateError, precompute_demo_area, precompute_stops  # noqa: E402


if __name__ == "__main__":
    parser = ArgumentParser(description="Precompute the HeatShield X cached OSM data.")
    parser.add_argument("--stops-only", action="store_true", help="Refresh only data/cache/stops.geojson from OSM.")
    arguments = parser.parse_args()
    configure_logging()
    try:
        result = precompute_stops() if arguments.stops_only else precompute_demo_area()
        print(json.dumps(result, indent=2))
    except CoverageGateError as exc:
        print(f"COVERAGE GATE FAILED: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
    except RuntimeError as exc:
        print(f"DATA LOAD FAILED: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
