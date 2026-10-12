"""Is Jev's tail a real risk, or one cold call?

§01.J3 measured `jev-latest` at p50 240 ms with a **26,655 ms p95** over six rounds, and concluded
the tail — not the median — is what would blow a voice turn. A p95 over six samples is two samples
wide, so that number could be a single cold call rather than a property of the model.

This asks the question properly: many rounds, every sample kept, outliers reported individually.
A one-off first call is a warm-up problem and is fixed by the pre-warm already in place. A tail that
reproduces is a design constraint.

    TYPESAFE_API_KEY=... python tools/probe_jev_tail.py
"""
from __future__ import annotations

import asyncio
import json
import os
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from mushegh.brain.judgment import DecisionOption, DecisionRequest, JudgmentService  # noqa: E402

KEY = os.environ.get("TYPESAFE_API_KEY", "").strip()
BUDGET_MS = 400.0

PROBE = DecisionRequest(
    question="The owner asked to 'check my email and remember the lease date'. Which tool group "
             "should serve the first part?",
    options=(DecisionOption("email", "read the mailbox"),
             DecisionOption("calendar", "read the calendar")),
    kind="tail_probe",
)


async def sample(model: str, rounds: int) -> list[float]:
    service = JudgmentService(key=KEY, model=model, timeout=30.0)
    out: list[float] = []
    for i in range(rounds):
        t0 = time.perf_counter()
        await service.judge(PROBE, correlation_id=f"tail-{i}")
        ms = (time.perf_counter() - t0) * 1000
        out.append(ms)
        print(f"    {i + 1:2}/{rounds}  {ms:8.0f} ms{'   <-- OVER BUDGET' if ms > BUDGET_MS else ''}")
        # A real turn does not hammer the same decision back to back; a short pause keeps this
        # measuring the model rather than this script's own connection reuse.
        await asyncio.sleep(0.4)
    return out


def report(model: str, samples: list[float]) -> dict:
    s = sorted(samples)
    over = [x for x in samples if x > BUDGET_MS]
    trimmed = [x for x in samples if x <= BUDGET_MS]
    row = {
        "model": model,
        "n": len(s),
        "min": round(s[0]),
        "p50": round(statistics.median(s)),
        "p90": round(s[int(len(s) * 0.9)]),
        "max": round(s[-1]),
        "over_budget": len(over),
        "p50_excluding_outliers": round(statistics.median(trimmed)) if trimmed else None,
        "first_call": round(samples[0]),
    }
    print(f"\n  {model}")
    print(f"    min {row['min']} | p50 {row['p50']} | p90 {row['p90']} | max {row['max']} ms")
    print(f"    over the {BUDGET_MS:.0f} ms budget: {len(over)}/{len(s)}")
    if over:
        print(f"    outliers: {[round(x) for x in sorted(over)]} ms")
    print(f"    first call (cold): {row['first_call']} ms — the warm-up signal")
    return row


async def main() -> int:
    if not KEY:
        print("TYPESAFE_API_KEY is not set.")
        return 2
    rounds = int(os.environ.get("ROUNDS", "12"))
    rows = []
    for model in ("jev-latest", "jev-preview"):
        print(f"\n--- {model} ({rounds} rounds) ---")
        rows.append(report(model, await sample(model, rounds)))

    print("\n=== verdict ===")
    latest = next(r for r in rows if r["model"] == "jev-latest")
    if latest["over_budget"] == 0:
        print("  the 26.6 s p95 did NOT reproduce — it was one cold call, and the pre-warm already")
        print("  covers it. The tail is not currently a design constraint.")
    elif latest["over_budget"] <= 2 and latest["first_call"] > BUDGET_MS:
        print("  the tail tracks the FIRST call, so it is a warm-up effect, not the model.")
    else:
        print(f"  {latest['over_budget']}/{latest['n']} calls exceeded the budget and the tail is")
        print("  NOT explained by warm-up. It is a property of the service and needs a strategy.")

    out = Path("logs/jev-tail-probe.json")
    out.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))