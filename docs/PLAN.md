# HeatShield X: Constrained Implementation Plan

## Planning basis and constraints

This plan implements, and does not redefine, the HeatShield X Master SRS v2.0.
`AGENTS.md` was read in full. Its referenced `docs/PROBLEM.md` and
`docs/PRD.md` are not present in the workspace; this plan therefore treats
`docs/SRS.md` as the available product source of truth.

Non-negotiable constraints retained throughout this plan:

- Build P0 before P1 and P2; do not alter product goals, formulas, labels,
  priorities, or safety boundaries.
- Deterministic engines are the source of truth. The Copilot explains actual
  structured outputs and never overrides them.
- Modelled prioritization is not a medical measurement, diagnosis, individual
  heatstroke prediction, or guaranteed-safety claim.
- Preserve Observed, Estimated, Modelled, and Interpolated status and the
  complete provenance contract on data-bearing records.
- Prefer a reliable, fixed small demo area over fragile city-wide scale; retain
  the SRS fallback behaviour and visibly label it.

## 1. Project understanding and MVP scope

### Product

HeatShield X is a hyperlocal heat-risk, response, and safe-mobility web
platform. It answers where human heat exposure is highest, when it changes,
why it occurs, where scarce heat-response resources should be deployed, what
the **Modelled Impact** is after interventions, and how citizens can select a
route with **Lower modelled heat exposure**.

The core planner workflow is **Map -> Explain -> Simulate -> Optimize -> Act**:
load a selected demonstration area, select a canonical time, inspect
street-level risk and the WHY panel, compare the hottest street with the
highest human-risk street, set resource counts, optimize deployment, and view
the before/modelled-after comparison.

The citizen workflow is **Understand -> Route -> Safe Stop -> Act**: enter an
origin and destination, compare fastest / heat-aware / balanced routes, choose
one, see relevant safe stops, and receive general non-diagnostic heat guidance.

### Priority split

| Priority | Scope from the SRS | Delivery rule |
| --- | --- | --- |
| P0 | Street-level mapping; shadow/exposure engine; five time points; vulnerability; cooling access; risk engine; WHY panel; intervention optimizer; before/after. | Must work and be testable before visual polish or later priorities. |
| P1 | Why-not-the-hottest; heat-aware routing; route comparison; Hindi public view. | Begin only after P0 acceptance passes. |
| P2 | HeatShield Copilot; safe-stop recommendations; sponsored-business concept. | Implement only after P0/P1 are stable and time remains. |
| Future | Real-time weather, satellite validation/ingestion, mobile app, advanced optimization, municipal/commercial platform capabilities. | Do not build in the 36-hour hackathon scope. |

### MVP boundary

The MVP is a fixed, configurable small demonstration area with cached street
and building geometry and five independently cached canonical snapshots:
`09:00`, `11:00`, `13:00`, `15:00`, and `17:00`. Intermediate slider values
may interpolate supported modelled fields only and must be marked Estimated /
Interpolated. The MVP includes elderly and outdoor-worker vulnerability only.

It applies the SRS contracts centrally:

```text
BASELINE_RISK  = EXPOSURE * VULNERABILITY
ACCESS_PENALTY = configurable_function(water distance, cooling distance,
                 facility availability, service radius)
FINAL_RISK_RAW = BASELINE_RISK * (1 + ACCESS_PENALTY)
RISK_SCORE     = deterministic_normalization(FINAL_RISK_RAW, configured scope)
```

Risk classes remain exactly: `0-25 LOW`, `26-50 MODERATE`, `51-75 HIGH`, and
`76-100 CRITICAL`. These are relative/modelled prioritization categories, not
medical thresholds.

## 2. Stack decision

**Decision: proceed with Python + FastAPI + Jinja templates + HTML/CSS/vanilla
JavaScript + Leaflet, subject to the SRS and AGENTS.md constraints.**

This is a permitted implementation choice, not a product or algorithm change:

- The SRS primary stack already specifies Python and includes `Folium/Leaflet`.
  Leaflet is the browser map library; Folium is a Python HTML-generation
  wrapper around Leaflet. Using Leaflet directly gives the production-quality,
  responsive, map-first UI requested without losing map capabilities.
