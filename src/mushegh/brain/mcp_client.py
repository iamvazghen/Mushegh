"""Minimal MCP client Ã¢â‚¬â€ expose external MCP-server tools through Mushegh's normal registry (Phase 4.6).

The Model Context Protocol (MCP) stdio transport is just newline-delimited JSON-RPC 2.0 over a child
process's stdin/stdout, so a tiny client covers it with NO new dependency: spawn the configured server,
`initialize`, `tools/list`, and `tools/call`. Each MCP tool is converted into the same OpenAI function
schema + async handler everything else in the registry uses, namespaced `mcp__<server>__<tool>` so
names never collide.

Security boundary: ONLY servers explicitly listed in ``settings.mcp_servers`` are ever launched Ã¢â‚¬â€
there is no default server, no arbitrary filesystem/network access. Missing config -> zero tools.
A server that fails to start (bad command, missing binary) is logged and skipped; it never blocks
startup or crashes a turn.

Config (``MUSHEGH_MCP_SERVERS``) is a JSON object, inline or a path to a .json file::

    {"filesystem": {"command": "npx",
                    "args": ["-y", "@modelcontextprotocol/server-filesystem", "/safe/dir"]}}
"""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from typing import Any, Awaitable, Callable

from loguru import logger

from mushegh.brain.tools.base import policy_for
from mushegh.config import settings

_PROTOCOL_VERSION = "2024-11-05"

#: Floor for the Streamable-HTTP transport's own default. See `HttpMcpClient.__init__`.
_MCP_MIN_TIMEOUT_S = 30.0


def to_openai_schema(server: str, tool: dict[str, Any]) -> dict[str, Any]:
    """Convert one MCP tool descriptor into an OpenAI function schema (namespaced by server)."""
    params = tool.get("inputSchema") or {"type": "object", "properties": {}}
    # OpenAI expects a JSON-schema object; MCP inputSchema already is one. Ensure the basics exist.
    if "type" not in params:
        params = {**params, "type": "object"}
    params.setdefault("properties", {})
    return {
        "type": "function",
        "function": {
            "name": f"mcp__{server}__{tool['name']}",
            "description": (tool.get("description") or f"{tool['name']} (via MCP server '{server}')")[:1024],
            "parameters": params,
        },
    }


def _expand(node: Any) -> Any:
    """Expand `${VAR}` inside strings, recursively.

    An MCP server that needs a bearer token would otherwise mean pasting the secret into
    `MUSHEGH_MCP_SERVERS`, which is a config string that gets logged, diffed and pasted into
    issues. The token belongs in `.env` and only the NAME of its variable belongs here.

    An UNRESOLVED variable becomes the sentinel below rather than an empty string. Empty would
    turn `"Bearer ${MISSING}"` into `"Bearer "`, which is non-empty and would therefore be sent —
    turning a missing credential into what looks like a rejected one. That is the hardest kind of
    config bug to see from the outside, so it gets its own marker and the header is dropped.
    """
    import os
    import re as _re

    if isinstance(node, str):
        def sub(m: "_re.Match[str]") -> str:
            name = m.group(1)
            val = os.environ.get(name)
            return val if val else _UNRESOLVED + name + _UNRESOLVED
        return _re.sub(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}", sub, node)
    if isinstance(node, dict):
        return {k: _expand(v) for k, v in node.items()}
    if isinstance(node, list):
        return [_expand(v) for v in node]
    return node


#: Marks a `${VAR}` that is not set. `_load_config` drops any header still carrying one.
_UNRESOLVED = "\x00unresolved:"


def _load_config() -> dict[str, dict]:
    """Parse ``settings.mcp_servers`` (inline JSON or a path to a .json file). {} if unset/invalid."""
    raw = (settings.mcp_servers or "").strip()
    if not raw:
        return {}
    try:
        if not raw.startswith("{"):
            p = Path(raw).expanduser()
            raw = p.read_text(encoding="utf-8") if p.is_file() else "{}"
        cfg = json.loads(raw)
        cfg = _expand(cfg) if isinstance(cfg, dict) else {}
        # Drop a server whose only credential failed to expand: an empty Authorization header
        # would otherwise be sent and look like a real auth failure rather than a config gap.
        for name, spec in list(cfg.items()):
            if isinstance(spec, dict):
                hdrs = spec.get("headers") or {}
                spec["headers"] = {
                    k: v for k, v in hdrs.items()
                    if v and _UNRESOLVED not in str(v)
                }
        return cfg if isinstance(cfg, dict) else {}
    except (OSError, json.JSONDecodeError) as e:
        logger.warning(f"MCP config could not be read ({type(e).__name__}); no MCP tools loaded")
        return {}


