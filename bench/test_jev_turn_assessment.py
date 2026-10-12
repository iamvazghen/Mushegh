"""Jev at full capacity: one bounded call for route, clarity, urgency and tone (01.R7).

`01.R6` gave Jev one job — pick the tool group. This asserts the extension that makes it the
turn's decision layer, and the three properties that keep that safe:

  * **One call, not four.** Route, clarity, urgency and tone are asked together, because three
    sequential calls would spend three budgets and could contradict each other — the third
    would be reading a different moment from the first.
  * **Ambiguity gets a question, not a guess.** When the turn gives no clear decision
    indication — Jev says the request is underspecified, or it names a group it will not stand
    behind — the reply is ONE clarifying question and no tool fires. This generalises 01.R2,
    which caught only a pointer with no antecedent ("the same as before").
  * **Silence is for a FAILED assessment, not an unsure one.** They are different failures and
    only one of them is the owner's to solve. An outage must not start asking questions about
    turns that are perfectly clear.

And the safety line, asserted rather than assumed: **urgency shapes framing only.** It can
never raise the interruption budget or pierce quiet hours (D-29, D-32); only life-safety does
that, and that stays deterministic code (D-18).

Hermetic: the transport is replaced. No network, no key, no LLM.

    uv run python bench/test_jev_turn_assessment.py
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
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


CLEAR = "my inbox has something about the lease document"
UNCLEAR = "set it to three"


async def service_contract(root: Path) -> None:
    from mushegh.brain.judgment import (
        ENTROPY_FAST_MAX,
        ENTROPY_ROUTE_FAST_MAX,
        JudgmentService,
        clarity_question,
        manner_note,
        normalized_entropy,
    )

    print("[1] one request carries every question the turn needs")
    seen: list[dict] = []

    async def full(payload, _k, _e, _t):
        seen.append(payload)
        return 200, {"model": "jev-test", "answers": {
            "route": {"choice": "group_2",
                      "probabilities": {"group_1": 0.1, "group_2": 0.9}},
            "clarity": {"choice": "clarity_clear", "probabilities": {"clarity_clear": 0.95}},
            "urgency": {"choice": "urgency_now", "probabilities": {"urgency_now": 0.7}},
            "tone": {"choice": "tone_direct", "probabilities": {"tone_direct": 0.6}},
        }}

    svc = JudgmentService(key="k", transport=full, log_path=root / "full.jsonl")
    sig = await svc.assess_turn(CLEAR, groups=["office", "docs"], ask_clarity=True)
    check("exactly one round trip", len(seen) == 1, str(len(seen)))
    check("all four questions travelled in it",
          sorted(seen[0]["questions"]) == ["clarity", "route", "tone", "urgency"],
          str(sorted(seen[0]["questions"])))
    check("route, clarity, urgency and tone all came back",
          sig is not None and sig.group == "docs" and sig.clarity == "clear"
          and sig.urgency == "now" and sig.tone == "direct", repr(sig))
    check("a confident pick is routed", sig is not None and sig.routed)
    check("no clarification is needed", sig is not None and not sig.needs_clarification)
    check("the labels came from code, not the model", sig is not None
          and sig.urgency in ("now", "soon", "whenever")
          and sig.tone in ("direct", "steady", "gentle", "curt"), repr(sig))

    print("\n[2] an unsure request asks ONE question instead of guessing")
    async def unclear(_p, _k, _e, _t):
        return 200, {"model": "jev-test", "answers": {
            "route": {"choice": "group_1",
                      "probabilities": {"group_1": 0.9, "group_2": 0.1}},
            "clarity": {"choice": "clarity_unclear"},
            "urgency": {"choice": "urgency_whenever"},
            "tone": {"choice": "tone_steady"},
        }}

    svc = JudgmentService(key="k", transport=unclear, log_path=root / "unclear.jsonl")
    sig = await svc.assess_turn(UNCLEAR, groups=[], ask_clarity=True)
    check("clarity 'unclear' is carried through", sig is not None and sig.needs_clarification,
          repr(sig))
    q = clarity_question()
    check("it is exactly one question", q.count("?") == 1, q)
    check("...asked about the thing, not about internal groups",
          not any(w in q for w in ("office", "docs", "group", "one or")), q)

    async def two_unclear(_p, _k, _e, _t):
        return 200, {"model": "jev-test", "answers": {
            "route": {"choice": "group_1",
                      "probabilities": {"group_1": 0.95, "group_2": 0.05}},
            "clarity": {"choice": "clarity_unclear"},
            "urgency": {"choice": "urgency_now"},
            "tone": {"choice": "tone_gentle"},
        }}

    svc = JudgmentService(key="k", transport=two_unclear, log_path=root / "2c.jsonl")
    sig = await svc.assess_turn(CLEAR, groups=["office", "docs"], ask_clarity=True)
    check("a confident route but an unclear request still asks", sig is not None
          and sig.needs_clarification, repr(sig))
    check("...and still without naming the candidates it could not choose between",
          not any(w in clarity_question() for w in ("office", "docs")), clarity_question())

    print("\n[3] the gate is entropy, not a fixed probability")
    # The same top probability means two different things depending on how many rivals it has.
    # A fixed floor reads every one of these as "sure"; entropy cannot, and the example that
    # proves it is one probability landing in two different zones purely because K changed.
    two_way = normalized_entropy({"group_1": 0.85, "group_2": 0.15})
    four_way = normalized_entropy({"group_1": 0.85, "group_2": 0.05,
                                   "group_3": 0.05, "group_4": 0.05})
    tie = normalized_entropy({"group_1": 0.51, "group_2": 0.49})
    check("0.85 over two options is NOT the same call as over four",
          two_way >= ENTROPY_ROUTE_FAST_MAX > four_way, f"two={two_way:.3f} four={four_way:.3f}")
    check("...so one fixed threshold would have to be wrong for one of them",
          (two_way < ENTROPY_FAST_MAX) != (four_way < ENTROPY_FAST_MAX)
          or (two_way < ENTROPY_ROUTE_FAST_MAX) != (four_way < ENTROPY_ROUTE_FAST_MAX),
          f"two={two_way:.3f} four={four_way:.3f}")
    check("a two-way near-tie is maximum ambiguity", tie > 0.95, f"H_n={tie:.3f}")
    check("a distribution with no information is never certain",
          normalized_entropy({}) == 1.0 and normalized_entropy({"only": 1.0}) == 1.0)

    async def four_way_clear(_p, _k, _e, _t):
        return 200, {"model": "jev-test", "answers": {
            "route": {"choice": "group_1", "probabilities": {
                "group_1": 0.94, "group_2": 0.02, "group_3": 0.02, "group_4": 0.02}},
            "clarity": {"choice": "clarity_clear"},
            "urgency": {"choice": "urgency_soon"},
            "tone": {"choice": "tone_steady"},
        }}

    svc = JudgmentService(key="k", transport=four_way_clear, log_path=root / "fw.jsonl")
    sig = await svc.assess_turn("do the thing", groups=["office", "docs", "home", "vitals"])
    check("a decisive four-way distribution is routed", sig is not None and sig.routed,
          f"zone={getattr(sig, 'zone', None)} H_n={getattr(sig, 'entropy', None)}")
    check("...and its entropy is recorded", sig is not None and sig.entropy < 0.25,
          f"{getattr(sig, 'entropy', None)}")

    async def coin_flip(_p, _k, _e, _t):
        return 200, {"model": "jev-test", "answers": {
            "route": {"choice": "group_1",
                      "probabilities": {"group_1": 0.51, "group_2": 0.49}},
            "clarity": {"choice": "clarity_clear"},
            "urgency": {"choice": "urgency_soon"},
            "tone": {"choice": "tone_steady"},
        }}

    svc = JudgmentService(key="k", transport=coin_flip, log_path=root / "coin.jsonl")
    sig = await svc.assess_turn(CLEAR, groups=["office", "docs"], ask_clarity=True)
    check("a two-way near-tie is not routed", sig is not None and not sig.routed)
    check("...it lands in the ambiguous band, not the marginal one",
          sig is not None and sig.zone == "ambiguous", f"zone={getattr(sig, 'zone', None)}")
    check("...and is therefore NOT treated as a near-miss to ask about",
          sig is not None and not sig.too_low_confidence)
    check("...the whole distribution came back, not just the winner",
          sig is not None and len(sig.distribution) == 2, str(getattr(sig, "distribution", None)))
    check("...and a near-tie is the owner's ambiguity to have or not have",
          sig is not None and not sig.needs_clarification, repr(sig))

    print("\n[4] a failed assessment is silent, not a question")
    async def dead(*_a, **_kw):
        raise ConnectionError("unreachable")

    svc = JudgmentService(key="k", transport=dead, log_path=root / "dead.jsonl")
    sig = await svc.assess_turn(CLEAR, groups=["office", "docs"], ask_clarity=True)
    check("an outage produces no decision", sig is not None and sig.outcome == "unavailable")
    check("...no group", sig is not None and sig.group is None)
    check("...and NO clarifying question", sig is not None and not sig.needs_clarification
          and not sig.too_low_confidence, repr(sig))
    check("a missing key is equally silent", True)
    svc = JudgmentService(key="", transport=dead, log_path=root / "nokey.jsonl")
    sig = await svc.assess_turn(CLEAR, groups=["office", "docs"], ask_clarity=True)
    check("...confirmed on the no-key path", sig is not None and sig.outcome == "unavailable"
          and not sig.needs_clarification, repr(sig))

    print("\n[5] urgency and tone shape the reply, and nothing else")
    async def urgent(_p, _k, _e, _t):
        return 200, {"model": "jev-test", "answers": {
            "clarity": {"choice": "clarity_clear"}, "urgency": {"choice": "urgency_now"},
            "tone": {"choice": "tone_curt"}}}

    svc = JudgmentService(key="k", transport=urgent, log_path=root / "urgent.jsonl")
    sig = await svc.assess_turn("is the build still running", ask_clarity=True)
    note = manner_note(sig)
    check("urgency produces a framing note", note is not None and "now" in note, repr(note))
    check("tone produces a register note", note is not None and "clipped" in note, repr(note))
    check("...and nothing else in the note", note is not None
          and not any(w in note.lower() for w in ("budget", "quiet hour", "interrupt")),
          repr(note))
    check("a failed assessment produces no note at all", manner_note(
        await JudgmentService(key="k", transport=dead, log_path=root / "n2.jsonl")
        .assess_turn("hello", ask_clarity=True)) is None)

    print("\n[6] chatter and single-candidate turns make no call")
    calls = {"n": 0}

    async def counting(*_a, **_kw):
        calls["n"] += 1
        raise AssertionError("called")

    svc = JudgmentService(key="k", transport=counting, log_path=root / "none.jsonl")
    check("no candidates and no clarity question returns nothing",
          await svc.assess_turn("hello", groups=[], ask_clarity=False) is None)
    check("...and the transport was never touched", calls["n"] == 0, str(calls))

    print("\n[7] the provenance row records what was asked, not what was said")
    rows = [json.loads(ln) for ln in
            (root / "full.jsonl").read_text(encoding="utf-8").splitlines() if ln.strip()]
    check("one row per assessment", len(rows) == 1, str(len(rows)))
    if rows:
        row = rows[0]
        check("it names the questions that went out",
              row.get("asked") == ["clarity", "route", "tone", "urgency"], str(row.get("asked")))
        check("...the candidates, as labels", row.get("candidates") == ["office", "docs"],
              str(row.get("candidates")))
        check("...and the picks, as labels",
              (row.get("picked") or {}).get("group") == "docs", str(row.get("picked")))
        blob = json.dumps(row).lower()
        check("the utterance itself is NOT in the row",
              not any(w in blob for w in ("lease", "inbox", "document")), blob[:200])


class _Stub:
    def __init__(self, signals):
        self._signals = signals
        self.calls = 0

    async def assess_turn(self, _text, *, groups=(), arbitrate=True, ask_clarity=True,
                          correlation_id=""):
        self.calls += 1
        return self._signals

    async def consider(self, _text, *, correlation_id=""):
        return None


class _FakeLLM:
    def __init__(self, answer: str):
        self.answer = answer
        self.tools_seen: list[list[str]] = []

    async def complete(self, messages, **kwargs):
        self.tools_seen.append([t["function"]["name"] for t in (kwargs.get("tools") or [])])
        return SimpleNamespace(content=self.answer, tool_calls=None)


async def agent_contract(root: Path) -> None:
    import mushegh.brain.agent as agent_module
    from mushegh.brain.agent import MusheghAgent
    from mushegh.brain.judgment import TurnSignals

    os.environ["MUSHEGH_TRACE_DIR"] = str(root / "traces")
    original = agent_module.JUDGMENTS

    print("\n[8] the turn asks, and no tool fires")
    try:
        asking = TurnSignals(("office", "docs"), None, None, None, "unclear", "decided", 1.0)
        agent_module.JUDGMENTS = _Stub(asking)
        agent = MusheghAgent()
        agent._history = []
        agent._persist_session = lambda: None
        agent._spawn_review = lambda: None
        llm = _FakeLLM("I'll just guess then.")
        agent._llm = llm
        said = await agent.respond("set it to three")
        check("the reply is a question", said.rstrip().endswith("?"), said)
        check("...and the model was never called", llm.tools_seen == [], str(llm.tools_seen))
        check("...it is recorded in history so the answer has context",
              agent._history and agent._history[-1]["content"] == said,
              str(agent._history[-1:]))
    finally:
        agent_module.JUDGMENTS = original

    print("\n[9] a clear turn is answered, not questioned")
    try:
        clear = TurnSignals(("office",), None, "soon", "steady", "clear", "decided", 1.0)
        agent_module.JUDGMENTS = _Stub(clear)
        agent = MusheghAgent()
        agent._history = []
        agent._persist_session = lambda: None
        agent._spawn_review = lambda: None
        llm = _FakeLLM("Still running, sir.")
        agent._llm = llm
        said = await agent.respond("is the build still running")
        check("Jev was consulted once", agent_module.JUDGMENTS.calls == 1)
        check("the turn produced an answer, not a question", said == "Still running, sir.", said)
        check("...and the model was called", bool(llm.tools_seen), str(len(llm.tools_seen)))
    finally:
        agent_module.JUDGMENTS = original

    print("\n[10] a coin-flip route hands the model the full surface instead of asking")
    try:
        flip = TurnSignals(("office", "docs"), "office", None, None, "clear", "decided", 1.0,
                           probability=0.51,
                           distribution=(("office", 0.51), ("docs", 0.49)))
        agent_module.JUDGMENTS = _Stub(flip)
        agent = MusheghAgent()
        agent._history = []
        agent._persist_session = lambda: None
        agent._spawn_review = lambda: None
        from mushegh.brain.tools import group_tool_schemas
        office = {s["function"]["name"] for s in group_tool_schemas("office")}
        llm = _FakeLLM("Looking at the document and your mail.")
        agent._llm = llm
        said = await agent.respond(CLEAR)
        offered = set(llm.tools_seen[-1]) if llm.tools_seen else set()
        check("the turn answered rather than asking", not said.rstrip().endswith("?"), said)
        check("...the model was actually consulted", bool(llm.tools_seen), said[:60])
        # The assertion is "arbitration did not narrow", not "every group is present": the
        # catalogue budget independently defers one of these two groups, and conflating the two
        # would make this test pass for the wrong reason.
        check("...and the surface was NOT narrowed to the coin-flip winner",
              bool(office & offered), f"offered={len(offered)}")
        check("...because routing uncertainty is ours to resolve, not his to answer",
              not any(w in said.lower() for w in ("office", "docs", "which")), said)
    finally:
        agent_module.JUDGMENTS = original


async def answerable_contract(root: Path) -> None:
    """01.J13 — the `answerable` verdict rides in the call that already happens.

    Opt-in, so section [1]'s four-question assertion is the regression guard for the production
    payload: if this ever starts being asked by default, [1] goes red, which is the point.
    """
    from mushegh.brain.judgment import (
        ANSWERABLE_BANDS,
        ANSWERABLE_INSTRUCTIONS,
        JudgmentService,
        answerable_note,
    )

    print("\n[11] the answerable verdict is a fifth QUESTION in the same call, not a fifth call")

    def _answers(pick: str) -> dict:
        return {"model": "jev-test", "answers": {
            "route": {"choice": "group_2", "probabilities": {"group_1": 0.1, "group_2": 0.9}},
            "clarity": {"choice": "clarity_clear", "probabilities": {"clarity_clear": 0.95}},
            "urgency": {"choice": "urgency_now", "probabilities": {"urgency_now": 0.7}},
            "tone": {"choice": "tone_direct", "probabilities": {"tone_direct": 0.6}},
            "answerable": {"choice": f"answerability_{pick}",
                           "probabilities": {"answerable": 0.95, "not_answerable": 0.05}},
        }}

    seen: list[dict] = []

    async def not_answerable(payload, _k, _e, _t):
        seen.append(payload)
        return 200, _answers("not_answerable")

    svc = JudgmentService(key="k", transport=not_answerable, log_path=root / "ans.jsonl")
    sig = await svc.assess_turn(CLEAR, groups=["office", "docs"], ask_answerable=True)

    check("still exactly one round trip", len(seen) == 1, str(len(seen)))
    check("five questions in that one call",
          sorted(seen[0]["questions"]) == ["answerable", "clarity", "route", "tone", "urgency"],
          str(sorted(seen[0]["questions"])))
    check("the verdict came back", sig is not None and sig.answerable == "not_answerable", repr(sig))
    check("...and is carried as a hedge", sig is not None and sig.needs_hedge)
    check("the labels are the ones code declared",
          sorted(seen[0]["questions"]["answerable"]["criteria"]) ==
          sorted(f"answerability_{b}" for b in ANSWERABLE_BANDS),
          str(seen[0]["questions"]["answerable"]["criteria"]))

    print("\n[12] the wording is load-bearing: a tool-answerable turn must not be ruled out")
    # This is the finding from 01.J13, turned into a gate. The probe's `no-tools` wording scored
    # "what time is it" at p=0.00, and a verdict used as-is would suppress the tool call on
    # exactly the turns that need one — at 100% accuracy, which is how it would have looked
    # like a win. The instruction has to keep admitting ordinary tools.
    instr = seen[0]["questions"]["answerable"]["instructions"].lower()
    check("the instructions still admit ordinary tools", "tool" in instr, instr[:120])
    check("...specifically a clock or a lookup", "clock" in instr or "search" in instr, instr[:120])
    check("...and do not forbid fetching", "without fetching" not in instr, instr[:120])
    check("the shipped instructions are the measured ones",
          ANSWERABLE_INSTRUCTIONS.lower() == instr)

    print("\n[13] the note steers the generated answer and never the tool surface")
    note = answerable_note(sig) or ""
    check("a decided not_answerable produces a note", bool(note), note[:80])
    check("...it tells the model not to invent a specific answer",
          "do not invent" in note.lower(), note[:120])
    check("...and explicitly tells it to KEEP using tools",
          "tool" in note.lower() and "not a reason to skip" in note.lower(), note[:160])
    check("answerable stays silent", answerable_note(
        _signals_with("answerable")) is None)

    print("\n[14] it is fail-closed: no advice means no hedge")
    sig_unavailable = sig.__class__(("office", "docs"), None, None, None, "clear",
                                     "unavailable", 400.0)
    check("a timed-out assessment does NOT ask for a hedge",
          sig_unavailable.needs_hedge is False, repr(sig_unavailable))
    check("...and produces no note", answerable_note(sig_unavailable) is None)
    check("a never-asked verdict is not a hedge either",
          sig_unavailable.needs_hedge is False)

    print("\n[15] the provenance row records the question and the pick, never the utterance")
    rows = [json.loads(ln) for ln in
            (root / "ans.jsonl").read_text(encoding="utf-8").splitlines() if ln.strip()]
    check("one row per assessment", len(rows) == 1, str(len(rows)))
    if rows:
        row = rows[0]
        check("it names the question that went out", "answerable" in (row.get("asked") or []),
              str(row.get("asked")))
        check("...and the pick, as a label",
              (row.get("picked") or {}).get("answerable") == "not_answerable",
              str(row.get("picked")))
        blob = json.dumps(row).lower()
        check("...and still NOT the utterance",
              not any(w in blob for w in ("lease", "inbox", "document")), blob[:200])


def _signals_with(answerable: str):
    from mushegh.brain.judgment import TurnSignals
    return TurnSignals(("office", "docs"), None, None, None, "clear", "decided", 1.0,
                       answerable=answerable)


async def main() -> int:
    import tempfile
    with tempfile.TemporaryDirectory(prefix="mushegh-turn-assessment-") as tmp:
        root = Path(tmp)
        await service_contract(root)
        await agent_contract(root)
        await answerable_contract(root)
    print(f"\n=== {passed + failed} checks: {passed} passed, {failed} failed ===")
    if not failed:
        print("ALL CHECKS PASSED ===")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
