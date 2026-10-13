"""Open maps — travel time and place search on OpenStreetMap services, no key, no billing.

The engine `maps.py` uses when no Google key is set. One service per job, each the best open
option for that job, each with a fallback:

  geocoding   Nominatim (OSMF) -> Photon (komoot)
  driving     OSRM demo        -> Valhalla (FOSSGIS)
  walk / bike Valhalla         (the OSRM demo server only carries the car profile)
  transit     Transitous (MOTIS, community-run, Europe-wide GTFS)
  places      Nominatim in a box around the anchor -> Overpass around it -> Photon text search

Order is by measurement from the VPS, 2026-10-13: Nominatim 0.16-0.3 s, Photon 2.5-3 s, OSRM
0.8 s, Valhalla 1.1 s, Transitous 1.4 s, Overpass 1-8 s or a 504 when busy. Nominatim's policy is
one request a second, so its calls are spaced and every geocode is cached for a week (places do
not move; the home address would otherwise be looked up on every question).

What open data cannot give: live traffic (driving times are free-flow) and ratings/reviews.
"""

from __future__ import annotations

import asyncio
import json
import math
import re
import time
from datetime import datetime
from zoneinfo import ZoneInfo

from mushegh.brain.cache import CACHE
from mushegh.brain.tools.base import HttpPolicy, http_get, http_post, missing_arg, register_policy, \
    tool_error

PHOTON = "https://photon.komoot.io/api/"
NOMINATIM = "https://nominatim.openstreetmap.org/search"
OSRM = "https://router.project-osrm.org/route/v1/driving/"
VALHALLA = "https://valhalla1.openstreetmap.de/route"
TRANSITOUS = "https://api.transitous.org/api/v1/plan"
# ponytail: one Overpass host. The public mirrors (private.coffee, kumi) timed out on every probe
# 2026-10-13; Photon is the fallback instead. Add a mirror here if one proves reliable.
OVERPASS = "https://overpass-api.de/api/interpreter"
#: Seconds between Nominatim calls (its usage policy: at most one per second).
NOMINATIM_GAP = 1.0
_nominatim_last = 0.0

for _host, _pol in {
    "photon.komoot.io": HttpPolicy(6.0, 0, "the fallback geocoder; already slow, so no retry"),
    "nominatim.openstreetmap.org": HttpPolicy(5.0, 0, "its usage policy is one request per "
                                                      "second, so a retry is Photon's job"),
    "router.project-osrm.org": HttpPolicy(10.0, 1, "idempotent route query"),
    "valhalla1.openstreetmap.de": HttpPolicy(15.0, 1, "idempotent route query"),
    "api.transitous.org": HttpPolicy(20.0, 1, "idempotent journey query; it is slower than a "
                                              "road route because it searches timetables"),
    "overpass-api.de": HttpPolicy(6.0, 0, "a busy Overpass refuses rather than slows; Photon "
                                          "is the retry, and a voice answer cannot wait 15 s"),
}.items():
    register_policy(_host, _pol)

_MODES = {"drive": "driving", "driving": "driving", "car": "driving",
          "walk": "walking", "walking": "walking", "foot": "walking",
          "bike": "bicycling", "bicycling": "bicycling", "cycling": "bicycling", "cycle": "bicycling",
          "transit": "transit", "public transport": "transit", "train": "transit", "bus": "transit"}
_VALHALLA_COSTING = {"driving": "auto", "walking": "pedestrian", "bicycling": "bicycle"}
_VERB = {"driving": "by car", "walking": "on foot", "bicycling": "by bike"}
#: Spoken words that are not the OSM tag value. Small on purpose; a miss falls through.
_TAG_SYNONYMS = {"gym": "fitness_centre", "coffee": "cafe", "petrol": "fuel", "gas station": "fuel",
                 "atm": "atm", "doctor": "doctors", "chemist": "pharmacy", "drugstore": "pharmacy",
                 "grocery": "supermarket", "bar": "bar|pub", "hotel": "hotel|hostel"}


async def _nominatim(params: dict) -> list:
    global _nominatim_last
    # ponytail: spacing by timestamp, not a lock - one owner, rarely two lookups in flight.
    wait = _nominatim_last + NOMINATIM_GAP - time.monotonic()
    if wait > 0:
        await asyncio.sleep(wait)
    _nominatim_last = time.monotonic()
    return (await http_get(NOMINATIM, params={"format": "jsonv2", **params})).json()


