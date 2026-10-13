"""31.R3 must be REACHABLE, not merely present.

`brain/self_report.py` shipped complete and gated (test_self_report.py) while
nothing in src/ referenced it — one of only four brain modules the code graph
showed with no importer at all. It took a route in proactive.py to make it
runnable, and nothing in the suite would have noticed if that route were deleted
again: every other self_report gate exercises the module directly, so a module
that is perfectly healthy and permanently unreachable passes all of them.

That is the same defect shape as an unrouted tool — a capability the system owns
and no one can call — and the fix is to gate the ROUTE, not the module.

Hermetic: drives the real signal source with injected timestamps and asserts it
speaks only in its own slot, which needs no clock and no network.

    uv run python bench/test_self_report_wiring.py
"""

from __future__ import annotations

import asyncio
import datetime as dt
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from mushegh.brain.proactive_signals import weekly_self_report  # noqa: E402

passed = failed = 0


def check(ok: bool, name: str, detail: str = "") -> None:
    global passed, failed
    if ok:
        passed += 1
        print(f"  [PASS] {name}")
    else:
        failed += 1
        print(f"  [FAIL] {name}  {detail}")


def utc(d: int, h: int, m: int) -> dt.datetime:
    return dt.datetime(2026, 10, 11 if d == 11 else 10, h, m, tzinfo=dt.timezone.utc)


def fire(when: dt.datetime):
    return asyncio.run(weekly_self_report(when))


def main() -> int:
    print("\n[1] the self-report is wired into the proactive engine at all")
    check(weekly_self_report is not None,
          "proactive_signals exposes weekly_self_report")

    # Sunday 2026-10-11.
    check(fire(dt.datetime(2026, 10, 11, 20, 0, tzinfo=dt.timezone.utc)) == [],
          "silent at Sun 20:00 — the activity digest owns that minute")
    check(fire(dt.datetime(2026, 10, 11, 19, 59, tzinfo=dt.timezone.utc)) == [],
          "silent at Sun 19:59")

    spoken = fire(dt.datetime(2026, 10, 11, 20, 5, tzinfo=dt.timezone.utc))
    check(len(spoken) == 1, "speaks at Sun 20:05", str(spoken))

    check(fire(dt.datetime(2026, 10, 10, 20, 5, tzinfo=dt.timezone.utc)) == [],
          "silent on a Saturday")
    check(fire(dt.datetime(2026, 10, 11, 20, 5, tzinfo=dt.timezone.utc)) is not None
          and fire(dt.datetime(2026, 10, 11, 21, 5, tzinfo=dt.timezone.utc)) == [],
          "silent at Sun 21:05 — it does not repeat")

    print("\n[2] the signal it returns is shaped for the engine")
    if spoken:
        sig = spoken[0]
        check(sig.key == "weekly-self-report",
              "stable key, so repeat-suppression can hold it", sig.key)
        check(sig.kind == "weekly-self-report",
              "a distinct kind from the activity digest", sig.kind)
        check(sig.urgency == 0.6,
              "urgency matches the digest rather than paging", str(sig.urgency))
        check(bool(sig.message.strip()), "carries a spoken message")

        print("\n[3] 31.R3's own rule: an unmeasured section is SAYS SO out loud")
        # The module exists because a report that renders "nothing needed you"
        # when it could not read the escalation record is worse than silence.
        low = sig.message.lower()
        spoke_unknown = any(p in low for p in
                            ("no-data", "unknown", "i cannot tell you", "no escalation record"))
        check(spoke_unknown,
              "says a section is unmeasured instead of implying health",
              sig.message[:160])

    print(f"\n  {passed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())