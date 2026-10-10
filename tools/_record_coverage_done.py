"""One-shot: record the 2026-10-10 coverage-floor remediation result on 01.E2.

A file rather than `python -c` because the note contains quotes; inlining prose with quotes into
a PowerShell here-string mangles them.
"""

import json

PATH = "docs/systems-plan.json"

NOTE = (
    "Coverage floor remediated: 62 -> 73 scenarios, and the number of categories sitting exactly "
    "on MIN_RUNNABLE_PER_CATEGORY = 2 went from TWELVE OF SEVENTEEN to TWO. What remains is "
    "Fleet, which the owner reserved, and Multi-Device, which needs two live edge clients and so "
    "cannot be asserted hermetically. Every new scenario was checked twice before being written "
    "down: first that the tool exists in the registry, then that calling it directly returns real "
    "data rather than raising. "
    "The additions, and why each is a different path rather than a third copy of what sat beside "
    "it. Tasks gained task_status_local, which reads the LOCAL task store rather than Notion, so "
    "the category has a scenario that cannot go down with a Notion token. Knowledge gained "
    "journal_recall, covering the L2 journal where the existing two only touched the L3 vault. "
    "Safety gained a mass-deletion refusal, a third shape beside the outward-send and the "
    "system-directory cases. Latency gained a one-word turn. Honesty gained an ANSWERABLE "
    "control that must be answered, which is what stops the category rewarding a refusal. Web "
    "gained a search that does not need the scraper, which is currently 402 on every URL. "
    "Memory and Conversation each gained one. "
    "Autonomy gained autonomy_inline, which is a boundary test rather than another capability: "
    "a trivial question that must NOT be backgrounded. An Autonomy category whose two scenarios "
    "both delegate cannot tell 'correctly delegated' from 'delegated everything'. "
    "Proactivity gained proactivity_next, because its other two SET and READ and never exercise "
    "the proactive path of offering a suggestion. "
    "Two of these were found by measuring and both were authored wrong first: conversation_"
    "followup was described as a second turn but written as a single one, so it scored 76.0 by "
    "answering with the current time - a reasonable reply to a question with no history and a "
    "useless test. And 'remind me what day of the week it is' routed to set_reminder and created "
    "a REAL 09:00 reminder, because the route matched 'remind me' without seeing that a question "
    "word followed; that is fixed with a discriminator and is a bug that would have bitten in "
    "ordinary use, not only in a test."
)


def main() -> int:
    with open(PATH, encoding="utf-8") as fh:
        plan = json.load(fh)

    s01 = next(s for s in plan["systems"] if s["id"] == "S01")
    e2 = next(t for t in s01["tasks"] if t["id"] == "01.E2")
    e2.setdefault("evidence", []).append({
        "kind": "recorded-note",
        "source": "bench/behavioral_suite.py scenario inventory + direct tool probes, 2026-10-10",
        "note": NOTE,
    })

    with open(PATH, "w", encoding="utf-8") as fh:
        json.dump(plan, fh, indent=2, ensure_ascii=False)
    print("01.E2 coverage remediation recorded")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())