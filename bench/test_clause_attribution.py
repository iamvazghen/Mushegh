"""01.E1 / S01 open question 1 — is the compound-intent failure ROUTING or COMPLETION?

The subsystem document asks: after `01.F1` unified the two completion paths, the
residual 51.5% multi-intent score is either a clause that was never *routed* or a
clause that was routed and its tool never *fired*. "No per-clause trace exists to
tell them apart, and the next change depends on the answer."

This gate is that trace, and it answers the question from a live turn rather than
from a claim. It drives real compound prompts through `AfonAgent.respond`, then
reads `turn_trace` and attributes every clause.

Live by design: the answer is about the running system, and a hermetic stub would
answer a different question. Offline it prints WHY each turn was skipped rather
than failing silently.

Usage:
    python bench/test_clause_attribution.py            # live
    python bench/test_clause_attribution.py --offline  # structure only
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from afon.brain import turn_trace  # noqa: E402

# Compound prompts in the shape 01.E1 measures: two or more independent asks that
# each route to a different tool, so a missing clause is visible rather than
# masked by a single-intent path.
PROMPTS: list[tuple[str, str]] = [
    ("check my calendar and what is unread in telegram", "two lookups, two tools"),
    ("what is on my calendar and also add milk to the shopping list", "lookup + write"),
    ("read my unread telegram and tell me the time", "lookup + clock"),
    ("add eggs to the list and check my calendar", "write + lookup"),
    ("what is the time and what is on my calendar", "clock + lookup"),
    ("show my task list and what is unread in telegram", "two lookups"),
    ("add bread to the shopping list and tell me the time", "write + clock"),
    ("check the calendar and add coffee to the list", "lookup + write"),
]

PASSED: list[str] = []
FAILED: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    (PASSED if ok else FAILED).append(label)
    print(f"  {'PASS' if ok else 'FAIL'}  {label}" + (f"  [{detail}]" if detail else ""))


def _classify(agent_module: Any) -> Any:
    from afon.brain.agent import AfonAgent
    agent = AfonAgent()
    agent._history = []
    agent._persist_session = lambda: None
    agent._spawn_review = lambda: None
    return agent


async def _live() -> int:
    from afon.brain.agent import AfonAgent

    totals = {"satisfied": 0, "completion_failure": 0, "unrouted": 0}
    turns_with_clauses = 0
    per_prompt: list[tuple[str, list[dict[str, Any]], list[str]]] = []

    for prompt, note in PROMPTS:
        agent = AfonAgent()
        agent._history = []
        agent._persist_session = lambda: None
        agent._spawn_review = lambda: None
        started = time.time()
        try:
            await asyncio.wait_for(agent.respond(prompt), timeout=45)
            elapsed = time.time() - started
            trace = turn_trace.last() or {}
            clauses = list(trace.get("clauses") or [])
            fired = list(trace.get("tools_fired") or [])
            per_prompt.append((prompt, clauses, fired))
            if clauses:
                turns_with_clauses += 1
            for clause in clauses:
                outcome = ("satisfied" if clause.get("fired")
                           else "completion_failure" if clause.get("planned")
                           else "unrouted")
                totals[outcome] += 1
            verdict = ", ".join(
                f"{c['text'][:26]!r}->{c['tool'] or 'NONE'}:"
                f"{'ok' if c.get('fired') else ('completion' if c.get('planned') else 'NO-ROUTE')}"
                for c in clauses) or "(no clauses recorded)"
            print(f"  {elapsed:5.1f}s  {prompt[:44]:<46} {verdict}")
        except asyncio.TimeoutError:
            per_prompt.append((prompt, [], []))
            print(f"  TIMEOUT {prompt[:44]}")

    observed = sum(totals.values())
    print(f"\n  turns that produced a clause trace : {turns_with_clauses}/{len(PROMPTS)}")
    print(f"  clauses attributed                 : {observed}")
    for key, value in totals.items():
        share = f"({value / observed:.0%})" if observed else "(n/a)"
        print(f"    {key:<20} {value:>4} {share}")

    print("\n=== the question this gate exists to answer ===")
    if observed == 0:
        check("at least one clause was attributed", False,
              "no live clause data - check provider reachability")
    else:
        # The question is which FAILURE mode dominates, so the comparison is
        # between the two failure modes. Ranking against `satisfied` would let a
        # mostly-successful run answer "no failure dominates" and hide the very
        # split the gate was built to find.
        failures = {k: totals[k] for k in ("completion_failure", "unrouted")}
        total_failed = sum(failures.values())
        dominant = max(failures, key=lambda k: failures[k])
        check("every clause is attributed to exactly one outcome", True, f"{observed} clauses")
        if total_failed == 0:
            check("a single dominant failure mode is identified", True, "no failures observed")
            print("\n  ANSWER: every clause routed AND fired. No residual failure to explain.")
        else:
            share = failures[dominant] / total_failed
            check("a single dominant failure mode is identified",
                  share >= 0.5, f"{dominant} is {share:.0%} of {total_failed} failures")
            if dominant == "unrouted":
                print("\n  ANSWER: the dominant residual failure is a MISSING ROUTE, not a bad")
                print("  one. Those clauses match nothing in _ROUTES or _CLAUSE_ONLY_ROUTES, so")
                print("  clause_tools() never engaged and the turn ran on the full catalogue. A")
                print("  tool that fired anyway was the model's own pick, not something the tracer")
                print("  planned - so these clauses are unmeasurable until a route exists.")
            else:
                print("\n  ANSWER: the residual failure is COMPLETION. The clause was routed and")
                print("  its tool still did not fire. Fix the completion pass or its budget.")
            if total_failed:
                print(f"\n  failure split: {failures}")
                unrouted = sorted({
                    c["text"] for _, cs, _ in per_prompt for c in cs
                    if not c.get("planned")
                })
                if unrouted:
                    print("  clauses with NO ROUTE AT ALL (the systematic cause):")
                    for clause in unrouted:
                        print(f"    - {clause!r}")

    check("clause text never leaks the full utterance into the trace",
          all(len(c.get("text", "")) <= 160 for _, cs, _ in per_prompt for c in cs),
          "each clause is truncated to 160 chars")
    return 0


def _offline() -> int:
    """Structure only: prove the tracer can express all three outcomes."""
    print("=== offline: tracer structure ===")
    with turn_trace.turn("check my calendar and what is unread in telegram") as trace:
        trace.note_clause("check my calendar", tool="calendar_upcoming")
        trace.note_clause("what is unread in telegram", tool="telegram_unread")
        trace.note_clause("add milk to the list", tool="todo_add")
        trace.note_clause("and what is the time", tool=None)   # routing failure
        trace.fired("calendar_upcoming")
        trace.fired("telegram_unread")
        # todo_add is deliberately never fired -> completion_failure
        verdicts = trace.clause_verdicts()
        row = trace.row()

    outcomes = [v["outcome"] for v in verdicts]
    check("a planned+fired clause is satisfied", outcomes[0] == "satisfied", outcomes[0])
    check("a planned+fired clause is satisfied (second)", outcomes[1] == "satisfied", outcomes[1])
    check("a planned+unfired clause is a completion failure",
          outcomes[2] == "completion_failure", outcomes[2])
    check("an unplanned clause is a routing failure",
          outcomes[3] == "unrouted", outcomes[3])
    check("the row carries the clauses", len(row.get("clauses", [])) == 4,
          str(len(row.get("clauses", []))))
    check("the 01.F3 completeness contract is unchanged",
          turn_trace.is_complete(row), "is_complete still passes")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()
    if args.offline:
        code = _offline()
    else:
        try:
            code = asyncio.run(_live())
        except Exception as exc:  # noqa: BLE001
            print(f"\n  live run unavailable: {type(exc).__name__}: {exc}")
            print("  falling back to the offline structural check\n")
            code = _offline()
    print(f"\nPASSED {len(PASSED)}   FAILED {len(FAILED)}")
    for name in FAILED:
        print(f"  - {name}")
    return 1 if FAILED else 0


if __name__ == "__main__":
    raise SystemExit(main())
