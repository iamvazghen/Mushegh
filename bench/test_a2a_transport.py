"""The one runnable check behind the fleet transport: can Mushegh reach each of the eighteen?

Two halves, deliberately different in cost:

* **Offline** (default, no network): the roster is complete and exclusive, every agent has a
  transport, a name that is not on the roster is refused rather than approximated, and the
  A2A request this module builds is shaped the way the gateway's own schema demands. These are
  the assertions that fail when someone edits the roster or the request body.
* **Live** (``--live``): one real round trip per agent, asking it to say its own name back. This
  is the only thing that proves the fleet answers — a gateway that is up proves a process runs,
  not that this agent's config resolves or that its token maps to it.

    uv run python bench/test_a2a_transport.py
    uv run python bench/test_a2a_transport.py --live
"""

from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from mushegh.brain import a2a, roster  # noqa: E402


def offline() -> None:
    names = roster.names()
    assert len(names) == 18, names
    assert sum(len(roster.domains(n)) for n in names) == 83

    # One owner per domain, across BOTH frameworks. This is the fleet's defining property and
    # the thing a careless roster edit breaks first.
    owners: dict[int, str] = {}
    for n in names:
        for util in roster.domains(n):
            uid = int(util["id"])
            assert uid not in owners, f"domain {uid}: {owners[uid]} and {n}"
            owners[uid] = n
    assert len(owners) == 83

    kinds = {n: roster.transport(n) for n in names}
    assert sorted(kinds.values()).count("a2a") == 9, kinds
    assert sorted(kinds.values()).count("hermes") == 9, kinds

    # The deleted router must not resolve. "The nearest thing" is how a legal brief reaches the
    # media agent, and `ispir` is the name most likely to still be in an old prompt or note.
    for dead in ("ispir", "", "business", "personal"):
        try:
            roster.resolve(dead)
        except roster.UnknownAgent:
            pass
        else:
            raise AssertionError(f"{dead!r} resolved; it is not one of the eighteen")

    # The request body, against the gateway's A2A schema: role is an enum, parts carry text,
    # and returnImmediately is what makes this a submit-and-poll client rather than a held
    # connection. A silently renamed field here is a -32602 at runtime.
    body = a2a._rpc("message/send", {
        "message": {"messageId": "m", "role": "ROLE_USER", "contextId": "ctx-mushegh-gagas",
                    "parts": [{"text": "x"}]},
        "configuration": {"returnImmediately": True},
    })
    assert body["jsonrpc"] == "2.0" and body["method"] == "message/send"
    assert body["params"]["message"]["role"] in {"ROLE_USER", "user"}
    assert body["params"]["configuration"]["returnImmediately"] is True
    json.dumps(body)  # must survive the wire

    # A slash command is refused before dispatch, not sent and rejected server-side.
    try:
        asyncio.run(a2a.ask("gagas", "/status"))
    except a2a.AgentUnreachable as e:
        assert "slash" in str(e), e
    else:
        raise AssertionError("a slash command was dispatched")

    # Artefact extraction is the only place an answer comes from: a completed task with no
    # artefacts must not read as an empty success.
    assert a2a._artifact_text({"artifacts": [{"parts": [{"text": "hi"}]}]}) == "hi"
    assert a2a._artifact_text({"artifacts": []}) == ""
    assert a2a._artifact_text({}) == ""

    # A JSON-RPC error member is a failure even under HTTP 200.
    try:
        a2a._result({"jsonrpc": "2.0", "error": {"code": -32004, "message": "nope"}}, "t")
    except a2a.AgentUnreachable as e:
        assert "-32004" in str(e), e
    else:
        raise AssertionError("a JSON-RPC error read as success")

    print(f"offline ok: 18 agents, 83 domains one owner each, 9 a2a + 9 hermes; "
          f"roster drift: {roster.drift() or 'none'}")


async def live() -> int:
    names = roster.names()
    unconfigured = [n for n in names if not a2a.configured(n)]
    if unconfigured:
        print(f"not configured, so not probed: {', '.join(unconfigured)}")
    results: list[tuple[str, str, bool, float, str]] = []
    for n in names:
        if n in unconfigured:
            continue
        started = time.monotonic()
        ok, detail = await a2a.ping(n, timeout_s=180)
        results.append((n, roster.transport(n), ok, time.monotonic() - started, detail))
        print(f"{'ok ' if ok else 'BAD'} {n:<9} {roster.transport(n):<7} "
              f"{time.monotonic() - started:6.1f}s  {detail[:60]}")
    bad = [r for r in results if not r[2]]
    print(f"\n{len(results) - len(bad)}/{len(names)} agents answered with their own name"
          f"{'; failed: ' + ', '.join(r[0] for r in bad) if bad else ''}")
    return 1 if (bad or unconfigured) else 0


if __name__ == "__main__":
    offline()
    if "--live" in sys.argv:
        raise SystemExit(asyncio.run(live()))