class StdioMCPServer:
    """One MCP server spoken to over stdio (newline-delimited JSON-RPC 2.0)."""

    def __init__(self, name: str, command: str, args: list[str], env: dict | None = None,
                 timeout: float = 20.0) -> None:
        self.name = name
        self._command = command
        self._args = args or []
        self._env = env
        #: Per-server handshake budget. An Electron-hosted daemon (Open Design) needs ~13s to
        #: answer `initialize`, which is most of the old flat 20s and overran it on the second
        #: attempt Ã¢â‚¬â€ so the default lives here, is overridable per server, and the elapsed cost
        #: is logged. A server that cannot answer its handshake should be SKIPPED, not allowed to
        #: decide whether the brain comes up.
        self._timeout = float(timeout)
        self._proc: asyncio.subprocess.Process | None = None
        self._id = 0
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        import os

        env = {**os.environ, **(self._env or {})}
        self._proc = await asyncio.create_subprocess_exec(
            self._command, *self._args,
            stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL, env=env,
        )
        await self._request("initialize", {
            "protocolVersion": _PROTOCOL_VERSION,
            "capabilities": {},
            "clientInfo": {"name": "mushegh", "version": "1"},
        })
        await self._notify("notifications/initialized")

    async def _send(self, msg: dict) -> None:
        assert self._proc and self._proc.stdin
        self._proc.stdin.write((json.dumps(msg) + "\n").encode("utf-8"))
        await self._proc.stdin.drain()

    async def _notify(self, method: str, params: dict | None = None) -> None:
        await self._send({"jsonrpc": "2.0", "method": method, "params": params or {}})

    async def _request(self, method: str, params: dict | None = None, timeout: float | None = None) -> Any:
        timeout = float(timeout if timeout is not None else self._timeout)
        assert self._proc and self._proc.stdout
        async with self._lock:
            self._id += 1
            req_id = self._id
            await self._send({"jsonrpc": "2.0", "id": req_id, "method": method,
                              "params": params or {}})
            # Read lines until the response with our id (skip notifications / other messages).
            while True:
                line = await asyncio.wait_for(self._proc.stdout.readline(), timeout=timeout)
                if not line:
                    raise RuntimeError(f"MCP server '{self.name}' closed the connection")
                try:
                    msg = json.loads(line.decode("utf-8").strip())
                except json.JSONDecodeError:
                    continue  # server may emit non-JSON log noise; ignore
                if msg.get("id") == req_id:
                    if "error" in msg:
                        raise RuntimeError(f"MCP error: {msg['error']}")
                    return msg.get("result")

    async def list_tools(self) -> list[dict]:
        result = await self._request("tools/list")
        return (result or {}).get("tools") or []

    async def call(self, tool: str, arguments: dict) -> str:
        result = await self._request("tools/call", {"name": tool, "arguments": arguments or {}})
        # MCP returns content blocks; flatten the text ones into a single string.
        blocks = (result or {}).get("content") or []
        texts = [b.get("text", "") for b in blocks if isinstance(b, dict) and b.get("type") == "text"]
        out = "\n".join(t for t in texts if t).strip()
        if (result or {}).get("isError"):
            return f"MCP tool '{tool}' reported an error: {out or 'unknown error'}"
        return out or "(the MCP tool returned no text)"

    async def stop(self) -> None:
        if self._proc and self._proc.returncode is None:
            try:
                self._proc.terminate()
                await asyncio.wait_for(self._proc.wait(), timeout=5.0)
            except (ProcessLookupError, asyncio.TimeoutError):
                pass


