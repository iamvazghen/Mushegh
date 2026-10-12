"""Live German transit — inter-city (DB) and city (KVB/Stadtbahn), no API key.

One module because the question is always the same one: *when do I leave and what
do I catch*. "Do I still make my train from Köln Hbf?" and "when's the next tram
from Neumarkt?" differ only in which operator answers.

**No key, by design.** `v6.db.transport.rest` is a community wrapper over DB's
own Hafas and IRIS engines, so this is the first integration in the belt that is
*more* available than a keyed one: no account, no quota, no key to lose, and it
degrades to a spoken note rather than going dark. That is why it has no
``not_configured`` branch — there is nothing to configure.

Three sources, each for what it is actually best at:

* ``v6.db.transport.rest`` — the workhorse. Station lookup, live departures with
  delay and platform, and A→B journey planning across the whole network
  (long-distance, regional, and — because the transport.rest wrapper indexes the
  Cologne KVB Stadtbahn alongside DB — local trams and buses).
* ``bahn.expert/api/iris/v2`` — DB's internal station display, which is the only
  place the *reason* for a delay exists ("Signalstörung", "Verspätung eines
  vorausfahrenden Zuges"). A departure board says a train is 12 minutes late; IRIS
  says why, which is the difference between useful and annoying.
* ``bahn.expert/api/reihung/v4`` — carriage formation, so "which coach do I get
  on for the café car" is answerable before leaving the house.

Read-only. Nothing here books, cancels or pays, so none of it is confirm-gated.

Data is fetched at request time and discarded; the module keeps no store, because
a departure board is true for about thirty seconds and a cached one is worse than
none.
"""

from __future__ import annotations

from typing import Any

from mushegh.brain.tools.base import http_get, missing_arg, tool_error

#: The community wrapper over DB Hafas. Keyless; indexes DB plus the KVB network.
DB = "https://v6.db.transport.rest"
#: DB's internal station display (IRIS) — the only source that carries a delay REASON.
IRIS = "https://bahn.expert/api/iris/v2"
#: Carriage formation, so a coach question is answerable before leaving.
REIHUNG = "https://bahn.expert/api/reihung/v4"

#: Cap on how many departures are ever spoken. A 60-minute board is ~40 rows and
#: nobody wants them read aloud; the caller asks for a window, not a dump.
MAX_ROWS = 8


# ---------------------------------------------------------------- formatting
# Pure functions over already-fetched JSON. Every claim the assistant makes about
# a train comes from one of these, so they are the testable half of this module.

def hhmm(ts: str | None) -> str:
    """The HH:MM out of an ISO timestamp, or an em dash if it is not one.

    The upstream API returns ISO-8601 with a timezone offset. Slicing is right and
    `fromisoformat` is wrong here: a timestamp arriving as ``2026-10-10T14:15:00+02:00``
    must render in the DEPARTURE's local time, which is what the first 16 chars
    already carry, and reparsing would tempt a later edit to convert it to the
    machine's zone and start showing a board an hour wrong.
    """
    return ts[11:16] if isinstance(ts, str) and len(ts) >= 16 else "—"


def delay_phrase(delay_seconds: int | None, cancelled: bool = False) -> str:
    """How to SAY the delay. Never a bare number, never a negative.

    A negative ``delay`` means an EARLY train. Printing "-3 min" reads as a bug
    to a human and as a contradiction to a model, so it becomes "3 min early".
    """
    if cancelled:
        return "CANCELLED"
    if not delay_seconds:
        return "on time"
    minutes = abs(int(delay_seconds)) // 60
    if minutes < 1:
        return "on time" if not delay_seconds else "a moment late"
    return f"{minutes} min early" if delay_seconds < 0 else f"+{minutes} min"


def platform_of(train: dict) -> str:
    """Actual platform if there is one, else the planned one, else unknown.

    Platform changes are the single most common reason someone misses a train in
    Germany, so an actual value is preferred over a planned one — but a missing
    actual falls back rather than reporting nothing.
    """
    return str(train.get("platform") or train.get("plannedPlatform") or "?")


