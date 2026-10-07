"""02.E1 — a full outage is audible, and it is described accurately.

A full outage of the primary and the first fallback was journalled — `llm.py` records
`agentic/llm_chain_exhausted` with every model's error attached, and the comment beside it names
what the owner experiences: "Afon going mute or apologising" — and never said. Meanwhile the server
answered EVERY failure with one sentence, "I'm having trouble reaching my reasoning right now", which
is a claim about the models, and which the owner also heard when a `KeyError` in a tool took the turn
down. Two consequences, the second serious:

  * he was told to "give me a moment" for a bug a moment will never fix, and
  * he was sent to the model chain when the fault was in Afon's own code.

So what is asserted here is that the sentence is CHOSEN FROM THE CAUSE:

  * the chain exhausted → it says the models are down, and that nothing is lost
  * one model timed out → it says that, and not that the chain is gone
  * **anything else → it says it is Afon's own fault and NOT the network.** This is the one that
    matters: an assistant that cannot tell its own bug from an outage sends the person trying to fix
    it in the wrong direction, and a wrong direction at 3am costs hours.
  * an UNKNOWN exception classifies as internal, deliberately — a failure nobody recognised is far
    more likely to be a bug in Afon than an unrecognised outage, and "I broke" is the sentence that
    points at the right log.
  * the classifier is total and never raises, because a classifier that breaks must not cost the
    sentence that is supposed to explain the breakage
  * the server's turn handler actually calls it — the sentence existing and being unused is exactly
    the defect 45.R2 was found in, so the wiring is asserted too

Hermetic: constructed exceptions only, plus a source-level check of the one call site. No model, no
settings, no network.

    uv run python bench/test_outage_audible.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(ROOT / "src"))

passed = failed = 0


def check(name: str, ok: bool, detail: str = "") -> None:
    global passed, failed
    if ok:
        passed += 1
        print(f"  [PASS] {name}")
    else:
        failed += 1
        print(f"  [FAIL] {name}  {detail}")


def main() -> int:
    from afon.brain.llm import ChainExhausted
    from afon.brain.outage import INTERNAL, MODEL_QUIET, MODELS_DOWN, classify, spoken_for

    print("\n[1] the three failures are told apart")
    check("an exhausted chain is MODELS_DOWN", classify(ChainExhausted("all LLM models failed"))
          == MODELS_DOWN)
    check("a timeout that did not exhaust the chain is MODEL_QUIET",
          classify(asyncio.TimeoutError()) == MODEL_QUIET
          and classify(TimeoutError()) == MODEL_QUIET)
    for exc, what in ((KeyError("tool"), "a KeyError in a tool"),
                      (TypeError("bad arg"), "a TypeError"),
                      (ValueError("bad value"), "a ValueError"),
                      (RuntimeError("forced tool_choice rejected"), "a runtime failure"),
                      (Exception("?"), "an unknown exception")):
        check(f"{what} is INTERNAL, not blamed on the models", classify(exc) == INTERNAL,
              f"got {classify(exc)}")

    print("\n[2] a bug in Afon is never reported as an outage")
    bug = spoken_for(KeyError("turn_tools"))
    check("the sentence says it is Afon's own fault", "my own fault" in bug, bug)
    check("...and explicitly NOT the network", "not the network" in bug, bug)
    check("...and does not mention models or reasoning at all",
          "model" not in bug.casefold() and "reasoning" not in bug.casefold(), bug)
    check("...and it tells the owner it was written down, so he knows where to look",
          "written down" in bug, bug)
    for exc in (TypeError("x"), ValueError("y"), Exception("z"), RuntimeError("w")):
        check(f"no exception leaks the old blanket wording: {type(exc).__name__}",
              "trouble reaching my reasoning" not in spoken_for(exc).casefold(), spoken_for(exc))

    print("\n[3] an outage says so, and reassures that nothing is lost")
    down = spoken_for(ChainExhausted("all LLM models failed"))
    check("it names the chain being down", "chain is down" in down, down)
    check("...and says every model refused, so it is not one bad provider",
          "every model" in down, down)
    check("...and that the work will be there", "nothing is lost" in down.casefold(), down)
    check("...and gives a moment when to retry", "in a minute" in down, down)
    check("it does not claim Afon is at fault, because he is not",
          "my own fault" not in down, down)

    print("\n[4] one model going quiet is not a full outage")
    quiet = spoken_for(asyncio.TimeoutError())
    check("it says the model went quiet, not that the chain is gone",
          "went quiet" in quiet and "chain is down" not in quiet, quiet)
    check("...and it is logged, so the owner is not left guessing",
          "logged" in quiet, quiet)

    print("\n[5] the classifier is total and never costs the sentence")
    class Exploding(BaseException):
        pass

    check("a BaseException is still classified, not raised", classify(Exploding()) == INTERNAL)
    for exc in (KeyboardInterrupt(), SystemExit(), MemoryError()):
        check(f"{type(exc).__name__} gets a sentence rather than propagating",
              isinstance(spoken_for(exc), str) and spoken_for(exc), "no sentence")
    check("the sentence is never empty for any exception",
          all(spoken_for(e) for e in (ChainExhausted("x"), TimeoutError(), KeyError("k"), Exception())),
          "an empty sentence is silence, which is the defect")

    print("\n[6] the server actually uses it — an unused sentence is the defect 45.R2 was")
    src = (ROOT / "src" / "afon" / "brain" / "server.py").read_text(encoding="utf-8")
    check("the turn handler calls outage.spoken_for", "outage.spoken_for(e)" in src)
    # Assert the old sentence is gone from EXECUTABLE code, not from the file: the explanation
    # written beside the fix quotes it, and a grep for the text would therefore always match. A
    # first draft of this check did exactly that and failed on its own comment. Parsing and looking
    # for the literal in the AST ignores comments, which is what the claim is actually about.
    import ast

    literals = [n.value for n in ast.walk(ast.parse(src))
                if isinstance(n, ast.Constant) and isinstance(n.value, str)]
    check("...and the old one-size-fits-all sentence is gone from the CODE (comments may quote it)",
          not any("trouble reaching my reasoning" in v for v in literals),
          "the blanket apology is still executable somewhere")
    check("...and there is a fallback if even the classifier is unavailable",
          "Something went wrong on my side" in src)
    check("the handler still never 500s the phone", "always speak something" in src)
    check("...and still logs the real exception before speaking",
          "log turn failed" in src or "/talk turn failed" in src)

    print("\n[7] the outage was already journalled; this only makes it audible")
    llm_src = (ROOT / "src" / "afon" / "brain" / "llm.py").read_text(encoding="utf-8")
    check("llm.py already records the exhausted chain as its own operation",
          "llm_chain_exhausted" in llm_src)
    check("...with every model's error attached, not just the last",
          "context=" in llm_src and "errors" in llm_src)
    check("...so the count of outages was always available; only the sentence was missing",
          "record_op" in llm_src)

    print(f"\n{'=' * 60}")
    print(f"  {passed} passed, {failed} failed")
    print("=" * 60)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