class HttpMCPServer:
    """One MCP server spoken to over Streamable HTTP (the remote transport).

    Added 2026-10-10 because the client was stdio-only: a server configured with a `url`
    instead of a `command` was skipped with a warning, which is how Jina's official MCP server
    (https://mcp.jina.ai/v1) would have been silently dropped on the way to being declared as
    working. MCP's own recommendation for a hosted server is HTTP, so stdio-only was a real gap
    rather than a preference.

    The wire format is JSON-RPC 2.0 over POST. A Streamable HTTP server may answer with plain
    JSON OR with an SSE stream (`data: {...}` lines), so both are parsed Ã¢â‚¬â€ answering only one
    shape is the kind of thing that works in testing and 404s in production.
    """

    def __init__(self, name: str, url: str, headers: dict | None = None,
                 timeout: float | None = None) -> None:
        self.name = name
        self.url = url
        self.headers = dict(headers or {})
        # The timeout is read from the declared table rather than written here, so
        # the rule that no module carries its own outbound number holds for this
        # one too (`test_api_policy`; `semantic.py` is the other reader).
        #
        # `retries` is deliberately NOT taken from that table, and the asymmetry is
        # the point: an MCP `tools/call` whose response is lost may well have
        # EXECUTED server-side. A transport that retries turns "I am not sure it
        # ran" into "it ran twice". Only the timeout is borrowed; the retry
        # decision stays absent, which is why this builds its own client instead
        # of calling tools.base.http_post.
        #
        # The floor is MCP's own, not the table's general default: behind a
        # `tools/call` POST sits real work (a design tool, a filesystem walk), and
        # a client-side timeout surfaces that as "the tool failed" when the tool
        # may simply still be running. A host with a longer declared policy —
        # Jina's 45s — still wins, because the table is the ceiling here.
        self._timeout = (float(timeout) if timeout is not None
                         else max(policy_for(url).timeout, _MCP_MIN_TIMEOUT_S))
        self._id = 0
        self._session_id: str | None = None
        self._tools: list[dict[str, Any]] = []
        self._inited = False

    async def _rpc(self, method: str, params: dict | None = None) -> dict[str, Any]:
        import httpx

        self._id += 1
        payload = {"jsonrpc": "2.0", "id": self._id, "method": method}
        if params is not None:
            payload["params"] = params
        headers = {
            "Content-Type": "application/json",
            # A compliant Streamable HTTP server may pick either representation.
            "Accept": "application/json, text/event-stream",
            **self.headers,
        }
        if self._session_id:
            headers["Mcp-Session-Id"] = self._session_id

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(self.url, json=payload, headers=headers)
            resp.raise_for_status()
            sid = resp.headers.get("mcp-session-id")
            if sid:
                self._session_id = sid

        text = (resp.text or "").strip()
        if not text:
            raise RuntimeError(f"{self.name}: empty response to {method}")
        # Streamable HTTP may answer with plain JSON or an SSE stream, and the SSE body does NOT
        # necessarily start with `data:` Ã¢â‚¬â€ Jina's begins `event: message\ndata: {...}`. Checking
        # the first line only is the kind of thing that passes against a well-behaved server and
        # fails against the one you actually configured, so scan the whole body for data frames.
        frames = [ln[5:].strip() for ln in text.splitlines() if ln.startswith("data:")]
        frames = [f for f in frames if f and f != "[DONE]"]
        if frames:
            text = frames[-1]          # the LAST data frame answers this request id
        elif not text.startswith(("{", "[")):
            raise RuntimeError(
                f"{self.name}: {method} returned neither JSON nor an SSE data frame "
                f"(content-type {resp.headers.get('content-type')!r}, first line "
                f"{text.splitlines()[0][:60]!r})")
        body = json.loads(text)
        if isinstance(body, dict) and body.get("error"):
            raise RuntimeError(f"{self.name}: {body['error'].get('message', 'RPC error')}")
        result = body.get("result") if isinstance(body, dict) else None
        if result is None:
            raise RuntimeError(f"{self.name}: {method} returned no result")
        return result

    async def start(self) -> None:
        await self._rpc("initialize", {
            "protocolVersion": _PROTOCOL_VERSION,
            "capabilities": {},
            "clientInfo": {"name": "mushegh", "version": "1"},
        })
        # The spec requires a notification after initialize; servers that enforce it 400 without.
        await self._notify("notifications/initialized")
        self._inited = True

    async def _notify(self, method: str) -> None:
        import httpx

        headers = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream",
                   **self.headers}
        if self._session_id:
            headers["Mcp-Session-Id"] = self._session_id
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                await client.post(self.url,
                                  json={"jsonrpc": "2.0", "method": method},
                                  headers=headers)
        except Exception:  # noqa: BLE001 - a notification is advisory; failing it must be fatal-free
            pass

    async def list_tools(self) -> list[dict[str, Any]]:
        result = await self._rpc("tools/list")
        tools = result.get("tools") or []
        self._tools = tools
        return tools

    async def call(self, tool: str, args: dict) -> str:
        result = await self._rpc("tools/call", {"name": tool, "arguments": args or {}})
        if result.get("isError"):
            text = result.get("content")
            return f"The MCP tool returned an error: {text}" if not text else str(text)
        parts = result.get("content") or []
        bits = [p.get("text", "") for p in parts if isinstance(p, dict) and p.get("text")]
        return "\n".join(bits).strip() or str(result)

    async def stop(self) -> None:
        return None


