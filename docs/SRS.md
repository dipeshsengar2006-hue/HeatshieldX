# HEATSHIELD X — Master SRS v2.0
**Hyperlocal Heat Risk, Response & Safe Mobility Platform**
AI-Implementation-Grade • Hackathon Build • 36 hours • Web application

- **Source of truth:** HeatShield X PRD / Build Specification (user-supplied)
- **Primary problem:** Heat-Risk Mapping at Human Scale
- **Primary stack (per SRS):** Python, GeoPandas, OSMnx, Shapely, pvlib, Pandas, NumPy, Streamlit, Folium/Leaflet, Plotly. Optional: OR-Tools; LLM API for HeatShield Copilot.
- **Primary users:** Urban planners, disaster-management authorities, citizens
- **Core principle:** Algorithm decides. AI explains.
- **Note:** Implementation contracts below are configurable prototype assumptions. They are NOT a scientifically validated heat-health model.

---

# PART I — PRODUCT DEFINITION AND SCOPE

## 1. Executive Summary
HeatShield X moves beyond city-level heatwave warnings. It estimates which streets are most exposed, at what time, who is most vulnerable, why a street is risky, where limited interventions should be deployed, and how citizens can choose lower-heat routes.

It combines: OpenStreetMap street and building data; building geometry and estimated heights; solar-position-based shadow analysis; time-dependent street exposure; vulnerable-population estimates; cooling/water accessibility; explainable risk scoring; resource-constrained intervention optimization; heat-aware routing; citizen-facing recommendations; an optional AI assistant called HeatShield Copilot.

Philosophy: **Map → Explain → Simulate → Optimize → Act**

## 2. Problem Statement
Heatwaves affect urban areas unevenly. A city-wide forecast does not distinguish between: a shaded vs an exposed street; a green vs a highly paved area; a low-vulnerability area vs an area with many elderly/outdoor workers; a street near cooling/water facilities vs one far away.

Authorities have limited resources (e.g. 2 water points, 1 cooling centre, 2 temporary shade structures).

Key question 1: Where should limited heat-response resources be deployed first to protect the greatest amount of vulnerable human exposure?
Key question 2 (citizens): If a person must travel through a heatwave-affected area, which route exposes them to less modelled heat?

## 3. Product Vision
Transform heatwave information from a static hazard map into an actionable decision-support platform.
- Authorities: Identify → Explain → Prioritize → Optimize → Measure
- Citizens: Understand → Route → Find safe stops → Act

## 4. Product Goals
**Primary:** (1) Calculate street-level heat exposure. (2) Make exposure time-dependent. (3) Estimate human vulnerability at street level. (4) Incorporate cooling/water accessibility. (5) Produce an explainable heat-risk score. (6) Identify priority streets. (7) Optimize limited intervention resources. (8) Show modelled before/after impact. (9) Provide heat-aware route alternatives. (10) Provide a citizen-friendly interface. (11) Provide an AI assistant that explains and operates the platform.

**Secondary:** (1) Demonstrate practical urban heat-response planning. (2) Show transparent assumptions. (3) Demonstrate future commercialization through verified/sponsored heat-safe stops. (4) Provide a foundation for real-time weather and better datasets.

## 5. Non-Goals
The 36-hour prototype will NOT: predict individual heatstroke; provide medical diagnosis; provide scientifically validated medical risk thresholds; build a complete mobile app; build real-time satellite ingestion; build a full advertising marketplace; implement complex ML models; build a full navigation product comparable to Google Maps; guarantee an intervention produces a specific real-world temperature reduction; claim scientifically validated intervention effectiveness.

## 6. Target Users
- **6.1 Urban Planner / Municipality:** Which streets need intervention first? Why? Which intervention? What can we achieve with limited resources?
- **6.2 Disaster Management Authority:** Which vulnerable areas should receive emergency resources during a heatwave?
- **6.3 Citizen:** Is my route currently exposed? Can I take a lower-heat route? Where can I find water or cooling? When should I travel?
- **6.4 Business / Commercial Partner (future):** Can my verified heat-safe location become a useful cooling stop? Sponsored placements must be clearly labelled.

## 7. Core Product Modules
1 Data Engine; 2 Street Segmentation Engine; 3 Shadow & Solar Exposure Engine; 4 Vulnerability Engine; 5 Cooling Access Engine; 6 Heat-Risk Engine; 7 Explainability / Why Panel; 8 Priority Intervention Engine; 9 Resource Optimization Engine; 10 Before/After Impact Engine; 11 Heat-Aware Routing Engine; 12 Heat-Safe Stop Finder; 13 Citizen Public View; 14 HeatShield Copilot; 15 Planner Dashboard.

