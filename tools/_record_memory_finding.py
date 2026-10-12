"""One-shot: record the 2026-10-10 Memory + define_word findings in the S01 registry.

A file rather than `python -c` because the note contains quotes; inlining it into a PowerShell
here-string mangles them. Same reason `tools/_record_calibration_finding.py` exists.
"""

import json

PATH = "docs/systems-plan.json"

NOTE = (
    "Memory 65.0 diagnosed from the healthy-chain run, and the safety net turned out to be working. "
    "The owner asks Mushegh to remember that his dentist is called Dr Petrov and the model did not call "
    "remember; what he heard instead was _FABRICATION_DEGRADE, the B3 anti-fabrication hard stop, "
    "which is CORRECT behaviour. The router does force remember (verified directly) and remember is "
    "not confirm-gated, so the model simply dodged the call through the whole escalation ladder. That "
    "part is a model-capability limit, not a routing bug, and it is recorded rather than papered over. "
    "The routing half WAS a bug and is fixed: a CORRECTION to something already stored routed to "
    "NOTHING - 'actually it is Petrova, can you fix that one', 'change that to Petrova', 'update the "
    "dentist one to Petrova' - which is what held memory_update at 48.0. Those now route to remember, "
    "which is correct because 30.R10 supersession already makes a corrected fact replace its "
    "predecessor; no new update tool is needed. Placement mattered more than the pattern: the first "
    "attempt sat beside the other memory routes and hijacked a request to change an email's subject "
    "line into a memory write. It now sits AFTER the email, calendar, telegram, tasks and recall "
    "routes, and the back-reference is excluded when a noun follows. Verified against twelve cases "
    "including four negatives. "
    "Separately, define_word was found completely broken: api.dictionaryapi.dev returns 403 for every "
    "word from this host, http_get raises on a non-2xx, so the graceful branch was unreachable and the "
    "owner heard a raw HTTPStatusError. It now degrades and hands the answer back to the model."
)


def main() -> int:
    with open(PATH, encoding="utf-8") as fh:
        plan = json.load(fh)

    s01 = next(s for s in plan["systems"] if s["id"] == "S01")
    e2 = next(t for t in s01["tasks"] if t["id"] == "01.E2")
    e2.setdefault("evidence", []).append({
        "kind": "recorded-note",
        "source": "bench/behavioral_suite.py healthy run 2026-10-10, "
                  "shared/uncertainty.py, brain/intent_router.py, brain/tools/utility.py",
        "note": NOTE,
    })

    with open(PATH, "w", encoding="utf-8") as fh:
        json.dump(plan, fh, indent=2, ensure_ascii=False)
    print("01.E2 Memory + define_word evidence recorded")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())