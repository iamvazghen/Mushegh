"""One-shot: record the 2026-10-10 scorer-integrity finding on 01.E2.

A file rather than `python -c` because the note contains quotes and apostrophes; inlining it
into a PowerShell here-string mangles them.
"""

import json

PATH = "docs/systems-plan.json"

NOTE = (
    "Scorer integrity, found by reading a passing result rather than a failing one. "
    "`proactivity_list` scored 100.0 with the note 'reply content matched' on the reply: "
    "I could not fetch your reminders, sir. That is a FAILURE. `list_reminders` had raised, "
    "`tool_error` returned its prose, and the model paraphrased it - and the scenario still scored "
    "full marks for two independent reasons. First, the expectation check counted a tool as "
    "satisfied if it was INVOKED, never asking whether it worked, so a dead integration "
    "satisfied `expect_tools`. Second, the reply contained the word 'reminder', which is one of "
    "the expect_text substrings, so a failure message matched the content check. "
    "The expectation now uses tools that ran AND returned something `looks_failed` does not "
    "recognise, which catches the hard shape (`ok=False`, the handler raised) and the soft one "
    "(`tool_error` prose returned with `ok=True`, how most of this codebase reports a degraded "
    "capability). Verified: hard failure and soft failure both now score 50.0 instead of 100.0, "
    "a genuine success still scores 100.0, and an EMPTY reminder list still scores 100.0 "
    "because having nothing set is an answer, not a failure. "
    "The consequence is worth stating plainly rather than burying: this will LOWER several "
    "category scores, because dead integrations were previously scoring full marks. Every "
    "behavioural number measured before this fix was optimistic, and any comparison across it is "
    "invalid unless both sides used the same scorer."
)


def main() -> int:
    with open(PATH, encoding="utf-8") as fh:
        plan = json.load(fh)

    s01 = next(s for s in plan["systems"] if s["id"] == "S01")
    e2 = next(t for t in s01["tasks"] if t["id"] == "01.E2")
    e2.setdefault("evidence", []).append({
        "kind": "recorded-note",
        "source": "bench/behavioral_suite.py _score_turn, 2026-10-10",
        "note": NOTE,
    })

    with open(PATH, "w", encoding="utf-8") as fh:
        json.dump(plan, fh, indent=2, ensure_ascii=False)
    print("01.E2 scorer-integrity finding recorded")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())