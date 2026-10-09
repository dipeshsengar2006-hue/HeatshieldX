"""Citizen-view display strings, isolated for a later Hindi translation."""

from __future__ import annotations


CITIZEN_EN = {
    "page_title": "HeatShield X | Citizen",
    "brand_name": "HeatShield X",
    "meta_description": "Compare routes with modelled heat context.",
    "header_context": "Heat-aware mobility",
    "nav_planner": "Planner",
    "nav_citizen": "Citizen",
    "eyebrow": "Citizen mode",
    "title": "Plan a route with modelled heat context",
    "intro": "Compare cached route options and choose the trade-off that suits your trip.",
    "route_planner_title": "Route planner",
    "origin_label": "Origin",
    "destination_label": "Destination",
    "origin_placeholder": "Search a street, building or amenity",
    "destination_placeholder": "Search a street, building or amenity",
    "pick_origin": "Pick origin on map",
    "pick_destination": "Pick destination on map",
    "pick_instruction_origin": "Select the origin on the map.",
    "pick_instruction_destination": "Select the destination on the map.",
    "departure_time": "Departure time",
    "modelled": "Modelled",
    "interpolated": "Interpolated",
    "find_routes": "Find routes",
    "finding_routes": "Finding routes…",
    "examples": "Examples",
    "examples_note": "Example trips use the same route service as manual entries.",
    "preset_kadavghat": "Kadavghat road → M.G. Road · 09:00",
    "preset_yashwant": "Yashwant road → M.G. Road · 09:00",
    "preset_riverside": "M.G. Road → River Side Road · 17:00",
    "preset_origin_kadavghat": "Kadavghat road",
    "preset_origin_yashwant": "Yashwant road",
    "preset_origin_riverside": "M.G. Road",
    "preset_destination_mg": "M.G. Road",
    "preset_destination_riverside": "River Side Road",
    "map_label": "Route map",
    "osm_attribution": "© OpenStreetMap contributors",
    "map_fallback": "Cached street data remains available if map tiles do not load.",
    "route_legend": "Route legend",
    "stop_legend": "Recorded stop types",
    "legend_fastest": "Fastest",
    "legend_heat_aware": "Lower modelled heat exposure",
    "legend_balanced": "Balanced",
    "route_options": "Route options",
    "route_options_empty": "Choose an origin and destination to compare route options.",
    "route_fastest": "Fastest",
    "route_heat_aware": "Lower modelled heat exposure",
    "route_balanced": "Balanced",
    "card_fastest": "FASTEST",
    "card_heat_aware": "HEAT-AWARE",
    "card_balanced": "BALANCED",
    "same_as_fastest": "Same as Fastest",
    "same_as_route": "Same as {route}",
    "time": "Time",
    "distance": "Distance",
    "modelled_heat": "Modelled heat exposure",
    "heat_change": "Change versus fastest",
    "extra_minutes": "Extra minutes",
    "weighted_shade": "Weighted shade",
    "cooling_access": "Cooling access",
    "cooling_unavailable": "Data unavailable (no recorded facility)",
    "minutes": "min",
    "metres": "m",
    "modelled_estimate": "Modelled estimate, not a safety guarantee.",
    "selected_route": "Selected route",
    "stops_title": "Stops along this route",
    "stops_empty": "Choose a route to view recorded stops.",
    "route_distance": "Distance from route",
    "detour_distance": "Detour distance",
    "verified_status": "Unverified (OSM)",
    "amenities": "Amenities",
    "rating_unavailable": "Rating unavailable",
    "sponsored": "Sponsored",
    "guidance_title": "Heat guidance",
    "guidance_carry_water": "Carry water for your journey.",
    "guidance_prefer_shade": "Prefer shaded parts of the route where practical.",
    "guidance_rest_cool": "Rest in cool places when you need a break.",
    "guidance_avoid_hottest": "Avoid the hottest hours when your schedule allows.",
    "status_loading_places": "Searching cached places…",
    "status_no_places": "No matching cached places found.",
    "status_pick_required": "Choose a point on the map or select a cached place.",
    "status_loading_routes": "Calculating cached route options…",
    "status_route_ready": "Route options are ready.",
    "status_error_prefix": "Unable to find routes: {message}",
    "status_stops_missing": "No stop data available",
    "status_stops_empty": "No eligible stops recorded in OSM along this route",
    "status_tile_error": "Map tiles are unavailable; cached routes and streets still work.",
    "mode_geometric": "Geometric shadow mode",
    "mode_estimated": "Estimated Exposure Mode",
    "nav_label": "Main navigation",
    "planner_page": "Planner",
    "citizen_page": "Citizen",
    "place_search_label": "Search suggestions",
    "places_loading": "Searching places…",
    "places_error": "Place search is unavailable. Try picking a point on the map.",
    "places_no_match": "No matching places found.",
    "origin_required": "Choose an origin from suggestions or pick it on the map.",
    "destination_required": "Choose a destination from suggestions or pick it on the map.",
    "route_error_422": "Check the selected points and departure time, then try again.",
    "route_error_area": "One or both points are outside the mapped area. Choose points inside the demo area.",
    "route_error_path": "No walking path connects those points in the cached street data.",
    "route_error_generic": "Route options could not be loaded. Please try again.",
    "map_pick_origin": "Picking origin. Select a point on the map.",
    "map_pick_destination": "Picking destination. Select a point on the map.",
    "stop_type_water": "Water point",
    "stop_type_cooling": "Cooling place",
    "stop_type_shaded_public": "Shaded public place",
    "stop_type_business": "Business",
    "stop_type_other": "Recorded stop",
    "stops_unavailable": "No stop data available",
    "stops_no_eligible": "No eligible stops recorded in OSM along this route",
    "stop_distance_value": "{value} m",
    "extra_minutes_value": "{value} min",
    "same_route_fastest": "Same as Fastest",
    "recommendation_small": "Differences are small ({percent}% lower modelled heat exposure); the fastest route is a reasonable choice.",
    "recommendation_heat": "Recommended heat-aware route: adds approximately {minutes} minutes but has lower modelled heat exposure ({percent}% lower).",
    "recommendation_no_reduction": "The fastest route has the lowest modelled heat exposure among these options.",
    "no_heat_route": "No separate lower-exposure route was found within the allowed detour.",
    "empty_routes": "No route options are available for these points.",
    "selected_stop_status": "Route stops are unverified OpenStreetMap records.",
    "footer": "Configuration {config_version} · Source: © OpenStreetMap contributors · Data download: {data_download_date}",
}