- `AGENTS.md` expressly permits Flask or FastAPI with HTML, CSS, vanilla JS,
  and Jinja templates. FastAPI is suitable for a server-rendered planner/public
  site with focused JSON endpoints for time snapshots, routes, and Copilot.
- Retain the SRS geospatial/data tooling in Python: GeoPandas, OSMnx, Shapely,
  pvlib, Pandas, and NumPy. OR-Tools remains optional and is not needed for the
  deterministic greedy MVP optimizer.
- Do not introduce React, Node, mobile code, microservices, complex cloud
  architecture, or ML.

### Technical risks of this implementation choice

| Risk | Effect | Mitigation |
| --- | --- | --- |
| FastAPI/Leaflet has more UI wiring than Streamlit/Folium | Can consume hackathon time. | Use server-rendered Jinja pages, one shared map module, CSS variables, and narrowly scoped JSON endpoints; avoid a client framework. |
| Browser GeoJSON/map payloads become heavy | Slow map/slider interactions. | Fix a small demo area, simplify serialised geometries where necessary, cache five snapshots, and send only selected-time data. |
| Frontend/backend state drifts | UI could show a time/mode inconsistent with deterministic results. | Make the selected time, configuration version, and computation mode explicit in every snapshot response and visible in the UI. |
| Tile/network availability or CORS issues | Map can fail in a demo. | Test the selected tile source early and provide a documented preloaded/offline-friendly demo-data path; never let map tiles change computed values. |
| Geospatial native dependencies | Setup may be slower than Streamlit-only scaffolding. | Pin tested Python dependencies, document one setup path, and validate the data pipeline in hours 0-4. |

I do **not** disagree with the requested FastAPI + Leaflet stack, so no stack
confirmation is required. If the stack is later changed, approval is required
before doing so.

## 3. Ambiguities and missing inputs

1. Which exact demo area should be fixed for the final build (city, boundary,
   and a suitably small selectable polygon)?
2. What approved source supplies population and demographic data for that area,
   including elderly indicators and any outdoor-worker proxy? If unavailable,
   may the final demo use a documented synthetic/area-level estimate?
3. What is the approved building-height fallback when OSM `height` and
   `building:levels` are absent? The SRS default is two floors at 3 m per floor
   (6 m); confirm whether that default should be used for the selected area.
4. What data source should supply water points, cooling centres, and other
   cooling facilities? Are OSM tags sufficient, or is a municipal/curated
   source available?
5. Which LLM provider, model, credential path, budget, and privacy terms are
   approved for the optional HeatShield Copilot? Is a deterministic disabled
   state acceptable until credentials are available?
6. Which date, timezone, and representative weather/temperature proxy should
   be configured for solar positions and fallback exposure in the demo area?
7. Which map tile provider and attribution treatment are approved for the
   public demo, and must it work without internet connectivity?
8. What is the exact source/licence and freshness expectation for OSM and
   demographic/facility data snapshots to be cited in the UI?
9. Are there known verified heat-safe businesses or shaded public areas for the
   selected area, or should the safe-stop MVP only use source-supported OSM /
   curated facilities?
10. What general heat-safety text is approved for English and Hindi? It must
    remain general guidance and must not diagnose.
11. Are the default intervention inventory examples (2 water points, 1 cooling
    centre, 2 shade structures) the intended initial UI values, while remaining
    editable by the planner?
12. Should the final demo use a preloaded snapshot by default even when a live
    OSM download succeeds, to maximise reproducibility?

## 4. Simple architecture and folder structure

Use a single FastAPI application (a modular monolith), server-rendered Jinja
pages, Leaflet in the browser, and deterministic Python engines. It preserves
the SRS section 76 module boundaries without creating networked microservices.
The only source of coefficients, feature flags, datasets, modes, and versions
is the central configuration layer specified below.

