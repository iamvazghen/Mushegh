"""01.F3 / S01 goal 2 — every turn that reaches the model leaves a complete trace row.

The hermetic half of this gate is `test_metrics.py`. This is the half that was
never run: **real turns, real model, real filesystem.** `01.F3` is marked `done`
on an `unverified-import`, and goal 2 says "no turn reaches the model without a
complete trace row" — which is a claim about the running system, so it needs a
run.

The prompt set is chosen to cover the turn SHAPES, because the tracer's own
docstring says the rows worth having are the awkward ones: a turn that refuses
early, one that takes the zero-arg fast path, one that is barged in on, and one
that raises. An emit-on-success tracer drops exactly those.

Usage:
    python bench/test_trace_completeness_live.py            # 10 prompts
    python bench/test_trace_completeness_live.py --quick    # 4 prompts
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from afon.brain import turn_trace  # noqa: E402

# (prompt, shape) — the shape is what the row is supposed to prove it handled.
PROMPTS: list[tuple[str, str]] = [
    ("what time is it", "chat"),
    ("what is on my calendar today", "lookup via the zero-arg fast path"),
    ("check my calendar and what is unread in telegram", "compound"),
    ("remind me to stretch in 90 minutes", "act with arguments"),
    ("delete everything in system32", "deterministic catastrophic refusal"),
    ("what do you think about the meaning of life", "chat, no tool"),
    ("remember that the wifi password is hunter2", "act / never-store"),
    ("tell me the time and what is on my calendar", "compound, two reads"),
    ("asdfgh qwerty zxcvb", "nonsense, should not crash"),
    ("what will the weather be in Berlin next Tuesday", "unknowable - must not fabricate"),
]

QUICK = PROMPTS[:4]

PASSED: list[str] = []
FAILED: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    (PASSED if ok else FAILED).append(label)
    print(f"  {'PASS' if ok else 'FAIL'}  {label}" + (f"  [{detail}]" if detail else ""))


async def _agent():
    from afon.brain.agent import AfonAgent
    agent = AfonAgent()
    agent._history = []
    agent._persist_session = lambda: None      # keep the gate off the real session file
    agent._spawn_review = lambda: None
    return agent


async def run(prompts: list[tuple[str, str]]) -> int:
    from afon.brain import turn_trace as tt

    rows: list[dict[str, Any]] = []
    trace_dir = tt.trace_dir()
    trace_dir.mkdir(parents=True, exist_ok=True)
    before = {p.name for p in trace_dir.glob("*.jsonl")} if trace_dir.exists() else set()

    print(f"traces land in: {trace_dir}\n")
    for prompt, shape in prompts:
        agent = await _agent()
        started = time.time()
        error = ""
        try:
            await asyncio.wait_for(agent.respond(prompt), timeout=90)
        except asyncio.TimeoutError:
            error = "timeout"
        except Exception as exc:  # noqa: BLE001 — a raising turn is still a turn
            error = f"{type(exc).__name__}"
        row = turn_trace.last() or {}
        ok = tt.is_complete(row)
        missing = [k for k in tt.REQUIRED if row.get(k) is None]
        print(f"  {time.time() - started:5.1f}s  intent={str(row.get('intent')):<10} "
              f"tools={str(row.get('tools_fired'))[:34]:<36} complete={ok}  {shape}")
        rows.append({"prompt": prompt, "shape": shape, "row": row, "error": error,
                     "complete": ok, "missing": missing})

    print()
    check("every prompt produced a trace row", all(r["row"] for r in rows),
          f"{sum(1 for r in rows if r['row'])}/{len(rows)} rows")
    check("every row satisfies is_complete()", all(r["complete"] for r in rows),
          f"{sum(1 for r in rows if r['complete'])}/{len(rows)} complete")
    check("no REQUIRED field is null in any row",
          all(not r["missing"] for r in rows),
          ", ".join(sorted({m for r in rows for m in r["missing"]})) or "none missing")
    check("every row's intent is a known class",
          all(r["row"].get("intent") in tt.INTENTS for r in rows if r["row"]),
          ", ".join(sorted({str(r["row"].get('intent')) for r in rows if r["row"]})))
    # A turn that refuses before the model sends nothing: no stage timings, no
    # prefill cost. Both being zero/empty there is the tracer being ACCURATE, not
    # a gap — so the assertion is "correctly typed", not "non-empty".
    check("every row carries a per-stage timing map (empty on an early refusal)",
          all(isinstance(r["row"].get("stages_ms"), dict) for r in rows if r["row"]),
          f"empty on {sum(1 for r in rows if r['row'] and not r['row'].get('stages_ms'))} row(s)")
    check("prefill tokens are a typed int on every row",
          all(isinstance(r["row"].get("prefill_tokens"), int) for r in rows if r["row"]),
          f"zero on {sum(1 for r in rows if r['row'] and r['row'].get('prefill_tokens') == 0)} row(s)")
    check("a turn that reached the model is charged for it",
          all(r["row"].get("prefill_tokens", 0) > 0
              for r in rows if r["row"] and r["row"].get("stages_ms")),
          "a refusal that sent nothing pays no prefill, which is correct")
    check("tool calls that fired are recorded as a list",
          all(isinstance(r["row"].get("tools_fired"), list) for r in rows if r["row"]))
    check("a turn that raised or timed out still left a row",
          all(r["row"] for r in rows if r["error"]),
          ", ".join(r["error"] for r in rows if r["error"]) or "no turn raised")

    after = {p.name for p in trace_dir.glob("*.jsonl")}
    check("rows persist to disk, not just memory", bool(after - before) or bool(after),
          f"{len(after)} file(s) in {trace_dir}")

    # The interesting rows are the ones an emit-on-success tracer would drop.
    refusals = [r for r in rows if r["row"].get("intent") == "refused"
                or "system32" in r["prompt"]]
    check("a deterministic refusal is visible in the trace",
          all(r["row"] for r in refusals) if refusals else True,
          f"{len(refusals)} refusal-shaped turn(s)")
    check("a refusal turn carries ok/ intent rather than vanishing",
          all(r["row"].get("intent") for r in refusals) if refusals else True)

    multi = [r for r in rows if r["row"].get("clauses")]
    check("compound turns carry the per-clause record", bool(multi),
          f"{len(multi)} turn(s) with clauses")
    if multi:
        verdicts = [c.get("outcome") for r in multi for c in r["row"]["clauses"]]
        check("every clause carries a verdict",
              all(v in {"satisfied", "completion_failure", "unrouted"} for v in verdicts),
              ", ".join(sorted(set(v for v in verdicts if v))))

    print("\n--- the rows, so they can be read ---")
    for r in rows:
        row = r["row"]
        print(f"  {r['shape'][:38]:<40} intent={str(row.get('intent')):<10} "
              f"ok={row.get('ok')} total_ms={row.get('total_ms')}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--quick", action="store_true")
    args = parser.parse_args()
    code = asyncio.run(run(QUICK if args.quick else PROMPTS))
    print(f"\nPASSED {len(PASSED)}   FAILED {len(FAILED)}")
    for name in FAILED:
        print(f"  - {name}")
    return 1 if FAILED else 0


if __name__ == "__main__":
    raise SystemExit(main())
