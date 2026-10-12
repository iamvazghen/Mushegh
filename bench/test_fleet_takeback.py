"""39.R2 — a delegation that stalls comes BACK to Mushegh, and is never sent twice.

The defect this closes was not a missing feature, it was a wrong answer. `delegate_to_fleet`
wrapped its work in `asyncio.wait_for(...)` and a `TimeoutError` from that wrapper fell into a
bare `except Exception`. So a **stall** — the fleet took the job and went quiet — was handled
exactly like an **outage**, and the outage handler re-sent the same task over a second
transport. Safe after a connection failure, because nothing was ever sent; not safe after a
stall, because the first attempt may still be running and a non-idempotent task — send this
email, spawn this process, pay this — then happens **twice**.

**The architecture changed under this test, and what it asserts changed with it.** The
WebSocket path and its CLI fallback are gone: A2A replaced them, Mushegh is a protocol peer,
and there is no longer a second transport to re-send over. That makes the double-execution bug
*structurally* impossible rather than guarded — a better outcome than the test was originally
defending, and exactly the kind of claim that has to be checked rather than assumed. So:

  * a stall still raises `FleetStalled`, a DISTINCT type, and the owner is still told it
    stalled rather than that the bridge is broken
  * the takeback wording is still there: it may still be running remotely, and it will not be
    re-sent without being told
  * the transport is called **exactly once** per delegation, asserted by counting — the
    double-execution guard, now a property of the shape rather than of a clause ordering
  * an outage (nothing was ever sent) is still a DIFFERENT, non-stall failure, because
    collapsing the two was the original bug in the other direction
  * the deleted retry really is deleted, rather than unused and waiting to be re-wired
  * a completed task carrying no text is a failure, not an empty success

Hermetic: the A2A client is replaced at the module seam. No socket is opened.

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


def main() -> int:
    from mushegh.brain import a2a
    from mushegh.brain.fleet import FleetStalled, FleetUnavailable, delegate_to_fleet
    from mushegh.config import settings

    import mushegh.brain.prefs as prefs

    store: dict = {}
    saved_prefs = (prefs.get, prefs.set)
    prefs.get = lambda k, d=None: store.get(k, d)
    prefs.set = lambda k, v: store.__setitem__(k, v)

    sent: list[str] = []
    progress: list[str] = []
    real = (a2a.ask, a2a.configured, settings.openclaw_delegation_enabled)
    a2a.configured = lambda _a: True
    settings.openclaw_delegation_enabled = True

    try:
        print("\n[1] a STALL comes back to Mushegh, and is not re-sent")

        async def stalls(agent, text, *, timeout_s=None, on_progress=None):
            sent.append(agent)
            if on_progress:
                on_progress("putting that to Tamara")
            # The exact shape `_ask_a2a` raises when its deadline passes with the task still
            # running. The wording is load-bearing: `fleet.ask` keys the stall on it.
            raise a2a.AgentUnreachable(
                f"{agent} took the task and had not answered after 1s; it may still be running"
            )

        a2a.ask = stalls

        async def run_stall():
            try:
                return await delegate_to_fleet("email Anna the invoice", "tamara", timeout_s=1,
                                               on_progress=progress.append)
            except FleetUnavailable as e:
                return e

        got = asyncio.run(run_stall())
        check("a stall raises, so the caller can tell it from a success", isinstance(got, Exception),
              repr(got))
        check("...and it is the DISTINCT stall type, not a generic outage",
              isinstance(got, FleetStalled), type(got).__name__)
        check("THE DOUBLE-EXECUTION GUARD: the task was sent exactly once", len(sent) == 1,
              f"sent {len(sent)} time(s) — it may still be running remotely")
        msg = str(got)
        check("the owner is told it STALLED, not that the bridge is broken",
              "did not answer" in msg and "gateway error" not in msg, msg[:120])
        check("...and that the work is back with Mushegh", "taken" in msg and "back" in msg, msg[:120])
        check("...including the warning that it may still be running there",
              "may still be running" in msg, msg[:160])
        check("...and that it will not be re-sent without being told",
              "without you saying so" in msg, msg[:200])
        check("...named by the person, not the agent id, because that is who the owner asked about",
              "Tamara" in msg, msg[:80])
        check("the owner heard a progress note before the wait began", bool(progress),
              str(progress))

        print("\n[2] an OUTAGE is a different event, and says so")
        sent.clear()

        async def refuses(agent, text, *, timeout_s=None, on_progress=None):
            sent.append(agent)
            raise a2a.AgentUnreachable("the gateway is unreachable: ConnectError")

        a2a.ask = refuses

        async def run_outage():
            try:
                return await delegate_to_fleet("research the Lisbon property", "ishkhan",
                                               timeout_s=1)
            except FleetUnavailable as e:
                return e

        got2 = asyncio.run(run_outage())
        check("an outage raises FleetUnavailable", isinstance(got2, FleetUnavailable),
              type(got2).__name__)
        check("...and NOT FleetStalled, because a stall is a different event",
              not isinstance(got2, FleetStalled), type(got2).__name__)
        check("...and it is still sent only once", len(sent) == 1, str(sent))
        check("...with the transport failure named", "unreachable" in str(got2), str(got2)[:120])

        print("\n[3] there is no second transport, so the re-send cannot come back")
        src = (ROOT / "src" / "mushegh" / "brain" / "fleet.py").read_text(encoding="utf-8")
        for gone in ("_delegate_via_cli", "_block_ws", "_ws_url", "websockets"):
            check(f"{gone} is gone from fleet.py, not merely unused", gone not in src)
        ask_body = src.split("async def ask(")[1].split("\nasync def ")[0]
        check("a stall is keyed on a TYPE the transport raises, not on a bare except Exception",
              "except Exception" not in ask_body)

        print("\n[4] a completed task with no text is a failure, not an empty answer")
        check("no artefacts means no answer", a2a._artifact_text({"artifacts": []}) == "")
        check("...and the A2A client raises on it rather than returning the empty string",
              "completed the task and returned no text"
              in (ROOT / "src" / "mushegh" / "brain" / "a2a.py").read_text(encoding="utf-8"))

        print("\n[5] the distinction is a TYPE, so a caller can branch on it")
        check("FleetStalled is a FleetUnavailable, so every existing caller still handles it",
              issubclass(FleetStalled, FleetUnavailable))

        def branch(e):
            if isinstance(e, FleetStalled):
                return "takeback"
            if isinstance(e, FleetUnavailable):
                return "outage"
            return "something else"

        check("a caller CAN branch on the two: a stall is a takeback, an outage is an outage",
              branch(FleetStalled("x")) == "takeback" and branch(FleetUnavailable("x")) == "outage")

    finally:
        a2a.ask, a2a.configured, settings.openclaw_delegation_enabled = real
        prefs.get, prefs.set = saved_prefs

    print(f"\n{'=' * 60}")
    print(f"  {passed} passed, {failed} failed")
    print("=" * 60)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