def format_departures(departures: list[dict], limit: int = MAX_ROWS) -> str:
    """A live departure board as one line per train, soonest first.

    Sorted by ACTUAL departure where known, planned otherwise. Sorting on planned
    only would put a delayed train behind a later one that is running on time,
    which is exactly backwards from what someone standing on a platform needs.
    """
    def key(t: dict) -> str:
        return t.get("when") or t.get("plannedWhen") or ""

    rows = sorted(departures, key=key)[:limit]
    if not rows:
        return "No departures in that window."
    out = []
    for t in rows:
        line = (t.get("line") or {}).get("name") or "?"
        direction = t.get("direction") or "?"
        cancelled = bool(t.get("cancelled"))
        when = "CANCELLED" if cancelled else hhmm(t.get("when") or t.get("plannedWhen"))
        if cancelled:
            # No track at all: a cancelled train has no platform, and printing
            # "track ?" beside CANCELLED reads like it is still running and we
            # just don't know where.
            out.append(f"{when}  {line} → {direction}")
            continue
        out.append(f"{when}  {line} → {direction}  (track {platform_of(t)}, "
                   f"{delay_phrase(t.get('delay'))})")
    return "\n".join(out)


def _stop_name(obj: Any) -> str:
    """A stop name out of whatever shape the leg carries it in.

    transport.rest follows the Hafas naming (``origin``/``destination``), but the
    same payload has shipped under ``from``/``to``, and a leg with neither is not
    worth dropping the whole journey over. One helper keeps that tolerance in a
    single place instead of a chain of ``.get`` guesses at every use site.
    """
    if not isinstance(obj, dict):
        return "?"
    for key in ("origin", "from", "departure", "stop"):
        v = obj.get(key)
        if isinstance(v, dict) and v.get("name"):
            return str(v["name"])
        if isinstance(v, str) and v:
            return v
    return "?"


def format_journey(journey: dict) -> str:
    """One A→B option: when it leaves, how long, how many changes, what it costs.

    Times are read off the legs rather than off the journey: v6 moved the
    journey-level ``departure``/``arrival`` onto the first and last leg, and a
    client that still reads the old keys gets "—" for every query instead of an
    error, which is the failure mode that survives review.
    """
    legs = journey.get("legs") or []
    if not legs:
        return "No route found between those."
    first, last = legs[0], legs[-1]
    dep = hhmm(first.get("departure") or journey.get("departure"))
    arr = hhmm(last.get("arrival") or journey.get("arrival"))
    mins = _duration_minutes(first.get("departure") or journey.get("departure"),
                             last.get("arrival") or journey.get("arrival"))
    changes = max(0, len(legs) - 1)
    price = journey.get("price") or {}
    fare = f", {price.get('amount')} {price.get('currency')}" if price.get("amount") else ""

    parts = []
    for leg in legs:
        name = (leg.get("line") or {}).get("name") or (leg.get("route") or {}).get("short_name") or "walk"
        parts.append(f"{name} from {_stop_name(leg)}")
    route = " then ".join(parts)

    return (f"Leave {dep}, arrive {arr}"
            + (f" (~{mins} min)" if mins else "")
            + f", {changes} change{'s' if changes != 1 else ''}{fare}. {route}.")


