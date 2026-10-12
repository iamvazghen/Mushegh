"""Where did 117 seconds go? One utterance, instrumented.

01.J5 measured the worst turn in the corpus — "read the vault note about the rabbit farm and tell me
what it says" — at 117,084 ms. A voice turn that long is not slow, it is abandoned. This replays
that exact utterance with the agent's own timing visible: per-call LLM latency, tool calls, retries,
and the stage breakdown the trace already records.

    python tools/probe_slow_turn.py
"""
from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from mushegh.brain import audit  # noqa: E402
from mushegh.brain.agent import MusheghAgent  # noqa: E402

TARGET = "read the vault note about the rabbit farm and tell me what it says"

#: Everything the agent emits, with a clock, so the slow part is visible rather than inferred.
EVENTS: list[tuple[float, str, dict]] = []
T0 = time.perf_counter()


def _stamp(kind: str, **fields) -> None:
    EVENTS.append((time.perf_counter() - T0, kind, fields))


_orig_record = audit.record


def _record(tool, args, result, *, ok=True, **kw):  # noqa: ANN001, ANN202
    _stamp("tool", tool=str(tool), ok=bool(ok),
           args=str(args)[:120], result=str(result)[:120])
    return _orig_record(tool, args, result, ok=ok, **kw)


async def main() -> int:
    audit.record = _record

    from mushegh.brain import llm as llm_mod

    # The chain is where a second round trip hides, so count and time every completion.
    calls: list[float] = []
    real_complete = llm_mod.LLMClient.complete

    async def timed_complete(self, *a, **kw):  # noqa: ANN001, ANN202
        t0 = time.perf_counter()
        try:
            return await real_complete(self, *a, **kw)
        finally:
            calls.append((time.perf_counter() - t0) * 1000)

    llm_mod.LLMClient.complete = timed_complete  # type: ignore[method-assign]

    agent = MusheghAgent()
    agent._self_improve = False

    print(f"replaying: {TARGET!r}\n")
    t0 = time.perf_counter()
    reply = await agent.respond(TARGET)
    total = (time.perf_counter() - t0) * 1000

    print(f"\n=== total {total:.0f} ms ===")
    print(f"LLM completions: {len(calls)}  total {sum(calls):.0f} ms")
    for i, ms in enumerate(calls, 1):
        print(f"    {i:2}: {ms:8.0f} ms")
    print(f"non-LLM time   : {total - sum(calls):.0f} ms")

    print("\n=== tools ===")
    for ts, kind, fields in EVENTS:
        if kind == "tool":
            print(f"  {ts * 1000:8.0f} ms  {fields['tool']:22} ok={fields['ok']}")
            print(f"      args: {fields['args']}")
            print(f"      out : {fields['result']}")

    print("\n=== trace stages ===")
    try:
        from mushegh.brain import turn_trace

        row = turn_trace.current()
        stages = getattr(row, "stages", None) or getattr(row, "ms", None)
        print(f"  {stages}")
    except Exception as exc:  # noqa: BLE001
        print(f"  (stage readout unavailable: {type(exc).__name__})")

    print(f"\nreply: {reply[:220]}")

    out = Path("logs/slow-turn-probe.json")
    out.write_text(json.dumps({
        "utterance": TARGET, "total_ms": round(total),
        "llm_calls": [round(c) for c in calls],
        "llm_total_ms": round(sum(calls)),
        "non_llm_ms": round(total - sum(calls)),
        "events": [{"at_ms": round(ts * 1000), **f} for ts, _k, f in EVENTS],
    }, indent=2), encoding="utf-8")
    print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))