"""Citizen-view display strings, isolated for a later Hindi translation."""

from __future__ import annotations

import re


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
    "finding_routes": "Finding routesâ€¦",
    "examples": "Examples",
    "examples_note": "Example trips use the same route service as manual entries.",
    "preset_kadavghat": "Kadavghat road â†’ M.G. Road Â· 09:00",
    "preset_yashwant": "Yashwant road â†’ M.G. Road Â· 09:00",
    "preset_riverside": "M.G. Road â†’ River Side Road Â· 17:00",
    "preset_origin_kadavghat": "Kadavghat road",
    "preset_origin_yashwant": "Yashwant road",
    "preset_origin_riverside": "M.G. Road",
    "preset_destination_mg": "M.G. Road",
    "preset_destination_riverside": "River Side Road",
    "map_label": "Route map",
    "osm_attribution": "Â© OpenStreetMap contributors",
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
    "status_loading_places": "Searching cached placesâ€¦",
    "status_no_places": "No matching cached places found.",
    "status_pick_required": "Choose a point on the map or select a cached place.",
    "status_loading_routes": "Calculating cached route optionsâ€¦",
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
    "places_loading": "Searching placesâ€¦",
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
    "stops_available": "Available",
    "stop_distance_value": "{value} m",
    "extra_minutes_value": "{value} min",
    "same_route_fastest": "Same as Fastest",
    "recommendation_small": "Differences are small ({percent}% lower modelled heat exposure); the fastest route is a reasonable choice.",
    "recommendation_heat": "Recommended heat-aware route: adds approximately {minutes} minutes but has lower modelled heat exposure ({percent}% lower).",
    "recommendation_no_reduction": "The fastest route has the lowest modelled heat exposure among these options.",
    "no_heat_route": "No separate lower-exposure route was found within the allowed detour.",
    "empty_routes": "No route options are available for these points.",
    "selected_stop_status": "Route stops are unverified OpenStreetMap records.",
    "language_label": "Language",
    "language_english": "English",
    "language_hindi": "à¤¹à¤¿à¤¨à¥à¤¦à¥€",
    "summary_title": "Heat summary for this time",
    "summary_before_location": "Choose a location to see street-level details here.",
    "summary_exposure_label": "Street level",
    "summary_peak_label": "Area peak window",
    "summary_water_label": "Distance to water",
    "summary_cooling_label": "Distance to a cooling place",
    "summary_lower_route": "A route with lower modelled heat exposure is available.",
    "summary_no_lower_route": "Find routes to check whether a lower-exposure option is available.",
    "summary_level_low": "LOW",
    "summary_level_moderate": "MODERATE",
    "summary_level_high": "HIGH",
    "summary_peak_window": "Highest modelled exposure {start_time}-{end_time}",
    "summary_distance": "{value} m",
    "summary_data_unavailable": "Data unavailable (no recorded facility)",
    "summary_loading": "Loading street summaryâ€¦",
    "summary_error": "Summary data is unavailable for this location.",
    "summary_error_area": "Choose a location inside the mapped demo area, near a recorded street.",
    "summary_status_modelled": "Modelled",
    "summary_status_estimated": "Estimated",
    "summary_status_interpolated": "Interpolated",
    "summary_map_level": "Pick an origin on the map",
    "footer": "Configuration {config_version} Â· Source: Â© OpenStreetMap contributors Â· Data download: {data_download_date}",
}


