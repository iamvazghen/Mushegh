"""What does JEv's HTTP transport actually return for an arbitration payload?

The 400 ms arbitration cap is enforced with asyncio.wait_for, yet measured elapsed came
back at 773-1264 ms with outcome "unavailable". A timeout at 400 ms would report ~400 ms,
so the overrun means the call either completed past the deadline or raised something
else. This calls the transport directly, outside the cap, to find out which.

Usage:
    python tools/diagnose_jev_transport.py
"""

from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mushegh.brain.judgment import _http_transport  # noqa: E402
from mushegh.config import settings  # noqa: E402

PAYLOAD = {
    "model": settings.jev_model,
    "state": {"question": "what's on today"},
    "questions": {
        "route": {
            "type": "choice",
            "instructions": "Pick the group that should answer this turn.",
            "criteria": {"group_1": "mushegh.brain.tools.calendar",
                         "group_2": "mushegh.brain.tasks"},
        }
    },
}


async def main() -> int:
    key = settings.typesafe_api_key.get_secret_value() if settings.typesafe_api_key else ""
    print("JEv transport diagnostic (no cap applied)")
    print(f"  endpoint    : {settings.jev_endpoint}")
    print(f"  model       : {settings.jev_model}")
    print(f"  httpx timeout passed: {settings.jev_timeout_seconds} s "
          f"(this is the SERVICE timeout, not the arbitration cap)")
    if not key:
        print("  no credential - cannot call")
        return 2

    started = time.perf_counter()
    try:
        status, body = await _http_transport(
            PAYLOAD, key, settings.jev_endpoint, settings.jev_timeout_seconds
        )
        elapsed = (time.perf_counter() - started) * 1000
        print(f"\n  HTTP status : {status}")
        print(f"  elapsed     : {elapsed:.0f} ms  (uncapped)")
        print(f"  body keys   : {sorted(body)[:10]}")
        answers = body.get("answers") or {}
        print(f"  answers     : {list(answers)}")
        for name, value in answers.items():
            print(f"    {name} = {str(value)[:160]}")
        return 0 if status == 200 else 1
    except Exception as exc:  # noqa: BLE001
        elapsed = (time.perf_counter() - started) * 1000
        print(f"\n  RAISED      : {type(exc).__name__}: {exc}")
        print(f"  elapsed     : {elapsed:.0f} ms")
        return 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))