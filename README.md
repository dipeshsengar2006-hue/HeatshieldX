# HeatShield X

HeatShield X is a constrained, cache-first hyperlocal heat-response prototype.
Prompt 1 provides the FastAPI planner shell and OSM precompute pipeline only;
it does not calculate risk, shadows, routes, or intervention effects.

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

## Download and precompute the demo area

Run while OpenStreetMap/Overpass is reachable. This validates Rajwada-Sarafa
building coverage, saves raw OSM inputs to `data/raw/`, and writes API-ready
cached GeoJSON to `data/cache/`.

```powershell
python scripts/precompute_demo_area.py
```

If the coverage gate fails, stop and select another dense approximately 1 km2
Indore area explicitly; do not silently change configuration.

## Precompute geometric shadow validation snapshots

After Prompt 1 cache data is present, calculate and cache the five geometric
shadow-validation snapshots. This uses the configured 2026-05-15 date and
Asia/Kolkata timezone; it does not run during web requests.

```powershell
python scripts/precompute_shadows.py
```

## Run locally

```powershell
python -m uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000/`. The app serves precomputed files only. If no
cache is present, it displays an actionable precompute instruction.

## Test

```powershell
python -m pytest
```
