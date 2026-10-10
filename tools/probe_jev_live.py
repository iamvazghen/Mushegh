"""Live probe: can this host actually reach JEv, and if not, why not?

Written because the S01 blockers list said "JEv times out from this host". That is a
network claim. `JudgmentClient.judge` short-circuits to `missing_key` *before* any HTTP
when no credential is configured, so a probe that only reports "JEv did not answer"
cannot tell an outage from an absent key. This separates the three cases:

  1. no credential configured  -> short-circuit, no network touched
  2. credential present, TCP fails -> genuinely a network problem
  3. credential present, HTTP reaches -> live verdict, returned in full

Usage:
    python tools/probe_jev_live.py
"""

from __future__ import annotations

import asyncio
import socket
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from afon.brain.judgment import (  # noqa: E402
    DecisionOption,
    DecisionRequest,
    JudgmentService,
)
from afon.config import settings  # noqa: E402


def tcp_probe(host: str, port: int = 443, timeout: float = 6.0) -> tuple[bool, str]:
    started = time.perf_counter()
    try:
        with socket.create_connection((host, port), timeout=timeout):
            ms = (time.perf_counter() - started) * 1000
            return True, f"connected in {ms:.0f} ms"
    except OSError as error:
        return False, f"{type(error).__name__}: {error}"


async def main() -> int:
    key_present = bool(settings.typesafe_api_key)
    print("JEv live probe")
    print(f"  endpoint        : {settings.jev_endpoint}")
    print(f"  jev_enabled     : {settings.jev_enabled}")
    print(f"  credential      : {'PRESENT (value never printed)' if key_present else 'ABSENT'}")
    print(f"  endpoint in use : {'yes' if key_present else 'no - judge() short-circuits first'}")

    reachable, detail = tcp_probe("api.typesafe.ai")
    print(f"  TCP 443         : {'ok' if reachable else 'FAILED'} - {detail}")

    client = JudgmentService()
    request = DecisionRequest(
        question="Which of these two should the probe pick?",
        options=(
            DecisionOption(id="a", text="the first option"),
            DecisionOption(id="b", text="the second option"),
        ),
    )
    verdict = await client.judge(request, correlation_id="probe")
    print(f"\n  verdict.outcome : {verdict.outcome}")
    print(f"  selected_id     : {verdict.selected_id}")
    print(f"  selected_text   : {verdict.selected_text}")
    print(f"  probability     : {verdict.probability}")
    print(f"  confidence      : {verdict.confidence}")
    print(f"  model           : {verdict.model}")
    print(f"  latency_ms      : {verdict.latency_ms:.0f}")
    print(f"  fallback        : {verdict.fallback}")
    print(f"  error           : {verdict.error or '(none)'}")

    if verdict.outcome == "unavailable" and "missing_key" in (verdict.error + verdict.fallback):
        print("\n  CONCLUSION: the blocker is an ABSENT CREDENTIAL, not the network.")
        print("  No HTTP request was made.")
        return 2
    if verdict.decided:
        print("\n  CONCLUSION: JEv is LIVE from this host and returned a real verdict.")
        return 0
    print(f"\n  CONCLUSION: JEv answered but did not decide: outcome={verdict.outcome}.")
    return 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))