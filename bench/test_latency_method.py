"""M13's method gate — the measurement protocol is fixed and matches D-35.

M13 has been open partly because nobody ever wrote the protocol down: the acceptance criterion
says "measured over 30 utterances per device, method and date recorded", and "30 utterances"
meant whatever the measurer happened to say. Neither existing latency gate measures M13 —
`test_latency_budget.py` is a one-round-trip regression tripwire and `test_latency_guard.py`
states outright that it cannot measure a real TTFW.

So this gate does the part that CAN be done hermetically: it proves the method exists, is
complete enough to be reproducible, and agrees with the charter on the budgets. It does NOT
measure latency, and it must not be mistaken for doing so — the number still requires a live
voice loop, and the edge is parked.

    uv run python bench/test_latency_method.py
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "bench" / "latency_corpus.json"
METHOD = ROOT / "docs" / "LATENCY-METHOD.md"
DECISIONS = ROOT / "docs" / "DECISIONS.md"

#: M13's words, quoted from ROADMAP.md so the gate fails if the milestone is quietly reworded.
MILESTONE_N = 30

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
    print("M13 — the latency measurement method (not a latency measurement)")

    print("\n[1] the artefacts exist")
    check("bench/latency_corpus.json", CORPUS.is_file(), str(CORPUS))
    check("docs/LATENCY-METHOD.md", METHOD.is_file(), str(METHOD))
    if not (CORPUS.is_file() and METHOD.is_file()):
        return 1
    corpus = json.loads(CORPUS.read_text(encoding="utf-8"))
    method = METHOD.read_text(encoding="utf-8")

    print("\n[2] the corpus is 30 utterances per device — the milestone's number")
    batches = corpus.get("batches") or []
    check("both devices are present", {b.get("device") for b in batches} == {"laptop", "phone"},
          str([b.get("device") for b in batches]))
    for b in batches:
        n = len(b.get("utterances") or [])
        check(f"{b.get('device')}: exactly {MILESTONE_N} utterances", n == MILESTONE_N, str(n))
        spoken = [u.get("say", "").strip() for u in (b.get("utterances") or [])]
        check(f"{b.get('device')}: no duplicate utterances", len(set(spoken)) == len(spoken),
              str([s for s, c in Counter(spoken).items() if c > 1]))
        check(f"{b.get('device')}: every utterance names a class",
              all(u.get("class") for u in b.get("utterances") or []))

    print("\n[3] the corpus is not one shape of turn wearing 30 hats")
    # A p95 over an all-chat corpus is a number about nothing in particular. The classes exist so
    # the reader can see WHAT the number is made of — compound turns can cost a second LLM round
    # trip, vault reads run, hedges add a pass.
    classes = Counter(u.get("class") for b in batches for u in (b.get("utterances") or []))
    for needed in ("reflex", "chat", "tool", "compound", "adversarial"):
        check(f"corpus exercises '{needed}' turns", classes.get(needed, 0) > 0, str(dict(classes)))
    check("no single class is more than half the corpus",
          max(classes.values()) <= sum(classes.values()) / 2, str(dict(classes)))

    print("\n[4] the budgets agree with the charter (D-35), not with this gate")
    d35 = DECISIONS.read_text(encoding="utf-8")
    block = re.search(r"##\s*D-35(.*?)(?=\n##\s*D-\d)", d35, re.S)
    check("D-35 is present in DECISIONS.md", block is not None)
    if block:
        charter = block.group(1)
        for device, budget in (("laptop", 300), ("phone", 500)):
            check(f"D-35 states the {device} budget as {budget} ms",
                  re.search(rf"{budget}\s*ms", charter) is not None, charter[:120])
    for b in batches:
        expected = 300 if b.get("device") == "laptop" else 500
        check(f"{b.get('device')}: corpus budget is D-35's {expected} ms",
              b.get("budget_ms") == expected, str(b.get("budget_ms")))
        check(f"{b.get('device')}: corpus cites the decision that owns its budget",
              str(b.get("decision")) == "D-35", str(b.get("decision")))

    print("\n[5] the method states what makes a number comparable")
    for needle, label in (
        ("p95", "p95 is reported"),
        ("per device", "per-device"),
        ("condition", "conditions are recorded"),
        ("date", "the date is recorded"),
        ("MAINTENANCE", "what blocks the run today is named"),
    ):
        check(f"method mentions {label}", needle.lower() in method.lower(), needle)
    # The exclusions are the part people skip, and skipping them is how a mean turns into a lie.
    check("method excludes reflex/barge-in turns from the average",
          ("barge-in" in method.lower() and "exclud" in method.lower()))
    check("method says plainly that it does not set the budget",
          re.search(r"must never be used to argue|does not set a budget|do not set a budget",
                    method, re.I) is not None)

    print("\n[6] this gate is NOT the measurement")
    # Said out loud on purpose: the honest state of M13 is "method fixed, number not taken".
    check("method states goal 7 is still 'not yet measured'",
          "not yet measured" in method.lower() or "no end-to-end latency number has been taken" in method.lower())

    print(f"\n=== {_passed}/{_passed + _failed} checks passed ===")
    return 1 if _failed else 0


if __name__ == "__main__":
    sys.exit(main())