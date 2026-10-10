"""One-shot: record the 2026-10-10 Calibration finding and the 01.E2 correction in the registry.

Kept as a file rather than `python -c` because the note is long prose containing quotes, and
inlining that into a PowerShell here-string is how the quoting gets mangled.
"""

import json

PATH = "docs/systems-plan.json"

NOTE = (
    "Re-measured end to end on a healthy model chain, which lifted the overall from 74.5 to 84.4 "
    "and Calibration from 63.5 to 78.5. CORRECTION TO AN EARLIER CLAIM IN THIS FILE: it is WRONG to "
    "say 01.E2 is gated ONLY on Calibration. That holds for the >=95 overall (Calibration alone caps "
    "it at roughly 87), but the task also demands no category below 90, and four are below - Memory "
    "65.0, Fleet 68.5, Web 71.5, Calibration 78.5. "
    "Calibration then went 78.5 -> 88.0 on a REPLAY of the model's own replies, with no behaviour "
    "change at all. A per-kind breakdown showed contested failing 3 of 3, and reading the replies "
    "showed three of the five listed failures were FALSE POSITIVES: telling the owner there is no "
    "single best language, presenting both sides of the nuclear debate, and stating that the forecast "
    "tool is not set up are all admissions a person would credit. Two mechanical causes. The lexicon "
    "held 'depends on', which does not match 'depends entirely on' because a word sits between. And "
    "'still' sat in _CONTRASTIVE, so an ordinary adverb split a balanced answer and made the "
    "supporting date after it read as overconfidence. Fixed both; test_uncertainty went 34 -> 41 "
    "with the live replies pinned as positives and the negatives - a rough-eyeball estimate, a bare "
    "figure, a hedge taken back - held as negatives. One control also recovered 85 -> 100, so the old "
    "classifier was penalising a correct answer in the other direction too."
)

SHAPE_NOTE = (
    "A SHAPE GATE CANNOT SEE A DEAD CHAIN. test_finetune.py passes on the shipped .env while the "
    "system burns about 9 seconds per turn: it asserts the primary is minimax, that the chain has at "
    "least three entries across at least two providers, that a free/groq tier sits between the primary "
    "and the gateway, and that vercel entries are the contiguous tail. Every one of those is true of "
    "a chain in which six of eight entries cannot answer - minimax 401s, three groq ids 404 because "
    "those models do not exist, gemini and mistral are unreachable. The invariants describe the SHAPE "
    "of the chain and are silent on whether anything in it responds. Recorded so nobody concludes that "
    "a green test_finetune means a fast system."
)


def main() -> int:
    with open(PATH, encoding="utf-8") as fh:
        plan = json.load(fh)

    s01 = next(s for s in plan["systems"] if s["id"] == "S01")
    e2 = next(t for t in s01["tasks"] if t["id"] == "01.E2")
    e2.setdefault("evidence", []).append({
        "kind": "recorded-note",
        "source": "bench/behavioral_suite.py healthy-chain run 2026-10-10, shared/uncertainty.py",
        "note": NOTE,
    })

    s45 = next(s for s in plan["systems"] if s["id"] == "S45")
    r10 = next(t for t in s45["tasks"] if t["id"] == "45.R10")
    r10.setdefault("evidence", []).append({
        "kind": "recorded-note",
        "source": "bench/test_finetune.py, 2026-10-10",
        "note": SHAPE_NOTE,
    })

    with open(PATH, "w", encoding="utf-8") as fh:
        json.dump(plan, fh, indent=2, ensure_ascii=False)
    print("01.E2 and 45.R10 evidence updated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())