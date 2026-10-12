"""Why does a compound turn offer `get_time` first? Measure, don't reason about it.

`test_clause_completion.py` fails with `plan=['read_email', 'remember']` but
`fired=['get_time', 'remember']` — the model called `get_time`, which is not in the clause
plan at all. The test's fake model faithfully fires "the first tool it is offered", so the
question is entirely about what the agent ADVERTISED on the first pass and in what order.

This prints, for that one prompt, each of the things that could produce it:
  * `forced_tools` / `clause_tools` / `groups_for_text` — what the router decided
  * whether the turn is multi_intent and whether it is narrowed
  * the actual advertised tool order on the first model call

Nothing is changed or stubbed here beyond reading the routing decision. Read-only with
respect to src/.

Usage:
    python tools/diagnose_clause_offer.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mushegh.brain.intent_router import _is_multi_intent, clause_tools, forced_tools  # noqa: E402

COMBO = "check my email and remember to call mum"


def main() -> int:
    print(f"prompt: {COMBO!r}\n")
    print("  forced_tools      :", forced_tools(COMBO))
    print("  clause_tools      :", clause_tools(COMBO))
    print("  _is_multi_intent  :", _is_multi_intent(COMBO))

    # Now the part that matters: what does the first model call actually SEE?
    from mushegh.brain.agent import MusheghAgent

    seen_order: list[list[str]] = []

    class _Probe:
        """Fires nothing. Records the offered order and answers in prose, so the turn
        completes without a tool firing and the agent's own narrowing is visible."""

        def __init__(self) -> None:
            self.n = 0

        def _names(self, tools):
            return [t["function"]["name"] for t in (tools or [])]

        def complete(self, messages, tools=None, **kw):
            self.n += 1
            order = self._names(tools)
            seen_order.append(order)
            return {"role": "assistant", "content": "Done."}

    import asyncio

    agent = MusheghAgent()
    agent._llm = _Probe()
    agent._self_improve = False
    try:
        asyncio.run(agent.respond(COMBO))
    except Exception as exc:  # noqa: BLE001
        print(f"\n  (turn raised: {type(exc).__name__}: {exc})")

    print("\n  advertised tool order per model call:")
    for i, order in enumerate(seen_order):
        head = order[:12]
        print(f"    call {i + 1}: {len(order)} tool(s) -> {head}"
              + (" ..." if len(order) > 12 else ""))

    if seen_order:
        first = seen_order[0]
        print(f"\n  get_time on the first call? {'get_time' in first}")
        print(f"  read_email on the first call? {'read_email' in first}")
        if first:
            print(f"  index of get_time  : {first.index('get_time') if 'get_time' in first else '-'}")
            print(f"  index of read_email: "
                  f"{first.index('read_email') if 'read_email' in first else '-'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())