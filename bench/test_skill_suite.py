"""The skill suite is reachable and truthful (hermetic — no network, no model call).

**Two ways a playbook lies to the model, both of which have happened here.**

1. **Silent truncation.** `read_skill` does `clip(text, 6000)`. A playbook past that limit is not
   errored on — it is *cut*, and the model proceeds with an instruction set that ends mid-
   sentence with no indication anything was removed. `governance-and-compliance.md` was 7,585
   characters and had been shipping truncated; the GDPR tables were invisible. Nothing failed.
   That is the worst class of bug in this system because it looks like success.

2. **Phantom tools.** A playbook that tells the model to call a tool which does not exist
   teaches it to invent arguments and then to be confused when nothing happens. This is the same
   defect `test_tool_reachability.py` exists for on the routing side, applied to the prose side.

**Negative controls.** Each check below is paired with a positive one. "The file is under the
limit" also passes for an empty file, so the gate separately asserts the file has real content.
"The tool is in the registry" also passes if the gate extracted nothing, so the gate asserts it
extracted a non-trivial number of candidates. A gate that passes vacuously is worse than no gate.

    uv run python bench/test_skill_suite.py
"""

from __future__ import annotations

import asyncio
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mushegh.brain.tools.skills import _skill_files, _SKILLS_DIR, read_skill  # noqa: E402

# read_skill clips at this. Mirrored, not imported, because the point is to catch someone
# RAISING the limit in base.py without noticing what it was hiding.
CLIP = 6000

passed = failed = 0

# Names the playbooks reference that are deliberately NOT registry tools. Each needs a reason,
# so that quietly promoting one of these into the registry (or quietly using a name that should
# have been here) is visible in this file rather than inferred from a failure.
NOT_TOOLS = {
    "reset_session": "an MusheghAgent method, not a tool — the model asks in prose",
    "list_tools": "no such tool; the registry is authoritative via adding-a-tool.md",
    "ask_user": "no such tool; clarifying questions come from maybe_correct/maybe_ask",
    "graphify": "an external CLI, not an Mushegh tool",
    "clip": "base.clip, internal",
    # laptop-executor ops (edge/pc_agent.py) reached via file_op, not brain-registry tools
    "create_file": "a pc_agent op value for file_op, not a brain tool",
    "create_folder": "a pc_agent op value for file_op, not a brain tool",
    "delete_file": "a pc_agent op value for file_op, not a brain tool",
    "delete_folder": "a pc_agent op value for file_op, not a brain tool",
    # internals named in prose
    "confirm_required": "proactive.py function, internal",
    "send_proactive": "internal sender, internal",
    "maybe_correct": "uncertainty.py internal",
    "maybe_ask": "uncertainty.py internal",
    "not_configured": "a tool_error marker string, not a tool",
    "needs_clarification": "a tool_error marker string, not a tool",
    "tool_error": "base.py sentinel, not a tool",
    "rule_applied": "an audit.py field, not a tool",
    "run_all_tests": "bench/run_all_tests.py, a script",
    "http_get": "illustrative name inside adding-a-tool.md prose",
    "http_post": "illustrative name inside adding-a-tool.md prose",
    "node_modules": "a directory, not a tool",
    # --- added 2026-10-12: the prompting-* and the-fleet playbooks. ------------
    # These describe OTHER agents, not Mushegh. The four prompting playbooks are
    # about the coding chain (Claude Code -> mcode -> Mistral Vibe -> Open
    # Design), so the names they quote are that CLI's or MCP server's surface --
    # a tool Mushegh cannot call and is not meant to. Declaring them here is what
    # the list is for; the alternative is to delete accurate prose to satisfy a
    # grep, which would make the playbook lie about the tool it documents.
    # Open Design's MCP server surface, namespaced mcp__open-design__* at runtime.
    "list_projects": "an Open Design MCP tool, not an Mushegh tool",
    "get_project": "an Open Design MCP tool, not an Mushegh tool",
    "get_active_context": "an Open Design MCP tool, not an Mushegh tool",
    "list_files": "an Open Design MCP tool, not an Mushegh tool",
    "list_plugins": "an Open Design MCP tool, not an Mushegh tool",
    "list_agents": "an Open Design MCP tool, not an Mushegh tool",
    "get_artifact": "an Open Design MCP tool, not an Mushegh tool",
    "get_file": "an Open Design MCP tool, not an Mushegh tool",
    "search_files": "an Open Design MCP tool, not an Mushegh tool",
    "start_run": "an Open Design MCP tool, not an Mushegh tool",
    "get_run": "an Open Design MCP tool, not an Mushegh tool",
    "cancel_run": "an Open Design MCP tool, not an Mushegh tool",
    "write_file": "an Open Design MCP tool, not an Mushegh tool",
    "create_project": "an Open Design MCP tool, not an Mushegh tool",
    "create_artifact": "an Open Design MCP tool, not an Mushegh tool",
    "delete_project": "an Open Design MCP tool, not an Mushegh tool",
    "collect_brief": "an Open Design MCP tool, not an Mushegh tool",
    "confirm_brief": "an Open Design MCP tool, not an Mushegh tool",
    "start_vela_login": "an Open Design MCP tool named for internal compatibility, not an Mushegh tool",
    # Claude Code's own stream protocol -- the playbook tells Mushegh how to READ
    # that agent's output, not that Mushegh may call it.
    "is_error": "a Claude Code stream-event field, not an Mushegh tool",
    "parse_stream_json": "the Claude Code result parser the playbook describes, not a tool",
    # mcode's JSON event vocabulary.
    "tests_run": "an mcode event field, not an Mushegh tool",
    # Mistral Vibe's transcript parser.
    "parse_vibe_json": "the Mistral Vibe parser the playbook describes, not a tool",
    # the fleet gate is a setting, and the playbook says so in the same sentence.
    "fleet_authorized": "the fleet arming switch (a setting), not an Mushegh tool",
}

