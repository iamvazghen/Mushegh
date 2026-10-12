"""Point the Open Design MCP registration at the sidecar pipe that is actually live.

**The defect this fixes.** `_register_open_design.py` wrote a registration containing
`OD_SIDECAR_CLIENT_ENDPOINT=\\\\.\\pipe\\open-design-sidecar-<hash>`, and that hash does not
survive an app restart. Measured on 2026-10-11: the registration named
`...-915c57a54ceac48bdbb60d335d79e8e2`, the three live pipes were `45933e02...`, `3e77c7b6...` and
`6271be84...`, and the route had been quietly dead — `mcp__open-design__*` tools simply were not
there. The app says so itself when the endpoint is missing or wrong:

    The Open Design MCP registration is missing its runtime connection. Open the app and refresh
    the MCP registration, then restart this MCP session.

This is that refresh, without the app's UI. It is **not** in the data path: nothing probes pipes at
tool-call time. Run it when the Open Design tools are absent, which in practice means after the app
restarts or the machine reboots.

The hash is not derivable — 168 combinations of the data dir, namespace, user and exe path across
md5/sha1/sha256 and two encodings produced no match — so the only honest way to find the right pipe
is to try them, which is what this does.

    uv run python tools/refresh_open_design_mcp.py
    uv run python tools/refresh_open_design_mcp.py --check    # report only, write nothing
"""

from __future__ import annotations

import glob
import io
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

ENV_FILE = Path(__file__).resolve().parents[1] / ".env"
SETTING = "MUSHEGH_MCP_SERVERS"
SERVER = "open-design"
PIPE_GLOB = r"\\.\pipe\*"
PIPE_MARK = "open-design-sidecar"
#: Per pipe. The working one answered `initialize` in about five seconds; a pipe that is not the
#: daemon's does not answer at all, so this is a budget for the negative case, not the positive.
PROBE_SECONDS = 20


def _load() -> tuple[str, dict]:
    text = ENV_FILE.read_text(encoding="utf-8")
    match = re.search(rf"^{SETTING}=(.*)$", text, re.M)
    if not match:
        raise SystemExit(f"{SETTING} is not set in {ENV_FILE}")
    return text, json.loads(match.group(1))


def live_pipes() -> list[str]:
    return sorted(p for p in glob.glob(PIPE_GLOB) if PIPE_MARK in p)


def probe(server: dict, pipe: str) -> list[dict] | None:
    """Spawn the daemon CLI against ``pipe`` and return its tool list, or None."""
    argv = [server["command"], *server.get("args", [])]
    env = dict(os.environ)
    env.update(server.get("env", {}))
    env["OD_SIDECAR_CLIENT_ENDPOINT"] = pipe
    proc = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.DEVNULL, env=env, text=True,
                            encoding="utf-8", errors="replace", bufsize=1)
    try:
        def send(obj: dict) -> None:
            proc.stdin.write(json.dumps(obj) + "\n")
            proc.stdin.flush()

        send({"jsonrpc": "2.0", "id": 1, "method": "initialize",
              "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                         "clientInfo": {"name": "mushegh-refresh", "version": "1"}}})
        deadline = time.time() + PROBE_SECONDS
        while time.time() < deadline:
            line = proc.stdout.readline()
            if not line:
                return None
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                msg = json.loads(line)
            except ValueError:
                continue
            if msg.get("id") == 1 and msg.get("result"):
                send({"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}})
                send({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
            elif msg.get("id") == 2:
                return (msg.get("result") or {}).get("tools") or []
            elif msg.get("id") == 1 and msg.get("error"):
                return None
        return None
    finally:
        proc.kill()


def main(argv: list[str]) -> int:
    check_only = "--check" in argv
    text, servers = _load()
    server = servers.get(SERVER)
    if not server:
        raise SystemExit(f"{SETTING} has no {SERVER!r} entry; run tools/_register_open_design.py first")

    current = (server.get("env") or {}).get("OD_SIDECAR_CLIENT_ENDPOINT", "")
    pipes = live_pipes()
    if not pipes:
        print("no Open Design sidecar pipe is live — start the app, then run this again")
        return 1
    print(f"registered: {current or '<none>'}")
    print(f"live:       {', '.join(p.rsplit('-', 1)[-1] for p in pipes)}")
    if current in pipes:
        print("the registered pipe is live; probing it to be sure rather than assuming")

    # The registered one first: when it still works this costs one probe and changes nothing.
    for pipe in ([current] if current in pipes else []) + [p for p in pipes if p != current]:
        tools = probe(server, pipe)
        if tools is None:
            print(f"  {pipe.rsplit('-', 1)[-1]}: no handshake")
            continue
        print(f"  {pipe.rsplit('-', 1)[-1]}: {len(tools)} tools — this is the daemon")
        if pipe == current:
            print("registration is already correct; nothing written")
            return 0
        if check_only:
            print(f"--check: would set OD_SIDECAR_CLIENT_ENDPOINT to {pipe}")
            return 0
        server.setdefault("env", {})["OD_SIDECAR_CLIENT_ENDPOINT"] = pipe
        line = SETTING + "=" + json.dumps(servers, separators=(", ", ": "))
        shutil.copy2(ENV_FILE, str(ENV_FILE) + ".pre-od-refresh")
        io.open(ENV_FILE, "w", encoding="utf-8", newline="\n").write(
            re.sub(rf"^{SETTING}=.*$", lambda _m: line, text, count=1, flags=re.M))
        print(f"updated {ENV_FILE} (backup: .env.pre-od-refresh)")
        print("restart the brain for it to take effect — an MCP session holds its own child")
        return 0

    print("no live pipe answered the MCP handshake. The app is running but its daemon is not "
          "reachable; open Open Design, let it finish starting, and run this again")
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
