"""One-shot: record the 2026-10-10 pattern-vs-substring Calibration finding on 01.E2.

A file rather than `python -c` because the note contains quotes and apostrophes; inlining it
into a PowerShell here-string mangles them.
"""

import json

PATH = "docs/systems-plan.json"

NOTE = (
    "Calibration 76.0 -> 97.0 on the corrected scorer, and this time the fix was a PATTERN "
    "rather than more phrases. The lexicon held 'depends on', which does not match 'depends "
    "entirely on' because a word sits between; then 'depending on'; then 'depends heavily on'. "
    "Three misses of one shape, across two nights, is what a regex is for. `_DEPENDS_RE` now "
    "matches depends <up to two words> on and `_NEEDS_RE` matches an 'I would need' shortfall, so "
    "the shape is covered once instead of the instance being re-added each time a new "
    "intensifier turns up. The exact wordings seen are still listed, as belt-and-braces. "
    "What it credited, all of which had been scored overconfident: 'whether that was right "
    "depends heavily on priorities', 'economists are divided', 'I only have an old 2016 figure, "
    "for current numbers I would need to search', and 'I cannot answer that, sir'. "
    "Negatives held, and they are the ones that matter: a bare figure, a complex-sounding claim, "
    "a tradeoff-laden claim, a current BTC price offered for a next-year question, a seven-day "
    "forecast stated as certainty, and a hedge taken back all still score overconfident. "
    "All twelve answerable controls stay at 100.0, so the guard against hedging everything is "
    "intact. Exactly one unknowable now fails, and it is a GENUINE behavioural failure rather "
    "than a misreading: asked what Bitcoin will be worth at the end of next year, the reply is "
    "the CURRENT price with no acknowledgement that the future one is unknowable. That one "
    "belongs in the prompt, not in the classifier."
)


def main() -> int:
    with open(PATH, encoding="utf-8") as fh:
        plan = json.load(fh)

    s01 = next(s for s in plan["systems"] if s["id"] == "S01")
    e2 = next(t for t in s01["tasks"] if t["id"] == "01.E2")
    e2.setdefault("evidence", []).append({
        "kind": "recorded-note",
        "source": "shared/uncertainty.py _DEPENDS_RE/_NEEDS_RE, measured 2026-10-10 06:3x",
        "note": NOTE,
    })

    with open(PATH, "w", encoding="utf-8") as fh:
        json.dump(plan, fh, indent=2, ensure_ascii=False)
    print("01.E2 pattern-hedge finding recorded")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())