"""Create cache-only geometric shadow validation snapshots for the demo area."""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.logging_config import configure_logging  # noqa: E402
from app.services.shadow_engine import precompute_shadows  # noqa: E402


if __name__ == "__main__":
    configure_logging()
    try:
        print(json.dumps(precompute_shadows(), indent=2))
    except FileNotFoundError as exc:
        print(f"SHADOW PRECOMPUTE FAILED: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
