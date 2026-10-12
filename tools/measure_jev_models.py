"""Measure the decision call against every model the TypeSafe catalogue actually serves.

§01.J1 asked which model should serve the decision call and recommended a *small, fast dedicated
model* at 0.63 confidence. That recommendation is only actionable if a smaller model exists, and
this checks that rather than assuming it: `GET /v1/models` returns what is served, and each entry
is then timed on the same call the turn path makes.

    TYPESAFE_API_KEY=... python tools/measure_jev_models.py
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from mushegh.brain.judgment import DecisionOption, DecisionRequest, JudgmentService  # noqa: E402

KEY = os.environ.get("TYPESAFE_API_KEY", "").strip()
CATALOGUE = "https://api.typesafe.ai/v1/models"

PROBE = DecisionRequest(
    question="The owner asked to 'check my email and remember the lease date'. Which tool group "
             "should serve the first part?",
    options=(DecisionOption("email", "read the mailbox"),
             DecisionOption("calendar", "read the calendar")),
    kind="model_latency_probe",
)


def catalogue() -> list[dict]:
    req = urllib.request.Request(CATALOGUE, headers={"Authorization": f"Bearer {KEY}"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8")).get("models", [])


async def time_model(model: str, rounds: int) -> dict:
    service = JudgmentService(key=KEY, model=model, timeout=30.0)
    samples, outcomes = [], []
    for _ in range(rounds):
        t0 = time.perf_counter()
        verdict = await service.judge(PROBE, correlation_id="model-probe")
        samples.append((time.perf_counter() - t0) * 1000)
        outcomes.append(verdict.outcome)
    samples.sort()
    return {
        "model": model,
        "rounds": rounds,
        "p50_ms": round(samples[len(samples) // 2]),
        "p95_ms": round(samples[int(len(samples) * 0.95)]),
        "min_ms": round(samples[0]),
        "decided": sum(1 for o in outcomes if o == "decided"),
        "outcomes": sorted(set(outcomes)),
    }


async def main() -> int:
    if not KEY:
        print("TYPESAFE_API_KEY is not set.")
        return 2
    models = catalogue()
    print(f"the catalogue serves {len(models)} model(s):")
    for m in models:
        print(f"  {m['name']:14} {m.get('description','')[:60]}")

    rounds = int(os.environ.get("ROUNDS", "6"))
    results = []
    for m in models:
        row = await time_model(m["name"], rounds)
        results.append(row)
        print(f"\n  {row['model']}: p50={row['p50_ms']}ms p95={row['p95_ms']}ms "
              f"decided={row['decided']}/{row['rounds']}")

    print("\n=== is any model fast enough for the 400 ms arbitration budget? ===")
    for row in results:
        verdict = "fits" if row["p50_ms"] <= 400 else "does not fit"
        print(f"  {row['model']:14} p50 {row['p50_ms']:>5}ms -> {verdict}")

    out = Path("logs/jev-model-latency.json")
    out.write_text(json.dumps({"catalogue": models, "results": results}, indent=2), encoding="utf-8")
    print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))