_CITIZEN_HI_BASE = {
    "page_title": "HeatShield X | à¤¨à¤¾à¤—à¤°à¤¿à¤•",
    "brand_name": "HeatShield X",
    "meta_description": "à¤®à¥‰à¤¡à¤² à¤ªà¤° à¤†à¤§à¤¾à¤°à¤¿à¤¤ à¤—à¤°à¥à¤®à¥€ à¤•à¥€ à¤œà¤¾à¤¨à¤•à¤¾à¤°à¥€ à¤•à¥‡ à¤¸à¤¾à¤¥ à¤®à¤¾à¤°à¥à¤—à¥‹à¤‚ à¤•à¥€ à¤¤à¥à¤²à¤¨à¤¾ à¤•à¤°à¥‡à¤‚à¥¤",
    "header_context": "à¤—à¤°à¥à¤®à¥€ à¤•à¥€ à¤œà¤¾à¤¨à¤•à¤¾à¤°à¥€ à¤•à¥‡ à¤¸à¤¾à¤¥ à¤¯à¤¾à¤¤à¥à¤°à¤¾",
    "nav_planner": "à¤¯à¥‹à¤œà¤¨à¤¾",
    "nav_citizen": "à¤¨à¤¾à¤—à¤°à¤¿à¤•",
    "eyebrow": "à¤¨à¤¾à¤—à¤°à¤¿à¤• à¤®à¥‹à¤¡",
    "title": "à¤—à¤°à¥à¤®à¥€ à¤•à¥€ à¤®à¥‰à¤¡à¤² à¤œà¤¾à¤¨à¤•à¤¾à¤°à¥€ à¤•à¥‡ à¤¸à¤¾à¤¥ à¤®à¤¾à¤°à¥à¤— à¤šà¥à¤¨à¥‡à¤‚",
    "intro": "à¤•à¥ˆà¤¶ à¤•à¤¿à¤ à¤—à¤ à¤®à¤¾à¤°à¥à¤—à¥‹à¤‚ à¤•à¥€ à¤¤à¥à¤²à¤¨à¤¾ à¤•à¤°à¥‡à¤‚ à¤”à¤° à¤…à¤ªà¤¨à¥€ à¤¯à¤¾à¤¤à¥à¤°à¤¾ à¤•à¥‡ à¤²à¤¿à¤ à¤¸à¤¹à¥€ à¤µà¤¿à¤•à¤²à¥à¤ª à¤šà¥à¤¨à¥‡à¤‚à¥¤",
    "route_planner_title": "à¤®à¤¾à¤°à¥à¤— à¤¯à¥‹à¤œà¤¨à¤¾",
    "origin_label": "à¤¶à¥à¤°à¥à¤†à¤¤à¥€ à¤¸à¥à¤¥à¤¾à¤¨",
    "destination_label": "à¤®à¤‚à¤œà¤¼à¤¿à¤²",
    "origin_placeholder": "à¤¸à¤¡à¤¼à¤•, à¤‡à¤®à¤¾à¤°à¤¤ à¤¯à¤¾ à¤¸à¥à¤µà¤¿à¤§à¤¾ à¤–à¥‹à¤œà¥‡à¤‚",
    "destination_placeholder": "à¤¸à¤¡à¤¼à¤•, à¤‡à¤®à¤¾à¤°à¤¤ à¤¯à¤¾ à¤¸à¥à¤µà¤¿à¤§à¤¾ à¤–à¥‹à¤œà¥‡à¤‚",
    "pick_origin": "à¤®à¤¾à¤¨à¤šà¤¿à¤¤à¥à¤° à¤ªà¤° à¤¶à¥à¤°à¥à¤†à¤¤ à¤šà¥à¤¨à¥‡à¤‚",
    "pick_destination": "à¤®à¤¾à¤¨à¤šà¤¿à¤¤à¥à¤° à¤ªà¤° à¤®à¤‚à¤œà¤¼à¤¿à¤² à¤šà¥à¤¨à¥‡à¤‚",
    "pick_instruction_origin": "à¤®à¤¾à¤¨à¤šà¤¿à¤¤à¥à¤° à¤ªà¤° à¤¶à¥à¤°à¥à¤†à¤¤à¥€ à¤¸à¥à¤¥à¤¾à¤¨ à¤šà¥à¤¨à¥‡à¤‚à¥¤",
    "pick_instruction_destination": "à¤®à¤¾à¤¨à¤šà¤¿à¤¤à¥à¤° à¤ªà¤° à¤®à¤‚à¤œà¤¼à¤¿à¤² à¤šà¥à¤¨à¥‡à¤‚à¥¤",
    "departure_time": "à¤°à¤µà¤¾à¤¨à¤¾ à¤¹à¥‹à¤¨à¥‡ à¤•à¤¾ à¤¸à¤®à¤¯",
    "modelled": "à¤®à¥‰à¤¡à¤² à¤ªà¤° à¤†à¤§à¤¾à¤°à¤¿à¤¤",
    "interpolated": "à¤¬à¥€à¤š à¤•à¥‡ à¤¸à¤®à¤¯ à¤•à¤¾ à¤…à¤¨à¥à¤®à¤¾à¤¨",
    "find_routes": "à¤®à¤¾à¤°à¥à¤— à¤–à¥‹à¤œà¥‡à¤‚",
    "finding_routes": "à¤®à¤¾à¤°à¥à¤— à¤–à¥‹à¤œà¥‡ à¤œà¤¾ à¤°à¤¹à¥‡ à¤¹à¥ˆà¤‚â€¦",
    "examples": "à¤‰à¤¦à¤¾à¤¹à¤°à¤£",
    "examples_note": "à¤‰à¤¦à¤¾à¤¹à¤°à¤£ à¤¯à¤¾à¤¤à¥à¤°à¤¾à¤à¤ à¤­à¥€ à¤‡à¤¸à¥€ à¤®à¤¾à¤°à¥à¤— à¤¸à¥‡à¤µà¤¾ à¤•à¤¾ à¤‰à¤ªà¤¯à¥‹à¤— à¤•à¤°à¤¤à¥€ à¤¹à¥ˆà¤‚à¥¤",
    "preset_kadavghat": "à¤•à¤¡à¤¼à¤¾à¤µà¤˜à¤¾à¤Ÿ à¤°à¥‹à¤¡ â†’ à¤à¤®.à¤œà¥€. à¤°à¥‹à¤¡ Â· 09:00",
    "preset_yashwant": "à¤¯à¤¶à¤µà¤‚à¤¤ à¤°à¥‹à¤¡ â†’ à¤à¤®.à¤œà¥€. à¤°à¥‹à¤¡ Â· 09:00",
    "preset_riverside": "à¤à¤®.à¤œà¥€. à¤°à¥‹à¤¡ â†’ à¤°à¤¿à¤µà¤° à¤¸à¤¾à¤‡à¤¡ à¤°à¥‹à¤¡ Â· 17:00",
    "preset_origin_kadavghat": "à¤•à¤¡à¤¼à¤¾à¤µà¤˜à¤¾à¤Ÿ à¤°à¥‹à¤¡",
    "preset_origin_yashwant": "à¤¯à¤¶à¤µà¤‚à¤¤ à¤°à¥‹à¤¡",
    "preset_origin_riverside": "à¤à¤®.à¤œà¥€. à¤°à¥‹à¤¡",
    "preset_destination_mg": "à¤à¤®.à¤œà¥€. à¤°à¥‹à¤¡",
    "preset_destination_riverside": "à¤°à¤¿à¤µà¤° à¤¸à¤¾à¤‡à¤¡ à¤°à¥‹à¤¡",
    "map_label": "à¤®à¤¾à¤°à¥à¤— à¤®à¤¾à¤¨à¤šà¤¿à¤¤à¥à¤°",
    "osm_attribution": "Â© OpenStreetMap contributors",
    "map_fallback": "à¤®à¤¾à¤¨à¤šà¤¿à¤¤à¥à¤° à¤Ÿà¤¾à¤‡à¤²à¥‡à¤‚ à¤¨ à¤–à¥à¤²à¥‡à¤‚, à¤¤à¤¬ à¤­à¥€ à¤•à¥ˆà¤¶ à¤•à¥€ à¤—à¤ˆ à¤¸à¤¡à¤¼à¤•à¥‡à¤‚ à¤‰à¤ªà¤²à¤¬à¥à¤§ à¤°à¤¹à¥‡à¤‚à¤—à¥€à¥¤",
    "route_legend": "à¤®à¤¾à¤°à¥à¤— à¤¸à¤‚à¤•à¥‡à¤¤",
    "stop_legend": "à¤¦à¤°à¥à¤œ à¤ à¤¹à¤°à¤¾à¤µ à¤•à¥‡ à¤ªà¥à¤°à¤•à¤¾à¤°",
    "legend_fastest": "à¤¸à¤¬à¤¸à¥‡ à¤¤à¥‡à¤œà¤¼",
    "legend_heat_aware": "à¤•à¤® à¤®à¥‰à¤¡à¤² à¤ªà¤° à¤†à¤§à¤¾à¤°à¤¿à¤¤ à¤—à¤°à¥à¤®à¥€ à¤•à¤¾ à¤…à¤¨à¥à¤®à¤¾à¤¨",
    "legend_balanced": "à¤¸à¤‚à¤¤à¥à¤²à¤¿à¤¤",
    "route_options": "à¤®à¤¾à¤°à¥à¤— à¤µà¤¿à¤•à¤²à¥à¤ª",
    "route_options_empty": "à¤®à¤¾à¤°à¥à¤—à¥‹à¤‚ à¤•à¥€ à¤¤à¥à¤²à¤¨à¤¾ à¤•à¥‡ à¤²à¤¿à¤ à¤¶à¥à¤°à¥à¤†à¤¤ à¤”à¤° à¤®à¤‚à¤œà¤¼à¤¿à¤² à¤šà¥à¤¨à¥‡à¤‚à¥¤",
    "route_fastest": "à¤¸à¤¬à¤¸à¥‡ à¤¤à¥‡à¤œà¤¼",
    "route_heat_aware": "à¤•à¤® à¤®à¥‰à¤¡à¤² à¤ªà¤° à¤†à¤§à¤¾à¤°à¤¿à¤¤ à¤—à¤°à¥à¤®à¥€ à¤•à¤¾ à¤…à¤¨à¥à¤®à¤¾à¤¨",
    "route_balanced": "à¤¸à¤‚à¤¤à¥à¤²à¤¿à¤¤",
    "card_fastest": "à¤¸à¤¬à¤¸à¥‡ à¤¤à¥‡à¤œà¤¼",
    "card_heat_aware": "à¤—à¤°à¥à¤®à¥€ à¤•à¥‡ à¤¹à¤¿à¤¸à¤¾à¤¬ à¤¸à¥‡",
    "card_balanced": "à¤¸à¤‚à¤¤à¥à¤²à¤¿à¤¤",
    "same_as_fastest": "à¤¸à¤¬à¤¸à¥‡ à¤¤à¥‡à¤œà¤¼ à¤®à¤¾à¤°à¥à¤— à¤œà¥ˆà¤¸à¤¾",
    "same_as_route": "{route} à¤œà¥ˆà¤¸à¤¾",
    "time": "à¤¸à¤®à¤¯",
    "distance": "à¤¦à¥‚à¤°à¥€",
    "modelled_heat": "à¤®à¥‰à¤¡à¤² à¤ªà¤° à¤†à¤§à¤¾à¤°à¤¿à¤¤ à¤—à¤°à¥à¤®à¥€ à¤•à¤¾ à¤…à¤¨à¥à¤®à¤¾à¤¨",
    "heat_change": "à¤¸à¤¬à¤¸à¥‡ à¤¤à¥‡à¤œà¤¼ à¤®à¤¾à¤°à¥à¤— à¤¸à¥‡ à¤…à¤‚à¤¤à¤°",
    "extra_minutes": "à¤…à¤¤à¤¿à¤°à¤¿à¤•à¥à¤¤ à¤¸à¤®à¤¯",
    "weighted_shade": "à¤­à¤¾à¤°à¤¿à¤¤ à¤›à¤¾à¤¯à¤¾",
    "cooling_access": "à¤ à¤‚à¤¡à¤• à¤•à¥€ à¤¸à¥à¤µà¤¿à¤§à¤¾ à¤¤à¤• à¤ªà¤¹à¥à¤à¤š",
    "cooling_unavailable": "à¤œà¤¾à¤¨à¤•à¤¾à¤°à¥€ à¤‰à¤ªà¤²à¤¬à¥à¤§ à¤¨à¤¹à¥€à¤‚ (à¤•à¥‹à¤ˆ à¤¸à¥à¤µà¤¿à¤§à¤¾ à¤¦à¤°à¥à¤œ à¤¨à¤¹à¥€à¤‚)",
    "minutes": "min",
    "metres": "m",
    "modelled_estimate": "à¤¯à¤¹ à¤®à¥‰à¤¡à¤² à¤•à¤¾ à¤…à¤¨à¥à¤®à¤¾à¤¨ à¤¹à¥ˆ; à¤µà¤¾à¤¸à¥à¤¤à¤µà¤¿à¤• à¤¸à¥à¤¥à¤¿à¤¤à¤¿ à¤…à¤²à¤— à¤¹à¥‹ à¤¸à¤•à¤¤à¥€ à¤¹à¥ˆà¥¤",
    "selected_route": "à¤šà¥à¤¨à¤¾ à¤¹à¥à¤† à¤®à¤¾à¤°à¥à¤—",
    "stops_title": "à¤‡à¤¸ à¤®à¤¾à¤°à¥à¤— à¤•à¥‡ à¤ à¤¹à¤°à¤¾à¤µ",
    "stops_empty": "à¤¦à¤°à¥à¤œ à¤ à¤¹à¤°à¤¾à¤µ à¤¦à¥‡à¤–à¤¨à¥‡ à¤•à¥‡ à¤²à¤¿à¤ à¤®à¤¾à¤°à¥à¤— à¤šà¥à¤¨à¥‡à¤‚à¥¤",
    "route_distance": "à¤®à¤¾à¤°à¥à¤— à¤¸à¥‡ à¤¦à¥‚à¤°à¥€",
    "detour_distance": "à¤…à¤¤à¤¿à¤°à¤¿à¤•à¥à¤¤ à¤¦à¥‚à¤°à¥€",
    "verified_status": "à¤¸à¤¤à¥à¤¯à¤¾à¤ªà¤¿à¤¤ à¤¨à¤¹à¥€à¤‚ (OSM)",
    "amenities": "à¤¸à¥à¤µà¤¿à¤§à¤¾à¤à¤",
    "rating_unavailable": "à¤°à¥‡à¤Ÿà¤¿à¤‚à¤— à¤‰à¤ªà¤²à¤¬à¥à¤§ à¤¨à¤¹à¥€à¤‚",
    "sponsored": "à¤ªà¥à¤°à¤¾à¤¯à¥‹à¤œà¤¿à¤¤",
    "guidance_title": "à¤—à¤°à¥à¤®à¥€ à¤®à¥‡à¤‚ à¤¯à¤¾à¤¤à¥à¤°à¤¾ à¤•à¥‡ à¤¸à¥à¤à¤¾à¤µ",
    "guidance_carry_water": "à¤¯à¤¾à¤¤à¥à¤°à¤¾ à¤•à¥‡ à¤²à¤¿à¤ à¤ªà¤¾à¤¨à¥€ à¤¸à¤¾à¤¥ à¤°à¤–à¥‡à¤‚à¥¤",
    "guidance_prefer_shade": "à¤œà¤¹à¤¾à¤ à¤¸à¤‚à¤­à¤µ à¤¹à¥‹, à¤›à¤¾à¤¯à¤¾à¤¦à¤¾à¤° à¤°à¤¾à¤¸à¥à¤¤à¤¾ à¤šà¥à¤¨à¥‡à¤‚à¥¤",
    "guidance_rest_cool": "à¤µà¤¿à¤°à¤¾à¤® à¤•à¥‡ à¤²à¤¿à¤ à¤ à¤‚à¤¡à¥€ à¤œà¤—à¤¹ à¤ªà¤° à¤°à¥à¤•à¥‡à¤‚à¥¤",
    "guidance_avoid_hottest": "à¤¸à¤®à¤¯ à¤®à¤¿à¤²à¥‡ à¤¤à¥‹ à¤¦à¤¿à¤¨ à¤•à¥‡ à¤¸à¤¬à¤¸à¥‡ à¤—à¤°à¥à¤® à¤˜à¤‚à¤Ÿà¥‹à¤‚ à¤¸à¥‡ à¤¬à¤šà¥‡à¤‚à¥¤",
    "status_loading_places": "à¤•à¥ˆà¤¶ à¤•à¥€ à¤—à¤ˆ à¤œà¤—à¤¹à¥‡à¤‚ à¤–à¥‹à¤œà¥€ à¤œà¤¾ à¤°à¤¹à¥€ à¤¹à¥ˆà¤‚â€¦",
    "status_no_places": "à¤‡à¤¸ à¤¨à¤¾à¤® à¤¸à¥‡ à¤•à¥‹à¤ˆ à¤œà¤—à¤¹ à¤¨à¤¹à¥€à¤‚ à¤®à¤¿à¤²à¥€à¥¤",
    "status_pick_required": "à¤®à¤¾à¤¨à¤šà¤¿à¤¤à¥à¤° à¤ªà¤° à¤¬à¤¿à¤‚à¤¦à¥ à¤šà¥à¤¨à¥‡à¤‚ à¤¯à¤¾ à¤¸à¥‚à¤šà¥€ à¤¸à¥‡ à¤œà¤—à¤¹ à¤šà¥à¤¨à¥‡à¤‚à¥¤",
    "status_loading_routes": "à¤•à¥ˆà¤¶ à¤•à¤¿à¤ à¤—à¤ à¤®à¤¾à¤°à¥à¤—à¥‹à¤‚ à¤•à¥€ à¤—à¤£à¤¨à¤¾ à¤¹à¥‹ à¤°à¤¹à¥€ à¤¹à¥ˆâ€¦",
    "status_route_ready": "à¤®à¤¾à¤°à¥à¤— à¤µà¤¿à¤•à¤²à¥à¤ª à¤¤à¥ˆà¤¯à¤¾à¤° à¤¹à¥ˆà¤‚à¥¤",
    "status_error_prefix": "à¤®à¤¾à¤°à¥à¤— à¤¨à¤¹à¥€à¤‚ à¤®à¤¿à¤²à¥‡: {message}",
    "status_stops_missing": "à¤ à¤¹à¤°à¤¾à¤µ à¤•à¥€ à¤œà¤¾à¤¨à¤•à¤¾à¤°à¥€ à¤‰à¤ªà¤²à¤¬à¥à¤§ à¤¨à¤¹à¥€à¤‚",
    "status_stops_empty": "à¤‡à¤¸ à¤®à¤¾à¤°à¥à¤— à¤ªà¤° OSM à¤®à¥‡à¤‚ à¤•à¥‹à¤ˆ à¤‰à¤ªà¤¯à¥à¤•à¥à¤¤ à¤ à¤¹à¤°à¤¾à¤µ à¤¦à¤°à¥à¤œ à¤¨à¤¹à¥€à¤‚ à¤¹à¥ˆ",
    "status_tile_error": "à¤®à¤¾à¤¨à¤šà¤¿à¤¤à¥à¤° à¤Ÿà¤¾à¤‡à¤²à¥‡à¤‚ à¤‰à¤ªà¤²à¤¬à¥à¤§ à¤¨à¤¹à¥€à¤‚ à¤¹à¥ˆà¤‚; à¤•à¥ˆà¤¶ à¤•à¤¿à¤ à¤—à¤ à¤®à¤¾à¤°à¥à¤— à¤”à¤° à¤¸à¤¡à¤¼à¤•à¥‡à¤‚ à¤•à¤¾à¤® à¤•à¤°à¥‡à¤‚à¤—à¥‡à¥¤",
    "mode_geometric": "à¤œà¥à¤¯à¤¾à¤®à¤¿à¤¤à¥€à¤¯ à¤›à¤¾à¤¯à¤¾ à¤®à¥‹à¤¡",
    "mode_estimated": "à¤…à¤¨à¥à¤®à¤¾à¤¨à¤¿à¤¤ à¤à¤•à¥à¤¸à¤ªà¥‹à¤œà¤¼à¤° à¤®à¥‹à¤¡",
    "nav_label": "à¤®à¥à¤–à¥à¤¯ à¤¨à¥‡à¤µà¤¿à¤—à¥‡à¤¶à¤¨",
    "planner_page": "à¤¯à¥‹à¤œà¤¨à¤¾",
    "citizen_page": "à¤¨à¤¾à¤—à¤°à¤¿à¤•",
    "place_search_label": "à¤œà¤—à¤¹ à¤–à¥‹à¤œà¤¨à¥‡ à¤•à¥‡ à¤¸à¥à¤à¤¾à¤µ",
    "places_loading": "à¤œà¤—à¤¹à¥‡à¤‚ à¤–à¥‹à¤œà¥€ à¤œà¤¾ à¤°à¤¹à¥€ à¤¹à¥ˆà¤‚â€¦",
    "places_error": "à¤œà¤—à¤¹ à¤–à¥‹à¤œà¤¨à¤¾ à¤‰à¤ªà¤²à¤¬à¥à¤§ à¤¨à¤¹à¥€à¤‚ à¤¹à¥ˆà¥¤ à¤®à¤¾à¤¨à¤šà¤¿à¤¤à¥à¤° à¤ªà¤° à¤¬à¤¿à¤‚à¤¦à¥ à¤šà¥à¤¨à¥‡à¤‚à¥¤",
    "places_no_match": "à¤‡à¤¸ à¤¨à¤¾à¤® à¤¸à¥‡ à¤•à¥‹à¤ˆ à¤œà¤—à¤¹ à¤¨à¤¹à¥€à¤‚ à¤®à¤¿à¤²à¥€à¥¤",
    "origin_required": "à¤¸à¥‚à¤šà¥€ à¤¸à¥‡ à¤¶à¥à¤°à¥à¤†à¤¤ à¤šà¥à¤¨à¥‡à¤‚ à¤¯à¤¾ à¤®à¤¾à¤¨à¤šà¤¿à¤¤à¥à¤° à¤ªà¤° à¤¬à¤¿à¤‚à¤¦à¥ à¤šà¥à¤¨à¥‡à¤‚à¥¤",
    "destination_required": "à¤¸à¥‚à¤šà¥€ à¤¸à¥‡ à¤®à¤‚à¤œà¤¼à¤¿à¤² à¤šà¥à¤¨à¥‡à¤‚ à¤¯à¤¾ à¤®à¤¾à¤¨à¤šà¤¿à¤¤à¥à¤° à¤ªà¤° à¤¬à¤¿à¤‚à¤¦à¥ à¤šà¥à¤¨à¥‡à¤‚à¥¤",
    "route_error_422": "à¤šà¥à¤¨à¥‡ à¤—à¤ à¤¬à¤¿à¤‚à¤¦à¥ à¤”à¤° à¤¸à¤®à¤¯ à¤œà¤¾à¤à¤šà¤•à¤° à¤«à¤¿à¤° à¤•à¥‹à¤¶à¤¿à¤¶ à¤•à¤°à¥‡à¤‚à¥¤",
    "route_error_area": "à¤à¤• à¤¯à¤¾ à¤¦à¥‹à¤¨à¥‹à¤‚ à¤¬à¤¿à¤‚à¤¦à¥ à¤®à¤¾à¤¨à¤šà¤¿à¤¤à¥à¤° à¤µà¤¾à¤²à¥‡ à¤•à¥à¤·à¥‡à¤¤à¥à¤° à¤¸à¥‡ à¤¬à¤¾à¤¹à¤° à¤¹à¥ˆà¤‚à¥¤ à¤¡à¥‡à¤®à¥‹ à¤•à¥à¤·à¥‡à¤¤à¥à¤° à¤•à¥‡ à¤­à¥€à¤¤à¤° à¤šà¥à¤¨à¥‡à¤‚à¥¤",
    "route_error_path": "à¤•à¥ˆà¤¶ à¤•à¤¿à¤ à¤—à¤ à¤¸à¤¡à¤¼à¤• à¤¡à¥‡à¤Ÿà¤¾ à¤®à¥‡à¤‚ à¤‡à¤¨ à¤¬à¤¿à¤‚à¤¦à¥à¤“à¤‚ à¤•à¥‡ à¤¬à¥€à¤š à¤ªà¥ˆà¤¦à¤² à¤®à¤¾à¤°à¥à¤— à¤¨à¤¹à¥€à¤‚ à¤®à¤¿à¤²à¤¾à¥¤",
    "route_error_generic": "à¤®à¤¾à¤°à¥à¤— à¤µà¤¿à¤•à¤²à¥à¤ª à¤¨à¤¹à¥€à¤‚ à¤®à¤¿à¤² à¤ªà¤¾à¤à¥¤ à¤«à¤¿à¤° à¤•à¥‹à¤¶à¤¿à¤¶ à¤•à¤°à¥‡à¤‚à¥¤",
    "map_pick_origin": "à¤¶à¥à¤°à¥à¤†à¤¤à¥€ à¤¬à¤¿à¤‚à¤¦à¥ à¤šà¥à¤¨ à¤°à¤¹à¥‡ à¤¹à¥ˆà¤‚à¥¤ à¤®à¤¾à¤¨à¤šà¤¿à¤¤à¥à¤° à¤ªà¤° à¤œà¤—à¤¹ à¤šà¥à¤¨à¥‡à¤‚à¥¤",
    "map_pick_destination": "à¤®à¤‚à¤œà¤¼à¤¿à¤² à¤šà¥à¤¨ à¤°à¤¹à¥‡ à¤¹à¥ˆà¤‚à¥¤ à¤®à¤¾à¤¨à¤šà¤¿à¤¤à¥à¤° à¤ªà¤° à¤œà¤—à¤¹ à¤šà¥à¤¨à¥‡à¤‚à¥¤",
    "stop_type_water": "à¤ªà¤¾à¤¨à¥€ à¤•à¤¾ à¤¸à¥à¤¥à¤¾à¤¨",
    "stop_type_cooling": "à¤ à¤‚à¤¡à¥€ à¤œà¤—à¤¹",
    "stop_type_shaded_public": "à¤›à¤¾à¤¯à¤¾à¤¦à¤¾à¤° à¤¸à¤¾à¤°à¥à¤µà¤œà¤¨à¤¿à¤• à¤œà¤—à¤¹",
    "stop_type_business": "à¤µà¥à¤¯à¤¾à¤ªà¤¾à¤°à¤¿à¤• à¤œà¤—à¤¹",
    "stop_type_other": "à¤¦à¤°à¥à¤œ à¤ à¤¹à¤°à¤¾à¤µ",
    "stops_unavailable": "à¤ à¤¹à¤°à¤¾à¤µ à¤•à¥€ à¤œà¤¾à¤¨à¤•à¤¾à¤°à¥€ à¤‰à¤ªà¤²à¤¬à¥à¤§ à¤¨à¤¹à¥€à¤‚",
    "stops_no_eligible": "à¤‡à¤¸ à¤®à¤¾à¤°à¥à¤— à¤ªà¤° OSM à¤®à¥‡à¤‚ à¤•à¥‹à¤ˆ à¤‰à¤ªà¤¯à¥à¤•à¥à¤¤ à¤ à¤¹à¤°à¤¾à¤µ à¤¦à¤°à¥à¤œ à¤¨à¤¹à¥€à¤‚ à¤¹à¥ˆ",
    "stops_available": "à¤‰à¤ªà¤²à¤¬à¥à¤§",
    "stop_distance_value": "{value} m",
    "extra_minutes_value": "{value} min",
    "same_route_fastest": "à¤¸à¤¬à¤¸à¥‡ à¤¤à¥‡à¤œà¤¼ à¤®à¤¾à¤°à¥à¤— à¤œà¥ˆà¤¸à¤¾",
    "recommendation_small": "à¤…à¤‚à¤¤à¤° à¤•à¤® à¤¹à¥ˆ ({percent}% à¤•à¤® à¤®à¥‰à¤¡à¤² à¤ªà¤° à¤†à¤§à¤¾à¤°à¤¿à¤¤ à¤—à¤°à¥à¤®à¥€ à¤•à¤¾ à¤…à¤¨à¥à¤®à¤¾à¤¨); à¤¸à¤¬à¤¸à¥‡ à¤¤à¥‡à¤œà¤¼ à¤®à¤¾à¤°à¥à¤— à¤‰à¤šà¤¿à¤¤ à¤µà¤¿à¤•à¤²à¥à¤ª à¤¹à¥ˆà¥¤",
    "recommendation_heat": "à¤—à¤°à¥à¤®à¥€ à¤•à¥‡ à¤¹à¤¿à¤¸à¤¾à¤¬ à¤µà¤¾à¤²à¤¾ à¤®à¤¾à¤°à¥à¤— à¤²à¤—à¤­à¤— {minutes} min à¤…à¤§à¤¿à¤• à¤²à¥‡à¤¤à¤¾ à¤¹à¥ˆ à¤”à¤° à¤—à¤°à¥à¤®à¥€ à¤•à¤¾ à¤®à¥‰à¤¡à¤² à¤ªà¤° à¤†à¤§à¤¾à¤°à¤¿à¤¤ à¤…à¤¨à¥à¤®à¤¾à¤¨ {percent}% à¤•à¤® à¤¹à¥ˆà¥¤",
    "recommendation_no_reduction": "à¤‡à¤¨ à¤µà¤¿à¤•à¤²à¥à¤ªà¥‹à¤‚ à¤®à¥‡à¤‚ à¤¸à¤¬à¤¸à¥‡ à¤¤à¥‡à¤œà¤¼ à¤®à¤¾à¤°à¥à¤— à¤•à¤¾ à¤®à¥‰à¤¡à¤² à¤ªà¤° à¤†à¤§à¤¾à¤°à¤¿à¤¤ à¤—à¤°à¥à¤®à¥€ à¤•à¤¾ à¤…à¤¨à¥à¤®à¤¾à¤¨ à¤¸à¤¬à¤¸à¥‡ à¤•à¤® à¤¹à¥ˆà¥¤",
    "no_heat_route": "à¤¤à¤¯ à¤…à¤¤à¤¿à¤°à¤¿à¤•à¥à¤¤ à¤¦à¥‚à¤°à¥€ à¤•à¥‡ à¤­à¥€à¤¤à¤° à¤•à¤® à¤…à¤¨à¥à¤®à¤¾à¤¨ à¤µà¤¾à¤²à¤¾ à¤…à¤²à¤— à¤®à¤¾à¤°à¥à¤— à¤¨à¤¹à¥€à¤‚ à¤®à¤¿à¤²à¤¾à¥¤",
    "empty_routes": "à¤‡à¤¨ à¤¬à¤¿à¤‚à¤¦à¥à¤“à¤‚ à¤•à¥‡ à¤²à¤¿à¤ à¤•à¥‹à¤ˆ à¤®à¤¾à¤°à¥à¤— à¤µà¤¿à¤•à¤²à¥à¤ª à¤‰à¤ªà¤²à¤¬à¥à¤§ à¤¨à¤¹à¥€à¤‚ à¤¹à¥ˆà¥¤",
    "selected_stop_status": "à¤®à¤¾à¤°à¥à¤— à¤•à¥‡ à¤ à¤¹à¤°à¤¾à¤µ OSM à¤®à¥‡à¤‚ à¤¦à¤°à¥à¤œ à¤¹à¥ˆà¤‚, à¤¸à¤¤à¥à¤¯à¤¾à¤ªà¤¿à¤¤ à¤¨à¤¹à¥€à¤‚à¥¤",
    "footer": "à¤•à¥‰à¤¨à¥à¤«à¤¼à¤¿à¤—à¤°à¥‡à¤¶à¤¨ {config_version} Â· à¤¸à¥à¤°à¥‹à¤¤: Â© OpenStreetMap contributors Â· à¤¡à¥‡à¤Ÿà¤¾ à¤¤à¤¾à¤°à¥€à¤–: {data_download_date}",
    "language_label": "à¤­à¤¾à¤·à¤¾",
    "language_english": "English",
    "language_hindi": "à¤¹à¤¿à¤¨à¥à¤¦à¥€",
    "summary_title": "à¤‡à¤¸ à¤¸à¤®à¤¯ à¤•à¥€ à¤—à¤°à¥à¤®à¥€ à¤•à¥€ à¤œà¤¾à¤¨à¤•à¤¾à¤°à¥€",
    "summary_before_location": "à¤œà¤—à¤¹ à¤šà¥à¤¨à¤¨à¥‡ à¤ªà¤° à¤¸à¤¡à¤¼à¤• à¤•à¥€ à¤œà¤¾à¤¨à¤•à¤¾à¤°à¥€ à¤¯à¤¹à¤¾à¤ à¤¦à¤¿à¤–à¥‡à¤—à¥€à¥¤",
    "summary_exposure_label": "à¤¸à¤¡à¤¼à¤• à¤•à¤¾ à¤¸à¥à¤¤à¤°",
    "summary_peak_label": "à¤•à¥à¤·à¥‡à¤¤à¥à¤° à¤•à¤¾ à¤¸à¤®à¤¯",
    "summary_water_label": "à¤ªà¤¾à¤¨à¥€ à¤¤à¤• à¤¦à¥‚à¤°à¥€",
    "summary_cooling_label": "à¤ à¤‚à¤¡à¥€ à¤œà¤—à¤¹ à¤¤à¤• à¤¦à¥‚à¤°à¥€",
    "summary_lower_route": "à¤•à¤® à¤®à¥‰à¤¡à¤² à¤ªà¤° à¤†à¤§à¤¾à¤°à¤¿à¤¤ à¤—à¤°à¥à¤®à¥€ à¤•à¥‡ à¤…à¤¨à¥à¤®à¤¾à¤¨ à¤µà¤¾à¤²à¤¾ à¤®à¤¾à¤°à¥à¤— à¤‰à¤ªà¤²à¤¬à¥à¤§ à¤¹à¥ˆà¥¤",
    "summary_no_lower_route": "à¤•à¤® à¤…à¤¨à¥à¤®à¤¾à¤¨ à¤µà¤¾à¤²à¤¾ à¤®à¤¾à¤°à¥à¤— à¤‰à¤ªà¤²à¤¬à¥à¤§ à¤¹à¥ˆ à¤¯à¤¾ à¤¨à¤¹à¥€à¤‚, à¤¯à¤¹ à¤œà¤¾à¤¨à¤¨à¥‡ à¤•à¥‡ à¤²à¤¿à¤ à¤®à¤¾à¤°à¥à¤— à¤–à¥‹à¤œà¥‡à¤‚à¥¤",
    "summary_level_low": "à¤•à¤®",
    "summary_level_moderate": "à¤®à¤§à¥à¤¯à¤®",
    "summary_level_high": "à¤œà¤¼à¥à¤¯à¤¾à¤¦à¤¾",
    "summary_peak_window": "à¤—à¤°à¥à¤®à¥€ à¤•à¤¾ à¤¸à¤¬à¤¸à¥‡ à¤Šà¤à¤šà¤¾ à¤®à¥‰à¤¡à¤² à¤ªà¤° à¤†à¤§à¤¾à¤°à¤¿à¤¤ à¤…à¤¨à¥à¤®à¤¾à¤¨ {start_time}â€“{end_time}",
    "summary_distance": "{value} m",
    "summary_data_unavailable": "à¤œà¤¾à¤¨à¤•à¤¾à¤°à¥€ à¤‰à¤ªà¤²à¤¬à¥à¤§ à¤¨à¤¹à¥€à¤‚ (à¤•à¥‹à¤ˆ à¤¸à¥à¤µà¤¿à¤§à¤¾ à¤¦à¤°à¥à¤œ à¤¨à¤¹à¥€à¤‚)",
    "summary_loading": "à¤¸à¤¡à¤¼à¤• à¤•à¥€ à¤œà¤¾à¤¨à¤•à¤¾à¤°à¥€ à¤²à¥‹à¤¡ à¤¹à¥‹ à¤°à¤¹à¥€ à¤¹à¥ˆâ€¦",
    "summary_error": "à¤‡à¤¸ à¤œà¤—à¤¹ à¤•à¥€ à¤œà¤¾à¤¨à¤•à¤¾à¤°à¥€ à¤‰à¤ªà¤²à¤¬à¥à¤§ à¤¨à¤¹à¥€à¤‚ à¤¹à¥ˆà¥¤",
    "summary_error_area": "à¤®à¤¾à¤¨à¤šà¤¿à¤¤à¥à¤° à¤µà¤¾à¤²à¥‡ à¤¡à¥‡à¤®à¥‹ à¤•à¥à¤·à¥‡à¤¤à¥à¤° à¤®à¥‡à¤‚, à¤¦à¤°à¥à¤œ à¤¸à¤¡à¤¼à¤• à¤•à¥‡ à¤ªà¤¾à¤¸ à¤•à¥€ à¤œà¤—à¤¹ à¤šà¥à¤¨à¥‡à¤‚à¥¤",
    "summary_status_modelled": "à¤®à¥‰à¤¡à¤² à¤ªà¤° à¤†à¤§à¤¾à¤°à¤¿à¤¤",
    "summary_status_estimated": "à¤…à¤¨à¥à¤®à¤¾à¤¨à¤¿à¤¤",
    "summary_status_interpolated": "à¤¬à¥€à¤š à¤•à¥‡ à¤¸à¤®à¤¯ à¤•à¤¾ à¤…à¤¨à¥à¤®à¤¾à¤¨",
    "summary_map_level": "à¤®à¤¾à¤¨à¤šà¤¿à¤¤à¥à¤° à¤ªà¤° à¤¶à¥à¤°à¥à¤†à¤¤à¥€ à¤œà¤—à¤¹ à¤šà¥à¤¨à¥‡à¤‚",
}

