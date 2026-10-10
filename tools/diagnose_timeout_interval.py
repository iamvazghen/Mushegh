"""Why did the 400 ms arbitration cap look un-enforceable? Measure the right interval.

Two earlier measurements said httpx "does not honour a 0.4 s timeout against this host".
Both timed from *outside* an `async with httpx.AsyncClient(...)` block, so the number
included `aclose()` - the connection-pool teardown. Against a local server that always
sleeps, the overshoot was a near-constant ~1 s on top of whatever timeout was asked for:

    timeout=0.1 -> ReadTimeout at 1071 ms
    timeout=0.4 -> ReadTimeout at 1118 ms
    timeout=1.0 -> ReadTimeout at 1927 ms
    timeout=2.0 -> ReadTimeout at 3072 ms

which is elapsed ~= timeout + 1000 ms, not "the timeout is ignored". This measures the
await itself, with teardown excluded, for both a local control and the real JEv endpoint.

Usage:
    python tools/diagnose_timeout_interval.py
"""

from __future__ import annotations

import asyncio
import json
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import httpx

ROOT = __import__("pathlib").Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from afon.config import settings  # noqa: E402

CONTROL_SLEEP = 4.0


class _Slow(BaseHTTPRequestHandler):
    def do_POST(self) -> None:  # noqa: N802
        time.sleep(CONTROL_SLEEP)
        body = json.dumps({"ok": True}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        try:
            self.wfile.write(body)
        except OSError:
            pass  # the client hung up at its deadline; that is the point of the test

    def log_message(self, *args: object) -> None:
        pass


async def timed(label: str, make_request) -> str:
    """Time only the await. Teardown happens after the clock stops."""
    async with httpx.AsyncClient(timeout=label if isinstance(label, float) else 5.0) as client:
        started = time.perf_counter()
        try:
            response = await make_request(client)
            outcome = f"{response.status_code}"
        except Exception as exc:  # noqa: BLE001
            outcome = type(exc).__name__
        elapsed = (time.perf_counter() - started) * 1000
        print(f"    await only : {outcome:<14} at {elapsed:6.0f} ms")
        return outcome


async def main() -> int:
    print("Timeout interval, measured correctly (teardown excluded)\n")

    server = ThreadingHTTPServer(("127.0.0.1", 0), _Slow)
    port = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()
    local = f"http://127.0.0.1:{port}/slow"

    print(f"  CONTROL - local server that sleeps {CONTROL_SLEEP:.0f}s")
    for t in (0.1, 0.4, 1.0):
        async with httpx.AsyncClient(timeout=t) as client:
            started = time.perf_counter()
            try:
                await client.post(local, json={"q": 1})
                outcome = "completed"
            except Exception as exc:  # noqa: BLE001
                outcome = type(exc).__name__
            elapsed = (time.perf_counter() - started) * 1000
            over = elapsed - t * 1000
            print(f"    timeout={t:<5} -> {outcome:<14} at {elapsed:6.0f} ms "
                  f"(overshoot {over:+.0f} ms)")
    server.shutdown()

    key = settings.typesafe_api_key.get_secret_value() if settings.typesafe_api_key else ""
    if not key:
        print("\n  no JEv credential; stopping after the control")
        return 2

    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    payload = {
        "model": settings.jev_model,
        "state": {"question": "what is on today"},
        "questions": {"route": {"type": "choice", "instructions": "Pick the group.",
                                "criteria": {"group_1": "afon.brain.tools.calendar",
                                             "group_2": "afon.brain.tasks"}}},
    }

    print("\n  JEv - api.typesafe.ai, real endpoint")
    for t in (0.4, 0.4):
        started = time.perf_counter()
        async with httpx.AsyncClient(timeout=t) as client:
            try:
                response = await client.post(settings.jev_endpoint, headers=headers,
                                             json=payload)
                outcome = f"{response.status_code}"
            except Exception as exc:  # noqa: BLE001
                outcome = type(exc).__name__
            elapsed = (time.perf_counter() - started) * 1000
        print(f"    timeout={t:<5} -> {outcome:<14} at {elapsed:6.0f} ms")

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))