async def _geocode_uncached(text: str) -> dict | None:
    try:
        hits = await _nominatim({"q": text, "limit": 1})
        if hits:
            return {"name": hits[0].get("name") or text, "lat": float(hits[0]["lat"]),
                    "lon": float(hits[0]["lon"])}
    except Exception:  # noqa: BLE001 - fall through to Photon
        pass
    try:
        feats = (await http_get(PHOTON, params={"q": text, "limit": 1})).json().get("features") or []
        if feats:
            lon, lat = feats[0]["geometry"]["coordinates"]
            p = feats[0].get("properties") or {}
            return {"name": p.get("name") or text, "lat": lat, "lon": lon}
    except Exception:  # noqa: BLE001
        pass
    return None


async def geocode(text: str) -> dict | None:
    """{name, lat, lon} for a place name or address. Nominatim, then Photon; cached a week."""
    text = (text or "").strip()
    if not text:
        return None

    async def fetch() -> str:
        hit = await _geocode_uncached(text)
        return json.dumps(hit) if hit else ""    # "" is not cached: a miss is retried next time

    raw = await CACHE.cached("geo", text.lower(), ttl=7 * 86400, factory=fetch)
    return json.loads(raw) if raw else None


def _dur(secs: float) -> str:
    mins = max(1, round(secs / 60))
    if mins >= 60:
        return f"{mins // 60}h {mins % 60}m"
    return f"{mins} minute{'s' if mins != 1 else ''}"


def _metres(a: dict, lat: float, lon: float) -> float:
    dx = math.radians(lon - a["lon"]) * math.cos(math.radians((lat + a["lat"]) / 2))
    return 6_371_000 * math.hypot(dx, math.radians(lat - a["lat"]))


async def _osrm(o: dict, d: dict) -> tuple[float, float] | None:
    r = await http_get(f"{OSRM}{o['lon']},{o['lat']};{d['lon']},{d['lat']}",
                       params={"overview": "false"})
    routes = r.json().get("routes") or []
    return (routes[0]["duration"], routes[0]["distance"] / 1000) if routes else None


async def _valhalla(o: dict, d: dict, mode: str) -> tuple[float, float] | None:
    r = await http_post(VALHALLA, json={
        "locations": [{"lat": o["lat"], "lon": o["lon"]}, {"lat": d["lat"], "lon": d["lon"]}],
        "costing": _VALHALLA_COSTING[mode], "directions_options": {"units": "kilometers"}})
    s = (r.json().get("trip") or {}).get("summary") or {}
    return (s["time"], s["length"]) if "time" in s else None


def _clock(iso: str) -> str:
    from mushegh.config import settings
    t = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    return t.astimezone(ZoneInfo(settings.user_tz or "UTC")).strftime("%H:%M")


async def _transit(o: dict, d: dict) -> str | None:
    r = await http_get(TRANSITOUS, params={"fromPlace": f"{o['lat']},{o['lon']}",
                                           "toPlace": f"{d['lat']},{d['lon']}"})
    its = r.json().get("itineraries") or []
    if not its:
        return None
    it = its[0]
    steps = []
    for leg in it.get("legs") or []:
        if leg.get("mode") == "WALK":
            if leg.get("duration", 0) >= 180:      # a two-minute platform change is not news
                steps.append(f"walk {_dur(leg['duration'])}")
            continue
        line = leg.get("routeShortName") or leg.get("mode", "").replace("_", " ").lower()
        stop = (leg.get("to") or {}).get("name", "")
        steps.append(f"{line} at {_clock(leg['startTime'])} to {stop}")
    return (f"{_dur(it['duration'])} by public transport, sir — leave at "
            f"{_clock(it['startTime'])}, arrive {_clock(it['endTime'])}: " + ", then ".join(steps) + ".")