## 8. System Architecture
Data flow: Open data (OSM, population data) → Data processing → Street/Building model → Shadow engine → Exposure engine → Vulnerability engine → Cooling access engine → Risk engine → splits into:
- **Planner system:** Priority action → Resource optimizer → Before/After
- **Citizen system:** Heat-aware route → Safe stop finder → Public view
- Both feed → **HeatShield Copilot**

---

# PART II — FUNCTIONAL SPECIFICATION

## 9. Data Requirements
### 9.1 Required Data (OpenStreetMap via OSMnx)
Road network, street geometry, building footprints, building levels where available, amenities, water points where available, cooling-related facilities where available.

### 9.2 Building Height
Priority: (1) actual building height if available; (2) building levels if available; (3) estimated height.
Fallback: Estimated Height = Building Levels × 3 metres. Default if levels unavailable: 2 floors × 3 m = 6 m.
Every estimated value must be internally flagged as estimated.

### 9.3 Population Data
If street-level population data is unavailable: obtain ward-level population/demographic information, distribute spatially using transparent assumptions, clearly label as an estimate. Do not claim exact street-level demographic accuracy.

## 10. Shadow & Solar Exposure Engine
Estimate how much of each street segment is exposed to direct sunlight at different times.
Timestamps: 09:00, 11:00, 13:00, 15:00, 17:00.
Uses solar-position calculations and building geometry. Recommended: pvlib; geometry via Shapely / GeoPandas.

## 11. Shadow Engine Processing
For each timestamp: Building geometry → Building height → Solar position → Shadow geometry → Intersect shadow with street → Calculate shade fraction → Calculate exposure fraction.
Exposure Fraction = 1 − Shade Fraction.
Preserve the spatial relationship between streets and nearby building shadows.

## 12. Shadow Engine Validation
Before processing the full area: Test 1 one building; Test 2 known timestamp; Test 3 known/expected shadow direction; Test 4 intersection with a nearby street; Test 5 multiple buildings. Only then process the complete street network.

## 13. 12-Hour Technical Checkpoint
At ~12 hours:
- **PASS** (shadow engine reliable): continue with geometric exposure.
- **FAIL:** switch to fallback exposure mode: Hourly Temperature Proxy × Static Shade Factor × Exposure Duration. Time slider remains functional. UI must clearly show **"Estimated Exposure Mode"**. The fallback must never pretend to be geometric shadow simulation.

## 14. Time Slider
Slider from 09:00 to 17:00. Primary values at 09, 11, 13, 15, 17. Intermediate values may be interpolated and must be labelled internally as estimates.

## 15. Exposure Engine
Per street segment. Inputs: shade fraction, direct exposure fraction, time, street length, exposure duration, relevant environmental variables. Output: normalized exposure value (e.g. Street A = 0.82, Street B = 0.41). Used for prioritization, not as a medical measurement.

## 16. Vulnerability Engine
MVP groups: **Elderly** (estimated from available demographic information) and **Outdoor Workers** (estimated where reliable street-level info is unavailable). All estimates clearly labelled.
Future (excluded from MVP): children, people with disabilities, medically vulnerable groups, commuters, others.

## 17. Heat-Risk Engine
Baseline Risk = Heat Exposure × Vulnerability. Normalized to a 0–100 prioritization score.

## 18. Cooling Access
A modifier, not a direct multiplier with exposure. Inputs: walking distance to cooling centre, walking distance to water point, facility availability, service radius.
Access Penalty = f(distance, accessibility). Final Risk = Baseline Risk × (1 + Access Penalty). Coefficients configurable and documented as prototype assumptions.

## 19. Risk Classification
0–25 LOW; 26–50 MODERATE; 51–75 HIGH; 76–100 CRITICAL. Relative/modelled categories, NOT medical thresholds.

## 20. Interactive Risk Map
Main planner dashboard shows: street segments, risk level, selected time, vulnerable exposure, cooling access, intervention priority. The map must update when the time slider changes.

## 21. WHY Panel
When a user selects a street, show e.g.: Street S-27; Risk 87/100; Solar Exposure HIGH; Shade LOW; Vulnerability HIGH; Cooling Access POOR. Identify dominant risk drivers, e.g. "Low afternoon shade, high estimated vulnerable exposure and poor cooling accessibility."

## 22. "Why Not the Hottest?" Feature
Compare the hottest street versus the highest human-risk street, showing exposure, vulnerable population, cooling access, final priority. Purpose: show HeatShield X prioritizes human impact, not temperature alone.

## 23. Intervention Types (MVP)
1. **Water Point** — maximize vulnerable population coverage.
2. **Cooling Centre** — maximize vulnerable population coverage within acceptable walking distance.
3. **Shade Structure** — reduce estimated heat exposure on high-impact street segments.

## 24. Resource Constraints
Planner can define e.g. Water Points: 2, Cooling Centres: 1, Shade Structures: 2. The system must respect these constraints.

