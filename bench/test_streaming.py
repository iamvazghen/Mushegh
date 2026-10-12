"""Streaming voice path — agent.respond_stream yields spoken sentences as they generate.

Hermetic (fake LLM, no network). Verifies: (1) a plain answer streams out sentence-by-sentence;
(2) a tool call is resolved between passes and the final answer still streams; (3) the full reply
is persisted to history; (4) the sentence splitter keeps a trailing partial sentence and flushes it.

    uv run python bench/test_streaming.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


# This file says it is hermetic, and until 2026-10-08 it was not: every agent built here
# stubbed `_llm` but still reached the REAL judgment service for its turn assessment.
# `test_run_all_tests.py` classifies this "offline", so a live network call is a contract
# break - and an intermittent one, because it only failed when Jev happened to answer "I
# need clarification" for a test prompt ("tell me a long story") that has nothing to do
# with streaming. The agent then returned the canned question instead of streaming, and a
# streaming gate failed on a judgement it was never meant to test.
#
# The subject here is SENTENCES, so the assessment is stubbed to the boring case: nothing
# is unclear, nothing needs arbitrating. Same shape as `_Stub` in
# `test_jev_turn_assessment.py`, applied once for the whole file.
class _OfflineJudgments:
    async def assess_turn(self, _text, *, groups=(), arbitrate=True, ask_clarity=True,
                          correlation_id=""):
        from mushegh.brain.judgment import TurnSignals
        return TurnSignals(candidates=(), group=None, urgency=None, tone=None, clarity=None,
                           outcome="disabled", latency_ms=0.0)

    async def consider(self, _text, *, correlation_id=""):
        return None


def _make_hermetic() -> None:
    from mushegh.brain import agent as _agent
    _agent.JUDGMENTS = _OfflineJudgments()


_make_hermetic()

passed = failed = 0


def check(name: str, ok: bool, detail: str = "") -> None:
    global passed, failed
    if ok:
        passed += 1
        print(f"  [PASS] {name}")
    else:
        failed += 1
        print(f"  [FAIL] {name}  {detail}")


class FakeLLM:
    """Scripted streamer: each call to stream_with_tools replays the next pass of events."""

    def __init__(self, scripts: list[list[tuple]]) -> None:
        self._scripts = scripts
        self._i = 0

    async def stream_with_tools(self, messages, tools=None, temperature=0.6, tool_choice="auto", skip_primary=False):
        script = self._scripts[self._i]
        self._i += 1
        for ev in script:
            yield ev


async def test_plain_answer() -> None:
    print("[1] plain answer streams sentence-by-sentence")
    from mushegh.brain.agent import MusheghAgent

    agent = MusheghAgent()
    agent._llm = FakeLLM([[("text", "I am well, Sir. "), ("text", "All systems green.")]])
    out = [s async for s in agent.respond_stream("how are you")]
    check("yielded two sentences in order", out == ["I am well, Sir.", "All systems green."], repr(out))
    check("full reply persisted to history",
          agent._history[-1]["role"] == "assistant"
          and "All systems green." in agent._history[-1]["content"], repr(agent._history[-1]))


async def test_tool_then_stream() -> None:
    print("\n[2] a NON-speakable tool call is resolved, then the final answer streams (two-pass)")
    from mushegh.brain.agent import MusheghAgent

    agent = MusheghAgent()
    ran = {"n": 0}

    async def fake_tool(_args: dict) -> str:
        ran["n"] += 1
        return "note: the rabbit farm charter is in 30-Projects"

    # search_vault is NOT in _SPEAKABLE_DIRECT, so the model still does its summary pass.
    agent._registry["search_vault"] = fake_tool
    agent._llm = FakeLLM([
        [("tools", [{"id": "c1", "name": "search_vault", "arguments": "{}"}])],
        [("text", "Found it, Sir.")],
    ])
    out = [s async for s in agent.respond_stream("search my vault for the rabbit farm")]
    check("the tool ran exactly once", ran["n"] == 1, str(ran))
    check("the post-tool answer streamed", out == ["Found it, Sir."], repr(out))
    check("history holds user + tool turn + final assistant",
          agent._history[-1]["content"] == "Found it, Sir.")


async def test_no_double_failover_midstream() -> None:
    print("\n[3] mid-stream provider break does not double-speak (fails over only before 1st token)")
    from mushegh.brain.llm import LLMClient

    llm = LLMClient()
    llm._chain = ["a", "b"]

    import httpx
    from openai import APITimeoutError

    async def fake_create(**kwargs):
        # Model 'a' yields one token then the stream raises a (failover-eligible) timeout; 'b'
        # would answer — but since 'a' already emitted, we must NOT fail over (would repeat speech).
        async def gen():
            if kwargs["model"] == "a":
                yield _chunk("Hello ")
                raise APITimeoutError(request=httpx.Request("POST", "http://localhost"))
            yield _chunk("SHOULD-NOT-APPEAR")
        return gen()

    llm._default.chat.completions.create = fake_create
    texts = []
    async for kind, payload in llm.stream_with_tools([{"role": "user", "content": "hi"}]):
        if kind == "text":
            texts.append(payload)
    check("only the first model's partial text came through", texts == ["Hello "], repr(texts))


def _chunk(content):
    from types import SimpleNamespace
    return SimpleNamespace(choices=[SimpleNamespace(
        delta=SimpleNamespace(content=content, tool_calls=None))])


async def test_cancelled_stream_no_dangling_user() -> None:
    print("\n[4] a cancelled stream still records an assistant turn (no dangling user msg, AUDIT #7)")
    from mushegh.brain.agent import MusheghAgent

    agent = MusheghAgent()
    agent._llm = FakeLLM([[("text", "First sentence. "), ("text", "Second. "), ("text", "Third.")]])
    gen = agent.respond_stream("tell me a long story")
    first = await gen.__anext__()      # consume one chunk…
    await gen.aclose()                 # …then a barge-in / supersede closes the stream mid-turn
    check("first chunk streamed", first == "First sentence.", repr(first))
    check("history ends on an assistant turn (not a dangling user msg)",
          agent._history[-1]["role"] == "assistant", repr(agent._history[-1]))
    check("no two consecutive user turns",
          not (len(agent._history) >= 2
               and agent._history[-1]["role"] == "user" and agent._history[-2]["role"] == "user"))


async def test_midstream_break_is_continued() -> None:
    """02.R3 — the two streaming paths were wrong in opposite directions.

    `stream_with_tools` refused to fail over once it had spoken (right: restarting says the opening
    twice) and therefore ended the turn wherever the fault landed — half a sentence. `stream`, the
    PURE-CHAT path and the commonest turn there is, had no such guard at all: it fell through to the
    next model, which answered from the beginning, and the owner heard the first sentence twice.
    Both now ask the next model for the REST.
    """
    print("\n[5] 02.R3 — a break mid-sentence is finished, not repeated and not cut")
    import httpx
    from openai import APITimeoutError
    from types import SimpleNamespace

    from mushegh.brain.llm import LLMClient, _drop_overlap

    # The de-overlap rule on its own: a model told not to repeat itself still often echoes the last
    # few words, and the owner hears that as a stutter.
    check("an echoed tail is dropped",
          _drop_overlap("I checked the calendar and", " and you have two meetings")
          == " you have two meetings",
          repr(_drop_overlap("I checked the calendar and", " and you have two meetings")))
    # The spacing at the join survives on purpose: trimming it would glue "calendar" to "and" —
    # a fix for a stutter that produces a worse artefact than the stutter.
    check("the word boundary at the join is kept",
          _drop_overlap("I checked the calendar and", " and you have").startswith(" "))
    check("a continuation that does not overlap is left alone",
          _drop_overlap("Morning, sir.", " You have two meetings.") == " You have two meetings.")
    check("an empty continuation stays empty", _drop_overlap("anything", "") == "")
    check("a whole repeat is NOT silently deleted",
          _drop_overlap("x" * 500, "y" * 10) == "y" * 10,
          "past the cap, a repeat is better visible than quietly swallowed")

    # --- the tool path: broke after speaking, used to stop there ---------------------------------
    llm = LLMClient()
    llm._chain = ["a", "b"]

    async def break_after_lead(**kwargs):
        async def gen():
            if kwargs["model"] == "a":
                yield _chunk("I checked the calendar and ")
                raise APITimeoutError(request=httpx.Request("POST", "http://localhost"))
            yield _chunk("RESTARTED FROM THE TOP")
        return gen()

    llm._default.chat.completions.create = break_after_lead

    seen: list[str] = []

    async def fake_complete(messages, **_kw):
        seen.append(messages[-2]["content"])      # what the continuation was handed
        return SimpleNamespace(content=" and you have two meetings, sir.", tool_calls=None)

    llm.complete = fake_complete
    out = []
    async for kind, payload in llm.stream_with_tools([{"role": "user", "content": "my day?"}]):
        if kind == "text":
            out.append(payload)
    spoken = "".join(out)
    check("the utterance is finished, not cut off mid-sentence",
          spoken.endswith("two meetings, sir."), repr(spoken))
    check("...and nothing is said twice", spoken.count("I checked the calendar") == 1, repr(spoken))
    check("...and the fallback did NOT restart from the top",
          "RESTARTED" not in spoken, repr(spoken))
    check("the continuation is handed what was already spoken",
          seen and seen[0].startswith("I checked the calendar"), str(seen))

    # --- the pure-chat path: broke after speaking, used to repeat itself -------------------------
    llm2 = LLMClient()
    llm2._chain = ["a", "b"]
    llm2._default.chat.completions.create = break_after_lead
    llm2.complete = fake_complete
    pieces = [p async for p in llm2.stream([{"role": "user", "content": "my day?"}])]
    said = "".join(pieces)
    check("the pure-chat path no longer restarts the answer",
          "RESTARTED" not in said, repr(said))
    check("...and it is finished too", said.endswith("two meetings, sir."), repr(said))

    # --- a break BEFORE the first token must still fail over ------------------------------------
    # This is the case the first version of this gate missed, and `test_llm_failover_speed.py`
    # caught it on the pre-push run: `got_any` was initialised inside the try, whose FIRST statement
    # is the connect, so a provider that refuses the connection outright made the except clause read
    # an unbound variable — UnboundLocalError instead of a failover. Nothing about "mid-utterance"
    # was wrong; the guard simply ran on a path where it had no state yet.
    llm4 = LLMClient()
    llm4._chain = ["a", "b"]

    async def dead_on_connect(**kwargs):
        if kwargs["model"] == "a":
            raise APITimeoutError(request=httpx.Request("POST", "http://localhost"))

        async def gen():
            yield _chunk("The fallback answered.")
        return gen()

    llm4._default.chat.completions.create = dead_on_connect
    early = "".join([p async for p in llm4.stream([{"role": "user", "content": "hi"}])])
    check("a model that fails before the first token still fails over",
          early == "The fallback answered.", repr(early))

    # --- and when the continuation itself fails, we keep what we had ----------------------------
    llm3 = LLMClient()
    llm3._chain = ["a", "b"]
    llm3._default.chat.completions.create = break_after_lead

    async def dead_complete(*_a, **_kw):
        raise RuntimeError("the chain is down too")

    llm3.complete = dead_complete
    kept = "".join([p async for p in llm3.stream([{"role": "user", "content": "my day?"}])])
    check("a failed continuation leaves the partial utterance, never an exception",
          kept == "I checked the calendar and ", repr(kept))
    check("...and still does not restart", "RESTARTED" not in kept, repr(kept))


async def test_interrupted_turn_resumes() -> None:
    """07.R3 — "carry on" finishes the answer a barge-in cut off.

    An interrupted turn used to be recorded as the bare word "(interrupted)", which throws away
    both halves of what a resume needs: what he asked for, and how far the answer got. Asking Mushegh
    to carry on then produced either a fresh answer to nothing, or a confident restatement of
    something he had already heard.
    """
    print("\n[6] 07.R3 — an interrupted turn is held, and 'carry on' finishes it")
    from mushegh.brain.agent import _NOTHING_TO_RESUME, _RESUME_RE, MusheghAgent

    for phrase in ("carry on", "go on", "continue", "keep going", "finish that",
                   "you were saying", "and then?"):
        check(f"{phrase!r} reads as a resume", bool(_RESUME_RE.match(phrase)))
    # Anchored to the whole utterance on purpose: these name their own subject, so they are
    # ordinary requests and must not hijack a held turn.
    for phrase in ("carry on with the shopping list", "continue the report to Anna",
                   "go on holiday planning"):
        check(f"{phrase!r} is an ordinary request, not a resume",
              not _RESUME_RE.match(phrase))

    # A deliberately tool-free utterance: this is testing the interruption path, and a request that
    # routes to a real tool would answer from the owner's actual data instead of the script.
    agent = MusheghAgent()
    agent._llm = FakeLLM([[("text", "The first thing is the boiler. "),
                           ("text", "The second is the letter. "),
                           ("text", "The third is…")]])
    gen = agent.respond_stream("tell me a story about the sea")
    first = await gen.__anext__()
    await gen.aclose()                       # barge-in mid-answer

    check("the first sentence reached him", first.startswith("The first thing"), repr(first))
    check("the cut turn is held, not discarded", agent._interrupted is not None)
    check("...along with what he actually asked for",
          (agent._interrupted or {}).get("ask") == "tell me a story about the sea")
    check("...and how far the answer got", "boiler" in (agent._interrupted or {}).get("said", ""))
    check("the transcript keeps what he heard, not just '(interrupted)'",
          "boiler" in str(agent._history[-1].get("content", "")),
          str(agent._history[-1])[:100])

    # Resuming asks the chain to continue from what was already spoken — the same mechanism a
    # mid-stream provider break uses (02.R3), for the same reason: what he heard is a perfectly
    # good assistant turn to hand the next pass.
    handed: dict = {}

    async def fake_finish(messages, said):
        handed["said"] = said
        handed["ask"] = messages[-1]["content"]
        return " The second is the letter to the landlord."

    agent._llm._finish_broken_stream = fake_finish
    out = "".join([c async for c in agent.respond_stream("carry on")])
    check("the resume continues rather than restarting",
          out.strip().startswith("The second"), repr(out[:70]))
    check("the continuation is handed what he already heard",
          handed.get("said", "").startswith("The first thing"), str(handed)[:90])
    check("...and the original question, so it knows what it is finishing",
          "story about the sea" in str(handed.get("ask", "")), str(handed.get("ask"))[:70])
    check("one resume per interruption — the slot is cleared", agent._interrupted is None)

    # Carrying on with nothing held must not invent a thread to continue.
    agent2 = MusheghAgent()
    agent2._interrupted = None
    plan = await agent2._prepare_turn("carry on")
    check("'carry on' with nothing interrupted asks him what to pick up",
          any(_NOTHING_TO_RESUME in str(m.get("content", "")) for m in plan.messages))
    check("...and the instruction says not to invent one",
          "do not invent" in _NOTHING_TO_RESUME.lower())


async def main() -> None:
    await test_plain_answer()
    await test_tool_then_stream()
    await test_no_double_failover_midstream()
    await test_cancelled_stream_no_dangling_user()
    await test_midstream_break_is_continued()
    await test_interrupted_turn_resumes()
    await test_interrupted_turn_resumes()
    print(f"\n=== {passed}/{passed + failed} checks passed ===")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