def _duration_minutes(start: str | None, end: str | None) -> int | None:
    """Whole minutes between two ISO timestamps, or None if either is unusable."""
    if not isinstance(start, str) or not isinstance(end, str):
        return None
    try:
        from datetime import datetime
        a = datetime.fromisoformat(start)
        b = datetime.fromisoformat(end)
    except ValueError:
        return None
    return int((b - a).total_seconds() // 60)


# --------------------------------------------------------------------- fetch


async def _locations(query: str) -> list[dict]:
    """Resolve a station/stop name to ids.

    The API returns several matches (the stop, the district, a nearby POI), which
    is why ``poi=false``/``addresses=false`` are set and why the caller must pick
    rather than blindly take index 0: "Köln" resolves to a dozen things.
    """
    r = await http_get(f"{DB}/locations",
                       params={"query": query, "poi": "false", "addresses": "false"})
    return r.json() or []


async def _best_match(query: str) -> dict | None:
    """The most likely station for a name, or None.

    A named place is turned into its address first, so "how do I get from home to
    city centre" reaches transport.rest as two real places rather than two words
    it has never heard of.

    Preference order is deliberate: a station whose name EQUALS the query beats a
    district that merely contains it. "Neumarkt" must not silently become
    "Neumarkt (Verkehrsplatz)" when the owner said "Neumarkt" and meant the stop
    they stand at every day.
    """
    found = await _locations(query)
    if not found:
        return None
    q = query.strip().lower()
    exact = [f for f in found if str(f.get("name", "")).strip().lower() == q]
    return (exact or found)[0]


def _named_place(query: str) -> str | None:
    """Resolve "home" / "the gym" to an address, or None.

    Returns None for anything that is not a named place OR that names an AMBIGUOUS
    one. "the gym" matching both gyms is the case that matters: routing to the
    wrong branch of the same chain is a confidently wrong answer, so the caller
    asks which gym instead.
    """
    from mushegh.brain.locations import BOOK

    hits = BOOK.resolve(query)
    if not hits:
        return None
    if len(hits) > 1:
        return None
    place = hits[0]
    if not place.is_complete:
        return None
    return place.one_line


# --------------------------------------------------------------------- tools


async def transit_departures(args: dict) -> str:
    """Live departure board with real delays and platforms."""
    station = (args.get("station") or args.get("stop") or args.get("query")
               or args.get("from") or "").strip()
    if not station:
        return missing_arg("transit_departures", args, "station", "stop", "query",
                           ask="Which station, sir?")
    minutes = max(1, min(120, int(args.get("minutes") or 20)))
    only_long = bool(args.get("long_distance"))

    try:
        match = await _best_match(station)
        if not match:
            return f"I couldn't find a station called '{station}', sir."
        params: dict[str, Any] = {"duration": minutes}
        if only_long:
            # "I'm catching an ICE", not "when's the next tram" — regional=false
            # keeps S-Bahn and Regionalbahn out of a long-distance answer.
            params["regional"] = "false"
            params["suburban"] = "false"
        r = await http_get(f"{DB}/stops/{match['id']}/departures", params=params)
        body = r.json() or {}
        name = match.get("name") or station
        board = format_departures(body.get("departures") or [])
        return f"From {name}, sir — next {minutes} min:\n{board}"
    except Exception as e:  # noqa: BLE001
        return tool_error("departure board", e)


async def transit_journey(args: dict) -> str:
    """A→B routing — the "how do I get there" question."""
    origin = (args.get("from") or args.get("origin") or "").strip()
    dest = (args.get("to") or args.get("destination") or "").strip()
    if not dest:
        return missing_arg("transit_journey", args, "to", "destination",
                           ask="Where to, sir?")
    if not origin:
        from mushegh.brain import prefs
        origin = prefs.home_location() or ""
    if not origin:
        return "I need a starting point, sir — or set your home location."

    try:
        # A named place wins over the literal string, so "from home to the gym"
        # routes to two addresses rather than two words. Falls through to the raw
        # string when the owner names a station directly.
        origin_q = _named_place(origin) or origin
        dest_q = _named_place(dest) or dest
        a, b = await _best_match(origin_q), await _best_match(dest_q)
        if not a or not b:
            missing = origin_q if not a else dest_q
            return f"I couldn't find {missing!r} as a station, sir."
        params = {"from": a["id"], "to": b["id"], "results": 3}
        if int(args.get("transfers") or 0) == 0:
            params["transfers"] = 0
        r = await http_get(f"{DB}/journeys", params=params)
        journeys = (r.json() or {}).get("journeys") or []
        if not journeys:
            return f"No route from {a.get('name')} to {b.get('name')}, sir."
        best = format_journey(journeys[0])
        others = len(journeys) - 1
        return best + (f" ({others} slower option{'s' if others != 1 else ''} available.)"
                       if others > 0 else "")
    except Exception as e:  # noqa: BLE001
        return tool_error("journey planning", e)


async def transit_delay_reason(args: dict) -> str:
    """WHY a train is late — the part no departure board will tell you."""
    station = (args.get("station") or args.get("query") or "").strip()
    if not station:
        return missing_arg("transit_delay_reason", args, "station", "query",
                           ask="Which station, sir?")
    try:
        r = await http_get(f"{IRIS}/abfahrten/{station.strip().replace(' ', '%20')}")
        rows = r.json() or []
        late = [x for x in rows if x.get("versp") not in (None, 0)]
        if not late:
            return f"Nothing delayed at {station} right now, sir."
        out = []
        for x in late[:MAX_ROWS]:
            train = x.get("kz") or x.get("train") or "?"
            reason = x.get("grund") or x.get("reason") or "no reason published"
            mins = int(x.get("versp") or 0) // 60
            out.append(f"{train} +{mins} min — {reason}")
        return f"Delayed at {station}, sir: " + "; ".join(out) + "."
    except Exception as e:  # noqa: BLE001
        return tool_error("delay reasons", e)


async def transit_carriage(args: dict) -> str:
    """Carriage formation — which coach, and where it stops."""
    train = (args.get("train") or args.get("number") or "").strip()
    if not train:
        return missing_arg("transit_carriage", args, "train", "number",
                           ask="Which train number, sir?")
    when = (args.get("departure_time") or args.get("when") or "").strip()
    if not when:
        return missing_arg("transit_carriage", args, "departure_time", "when",
                           ask="When does it leave, sir?")
    try:
        r = await http_get(f"{REIHUNG}/plan/{train.strip()}/{when.strip()}")
        data = r.json() or {}
        coaches = data.get("plan") or data.get("coachSections") or data.get("wagons") or []
        if not coaches:
            return f"No carriage plan published for {train} at {when}, sir."
        rows = []
        for c in coaches[:12]:
            coach_no = c.get("coachNumber") or c.get("number") or "?"
            classes = c.get("class") or c.get("classes") or "?"
            stops = c.get("stops") or c.get("position") or ""
            rows.append(f"Coach {coach_no} ({classes}) {stops}".strip())
        return f"{train}: " + "; ".join(rows) + "."
    except Exception as e:  # noqa: BLE001
        return tool_error("carriage formation", e)


SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "transit_departures",
            "description": ("Live departure board for ANY German station or Cologne KVB stop — real "
                            "delays, cancellations and platform changes. Use for 'when's the next "
                            "ICE from Köln Hbf', 'is my train delayed', 'when's the next tram from "
                            "Neumarkt'. For the reason behind a delay use transit_delay_reason; for "
                            "getting somewhere use transit_journey."),
            "parameters": {
                "type": "object",
                "properties": {
                    "station": {"type": "string", "description": "Station or stop name, e.g. 'Köln Hbf', 'Neumarkt'."},
                    "minutes": {"type": "integer", "description": "How far ahead to look. Default 20."},
                    "long_distance": {"type": "boolean", "description": "Only ICE/IC and other long-distance trains."},
                },
                "required": ["station"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "transit_journey",
            "description": ("Route from A to B across the whole network — long-distance, regional and "
                            "Cologne Stadtbahn — with departure time, arrival time, changes and fare. "
                            "Use for 'how do I get to the airport', 'how long to Frankfurt', 'what's "
                            "the fastest way to X'."),
            "parameters": {
                "type": "object",
                "properties": {
                    "from": {"type": "string", "description": "Origin station/stop (default: home)."},
                    "to": {"type": "string", "description": "Destination station/stop."},
                    "transfers": {"type": "integer", "description": "0 for a direct route only."},
                },
                "required": ["to"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "transit_delay_reason",
            "description": ("Why a train is delayed, from DB's internal station display — 'Signalstörung', "
                            "'Verspätung eines vorausfahrenden Zuges' and so on. Use when a departure "
                            "board shows a delay and the owner asks why, or is deciding whether to wait."),
            "parameters": {
                "type": "object",
                "properties": {"station": {"type": "string", "description": "Station name."}},
                "required": ["station"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "transit_carriage",
            "description": ("Carriage formation for a named train and departure time — which coach is the "
                            "bistro/cafe car, and where it stops. Use for 'where's the cafe car on ICE "
                            "105', 'which coach do I want'."),
            "parameters": {
                "type": "object",
                "properties": {
                    "train": {"type": "string", "description": "Train number, e.g. 105."},
                    "departure_time": {"type": "string", "description": "Departure timestamp for that run."},
                },
                "required": ["train", "departure_time"],
            },
        },
    },
]

HANDLERS = {
    "transit_departures": transit_departures,
    "transit_journey": transit_journey,
    "transit_delay_reason": transit_delay_reason,
    "transit_carriage": transit_carriage,
}