## 25. Optimization Engine
Objective: maximize estimated reduction in vulnerable heat exposure under resource constraints. MVP: greedy is acceptable; OR-Tools only if stable and time permits.
Output: Priority 1 → Location A → Cooling Centre; Priority 2 → Location B → Water Point; Priority 3 → Location C → Shade Structure; ...

## 26. Before/After Engine
Recalculate the model after interventions. Metrics: vulnerable exposure, high-risk population exposure, average walking distance, cooling coverage, intervention coverage. Show Before vs After for each (e.g. coverage X% → Y%, avg cooling distance X m → Y m). All results labelled **Modelled Impact**. No hardcoded impact numbers.

## 27. Heat-Aware Routing
Citizen selects Origin → Destination. Multiple route options:
- Route A: Fastest
- Route B: Lower modelled heat exposure
- Route C: Balanced
Example: FASTEST 18 min, high exposure; HEAT-AWARE 22 min, lower modelled exposure; BALANCED 20 min, moderate exposure.

## 28. Route Scoring
Route Heat Exposure = sum of street-segment exposure weighted by route length/time. Compare: travel time, exposure, shade, cooling access. User can choose the preferred trade-off.

## 29. Route Recommendation
Example: "Recommended heat-aware route: adds approximately 4 minutes but has lower modelled heat exposure." Never claim "This route prevents heatstroke." Use "Lower modelled heat exposure."

## 30. Heat-Safe Stop Finder
Along a selected route identify: water points, cooling centres, shaded public areas, verified heat-safe businesses, cafes/restaurants with relevant amenities. Criteria: distance from route, detour distance, rating, verified amenities, cooling characteristics, relevance to current route.

## 31. Commercialization Layer (future)
Sponsored Heat-Safe Stops: sponsored placement, promoted heat-safe stop, heatwave campaign, verified cooling amenity listing. Sponsored results must be clearly labelled; sponsorship must not override core safety/relevance filters.

## 32. HeatShield Copilot
The conversational AI layer. NOT the core calculation engine. Core engines calculate risk, exposure, routing, optimization. The Copilot explains, guides, retrieves, recommends, assists. Principle: **Algorithm decides. AI explains.**

## 33. Copilot Feature Set
- 33.1 Platform Guide: how to use the map, what the time slider means, what the risk score is, how to compare streets, generate an action plan, find a lower-exposure route.
- 33.2 Risk Explanation: "Why is this street high risk?" → explains actual model outputs.
- 33.3 Route Assistant: user says "A se B jaana hai." → retrieves route results, explains fastest / lower-exposure / balanced and trade-offs.
- 33.4 Safe Stop Assistant: "Mujhe raste mein break lena hai." → finds relevant stops.
- 33.5 Planner Assistant: "Mere paas 2 water points aur 1 cooling centre hain." → explains optimizer's recommended deployment.
- 33.6 Data Transparency Assistant: "Building height kaise estimate hui?" → explains assumptions.
- 33.7 Heat Safety Assistant: general heat-safety guidance; must not diagnose.

## 34. Copilot Knowledge Boundary
Must not invent: risk scores, route times, facility distances, business ratings, intervention impact, scientific claims. If unavailable: **"Data unavailable for this area."**

## 35. Public View
Simplified citizen interface. Example: HIGH HEAT EXPOSURE, 12 PM – 4 PM; Exposure: High; Water: 300 m; Cooling Centre: 650 m; Lower-exposure route available. Languages: **English and Hindi**.

## 36. Planner Dashboard
Sections: Map (street risk visualization); Time (slider); Risk (score and categories); Why (risk-driver breakdown); Compare (why-not-the-hottest); Resources (available interventions); Optimize (priority action plan); Before/After (modelled impact).

## 37. User Flow — Planner
Open Dashboard → Select Area → Select Time → View Risk Map → Click Street → View WHY → Compare Priority → Set Available Resources → Run Optimization → View Recommended Deployment → View Before/After.

## 38. User Flow — Citizen
Open Public View → Enter Origin → Enter Destination → View Route Options → Compare Heat Exposure → Select Route → View Safe Stops → Get Heat Guidance.

## 39. User Flow — Copilot
Ask Question → Identify Intent → Retrieve Actual System Data → Call Relevant Engine → Generate Explanation → Answer User.

## 40. UI Requirements
Map-first experience; minimal clutter; clear risk categories; visible time slider; one-click explanations; clear before/after comparison; simple route comparison; prominent Copilot button. Avoid excessive dashboard cards.

## 41. Performance Requirements
Precompute expensive GIS calculations. Cache street geometry, building geometry, and the five primary time points. Do not recalculate the entire city on every slider movement. Use a small demonstration area if necessary. Prioritize demo reliability over city-wide scale.