CITIZEN_REQUIRED_IDS = frozenset("""
    page_title brand_name meta_description header_context nav_planner nav_citizen eyebrow title intro route_planner_title
    origin_label destination_label origin_placeholder destination_placeholder pick_origin pick_destination
    pick_instruction_origin pick_instruction_destination departure_time modelled interpolated find_routes
    finding_routes examples examples_note preset_kadavghat preset_yashwant preset_riverside
    preset_origin_kadavghat preset_origin_yashwant preset_origin_riverside preset_destination_mg
    preset_destination_riverside map_label osm_attribution map_fallback route_legend stop_legend legend_fastest legend_heat_aware
    legend_balanced route_options route_options_empty route_fastest route_heat_aware route_balanced
    card_fastest card_heat_aware card_balanced
    same_as_fastest same_as_route time distance modelled_heat heat_change extra_minutes weighted_shade
    cooling_access cooling_unavailable minutes metres modelled_estimate selected_route stops_title stops_empty route_distance
    detour_distance verified_status amenities rating_unavailable sponsored guidance_title guidance_carry_water
    guidance_prefer_shade guidance_rest_cool guidance_avoid_hottest status_loading_places status_no_places
    status_pick_required status_loading_routes status_route_ready status_error_prefix status_stops_missing
    status_stops_empty status_tile_error mode_geometric mode_estimated nav_label planner_page citizen_page
    place_search_label places_loading places_error places_no_match origin_required destination_required
    route_error_422 route_error_area route_error_path route_error_generic map_pick_origin map_pick_destination
    stop_type_water stop_type_cooling stop_type_shaded_public stop_type_business stop_type_other stops_unavailable
    stops_no_eligible stop_distance_value extra_minutes_value same_route_fastest recommendation_small
    recommendation_heat recommendation_no_reduction no_heat_route empty_routes selected_stop_status footer
""".split())


def validate_citizen_i18n() -> None:
    """Fail fast if the English catalog is incomplete or unsafe for this view."""
    missing = CITIZEN_REQUIRED_IDS - CITIZEN_EN.keys()
    if missing:
        raise ValueError(f"Citizen English strings are missing ids: {', '.join(sorted(missing))}")
    forbidden = ("heatstroke", "prevent", "safe route")
    for key, value in CITIZEN_EN.items():
        if any(word in value.casefold() for word in forbidden):
            raise ValueError(f"Citizen English string '{key}' contains prohibited wording.")