# Backticked snake_case tokens are candidate tool names.
CANDIDATE = re.compile(r"`([a-z][a-z0-9_]{3,})`")


def check(name: str, ok: bool, detail: str = "") -> None:
    global passed, failed
    if ok:
        passed += 1
        print(f"  [PASS] {name}")
    else:
        failed += 1
        print(f"  [FAIL] {name}" + (f"  -- {detail}" if detail else ""))


async def amain() -> None:  # noqa: C901 - linear gate
    files = _skill_files()
    check("skill directory is discoverable", bool(files), f"{len(files)} files")
    # Positive control for everything below: a suite of zero skills would pass "none truncated".
    check("skill suite is non-trivial (>=20 playbooks)", len(files) >= 20, f"{len(files)} files")

    print("\n=== 1. no playbook is silently truncated ===")
    over: list[str] = []
    for p in files:
        text = p.read_text(encoding="utf-8", errors="ignore")
        if len(text) > CLIP:
            over.append(f"{p.name} ({len(text)} chars, {len(text) - CLIP} cut)")
    check("every playbook fits inside the read_skill clip", not over, "; ".join(over))

    print("\n=== 2. every playbook has content and a title ===")
    for p in files:
        text = p.read_text(encoding="utf-8", errors="ignore")
        check(f"{p.name} is non-empty", len(text.strip()) > 200, f"{len(text)} chars")
        check(f"{p.name} starts with an H1", text.lstrip().startswith("# "),
              repr(text[:40]))

    print("\n=== 3. every playbook is actually readable through read_skill ===")
    for p in files:
        out = await read_skill({"name": p.stem})
        # A missing skill returns "I don't have a '<name>' skill" rather than raising, so the
        # negative check has to look at the text, not just for a non-empty return.
        check(f"read_skill resolves {p.stem}", "don't have a" not in out and bool(out.strip()),
              out[:70])
        check(f"read_skill returns {p.stem} untruncated", len(text_of(p)) <= CLIP
              and len(out) >= min(len(text_of(p)), CLIP) - 2,
              f"got {len(out)} of {len(text_of(p))}")

    print("\n=== 4. unknown skill names fail loudly, not silently ===")
    missing = await read_skill({"name": "definitely-not-a-real-skill-xyz"})
    check("a missing skill says so", "don't have a" in missing, missing[:70])

    print("\n=== 5. the new suite is present ===")
    stems = {p.stem for p in files}
    for required in ("integration-utilization", "prompting", "sessions-and-context",
                     "secrets-and-access", "owner-model", "governance-regulatory-mapping"):
        check(f"skills/{required}.md exists", required in stems, sorted(stems)[:5])

    print("\n=== 6. the split was honest — nothing was lost ===")
    gov = text_of(_SKILLS_DIR / "governance-and-compliance.md")
    reg = text_of(_SKILLS_DIR / "governance-regulatory-mapping.md")
    check("controls file no longer holds the GDPR tables", "Art. 9" not in gov, f"{len(gov)} chars")
    check("mapping file holds the GDPR tables", "Art. 9" in reg, f"{len(reg)} chars")
    check("controls file points at the mapping file",
          "governance-regulatory-mapping" in gov, "")
    for token in ("Art. 5", "Art. 9", "CONFIRM_TIER", "gap"):
        check(f"mapping file still carries {token}", token.lower() in reg.lower(), "")

    print("\n=== 7. playbooks reference only tools that exist ===")
    try:
        from mushegh.brain.agent import MusheghAgent

        registry = set(MusheghAgent()._registry)
    except Exception as exc:  # noqa: BLE001
        registry = set()
        check("registry could be built", False, type(exc).__name__)

    if registry:
        found: dict[str, set[str]] = {}
        for p in files:
            for name in CANDIDATE.findall(text_of(p)):
                found.setdefault(name, set()).add(p.name)
        # Positive control: if extraction found nothing the next check would pass vacuously.
        check("candidate names were actually extracted", len(found) >= 10, f"{len(found)} names")

        phantoms = {
            n: sorted(f) for n, f in found.items()
            if n not in registry and n not in NOT_TOOLS
        }
        # Real tool names, not function names. Only flag a name if it appears in NO skill as a
        # known non-tool and is not an obviously-internal module (contains a dot or is a path).
        phantoms = {
            n: f for n, f in phantoms.items()
            if not any(ch in n for ch in ".") and "_" in n and len(n.split("_")) <= 3
        }
        check("no playbook names a tool that is not in the registry",
              not phantoms, "; ".join(f"{n} in {f[0]}" for n, f in phantoms.items()))

    print(f"\n=== {passed}/{passed + failed} checks passed ===")
    if failed:
        sys.exit(1)


def text_of(p: Path) -> str:
    return p.read_text(encoding="utf-8", errors="ignore")


if __name__ == "__main__":
    asyncio.run(amain())