## 42. MVP Acceptance Criteria
- **Data:** OSM streets load; building footprints load; height estimates work.
- **Shadow:** one-building test works; shadow direction validated; multiple buildings process; five time points calculate.
- **Risk:** street exposure calculates; vulnerability estimate loads; cooling access calculates; risk score generates.
- **Dashboard:** risk map works; time slider works; Why panel works; Why-not-hottest comparison works.
- **Optimization:** resource limits can be entered; candidate interventions generated; priority deployment generated; before/after calculated.
- **Routing:** origin/destination works; multiple routes compared; heat exposure calculated for routes.
- **Copilot:** explains the platform; explains selected risk; explains route results; does not invent unavailable data.

## 43. 36-Hour Development Plan
- Hours 0–4: project skeleton, OSM download, basic map, street extraction, building extraction.
- Hours 4–8: building heights, coordinate systems, one-building shadow test, solar-position validation.
- Hours 8–12: multiple-building shadows, street intersections, five timestamps, exposure calculation. **HARD CHECKPOINT:** if shadow engine fails, switch to fallback mode.
- Hours 12–20: vulnerability, cooling access, risk engine, risk map, Why panel, time slider.
- Hours 20–27: intervention candidates, resource constraints, optimization, before/after.
- Hours 27–31: heat-aware routing, route comparison, safe-stop logic.
- Hours 31–34: HeatShield Copilot, Hindi public view, UI polish.
- Hours 34–36: NO new features. Only bug fixes, testing, demo rehearsal, PPT, backup demo, screenshots/video backup.

## 44. Technical Fallback Strategy
Three reliability levels: **Level 1 Full** (geometric shadow engine); **Level 2 Simplified** (precomputed shadow/exposure values); **Level 3 Fallback** (temperature curve × static shade factor). The UI must clearly communicate which mode is active.

## 45. Core Assumptions
The prototype may use: estimated building heights, estimated vulnerable population, configurable risk weights, estimated cooling-access penalties, modelled intervention effects, synthetic data where public data is unavailable. Every assumption must be documented.

## 46. Transparency Principle
Always distinguish: **Observed** (actual source data); **Estimated** (derived from assumptions); **Modelled** (calculated by the system); **Interpolated** (estimated between computed timestamps). Core product principle.

## 47. Security & Safety
Avoid collecting unnecessary personal information; avoid medical diagnosis; avoid claiming guaranteed safety; clearly disclose model limitations; clearly disclose sponsored recommendations; avoid presenting estimated demographic data as exact.

## 48. Future Roadmap
- Phase 2: real-time weather, improved population datasets, more vulnerability groups, better building-height datasets, improved routing, real-time heat alerts.
- Phase 3: satellite LST integration, sensor integration, historical heatwave analysis, advanced optimization, mobile app.
- Phase 4: municipal deployment, verified cooling network, business partnership network, sponsored heat-safe stops, analytics and reporting.

## 49. Competitive Differentiation
Do NOT claim "Nobody has ever mapped heat risk." Instead: "Existing heat-risk mapping tells us where heat risk exists. HeatShield X connects time-aware street exposure, human vulnerability, cooling access, constrained intervention optimization, and citizen heat-aware mobility into one decision workflow."

## 50. Core Innovation (decision loop)
WHERE? → WHEN? → WHO? → WHY? → WHAT INTERVENTION? → WITH WHAT LIMITED RESOURCES? → WHAT MODELLED CHANGE? → HOW SHOULD PEOPLE MOVE?

## 51. Winning Demo Narrative (3 minutes)
1. Show city heat map: "A city-wide heat warning doesn't tell us which street needs help first."
2. Zoom to streets.
3. Move time 9 AM → 1 PM → 5 PM, show changing exposure.
4. Click high-risk street, show WHY panel.
5. Click "Why not the hottest?", show human-risk comparison.
6. Set 2 water points, 1 cooling centre, 2 shade structures.
7. Click "Optimize Response".
8. Show deployment plan.
9. Show Before → Modelled After.
10. Switch to citizen mode, enter A → B, show fastest vs lower-exposure route.
11. Ask Copilot: "Mujhe route mein heat se bachne ke liye kya karna chahiye?" Show route + safe stop + explanation.
Final statement: "HeatShield X doesn't just map heat. It helps cities decide where to act and helps people decide how to move."

## 52. Success Metrics for Hackathon
Spatial: street-level risk differentiation. Temporal: risk/exposure changing through the day. Human: vulnerable population prioritization. Decision: resource-constrained intervention selection. Impact: modelled before/after improvement. Mobility: lower-exposure route selection. Accessibility: citizen-friendly Hindi guidance. Intelligence: Copilot explanation based on actual system data.

## 53. Final Product Definition
NOT a heat map with a chatbot. IS a hyperlocal heat-response decision platform that models street-level exposure over time, identifies vulnerable human exposure, optimizes limited interventions, and helps citizens choose lower-heat travel options.

