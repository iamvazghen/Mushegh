"""Google Maps — live travel times + place lookup (grounds every travel/logistics turn).

``travel_time`` answers "how long to the airport right now" with live traffic;
``find_place`` answers "a good sushi place near Alexanderplatz". Read-only, so neither is
confirm-gated. Degrades to a spoken note without MUSHEGH_GOOGLE_MAPS_API_KEY.
"""

from __future__ import annotations

from mushegh.config import settings
from mushegh.brain.tools.base import http_post, missing_arg, not_configured, tool_error

# The legacy Directions and Places (textsearch) endpoints cannot be enabled on Google Cloud
# projects created after 2025-03-01, so a fresh key only works against Routes + Places (New).
_NEEDS = "a Google Maps API key (MUSHEGH_GOOGLE_MAPS_API_KEY, Routes API + Places API (New) enabled)"
_TRAVEL_MODE = {"driving": "DRIVE", "walking": "WALK", "bicycling": "BICYCLE", "transit": "TRANSIT"}


def _headers(field_mask: str) -> dict:
    # Key in a header, not the query string, so it never lands in an httpx/loguru URL line.
    return {"X-Goog-Api-Key": settings.google_maps_api_key or "", "X-Goog-FieldMask": field_mask}


def _configured() -> bool:
    return bool(settings.google_maps_api_key)


async def travel_time(args: dict) -> str:
    """One travel-time tool, two engines: Google Directions (LIVE traffic) when the key is set,
    else the keyless OSRM route in tools/utility.py (no traffic, but never dark). The registry
    exposes only THIS one — utility's own schema entry was retired to avoid a duplicate name."""
    if not _configured():
        from mushegh.brain.tools.utility import osrm_travel_time
        return await osrm_travel_time(args)
    origin = (args.get("origin") or args.get("from") or "").strip()
    dest = (args.get("destination") or args.get("to") or "").strip()
    mode = {"drive": "driving", "walk": "walking", "bike": "bicycling"}.get(
        (args.get("mode") or "driving").strip().lower(), (args.get("mode") or "driving").strip().lower())
    if not dest:
        return missing_arg("travel_time", args, "destination", "dest", "to", "address", "mode",
                           ask="Where to, sir?")
    if not origin:
        origin = settings.owner_home_address or ""
    if not origin:
        from mushegh.brain import prefs
        origin = prefs.home_location() or ""
    if not origin:
        return ("I need a starting point, sir — or set your home location "
                "(say 'set my home to <place>').")
    try:
        travel = _TRAVEL_MODE.get(mode, "DRIVE")
        body = {"origin": {"address": origin}, "destination": {"address": dest},
                "travelMode": travel}
        if travel == "DRIVE":
            body["routingPreference"] = "TRAFFIC_AWARE"   # duration then includes live traffic
        r = await http_post(
            "https://routes.googleapis.com/directions/v2:computeRoutes", json=body,
            headers=_headers("routes.description,routes.localizedValues"))
        routes = r.json().get("routes") or []
        if not routes:
            return f"I couldn't find a route to {dest}, sir."
        local = routes[0].get("localizedValues") or {}
        dur = (local.get("duration") or {}).get("text", "unknown")
        dist = (local.get("distance") or {}).get("text", "")
        via = routes[0].get("description", "")
        return (f"{dur} to {dest} right now, sir"
                + (f" ({dist}" + (f", via {via})" if via else ")") if dist else "") + ".")
    except Exception as e:  # noqa: BLE001
        return tool_error("travel time", e)


async def find_place(args: dict) -> str:
    if not _configured():
        return not_configured("Google Maps", _NEEDS)
    query = (args.get("query") or "").strip()
    if not query:
        return missing_arg("find_place", args, "query", "place", "search", "text",
                           ask="What should I look for, sir?")
    try:
        r = await http_post(
            "https://places.googleapis.com/v1/places:searchText",
            json={"textQuery": query, "pageSize": 3},
            headers=_headers("places.displayName,places.formattedAddress,places.rating"))
        results = (r.json().get("places") or [])[:3]
        if not results:
            return f"Nothing found for '{query}', sir."
        lines = []
        for p in results:
            bits = [(p.get("displayName") or {}).get("text", "?")]
            if p.get("rating"):
                bits.append(f"{p['rating']}★")
            if p.get("formattedAddress"):
                bits.append(p["formattedAddress"])
            lines.append(", ".join(bits))
        return "Top matches, sir: " + "; ".join(lines) + "."
    except Exception as e:  # noqa: BLE001
        return tool_error("place search", e)


SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "travel_time",
            "description": ("LIVE travel time with current traffic — 'how long to the airport now', "
                            "'when should I leave for X'. Origin defaults to home if configured."),
            "parameters": {
                "type": "object",
                "properties": {
                    "origin": {"type": "string", "description": "Start address/place (default: home)."},
                    "destination": {"type": "string", "description": "Where the owner is going."},
                    "mode": {"type": "string", "enum": ["driving", "walking", "bicycling", "transit"]},
                },
                "required": ["destination"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "find_place",
            "description": ("Find real places — restaurants, shops, gyms, addresses — with ratings "
                            "and opening info. Use for 'find a sushi place near Alexanderplatz', "
                            "'gyms around here'. For how long it takes to get there, use "
                            "travel_time."),
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string", "description": "What + where."}},
                "required": ["query"],
            },
        },
    },
]

HANDLERS = {"travel_time": travel_time, "find_place": find_place}
