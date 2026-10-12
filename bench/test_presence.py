"""Phase 0 companion foundation — activity/presence tracking + persistent proactive state.

Proves the perception + memory layer the proactive companion is built on:
  * the presence store ingests activity snapshots and aggregates screen-time by app/category;
  * idle samples (user away) are NOT counted as screen time;
  * 'current activity' reflects the latest sample; the privacy off-switch pauses tracking;
  * retention pruning drops old samples;
  * the screen_time / current_activity / activity_tracking tools speak sensible lines;
  * the proactive engine PERSISTS its budget + repeat-suppression, so a brain RESTART doesn't
    re-fire the same nudge (the root-cause class behind the duplicate morning messages).

Hermetic: temp SQLite + temp state file, controlled timestamps, no laptop, no network.

    uv run python bench/test_presence.py
"""

from __future__ import annotations

import asyncio
import sys
import tempfile
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

passed = failed = 0


def check(name: str, ok: bool, detail: str = "") -> None:
    global passed, failed
    if ok:
        passed += 1
        print(f"  [PASS] {name}")
    else:
        failed += 1
        print(f"  [FAIL] {name}  {detail}")


def _owner_day_start(hour: int) -> float:
    """A timestamp at `hour` o'clock on the OWNER's today, as an epoch second.

    Mirrors `presence._day_bounds`, which is the code under test: it takes the day from
    `datetime.now(USER_TZ)`, not from the machine's timezone. A fixture that builds its samples
    from the machine's day lands outside the window whenever the two zones straddle midnight —
    routinely, since the brain runs UTC on a VPS and the owner does not.
    """
    from mushegh.brain.presence import _tz

    from datetime import datetime as _d

    start = _d.now(_tz()).replace(hour=hour, minute=0, second=0, microsecond=0)
    return start.timestamp()


