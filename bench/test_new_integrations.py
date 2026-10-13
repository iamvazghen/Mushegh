"""New real-world integrations (2026-07-28): Twilio phone/SMS/WhatsApp, Google Maps, Wolfram,
Google Fit, Meet-on-calendar. Hermetic — no network, no keys: verifies registration, graceful
degradation, confirm-gating of outward reach, and lazy-group activation."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

passed = failed = 0


def check(name: str, ok: bool, detail: str = "") -> None:
    global passed, failed
    mark = "[PASS]" if ok else "[FAIL]"
    if ok:
        passed += 1
    else:
        failed += 1
    print(f"  {mark} {name}" + (f" — {detail}" if detail and not ok else ""))


def main() -> None:
    from mushegh.brain.proactive import confirm_required
    from mushegh.brain.tools import groups_for_text, tool_handlers, tool_names
    from mushegh.brain.tools import fitness, maps, phone, wolfram
    from mushegh.config import settings

    # Force the unconfigured state regardless of a real .env.
    settings.twilio_account_sid = None
    settings.google_maps_api_key = None
    settings.wolfram_app_id = None
    settings.google_client_id = None

    print("[1] all new tools registered with handlers")
    names = set(tool_names())
    expected = {"place_call", "travel_time", "find_place",
                "compute", "sleep_summary", "activity_summary"}
    check("all 6 registered", expected <= names, str(expected - names))
    check("SMS/WhatsApp removed (owner's call 2026-07-29 — Telegram covers texting)",
          not ({"send_sms", "send_whatsapp"} & names))
    handlers = tool_handlers()
    check("all 6 resolvable", all(t in handlers for t in expected))

    print("\n[2] graceful degradation without keys")
    def degrades(out: str) -> bool:
        from mushegh.brain.tools.base import is_not_configured
        return is_not_configured(out)
    check("place_call degrades", degrades(asyncio.run(phone.place_call({"to": "+491", "message": "x"}))))
    # Neither maps tool degrades: with no Google key both DELEGATE to the open engine.
    from mushegh.brain.tools import openmaps

    async def _open_travel(args):
        return "open-travel"

    async def _open_place(args):
        return "open-place"

    orig_open = openmaps.travel_time, openmaps.find_place
    openmaps.travel_time, openmaps.find_place = _open_travel, _open_place   # restored below
    check("travel_time uses the open engine without a Google key",
          asyncio.run(maps.travel_time({"destination": "airport"})) == "open-travel")
    check("find_place uses the open engine without a Google key",
          asyncio.run(maps.find_place({"query": "sushi"})) == "open-place")

    # With a key: Routes API + Places API (New) — the only ones a post-2025 project can enable.
    import httpx
    sent: list[tuple[str, dict, dict]] = []
    replies = {
        "routes": {"routes": [{"description": "A100", "localizedValues": {
            "duration": {"text": "24 mins"}, "distance": {"text": "18 km"}}}]},
        "places": {"places": [{"displayName": {"text": "Sushi Ya"}, "rating": 4.6,
                               "formattedAddress": "Alexanderplatz 1"}]},
    }

    async def _fake_post(url, json=None, headers=None, **kw):
        sent.append((url, json or {}, headers or {}))
        key = "routes" if "routes.googleapis" in url else "places"
        return httpx.Response(200, json=replies[key], request=httpx.Request("POST", url))

    orig_post = maps.http_post
    maps.http_post, settings.google_maps_api_key = _fake_post, "test-key"
    try:
        out = asyncio.run(maps.travel_time({"origin": "home st 1", "destination": "BER"}))
        url, body, hdr = sent[-1]
        check("travel_time calls Routes computeRoutes", url.endswith("/directions/v2:computeRoutes"), url)
        check("drive is traffic-aware", body.get("travelMode") == "DRIVE"
              and body.get("routingPreference") == "TRAFFIC_AWARE", str(body))
        check("key goes in the header, not the URL", hdr.get("X-Goog-Api-Key") == "test-key"
              and "test-key" not in url and hdr.get("X-Goog-FieldMask"))
        check("travel_time speaks duration, distance, route", "24 mins" in out and "18 km" in out
              and "A100" in out, out)
        asyncio.run(maps.travel_time({"origin": "a", "destination": "b", "mode": "walking"}))
        check("walking has no routing preference (Routes rejects it)",
              sent[-1][1].get("travelMode") == "WALK" and "routingPreference" not in sent[-1][1])
        out = asyncio.run(maps.find_place({"query": "sushi near Alexanderplatz"}))
        check("find_place calls Places searchText", sent[-1][0].endswith("/v1/places:searchText"))
        check("find_place speaks name, rating, address",
              "Sushi Ya" in out and "4.6" in out and "Alexanderplatz 1" in out, out)
        replies["routes"] = {}
        check("no route is said plainly", "couldn't find a route" in
              asyncio.run(maps.travel_time({"origin": "a", "destination": "Atlantis"})))

        async def _boom(url, **kw):
            raise httpx.ConnectError("google down")
        maps.http_post = _boom
        check("a failing Google call falls back to the open engine, not to silence",
              asyncio.run(maps.travel_time({"origin": "a", "destination": "b"})) == "open-travel"
              and asyncio.run(maps.find_place({"query": "sushi"})) == "open-place")
    finally:
        maps.http_post, settings.google_maps_api_key = orig_post, None
        openmaps.travel_time, openmaps.find_place = orig_open

    check("compute degrades", degrades(asyncio.run(wolfram.compute({"query": "2+2"}))))
    check("sleep_summary degrades", degrades(asyncio.run(fitness.sleep_summary({}))))
    check("activity_summary degrades", degrades(asyncio.run(fitness.activity_summary({}))))

    print("\n[3] outward reach is confirm-gated; reads are not")
    check("place_call confirms", confirm_required("place_call", {}))
    check("travel_time does NOT confirm", not confirm_required("travel_time", {}))
    check("compute does NOT confirm", not confirm_required("compute", {}))

    print("\n[4] lazy groups light up on the right utterances")
    check("'call the restaurant' -> phone", "phone" in groups_for_text("call the restaurant and book a table"))
    check("'how long to the airport' -> places", "places" in groups_for_text("how long to the airport right now"))
    check("'convert 180 lbs' -> compute", "compute" in groups_for_text("convert 180 lbs to kilograms"))
    check("'how did i sleep' -> vitals", "vitals" in groups_for_text("how did I sleep last night"))
    check("plain chat stays lean", not ({"phone", "places", "compute", "vitals"}
                                        & groups_for_text("good morning, how are you")))

    print("\n[5] plan_today: owner's stated time -> main + prep reminders, day-plan recorded")
    import json
    import tempfile
    from datetime import datetime, timedelta
    from pathlib import Path as P

    import mushegh.brain.tools.reminders as rem
    import mushegh.brain.tools.routines as routines_mod
    import mushegh.brain.proactive_signals as ps

    ps._ROUTINES_PATH = P(tempfile.gettempdir()) / "test_routines_plan.json"
    ps._ROUTINES_PATH.write_text(json.dumps([
        {"key": "training", "dynamic": True, "message": "Training time, sir.",
         "prep_message": "Stretch first, sir.", "lead_minutes": 40},
    ]), encoding="utf-8")
    routines_mod._DAY_PLAN = P(tempfile.gettempdir()) / "test_day_plan_plan.json"
    routines_mod._DAY_PLAN.unlink(missing_ok=True)
    scheduled: list = []

    async def fake_set_reminder(args):
        scheduled.append(args)
        return "Done, sir."

    orig = rem.set_reminder
    rem.set_reminder = fake_set_reminder
    try:
        target = datetime.now(routines_mod.USER_TZ) + timedelta(hours=13)  # always future, ISO form
        out = asyncio.run(routines_mod.plan_today(
            {"commitment": "training", "time": target.isoformat()}))
        check("plan_today confirms", "Planned, sir" in out, out)
        check("two reminders scheduled (main + stretch prep)", len(scheduled) == 2, str(scheduled))
        mains = [datetime.fromisoformat(s["at"]) for s in scheduled]
        check("prep lands 40 min before training",
              abs((max(mains) - min(mains)).total_seconds() - 2400) < 60, str(mains))
        plan = json.loads(routines_mod._DAY_PLAN.read_text(encoding="utf-8"))
        check("day plan recorded (planning prompt goes quiet)", "training" in plan, str(plan))
        # An unambiguous past instant, the same way the future case above is built. This used to be
        # the literal "00:01", which is only in the past for all but ~60 seconds of the day — and the
        # 2026-08-01 deploy gate happened to run through 00:00:08, so it planned the time instead of
        # refusing it and failed a build over the clock rather than the code.
        past = datetime.now(routines_mod.USER_TZ) - timedelta(hours=13)
        out2 = asyncio.run(routines_mod.plan_today(
            {"commitment": "training", "time": past.isoformat()}))
        check("a past time is refused, not silently scheduled", "already past" in out2, out2)
    finally:
        rem.set_reminder = orig

    # --- 34.F1: the fitness source works with no API, no key and no enablement -----------------
    # The tools were written against Google Fit, which needs a Cloud-project enablement nobody has
    # done — so for months the capability existed and answered "not configured yet" to every
    # question. The plan retired that dependency: ingest an OPEN export format, and naming the
    # watch later changes no code. This is a real read of a real-shaped file.
    print("\n[fitness] 34.F1 — a real read from an Apple Health export")
    import tempfile
    from pathlib import Path as _Path

    from mushegh.brain import vitals as V

    sample = '<?xml version="1.0" encoding="UTF-8"?>\n<HealthData locale="en_GB">\n <Record type="HKQuantityTypeIdentifierStepCount" unit="count" startDate="2026-09-11 08:00:00 +0200" value="1200"/>\n <Record type="HKQuantityTypeIdentifierStepCount" unit="count" startDate="2026-09-11 18:00:00 +0200" value="3400"/>\n <Record type="HKQuantityTypeIdentifierRestingHeartRate" unit="count/min" startDate="2026-09-11 07:00:00 +0200" value="58"/>\n <Record type="HKCategoryTypeIdentifierSleepAnalysis" startDate="2026-09-11 00:30:00 +0200" value="HKCategoryValueSleepAnalysisAsleepCore"/>\n <Record type="HKQuantityTypeIdentifierStepCount" unit="count" startDate="not a date" value="99"/>\n</HealthData>\n'
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
        x = _Path(d) / "export.xml"
        x.write_text(sample, encoding="utf-8")
        read = V.read_apple_health(x)
        check("the export reads", read.ok, read.error)
        check("steps are counted", read.kinds.get("steps") == 2, str(read.kinds))
        check("...and summed per day", read.by_day("steps") == {"2026-09-11": 4600.0},
              str(read.by_day("steps")))
        check("heart rate averages rather than sums",
              read.by_day("resting heart rate") == {"2026-09-11": 58.0},
              str(read.by_day("resting heart rate")))
        check("a record with an unparseable date is dropped, not guessed at",
              read.kinds.get("steps") == 2, str(read.kinds))
        check("a missing file is an answer, not a crash",
              not V.read_apple_health(_Path(d) / "nope.xml").ok)
        broken = _Path(d) / "broken.xml"
        broken.write_text("<HealthData><Record", encoding="utf-8")
        check("malformed XML says so", "isn't valid XML" in V.read_apple_health(broken).error,
              V.read_apple_health(broken).error)

        store = _Path(d) / "vitals.json"
        V.save(read, store)
        check("the daily figures are kept", V.kept("steps", store) == {"2026-09-11": 4600.0},
              str(V.kept("steps", store)))
        check("...and not the raw records", "1200" not in store.read_text(encoding="utf-8"),
              "a copy of his whole health history answers no question worth asking")
        check("a second import merges rather than replacing",
              V.save(read, store).get("resting heart rate") == {"2026-09-11": 58.0})
        check("a trend needs data, and says so when there is none",
              "no steps on file" in V.recent("steps", path=_Path(d) / "empty.json"))

    src = (Path(__file__).resolve().parents[1]
           / "src/mushegh/brain/vitals.py").read_text(encoding="utf-8")
    check("the parser streams rather than loading the file whole", "iterparse" in src,
          "a real export is hundreds of megabytes")
    check("...and releases each element as it goes", "elem.clear()" in src)
    check("the reason is written down where the next reader will see it",
          "takes the brain down on the owner's actual file" in src)

    from mushegh.brain.tools import tool_handlers as _handlers

    check("the import tool is registered", "import_health" in _handlers())
    check("the trend tool is registered", "vitals_trend" in _handlers())

    print(f"\n=== {passed}/{passed + failed} checks passed ===")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
