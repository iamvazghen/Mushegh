"""Jev arbitrates the tool choice the deterministic router could not make (01.R6).

An utterance can match two lazy groups at once — "draft a reply to that email about the
document" hits `office` and `docs`. Until now every matched group was armed and the
generative model picked among ~60 advertised tools. That is the decision this test covers.

The shape that makes it safe to put on the hot path:

  * the **candidates come from code** (the trigger match), never from a model, so a model
    choosing among them cannot widen the surface — only narrow it;
  * **fewer than two candidates is not a decision**, so the ordinary turn costs no call at all;
  * the **budget is 400ms**, far below the service timeout, because a laptop turn is budgeted
    under 300ms (D-35) and an arbitration arriving late is worse than none;
  * **failure is silent** — the deterministic candidates stand, which is a real answer.

And the asymmetry that is easy to get wrong: the explicit two-option question asks the OWNER
on outage, while arbitration keeps every candidate. Conflating them turns "the model was
unsure" into "the model decided", so both directions are asserted below.

Hermetic: the transport is replaced. No network, no key, no LLM.

    uv run python bench/test_jev_tool_arbitration.py
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
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


# A real ambiguity, and a rare one. Found by searching the shipped triggers for an utterance that
# is genuinely unresolved: it matches two lazy groups (`office` on "inbox", `docs` on "document"),
# is not a compound request, does not fire the B1 single-tool router, and has both groups' tools
# inside the catalogue budget. Anything looser would have made this test decorative — an utterance
# the deterministic path already resolves needs no arbitration, and a fixture where only one group
# fits the budget would be arbitrating between a choice and a deferral.
AMBIGUOUS = "my inbox has something about the lease document"


class _Resp:
    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


async def service_contract(root: Path) -> None:
    from afon.brain.judgment import JudgmentService
    from afon.brain.tools import groups_for_text
    from afon.brain.intent_router import _is_multi_intent, forced_tools

    print("[0] the fixture is a real ambiguity, or this test is testing nothing")
    groups = groups_for_text(AMBIGUOUS)
    check("the utterance matches at least two groups", len(groups) >= 2, str(sorted(groups)))
    check("...and is not a multi-intent turn", not _is_multi_intent(AMBIGUOUS), AMBIGUOUS)
    check("...and the single-tool router does not already resolve it",
          not forced_tools(AMBIGUOUS), str(forced_tools(AMBIGUOUS)))

    print("\n[1] fewer than two candidates is not a decision, and costs no call")
    calls = {"n": 0}

    async def must_not_call(*_a, **_kw):
        calls["n"] += 1
        raise AssertionError("transport called for a non-decision")

    svc = JudgmentService(key="k", transport=must_not_call, log_path=root / "none.jsonl")
    check("a single candidate returns nothing", await svc.arbitrate("turn the lamp on", ["home"]) is None)
    check("no candidates return nothing", await svc.arbitrate("hello", []) is None)
    check("duplicates collapse to one candidate",
          await svc.arbitrate("x", ["home", "home", "home"]) is None)
    check("the transport was never touched", calls["n"] == 0, str(calls))

    print("\n[2] a real decision: one call, and a minimal payload")
    seen: list[dict] = []

    async def ok_transport(payload, _key, _endpoint, _timeout):
        seen.append(payload)
        return 200, {"model": "jev-test", "answers": {"route": {
            "choice": "group_1", "probabilities": {"group_1": 0.93, "group_2": 0.07},
            "confidence": 0.9}}}

    svc = JudgmentService(key="k", transport=ok_transport, log_path=root / "ok.jsonl")
    verdict = await svc.arbitrate(AMBIGUOUS, ["office", "docs"], correlation_id="turn-1")
    check("exactly one call was made", len(seen) == 1, str(len(seen)))
    check("the verdict carries the winner", verdict is not None and verdict.arbitrated
          and verdict.winner == "office", repr(verdict))
    check("...and the candidate set it chose from", verdict is not None
          and verdict.candidates == ("office", "docs"), repr(verdict))
    if seen:
        body = seen[0]
        question = body["state"]["question"]
        criteria = body["questions"]["route"]["criteria"]
        check("the options are the group names, with stable ids",
              sorted(criteria) == ["group_1", "group_2"] and
              sorted(criteria.values()) == ["docs", "office"], json.dumps(criteria))
        check("the question is the utterance, not the history", question == AMBIGUOUS, question)
        check("only the route question is asked on this path",
              sorted(body["questions"]) == ["route"], str(sorted(body["questions"])))
        blob = json.dumps(body).lower()
        leaked = [w for w in ("history", "memory", "recall", "vault", "token", "biometric",
                              "who am i", "earlier") if w in blob]
        check("nothing else rode along outbound", not leaked, str(leaked))

    print("\n[3] the budget is real, and a late answer is discarded")
    async def slow(_p, _k, _e, _t):
        await asyncio.sleep(2.0)
        return 200, {"model": "jev-test", "answers": {"route": {"choice": "group_1"}}}

    log = root / "timeout.jsonl"
    svc = JudgmentService(key="k", transport=slow, log_path=log)
    started = time.perf_counter()
    late = await svc.arbitrate(AMBIGUOUS, ["office", "docs"], timeout_s=0.4)
    elapsed = (time.perf_counter() - started) * 1000
    check("it returned inside the cap", elapsed < 900, f"{elapsed:.0f}ms")
    check("...keeping every candidate", late is not None and late.winner is None
          and late.candidates == ("office", "docs"), repr(late))
    check("...and reporting the timeout as unavailable", late is not None
          and late.outcome == "unavailable", repr(late))
    rows = [json.loads(ln) for ln in log.read_text(encoding="utf-8").splitlines() if ln.strip()]
    timed_out = [r for r in rows if r.get("kind") == "turn_assessment"
                 and r.get("fallback") == "deterministic"]
    check("the timeout is on the record, not a hole in it", len(timed_out) == 1,
          f"{len(timed_out)} rows of {len(rows)}")
    check("...naming the deterministic fallback", bool(timed_out) and
          not timed_out[0].get("selected_id"), json.dumps(timed_out[:1]))

    print("\n[4] an outage, a malformed body and a missing key all leave the candidates standing")
    async def boom(*_a, **_kw):
        raise ConnectionError("jev unreachable")

    async def garbage(*_a, **_kw):
        return 200, {"answers": {"route": {"choice": "not_a_group"}}}

    async def must_not_call2(*_a, **_kw):
        raise AssertionError("transport called without a key")

    for name, transport in (("outage", boom), ("malformed", garbage)):
        svc = JudgmentService(key="k", transport=transport, log_path=root / f"{name}.jsonl")
        out = await svc.arbitrate(AMBIGUOUS, ["office", "docs"])
        check(f"{name} keeps both candidates", out is not None and out.winner is None
              and len(out.candidates) == 2, repr(out))
    svc = JudgmentService(key="", transport=must_not_call2, log_path=root / "nokey.jsonl")
    out = await svc.arbitrate(AMBIGUOUS, ["office", "docs"])
    check("a missing key never reaches transport and keeps both candidates",
          out is not None and out.winner is None and out.outcome == "unavailable", repr(out))
    svc = JudgmentService(key="k", enabled=False, transport=must_not_call2,
                          log_path=root / "off.jsonl")
    out = await svc.arbitrate(AMBIGUOUS, ["office", "docs"])
    check("disabled arbitration is reported as disabled, not decided",
          out is not None and out.outcome == "disabled" and out.winner is None, repr(out))


class _StubArbitrator:
    """Stands in for JUDGMENTS on the full turn: a turn assessment plus a call counter."""

    def __init__(self, group: str | None):
        from afon.brain.judgment import TurnSignals
        # A distribution, not just a probability: the gate reads entropy over the whole
        # distribution, so a stub that supplies only a top number is indistinguishable from a
        # model that had no opinion at all.
        distribution = (("office", 0.93), ("docs", 0.07)) if group else \
                       (("office", 0.51), ("docs", 0.49))
        self._signals = TurnSignals(("office", "docs"), group, None, None, "clear",
                                    "decided" if group else "unavailable", 1.0,
                                    probability=0.93, model="jev-test",
                                    distribution=distribution)
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

    @property
    def widest(self) -> set[str]:
        """Every tool the model was offered on any call this turn.

        A turn may call the model more than once, and a later pass can carry a narrower list than
        the turn actually started with. Asserting on the last call alone would let a regression
        hide behind whichever pass happened to be smallest.
        """
        return set().union(*(set(call) for call in self.tools_seen)) if self.tools_seen else set()


async def agent_contract(root: Path) -> None:
    import afon.brain.agent as agent_module
    from afon.brain.agent import AfonAgent
    from afon.brain.tools import core_tool_schemas, group_tool_schemas, groups_for_text

    os.environ["AFON_TRACE_DIR"] = str(root / "traces")
    groups = sorted(groups_for_text(AMBIGUOUS))
    winner, loser = (groups[0], groups[1])
    core_names = {s["function"]["name"] for s in core_tool_schemas()}
    # Only tools that belong to the losing group ALONE can prove it was not advertised: several
    # group tools (send_email and friends) are also core, so they are on the turn either way and
    # would make this assertion pass for the wrong reason.
    home_names = {s["function"]["name"] for s in group_tool_schemas(winner)} - core_names
    away_names = {s["function"]["name"] for s in group_tool_schemas(loser)} - home_names - core_names
    # A follow-up phrase built from a trigger word that genuinely re-arms the losing group.
    follow_phrase = {"office": "check my email again", "docs": "read the document again"}

    print(f"\n[5] the winner is the only group armed (winner={winner}, loser={loser})")
    agent = AfonAgent()
    base = {s["function"]["name"] for s in agent._tools_for_turn(AMBIGUOUS)}
    narrowed = {s["function"]["name"] for s in agent._tools_for_turn(AMBIGUOUS, preferred_group=winner)}
    check("the losing group has tools of its own to test with", bool(away_names),
          f"loser={loser} exclusive={sorted(away_names)[:4]}")
    check("the winning group's tools are advertised", bool(home_names & narrowed),
          f"missing={sorted(home_names - narrowed)[:4]}")
    check("the losing group's tools are not", not (away_names & narrowed),
          f"leaked={sorted(away_names & narrowed)[:4]}")
    # The unarbitrated turn for this utterance is NOT both groups: the catalogue budget
    # (11000, of which core already spends 7418) fits office but defers docs. So arbitration is
    # not a cosmetic narrowing here — it is what decides which of the two the owner can reach at
    # all. Asserting that is the point; asserting "both were available before" would be a lie
    # about the budget, and a test that states a lie is worse than no test.
    check("without arbitration the winner's group was NOT reachable",
          not (home_names & base),
          f"baseline offered {sorted(home_names & base)[:3]}")
    check("...and arbitration is what changes that", bool(home_names & narrowed))
    check("...within the catalogue budget either way",
          len(narrowed) <= len(base) + len(home_names), f"{len(narrowed)} vs {len(base)}")

    print("\n[6] a losing group is not disabled — its own trigger still arms it")
    follow = {s["function"]["name"] for s in agent._tools_for_turn(follow_phrase[loser])}
    check("the loser returns on its own turn", bool(away_names & follow),
          f"{sorted(away_names & follow)[:3]} or none of {sorted(away_names)[:3]}")

    print("\n[7] the turn itself: Jev picks, the model only phrases")
    original = agent_module.JUDGMENTS
    try:
        agent_module.JUDGMENTS = _StubArbitrator(winner)
        live = AfonAgent()
        live._history = []
        live._persist_session = lambda: None
        live._spawn_review = lambda: None
        llm = _FakeLLM("Done, sir.")
        live._llm = llm
        said = await live.respond(AMBIGUOUS)
        check("Jev was consulted once", agent_module.JUDGMENTS.calls == 1,
              str(agent_module.JUDGMENTS.calls))
        check("the model was called and answered", bool(llm.tools_seen) and bool(said), said[:60])
        advertised = llm.widest
        check("the model only ever saw the winning group's tools",
              bool(home_names & advertised) and not (away_names & advertised),
              f"offered={len(advertised)} leaked={sorted(away_names & advertised)[:4]}")
    finally:
        agent_module.JUDGMENTS = original

    print("\n[8] arbitration failing changes nothing the owner can see")
    baseline = AfonAgent()
    base_surface = {s["function"]["name"] for s in baseline._tools_for_turn(AMBIGUOUS)}
    original = agent_module.JUDGMENTS
    try:
        agent_module.JUDGMENTS = _StubArbitrator(None)
        live = AfonAgent()
        live._history = []
        live._persist_session = lambda: None
        live._spawn_review = lambda: None
        llm = _FakeLLM("Done, sir.")
        live._llm = llm
        said = await live.respond(AMBIGUOUS)
        check("the turn still completes", bool(said), said[:60])
        # The precise claim: a failed arbitration is indistinguishable from never having tried.
        # Not "more tools" — the SAME tools the deterministic path would have offered.
        check("...offering exactly the unarbitrated surface", llm.widest == base_surface,
              f"extra={sorted(llm.widest - base_surface)[:4]} "
              f"missing={sorted(base_surface - llm.widest)[:4]}")
        check("...and no mention of arbitration to the owner",
              not any(w in said.lower() for w in ("jev", "arbitrat", "confidence")),
              said[:80])
    finally:
        agent_module.JUDGMENTS = original

    print("\n[9] the explicit two-option path is untouched: outage asks the OWNER")
    original = agent_module.JUDGMENTS
    try:
        class _AskingStub(_StubArbitrator):
            async def consider(self, _text, *, correlation_id=""):
                from afon.brain.judgment import DecisionVerdict
                return DecisionVerdict(
                    request_id="r", correlation_id=correlation_id, kind="explicit_options",
                    option_ids=("option_1", "option_2"), selected_id=None, selected_text=None,
                    probability=None, confidence=None, model="", latency_ms=1.0,
                    outcome="unavailable", fallback="ask_owner", error="http_429")
        agent_module.JUDGMENTS = _AskingStub(None)
        live = AfonAgent()
        live._history = []
        live._persist_session = lambda: None
        live._spawn_review = lambda: None
        llm = _FakeLLM("Choose blue")
        live._llm = llm
        held = await live.respond("Should I take the train or drive?")
        check("an outage asks rather than chooses", "haven't chosen" in held and "retry" in held, held)
        check("...and never invokes the generative model", llm.tools_seen == [], str(llm.tools_seen))
    finally:
        agent_module.JUDGMENTS = original


async def main() -> int:
    import tempfile
    with tempfile.TemporaryDirectory(prefix="afon-jev-arbitration-") as tmp:
        root = Path(tmp)
        await service_contract(root)
        await agent_contract(root)
    print(f"\n=== {passed + failed} checks: {passed} passed, {failed} failed ===")
    if not failed:
        print("ALL CHECKS PASSED ===")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

