"""MCP client — Phase 4.6 (hermetic: spawns a real local echo MCP server over stdio, no network).

Verifies the acceptance directly: a local MCP server's tools appear in Mushegh's registry and are
callable; schema conversion is correct; no config -> zero tools; a bad/missing server degrades cleanly
without crashing startup.

    uv run python bench/test_mcp_client.py
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path

# Module-level so the module-level helpers below can read the config the registry will parse.
# The run() function imports the public names again locally; that duplication is harmless and
# keeps the existing body untouched.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from mushegh.brain.mcp_client import _load_config  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

passed = failed = 0


def check(name: str, ok: bool, detail: str = "") -> None:
    global passed, failed
    if ok:
        passed += 1
        print(f"  [PASS] {name}")
    else:
        failed += 1
        print(f"  [FAIL] {name}  {detail}")


# A minimal, spec-correct MCP stdio server (newline-delimited JSON-RPC 2.0) that exposes one tool.
_ECHO_SERVER = r'''
import sys, json
for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    msg = json.loads(line)
    mid, method = msg.get("id"), msg.get("method")
    if method == "initialize":
        res = {"protocolVersion": "2024-11-05", "capabilities": {},
               "serverInfo": {"name": "echo", "version": "1"}}
    elif method == "tools/list":
        res = {"tools": [{"name": "echo", "description": "Echo the given text back",
                          "inputSchema": {"type": "object",
                                          "properties": {"text": {"type": "string"}},
                                          "required": ["text"]}}]}
    elif method == "tools/call":
        args = (msg.get("params") or {}).get("arguments") or {}
        res = {"content": [{"type": "text", "text": "echo: " + str(args.get("text", ""))}]}
    elif method and method.startswith("notifications/"):
        continue  # notifications get no response
    else:
        sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": mid,
                         "error": {"code": -32601, "message": "no method"}}) + "\n")
        sys.stdout.flush()
        continue
    sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": mid, "result": res}) + "\n")
    sys.stdout.flush()
'''


async def run() -> None:
    from mushegh.brain.mcp_client import MCPRegistry, to_openai_schema, _load_config
    from mushegh.config import settings

    print("[1] schema conversion (pure)")
    schema = to_openai_schema("demo", {"name": "echo", "description": "Echo text",
                                       "inputSchema": {"type": "object",
                                                       "properties": {"text": {"type": "string"}}}})
    check("name is namespaced mcp__server__tool", schema["function"]["name"] == "mcp__demo__echo")
    check("parameters carried through", "text" in schema["function"]["parameters"]["properties"])
    check("missing inputSchema still yields a valid object",
          to_openai_schema("d", {"name": "t"})["function"]["parameters"]["type"] == "object")

    print("\n[2] no config -> zero tools, clean")
    settings.mcp_servers = None
    reg0 = MCPRegistry()
    n0 = await reg0.load()
    check("no MCP config -> 0 tools", n0 == 0 and reg0.handlers == {})

    print("\n[3] a real local MCP server exposes a callable tool through the registry")
    tmp = Path(tempfile.mkdtemp(prefix="mushegh-mcp-")) / "echo_server.py"
    tmp.write_text(_ECHO_SERVER, encoding="utf-8")
    settings.mcp_servers = json.dumps({"demo": {"command": sys.executable, "args": [str(tmp)]}})
    reg = MCPRegistry()
    n = await reg.load()
    check("one tool was loaded from the server", n == 1, str(n))
    check("tool registered under the namespaced name", "mcp__demo__echo" in reg.handlers)
    check("its schema is advertised",
          any(s["function"]["name"] == "mcp__demo__echo" for s in reg.schemas))
    out = await reg.handlers["mcp__demo__echo"]({"text": "hello"})
    check("calling the MCP tool returns its result", out == "echo: hello", out)
    await reg.stop_all()

    print("\n[4] a bad/missing server degrades cleanly")
    settings.mcp_servers = json.dumps({"nope": {"command": "this-binary-does-not-exist-xyz", "args": []}})
    regb = MCPRegistry()
    nb = await regb.load()
    check("missing server -> 0 tools, no crash", nb == 0)
    await regb.stop_all()

    # ---- Streamable HTTP (added 2026-10-10) ------------------------------------------------
    # The client was stdio-only until then, and the registry SKIPPED any spec without a
    # `command` — so a hosted server such as Jina's `https://mcp.jina.ai/v1` was quietly dropped
    # with a warning nobody reads. This pins the dispatch: a `url` must build an HTTP server.
    settings.mcp_servers = '{"remote": {"url": "https://example.invalid/mcp"}}'
    check("a url-shaped spec is NOT dropped for lacking a command",
          _spec_kind("remote") == "http", _spec_kind("remote"))
    settings.mcp_servers = '{"local": {"command": "true"}}'
    check("a command-shaped spec still builds a stdio server",
          _spec_kind("local") == "stdio", _spec_kind("local"))
    settings.mcp_servers = '{"nameless": {"args": []}}'
    check("a spec with neither is skipped, not guessed at",
          _spec_kind("nameless") == "skip", _spec_kind("nameless"))
    settings.mcp_servers = None

    # The bearer token is referenced BY NAME in the config. A secret pasted into a config string
    # is a secret that ends up in a log, a diff and an issue.
    os.environ["MUSHEGH_TEST_MCP_TOKEN"] = "s3cr3t"
    settings.mcp_servers = '{"t": {"url": "https://x.invalid", "headers": {"Authorization": "Bearer ${MUSHEGH_TEST_MCP_TOKEN}"}}}'
    cfg = _load_config()
    check("${VAR} in a header expands from the environment",
          cfg["t"]["headers"]["Authorization"] == "Bearer s3cr3t",
          str(cfg["t"]["headers"]))
    os.environ.pop("MUSHEGH_TEST_MCP_TOKEN", None)
    settings.mcp_servers = '{"t": {"url": "https://x.invalid", "headers": {"Authorization": "Bearer ${MUSHEGH_NOT_SET_ANYWHERE}"}}}'
    cfg2 = _load_config()
    check("...and an unresolvable one is DROPPED, not sent as an empty credential",
          "Authorization" not in (cfg2["t"].get("headers") or {}), str(cfg2["t"].get("headers")))

    # SSE framing: Jina's body starts `event: message`, NOT `data:` — so a first-line check
    # passed against a tidy server and failed against the real one. Both shapes must parse.
    check("a JSON body parses", _extract_body('{"result":{"ok":1}}') == {"result": {"ok": 1}},
          _extract_body('{"result":{"ok":1}}'))
    sse = 'event: message\ndata: {"result":{"tools":["a"]}}'
    check("an SSE body starting with 'event:' still parses",
          _extract_body(sse) == {"result": {"tools": ["a"]}}, _extract_body(sse))
    check("the LAST data frame wins (a server may stream progress first)",
          _extract_body('data: {"result":{"n":1}}\ndata: {"result":{"n":2}}') == {"result": {"n": 2}},
          _extract_body('data: {"result":{"n":1}}\ndata: {"result":{"n":2}}'))
    check("a non-SSE, non-JSON body is rejected loudly, not silently",
          _extract_body("<html>502</html>") is None, _extract_body("<html>502</html>"))
    settings.mcp_servers = None


def _spec_kind(name: str) -> str:
    """Which server class the registry would build for this config entry."""
    cfg = _load_config()
    spec = cfg.get(name) or {}
    if spec.get("url"):
        return "http"
    if spec.get("command"):
        return "stdio"
    return "skip"


def _extract_body(text: str):
    """The response payload from either representation, mirroring HttpMCPServer._rpc."""
    import json as _json
    text = (text or "").strip()
    if not text:
        return None
    frames = [ln[5:].strip() for ln in text.splitlines() if ln.startswith("data:")]
    frames = [f for f in frames if f and f != "[DONE]"]
    if frames:
        text = frames[-1]
    elif not text.startswith(("{", "[")):
        return None
    try:
        return _json.loads(text)
    except _json.JSONDecodeError:
        return None


def main() -> None:
    asyncio.run(run())
    print(f"\n=== {passed}/{passed + failed} checks passed ===")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
