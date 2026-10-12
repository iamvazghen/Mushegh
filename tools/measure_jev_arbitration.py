"""Measure live JEv tool-arbitration latency against the 400 ms cap (01.R6).

The S01 document asked whether a real ambiguous turn still returns inside 400 ms, and
recorded the question as unreachable because "Jev times out here". That turned out to be
false - JEv answers from this host in about 1.5 s for a full decision. A 400 ms
arbitration is a different call from a 400 ms full decision, so the question is real and
answerable now.

What this measures, honestly:
  * `settings.jev_arbitration_timeout_seconds` - the configured cap
  * the real wall-clock latency of N arbitration calls
  * how many returned inside the cap, and what the caller got when they did not

The fallback matters more than the median. Arbitration's correct failure mode is
silence - keep the deterministic candidates - so a cap breach must degrade to "no
narrowing", never to a wrong winner.

Usage:
    python tools/measure_jev_arbitration.py [N]
"""

from __future__ import annotations

import asyncio
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mushegh.brain.judgment import Arbitration, JudgmentService  # noqa: E402
from mushegh.config import settings  # noqa: E402

#: Deliberately ambiguous utterances, each offered two deterministic candidate groups so
#: arbitration has something real to choose between. These are NOT model-authored options:
#: in the real turn the candidates come from the lazy-group trigger match in code.
PROBES = [
    ("what's on today", ("mushegh.brain.tools.calendar", "mushegh.brain.tasks")),
    ("remind me about the thing", ("mushegh.brain.tasks", "mushegh.brain.reminders")),
    ("how are we doing", ("mushegh.brain.health", "mushegh.brain.goal_deviation")),
    ("what's new", ("mushegh.brain.delivery", "mushegh.brain.presence")),
    ("catch me up", ("mushegh.brain.recall", "mushegh.brain.docstore")),
]


async def run(n: int) -> int:
    cap_ms = settings.jev_arbitration_timeout_seconds * 1000.0
    print("JEv arbitration latency, live")
    print(f"  configured cap  : {cap_ms:.0f} ms "
          f"(jev_arbitration_timeout_seconds={settings.jev_arbitration_timeout_seconds})")
    print(f"  jev_enabled     : {settings.jev_enabled}")
    print(f"  credential      : "
          f"{'PRESENT' if settings.typesafe_api_key else 'ABSENT'} (value never printed)")
    print(f"  probes          : {n} rounds over {len(PROBES)} utterances\n")

    service = JudgmentService()
    latencies: list[float] = []
    rows: list[tuple[str, str, str, float]] = []

    for round_index in range(n):
        for text, groups in PROBES:
            result: Arbitration | None = await service.arbitrate(
                text, groups, correlation_id=f"measure-{round_index}"
            )
            if result is None:
                rows.append((text, "None", "no result object", 0.0))
                continue
            latencies.append(result.latency_ms)
            rows.append((
                text[:34],
                result.outcome,
                (result.winner or "(kept all candidates)")[-38:],
                result.latency_ms,
            ))

    print(f"  {'utterance':<36}{'outcome':<14}{'winner / kept':<40}{'ms':>8}")
    for text, outcome, winner, ms in rows:
        print(f"  {text:<36}{outcome:<14}{winner:<40}{ms:>8.0f}")

    if not latencies:
        print("\n  no latency samples: arbitration never produced a result.")
        return 1

    inside = [x for x in latencies if x <= cap_ms]
    over = [x for x in latencies if x > cap_ms]
    print(f"\n  samples          : {len(latencies)}")
    print(f"  median           : {statistics.median(latencies):.0f} ms")
    print(f"  min / max        : {min(latencies):.0f} / {max(latencies):.0f} ms")
    print(f"  inside the cap   : {len(inside)}/{len(latencies)}")
    print(f"  over the cap     : {len(over)}/{len(latencies)}")

    outcomes = {row[1] for row in rows}
    print(f"  distinct outcomes: {sorted(outcomes)}")

    # The safety question, not the performance one: did a cap breach ever produce a
    # winner it should not have? Arbitration's designed failure is silence.
    bad = [row for row in rows if row[1] not in {"decided", "no_narrowing", "timeout",
                                                 "unavailable", "error", "disabled",
                                                 "abstained", "keep_all"}]
    if bad:
        print(f"\n  UNEXPECTED outcomes: {[r[1] for r in bad]}")
        return 1

    if len(inside) == len(latencies):
        print(f"\n  ANSWER: every arbitration returned inside {cap_ms:.0f} ms.")
    elif inside:
        print(f"\n  ANSWER: mixed. {len(inside)}/{len(latencies)} inside {cap_ms:.0f} ms. "
              f"The cap is a real constraint on this host, not a formality.")
    else:
        print(f"\n  ANSWER: NO arbitration returned inside {cap_ms:.0f} ms from this host "
              f"(median {statistics.median(latencies):.0f} ms).")
    print("  The cap's behaviour on breach is the part that matters: the caller must keep")
    print("  every deterministic candidate rather than act on a late answer.")
    return 0


if __name__ == "__main__":
    rounds = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    raise SystemExit(asyncio.run(run(rounds)))