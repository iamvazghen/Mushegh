"""One-shot: record the 2026-10-10 provider-availability finding on 01.E2.

A file rather than `python -c` because the note contains quotes and braces; inlining it into a
PowerShell here-string mangles them.
"""

import json

PATH = "docs/systems-plan.json"

NOTE = (
    "MEASUREMENT CONTAMINATION, recorded because it invalidates numbers measured earlier the "
    "same morning. Probing each chain entry individually at 08:0x on 2026-10-10: minimax "
    "MiniMax-Text-01 WORKS. groq llama-3.3-70b-versatile and llama-3.1-8b-instant return 404 "
    "(those model ids do not exist), gemini-3.5-flash and mistral-small-latest are "
    "unreachable, groq/compound is unreachable, and BOTH vercel entries return 402 with 'A "
    "positive credit balance is required for all requests'. "
    "So the only provider currently serving ANY request is MiniMax - which is the shipped "
    "primary, and which test_finetune.py requires the primary to be. A third full behavioural "
    "run finished at 59.1 against 82.2 and 77.8 for the two before it, and the reason is in "
    "the log: the vercel gateway ran out of credit mid-run and its cooldowns escalated 120s to "
    "960s, so the tail of the suite had nothing to answer with. That is not a quality "
    "regression, and treating it as one would be the wrong lesson. "
    "CONSEQUENCE FOR THE EARLIER A/B: the 'put vercel first' advice recorded earlier in this "
    "file is not merely a violation of the test_finetune invariants, it is operationally "
    "wrong. Following it would have left a chain whose only reachable provider is out of "
    "credit, while the paid MiniMax primary that already works was pushed behind a dead one. "
    "The correct statement is narrower than the one made earlier: the dead entries are real and "
    "they cost latency, but the fix is to REPAIR or REMOVE them, never to promote the gateway "
    "above a working primary. "
    "It also means the behavioural numbers from 2026-10-09/10 are not comparable to each other - "
    "the provider set changed underneath them - and none of them should be quoted as a baseline "
    "until a chain with at least two reachable providers is measured."
)


def main() -> int:
    with open(PATH, encoding="utf-8") as fh:
        plan = json.load(fh)

    s01 = next(s for s in plan["systems"] if s["id"] == "S01")
    e2 = next(t for t in s01["tasks"] if t["id"] == "01.E2")
    e2.setdefault("evidence", []).append({
        "kind": "recorded-note",
        "source": "direct per-provider probe 2026-10-10 08:0x CEST + bench/behavioral_suite.py run 3",
        "note": NOTE,
    })

    with open(PATH, "w", encoding="utf-8") as fh:
        json.dump(plan, fh, indent=2, ensure_ascii=False)
    print("01.E2 provider-availability finding recorded")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())