## 54. Taglines
Primary: "Heat isn't equally dangerous. Your response shouldn't be either." Technical: "From Heat Mapping to Heat Response Optimization." Demo: "Map the heat. Understand the risk. Optimize the response."

## 55. Final Feature Priority
- **P0:** street-level mapping; shadow/exposure engine; 5 time points; vulnerability; cooling access; risk engine; Why panel; intervention optimizer; Before/After.
- **P1:** Why-not-hottest; heat-aware routing; route comparison; Hindi public view.
- **P2:** HeatShield Copilot; safe-stop recommendations; sponsored business concept.
- **Future:** real-time weather; satellite validation; mobile app.

**Final product statement:** HeatShield X transforms heatwave response from "Where is it hottest?" into "Where is human heat exposure highest, when does it happen, why is it happening, where should limited resources be deployed, what changes after intervention, and how can citizens move through the heat more safely?"

---

# PART III — IMPLEMENTATION-GRADE CONTRACTS
These make conceptual parts explicit enough for deterministic implementation. They do not change the product goal.

## 56. Requirement Priority Model
- **P0** Core demo requirement: must be working and testable before polish. Failure means the core product is incomplete.
- **P1** Strong differentiator: implement only after P0 acceptance passes.
- **P2** Enhancement: implement only if P0/P1 are stable and time remains.
- **Future** Post-hackathon roadmap: do not build during the 36-hour core unless explicitly enabled.

## 57. Canonical Data Provenance Contract
Every data-bearing record carries enough provenance for the UI and Copilot. At minimum: `source_type`, `source_reference`, `observed_or_estimated`, `modelled_or_interpolated`, `timestamp`, `assumptions_version`, `computation_mode`.
Data status: Observed = directly sourced; Estimated = derived from explicit assumption; Modelled = produced by HeatShield X calculation; Interpolated = estimated between computed timestamps.
Source priority: (1) actual public/source data; (2) available OSM attributes; (3) transparent ward/area-level estimation; (4) synthetic/demo supplementation only when necessary; (5) never silently invent missing facts.

## 58. Canonical Street Segment Contract
| Field | Requirement |
|---|---|
| segment_id | Stable unique identifier for the demo dataset |
| geometry | Valid projected geometry suitable for length/intersection calculations |
| length_m | Computed segment length in metres |
| road_metadata | Relevant OSM tags retained where available |
| building_context | References to nearby buildings used by shadow processing |
| risk_snapshots | Links to time-specific exposure/risk records |
| provenance | Source and estimation metadata |

## 59. Canonical Building Contract
| Field | Requirement |
|---|---|
| building_id | Stable unique identifier |
| footprint | Valid building polygon |
| height_m | Resolved height |
| height_source | actual / levels / fallback |
| estimated_flag | True when height is not observed |
| levels | OSM levels where available |
| provenance | Source and assumption metadata |

## 60. Time-Snapshot Contract
Exactly five canonical computed timestamps for the MVP: `CANONICAL_TIMES = [09:00, 11:00, 13:00, 15:00, 17:00]`. Each snapshot is independently cacheable.
- t exactly equal to a canonical time → return cached canonical snapshot.
- t between two canonical times → interpolate only supported modelled fields; mark result INTERPOLATED / ESTIMATED.
- Never trigger a full GIS recomputation on every slider event.

## 61. Exposure Calculation Contract
Use a deterministic configurable proxy, not an invented medical model.
Inputs: shade_fraction, direct_exposure_fraction, exposure_duration, optional_temperature_proxy, optional_environmental_proxy.
Required properties: `0 <= exposure_value <= 1`; monotonic (more direct exposure must not reduce exposure; more shade must not increase exposure); deterministic for same inputs/configuration; labelled MODELLED / ESTIMATED where applicable.
Do not present exposure as actual physiological heat load or medical risk.

## 62. Vulnerability Contract
MVP: elderly and outdoor-worker vulnerability. Normalize available indicators to a consistent prioritization scale. Coefficients are configurable prototype assumptions stored in ONE configuration object/version, not scattered across UI code.
Components: elderly_component, outdoor_worker_component; optional future components disabled in MVP.
If exact street data is unavailable: estimate from the smallest available geographic source, distribute using transparent spatial assumptions, set `estimated_flag = true`.
Never output "Exactly N elderly people live on this street." Prefer "Estimated elderly exposure is high for this segment."

## 63. Risk Calculation Contract
```
BASELINE_RISK  = EXPOSURE * VULNERABILITY
ACCESS_PENALTY = configurable_function(walking_distance_to_water,
                 walking_distance_to_cooling, facility_availability, service_radius)
FINAL_RISK_RAW = BASELINE_RISK * (1 + ACCESS_PENALTY)
RISK_SCORE     = deterministic_normalization(FINAL_RISK_RAW, configured_scope)
CLASS: 0–25 LOW, 26–50 MODERATE, 51–75 HIGH, 76–100 CRITICAL
```
All values are MODELLED PRIORITIZATION values, not medical thresholds.