_WINDOWS_1252_BYTES = {
    0x20AC: 0x80, 0x201A: 0x82, 0x0192: 0x83, 0x201E: 0x84, 0x2026: 0x85,
    0x2020: 0x86, 0x2021: 0x87, 0x02C6: 0x88, 0x2030: 0x89, 0x0160: 0x8A,
    0x2039: 0x8B, 0x0152: 0x8C, 0x017D: 0x8E, 0x2018: 0x91, 0x2019: 0x92,
    0x201C: 0x93, 0x201D: 0x94, 0x2022: 0x95, 0x2013: 0x96, 0x2014: 0x97,
    0x02DC: 0x98, 0x2122: 0x99, 0x0161: 0x9A, 0x203A: 0x9B, 0x0153: 0x9C,
    0x017E: 0x9E, 0x0178: 0x9F,
}


def _restore_catalog_unicode(value: str) -> str:
    """Repair UTF-8 text decoded through the Windows console code page, if present."""
    raw = bytearray()
    for character in value:
        codepoint = ord(character)
        if codepoint in _WINDOWS_1252_BYTES:
            raw.append(_WINDOWS_1252_BYTES[codepoint])
        elif codepoint <= 0xFF:
            raw.append(codepoint)
        else:
            return value
    try:
        restored = raw.decode("utf-8")
    except UnicodeDecodeError:
        return value
    return restored


