"""P1 #4 — resilience under fault injection.

Unattended, things break: a model rate-limits, a cached provider raises, the scheduler DB is unwritable, a tool
throws. None of these may wedge or crash the brain — each must yield a *speakable* outcome and a
still-running system. This injects each fault and asserts graceful behaviour.

Hermetic: no real network. Fake LLM/responses; a raising factory; an unwritable jobstore path.

    uv run python bench/test_resilience.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

passed = failed = 0


def check(name: str, ok: bool, detail: str = "") -> None:
    global passed, failed
    if ok:
        passed += 1
        print(f"  [PASS] {name}")
    else:
        failed += 1
        print(f"  [FAIL] {name}  {detail}")


async def test_llm_failover() -> None:
    print("[1] LLM primary fails -> the chain answers via a fallback (no crash)")
    from afon.brain.llm import LLMClient

    llm = LLMClient()
    # Two models in the chain; the first returns a choiceless 200 (proxy error), the second answers.
    llm._chain = ["primary-broken", "fallback-good"]

    async def fake_create(**kwargs):
        if kwargs["model"] == "primary-broken":
            return SimpleNamespace(choices=[], error="simulated outage")  # -> _EmptyResponse failover
        msg = SimpleNamespace(content="Yerevan, sir.", tool_calls=None)
        return SimpleNamespace(choices=[SimpleNamespace(message=msg)])

    llm._default.chat.completions.create = fake_create
    msg = await llm.complete([{"role": "user", "content": "capital of Armenia?"}])
    check("a fallback model answered after the primary failed", msg.content == "Yerevan, sir.")


async def test_cache_fails_open() -> None:
    print("\n[2] the cache never becomes the failure — a miss, or an error, just runs the work")
    from afon.brain.cache import Cache

    # O3.2 dropped the Redis tier (Jev p=0.98), so "Redis is down" is no longer a reachable state.
    # The failure mode that remains is the one that always mattered more: the thing BEHIND the cache
    # blowing up. Replaced rather than deleted - dropping a resilience check outright would have
    # quietly reduced coverage while the suite total merely went down by one.
    cache = Cache()

    async def factory() -> str:
        return "fresh-value"

    val = await cache.cached("ns", "k", ttl=60, factory=factory)
    check("cached() returns the factory value on a cold miss", val == "fresh-value")
    check("the backend is named, so self-health can report it", cache.backend == "memory", cache.backend)
    again = await cache.cached("ns", "k", ttl=60, factory=lambda: _should_not_run())
    check("second lookup is an in-process hit", again == "fresh-value")

    async def boom() -> str:
        raise RuntimeError("provider exploded")

    try:
        await cache.cached("ns", "other", ttl=60, factory=boom)
        check("a raising factory propagates rather than being swallowed", False, "no exception")
    except RuntimeError:
        check("a raising factory propagates rather than being swallowed as a cache hit", True)
    check("and nothing was cached for it", await cache.get("ns", "other") is None)


def _should_not_run():  # pragma: no cover - only called if the cache failed to store
    raise AssertionError("factory should not run on a cache hit")


async def test_scheduler_failure() -> None:
    print("\n[3] Scheduler backend fails -> set_reminder degrades to a spoken error, brain survives")
    import afon.brain.tools.reminders as rem

    class _BrokenScheduler:
        def add_reminder(self, *a, **kw):
            raise OSError("jobstore unwritable")

    saved = rem.SCHEDULER
    rem.SCHEDULER = _BrokenScheduler()  # simulate the jobstore/scheduler being unavailable
    try:
        out = await rem.set_reminder({"message": "drink water", "in_minutes": 5})
        check("set_reminder returned a spoken string (no exception)", isinstance(out, str) and bool(out))
        check("it reads as a graceful failure, not a stack trace",
              any(w in out.lower() for w in ("trouble", "error", "couldn't", "problem")), out)
    except Exception as e:  # noqa: BLE001
        check("set_reminder did not raise", False, f"{type(e).__name__}: {e}")
    finally:
        rem.SCHEDULER = saved


async def test_tool_raises_in_turn() -> None:
    print("\n[4] A tool raises mid-turn -> the turn returns a safe reply (no crash)")
    from afon.brain.agent import AfonAgent

    agent = AfonAgent()

    async def boom(_args: dict) -> str:
        raise RuntimeError("kaboom")

    agent._registry["boom"] = boom

    calls = {"n": 0}

    async def fake_complete(messages, tools=None, temperature=0.6, tool_choice="auto", skip_primary=False):
        calls["n"] += 1
        if calls["n"] == 1:
            tc = SimpleNamespace(id="c1", function=SimpleNamespace(name="boom", arguments="{}"))
            return SimpleNamespace(content="", tool_calls=[tc])
        # Second pass (after the tool-error result is fed back): a normal spoken reply.
        return SimpleNamespace(content="That one failed, sir, but I'm still here.", tool_calls=None)

    agent._llm = SimpleNamespace(complete=fake_complete)
    try:
        reply = await agent.respond("do the boom thing")
        check("respond() returned a spoken reply instead of raising", bool(reply), repr(reply))
        check("history stayed intact (user + assistant)",
              agent._history[-2]["role"] == "user" and agent._history[-1]["role"] == "assistant")
    except Exception as e:  # noqa: BLE001
        check("respond() did not propagate the tool exception", False, f"{type(e).__name__}: {e}")


async def test_degraded_still_answers() -> None:
    """23.R2 — with no LLM reachable, time, reminders and status are still answerable.

    `shared/degraded.py` has always PROMISED this: its brain-down mode says "I can still hear you and
    answer simple things from here." Until now that was a claim with no code behind it — only time and
    date were local. A declared mode that overstates what is kept is worse than no mode, because it is
    the sentence he plans around.
    """
    print("\n[5] degraded: no LLM at all, yet time, reminders and status still answer")
    import time as _time

    from afon.edge import degraded_answers as da
    from afon.edge.reflexes import reflex_answer
    from afon.shared import degraded

    # time — the one that already worked, asserted here so the trio is covered in one place
    check("time is answered with no brain and no model",
          "It's" in (reflex_answer("what time is it") or ""), reflex_answer("what time is it"))

    # status — from the declared matrix, not from a model
    st = da.answer("what's your status", mode_name=degraded.BRAIN_DOWN)
    check("status is answered while brain-down", bool(st), str(st))
    check("...and names what is LOST from the matrix",
          st is not None and degraded.MATRIX[degraded.BRAIN_DOWN].lost in st)
    check("...and what is KEPT, which is the half he can act on",
          st is not None and degraded.MATRIX[degraded.BRAIN_DOWN].kept in st)
    net = da.answer("what is broken", mode_name=degraded.NETWORK_DOWN)
    check("a different mode gives a different answer, not one generic line",
          net is not None and net != st)

    # reminders — from the digest the brain handed over while it still could
    digest = {"generated": _time.time() - 2400,
              "reminders": [{"name": "vet call", "next": "Mon 09:00"}]}
    rem = da.answer("what's on today", mode_name=degraded.BRAIN_DOWN, digest=digest)
    check("reminders are answered from the cached digest", rem is not None and "vet call" in rem,
          str(rem))
    check("...and the answer STATES ITS AGE unprompted, because a stale copy is trusted",
          rem is not None and "40 minutes ago" in rem, str(rem))
    check("...and says it may be out of date", rem is not None and "out of date" in rem)
    empty = da.answer("what's on today", mode_name=degraded.BRAIN_DOWN,
                      digest={"generated": _time.time(), "reminders": []})
    check("an empty digest says 'nothing scheduled AS OF', not a bare 'nothing'",
          empty is not None and "as of" in empty.lower(), str(empty))
    none = da.answer("what are my reminders", mode_name=degraded.BRAIN_DOWN, digest=None,
                     path=Path("/nonexistent-23r2/x.json"))
    check("no cache at all admits it does not know, rather than inventing an empty list",
          none is not None and "don't know" in none, str(none))

    # the boundary: these belong to the brain when the brain is there
    check("in FULL health status goes to the brain, which knows strictly more",
          da.answer("what's your status", mode_name=degraded.FULL) is None)
    check("in FULL health reminders go to the brain too",
          da.answer("what's on today", mode_name=degraded.FULL) is None)

    # precision: a question this cannot answer WELL must fall through, not be answered from a cache
    for q in ("what time does the pharmacy close", "remind me to call the vet",
              "what's on at the cinema tonight", "what's my blood pressure"):
        check(f"falls through rather than guessing: {q!r}",
              da.answer(q, mode_name=degraded.BRAIN_DOWN, digest=digest) is None)

    # the cache round-trips on disk, so an edge restart mid-outage keeps the answer
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "d.json"
        check("digest saves", da.save([{"name": "x", "next": "Tue 08:00"}], now=1000.0, path=p))
        back = da.load(p)
        check("...and survives a restart as a plain file",
              back is not None and back["reminders"][0]["name"] == "x")
        p.write_text("{broken", encoding="utf-8")
        check("a corrupt digest reads as absent, never a crash", da.load(p) is None)

    # the routing order is the point: no model is spent on an answer that never needed one
    src = (ROOT / "src/afon/edge/remote_brain.py").read_text(encoding="utf-8")
    i_deg, i_std = src.index("_degraded_answer(text)"), src.index("_answer_local(text)")
    check("the degraded answer is tried BEFORE the LLM standby", i_deg < i_std)
    check("...and before 23.R4's queue, so trivia is answered rather than held",
          i_deg < src.index("_promise(text)"))


async def main() -> None:
    await test_llm_failover()
    await test_cache_fails_open()
    await test_scheduler_failure()
    await test_tool_raises_in_turn()
    await test_degraded_still_answers()
    print(f"\n=== {passed}/{passed + failed} checks passed ===")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
