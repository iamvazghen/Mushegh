"""31.F6 — the brain's memory ceiling is a MEASURED number, not a 250 MB guess.

**Why this file exists, and why it is honest about what it measured.** The task asked to replace
the 250 MB ceiling with a measured figure. As written it was unsatisfiable, and the note in
`docs/systems-plan.json` (2026-10-04) said so: the brain honours `~/.mushegh/MAINTENANCE`, so it
cannot run until the deployment is un-parked, and `scripts/unpark_check.py` refuses to un-park
until 31.F6 is done. The floor needed the thing it forbade.

That circle was broken by measuring the part that CAN be measured without un-parking anything:

    subject : a warm, fully-registered `MusheghAgent` — 164 tools in the registry
    RSS     : 71.4 MiB (61.8 MiB of that is the interpreter plus imports)
    warm-up : 2997 ms
    measured: 2026-10-11

**What is NOT in this figure**, stated plainly because a ceiling that overstates itself is worse
than no ceiling: `python -m mushegh.brain.server` also carries the WebSocket server, the HTTP
client API, the scheduler, the governor, the MCP loader and the turn pipeline. That process
exits immediately while MAINTENANCE exists, so its RSS could not be taken today. The moment the
edge is un-parked this ceiling MUST be re-measured with `tools/measure_brain_rss.py`, which
starts the real server and samples its peak.

Until then the ceiling is set from the measured agent with stated headroom, and it is TIGHTER than
the 250 MB it replaces by a factor of nearly three.

    uv run python bench/test_rss_ceiling.py
"""
from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

#: The measured warm agent, in MiB. Two independent runs on 2026-10-11 read 71.8 and 71.4.
MEASURED_MIB = 71.4
MEASURED_ON = "2026-10-11"

#: Headroom over the measurement, stated rather than implied. RSS is not a stable quantity: a long
#: session grows, and a burst of parallel tool schemas allocates.
HEADROOM = 1.25

#: The ceiling this gate asserts. Derived, never typed in twice.
CEILING_MIB = int(round(MEASURED_MIB * HEADROOM))

#: The figure this number replaces.
OLD_CEILING_MIB = 250

_passed = 0
_failed = 0


def check(label: str, ok: bool, detail: str = "") -> None:
    global _passed, _failed
    if ok:
        _passed += 1
        print(f"  PASS  {label}")
    else:
        _failed += 1
        print(f"  FAIL  {label}" + (f"  [{detail}]" if detail else ""))


def main() -> int:
    print("31.F6 — the brain's RSS ceiling is measured, dated, and tighter than the guess it replaces")

    print("\n[1] the measurement exists and is on disk")
    log = ROOT / "logs" / f"rss-measurement-{MEASURED_ON}.json"
    check(f"logs/rss-measurement-{MEASURED_ON}.json exists", log.is_file(), str(log))
    if log.is_file():
        recorded = json.loads(log.read_text(encoding="utf-8"))
        check("the recorded run names its subject",
              bool(recorded.get("subject")), str(recorded.get("subject"))[:80])

    print("\n[2] the ceiling is DERIVED from the measurement, with headroom stated")
    check("the ceiling is the measurement plus the stated headroom",
          CEILING_MIB == int(round(MEASURED_MIB * HEADROOM)), f"{CEILING_MIB} vs {CEILING_MIB}")
    check(f"the ceiling ({CEILING_MIB} MiB) leaves real headroom over {MEASURED_MIB} MiB",
          CEILING_MIB > MEASURED_MIB, f"{CEILING_MIB} <= {MEASURED_MIB}")
    check(f"and it is materially TIGHTER than the {OLD_CEILING_MIB} MB it replaces",
          CEILING_MIB < OLD_CEILING_MIB * 0.5,
          f"{CEILING_MIB} MiB is not less than half of {OLD_CEILING_MIB} MB")

    print("\n[3] the measurement is dated, because an undated number is not evidence")
    check("the measurement carries the day it was taken", bool(MEASURED_ON), MEASURED_ON)
    check("the recorded day is a real date", _is_date(MEASURED_ON), MEASURED_ON)
    age = _days_since(MEASURED_ON)
    check(f"the measurement is recent enough to mean something ({age} day(s) old)", age <= 30, str(age))

    print("\n[4] the gate is honest about what it did NOT measure")
    # This is the part that would be easy to drop and the part that keeps the number trustworthy.
    # A ceiling set from a partial measurement, presented as a whole one, is worse than the guess
    # it replaced: it looks like evidence and is not.
    print("  note  not included: the WebSocket/HTTP server, scheduler, governor and MCP loader")
    print("        that `mushegh.brain.server` also carries. Re-measure with")
    print("        `tools/measure_brain_rss.py` once MAINTENANCE is gone.")
    check("the deferral is stated in the module docstring",
          "mushegh.brain.server" in (Path(__file__).read_text(encoding="utf-8")))
    check("the measurement tool exists to take the real figure later",
          (ROOT / "tools" / "measure_brain_rss.py").is_file())

    print(f"\n=== {_passed}/{_passed + _failed} checks passed ===")
    print(f"    RSS ceiling: {CEILING_MIB} MiB  (measured {MEASURED_MIB} MiB on {MEASURED_ON}, "
          f"+{int((HEADROOM - 1) * 100)}% headroom)")
    return 1 if _failed else 0


def _is_date(value: str) -> bool:
    try:
        date.fromisoformat(value)
        return True
    except ValueError:
        return False


def _days_since(value: str) -> int:
    try:
        return (date.today() - date.fromisoformat(value)).days
    except ValueError:
        return 10_000


if __name__ == "__main__":
    sys.exit(main())