```text
HeatShieldX/
|- docs/
|  |- SRS.md
|  `- PLAN.md
|- app/
|  |- main.py                    # FastAPI app and route registration
|  |- config.py                  # ONE versioned central configuration layer
|  |- contracts.py               # Pydantic data contracts and provenance
|  |- routes/
|  |  |- planner.py              # Planner pages and JSON endpoints
|  |  |- public.py               # Citizen pages and JSON endpoints
|  |  `- copilot.py              # Grounded Copilot endpoint only
|  |- services/
|  |  |- data_engine.py
|  |  |- street_engine.py
|  |  |- building_engine.py
|  |  |- shadow_engine.py
|  |  |- exposure_engine.py
|  |  |- vulnerability_engine.py
|  |  |- cooling_access_engine.py
|  |  |- risk_engine.py
|  |  |- explainability_engine.py
|  |  |- intervention_engine.py
|  |  |- optimizer.py
|  |  |- impact_engine.py
|  |  |- routing_engine.py
|  |  |- stop_finder.py
|  |  `- copilot_service.py
|  |- repositories/
|  |  `- demo_store.py           # Cached/precomputed area data and snapshots
|  |- templates/
|  |  |- planner.html
|  |  `- public.html
|  `- static/
|     |- css/
|     `- js/                      # Leaflet map and small page controllers
|- data/
|  |- raw/                        # Downloaded source snapshots (not secrets)
|  `- processed/                  # Cached derived records/snapshots
|- tests/
|  |- unit/
|  |- geospatial/
|  |- integration/
|  |- e2e/
|  `- fixtures/                   # Fixed small-area test data
|- requirements.txt
|- .env.example
|- .gitignore
`- README.md
```

`app/config.py` is the one versioned configuration object/file. It owns:
`demo_area`, canonical times, building-height values, normalization method and
class ranges, vulnerability weights, water/cooling radii, access-penalty
weights, intervention effects, route weights, feature flags, computation mode,
and data-source metadata. Engines receive this configuration; templates,
JavaScript, and Copilot prompts do not copy any weights. Every output exposes
data snapshot, configuration version, and code version for reproducibility.

## 5. Planned data contracts

The following are **contract sketches for the later implementation**, not an
application implementation in this planning phase. Use Pydantic models for
boundary validation/JSON serialization; internal engines may use GeoPandas and
Shapely geometry while the API serialises GeoJSON-compatible values. All
data-bearing models embed the exact SRS provenance fields.

```python
class Provenance(BaseModel):
    source_type: Literal["osm", "public", "ward_estimate", "synthetic", "derived"]
    source_reference: str
    observed_or_estimated: Literal["OBSERVED", "ESTIMATED"]
    modelled_or_interpolated: Literal["MODELLED", "INTERPOLATED", "NOT_APPLICABLE"]
    timestamp: datetime
    assumptions_version: str
    computation_mode: Literal["FULL", "SIMPLIFIED", "FALLBACK"]

class StreetSegment(BaseModel):
    segment_id: str
    geometry: GeoJSONLineString
    length_m: float = Field(ge=0)
    road_metadata: dict[str, str | int | float | bool | None]
    building_context: list[str]
    risk_snapshot_ids: list[str]
    provenance: Provenance

class Building(BaseModel):
    building_id: str
    footprint: GeoJSONPolygon
    height_m: float = Field(gt=0)
    height_source: Literal["actual", "levels", "fallback"]
    estimated_flag: bool
    levels: int | None = Field(default=None, ge=1)
    provenance: Provenance

class RiskRecord(BaseModel):
    risk_record_id: str
    segment_id: str
    snapshot_time: time
    shade_fraction: float = Field(ge=0, le=1)
    direct_exposure_fraction: float = Field(ge=0, le=1)
    exposure_value: float = Field(ge=0, le=1)
    elderly_component: float = Field(ge=0)
    outdoor_worker_component: float = Field(ge=0)
    vulnerability_value: float = Field(ge=0)
    distance_to_water_m: float | None = Field(default=None, ge=0)
    distance_to_cooling_m: float | None = Field(default=None, ge=0)
    access_penalty: float = Field(ge=0)
    baseline_risk: float = Field(ge=0)
    final_risk_raw: float = Field(ge=0)
    risk_score: float = Field(ge=0, le=100)
    risk_class: Literal["LOW", "MODERATE", "HIGH", "CRITICAL"]
    driver_ids: list[str]
    provenance: Provenance

class Route(BaseModel):
    route_id: str
    route_classification: Literal["FASTEST", "HEAT-AWARE", "BALANCED"]
    geometry: GeoJSONLineString
    segment_ids: list[str]
    total_time_s: float = Field(ge=0)
    total_distance_m: float = Field(ge=0)
    modelled_heat_exposure: float = Field(ge=0)
    average_or_weighted_shade: float = Field(ge=0, le=1)
    cooling_access: float = Field(ge=0)
    snapshot_time: time
    provenance: Provenance

class SafeStop(BaseModel):
    stop_id: str
    stop_type: Literal["water", "cooling", "shaded_public", "business"]
    name: str | None
    location: GeoJSONPoint
    route_distance_m: float = Field(ge=0)
    detour_distance_m: float = Field(ge=0)
    verified_status: bool
    amenities: list[str]
    rating: float | None = Field(default=None, ge=0)
    sponsored_status: bool
    route_relevance: float
    provenance: Provenance
```