## 64. Normalization Contract
Select the method once, implement centrally, document in configuration. Do not use different normalization in different modules. Default (percentile/min-max over the selected analysis scope):
```
If max_raw == min_raw: score = 50
Else: score = 100 * (raw - min_raw) / (max_raw - min_raw)
Clip score to [0, 100].
```
If a percentile strategy is deliberately chosen, store strategy name and version in config and use it everywhere.

## 65. Cooling Access Contract
Cooling access is a modifier; do not multiply exposure by arbitrary accessibility factors. Distance and availability are converted into a bounded penalty through ONE central configurable function.
```
water_component   = bounded_distance_penalty(distance_to_water, water_service_radius)
cooling_component = bounded_distance_penalty(distance_to_cooling, cooling_service_radius)
availability_factor: unavailable facility => penalty increases; available => no availability penalty
access_penalty = weighted_bounded_sum(water_component, cooling_component, availability_factor)
```
Weights configurable; documented as prototype assumptions.

## 66. Intervention Effect Contract
Effects are configurable simulation rules, labelled modelled.
- Water point: improves water-access coverage and reduces access penalty for eligible segments within configured walking/service radius.
- Cooling centre: improves cooling-access coverage and reduces access penalty for eligible segments within configured radius.
- Shade structure: increases modelled shade for targeted segment(s), reducing direct exposure per a configurable prototype effect.
No intervention may claim an exact °C reduction.

## 67. Optimization Contract
Constrained selection problem. MVP: deterministic greedy.
```
maximize: estimated_reduction_in_vulnerable_heat_exposure
subject to: selected_water_points <= available_water_points
            selected_cooling_centres <= available_cooling_centres
            selected_shade_structures <= available_shade_structures
```
Greedy policy: (1) generate feasible candidates; (2) estimate marginal benefit of each; (3) rank by marginal benefit per constrained resource unit; (4) select highest-benefit feasible candidate; (5) update affected modelled coverage/exposure; (6) repeat until resources exhausted; (7) return selected plan + objective value + per-choice explanation. Never hardcode a fixed deployment plan.

## 68. Before/After Contract
Rerun the SAME deterministic scoring pipeline after intervention simulation. Before and after use the same configuration version and analysis scope.
Metrics: high-risk vulnerable exposure; cooling coverage; average cooling distance; intervention coverage — each compared before vs modelled after. Always label **Modelled Impact**; never present as measured real-world causal impact.

## 69. Routing Contract
Routing operates on the same street-segment graph used by the risk system. Candidate routes are generated by the graph engine and scored using the same cached exposure snapshots.
- FASTEST: minimize travel time.
- HEAT-AWARE: minimize a heat-aware objective penalizing segment exposure while preserving reasonable travel time.
- BALANCED: minimize `alpha * normalized_time + beta * normalized_heat_exposure` (configurable).
Required comparison fields: total_time, total_distance, modelled_heat_exposure, average/weighted shade, cooling access, route classification.
Wording: "Lower modelled heat exposure". Never "Prevents heatstroke."

## 70. Safe Stop Contract
| Field | Meaning |
|---|---|
| stop_id | Stable ID |
| stop_type | water / cooling / shaded_public / business |
| name | Source-provided name where available |
| location | Geographic point |
| route_distance | Distance from route |
| detour_distance | Additional distance/time required |
| verified_status | Whether amenities are verified |
| amenities | Only source-supported amenities |
| rating | Only if source provides it |
| sponsored_status | Clearly labelled if applicable |
| route_relevance | Calculated relevance to selected route |

## 71. Copilot Grounding Contract
The Copilot is a grounded interface over deterministic application tools/data. It may summarize, explain and guide; it must not become a parallel source of truth.
Pipeline: User → Intent classification → Retrieve structured system data → Call relevant deterministic engine/tool → Build facts + assumptions context → LLM generates natural-language explanation → Safety / fact-check gate → Answer.
If required data is missing: "Data unavailable for this area."
Never allow the model to invent: risk score, route time, distance, rating, intervention impact, scientific claim.

## 72. Copilot Intent Contract
| Intent | Required source |
|---|---|
| Platform guide | Static product help + UI state |
| Risk explanation | Selected RiskRecord + RiskDriver records |
| Route assistant | Actual Route objects and route metrics |
| Safe stop assistant | Actual SafeStop records |
| Planner assistant | Actual ResourcePlan / optimizer output |
| Data transparency | Provenance and assumption metadata |
| Heat safety | Approved general guidance; no diagnosis |

