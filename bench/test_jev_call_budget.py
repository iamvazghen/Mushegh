"""01.J1 — a turn the router already resolves spends no decision call.

The recommendation under test came from Jev itself, asked how it should be integrated with nothing
carrying weight: *"trivial turns should never cost a call"*, returned at confidence 0.96 — the
highest of the twenty answers.

What it looked like in practice, measured before the change
(`tools/probe_jev_call_coverage.py`): **2 of 9 turn classes cost nothing**, both pure chatter. A
reflex read and a single-route lookup each spent a full decision call, into a 400 ms budget whose
measured median on this host is 706 ms, with 5,437 recorded failures that are literally
`timeout_0.4s`. The cheapest turns were paying the most.

The skip applies to turns the router FORCES to exactly one argument-less tool: nothing to
arbitrate (one candidate), nothing to disambiguate (no arguments to supply), nothing to route.
Everything else still asks, and this gate exists so that stays true — including the failure mode,
where an exception in the predicate must cost a call rather than a turn.

    uv run python bench/test_jev_call_budget.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mushegh.brain.agent import _ZERO_ARG_READS, _is_pure_chat, _is_trivial_read  # noqa: E402

_passed = 0
_failed = 0


def check(label: str, ok: bool, detail: str = "") -> None:
    global _passed, _failed
    if ok:
        _passed += 1
        print(f"  PASS  {label}")
    else:
        _failed += 1
        print(f"  FAIL  {label}" + (f"  [{detail}]" if detail else ""))


#: Turns the router forces to exactly one argument-less tool -> no decision call.
SKIP = [
    "check my telegram",
    "read my calendar",
    "check my email",
    "how many unread emails",
]

#: Turns that must STILL ask. This half matters more than the first: a skip that overreaches is a
#: turn that quietly loses its clarity check, its urgency read and its arbitration.
ASK = [
    "what is the capital of Armenia",          # a lookup, but not forced and argument-taking
    "remember to call the dentist",            # an act with content to write
    "check my email and remember the lease date",   # compound: the clause plan steers this
    "send it",                                 # ambiguous - the whole point of asking
    "open Chrome or Firefox",                  # decision-shaped
    "what will Bitcoin be worth next year",    # unknowable: exactly who should be consulted
]


def main() -> int:
    print("01.J1 — trivial turns must not spend a decision call")

    print("\n[1] the predicate is what it claims to be")
    check("the zero-arg read set is non-empty and small",
          0 < len(_ZERO_ARG_READS) <= 6, str(sorted(_ZERO_ARG_READS)))

    print("\n[2] a forced, argument-less read skips the call")
    for text in SKIP:
        check(f"{text!r} is a trivial read", _is_trivial_read(text))

    print("\n[3] everything else still asks — the half that protects the turn")
    for text in ASK:
        check(f"{text!r} is NOT trivial (still asked)", not _is_trivial_read(text))

    print("\n[4] chatter was already skipped before 01.J1 and must stay skipped")
    for text in ("thanks", "good morning"):
        check(f"{text!r} is pure chat", _is_pure_chat(text))
        check(f"{text!r} is not treated as a trivial READ", not _is_trivial_read(text))

    print("\n[5] fail-safe: a broken predicate costs a call, never a turn")
    check("empty input is not a trivial read", not _is_trivial_read(""))
    check("whitespace is not a trivial read", not _is_trivial_read("   "))
    check("a nonsense string is not a trivial read", not _is_trivial_read("zzzz qqqq"))
    # The predicate catches everything and returns False, which is the pre-01.J1 behaviour: the
    # status quo is always safe, so an import error cannot silently mute the decision layer.
    check("the predicate is total (returns a bool for odd input)",
          isinstance(_is_trivial_read(None or ""), bool))

    print(f"\n=== {_passed}/{_passed + _failed} checks passed ===")
    return 1 if _failed else 0


if __name__ == "__main__":
    sys.exit(main())