CITIZEN_EN = {key: _restore_catalog_unicode(value) for key, value in CITIZEN_EN.items()}
CITIZEN_HI = {key: _restore_catalog_unicode(value) for key, value in _CITIZEN_HI_BASE.items()}
CITIZEN_HI.update({
    "nav_planner": "प्लानर",
    "intro": "पहले से तैयार मार्गों की तुलना करें और अपनी यात्रा के लिए सही विकल्प चुनें।",
    "title": "गर्मी के मॉडल अनुमान के साथ अपना रास्ता चुनें",
    "map_fallback": "मानचित्र की पृष्ठभूमि न खुले, तब भी सहेजी हुई सड़कें दिखेंगी।",
    "status_tile_error": "मानचित्र की पृष्ठभूमि उपलब्ध नहीं है; सहेजे हुए मार्ग और सड़कें काम करेंगे।",
    "status_loading_places": "जगहें खोजी जा रही हैं…",
    "status_loading_routes": "मार्गों की गणना हो रही है…",
    "route_error_path": "सड़क डेटा में इन बिंदुओं के बीच पैदल मार्ग नहीं मिला।",
    "weighted_shade": "मार्ग पर औसत छाया",
    "modelled_estimate": "यह मॉडल का अनुमान है, सुरक्षा की गारंटी नहीं; वास्तविक स्थिति अलग हो सकती है।",
    "summary_title": "चुने हुए समय के लिए गर्मी की जानकारी",
    "summary_exposure_label": "इस सड़क पर गर्मी का स्तर",
    "summary_peak_label": "क्षेत्र में सबसे गर्म समय",
    "summary_peak_window": "क्षेत्र में गर्मी का मॉडल-अनुमान सबसे अधिक: {start_time}–{end_time}",
    "summary_level_high": "अधिक",
    "no_heat_route": "तय अतिरिक्त समय की सीमा के भीतर कम अनुमान वाला अलग मार्ग नहीं मिला।",
    "guidance_rest_cool": "आराम के लिए ठंडी जगह पर रुकें।",
    "guidance_avoid_hottest": "यदि संभव हो, दिन के सबसे गर्म घंटों से बचें।",
    "minutes": "मिनट",
    "metres": "मीटर",
    "stop_distance_value": "{value} मीटर",
    "extra_minutes_value": "{value} मिनट",
    "summary_distance": "{value} मीटर",
    "recommendation_heat": "गर्मी के हिसाब वाला मार्ग लगभग {minutes} मिनट अधिक लेता है और गर्मी का मॉडल पर आधारित अनुमान {percent}% कम है।",
})
CITIZEN_HI["footer"] = CITIZEN_HI["footer"].replace("डेटा तारीख", "डेटा डाउनलोड की तारीख")
CITIZEN_HI = {
    key: value.replace("कैश किए गए", "सहेजे हुए").replace("कैश की गई", "सहेजी हुई")
    for key, value in CITIZEN_HI.items()
}

