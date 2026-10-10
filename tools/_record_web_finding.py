"""One-shot: record the 2026-10-10 Web category finding in the S01 registry.

A file rather than `python -c` because the note contains quotes; inlining prose with quotes into
a PowerShell here-string mangles them.
"""

import json

PATH = "docs/systems-plan.json"

NOTE = (
    "Web 71.5 traced to a single scenario, and the mechanism was not the one it looked like. The "
    "router DOES force scrape_url for the turn - verified directly. But _MULTI_INTENT_RE matched "
    "the words 'and tell' in 'Open example.com AND TELL me the page heading' and labelled the turn "
    "multi-intent, and multi-intent turns SKIP router narrowing entirely, because _narrowed_tools "
    "returns early with the full tool surface. So nothing was forced, the model chose the `browser` "
    "tool instead, that tool failed, and the reply then answered from memory - 'the page heading is "
    "Example Domain' - which is a fabrication of the same shape as the fabricated journal entry found "
    "earlier in the same category. 'And TELL ME X' is how the FIRST result is reported back, not a "
    "second capability, so tell/give now carry a lookahead that excludes 'tell me'. send and reply stay "
    "unguarded on purpose, because 'and send me the link' genuinely is a second action. Verified on "
    "eight cases; seven gates green. One case in that set - 'Find the file and open it' - is NOT "
    "detected as multi, because 'open' has never been in that verb list; that is a pre-existing gap, "
    "unrelated to this fix, and recorded rather than silently widened."
)


def main() -> int:
    with open(PATH, encoding="utf-8") as fh:
        plan = json.load(fh)

    s01 = next(s for s in plan["systems"] if s["id"] == "S01")
    e2 = next(t for t in s01["tasks"] if t["id"] == "01.E2")
    e2.setdefault("evidence", []).append({
        "kind": "recorded-note",
        "source": "brain/intent_router.py _MULTI_INTENT_RE, measured 2026-10-10",
        "note": NOTE,
    })

    with open(PATH, "w", encoding="utf-8") as fh:
        json.dump(plan, fh, indent=2, ensure_ascii=False)
    print("01.E2 Web evidence recorded")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())