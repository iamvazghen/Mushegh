"""Uptime watcher state machine (TODO #1 P2) — edge-triggered, no repeat alerts.

The whole value of the watcher is that it alerts EXACTLY ONCE when the brain goes down and EXACTLY
ONCE when it recovers — never spamming a message every tick during a long outage. This verifies that
edge-triggered logic. Pure, offline, no network.

    uv run python bench/test_uptime_watch.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

passed = failed = 0


def check(name: str, ok: bool, detail: str = "") -> None:
    global passed, failed
    mark = "[PASS]" if ok else "[FAIL]"
    if ok:
        passed += 1
    else:
        failed += 1
    print(f"  {mark} {name}" + (f"  {detail}" if detail and not ok else ""))


def main() -> None:
    from deploy.uptime_watch import WatchState

    print("[1] no alert until `fails_needed` consecutive misses")
    s = WatchState(fails_needed=2)
    check("first miss is silent (could be a blip)", s.observe(False) is None)
    check("second miss fires the DOWN edge", s.observe(False) == "down")
    check("state is now down", s.down is True)

    print("\n[2] a long outage does NOT repeat the alert")
    repeats = [s.observe(False) for _ in range(5)]
    check("no repeat alerts during sustained outage", all(r is None for r in repeats), str(repeats))

    print("\n[3] recovery fires exactly one UP edge")
    check("first success fires the UP edge", s.observe(True) == "up")
    check("state is now up", s.down is False)
    check("further successes are silent", all(s.observe(True) is None for _ in range(3)))

    print("\n[4] a single blip below the threshold never alerts")
    s2 = WatchState(fails_needed=3)
    check("miss 1 silent", s2.observe(False) is None)
    check("miss 2 silent", s2.observe(False) is None)
    check("a success resets the counter", s2.observe(True) is None and s2.consecutive_fails == 0)
    check("two more misses still silent (counter reset)",
          s2.observe(False) is None and s2.observe(False) is None)
    check("never went down on a sub-threshold flap", s2.down is False)

    print("\n[5] fails_needed=1 alerts on the very first miss")
    s3 = WatchState(fails_needed=1)
    check("immediate down on one miss", s3.observe(False) == "down")
    check("immediate up on recovery", s3.observe(True) == "up")

    print("\n[6] full flap sequence yields exactly one down + one up")
    s4 = WatchState(fails_needed=2)
    seq = [False, False, False, False, True, True]   # down after 2, up on first True
    edges = [e for e in (s4.observe(x) for x in seq) if e is not None]
    check("exactly [down, up] across the flap", edges == ["down", "up"], str(edges))

    print("\n[7] 23.R1 — the brain's Healthchecks.io ping (dead man's switch)")
    import asyncio
    import httpx
    from mushegh.config import settings
    from mushegh.brain._scheduled_jobs import _fire_uptime_ping

    from mushegh.brain.tools import base

    hits: list[str] = []
    status = {"code": 200}

    async def fake_get(url: str, **kw) -> httpx.Response:
        hits.append(url)
        return httpx.Response(status["code"], request=httpx.Request("GET", url))

    real_get = base.http_get
    base.http_get = fake_get
    saved = settings.healthchecks_uuid
    try:
        settings.healthchecks_uuid = None
        asyncio.run(_fire_uptime_ping())
        check("no UUID -> no request at all", hits == [], str(hits))
        settings.healthchecks_uuid = " 1234-abcd "
        asyncio.run(_fire_uptime_ping())
        check("one GET to hc-ping.com/<uuid>", hits == ["https://hc-ping.com/1234-abcd"], str(hits))
        status["code"] = 503
        asyncio.run(_fire_uptime_ping())
        check("a failing ping is logged, never raised into the scheduler", len(hits) == 2)
    finally:
        base.http_get = real_get
        settings.healthchecks_uuid = saved

    print(f"\n=== {passed}/{passed + failed} checks passed ===")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
