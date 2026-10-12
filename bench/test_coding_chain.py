"""The owner's coding pipeline: Claude Code, then mcode, then Mistral Vibe — and nothing else.

His direction, 2026-10-11: *"Claude Code as the main coding development tool, Mcode from minimax
as the 1st fallback and mistral-vibe as the 2nd fallback ... all of the code work has to be routed
down this pipeline"*, with frontend work going to Open Design instead.

That is three separate claims, and each one can be broken by a change that looks harmless:

1. **Order.** The chain is a declared constant, not the order rows happen to sit in the table.
2. **Exclusivity.** A coding executor that is not in the chain is not a candidate — and because
   that can make a correctly-added executor vanish, the drop is logged rather than silent.
3. **Fallback means on failure.** Each CLI is tried only when the one before it failed, judged by
   ``Result.ok`` (exit code plus the parser's verdict), never by prose. A *timeout* is the one
   failure that does NOT fall back: the first executor may still be writing in that worktree.
4. **Frontend never enters.** A coding CLI will happily rewrite a landing page, which is the whole
   reason the split exists, so a frontend brief is refused with the Open Design route named.

Hermetic: the executors are replaced with small Python processes. No CLI is invoked, no model is
called, nothing is spent.

    uv run python bench/test_coding_chain.py
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from mushegh.brain import executors as X  # noqa: E402
from mushegh.brain.executors import Brief, BriefRefused, Domain, ExecutorSpec, Tier  # noqa: E402

passed = failed = 0


def check(name: str, ok: bool, detail: str = "") -> None:
    global passed, failed
    if ok:
        passed += 1
        print(f"  [PASS] {name}")
    else:
        failed += 1
        print(f"  [FAIL] {name}  <- {detail}")


def _fake(name: str, code: int, says: str = "done") -> ExecutorSpec:
    """A coding executor that prints and exits with the code we ask for."""
    return ExecutorSpec(
        name=name, domains=(Domain.CODING,), tiers=(Tier.CORPORATE,),
        argv=(sys.executable, "-c",
              f"import sys; print({says!r}); sys.exit({code})"),
    )


def _brief(task: str = "fix the off-by-one in paging") -> Brief:
    return Brief(domain=Domain.CODING, task=task, acceptance="the paging test passes",
                 tier=Tier.CORPORATE, repo=os.getcwd())


async def main() -> int:
    print("\n[1] the declared pipeline is the owner's, in his order")
    check("Claude Code is the main tool", X.CODING_CHAIN[0] == "claude-code", str(X.CODING_CHAIN))
    check("mcode is the first fallback", X.CODING_CHAIN[1] == "mcode", str(X.CODING_CHAIN))
    check("Mistral Vibe is the second", X.CODING_CHAIN[2] == "vibe", str(X.CODING_CHAIN))
    check("...and there is no fourth", len(X.CODING_CHAIN) == 3, str(X.CODING_CHAIN))
    coding = [s for s in X.SPECS if Domain.CODING in s.domains]
    check("every name in the chain is a real row in the table",
          set(X.CODING_CHAIN) == {s.name for s in coding},
          str(sorted(s.name for s in coding)))
    check("each one is non-interactive, so there is nothing to type into",
          all(any(f in s.argv for f in ("-p", "exec")) for s in coding),
          str([s.argv[:2] for s in coding]))
    check("each one's output has a parser, so a failure cannot read as prose",
          all(s.parser in X.PARSERS for s in coding),
          str([(s.name, s.parser) for s in coding]))
    check("no coding executor is handed another's credential",
          len({k for s in coding for k in s.env_allow})
          == len([k for s in coding for k in s.env_allow]),
          str([(s.name, s.env_allow) for s in coding]))

    original, original_chain = X.SPECS, X.CODING_CHAIN
    try:
        print("\n[2] fallback happens on FAILURE, in order, and stops at the first success")
        X.SPECS = (_fake("first", 1, "first blew up"), _fake("second", 0, "second did it"),
                   _fake("third", 0, "third never ran"))
        X.CODING_CHAIN = ("first", "second", "third")
        final, attempts = await X.dispatch_chain(_brief())
        check("the answer is the one that worked", final.ok and final.executor == "second",
              f"{final.executor} ok={final.ok}")
        check("...and the chain stopped there rather than running the rest",
              [a.executor for a in attempts] == ["first", "second"],
              str([a.executor for a in attempts]))
        check("the failure is not hidden — every attempt comes back",
              attempts[0].exit_code == 1 and not attempts[0].ok)
        check("...with its output kept for the owner to read",
              "first blew up" in attempts[0].transcript, attempts[0].transcript[:60])

        print("\n[3] when all three fail, the last result is returned, not an exception")
        X.SPECS = (_fake("first", 1), _fake("second", 2), _fake("third", 3))
        final, attempts = await X.dispatch_chain(_brief())
        check("all three were tried", [a.executor for a in attempts] == ["first", "second", "third"],
              str([a.executor for a in attempts]))
        check("the final result is a failure, and says so", not final.ok and bool(final.error),
              f"ok={final.ok} error={final.error!r}")
        check("...and it is the LAST one's, so the owner hears about where it ended",
              final.executor == "third" and final.exit_code == 3, final.executor)

        print("\n[4] a TIMEOUT does not fall back — the first executor may still be writing")
        slow = ExecutorSpec(name="first", domains=(Domain.CODING,), tiers=(Tier.CORPORATE,),
                            argv=(sys.executable, "-c", "import time; time.sleep(30)"))
        X.SPECS = (slow, _fake("second", 0, "second did it"))
        X.CODING_CHAIN = ("first", "second")
        b = Brief(domain=Domain.CODING, task="refactor the paging helper",
                  acceptance="the paging test passes", tier=Tier.CORPORATE, repo=os.getcwd(),
                  timeout_s=5)
        final, attempts = await X.dispatch_chain(b)
        check("the deadline is reported as a failure", not final.ok and "deadline" in final.error,
              final.error[:80])
        check("THE GUARD: the next executor was NOT tried in the same worktree",
              [a.executor for a in attempts] == ["first"], str([a.executor for a in attempts]))

        print("\n[5] exclusivity — a coding executor outside the chain is not a candidate")
        X.SPECS = (_fake("claude-code", 0), _fake("rogue", 0))
        X.CODING_CHAIN = ("claude-code",)
        cands = [s.name for s in X.candidates(_brief(), require_available=False)]
        check("the unlisted one is dropped", cands == ["claude-code"], str(cands))
        src = Path(X.__file__).read_text(encoding="utf-8")
        check("...and the drop is LOGGED, so an added executor cannot vanish in silence",
              "not in CODING_CHAIN" in src)

        print("\n[6] a REFUSAL never falls back — the next executor cannot fix a bad brief")
        X.SPECS, X.CODING_CHAIN = original, original_chain
        try:
            await X.dispatch_chain(Brief(domain=Domain.FRONTEND, task="rebuild the landing page",
                                         acceptance="it matches the mock"))
        except BriefRefused as e:
            check("a frontend brief is refused rather than dispatched", "Open Design" in str(e),
                  str(e)[:100])
        else:
            check("a frontend brief is refused", False, "it was dispatched to a coding CLI")
        no_repo = Brief(domain=Domain.CODING, task="change something", acceptance="suite green",
                        tier=Tier.CORPORATE)
        try:
            await X.dispatch_chain(no_repo)
        except BriefRefused as e:
            check("a coding brief with no repo is refused before any process starts",
                  "repo" in str(e), str(e)[:80])
        else:
            check("a coding brief with no repo is refused", False, "it was dispatched")
    finally:
        X.SPECS, X.CODING_CHAIN = original, original_chain

    print("\n[7] the vibe parser, against the shape a real run produced")
    # Measured on this host from `vibe -p ... --output json`: ONE array, three entries, the answer
    # on the assistant message. Not JSONL like the other two, which is why it has its own parser.
    real_shape = json.dumps([
        {"type": "message", "role": "user", "generationStatus": "completed",
         "content": [{"type": "text", "text": "Reply with exactly: VIBE OK"}]},
        {"type": "reasoning", "generationStatus": "completed"},
        {"type": "message", "role": "assistant", "generationStatus": "completed",
         "content": [{"type": "text", "text": "VIBE OK"}]},
    ])
    transcript, error = X.parse_vibe_json(real_shape)
    check("the assistant's answer is the transcript", transcript == "VIBE OK", repr(transcript))
    check("...and the prompt echo is not in it", "Reply with exactly" not in transcript)
    check("a completed run reports no error", error == "", error)
    stopped = json.dumps([{"type": "message", "role": "assistant",
                           "generationStatus": "interrupted",
                           "content": [{"type": "text", "text": "half a"}]}])
    _, error2 = X.parse_vibe_json(stopped)
    check("a run that stopped early is an ERROR, not a short answer",
          "stopped early" in error2, error2)
    check("output that is not the documented shape is kept, not lost",
          X.parse_vibe_json("plain prose from a future version")[0]
          == "plain prose from a future version")
    check("empty output is empty, not a crash", X.parse_vibe_json("") == ("", ""))

    print(f"\n=== {passed + failed} checks: {passed} passed, {failed} failed ===")
    if not failed:
        print("ALL CHECKS PASSED ===")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
