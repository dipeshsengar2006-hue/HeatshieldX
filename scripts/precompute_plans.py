"""Precompute the deterministic resource-plan presets used in the planner demo."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.intervention_engine import optimize_resources


PRESETS = (
    {"water_points": 2, "cooling_centres": 1, "shade_structures": 2},
    {"water_points": 1, "cooling_centres": 1, "shade_structures": 1},
    {"water_points": 3, "cooling_centres": 2, "shade_structures": 3},
    {"water_points": 4, "cooling_centres": 2, "shade_structures": 4},
)


def main() -> None:
    for resources in PRESETS:
        plan = optimize_resources(resources)
        print(f"{plan['plan_id']}: {plan['runtime_seconds']:.3f}s")


if __name__ == "__main__":
    main()
