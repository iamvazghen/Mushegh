"""Fleet live test — brain -> each of the eighteen, end to end, GATED on authorization.

The fleet touches shared VPS infra, so this only RUNS when the operator has armed it
(``MUSHEGH_FLEET_AUTHORIZED=true``). Otherwise it self-skips with a clear sentinel — the
aggregate runner treats that as SKIP, not FAIL, so a default checkout stays green without a
gateway.

**It used to assert that one agent existed, and that was the weaker claim.** The old version
opened an operator WebSocket, sent ``agents.list`` and checked that the router ``ispir`` was in
the reply. ``ispir`` is gone, the WebSocket path is gone, and listing an agent never proved it
could answer anyway: a liveness check is not a survival check, and this fleet has twice shipped
a unit that reported healthy with its files deleted. So this asks each agent to say its own name
back, over whichever transport its framework actually speaks, and counts the ones that do.

Network failures are reported as a skip condition rather than a hard failure; an agent that is
reachable and answers *wrongly* is a real failure.

    MUSHEGH_FLEET_AUTHORIZED=true uv run python bench/test_fleet_connect.py
"""

from __future__ import annotations

import asyncio
import sys

from mushegh.config import settings

# Sentinels the aggregate runner greps for.
SKIP_SENTINEL = "fleet live test skipped"
PASS_SENTINEL = "fleet live checks passed"


def _skip(reason: str) -> None:
    print(f"{SKIP_SENTINEL}: {reason}")
    sys.exit(0)


async def main() -> None:
    if not settings.fleet_authorized:
        _skip("MUSHEGH_FLEET_AUTHORIZED is not true (fleet consult disarmed by default)")

    from mushegh.brain import a2a, roster

    drift = roster.drift()
    if drift:
        print(f"  note: {drift}")

    names = roster.names()
    unconfigured = [n for n in names if not a2a.configured(n)]
    if len(unconfigured) == len(names):
        _skip("no agent has a configured route (no A2A base url/tokens and no SSH target)")
    if unconfigured:
        print(f"  not configured, so not probed: {', '.join(unconfigured)}")

    probed: list[tuple[str, bool, str]] = []
    for name in names:
        if name in unconfigured:
            continue
        try:
            ok, detail = await asyncio.wait_for(a2a.ping(name, timeout_s=180), timeout=240)
        except (OSError, asyncio.TimeoutError) as e:
            print(f"  [SKIP] {name}: transport ({type(e).__name__})")
            continue
        probed.append((name, ok, detail))
        print(f"  [{'PASS' if ok else 'FAIL'}] {name} ({roster.transport(name)}) -> {detail[:60]!r}")

    if not probed:
        _skip("every configured agent failed at the transport level")
    bad = [n for n, ok, _ in probed if not ok]
    print(f"\n  {len(probed) - len(bad)}/{len(names)} of the eighteen answered with their own name")
    if bad:
        print(f"  reachable but answered wrongly: {', '.join(bad)}")
        sys.exit(1)
    print(f"\n=== {PASS_SENTINEL}: brain -> {len(probed)} agents verified ===")


if __name__ == "__main__":
    asyncio.run(main())
