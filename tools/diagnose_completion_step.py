"""Log what `_Completion.step` actually sees and decides for a compound turn.

Reading the code says this gate should pass: `outstanding` is non-empty,
`passes(0) < len(clause_plan)(2)`, and `multi_intent` is True. Three attempts to fix it
by editing have each traded a check for another, so this measures the decision itself
instead — no source is modified, the method is wrapped at runtime.

What it prints per step: the inputs, the computed `outstanding` / `may_complete`, and
the returned tuple. If `step` is never called at all, the problem is upstream of it — the
loop only calls it when the model returns NO tool calls.

Usage:
    python tools/diagnose_completion_step.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

COMBO = "check my email and remember to call mum"


def main() -> int:
    from afon.brain import agent as A

    original_step = A._Completion.step
    calls: list[str] = []

    def traced(self, seen_tools, turn_tools, forced_name, narrowed, messages):
        outstanding = [n for n in self.clause_plan if n not in seen_tools]
        may_complete = (
            (bool(outstanding) and self.passes < len(self.clause_plan))
            or (not self.clause_plan and len(seen_tools) == 1 and not self.done)
        )
        result = original_step(self, seen_tools, turn_tools, forced_name, narrowed, messages)
        calls.append(
            f"    step() called  seen={sorted(seen_tools)} outstanding={outstanding} "
            f"passes={self.passes}/{len(self.clause_plan)} done={self.done} "
            f"multi_intent={self.multi_intent} may_complete={may_complete}\n"
            f"      -> again={result[0]} forced={result[2]!r} narrowed={result[3]}"
        )
        return result

    A._Completion.step = traced  # type: ignore[method-assign]

    fired: list[str] = []

    class _M:
        def __init__(self, tool_calls=None, content=""):
            self.tool_calls = tool_calls
            self.content = content

    class _TC:
        _n = 0

        def __init__(self, name):
            _TC._n += 1
            self.id = f"c{_TC._n}"

            class _F:
                pass
            self.function = _F()
            self.function.name = name
            self.function.arguments = "{}"

    class FakeLLM:
        """Faithful to test_clause_completion.py: fire the FIRST tool offered, once,
        then talk. That is the real failure being modelled."""

        def __init__(self):
            self.calls = 0
            self.fired: list[str] = []

        async def complete(self, messages, tools=None, **kw):
            self.calls += 1
            offered = [t["function"]["name"] for t in (tools or [])]
            for name in offered:
                if name not in self.fired:
                    if self.calls == 1 or len(offered) == 1:
                        self.fired.append(name)
                        fired.append(name)
                        return _M(tool_calls=[_TC(name)])
            return _M(content="Done.")

    agent = A.AfonAgent()
    agent._llm = FakeLLM()
    agent._self_improve = False

    # The question the gate cannot answer: did the tool ACTUALLY RUN, whoever ran it?
    # Wrap the registry entries so execution is recorded independently of what the model
    # chose to emit. `test_clause_completion.py` asserts on the model's tool_calls, so a read
    # the agent fires itself is invisible to it however correctly it behaves.
    executed: list[str] = []

    def _wrap(name: str, original):
        async def _run(*a, **kw):
            executed.append(name)
            return await original(*a, **kw)
        return _run

    for tool_name in ("read_email", "remember", "get_time"):
        entry = agent._registry.get(tool_name)
        handler = getattr(entry, "handler", entry)
        if callable(handler):
            agent._registry[tool_name] = _wrap(tool_name, handler)

    reply = asyncio.run(agent.respond(COMBO))

    print(f"prompt : {COMBO!r}")
    print(f"model fired : {fired}      <- what the gate measures")
    print(f"actually ran: {executed}      <- what it claims to assert")
    from afon.brain.intent_router import clause_tools as _plan

    plan = _plan(COMBO)
    print(f"plan        : {plan}")
    print(f"reply       : {reply!r}\n")
    print(f"  every plan tool ACTUALLY ran? {all(n in executed for n in plan)}")
    print(f"  every plan tool appears in model tool_calls? {all(n in fired for n in plan)}")
    print("\n  _Completion.step trace:")
    if calls:
        for c in calls:
            print(c)
    else:
        print("    step() was NEVER CALLED.")

    A._Completion.step = original_step  # type: ignore[method-assign]
    return 0


if __name__ == "__main__":
    raise SystemExit(main())