# Shared Copilot controls.  They deliberately live with the citizen catalog so
# both public views use one reviewed English/Hindi source for the new UI.
CITIZEN_EN.update({
    "nav_caption_authorities": "For authorities",
    "nav_caption_citizens": "For citizens",
    "language_short_english": "EN",
    "language_short_hindi": "हिं",
    "flow_label": "Four-step trip flow",
    "flow_where": "Where",
    "flow_when": "When",
    "flow_compare": "Compare routes",
    "flow_stops": "Stops and tips",
    "summary_eyebrow": "Your trip heat overview",
    "recommended": "Recommended",
    "copilot_button": "Agni",
    "copilot_panel_title": "Agni",
    "copilot_subtitle": "HeatShield assistant",
    "copilot_open": "Open Agni assistant",
    "copilot_close": "Close Agni",
    "copilot_conversation": "Agni conversation",
    "copilot_context_none": "Agni uses: current view",
    "copilot_context_street": "Agni uses: Street {name} at {time}",
    "copilot_context_route": "Agni uses: Route {origin} → {destination} at {time}",
    "copilot_context_plan": "Agni uses: Plan {water}/{cooling}/{shade}",
    "copilot_examples": "Example questions",
    "copilot_example_risk": "Why is this street high risk?",
    "copilot_example_plan": "Explain the current resource plan.",
    "copilot_example_data": "How were building heights estimated?",
    "copilot_example_platform": "How do I use the time slider?",
    "copilot_example_route": "How do I compare route options?",
    "copilot_example_break": "I need a break along my current route.",
    "copilot_example_heat": "Mujhe route mein heat se bachne ke liye kya karna chahiye?",
    "copilot_example_height": "How were building heights estimated?",
    "copilot_input_label": "Ask Agni",
    "copilot_input_placeholder": "Ask about the current model results",
    "copilot_send": "Send",
    "copilot_clear": "Clear conversation",
    "copilot_character_count": "{count}/500",
    "copilot_loading": "Agni is checking model data…",
    "copilot_empty_greeting": "Hi, I’m Agni. Ask about the current model results or choose an example below.",
    "copilot_template": "Template answer",
    "copilot_ai_assisted": "AI-assisted, fact-checked",
    "copilot_data_unavailable": "Data unavailable",
    "copilot_facts_title": "Facts and assumptions used",
    "copilot_facts": "Facts used",
    "copilot_assumptions": "Assumptions",
    "copilot_no_facts": "No cached facts were returned.",
    "copilot_retry": "Retry",
    "copilot_error_network": "Agni could not be reached. The platform still works without it.",
    "copilot_error_timeout": "Agni took too long to respond. The platform still works without it.",
    "copilot_error_422": "Your message is too long. Keep it to 500 characters.",
    "copilot_error_unavailable": "Agni is unavailable. The platform still works without it.",
    "copilot_footer": "Agni explains model results; it does not diagnose or give medical advice.",
})
CITIZEN_HI.update({
    "nav_caption_authorities": "अधिकारियों के लिए",
    "nav_caption_citizens": "नागरिकों के लिए",
    "language_short_english": "EN",
    "language_short_hindi": "हिं",
    "flow_label": "यात्रा के चार चरण",
    "flow_where": "कहाँ",
    "flow_when": "कब",
    "flow_compare": "मार्ग तुलना",
    "flow_stops": "ठहराव और सुझाव",
    "summary_eyebrow": "आपकी यात्रा की गर्मी जानकारी",
    "recommended": "सुझाया गया",
    "copilot_button": "अग्नि",
    "copilot_panel_title": "अग्नि",
    "copilot_subtitle": "HeatShield सहायक",
    "copilot_open": "अग्नि सहायक खोलें",
    "copilot_close": "अग्नि बंद करें",
    "copilot_conversation": "अग्नि बातचीत",
    "copilot_context_none": "अग्नि उपयोग करती है: मौजूदा दृश्य",
    "copilot_context_street": "अग्नि उपयोग करती है: सड़क {name}, {time} पर",
    "copilot_context_route": "अग्नि उपयोग करती है: मार्ग {origin} → {destination}, {time} पर",
    "copilot_context_plan": "अग्नि उपयोग करती है: योजना {water}/{cooling}/{shade}",
    "copilot_examples": "उदाहरण प्रश्न",
    "copilot_example_risk": "इस सड़क पर जोखिम अधिक क्यों है?",
    "copilot_example_plan": "मौजूदा संसाधन योजना समझाइए।",
    "copilot_example_data": "इमारतों की ऊंचाई का अनुमान कैसे लगाया गया?",
    "copilot_example_platform": "समय स्लाइडर का उपयोग कैसे करूं?",
    "copilot_example_route": "मार्ग विकल्पों की तुलना कैसे करूं?",
    "copilot_example_break": "मौजूदा मार्ग पर मुझे विश्राम की जगह चाहिए।",
    "copilot_example_heat": "मुझे route में heat से बचने के लिए क्या करना चाहिए?",
    "copilot_example_height": "इमारतों की ऊंचाई का अनुमान कैसे लगाया गया?",
    "copilot_input_label": "अग्नि से पूछें",
    "copilot_input_placeholder": "मौजूदा मॉडल नतीजों के बारे में पूछें",
    "copilot_send": "भेजें",
    "copilot_clear": "बातचीत साफ़ करें",
    "copilot_character_count": "{count}/500 वर्ण",
    "copilot_loading": "अग्नि मॉडल डेटा देख रही है…",
    "copilot_empty_greeting": "नमस्ते, मैं अग्नि हूँ। मौजूदा मॉडल नतीजों के बारे में पूछें या नीचे से एक उदाहरण चुनें।",
    "copilot_template": "टेम्पलेट उत्तर",
    "copilot_ai_assisted": "AI-सहायित, तथ्य-जांचा हुआ",
    "copilot_data_unavailable": "डेटा उपलब्ध नहीं है",
    "copilot_facts_title": "इस्तेमाल किए गए तथ्य और मान्यताएं",
    "copilot_facts": "इस्तेमाल किए गए तथ्य",
    "copilot_assumptions": "मान्यताएं",
    "copilot_no_facts": "सहेजे हुए तथ्य नहीं मिले।",
    "copilot_retry": "फिर से कोशिश करें",
    "copilot_error_network": "अग्नि से संपर्क नहीं हो सका। प्लेटफ़ॉर्म इसके बिना भी काम करता है।",
    "copilot_error_timeout": "अग्नि के उत्तर में बहुत समय लगा। प्लेटफ़ॉर्म इसके बिना भी काम करता है।",
    "copilot_error_422": "आपका संदेश बहुत लंबा है। इसे 500 वर्णों तक रखें।",
    "copilot_error_unavailable": "अग्नि उपलब्ध नहीं है। प्लेटफ़ॉर्म इसके बिना भी काम करता है।",
    "copilot_footer": "अग्नि मॉडल के नतीजे समझाती है; यह चिकित्सा संबंधी सलाह नहीं देती।",
})


