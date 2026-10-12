"""Measure the REAL deployed brain's RSS: `python -m mushegh.brain.server`, warm.

The agent alone is not the brain. The server adds the WebSocket endpoint, the HTTP client API, the
scheduler, the governor, the MCP loader and the turn pipeline — and 31.F6 is about the process the
VPS actually runs, not about a library import.

Two things this had to get right, both found by the first attempt reading 4.2 MiB on a server that
was in fact warming up:

  * the server takes longer than 25s to finish starting (MCP alone is ~30s), and
  * stdout must not go into a pipe nobody drains — the child blocks once the pipe fills, which
    looks exactly like a small process that died.

So: log to a file, wait for the LISTENING port, then sample the peak.

Run:  python tools/measure_brain_rss.py
"""
from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
from datetime import date
from pathlib import Path

import psutil

ROOT = Path(__file__).resolve().parents[1]
PY = ROOT / ".venv" / "Scripts" / "python.exe"
LOG = ROOT / "logs" / "brain-server-rss-run.log"

#: Set by the caller if the brain is not on the default port.
PORT = int(os.environ.get("RSS_PORT", "8765"))
READY_TIMEOUT_S = float(os.environ.get("RSS_READY_S", "120"))


def port_is_open(port: int, host: str = "127.0.0.1") -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex((host, port)) == 0


def listener_rss_mib(port: int) -> float:
    """RSS of the running mushegh.brain.server, found BY ITS COMMAND LINE.

    Three earlier attempts read the wrong process, for two separate reasons worth recording: a
    venv's python.exe is a REDIRECTOR that idles at ~4 MiB while the real interpreter works, and
    that redirector then EXITS, reparenting the server so children() finds nothing.
    
et_connections() is the obvious third guess and it is also wrong here - it needs elevation
    to see another process's sockets on Windows. Matching the command line is the one lookup that
    needs no privileges and cannot be fooled by the launcher.
    """
    best = 0.0
    for proc in psutil.process_iter(["pid", "cmdline"]):
        try:
            cmd = proc.info.get("cmdline") or []
            if any("mushegh.brain.server" in part for part in cmd):
                best = max(best, proc.memory_info().rss / (1024 * 1024))
        except (psutil.Error, OSError):
            continue
    return best


def main() -> int:
    env = dict(os.environ)
    env.setdefault("MUSHEGH_STATE_DIR", str(Path.home() / ".mushegh"))

    interpreter_rss = psutil.Process().memory_info().rss
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("w", encoding="utf-8") as sink:
        proc = subprocess.Popen(
            [str(PY), "-m", "mushegh.brain.server"],
            cwd=str(ROOT), env=env, stdout=sink, stderr=subprocess.STDOUT,
        )
    peak = 0
    ready_at = None
    deadline = time.time() + READY_TIMEOUT_S
    try:
        while time.time() < deadline and proc.poll() is None:
            peak = max(peak, listener_rss_mib(PORT))
            if ready_at is None and port_is_open(PORT):
                ready_at = time.time()
                break
            time.sleep(0.5)

        # Sampled while it is actually serving, not while it was still importing.
        if ready_at is not None:
            for _ in range(10):
                if proc.poll() is not None:
                    break
                peak = max(peak, listener_rss_mib(PORT))
                time.sleep(0.5)
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()

    mib = 1024 * 1024
    ready = ready_at is not None
    result = {
        "measured_at": time.strftime("%Y-%m-%d %H:%M"),
        "measured_on": str(date.today()),
        "subject": "mushegh.brain.server — the process the VPS runs",
        "reached_listening": ready,
        "listen_port": PORT,
        "ready_after_s": round(ready_at - (deadline - READY_TIMEOUT_S), 1) if ready else None,
        "interpreter_rss_mib": round(interpreter_rss / mib, 1),
        "server_peak_rss_mib": round(peak / mib, 1),
        "server_log": str(LOG),
    }
    out = ROOT / "logs" / f"rss-measurement-server-{date.today()}.json"
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    print(f"\nwrote {out}")
    return 0 if ready else 1


if __name__ == "__main__":
    sys.exit(main())