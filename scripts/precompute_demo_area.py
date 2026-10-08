"""Run OSM acquisition and cache creation outside the web request path."""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.logging_config import configure_logging  # noqa: E402
from app.services.data_engine import CoverageGateError, precompute_demo_area  # noqa: E402


if __name__ == "__main__":
    configure_logging()
    try:
        print(json.dumps(precompute_demo_area(), indent=2))
    except CoverageGateError as exc:
        print(f"COVERAGE GATE FAILED: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
    except RuntimeError as exc:
        print(f"DATA LOAD FAILED: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