CITIZEN_REQUIRED_IDS = frozenset("""
    page_title brand_name meta_description header_context nav_planner nav_citizen nav_caption_authorities nav_caption_citizens eyebrow title intro route_planner_title
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
    stop_type_water stop_type_cooling stop_type_shaded_public stop_type_business stop_type_other stops_unavailable stops_available
    stops_no_eligible stop_distance_value extra_minutes_value same_route_fastest recommendation_small
    recommendation_heat recommendation_no_reduction no_heat_route empty_routes selected_stop_status footer
    language_label language_english language_hindi language_short_english language_short_hindi flow_label flow_where flow_when flow_compare flow_stops recommended summary_eyebrow summary_title summary_before_location summary_exposure_label
    summary_peak_label summary_water_label summary_cooling_label summary_lower_route summary_no_lower_route
    summary_level_low summary_level_moderate summary_level_high summary_peak_window summary_distance
    summary_data_unavailable summary_loading summary_error summary_error_area summary_status_modelled summary_status_estimated
    summary_status_interpolated summary_map_level
    copilot_button copilot_panel_title copilot_subtitle copilot_open copilot_close copilot_conversation copilot_context_none copilot_context_street
    copilot_context_route copilot_context_plan copilot_examples copilot_example_risk copilot_example_plan
    copilot_example_data copilot_example_platform copilot_example_route copilot_example_break copilot_example_heat
    copilot_example_height copilot_input_label copilot_input_placeholder copilot_send copilot_clear
    copilot_character_count copilot_loading copilot_empty_greeting copilot_template copilot_ai_assisted copilot_data_unavailable
    copilot_facts_title copilot_facts copilot_assumptions copilot_no_facts copilot_retry copilot_error_network
    copilot_error_timeout copilot_error_422 copilot_error_unavailable copilot_footer
""".split())