## 73. UI State Contract
| Screen/state | Minimum visible content |
|---|---|
| Planner map | Map, selected time, legend, risk segments, selected area |
| Street selection | Street ID/name, risk score, class, major drivers, vulnerability, cooling access |
| Why-not-hottest | Hottest vs highest human-risk comparison with driver values |
| Resource planner | Available counts, candidate interventions, Optimize Response action |
| Before/After | Before, Modelled After, delta and metric definitions |
| Citizen route | Origin, destination, route options, time, exposure, shade/cooling comparison |
| Safe stops | Stop type, name, distance/detour, verification, relevant amenities |
| Copilot | Conversation plus visible context/selected entity when relevant |

## 74. Failure-Mode Contract
| Failure | Required behavior |
|---|---|
| OSM unavailable | Show actionable data-load error; allow preloaded demo dataset if configured |
| Invalid geometry | Repair/skip with logged reason; do not crash entire pipeline |
| Missing building height | Use defined estimation hierarchy and flag it |
| Shadow engine failure | Use defined fallback mode and display Estimated Exposure Mode |
| Population missing | Use documented estimation/synthetic demo path and flag it |
| No cooling facility | Access component reflects unavailable coverage; do not invent a facility |
| Copilot API unavailable | Core platform remains functional; hide/disable Copilot gracefully |
| Routing failure | Explain route-generation failure; do not fabricate routes |
| Slow computation | Use cached/precomputed results; do not block UI unnecessarily |

## 75. Configuration Contract
All assumptions and coefficients live in a central versioned configuration layer/file. UI code, Copilot prompts and individual algorithms must not contain hidden copies of weights.
Config must include: demo_area, canonical_times, building_height_per_floor, fallback_building_floors, risk_normalization_method, risk_class_ranges, vulnerability_weights, cooling_service_radius, water_service_radius, access_penalty_weights, intervention_effect_coefficients, route_objective_weights, feature_flags, computation_mode, data_source_metadata.
Every modelled output must be reproducible from: data snapshot + configuration version + code version.

## 76. API / Module Boundary Contract
| Module | Consumes | Produces |
|---|---|---|
| DataEngine | OSM/public/synthetic inputs | normalized raw/derived datasets |
| StreetEngine | road graph | StreetSegments |
| BuildingEngine | building attributes | Buildings with resolved heights |
| ShadowEngine | Buildings + solar time + Streets | ShadowSnapshots |
| ExposureEngine | ShadowSnapshots + environmental/time inputs | ExposureRecords |
| VulnerabilityEngine | demographic inputs + Streets | VulnerabilityRecords |
| CoolingAccessEngine | facilities + Streets | CoolingAccessRecords |
| RiskEngine | Exposure + Vulnerability + Access | RiskRecords |
| ExplainabilityEngine | Risk + source drivers | RiskDrivers |
| InterventionEngine | Risk + vulnerability + facilities | InterventionCandidates |
| Optimizer | Candidates + resource constraints | ResourcePlan |
| ImpactEngine | Baseline + ResourcePlan | ImpactSnapshot |
| RoutingEngine | Street graph + Exposure | Routes |
| StopFinder | Route + facilities/business data | SafeStops |
| Copilot | structured application outputs | grounded natural-language response |

## 77. Testing Strategy
- Unit tests: formulas, normalization, distance penalties, route scoring, intervention effects.
- Geospatial tests: CRS, valid geometry, shadow direction, street/shadow intersection.
- Data-contract tests: provenance and observed/estimated/modelled/interpolated labels.
- Integration tests across the risk pipeline.
- Fallback tests proving the app continues when the shadow engine fails.
- End-to-end demo test using a fixed small area and deterministic configuration.
- Copilot grounding tests where facts exist and where facts are intentionally missing.
- UI smoke tests for planner, citizen route, WHY, optimizer and before/after flows.

## 78. Reproducibility Contract
Reproducible from a clean environment. Repository provides: a single setup path, dependency lock/requirements file, deterministic configuration, data-fetch/preload instructions, run command, test command. Demo area configurable but fixed for the final demo build.

## 79. Observability Contract
Log: data loading, geometry processing, shadow computation, risk generation, optimization and routing durations; fallback activation and reason; configuration version used; warnings for estimated/synthetic data. Do not log unnecessary personal data. Provide enough diagnostics to reproduce a failed demo state.

## 80. Security and Privacy Implementation Contract
Collect only necessary data. Do not store precise personal travel histories (route inputs transient where practical). Do not expose internal API keys in source or frontend. Do not expose private demographic records. Treat external business/sponsored metadata as untrusted input. Sponsorship metadata must not alter safety/relevance ranking logic.

## 81. Commercialization Boundary
Sponsored heat-safe stops are a future concept, not a 36-hour marketplace. The prototype may demonstrate a labelled sponsored flag and ranking rule, but must not build payments, ad auctions, merchant billing or a full ad system.
Flow: Safety/relevance filter → eligible stop → if sponsored: display "Sponsored"; do not bypass relevance; do not bypass verification; do not override core safety constraints → user sees result.

