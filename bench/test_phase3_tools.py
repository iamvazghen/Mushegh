"""Phase 3 verification — knowledge & channel tools + ispir-only delegation.

Offline & deterministic: no network, no live integrations. It proves the tool registry is
wired, the schemas are well-formed, every tool degrades gracefully when unconfigured, the
vault read/search works against a temp folder (with path-traversal blocked), and the
fleet interface is locked to ispir only (no per-call agent override).

    uv run python bench/test_phase3_tools.py
"""

from __future__ import annotations

import asyncio
import inspect
import sys
import tempfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from mushegh.brain import tools  # noqa: E402
from mushegh.brain.fleet import FLEET_TOOL_SCHEMA, delegate_to_fleet  # noqa: E402
from mushegh.config import settings  # noqa: E402

passed = 0
failed = 0


def check(name: str, ok: bool, detail: str = "") -> None:
    global passed, failed
    if ok:
        passed += 1
        print(f"  [PASS] {name}")
    else:
        failed += 1
        print(f"  [FAIL] {name}  {detail}")


async def main() -> None:
    schemas = tools.tool_schemas()
    handlers = tools.tool_handlers()
    names = tools.tool_names()

    print("[1] registry & schemas")
    expected = {"search_vault", "read_vault_note", "web_search", "scrape_url",
                "browse_web", "check_telegram", "send_telegram"}
    check("all Phase 3 tools registered", expected <= set(names), f"missing {expected - set(names)}")
    check("no duplicate tool names", len(names) == len(set(names)))
    check("every schema is a well-formed function", all(
        s.get("type") == "function" and "name" in s["function"] and "parameters" in s["function"]
        for s in schemas))
    check("every schema has a handler", all(n in handlers for n in names))

    print("\n[2] per-agent delegation - INVERTED 2026-10-11, there is no team lead")
    # This section used to assert the OPPOSITE of every line below: no `agent` parameter, and the
    # description naming `ispir` as the team lead. That was right while one router re-read each
    # brief and chose a specialist himself. `ispir` belonged to the eight-agent fleet deleted on
    # 2026-10-08; the eighteen-agent fleet has no router, each agent owns its domains exclusively,
    # so the choice moved into Mushegh and `agent` became REQUIRED. A test that still demanded its
    # absence would have locked the fleet to an agent that does not exist.
    from mushegh.brain import roster

    params = FLEET_TOOL_SCHEMA["function"]["parameters"]
    props = params["properties"]
    check("delegate_to_fleet schema exposes an 'agent' param", "agent" in props)
    check("...and it is required, so routing is never left to chance", "agent" in params["required"])
    check("...enumerated as exactly the eighteen, so an invented name cannot be sent",
          sorted(props["agent"].get("enum", [])) == sorted(roster.names()))
    check("delegate_to_fleet() takes an 'agent' argument",
          "agent" in inspect.signature(delegate_to_fleet).parameters)
    desc = FLEET_TOOL_SCHEMA["function"]["description"].lower()
    check("the schema does NOT name the deleted router", "ispir" not in desc)
    check("...and says plainly that there is no team lead",
          "no team lead" in desc or "no router" in desc, desc[:160])
    check("every agent is named in the description, since the model routes from it",
          all(n in desc for n in roster.names()))

    print("\n[3] graceful degradation when unconfigured")
    # Force a clean slate so each 'not configured' path is exercised deterministically.
    saved = {k: getattr(settings, k) for k in (
        "tavily_api_key", "browserbase_api_key", "browserbase_project_id",
        "telegram_api_id", "telegram_api_hash", "telegram_bot_token", "telegram_default_chat",
        "vault_path")}
    for k in saved:
        setattr(settings, k, None)
    try:
        # web_search now has a KEYLESS tail (Jina Search), so it no longer has a 'not configured'
        # state — with no keys the provider chain is just the keyless Jina provider (Phase 4.5).
        import mushegh.brain.tools.web as webmod
        chain = [n for n, _ in webmod._search_providers()]
        check("web_search w/o keys -> keyless Jina fallback only", chain == ["Jina"], str(chain))
        # scrape_url uses Jina Reader (keyless) so it has no 'not configured' state — not exercised here.
        r = await handlers["browse_web"]({"url": "example.com"})
        check("browse_web w/o key -> friendly note", "isn't configured" in r, r)
        r = await handlers["check_telegram"]({})
        check("check_telegram w/o creds -> friendly note", "isn't configured" in r, r)
        r = await handlers["send_telegram"]({"message": "hi", "to": "123"})
        check("send_telegram w/o token -> friendly note", "isn't configured" in r, r)
        r = await handlers["search_vault"]({"query": "x"})
        check("search_vault w/o vault path -> friendly note", "isn't configured" in r, r)
        # No handler raised — all returned speakable strings.
        check("no handler raised on missing config", True)

        print("\n[4] vault read/search against a temp vault")
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "30-Projects").mkdir()
            note = root / "30-Projects" / "rabbit-farm-charter.md"
            note.write_text("# Lpstrak Rabbit Farm\nQuarantine and insurance plan for the farm.",
                            encoding="utf-8")
            settings.vault_path = str(root)
            r = await handlers["search_vault"]({"query": "rabbit farm"})
            check("search_vault finds the note", "rabbit-farm-charter.md" in r, r)
            r = await handlers["read_vault_note"]({"path": "30-Projects/rabbit-farm-charter.md"})
            check("read_vault_note returns body", "Quarantine and insurance" in r, r)
            r = await handlers["read_vault_note"]({"path": "../../../etc/passwd"})
            check("read_vault_note blocks path traversal", "outside the vault" in r or "couldn't find" in r, r)
    finally:
        for k, v in saved.items():
            setattr(settings, k, v)

    print("\n[5] agent registers the Phase 3 tools")
    from mushegh.brain.agent import MusheghAgent
    a = MusheghAgent()
    registered = {s["function"]["name"] for s in a._tools}
    check("agent exposes vault+web+telegram+fleet", expected <= registered)
    check("agent still has get_time + delegate_to_fleet",
          {"get_time", "delegate_to_fleet"} <= registered)

    print(f"\n=== {passed}/{passed + failed} checks passed ===")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