def validate_citizen_i18n() -> None:
    """Fail fast if the English catalog is incomplete or unsafe for this view."""
    missing = CITIZEN_REQUIRED_IDS - CITIZEN_EN.keys()
    if missing:
        raise ValueError(f"Citizen English strings are missing ids: {', '.join(sorted(missing))}")
    if CITIZEN_HI.keys() != CITIZEN_EN.keys():
        raise ValueError("English and Hindi citizen catalogs must contain the same ids.")
    if any(not isinstance(value, str) or not value.strip() for value in (*CITIZEN_EN.values(), *CITIZEN_HI.values())):
        raise ValueError("Citizen catalogs must not contain empty strings.")
    for key in CITIZEN_EN:
        english_placeholders = set(re.findall(r"\{([a-zA-Z0-9_]+)\}", CITIZEN_EN[key]))
        hindi_placeholders = set(re.findall(r"\{([a-zA-Z0-9_]+)\}", CITIZEN_HI[key]))
        if english_placeholders != hindi_placeholders:
            raise ValueError(f"Citizen placeholder mismatch for '{key}'.")
    forbidden = ("heatstroke", "prevent", "safe route")
    for key, value in CITIZEN_EN.items():
        if any(word in value.casefold() for word in forbidden):
            raise ValueError(f"Citizen English string '{key}' contains prohibited wording.")
    forbidden_hindi = tuple(_restore_catalog_unicode(value) for value in (
        "à¤¸à¥à¤°à¤•à¥à¤·à¤¿à¤¤ à¤®à¤¾à¤°à¥à¤—", "à¤¸à¥à¤°à¤•à¥à¤·à¤¿à¤¤ à¤°à¤¾à¤¸à¥à¤¤à¤¾", "à¤¹à¥€à¤Ÿà¤¸à¥à¤Ÿà¥à¤°à¥‹à¤•",
        "à¤¬à¤šà¤¾à¤µ à¤•à¥€ à¤—à¤¾à¤°à¤‚à¤Ÿà¥€", "à¤‡à¤²à¤¾à¤œ", "à¤¦à¤µà¤¾", "à¤¨à¤¿à¤¦à¤¾à¤¨",
    ))
    for key, value in CITIZEN_HI.items():
        if any(word in value.casefold() for word in forbidden_hindi):
            raise ValueError(f"Citizen Hindi string '{key}' contains prohibited wording.")
    latin_only = {"brand_name", "language_english", "language_short_english", "osm_attribution", "minutes", "metres", "stop_distance_value", "extra_minutes_value", "summary_distance"}
    for key, value in CITIZEN_HI.items():
        if key not in latin_only and not any("\u0900" <= character <= "\u097f" for character in value):
            raise ValueError(f"Citizen Hindi string '{key}' has no Devanagari text.")