## 82. Roadmap Contract
Phase 2: real-time weather, improved population datasets, more vulnerability groups, better building-height datasets, improved routing, real-time heat alerts. Phase 3: satellite LST integration, sensor integration, historical heatwave analysis, advanced optimization, mobile application. Phase 4: municipal deployment, verified cooling network, business partnerships, sponsored heat-safe stops, analytics/reporting.

## 83. Hackathon Success Metrics
Spatial: street-level risk differentiation. Temporal: exposure/risk changes through the day. Human: vulnerable population prioritization. Decision: resource-constrained intervention selection. Impact: modelled before/after improvement. Mobility: lower-exposure route selection. Accessibility: citizen-friendly Hindi guidance. Intelligence: Copilot explanation based on actual system data.

## 84. AI Agent Handoff Contract
Treat this document as a constrained specification, not an invitation to redesign the product. The agent may choose implementation details inside the permitted architecture but must not silently change product goals, formulas, labels, priority order or safety boundaries.
AI build rules:
1. Read the entire SRS before coding.
2. Build P0 before P1 and P2.
3. Preserve module boundaries.
4. Centralize configuration.
5. Never invent missing factual data.
6. Never turn modelled values into medical claims.
7. Never let Copilot override deterministic outputs.
8. Never hardcode demo results.
9. Add tests for every new engine.
10. Preserve fallback behavior.
11. Prefer a reliable small demo area over fragile scale.
12. If a requirement is genuinely ambiguous: choose the smallest deterministic implementation, make it configurable, document the assumption, do not silently redefine the product.
13. Do not add React/Node/mobile/complex cloud/ML unless the specification is explicitly revised.
14. At every milestone report: implemented, tested, failed, assumptions, remaining blockers.

## 85. AI Agent Definition of Done
| Condition | Done when |
|---|---|
| Core pipeline | Data → street/building → shadow/fallback → exposure → vulnerability → cooling → risk works |
| Explainability | WHY and Why-not-hottest use actual computed data |
| Planning | Intervention candidates + constrained optimization + modelled before/after work |
| Mobility | Fastest/heat-aware/balanced routes compare actual metrics |
| Public view | Citizen flow works and Hindi guidance is available |
| Copilot | Grounded explanations work and hallucination cases are blocked |
| Reliability | Fallback works and is visibly labelled |
| Transparency | Observed/estimated/modelled/interpolated distinctions are preserved |
| Testing | Critical unit/integration/end-to-end tests pass |
| Demo | The 3-minute narrative can be completed without manual hidden steps |

## 86. Final Non-Negotiable Guardrails
- HeatShield X is NOT a heat map with a chatbot.
- Deterministic engines are the source of truth.
- Copilot explains and operates on actual system data.
- No individual heatstroke prediction. No medical diagnosis. No guaranteed safety claims.
- No fake demographic precision.
- No hardcoded intervention impact.
- No fake route data.
- No invented ratings or amenities.
- No sponsorship override of safety/relevance.
- No unnecessary ML.
- No full mobile app during the hackathon.
- No live satellite ingestion pipeline during the hackathon.
- No large cloud architecture unless required.
- No feature expansion during the final 2 hours.
- When the shadow engine fails, use the defined fallback rather than hiding the failure.

## 87. Final Traceability Matrix
| Original need | SRS sections | Primary module | Acceptance evidence |
|---|---|---|---|
| Street-level risk | 7–8, 58, 63–64 | Street + Risk | Street risk map + score |
| Time dependence | 10–15, 60 | Shadow + Exposure | 09/11/13/15/17 snapshots + slider |
| Vulnerability | 16, 62 | Vulnerability | Elderly/outdoor-worker estimates |
| Cooling access | 18, 65 | Cooling Access | Distance + access penalty |
| Explainability | 21–22, 72–73 | WHY | Driver breakdown + comparison |
| Intervention | 23–26, 66–68 | Optimizer | Deployment plan + impact |
| Mobility | 27–30, 69–70 | Routing | Route comparison + stops |
| Citizen experience | 35, 38, 73 | Public View | Citizen flow |
| AI | 32–34, 71–72 | Copilot | Grounded explanation |
| Reliability | 13, 44, 74 | Fallback | Estimated Exposure Mode |
| Transparency | 45–46, 57 | Data governance | Status/provenance labels |
| Safety | 47, 80, 86 | Cross-cutting | No unsafe/fabricated claims |
| Roadmap | 48, 82 | Product strategy | Phase 2–4 |
| Demo | 51 | All modules | 3-minute narrative |
| Success | 52, 83 | All modules | 8 success dimensions |

**Core workflow:** Map → Explain → Simulate → Optimize → Act. **Citizen workflow:** Understand → Route → Safe Stop → Act. **AI principle:** Algorithm decides. AI explains.