class MCPRegistry:
    """Starts the configured MCP servers and exposes their tools as schemas + handlers."""

    def __init__(self) -> None:
        self.servers: list[Any] = []
        self.schemas: list[dict[str, Any]] = []
        self.handlers: dict[str, Callable[[dict], Awaitable[str]]] = {}

    async def load(self) -> int:
        """Start every configured server and collect its tools. Returns the number of tools loaded.
        Best-effort: a server that fails to start is skipped with a warning, never raised."""
        cfg = _load_config()
        for name, spec in cfg.items():
            if not isinstance(spec, dict):
                logger.warning(f"MCP server '{name}' is not an object; skipping")
                continue
            if spec.get("url"):
                # Streamable HTTP. A hosted server has no command, and the old stdio-only branch
                # would have skipped it with a warning nobody reads.
                server = HttpMCPServer(
                    name, str(spec["url"]),
                    spec.get("headers") or {},
                    float(spec.get("timeout") or 30.0),
                )
            elif spec.get("command"):
                server = StdioMCPServer(name, spec["command"], spec.get("args") or [],
                                        spec.get("env"),
                                        float(spec.get("timeout") or 30.0))
            else:
                logger.warning(f"MCP server '{name}' has neither a command nor a url; skipping")
                continue
            try:
                _t0 = time.monotonic()
                await server.start()
                tools = await server.list_tools()
                elapsed = time.monotonic() - _t0
            except Exception as e:  # noqa: BLE001 Ã¢â‚¬â€ a bad/missing server must not break startup
                logger.warning(f"MCP server '{name}' unavailable ({type(e).__name__}); skipping")
                await server.stop()
                continue
            self.servers.append(server)
            for tool in tools:
                self.schemas.append(to_openai_schema(name, tool))
                self.handlers[f"mcp__{name}__{tool['name']}"] = self._make_handler(server, tool["name"])
            # The elapsed cost is logged because these servers load SERIALLY at brain warmup, so a
            # hosted daemon that takes 13s to answer `initialize` is 13s the assistant is not yet
            # listening. Boot latency that only shows up as a slow first response is still latency.
            logger.info(f"MCP server '{name}': exposed {len(tools)} tool(s) in {elapsed:.1f}s")
        return len(self.handlers)

    def _make_handler(self, server: Any, tool: str) -> Callable[[dict], Awaitable[str]]:
        async def handler(args: dict) -> str:
            try:
                return await server.call(tool, args)
            except Exception as e:  # noqa: BLE001 Ã¢â‚¬â€ degrade like every other tool
                return f"The MCP tool ({server.name}/{tool}) hit an error: {type(e).__name__}."
        return handler

    async def stop_all(self) -> None:
        for s in self.servers:
            await s.stop()


# Process-wide registry (empty until load() runs at brain warmup).
MCP = MCPRegistry()