async def travel_time(args: dict) -> str:
    """Travel time by car, foot, bike or public transport, all on open services."""
    dest = (args.get("to") or args.get("destination") or "").strip()
    if not dest:
        return missing_arg("travel_time", args, "to", "destination", "from", "origin", "mode",
                           ask="Where to, sir?")
    origin = (args.get("from") or args.get("origin") or "").strip()
    if not origin:
        from mushegh.config import settings
        origin = settings.owner_home_address or ""
    if not origin:
        from mushegh.brain import prefs
        origin = prefs.home_location() or ""
    if not origin:
        return ("From where, sir? Give me a starting point, or set your home location "
                "(say 'set my home to <place>').")
    mode = _MODES.get((args.get("mode") or "driving").strip().lower(), "driving")

    async def fetch() -> str:
        o, d = await geocode(origin), await geocode(dest)
        if not o:
            return f"I couldn't find '{origin}', sir."
        if not d:
            return f"I couldn't find '{dest}', sir."
        if mode == "transit":
            return (await _transit(o, d)
                    or f"I couldn't find a public transport connection to {d['name']}, sir.")
        got = None
        if mode == "driving":
            try:
                got = await _osrm(o, d)
            except Exception:  # noqa: BLE001 — Valhalla below
                got = None
        if got is None:
            got = await _valhalla(o, d, mode)
        if got is None:
            return f"I couldn't find a route from {o['name']} to {d['name']}, sir."
        secs, km = got
        note = " without live traffic" if mode == "driving" else ""
        return (f"About {_dur(secs)} {_VERB[mode]} from {o['name']} to {d['name']}{note}, sir — "
                f"roughly {km:.0f} km.")

    try:
        # Transit answers depend on the minute you ask; roads do not change in ten.
        ttl = 60 if mode == "transit" else 600
        return await CACHE.cached("travel", f"{origin}|{dest}|{mode}".lower(), ttl=ttl, factory=fetch)
    except Exception as e:  # noqa: BLE001
        return tool_error("travel time", e)


def _split(query: str) -> tuple[str, str]:
    """'sushi near Alexanderplatz' -> ('sushi', 'Alexanderplatz'); no anchor -> (query, '')."""
    low = f" {query.lower()} "
    for sep in (" near ", " around ", " close to ", " in "):
        i = low.rfind(sep)
        if i > 0:
            return query[:i - 1].strip(), query[i - 1 + len(sep):].strip()
    return query.strip(), ""


def _overpass_query(what: str, lat: float, lon: float, radius: int) -> str:
    # Spoken text goes into an OverpassQL regex: keep letters, digits, spaces and hyphens only.
    w = re.sub(r"[^\w\s-]", "", what.lower()).strip()
    tag = _TAG_SYNONYMS.get(w, w.replace(" ", "_"))
    around = f"(around:{radius},{lat},{lon})"
    return (f"[out:json][timeout:5];("
            f'nwr{around}[name~"{w}",i];'
            f'nwr{around}[cuisine~"{tag}",i];'
            f'nwr{around}[amenity~"^({tag})$",i];'
            f'nwr{around}[shop~"^({tag})$",i];'
            f'nwr{around}[leisure~"^({tag})$",i];'
            f'nwr{around}[tourism~"^({tag})$",i];'
            f");out center tags 30;")


def _describe(tags: dict) -> str:
    bits = [tags.get("name", "?")]
    street = " ".join(x for x in (tags.get("addr:street"), tags.get("addr:housenumber")) if x)
    if street:
        bits.append(street)
    if tags.get("opening_hours"):
        bits.append(f"open {tags['opening_hours']}")
    return ", ".join(bits)


def _nearest(at: dict, items: list[tuple[dict, float, float]]) -> list[str]:
    """(tags, lat, lon) -> the three nearest named ones, spoken with their distance."""
    named = sorted(((_metres(at, la, lo), tags) for tags, la, lo in items if tags.get("name")),
                   key=lambda x: x[0])
    out: list[str] = []
    seen: set[str] = set()
    for m, tags in named:
        line = _describe(tags)
        if line in seen:                  # one place mapped twice (node + building) is one place
            continue
        seen.add(line)
        out.append(f"{line} ({round(m / 50) * 50:.0f} m)" if m < 1000 else f"{line} ({m / 1000:.1f} km)")
        if len(out) == 3:
            break
    return out


