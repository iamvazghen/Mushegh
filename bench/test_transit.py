"""Live transit: the formatting half, which is the half that can be wrong quietly.

A departure board that renders the wrong platform is worse than no board — the
owner trusts it. So the pure formatting is tested against real API shapes, and
the assertions are about the *wording*, because a raw ``-180`` seconds or a
``12:00`` for a 12-minute delay is not a formatting nit, it is a wrong answer
delivered fluently.

No network: every case here is a literal taken from the transport.rest /
bahn.expert response shapes.

    uv run python bench/test_transit.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from mushegh.brain.tools.transit import (  # noqa: E402
    SCHEMAS,
    HANDLERS,
    delay_phrase,
    format_departures,
    format_journey,
    hhmm,
    platform_of,
)

passed = failed = 0


def check(name: str, ok: bool, detail: str = "") -> None:
    global passed, failed
    if ok:
        passed += 1
        print(f"  [PASS] {name}")
    else:
        failed += 1
        print(f"  [FAIL] {name}  {detail}")


def main() -> None:
    print("[1] a timestamp renders as HH:MM in the departure's own zone")
    check("full ISO with offset", hhmm("2026-10-10T14:15:00+02:00") == "14:15")
    check("without seconds", hhmm("2026-10-10T06:42:00Z") == "06:42")
    check("None is a dash, not a crash", hhmm(None) == "—")
    check("junk is a dash", hhmm("nonsense") == "—")

    print("[2] a delay is spoken, never printed as raw seconds")
    check("zero is on time", delay_phrase(0) == "on time")
    check("None is on time", delay_phrase(None) == "on time")
    check("12 minutes late", delay_phrase(720) == "+12 min")
    check("90 seconds is not '+1 min' of noise", delay_phrase(45) == "a moment late")
    check("cancelled beats any delay", delay_phrase(600, True) == "CANCELLED")
    check("an EARLY train does not print a minus sign", delay_phrase(-180) == "3 min early",
          "a bare negative reads as a bug to a human and a contradiction to a model")

    print("[3] an actual platform beats a planned one — platform changes are the classic miss")
    t = {"platform": "7", "plannedPlatform": "5"}
    check("actual wins", platform_of(t) == "7")
    check("falls back to planned", platform_of({"plannedPlatform": "5"}) == "5")
    check("neither is a question mark, never blank", platform_of({}) == "?")

    print("[4] the board is sorted by ACTUAL time, so a late train is not buried")
    rows = [
        {"plannedWhen": "2026-10-10T14:10:00+02:00", "when": "2026-10-10T14:22:00+02:00",
         "line": {"name": "ICE 105"}, "direction": "Basel SBB", "delay": 720, "platform": "6"},
        {"plannedWhen": "2026-10-10T14:15:00+02:00", "when": "2026-10-10T14:15:00+02:00",
         "line": {"name": "RE 1"}, "direction": "Hamm(Westf)", "delay": 0, "platform": "2"},
    ]
    board = format_departures(rows)
    lines = board.splitlines()
    check("the on-time train is first", lines[0].startswith("14:15"), board)
    check("the 12-min-late ICE is second", lines[1].startswith("14:22"), board)
    check("the actual time is shown, not the planned one", "14:22" in board and "14:10" not in board, board)

    print("[5] the board says the things that change a decision")
    check("line number is present", "ICE 105" in board, board)
    check("destination is present", "Basel SBB" in board, board)
    check("track is named 'track', not 'platform'", "track 6" in board, board)
    check("the delay is stated", "+12 min" in board, board)
    check("on-time is said plainly", "on time" in board, board)

    print("[6] a cancellation cannot be misread as a delay")
    cancelled = [{"plannedWhen": "2026-10-10T14:10:00+02:00", "line": {"name": "ICE 999"},
                  "direction": "München Hbf", "delay": 1800, "platform": None, "cancelled": True}]
    text = format_departures(cancelled)
    check("says CANCELLED", "CANCELLED" in text, text)
    check("does not also say '+30 min'", "+30 min" not in text, text)
    check("and does not print a track as if it were running", "track ?" not in text, text)

    print("[7] an empty board says so rather than returning nothing")
    check("empty list", format_departures([]) == "No departures in that window.")

    print("[8] a board is capped, because 40 rows is not a spoken answer")
    many = [{"plannedWhen": f"2026-10-10T14:{i:02d}:00+02:00", "line": {"name": f"RE {i}"},
             "direction": "X", "delay": 0} for i in range(1, 41)]
    check("default cap is 8 rows", len(format_departures(many).splitlines()) == 8)
    check("explicit cap honoured", len(format_departures(many, limit=3).splitlines()) == 3)

    print("[9] a journey reads as leave / arrive / changes / fare")
    # The real transport.rest/Hafas leg: timestamps sit on the leg, and the places
    # are under origin/destination. Reading journey-level departure (an older
    # shape) yields "—" for every query, which is a wrong answer that never raises.
    j = {
        "legs": [
            {"departure": "2026-10-10T14:00:00+02:00", "arrival": "2026-10-10T14:30:00+02:00",
             "origin": {"name": "Köln Hbf"}, "destination": {"name": "Köln Messe/Deutz"},
             "line": {"name": "ICE 105"}},
            {"departure": "2026-10-10T14:36:00+02:00", "arrival": "2026-10-10T15:12:00+02:00",
             "origin": {"name": "Köln Messe/Deutz"}, "destination": {"name": "Frankfurt (Main) Hbf"},
             "line": {"name": "ICE 571"}},
        ],
        "price": {"amount": "39.00", "currency": "EUR"},
    }
    out = format_journey(j)
    check("leaves at 14:00", "Leave 14:00" in out, out)
    check("arrives at 15:12", "arrive 15:12" in out, out)
    check("duration spans first departure to last arrival", "72 min" in out, out)
    check("counts the change", "1 change" in out, out)
    check("names the fare", "39.00 EUR" in out, out)
    check("names both legs", "ICE 105" in out and "ICE 571" in out, out)
    check("names the stops", "Köln Hbf" in out, out)

    print("[9b] it still reads the older shape without claiming to know better")
    old = {"departure": "2026-10-10T14:00:00+02:00", "arrival": "2026-10-10T14:55:00+02:00",
           "legs": [{"departure": "2026-10-10T14:00:00+02:00",
                     "from": {"name": "Neumarkt"}, "to": {"name": "Hansaring"},
                     "line": {"name": "Tram 1"}}]}
    check("from/to still yields a stop name", "Neumarkt" in format_journey(old), format_journey(old))
    check("journey-level departure still works", "Leave 14:00" in format_journey(old))

    print("[10] the awkward journey shapes")
    direct = {"departure": "2026-10-10T14:00:00+02:00", "arrival": "2026-10-10T14:55:00+02:00",
              "legs": [{"departure": {"name": "Neumarkt"}, "arrival": {"name": "Hansaring"},
                        "line": {"name": "Tram 1"}}]}
    check("a direct tram reads as zero changes", "0 changes" in format_journey(direct),
          format_journey(direct))
    check("a no-legs journey says so, not an empty string",
          "No route" in format_journey({"legs": []}))
    check("a missing duration is omitted rather than faked",
          "~" not in format_journey({"departure": None, "arrival": None,
                                      "legs": [{"departure": {"name": "A"},
                                                "arrival": {"name": "B"}}]}))
    check("an unparseable duration is omitted rather than crashing",
          "min)" not in format_journey({"departure": "junk", "arrival": "junk",
                                        "legs": [{"departure": {"name": "A"},
                                                  "arrival": {"name": "B"}}]}))

    print("[11] the tool surface the registry will advertise")
    names = {s["function"]["name"] for s in SCHEMAS}
    check("four tools", len(SCHEMAS) == 4, str(names))
    check("every schema has a handler", names == set(HANDLERS), str(names ^ set(HANDLERS)))
    check("every schema is a well-formed function", all(
        s.get("type") == "function" and s.get("function", {}).get("name")
        and s["function"].get("parameters", {}).get("type") == "object" for s in SCHEMAS))
    check("required args are declared", all(
        s["function"]["parameters"].get("required") for s in SCHEMAS))
    for want in ("transit_departures", "transit_journey", "transit_delay_reason", "transit_carriage"):
        check(f"{want} present", want in names)

    print(f"\n=== checks passed ===\n{passed} passed, {failed} failed")
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()