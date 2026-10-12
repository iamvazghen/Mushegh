"""Where does the 10–32 s per turn actually go?

01.J6c established that a turn spends 10–32 seconds in work that is neither `LLMClient.complete`
nor a tool call — 01.J6c's own `check my telegram` row spent 32.5 s with **zero** model calls. This
wraps every step `_prepare_turn` performs and reports each one's own wall-clock, so the cost gets a
name instead of a remainder.

Deliberately counting the Jev calls too: they are direct HTTP requests and do NOT go through
`LLMClient.complete`, which is exactly why the earlier attribution missed them.

    python tools/probe_turn_breakdown.py
"""
from __future__ import annotations

import asyncio
import time
from collections import defaultdict
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from mushegh.brain import judgment as J  # noqa: E402
from mushegh.brain.agent import MusheghAgent  # noqa: E402

TIMES: dict[str, list[float]] = defaultdict(list)


def timed(obj, name: str, label: str | None = None):
    label = label or name
    orig = getattr(obj, name)

    async def wrapper(*a, **kw):  # noqa: ANN001, ANN202
        t0 = time.perf_counter()
        try:
            return await orig(*a, **kw)
        finally:
            TIMES[label].append((time.perf_counter() - t0) * 1000)

    setattr(obj, name, wrapper)
    return orig


TURNS = [
    "check my telegram",       # §01.J2 skips the decision call entirely
    "what time is it",
    "how was your day",
]


async def main() -> int:
    timed(J.JudgmentService, "consider", "jev:consider")
    timed(J.JudgmentService, "assess_turn", "jev:assess_turn")
    timed(J.JudgmentService, "arbitrate", "jev:arbitrate")

    agent = MusheghAgent()
    timed(agent, "_recall_note", "recall_note")
    timed(agent, "_relational_note", "relational_note")
    timed(agent, "_world_note", "world_note")
    timed(agent, "_prepare_turn", "PREPARE_TURN (total)")
    agent._self_improve = False

    rows = []
    for text in TURNS:
        TIMES.clear()
        t0 = time.perf_counter()
        try:
            await agent.respond(text)
        except Exception as exc:  # noqa: BLE001
            print(f"  {text!r} ERROR {type(exc).__name__}: {exc}"[:120])
            continue
        total = (time.perf_counter() - t0) * 1000
        parts = {k: round(sum(v)) for k, v in TIMES.items() if k != "PREPARE_TURN (total)"}
        prep = TIMES.get("PREPARE_TURN (total)", [0])
        print(f"\n  {text!r}  total={total:.0f} ms")
        for k, ms in sorted(parts.items(), key=lambda kv: -kv[1]):
            print(f"      {k:22} {ms:8.0f} ms")
        print(f"      {'--- prepare total':22} {sum(prep):8.0f} ms")
        print(f"      {'--- everything else':22} {total - sum(prep):8.0f} ms")
        rows.append((text, total, parts, sum(prep), total - sum(prep)))

    print("\n=== the largest repeated cost across turns ===")
    agg: dict[str, float] = defaultdict(float)
    for _t, _tot, parts, _p, _rest in rows:
        for k, ms in parts.items():
            agg[k] += ms
    for k, ms in sorted(agg.items(), key=lambda kv: -kv[1])[:5]:
        print(f"  {k:22} {ms/1000:6.1f} s total")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))