async def _nominatim_near(what: str, at: dict, radius: int = 1500) -> list[str]:
    """Nominatim inside a box around the anchor: names and categories ('pharmacy', 'cafe'), with
    opening hours from extratags. Fast; blind to some categories (gyms), which Overpass covers."""
    w = re.sub(r"[^\w\s-]", "", what.lower()).strip()
    term = _TAG_SYNONYMS.get(w, w).split("|")[0].replace("_", " ")
    dlat = radius / 111_000
    dlon = dlat / max(0.1, math.cos(math.radians(at["lat"])))
    hits = await _nominatim({"q": term, "limit": 10, "bounded": 1, "addressdetails": 1,
                             "extratags": 1, "viewbox": f"{at['lon'] - dlon},{at['lat'] + dlat},"
                                                        f"{at['lon'] + dlon},{at['lat'] - dlat}"})
    items = []
    for h in hits:
        addr, extra = h.get("address") or {}, h.get("extratags") or {}
        tags = {"name": h.get("name"), "addr:street": addr.get("road"),
                "addr:housenumber": addr.get("house_number"),
                "opening_hours": extra.get("opening_hours")}
        items.append(({k: v for k, v in tags.items() if v}, float(h["lat"]), float(h["lon"])))
    return _nearest(at, items)


async def _overpass(what: str, at: dict, radius: int = 1500) -> list[str]:
    q = _overpass_query(what, at["lat"], at["lon"], radius)
    els = (await http_post(OVERPASS, data={"data": q})).json().get("elements") or []
    return _nearest(at, [(e.get("tags") or {}, (e.get("center") or e).get("lat", at["lat"]),
                          (e.get("center") or e).get("lon", at["lon"])) for e in els])


async def _photon(query: str, near: dict | None) -> list[str]:
    params: dict = {"q": query, "limit": 3}
    if near:
        params.update(lat=near["lat"], lon=near["lon"])
    feats = (await http_get(PHOTON, params=params)).json().get("features") or []
    out = []
    for f in feats:
        p = f.get("properties") or {}
        where = ", ".join(x for x in (" ".join(y for y in (p.get("street"), p.get("housenumber")) if y),
                                      p.get("city")) if x)
        line = ", ".join(x for x in (p.get("name"), where) if x) or "?"
        if line not in out:
            out.append(line)
    return out


async def _nominatim_named(query: str) -> list[str]:
    """No anchor at all: a plain name search ('Berghain', 'Pergamon Museum')."""
    out: list[str] = []
    for h in await _nominatim({"q": query, "limit": 3, "addressdetails": 1, "extratags": 1}):
        addr = h.get("address") or {}
        line = ", ".join(x for x in (h.get("name"), " ".join(y for y in (addr.get("road"),
                         addr.get("house_number")) if y), addr.get("city") or addr.get("town")) if x)
        if line and line not in out:
            out.append(line)
    return out


async def find_place(args: dict) -> str:
    """Real places from OpenStreetMap: around an anchor via Nominatim then Overpass, else by
    name via Photon."""
    query = (args.get("query") or "").strip()
    if not query:
        return missing_arg("find_place", args, "query", "place", "search", "text",
                           ask="What should I look for, sir?")

    async def fetch() -> str:
        what, where = _split(query)
        explicit = bool(where)
        if not where:
            from mushegh.brain import prefs
            where = prefs.home_location() or ""
        at = await geocode(where) if where else None
        # Cheapest first. "X near Y": the walkable box, then Overpass. No anchor but a home: the
        # walkable box, the region, Overpass (categories Nominatim cannot search, like gyms), then
        # a plain name search for a place in another city ('Berghain' asked from Cologne).
        # No anchor and no home: the plain name search alone.
        if at and explicit:
            engines = [lambda: _nominatim_near(what, at), lambda: _overpass(what, at)]
        elif at:
            engines = [lambda: _nominatim_near(what, at), lambda: _nominatim_near(what, at, 40_000),
                       lambda: _overpass(what, at), lambda: _nominatim_named(query)]
        else:
            engines = [lambda: _nominatim_named(query)]
        hits: list[str] = []
        for engine in engines:
            try:
                hits = await engine()
            except Exception:  # noqa: BLE001 - busy or down; the next engine answers
                hits = []
            if hits:
                break
        if not hits:
            hits = await _photon(query, at)
        if not hits:
            return f"Nothing found for '{query}', sir."
        return "Top matches, sir: " + "; ".join(hits) + "."

    try:
        return await CACHE.cached("place", query.lower(), ttl=3600, factory=fetch)
    except Exception as e:  # noqa: BLE001
        return tool_error("place search", e)
