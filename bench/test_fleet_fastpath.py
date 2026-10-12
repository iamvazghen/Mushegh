"""Delegation routing — the agent is named and checked, or refused; plus the learned bias.

**This file used to test a circuit breaker and no longer does, because the thing it protected is
gone.** Phase 4.4 added a per-URL breaker so a gateway that refuses operator WebSocket connects
did not cost a doomed handshake on every delegation. That path was deleted when A2A replaced it:
Mushegh is now a protocol peer with a peer's token, the handshake the breaker worked around does
not happen, and a breaker guarding nothing is dark code (D-46). Deleting this file with it would
have been wrong for a different reason — the *routing* half matters more now than it ever did,
because the fleet went from one router to eighteen named specialists in the same change and the
choice of specialist moved into Mushegh.

What is asserted:

  * an agent named in the call is validated against the roster, and a name that is not one of
    the eighteen is refused **before** any network call — including ``ispir``, the deleted
    router, which is the name most likely to still sit in an old prompt or vault note
  * a brief with no agent named resolves only when exactly one agent's domains match, and
    otherwise is refused **with the candidates named**: "the nearest thing" is how a legal
    question reaches the media agent
  * an unconfigured route says which setting is missing, and the answer differs per transport
  * the learned routing bias still needs two successes, and stays inside its prompt budget
  * the tool schema actually tells the model who the eighteen are

Hermetic: no socket is opened; the transport is replaced at the module seam.

    uv run python bench/test_fleet_fastpath.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from mushegh.brain import a2a, fleet, roster  # noqa: E402
from mushegh.config import settings  # noqa: E402

passed = failed = 0


def check(name: str, ok: bool, detail: str = "") -> None:
    global passed, failed
    if ok:
        passed += 1
        print(f"  [PASS] {name}")
    else:
        failed += 1
        print(f"  [FAIL] {name}  {detail}")


async def main() -> None:
    # Isolate prefs for the WHOLE test: a successful delegation calls _note_success, which would
    # otherwise write fake routing history into the owner's real prefs (and into his system prompt).
    import mushegh.brain.prefs as prefs

    store: dict = {}
    saved_get, saved_set = prefs.get, prefs.set
    prefs.get = lambda k, d=None: store.get(k, d)
    prefs.set = lambda k, v: store.__setitem__(k, v)
    try:
        await _body(store)
    finally:
        prefs.get, prefs.set = saved_get, saved_set

    print(f"\n=== {passed}/{passed + failed} checks passed ===")
    if failed:
        sys.exit(1)


async def _body(store: dict) -> None:
    print("\n[1] a named agent is CHECKED, never approximated")
    for dead in ("ispir", "business", "personal", "nobody"):
        try:
            fleet.resolve_agent("anything at all", dead)
        except fleet.FleetUnavailable as e:
            check(f"{dead!r} is refused", "not one of the eighteen" in str(e), str(e)[:90])
        else:
            check(f"{dead!r} is refused", False, "it resolved")
    check("a real agent resolves", fleet.resolve_agent("x", "zara") == "zara")
    check("...case and spacing are forgiven", fleet.resolve_agent("x", " ZARA ") == "zara")

    print("\n[2] with no agent named, one match routes and several refuse")
    one = fleet.resolve_agent("ffmpeg vertical clipping captions render", None)
    check("an unambiguous brief routes itself", one == "arsen", one)
    try:
        fleet.resolve_agent("zzzqqq wwwvvv", None)
    except fleet.FleetUnavailable as e:
        check("a brief matching nothing is refused with the roster named",
              "name one of" in str(e), str(e)[:90])
    else:
        check("a brief matching nothing is refused", False)
    try:
        # Deliberately broad: several agents' domains carry these words.
        fleet.resolve_agent("invoice contract vendor calendar research security", None)
    except fleet.FleetUnavailable as e:
        check("an ambiguous brief is refused WITH the candidates named",
              "name the one you mean" in str(e), str(e)[:130])
    else:
        check("an ambiguous brief is refused", False, "it picked one")

    print("\n[3] the transport is reached exactly once, and a refusal is never an empty answer")
    calls: list[tuple[str, str]] = []

    async def fake_ask(agent, text, *, timeout_s=None, on_progress=None):
        calls.append((agent, text))
        return "the specialist answered"

    real = (a2a.ask, a2a.configured, settings.openclaw_delegation_enabled)
    a2a.ask, a2a.configured = fake_ask, (lambda _a: True)
    settings.openclaw_delegation_enabled = True
    try:
        got = await fleet.delegate_to_fleet("look at the firewall rules", "zara")
        check("the answer comes back", got == "the specialist answered", got)
        check("...from exactly one call — there is no second transport to re-send over",
              len(calls) == 1, str(calls))
        check("...addressed to the agent that was named", calls[0][0] == "zara", str(calls))

        settings.openclaw_delegation_enabled = False
        try:
            await fleet.ask("zara", "x")
        except fleet.FleetUnavailable as e:
            check("delegation disabled refuses loudly", "disabled" in str(e), str(e)[:80])
        else:
            check("delegation disabled refuses", False, "it returned")
    finally:
        a2a.ask, a2a.configured, settings.openclaw_delegation_enabled = real

    print("\n[4] an unconfigured route names the setting it needs, per transport")
    saved = (settings.a2a_base_url, settings.a2a_tokens, settings.openclaw_cli_ssh_target,
             settings.openclaw_delegation_enabled)
    settings.a2a_base_url, settings.a2a_tokens = "", None
    settings.openclaw_cli_ssh_target = None
    settings.openclaw_delegation_enabled = True
    try:
        for agent, needle in (("zara", "MUSHEGH_A2A"), ("goharik", "SSH_TARGET")):
            try:
                await fleet.ask(agent, "x")
            except fleet.FleetUnavailable as e:
                check(f"{agent} ({roster.transport(agent)}) names what it needs",
                      needle in str(e), str(e)[:110])
            else:
                check(f"{agent} refuses when unconfigured", False)
    finally:
        (settings.a2a_base_url, settings.a2a_tokens, settings.openclaw_cli_ssh_target,
         settings.openclaw_delegation_enabled) = saved

    print("\n[5] routing memory still learns (Phase 4.4 'learned delegation')")
    store.clear()  # section [3]'s delegation landed here, not in the owner's real prefs
    check("no hint before anything is learned", fleet.routing_hint() == "")
    fleet._note_success("look at my stock portfolio")
    check("one success isn't a pattern yet", fleet.routing_hint() == "")
    fleet._note_success("check the etf market")
    hint = fleet.routing_hint()
    check("repeat domain becomes a routing hint", "finance/markets" in hint, hint)
    # The hint rides in EVERY system prompt against a hard 2000-tok budget, so it must stay short AND
    # bounded — an un-capped list blew the budget (2006 tok) as soon as a real user delegated twice.
    check("hint stays terse", len(hint) <= 60, f"{len(hint)} chars: {hint}")
    for extra in ("check my crypto wallet", "check my btc wallet", "refactor this code",
                  "fix the code bug", "find an apartment listing", "rent a property"):
        fleet._note_success(extra)
    many = fleet.routing_hint()
    check("hint stays capped as more domains are learned", len(many) <= 60, f"{len(many)} chars: {many}")

    print("\n[6] the tool schema tells the model who the eighteen are")
    desc = fleet.FLEET_TOOL_SCHEMA["function"]["description"]
    params = fleet.FLEET_TOOL_SCHEMA["function"]["parameters"]
    check("every agent is named in the description", all(n in desc for n in roster.names()))
    check("the agent argument is an enum of exactly the eighteen",
          sorted(params["properties"]["agent"]["enum"]) == sorted(roster.names()))
    check("...and is required, so routing is never left to chance",
          "agent" in params["required"])
    check("the deleted router is not advertised anywhere", "ispir" not in desc)


if __name__ == "__main__":
    asyncio.run(main())