async def main() -> None:
    from mushegh.config import settings
    settings.presence_poll_seconds = 60      # each active sample = 60s of screen time
    settings.presence_idle_threshold_seconds = 90
    settings.presence_retention_days = 30

    from mushegh.brain.presence import Presence
    import mushegh.brain.tools.activity as act

    tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
    p = Presence(db_path=Path(tmp.name) / "presence.sqlite")
    act.PRESENCE = p  # the tools resolve PRESENCE from this module binding

    now = time.time()
    # Anchored to a fixed hour of TODAY rather than to "six minutes ago". The assertions are about
    # `screen_time(0)` — one local day — and a relative offset walks backwards over midnight, so
    # this used to fail for the first few minutes after 00:00 and pass again by breakfast. 21.F3
    # replays the clock-sensitive tests across awkward dates for exactly this class of defect;
    # this one was reachable by the ordinary suite, just rarely.
    #
    # Timestamps in the future are fine here: `screen_time` selects by local-day bounds with no
    # upper clamp, and `current()` returns the last RECORDED sample rather than the newest one, so
    # "what is he doing now" still follows call order.
    day_base = _owner_day_start(8)      # 08:00 on the owner's today, whenever the suite runs

    print("[1] ingest snapshots + screen-time aggregation by app/category")
    # Spaced ONE POLL APART, which is what the poller does. They used to share a single timestamp,
    # which only worked because screen time was `sample count x the configured poll interval` — the
    # estimate 34.F2 replaced. Credit is now the real interval between samples, so a fixture where
    # six readings happen at the same instant correctly yields no time at all.
    base = day_base
    for i in range(3):
        p.record("chrome", "YouTube - something", 2.0, ts=base + i * 60)   # active browsing
    for i in range(3, 5):
        p.record("Code", "server.py - Mushegh", 4.0, ts=base + i * 60)        # active coding
    p.record("chrome", "idle tab", 300.0, ts=base + 5 * 60)                # away -> not counted
    data = p.screen_time(0)
    check("chrome credited 3×60s", data["apps"].get("chrome") == 180, str(data["apps"]))
    check("Code credited 2×60s", data["apps"].get("Code") == 120, str(data["apps"]))
    check("idle sample not counted", data["total"] == 300, str(data["total"]))
    check("category 'browsing' from chrome", data["categories"].get("browsing") == 180, str(data["categories"]))
    check("category 'coding' from Code/terminal", data["categories"].get("coding") == 120, str(data["categories"]))
    check("sample count includes the idle one", data["samples"] == 6, str(data["samples"]))

    print("\n[2] report + current activity")
    rep = p.report(0)
    check("report gives a total", "active about 5m" in rep, rep)
    check("report names top apps", "chrome" in rep and "Code" in rep, rep)
    p.record("Code", "writing tests", 1.0, ts=base + 6 * 60)       # latest = active coding
    check("current_line names the active app", "Code" in p.current_line(), p.current_line())
    p.record("chrome", "afk", 500.0, ts=base + 7 * 60)             # latest = idle
    check("current_line reports idle when away", "idle" in p.current_line().lower(), p.current_line())

    print("\n[3] ingest() parses raw snapshot JSON; junk is ignored")
    check("valid json ingested", p.ingest('{"app":"vlc","title":"movie","idle":0.5}'))
    check("empty '{}' ignored", not p.ingest("{}"))
    check("garbage ignored", not p.ingest("not json"))
    # The mapping is asserted directly, and the aggregate only for presence. `ingest` stamps its
    # row with the clock, so where that row SORTS among the fixture depends on the hour the suite
    # runs: land it before the day's block and its credit becomes the gap to the rest of the day,
    # land it after and it is the final sample credited one typical interval. Pinning the exact
    # number made this check a clock reading rather than a category test.
    from mushegh.brain.presence import _category

    check("vlc maps to the media category", _category("vlc") == "media", _category("vlc"))
    check("...and the ingested sample reaches today's screen time",
          p.screen_time(0)["categories"].get("media", 0) >= 60,
          str(p.screen_time(0)["categories"]))

    print("\n[4] privacy off-switch")
    check("enabled by default", p.enabled)
    r = await act.activity_tracking({"action": "pause"})
    check("pause acknowledged", "paused" in r.lower(), r)
    check("tracking now off", not p.enabled)
    await act.activity_tracking({"action": "resume"})
    check("resume turns it back on", p.enabled)

    print("\n[5] tools speak sensible lines")
    st = await act.screen_time({"scope": "today"})
    check("screen_time tool returns the report", "active about" in st, st)
    ca = await act.current_activity({})
    check("current_activity tool returns a line", "sir" in ca, ca)

    print("\n[6] retention prune drops old samples")
    old = now - 40 * 86400
    p.record("oldapp", "ancient", 1.0, ts=old)
    p.prune()
    with p._conn() as c:  # noqa: SLF001 — test introspection
        left = c.execute("SELECT COUNT(*) FROM activity WHERE app='oldapp'").fetchone()[0]
    check("40-day-old sample pruned", left == 0, str(left))

    print("\n[7] proactive engine persists budget + suppression across a restart")
    from datetime import datetime, timedelta
    from zoneinfo import ZoneInfo
    from mushegh.brain.proactive import ProactiveEngine, Signal
    tz = ZoneInfo(settings.user_tz)
    t0 = datetime(2026, 7, 13, 12, 0, tzinfo=tz)
    state_file = str(Path(tmp.name) / "proactive_state.json")

    async def emit(msg, urg, listening):
        return "voice"

    def src():
        return [Signal(key="rent-nudge", message="the rent is due", urgency=0.9)]

    eng1 = ProactiveEngine(emit=emit, sources=[src], is_listening=lambda: True,
                           clock=lambda: t0, quiet_hours="", daily_budget=6, threshold=0.6,
                           repeat_suppress_minutes=120, state_path=state_file)
    inter = await eng1.maybe_interject(t0)
    check("first interjection fires", inter is not None and inter.channel == "voice")
    check("budget consumed", eng1._used_today == 1)
    check("state file written", Path(state_file).exists())

    # Simulate a brain RESTART: a brand-new engine loading the same state file.
    eng2 = ProactiveEngine(emit=emit, sources=[src], is_listening=lambda: True,
                           clock=lambda: t0 + timedelta(minutes=30), quiet_hours="", daily_budget=6,
                           threshold=0.6, repeat_suppress_minutes=120, state_path=state_file)
    check("budget survived restart", eng2._used_today == 1, str(eng2._used_today))
    again = await eng2.maybe_interject(t0 + timedelta(minutes=30))
    check("same nudge is suppressed after restart (no re-fire)", again is None)
    # after the suppression window, it may fire again (that's correct behaviour)
    eng3 = ProactiveEngine(emit=emit, sources=[src], is_listening=lambda: True,
                           clock=lambda: t0 + timedelta(minutes=150), quiet_hours="", daily_budget=6,
                           threshold=0.6, repeat_suppress_minutes=120, state_path=state_file)
    later = await eng3.maybe_interject(t0 + timedelta(minutes=150))
    check("fires again only after the suppression window elapses", later is not None)

    try:
        tmp.cleanup()
    except Exception:  # noqa: BLE001
        pass

    print(f"\n=== {passed}/{passed + failed} checks passed ===")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