Additional contract rules to preserve:

- A building uses the ordered hierarchy actual height -> levels x configured
  metres-per-floor -> configured fallback floors x metres-per-floor; any
  non-observed height sets `estimated_flag=True`.
- `RiskRecord` values are deterministic modelled prioritization values. The
  normalization method is selected once in config; the default is min-max on
  the selected scope with `50` when `max_raw == min_raw`, clipped to `[0,100]`.
- `Route` is generated from the same segment graph and cached exposure
  snapshots used for risk. The Balanced objective remains configurable
  `alpha * normalized_time + beta * normalized_heat_exposure`.
- `SafeStop` fields are source-supported only. No rating, amenity, or
  verification may be invented. Sponsorship never bypasses the safety/relevance
  filter and is visibly labelled.

## 6. API and page route list

All routes validate input, return actionable errors, and include provenance /
computation mode where a response contains model outputs. Exact endpoint
shapes remain internal details; the deterministic engine contracts are the
source of truth.

| Surface | Route | Methods | Purpose |
| --- | --- | --- | --- |
| Planner | `/planner` | GET | Server-rendered map-first planner dashboard. |
| Planner | `/api/planner/area` | GET | Fixed demo-area metadata, available data sources, and active configuration/mode. |
| Planner | `/api/planner/snapshots/{time}` | GET | Cached or permitted interpolated street risk/exposure map snapshot. |
| Planner | `/api/planner/segments/{segment_id}` | GET | Selected street risk, drivers, vulnerability, cooling access, and provenance for WHY. |
| Planner | `/api/planner/compare/hottest` | GET | Hottest versus highest-human-risk comparison from computed records. |
| Planner | `/api/planner/interventions/candidates` | GET | Actual feasible intervention candidates. |
| Planner | `/api/planner/optimize` | POST | Validate resource constraints; produce deterministic `ResourcePlan`. |
| Planner | `/api/planner/impact` | POST | Return before versus **Modelled Impact** after using the same config/scope. |
| Citizen | `/public` | GET | Server-rendered English/Hindi citizen view. |
| Citizen | `/api/public/routes` | POST | Validate origin/destination; generate FASTEST, HEAT-AWARE, and BALANCED route comparisons. |
| Citizen | `/api/public/routes/{route_id}/stops` | GET | Source-supported safe stops relevant to the selected actual route. |
| Citizen | `/api/public/guidance` | GET | Approved general, non-diagnostic heat guidance in English/Hindi. |
| Copilot | `/api/copilot/chat` | POST | Intent -> structured retrieval/engine -> facts/assumptions -> LLM -> safety/fact gate. |
| Copilot | `/api/copilot/context` | GET | Visible selected entity/context used by the grounded conversation. |
| Platform | `/health` | GET | Liveness/readiness, active computation mode, and non-sensitive data availability. |

The Copilot route returns **"Data unavailable for this area."** when required
facts are absent. It does not calculate independent scores, routes, distances,
ratings, or impact.

