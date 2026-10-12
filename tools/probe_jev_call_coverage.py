"""Measure which turns actually spend a Jev call — the 0.96 recommendation, checked.

§01.J1 asks for trivial turns to skip Jev entirely (confidence 0.96). `_prepare_turn` already skips
pure chatter via `_is_pure_chat`, so the question is what survives that gate. This sends one turn of
each class and reports, from the judgement log, whether a Jev row appeared for it.

    python tools/probe_jev_call_coverage.py
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from mushegh.brain.agent import MusheghAgent  # noqa: E402
from mushegh.brain.judgment import JUDGMENTS  # noqa: E402
from mushegh.shared.paths import state_dir  # noqa: E402

CLASSES: list[tuple[str, str]] = [
    ("chatter", "thanks"),
    ("chatter", "good morning"),
    ("reflex read", "what time is it"),
    ("reflex read", "stop"),
    # The 01.J1 slice: the router FORCES exactly one zero-argument read, so the decision call has
    # nothing to arbitrate, disambiguate or route. Added to the list so the effect of 01.J1 is
    # visible rather than asserted.
    ("forced read", "check my telegram"),
    ("forced read", "read my calendar"),
    ("forced read", "check my email"),
    ("forced read", "how many unread emails"),
    ("simple lookup", "what is the capital of Armenia"),
    ("act", "remember to call the dentist"),
    ("compound", "check my email and remember the lease date"),
    ("ambiguous", "send it"),
    ("decision", "open Chrome or Firefox"),
]


def rows_now() -> int:
    p = state_dir() / "jev_judgments.jsonl"
    if not p.is_file():
        return 0
    with p.open(encoding="utf-8", errors="replace") as fh:
        return sum(1 for line in fh if line.strip())


async def main() -> int:
    agent = MusheghAgent()
    print(f"{'class':15} {'turn':46} {'jev rows added':>15}")
    print("-" * 80)
    results = []
    for kind, text in CLASSES:
        before = rows_now()
        # The turn plan is what decides whether Jev is consulted; running the whole agent would
        # also spend an LLM call and touch live state.
        try:
            await agent._prepare_turn(text)
        except Exception as exc:  # noqa: BLE001
            print(f"{kind:15} {text[:44]:46} ERROR {type(exc).__name__}")
            continue
        after = rows_now()
        added = after - before
        mark = "SKIPPED" if added == 0 else f"{added} call(s)"
        print(f"{kind:15} {text[:44]:46} {mark:>15}")
        results.append({"class": kind, "text": text, "jev_calls": added})

    out = Path("logs/jev-call-coverage.json")
    out.write_text(json.dumps(results, indent=2), encoding="utf-8")
    skipped = [r for r in results if r["jev_calls"] == 0]
    print(f"\n{len(skipped)}/{len(results)} turn classes spent NO Jev call")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))