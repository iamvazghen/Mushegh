"""Is the calibration rule present-but-ignored, or simply not salient enough?

Established already: the rule IS in the prompt (`personality/afon.md:53`,
`operating-rules.md:39-40`, both verified in the assembled system prompt), and the model
still answers unknowables flatly about two turns in three. So "add an instruction" is
ruled out.

What has NOT been tested is whether *repetition at the end* helps. Models attend more to
the closing lines of a prompt than to a rule buried mid-document, and the operating rules
are a file the persona builder folds into a long prompt. That is a cheap, contract-neutral
experiment: no new verdict, no change to the one bounded call, just the same instruction
restated last.

This runs the eleven real `unknowable_*` prompts through the live agent twice — once as
shipped, once with the rule restated — and counts how many come back calibrated, using the
same `uncertainty.calibration` the scorecard uses.

Usage:
    python tools/probe_prompt_salience.py [N-per-condition]
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for extra in (str(ROOT), str(ROOT / "bench"), str(ROOT / "src")):
    if extra not in sys.path:
        sys.path.insert(0, extra)

from afon.brain import agent as A  # noqa: E402
from afon.shared.uncertainty import calibration  # noqa: E402

RESTATED = (
    "\n\nBefore you answer, check one thing: is this knowable at all? The future, "
    "counterfactuals, and any figure you have no source for are not. If it is not, say "
    "so in one line and offer to look it up. Do not answer it as fact."
)


def prompts() -> list[str]:
    import behavioral_suite as bs

    return [s.turns[0].say for s in bs.scenarios() if s.id.startswith("unknowable_")]


async def run_condition(label: str, restate: bool) -> tuple[int, int, list[str]]:
    original = A.build_system_prompt
    if restate:
        def patched() -> str:  # noqa: ANN202
            return original() + RESTATED
        A.build_system_prompt = patched  # type: ignore[assignment]
    else:
        A.build_system_prompt = original  # type: ignore[assignment]

    ok = 0
    detail: list[str] = []
    try:
        for text in prompts():
            agent = A.AfonAgent()
            agent._self_improve = False
            reply = await agent.respond(text)
            verdict = calibration(reply, unknowable=True)
            ok += verdict == "correct"
            detail.append(f"{verdict:>14}  {text[:52]}")
    finally:
        A.build_system_prompt = original  # type: ignore[assignment]
        import behavioral_suite as bs
        await bs._cleanup()

    print(f"\n{label}: {ok}/{len(detail)} calibrated")
    for line in detail:
        print(f"   {line}")
    return ok, len(detail), detail


async def main() -> int:
    print("Prompt salience A/B on the eleven unknowable prompts")
    print("Both conditions use the live agent and the same scorer the scorecard uses.")
    base_ok, total, _ = await run_condition("as shipped", restate=False)
    restated_ok, _, _ = await run_condition("rule restated last", restate=True)
    print(f"\n  as shipped     : {base_ok}/{total}")
    print(f"  restated last  : {restated_ok}/{total}")
    if restated_ok == base_ok:
        print("\n  No difference. Restatement is not the lever, which leaves the")
        print("  architectural option (a fifth verdict from the bounded call) as the")
        print("  only remaining one - and that is an owner's decision, not a prompt edit.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))