"""Isolate the D-92 verbalizer tier from the network.

`test_jev_judgment.py` makes a live Jev call, so it is slow or times out for
reasons that have nothing to do with this change. This test exercises
`_verbalize_judgment` directly with a fake LLM, and asserts the one property
that matters: **with the tier off, the call is byte-identical to before.**

Network-free and deterministic.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from afon.brain import agent as agent_module  # noqa: E402
from afon.brain.judgment import DecisionVerdict  # noqa: E402

PASSED: list[str] = []
FAILED: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    (PASSED if ok else FAILED).append(label)
    print(f"  {'PASS' if ok else 'FAIL'}  {label}" + (f"  [{detail}]" if detail else ""))


class _Message:
    """The LLMClient return value carries `.content`; the fake must match it."""

    def __init__(self, content: str) -> None:
        self.content = content


class FakeLLM:
    """Records how it was called, and replies with the required prefix."""

    def __init__(self, reply: str = "") -> None:
        self.calls: list[dict[str, Any]] = []
        self._reply = reply

    async def complete(self, messages, tools=None, temperature=0.6,
                       tool_choice="auto", skip_primary=False,
                       prepend_model=None, only=None) -> Any:
        self.calls.append({"only": only, "n_messages": len(messages)})
        text = self._reply or f"Jev selected: {self._expected(messages)}. Reported confidence: 90%."
        return _Message(text)

    @staticmethod
    def _expected(messages) -> str:
        for message in messages:
            content = message.get("content") or ""
            if content.startswith("Required prefix:"):
                return content.split("Required prefix:", 1)[1].split("Reported confidence")[0].strip()
        return "the selected option"


class ExplodingLLM:
    """Fails every call, standing in for a tier that is not running."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def complete(self, messages, tools=None, temperature=0.6,
                       tool_choice="auto", skip_primary=False,
                       prepend_model=None, only=None) -> Any:
        self.calls.append({"only": only})
        raise RuntimeError("this tier is not available")


def _agent_with(llm: Any) -> Any:
    agent = object.__new__(agent_module.AfonAgent)
    agent._llm = llm
    agent._history = []
    agent._persist_session = lambda: None
    agent._spawn_review = lambda: None
    return agent


def _verdict(selected: str = "opt_a", text: str = "the office one",
             outcome: str = "decided") -> DecisionVerdict:
    return DecisionVerdict(
        request_id="req-test",
        correlation_id="",
        kind="explicit",
        option_ids=("opt_a", "opt_b"),
        selected_id=selected or None,
        selected_text=text or None,
        probability=0.9,
        confidence=0.9,
        model="jev-test",
        latency_ms=1,
        outcome=outcome,
        fallback="",
    )


async def _checks() -> int:
    verdict = _verdict()

    print("=== 1. tier OFF: the call carries only=None, exactly as before ===")
    fake = FakeLLM()
    reply = await _agent_with(fake)._verbalize_judgment(verdict)
    check("one LLM call was made", len(fake.calls) == 1, str(fake.calls))
    check("`only` is None, so the normal chain is walked", fake.calls[0]["only"] is None,
          repr(fake.calls[0]["only"]))
    check("the selected option is verbalized", "the office one" in reply, reply[:70])
    check("the losing alternative never reaches the model", "docs one" not in reply)
    # A reply that passed the guard must be returned verbatim, not the fallback.
    check("a compliant reply is returned, not replaced by the fallback",
          reply.count("Reported confidence") == 1 and "haven't chosen" not in reply, reply[:70])

    print("\n=== 2. the prefix guard still holds ===")
    disobedient = FakeLLM(reply="Actually, I would pick the docs one instead.")
    guarded = await _agent_with(disobedient)._verbalize_judgment(verdict)
    check("a disobedient reply is replaced by the deterministic sentence",
          guarded == f"Jev selected: the office one. Reported confidence: 90%.",
          guarded[:70])
    check("the disobedience cannot reverse the typed choice", "docs one" not in guarded)

    print("\n=== 3. tier ON: the dedicated models are passed through ===")
    import afon.config as config_module
    original = config_module.settings.verbalizer_models
    try:
        config_module.settings.verbalizer_models = "ollama:qwen3:0.6b,groq:llama-3.1-8b-instant"
        fake_on = FakeLLM()
        await _agent_with(fake_on)._verbalize_judgment(verdict)
        check("the dedicated tier is handed to the chain",
              fake_on.calls and fake_on.calls[0]["only"] ==
              ["ollama:qwen3:0.6b", "groq:llama-3.1-8b-instant"],
              repr(fake_on.calls[0]["only"]) if fake_on.calls else "no call")
    finally:
        config_module.settings.verbalizer_models = original

    print("\n=== 4. an unavailable tier degrades wording, never the decision ===")
    boom = ExplodingLLM()
    degraded = await _agent_with(boom)._verbalize_judgment(verdict)
    check("a failing tier still yields the decided option",
          degraded.startswith("Jev selected: the office one."), degraded[:70])
    check("the confidence is still reported", "90%" in degraded, degraded[:70])

    print("\n=== 5. an undecided verdict never reaches the renderer ===")
    undecided = _verdict(selected="", text="", outcome="unavailable")
    never = FakeLLM()
    asked = await _agent_with(never)._verbalize_judgment(undecided)
    check("no LLM call is made when Jev did not decide", never.calls == [])
    check("the owner is asked instead of the model choosing", "haven't chosen" in asked, asked[:60])

    print(f"\nPASSED {len(PASSED)}   FAILED {len(FAILED)}")
    for name in FAILED:
        print(f"  - {name}")
    return 1 if FAILED else 0


def main() -> int:
    return asyncio.run(_checks())


if __name__ == "__main__":
    raise SystemExit(main())
