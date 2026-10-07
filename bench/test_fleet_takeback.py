"""39.R2 — a delegation that stalls comes BACK to Afon, and is never sent twice.

The defect this closes is not a missing feature, it was a wrong answer. `delegate_to_fleet` wrapped
its work in `asyncio.wait_for(_run(), timeout_s + 15)`, and a `TimeoutError` from that wrapper fell
into a bare `except Exception`. So a **stall** — the gateway took the job and went quiet — was
handled exactly like an **outage**, and the handler for an outage does three things:

  1. **re-sends the same task** over the CLI, to the same agent, over a different transport. Safe
     after a connection failure, because nothing was ever sent. NOT safe after a stall: the first
     attempt may still be running over there, so a non-idempotent task — send this email, spawn this
     process, pay this — happens **twice**. That is a D-13 blast-radius failure caused by a timeout.
  2. **trips the WebSocket circuit breaker**, so one slow turn stops every later delegation.
  3. **reports a gateway error** to the owner, which is a different story from what happened.

What is asserted here:

  * a stall raises `FleetStalled`, a DISTINCT type, and the owner is told it stalled rather than that
    the bridge is broken
  * **the CLI fallback is NOT called** — the double-execution guard, and the reason this matters
  * **the breaker is NOT tripped** — one slow turn must not stop the next
  * the work is handed BACK: the message says it may still be running remotely and that it will not
    be re-sent without being told, which is the takeback the task asks for
  * **and, just as important, the outage path is untouched**: a real connection failure still trips
    the breaker and still retries over the CLI, because there the re-dispatch is safe. A fix that
    stopped re-dispatching everywhere would "pass" every assertion above while silently deleting the
    recovery that makes the fleet usable at all.
  * a delegation that finishes inside its budget is unaffected

Hermetic: `websockets.connect` is replaced with one that never answers, so no socket is opened and
no gateway is contacted. Everything else is patched at the module seam.

    uv run python bench/test_fleet_takeback.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
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


class _NeverAnswers:
    """An async context manager whose body waits forever. No socket, no gateway, no network."""

    def __init__(self, *_a, **_k) -> None:
        self._never = asyncio.Event()

    async def __aenter__(self):
        await self._never.wait()
        return self

    async def __aexit__(self, *_exc):
        return False

    async def recv(self):
        await self._never.wait()

    async def send(self, *_a, **_k):
        await self._never.wait()


class _RefusesNothing(_NeverAnswers):
    """The happy path's shape needs a real gateway's message-id protocol, so it is not faked here."""


def main() -> int:
    from afon.brain import fleet
    from afon.brain.fleet import FleetStalled, FleetUnavailable, delegate_to_fleet
    from afon.config import settings

    calls = {"cli": 0, "blocked": 0, "progress": []}

    async def fake_cli(task, timeout_s):
        calls["cli"] += 1
        return "cli answered"

    def fake_block(_reason):
        calls["blocked"] += 1

    def fake_reset():
        calls["blocked"] = -999

    real = {
        "cli": fleet._delegate_via_cli, "block": fleet._block_ws, "reset": fleet._reset_ws_block,
        "url": fleet._ws_url, "enabled": settings.openclaw_delegation_enabled,
        "token": settings.openclaw_token,
    }
    fleet._delegate_via_cli = fake_cli
    fleet._block_ws = fake_block
    fleet._reset_ws_block = fake_reset
    fleet._ws_url = lambda: "ws://127.0.0.1:1/never"
    settings.openclaw_delegation_enabled = True
    settings.openclaw_token = "t"

    import websockets
    real_connect = websockets.connect

    def reset() -> None:
        calls["cli"] = 0
        calls["blocked"] = 0
        calls["progress"] = []

    try:
        print("\n[1] a STALL comes back to Afon, and is not re-sent")
        websockets.connect = _NeverAnswers
        reset()

        async def stalled():
            try:
                return await delegate_to_fleet("email Anna the invoice", timeout_s=1,
                                               on_progress=calls["progress"].append)
            except FleetUnavailable as e:
                return e

        got = asyncio.run(stalled())
        check("a stall raises, so the caller can tell it from a success", isinstance(got, Exception),
              repr(got))
        check("...and it is the DISTINCT stall type, not a generic outage",
              isinstance(got, FleetStalled), type(got).__name__)
        check("THE DOUBLE-EXECUTION GUARD: the CLI fallback was NOT called", calls["cli"] == 0,
              f"the task was re-sent {calls['cli']} time(s) — it may still be running remotely")
        check("the breaker was NOT tripped by one slow turn", calls["blocked"] == 0,
              f"_block_ws called {calls['blocked']} time(s)")
        msg = str(got)
        check("the owner is told it STALLED, not that the bridge is broken",
              "did not answer" in msg and "gateway error" not in msg, msg[:120])
        check("...and that the work is back with Afon", "taken" in msg and "back" in msg, msg[:120])
        check("...including the warning that it may still be running there",
              "may still be running" in msg, msg[:160])
        check("...and that it will not be re-sent without being told",
              "without you saying so" in msg, msg[:200])
        check("the budget it waited is named, not vague", "16s" in msg, msg[:120])
        check("the owner heard a progress note explaining the takeback",
              any("twice" in p for p in calls["progress"]), str(calls["progress"]))

        print("\n[2] the OUTAGE path is untouched — the fix did not delete the recovery")
        # A connection failure means nothing was ever sent, so re-dispatching is safe. If this
        # stopped working, every assertion in [1] would still pass and the fleet would be worse.
        class _Refuses(_NeverAnswers):
            def __init__(self, *a, **k):
                super().__init__(*a, **k)

            async def __aenter__(self):
                raise ConnectionRefusedError(111, "connection refused")

        websockets.connect = _Refuses
        reset()

        async def refused():
            try:
                return await delegate_to_fleet("research the Lisbon property", timeout_s=1)
            except FleetUnavailable as e:
                return e

        got2 = asyncio.run(refused())
        check("an outage RECOVERS over the CLI rather than raising — nothing was ever sent",
              got2 == "cli answered", repr(got2)[:100])
        check("...and it is not reported as a stall, because a stall is a different event",
              not isinstance(got2, FleetStalled), type(got2).__name__)
        check("...the breaker IS tripped, because the gateway really is refusing",
              calls["blocked"] == 1, f"{calls['blocked']}")
        check("...and the CLI fallback IS still tried, because nothing was ever sent",
              calls["cli"] == 1, f"cli called {calls['cli']} time(s)")

        # ...and when the fallback ALSO fails, the owner is told both halves, not just the first.
        async def failing_cli(_task, _t):
            calls["cli"] += 1
            raise FleetUnavailable("ssh: command not found")
        fleet._delegate_via_cli = failing_cli
        reset()

        async def refused_twice():
            try:
                return await delegate_to_fleet("research the Lisbon property", timeout_s=1)
            except FleetUnavailable as e:
                return e

        got3 = asyncio.run(refused_twice())
        check("when the fallback fails too, the owner hears BOTH failures",
              isinstance(got3, FleetUnavailable) and "CLI fallback failed" in str(got3),
              str(got3)[:140])
        fleet._delegate_via_cli = fake_cli

        print("\n[3] a delegation inside its budget is unaffected — asserted at the source")
        # A live happy path is NOT exercised here. The success branch waits on `_await_response` and
        # `_collect_session` matching a real gateway's message ids, and a fake that does not
        # reproduce that shape loops forever (which it did, on the first run of this file). Inventing
        # the protocol to satisfy a test would make the test assert the mock — the same reason
        # `test_journeys.py` blocks a leg rather than faking the collector behind it. So the success
        # path is asserted structurally: the success marker is still the FIRST thing after the call,
        # and the stall clause is ordered so it can only catch a timeout.
        src = (ROOT / "src" / "afon" / "brain" / "fleet.py").read_text(encoding="utf-8")
        try_block = src[src.index("result = await asyncio.wait_for(_run()"):]
        check("the success path still resets the breaker first",
              try_block.index("_reset_ws_block()") < try_block.index("except"), "order changed")
        check("the stall clause is BEFORE the outage clause, so a timeout can never reach the retry",
              try_block.index("except (asyncio.TimeoutError") < try_block.index(
                  "except FleetUnavailable"),
              "a TimeoutError would fall through to the outage handler and be re-sent")
        stall_clause = (src[src.index("except (asyncio.TimeoutError"):
                            src.index("except FleetUnavailable")])
        check("...and the stall clause itself never blocks the gateway or re-sends the task",
              "_block_ws" not in stall_clause and "_delegate_via_cli" not in stall_clause,
              f"the stall path grew a retry: {stall_clause[:200]}")

        print("\n[4] the distinction is a TYPE, so a caller can branch on it")
        check("FleetStalled is a FleetUnavailable, so every existing caller still handles it",
              issubclass(FleetStalled, FleetUnavailable))

        async def branch(e):
            if isinstance(e, FleetStalled):
                return "takeback"
            if isinstance(e, FleetUnavailable):
                return "outage"
            return "something else"

        check("a caller CAN branch on the two: a stall is a takeback, an outage is an outage",
              asyncio.run(branch(FleetStalled("x"))) == "takeback"
              and asyncio.run(branch(FleetUnavailable("x"))) == "outage")

    finally:
        websockets.connect = real_connect
        fleet._delegate_via_cli = real["cli"]
        fleet._block_ws = real["block"]
        fleet._reset_ws_block = real["reset"]
        fleet._ws_url = real["url"]
        settings.openclaw_delegation_enabled = real["enabled"]
        settings.openclaw_token = real["token"]

    print(f"\n{'=' * 60}")
    print(f"  {passed} passed, {failed} failed")
    print("=" * 60)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
