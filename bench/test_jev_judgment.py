"""14.R5 - Jev owns explicit contextual decisions; the LLM only verbalizes.

Hermetic: every provider response is injected. The separate live smoke is manual and never part of
the aggregate gate.

    uv run python bench/test_jev_judgment.py
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

passed = failed = 0


def check(name: str, ok: bool, detail: str = "") -> None:
    global passed, failed
    if ok:
        passed += 1
        print(f"  [PASS] {name}")
    else:
        failed += 1
        print(f"  [FAIL] {name}  {detail}")


async def service_contract(root: Path) -> None:
    from afon.brain.judgment import JudgmentService, explicit_decision

    print("[1] conservative explicit-option parser")
    parsed = explicit_decision("Choose between taking the train or driving the car.")
    check("clear decision yields stable option IDs", parsed is not None and
          [o.id for o in parsed.options] == ["option_1", "option_2"])
    check("owner option prose is preserved", parsed is not None and
          [o.text for o in parsed.options] == ["taking the train", "driving the car"])
    check("an ambiguous command is not outsourced", explicit_decision("Open Chrome or Firefox") is None)
    check("an ordinary should-question is not outsourced",
          explicit_decision("Should I call an ambulance for a nosebleed?") is None)
    check("duplicate alternatives are rejected", explicit_decision("Choose between blue or blue") is None)

    print("\n[2] absent key is fail-closed and makes no network call")
    network = {"calls": 0}

    async def must_not_call(*_args):
        network["calls"] += 1
        raise AssertionError("network called")

    no_key = JudgmentService(key="", transport=must_not_call, log_path=root / "no-key.jsonl")
    unavailable = await no_key.consider("Choose between blue or green", correlation_id="turn-1")
    check("missing key returns an unavailable verdict", unavailable is not None and
          unavailable.outcome == "unavailable" and unavailable.fallback == "ask_owner")
    check("missing key never touches transport", network["calls"] == 0)

    print("\n[3] successful payload is minimal and result is typed")
    captured = {}

    async def success(payload, key, endpoint, timeout):
        captured.update(payload=payload, key=key, endpoint=endpoint, timeout=timeout)
        return 200, {
            "model": "jev-1.13.0",
            "answers": {"decision": {
                "type": "choice", "choice": "option_2", "confidence": 0.91,
                "probabilities": {"option_1": 0.14, "option_2": 0.86},
            }},
        }

    log = root / "success.jsonl"
    service = JudgmentService(key="test-secret", transport=success, log_path=log)
    verdict = await service.consider(
        "Choose between taking the train or driving the car", correlation_id="turn-2",
    )
    check("Jev selection maps back to owner option", verdict is not None and verdict.decided and
          verdict.selected_id == "option_2" and verdict.selected_text == "driving the car")
    check("probability, confidence and resolved model survive", verdict is not None and
          verdict.probability == 0.86 and verdict.confidence == 0.91 and verdict.model == "jev-1.13.0")
    payload = captured.get("payload", {})
    check("outbound contract has only model/state/questions", set(payload) == {"model", "state", "questions"})
    check("state contains current question only", set(payload.get("state", {})) == {"question"})
    wire = json.dumps(payload).lower()
    check("payload excludes history, memory, tools, biometrics and secret",
          all(term not in wire for term in ("history", "memory", "tool_output", "biometric", "test-secret")))
    check("criteria uses only stable option IDs",
          set(payload["questions"]["decision"]["criteria"]) == {"option_1", "option_2"})

    row_text = log.read_text(encoding="utf-8")
    row = json.loads(row_text)
    check("audit links request and turn without prose", row["correlation_id"] == "turn-2" and
          row["selected_id"] == "option_2" and "question" not in row and "options" not in row)
    check("audit never stores raw option text", "train" not in row_text and "driving" not in row_text)
    snap = service.snapshot()
    check("compact HUD status has availability and latest IDs", snap["available"] is True and
          snap["calls"] == 1 and snap["latest"]["selected_id"] == "option_2")

    print("\n[4] provider and schema failures never fall back to an LLM decision")
    outcomes = []

    async def http_error(_payload, _key, _endpoint, _timeout):
        return 429, {"error": "rate limited"}

    async def malformed(_payload, _key, _endpoint, _timeout):
        return 200, {"model": "jev-x", "answers": {"decision": {"choice": "option_99"}}}

    async def timeout(_payload, _key, _endpoint, _timeout):
        raise TimeoutError("late")

    for i, transport in enumerate((http_error, malformed, timeout)):
        svc = JudgmentService(key="fake", transport=transport, log_path=root / f"error-{i}.jsonl")
        result = await svc.consider("Which option: local or cloud?", correlation_id=f"err-{i}")
        outcomes.append(result)
    check("429, malformed choice and timeout all ask the owner",
          all(v is not None and not v.decided and v.fallback == "ask_owner" for v in outcomes))
    check("malformed response is distinguished from outage",
          [v.outcome for v in outcomes if v is not None] == ["unavailable", "invalid", "unavailable"])


class StubJudgments:
    def __init__(self, verdict):
        self.verdict = verdict
        self.calls = 0

    async def consider(self, _text, *, correlation_id=""):
        self.calls += 1
        return self.verdict


class FakeLLM:
    def __init__(self, answer: str):
        self.answer = answer
        self.calls = []

    async def complete(self, messages, **_kwargs):
        self.calls.append(messages)
        return SimpleNamespace(content=self.answer, tool_calls=None)


async def agent_contract(root: Path) -> None:
    import afon.brain.agent as agent_module
    from afon.brain.agent import AfonAgent
    from afon.brain.judgment import DecisionVerdict

    os.environ["AFON_TRACE_DIR"] = str(root / "traces")
    selected = DecisionVerdict(
        request_id="req-1", correlation_id="turn-1", kind="explicit_options",
        option_ids=("option_1", "option_2"), selected_id="option_2", selected_text="green",
        probability=0.8, confidence=0.9, model="jev-test", latency_ms=1.0,
        outcome="decided", fallback="none",
    )
    unavailable = DecisionVerdict(
        request_id="req-2", correlation_id="turn-2", kind="explicit_options",
        option_ids=("option_1", "option_2"), selected_id=None, selected_text=None,
        probability=None, confidence=None, model="", latency_ms=1.0,
        outcome="unavailable", fallback="ask_owner", error="http_429",
    )
    original = agent_module.JUDGMENTS
    try:
        print("\n[5] LLM can phrase but cannot reverse the Jev choice")
        agent_module.JUDGMENTS = StubJudgments(selected)
        agent = AfonAgent()
        agent._history = []
        agent._persist_session = lambda: None
        agent._spawn_review = lambda: None
        bad_llm = FakeLLM("I recommend blue instead.")
        agent._llm = bad_llm
        reply = await agent.respond("Choose between blue or green")
        check("invalid verbalization is replaced with typed Jev result",
              reply.startswith("Jev selected: green.") and "blue" not in reply, reply)
        prompt_wire = json.dumps(bad_llm.calls[0]).lower()
        check("wording model sees selected option but not losing option",
              "green" in prompt_wire and "blue" not in prompt_wire, prompt_wire)

        print("\n[6] streaming and buffered paths share the decision seam")
        agent2 = AfonAgent()
        agent2._history = []
        agent2._persist_session = lambda: None
        agent2._spawn_review = lambda: None
        agent2._llm = FakeLLM("Jev selected: green. Reported confidence: 90%.")
        chunks = [chunk async for chunk in agent2.respond_stream("Choose between blue or green")]
        check("stream path emits the same authoritative selection", chunks == [
            "Jev selected: green. Reported confidence: 90%."
        ], repr(chunks))
        check("stream history records the decision response", agent2._history[-1]["content"] == chunks[0])

        print("\n[7] Jev outage cannot silently become an LLM decision")
        agent_module.JUDGMENTS = StubJudgments(unavailable)
        agent3 = AfonAgent()
        agent3._history = []
        agent3._persist_session = lambda: None
        agent3._spawn_review = lambda: None
        unused_llm = FakeLLM("Choose blue")
        agent3._llm = unused_llm
        held = await agent3.respond("Choose between blue or green")
        check("outage asks rather than chooses", "haven't chosen" in held and "retry" in held)
        check("outage never invokes generative model", unused_llm.calls == [])

        print("\n[8] deterministic catastrophic refusal stays above Jev")
        counter = StubJudgments(selected)
        agent_module.JUDGMENTS = counter
        agent4 = AfonAgent()
        agent4._history = []
        agent4._persist_session = lambda: None
        refused = await agent4.respond("format c:")
        check("catastrophic command is still refused",
              "refused" in refused.lower() and "won't do" in refused.lower(), refused)
        check("catastrophic command never reaches Jev", counter.calls == 0)
    finally:
        agent_module.JUDGMENTS = original


async def main() -> None:
    with tempfile.TemporaryDirectory(prefix="afon-jev-") as tmp:
        root = Path(tmp)
        await service_contract(root)
        await agent_contract(root)
    print(f"\n=== {passed}/{passed + failed} checks passed ===")
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
