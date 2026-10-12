"""Turn assembly — the local-STT turn decision.

The claim under test is the one the live pipeline cannot easily make: that text
plus quiet is a better end-of-turn signal than a fixed silence timer, without
any input being able to hang the assistant.

    uv run python bench/test_turn_assembly.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from mushegh.edge.turn_assembly import (  # noqa: E402
    TurnAssembler,
    hold_ms_for,
    looks_complete,
    normalise,
)

passed = failed = 0


def check(name: str, ok: bool, detail: str = "") -> None:
    global passed, failed
    if ok:
        passed += 1
        print(f"  [PASS] {name}")
    else:
        failed += 1
        print(f"  [FAIL] {name}  {detail}")


def a(base: int = 350, long: int = 900, ceiling: int = 2_500) -> TurnAssembler:
    return TurnAssembler(base_hold_ms=base, long_hold_ms=long, max_wait_ms=ceiling)


def main() -> None:
    print("[1] a finished sentence reads as finished")
    check("terminal period", looks_complete("remind me about the invoice."))
    check("terminal question", looks_complete("what did Anna say?"))
    check("terminal ellipsis", looks_complete("I meant the one about..."))
    check("closing quote after punctuation", looks_complete("he said 'done.'"))
    check("a bare noun phrase counts", looks_complete("the quarterly report"))
    check("nothing at all is not finished", not looks_complete(""))
    check("whitespace is not a sentence", not looks_complete("   "))

    print("[2] an open-ended fragment reads as unfinished")
    for t in (
        "remind me about the thing I mentioned to",
        "the one because it was",
        "can you look at",
        "I said and then",
    ):
        check(f"open: {t!r}", not looks_complete(t), t)
    check("terminal punctuation beats the word list",
          looks_complete("it failed because of the delay."), "trailing 'delay' is fine")
    check("a bare auxiliary is open, not finished", not looks_complete("the one because it was"))
    check("'let's' is not a continuation", looks_complete("let's go"))
    check("'don't' is not a continuation", looks_complete("don't stop"))
    check("'we'll' is not a continuation", looks_complete("we'll see"))

    print("[3] whitespace normalisation is idempotent")
    check("collapses runs", normalise("  a   b \n c ") == "a b c")
    check("preserves case and punctuation", normalise(" Do  that, now. ") == "Do  that, now.".replace("  ", " "))
    check("None is survivable", normalise(None) == "")  # type: ignore[arg-type]

    print("[4] the hold is short for a finished sentence and long for an open one")
    check("complete -> short hold", hold_ms_for("do the thing.", base_ms=350, long_ms=900) == 350)
    check("open -> long hold", hold_ms_for("do the thing and", base_ms=350, long_ms=900) == 900)
    check("empty -> long hold (nothing is finished)", hold_ms_for("", base_ms=350, long_ms=900) == 900)

    print("[5] a turn fires only after text AND quiet")
    t = a()
    check("nothing pending is not due", not t.due(now_ms=0))
    t.push_fragment("remind me about the invoice.", now_ms=0)
    check("speech still going is not due", not t.due(now_ms=100))
    t.note_silence(now_ms=100)
    check("too soon after silence", not t.due(now_ms=100))
    check("due once the short hold elapses", t.due(now_ms=100 + 350))

    print("[6] an open-ended fragment waits longer than a finished one")
    done, open_ = a(), a()
    done.push_fragment("what time is it.", now_ms=0)
    open_.push_fragment("what time is it because", now_ms=0)
    done.note_silence(now_ms=100)
    open_.note_silence(now_ms=100)
    check("finished fires at the short hold", done.due(now_ms=450))
    check("open has NOT fired at the short hold", not open_.due(now_ms=450))
    check("open fires at the long hold", open_.due(now_ms=1_000))

    print("[7] the ceiling is honoured even on text that never looks finished")
    t = a()
    t.push_fragment("and", now_ms=0)
    t.note_silence(now_ms=0)
    check("not due immediately", not t.due(now_ms=0))
    check("due at the ceiling regardless", t.due(now_ms=2_500))
    check("and it stays due", t.due(now_ms=60_000))

    print("[8] silence before any speech does not pre-satisfy the hold")
    t = a()
    t.note_silence(now_ms=0)          # a quiet room before the owner speaks
    t.push_fragment("hello", now_ms=5_000)
    check("not due the instant speech stops", not t.due(now_ms=5_000))
    t.note_silence(now_ms=5_000)
    check("due after the hold from THAT silence", t.due(now_ms=5_350))

    print("[9] fragments accumulate into one turn, not several")
    t = a()
    t.push_fragment("remind me about", now_ms=0)
    t.push_fragment("the thing I told", now_ms=200)
    t.push_fragment("Anna last week", now_ms=400)
    check("pending is the joined transcript",
          t.pending == "remind me about the thing I told Anna last week", t.pending)
    check("one take empties the turn", t.take() == "remind me about the thing I told Anna last week")
    check("take on an empty turn returns empty", t.take() == "")
    check("nothing is due after take", not t.due(now_ms=999))

    print("[10] new speech re-arms a turn that was waiting")
    t = a()
    t.push_fragment("do you think I should", now_ms=0)
    t.note_silence(now_ms=100)
    check("waiting on the long hold", not t.due(now_ms=300))
    t.push_fragment("call her or not", now_ms=400)   # owner carried on
    check("silence cleared by the new fragment", not t.due(now_ms=400))
    t.note_silence(now_ms=400)                       # and then went quiet again
    check("now it reads complete", t.pending.endswith("or not"))
    check("and it fires on the short hold", t.due(now_ms=750))

    print("[11] blank fragments are not speech")
    t = a()
    t.push_fragment("   ", now_ms=0)
    check("whitespace is not pending", not t.due(now_ms=9_999))
    check("and pending stays empty", t.pending == "")
    t.push_fragment("real speech", now_ms=10)
    check("a real fragment still works", t.pending == "real speech")

    print("[12] reset drops the turn without leaving residue")
    t = a()
    t.push_fragment("half a thought", now_ms=0)
    t.note_silence(now_ms=10)
    t.reset()
    check("pending cleared", t.pending == "")
    check("not due", not t.due(now_ms=5_000))
    t.push_fragment("a new one", now_ms=6_000)
    t.note_silence(now_ms=6_000)
    check("a fresh turn does not inherit the old ceiling", t.due(now_ms=6_350))

    print("[13] misconfiguration is refused at construction, not at runtime")
    for kwargs in (
        {"base_hold_ms": -1},
        {"base_hold_ms": 900, "long_hold_ms": 350},
        {"base_hold_ms": 100, "long_hold_ms": 900, "max_wait_ms": 500},
    ):
        try:
            TurnAssembler(**kwargs)  # type: ignore[arg-type]
            check(f"refused {kwargs}", False, "constructed without raising")
        except ValueError:
            check(f"refused {kwargs}", True)

    print(f"\n=== checks passed ===\n{passed} passed, {failed} failed")
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()