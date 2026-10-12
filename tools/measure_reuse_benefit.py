"""Would connection reuse let arbitration fit inside its 400 ms cap?

The diagnosis, measured 2026-10-08:

    cold connection (new AsyncClient) : 1174 ms, 1167 ms
    warm connection (reused client)   : 597 ms, 226 ms, 424 ms

`src/mushegh/brain/tools/base.py` does `async with _client(url) as c` per request, so every
call pays a fresh TLS handshake - roughly a second of the budget before Jev is even asked
a question. The 400 ms cap is not unreachable because Jev is slow; it is unreachable
because the socket is.

This runs the REAL arbitration path - `JudgmentService.arbitrate` with its real 400 ms
cap - twice: once through the project's own transport, and once through a transport that
keeps one client alive. Same service, same cap, same payload. Only connection handling
differs, so the difference in how many land inside the cap is the answer to whether a
client-reuse fix is worth its blast radius.

Nothing is changed here. This measures; it does not propose.

Usage:
    python tools/measure_reuse_benefit.py [N]
"""

from __future__ import annotations

import asyncio
import statistics
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mushegh.brain.judgment import DecisionOption, DecisionRequest, JudgmentService  # noqa: E402
from mushegh.config import settings  # noqa: E402

PROBE = ("what's on today", ("mushegh.brain.tools.calendar", "mushegh.brain.tasks"))


async def reusing_transport_factory(key: str, endpoint: str, timeout: float):
    """One AsyncClient for the whole run, the way a long-lived process should behave."""
    client = httpx.AsyncClient(timeout=timeout, follow_redirects=True)
    try:
        async def transport(payload, _key, _endpoint, _timeout):
            response = await client.post(
                endpoint,
                headers={"Authorization": f"Bearer {key}",
                         "Content-Type": "application/json"},
                json=payload,
            )
            return response.status_code, response.json()
        return transport
    finally:
        pass  # the caller closes it


async def measure(service: JudgmentService, n: int) -> tuple[list[float], dict[str, int]]:
    latencies: list[float] = []
    outcomes: dict[str, int] = {}
    for i in range(n):
        text, groups = PROBE
        result = await service.arbitrate(text, groups, correlation_id=f"reuse-{i}")
        if result is None:
            continue
        latencies.append(result.latency_ms)
        outcomes[result.outcome] = outcomes.get(result.outcome, 0) + 1
    return latencies, outcomes


async def main() -> int:
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    key = settings.typesafe_api_key.get_secret_value()
    if not key:
        print("no JEv credential")
        return 2

    cap_ms = settings.jev_arbitration_timeout_seconds * 1000
    print(f"Real arbitration path, cap = {cap_ms:.0f} ms, {n} probes each way\n")

    baseline = await measure(JudgmentService(), n)
    print("  project's own transport (a new AsyncClient per request)")
    _report(baseline, cap_ms)

    client = httpx.AsyncClient(timeout=settings.jev_timeout_seconds, follow_redirects=True)

    async def transport(payload, _key, _endpoint, _timeout):  # noqa: ANN001
        response = await client.post(
            settings.jev_endpoint,
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json=payload,
        )
        return response.status_code, response.json()

    reused = await measure(JudgmentService(transport=transport), n)
    print("\n  one client kept alive for the whole run")
    _report(reused, cap_ms)
    await client.aclose()

    base_in = sum(1 for x in baseline[0] if x <= cap_ms)
    reuse_in = sum(1 for x in reused[0] if x <= cap_ms)
    print(f"\n  inside the cap: baseline {base_in}/{n}, with reuse {reuse_in}/{n}")
    print("  This is the whole argument for touching the shared transport, and also")
    print("  the blast radius of touching it: `_request` is every tool's HTTP path.")
    return 0


def _report(pair: tuple[list[float], dict[str, int]], cap_ms: float) -> None:
    latencies, outcomes = pair
    if not latencies:
        print("    no samples")
        return
    inside = sum(1 for x in latencies if x <= cap_ms)
    print(f"    median {statistics.median(latencies):6.0f} ms | "
          f"inside cap {inside}/{len(latencies)} | outcomes {outcomes}")


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))