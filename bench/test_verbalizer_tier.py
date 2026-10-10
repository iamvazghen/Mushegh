"""Test the D-92 dedicated verbalizer tier.

Three properties, and the first is the one that matters most:

1. **Off by default.** With `verbalizer_models` blank, the verbalizer walks the
   normal chain exactly as before. No existing behaviour changes.
2. **On, it narrows one call.** The dedicated entries are preferred, in order,
   and the primary is not silently substituted.
3. **Unknown or empty does not fall back to the primary.** A caller that asked
   for a narrow tier must not get the full chain back.

Run:  uv run python bench/test_verbalizer_tier.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from afon.brain.llm import LLMClient  # noqa: E402

PASSED: list[str] = []
FAILED: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    (PASSED if ok else FAILED).append(label)
    print(f"  {'PASS' if ok else 'FAIL'}  {label}" + (f"  [{detail}]" if detail else ""))


async def _checks() -> int:
    client = LLMClient()
    base = list(client.chain)
    print(f"chain: {base}\n")

    print("=== 1. default: the chain is untouched ===")
    check("no `only` returns the full chain", client._candidate_chain() == base, str(base))
    check("no `only` twice is stable", client._candidate_chain() == client._candidate_chain())

    print("\n=== 2. a narrow tier wins, in the order given ===")
    narrow = ["cheap-a", "cheap-b"]
    got = client._candidate_chain(only=narrow)
    check("only= returns exactly the requested entries", got == narrow, str(got))

    print("\n=== 3. caller order is preserved, not chain order ===")
    # 'cheap-b' appears before 'cheap-a' in the caller's list.
    got_rev = client._candidate_chain(only=["cheap-b", "cheap-a"])
    check("caller order wins over chain order", got_rev == ["cheap-b", "cheap-a"], str(got_rev))

    print("\n=== 4. an explicit entry is used as given; a BLANK tier never widens ===")
    # An entry the caller named explicitly is attempted even when it is not in
    # the turn's chain - the same contract prepend_model already has, and the
    # only one that makes a separately-configured local model usable.
    unknown = client._candidate_chain(only=["not-in-the-chain"])
    check("an explicitly named entry is used as given", unknown == ["not-in-the-chain"],
          str(unknown))
    # The safety property: narrowing must never silently hand back the full chain.
    check("empty only= yields an empty chain, not the primary",
          client._candidate_chain(only=[]) == [], "never widens")
    check("blank-only entries yield an empty chain",
          client._candidate_chain(only=["", "  "]) == [], "never widens")

    print("\n=== 5. blanks are dropped, not treated as models ===")
    blanked = client._candidate_chain(only=["  ", "cheap-a", ""])
    check("blank entries are dropped", blanked == ["cheap-a"], str(blanked))

    print("\n=== 6. complete() accepts the new keyword ===")
    import inspect
    signature = inspect.signature(LLMClient.complete)
    check("complete() has an `only` parameter", "only" in signature.parameters,
          str(list(signature.parameters)))
    check("`only` defaults to None, so callers are unaffected",
          signature.parameters["only"].default is None)

    print(f"\nPASSED {len(PASSED)}   FAILED {len(FAILED)}")
    for name in FAILED:
        print(f"  - {name}")
    return 1 if FAILED else 0


def main() -> int:
    # `_candidate_chain` reads the running loop for its cooldown check, exactly
    # as it always did; the tests must therefore run inside one.
    return asyncio.run(_checks())


if __name__ == "__main__":
    raise SystemExit(main())
