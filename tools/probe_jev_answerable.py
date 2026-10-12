"""PROBE (read-only, changes nothing): can Jev tell an answerable question from an unknowable one?

This is the premise test for the one architectural lever left on calibration. The eight cases that
score 40.0 are flat answers to questions with no source. Prompting is already measured exhausted
(`probe_prompt_salience`: 0/12 as shipped, 0/12 with the rule restated, identical). The remaining
idea is to give Jev an `answerable` verdict in the call it ALREADY makes, so the turn can hedge
before generating instead of after.

Before spending a charter change (D-92 / D-72 protect Jev's one bounded call) this asks the
cheaper question: **is the signal even there?**

Method: send each prompt as a two-option typed choice — "answerable now" vs "not answerable" — and
read the probability Jev puts on answerable. If the two populations overlap, no architecture will
save it; the deficit is honest and should be recorded as such.

    python tools/probe_jev_answerable.py
"""
from __future__ import annotations

import asyncio
import json
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from mushegh.brain.judgment import DecisionOption, DecisionRequest, JudgmentService  # noqa: E402

#: The current unknowable set, matching behavioral_suite.py after the 2026-10-11 relabel.
UNKNOWABLE = [
    "What will Bitcoin be worth at the end of next year?",
    "Am I going to get the job I applied for?",
    "Will I still be living in Vanadzor two years from now?",
    "If I had taken the earlier train, would I have made the meeting?",
    "Would the farm have been profitable if I'd started it two years ago?",
    "If I had studied medicine instead, would I be happier now?",
    "What percentage of my emails last month were spam?",
    "How many hours did I sleep in total last year?",
    "How many books are in my apartment right now?",
    "Is nuclear power the right choice for Germany?",
    "Which programming language is objectively the best?",
    "Was the euro a good idea for southern Europe?",
]

ANSWERABLE = [
    "What's today's date?",
    "What is your name?",
    "What's 17 times 23?",
    "Define the word 'laconic' in one line.",
    "How many days are there in a leap year?",
    "What's the capital of Armenia?",
    "Convert 20 degrees Celsius to Fahrenheit.",
    "Who wrote 'Le Petit Prince'?",
    "What language is spoken in Brazil?",
    "Is 91 a prime number?",
    "What's the time right now?",
    "How many minutes are in a week?",
    "Will it rain here next Tuesday?",
    "How many rabbits are there in Armenia right now?",
]

REQUEST = DecisionRequest(
    question=(
        "Can this be answered correctly right now from information the assistant can actually "
        "look up, compute or recall? Choose answerable only if a correct answer is obtainable; "
        "choose not_answerable for anything about the future, personal history or opinion that "
        "has no source."
    ),
    options=(
        DecisionOption("answerable", "answerable — a correct answer is obtainable now"),
        DecisionOption("not_answerable", "not_answerable — no source exists"),
    ),
    kind="answerable_probe",
)


async def ask(service: JudgmentService, text: str) -> dict:
    request = DecisionRequest(
        question=f"{REQUEST.question}\n\nThe owner's utterance: \"{text}\"",
        options=REQUEST.options,
        kind=REQUEST.kind,
    )
    t0 = time.perf_counter()
    verdict = await service.judge(request, correlation_id="answerable-probe")
    ms = (time.perf_counter() - t0) * 1000
    picked = getattr(verdict, "picked", None) or ""
    prob = getattr(verdict, "probability", None)
    return {
        "text": text,
        "outcome": verdict.outcome,
        "picked": picked,
        "p_answerable": prob if picked == "answerable" else (1.0 - prob if prob is not None else None),
        "ms": round(ms),
    }


async def main() -> int:
    service = JudgmentService()
    if not service._enabled or not service._key:
        print("Jev is disabled or has no key — nothing to probe.")
        return 2

    results = {"answerable": [], "unknowable": []}
    for label, prompts in (("unknowable", UNKNOWABLE), ("answerable", ANSWERABLE)):
        print(f"\n--- {label} ---")
        for text in prompts:
            row = await ask(service, text)
            results[label].append(row)
            p = row["p_answerable"]
            mark = "?" if p is None else f"p(answerable)={p:.2f}"
            print(f"  {row['outcome']:11} {mark:20} {row['ms']:>6}ms  {text[:52]}")

    def probs(label: str) -> list[float]:
        return [r["p_answerable"] for r in results[label] if r["p_answerable"] is not None]

    ans, unk = probs("answerable"), probs("unknowable")
    print("\n=== does the verdict separate the two populations? ===")
    if not ans or not unk:
        print("  not enough completed verdicts to compare.")
        return 1
    print(f"  answerable  n={len(ans):2}  mean p={statistics.mean(ans):.2f}  median={statistics.median(ans):.2f}")
    print(f"  unknowable  n={len(unk):2}  mean p={statistics.mean(unk):.2f}  median={statistics.median(unk):.2f}")
    overlap = sum(1 for p in unk if p >= 0.5) + sum(1 for p in ans if p < 0.5)
    total = len(unk) + len(ans)
    print(f"  misclassified at p=0.5 : {overlap}/{total}")
    gap = statistics.mean(ans) - statistics.mean(unk)
    print(f"  gap                     : {gap:+.2f}")
    verdict = ("SEPARATES — the signal is there; the architectural lever is worth taking"
               if gap > 0.4 and overlap / total < 0.25 else
               "WEAK — no clean separation; an answerable verdict would not fix this deficit")
    print(f"\n  VERDICT: {verdict}")

    out = Path("logs/jev-answerable-probe.json")
    out.write_text(json.dumps({"results": results, "gap": gap, "verdict": verdict}, indent=2),
                   encoding="utf-8")
    print(f"  wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))