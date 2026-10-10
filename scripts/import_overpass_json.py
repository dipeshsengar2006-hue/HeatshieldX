"""Import a manually saved Overpass JSON response into the safe-stop cache."""

from __future__ import annotations

import json
import sys
from argparse import ArgumentParser
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.logging_config import configure_logging  # noqa: E402
from app.services.data_engine import import_overpass_stops  # noqa: E402


if __name__ == "__main__":
    parser = ArgumentParser(description="Import a saved Overpass JSON response as HeatShield X safe stops.")
    parser.add_argument("file", type=Path, help="Saved Overpass JSON response")
    arguments = parser.parse_args()
    configure_logging()
    try:
        print(json.dumps(import_overpass_stops(arguments.file), indent=2))
    except ValueError as exc:
        print(f"IMPORT FAILED: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