## 7. Development phases: 36-hour delivery schedule

This sequence follows SRS section 43, P0/P1/P2 ordering, the mandatory
12-hour shadow checkpoint, and the final two-hour feature freeze.

| Hours | Priority | Reviewable result and gate |
| --- | --- | --- |
| 0-4 | P0 | Skeleton, central config, fixed demo-area setup, OSM/preloaded-data path, basic Leaflet map, street/building extraction. Gate: OSM failure displays an actionable error and preloaded demo mode works when configured. |
| 4-8 | P0 | Building-height hierarchy, projected CRS policy, one-building shadow test, solar-position and expected-direction validation. Gate: height estimates/provenance and geospatial unit tests pass. |
| 8-12 | P0 | Multiple-building shadows, street intersections, five canonical timestamps, exposure calculation/caching. **Hard checkpoint:** reliable geometric results -> `FULL`; otherwise activate `SIMPLIFIED` if prepared or `FALLBACK` (temperature proxy x static shade factor x exposure duration), display **Estimated Exposure Mode**, and keep the slider functional. |
| 12-20 | P0 | Vulnerability, cooling access, risk pipeline, map snapshot endpoint, time slider, WHY panel, and provenance/status display. Gate: P0 data/risk/dashboard acceptance checks pass in the active mode. |
| 20-27 | P0 | Intervention candidates, editable resource limits, deterministic greedy optimizer, and same-pipeline before/**Modelled Impact** after. Gate: P0 optimization checks and constraint tests pass. |
| 27-31 | P1 | Why-not-the-hottest, graph routing, FASTEST/HEAT-AWARE/BALANCED comparison, and safe-stop logic using actual data. Gate: P1 route comparison checks pass without fabricated routes/stops. |
| 31-34 | P1 then P2 | Hindi public view (P1); only if stable, grounded Copilot and optional labelled sponsored flag (P2); UI/accessibility polish. Gate: Copilot grounding tests block unavailable facts. |
| 34-36 | Freeze | **No new features.** Fix defects, run the full suite, rehearse the 3-minute narrative, prepare PPT and screenshots/video/demo-data backup. Gate: end-to-end fixed-area demo completes without hidden manual steps. |

## 8. Prompt-by-prompt implementation plan

Each later build prompt is one reviewable phase and must end with
implemented/tested/failed/assumptions/blockers reporting. Never proceed past a
failed gate without fixing it or explicitly activating the SRS fallback.

| Prompt / phase | Scope | Tests and acceptance evidence |
| --- | --- | --- |
| 1. Foundation and data loading | App skeleton, one central config, fixed demo area, data acquisition/preload, base planner map. | SRS 42 Data: OSM streets and footprints load; height-source fields exist. SRS 74: OSM-unavailable path is actionable and preloaded mode works. |
| 2. Geometry and shadow validation | CRS selection, height hierarchy, solar position, one-building then multiple-building shadow/intersection engine. | SRS 12 / 42 Shadow: one-building test, known timestamp/direction, nearby-street intersection, multiple buildings, five time points. Geospatial CRS/validity tests pass. |
| 3. Exposure checkpoint | Exposure records/cache for canonical times, time interpolation labels, computation-mode UI. | SRS 60-61 cache/monotonicity/bounds tests. At hour 12 record PASS or activate fallback; SRS 85 Reliability requires visible fallback and a working slider. |
| 4. Risk and explainability | Vulnerability, cooling access, centralized normalization, risk records, risk map, slider, WHY. | SRS 42 Risk/Dashboard: exposure, vulnerability, cooling, score, map, slider, WHY. SRS 85 Explainability uses actual computed data; provenance contract tests pass. |
| 5. Intervention and impact | Candidates, constraints, deterministic greedy selection, same-pipeline comparison. | SRS 42 Optimization: resource counts, candidates, deployment, before/after. Unit tests cover effects, marginal benefits, constraints, no hardcoded impact; SRS 85 Planning passes. |
| 6. Citizen mobility | Why-not-hottest, routing graph, actual route alternatives, metrics, safe stops, Hindi public view. | SRS 42 Routing: origin/destination, multiple routes, heat exposure. SRS 69 route-scoring tests; SRS 85 Mobility/Public view checks; no fabricated route/stop data. |
| 7. Grounded Copilot and polish | Structured retrieval/tool pipeline, fact/safety gate, selected-context display, responsive accessible UI. | SRS 42 Copilot: platform/risk/route explanations and no invention. SRS 71-72 tests cover existing and intentionally missing facts; SRS 85 blocks hallucination cases. |
| 8. Freeze and demo | Regression, failure modes, reproducibility, observability, demo rehearsal and backup. | SRS 77 unit/geospatial/integration/fallback/E2E/UI smoke suite; SRS 85 full definition of done; 3-minute SRS 51 narrative works without hidden manual steps. |

## 9. Top technical risks and mitigations

| Risk | Mitigation and required behaviour |
| --- | --- |
| OSM download is unavailable, rate-limited, incomplete, or licence metadata is missing | Attempt acquisition early; record source/attribution; show actionable load error; use a configured preloaded fixed demo dataset when available. Never silently manufacture inputs. |
| Shadow geometry is wrong because of geographic CRS, solar direction, invalid polygons, or performance | Reproject to a suitable local projected CRS before metres/intersections; validate one building, timestamp, direction, street intersection, then multiple buildings; repair/skip invalid geometry with a logged reason. Enforce the 12-hour pass/fallback decision. |
| Full shadow processing is too slow or unreliable | Cache geometry and five canonical snapshots. Use Level 1 Full, Level 2 Simplified precomputed exposure, or Level 3 Fallback exactly as defined. Clearly show **Estimated Exposure Mode** for fallback and do not conceal the failure. |
| Routing graph is disconnected or route metrics conflict with risk data | Build routing from the same street-segment graph and cached exposure snapshots; validate origin/destination snapping; show a route-generation error rather than inventing a route; test FASTEST/HEAT-AWARE/BALANCED scoring. |
| Demographic, height, or facility coverage is incomplete | Apply only the SRS source hierarchy; set estimated flags/provenance; document spatial assumptions; use unavailable coverage in access calculations rather than inventing facilities; never present precise street-level demographics as fact. |
| Copilot hallucinates or becomes an alternate decision engine | Retrieve actual structured records, call deterministic tools, include facts and assumptions in context, apply post-generation fact/safety gate, return **"Data unavailable for this area."** when facts are missing, and disable gracefully if the API is unavailable. |
| Configuration/weight drift changes results between engines or UI | One versioned config file only; include configuration version in records/logs; do not copy weights into JavaScript, templates, or prompts; regression-test deterministic outputs. |
| Demo failure due to network or late feature additions | Keep precomputed assets/snapshots and screenshots/video backup; feature freeze at hour 34; final two hours only test, fix, rehearse, and package evidence. |

## 10. Explicitly out of scope

The following are excluded for the 36-hour build unless the SRS is formally
revised:

- Individual heatstroke prediction, medical diagnosis, scientifically validated
  medical thresholds, or guaranteed safety/intervention claims.
- Fake demographic precision, hardcoded intervention impact, fake route data,
  invented ratings/amenities, or sponsorship overriding safety/relevance.
- Unnecessary ML or an LLM as the calculation/routing/optimization source of
  truth.
- A complete native mobile application.
- Live satellite-ingestion pipeline; real-time weather, satellite LST,
  sensors, historical analysis, and advanced optimization belong to later
  roadmap phases.
- A full navigation product comparable to Google Maps.
- Payments, ad auctions, merchant billing, or a full sponsored-business
  marketplace. A clearly labelled sponsored flag may be demonstrated only if
  P0/P1 are stable and it never changes core relevance/safety ranking.
- Large cloud/microservice architecture, React/Node, and broad platform
  expansion not required by the SRS.
- Extra vulnerability groups beyond elderly and outdoor workers in the MVP.
- Any new feature during hours 34-36.

## Pre-implementation decisions needed

Before implementation, resolve at least the demo-area/data-source choices in
Section 3 and the Copilot provider decision. Until then, use no unapproved
facts and do not begin application-code implementation.
