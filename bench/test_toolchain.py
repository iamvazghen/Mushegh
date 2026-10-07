"""D-88/D-89 — the toolchain updates itself, proves each update, and rolls a bad one back.

The owner asked for two jobs: every 24 h check Claude Code, Codex, OpenClaw and MiniMax Code for a
new version and install it, then ping for a pong so nothing is left broken; every 168 h let Jev say
what each tool is missing and ask the tools themselves.

An unattended updater is the kind of automation that is either carefully bounded or a liability, so
this gate is mostly about the bounds:

  * **a failed ping is rolled back**, not reported and left in place — and where no verified
    downgrade exists (Claude Code's native installer) that asymmetry is stated rather than faked;
  * **one tool at a time**, each proved before the next is touched, because updating four and then
    pinging four leaves four suspects for one failure;
  * **no credential reaches a child** except the one that tool needs;
  * **a quiet run says nothing** — a daily "nothing changed" is an interruption bought with no
    information (D-29, D-34);
  * **the weekly review installs nothing.** Jev ranks candidates *code* declared and the tools are
    asked for prose; applying any of it is the owner's (D-47).

Hermetic: every subprocess is replaced. No npm, no network, no CLI, nothing installed.

    uv run python bench/test_toolchain.py
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

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
        print(f"  [FAIL] {name}" + (f"  <- {detail}" if detail else ""))


class FakeShell:
    """Stands in for every process the module runs, and records the argv it was asked for."""

    def __init__(self) -> None:
        self.calls: list[list[str]] = []
        self.installed = {"@openai/codex": "1.0.0", "@minimax-ai/code": "0.6.3",
                          "openclaw": "2026.2.14"}
        self.latest = {"@openai/codex": "1.0.1", "@minimax-ai/code": "0.6.3",
                       "openclaw": "2026.2.14"}
        self.native_version = "2.1.288"
        self.native_after_update = "2.1.288"
        self.pong = True
        self.update_fails = False
        self.rollback_fails = False
        self.envs: list[dict] = []

    async def run(self, argv, *, timeout, env=None, cwd=None):
        self.calls.append(list(argv))
        self.envs.append(dict(env or {}))
        joined = " ".join(argv)
        if argv[:3] == ["npm", "ls", "-g"]:
            return 0, json.dumps({"dependencies": {k: {"version": v}
                                                   for k, v in self.installed.items()}}), ""
        if argv[:2] == ["npm", "view"]:
            return 0, self.latest.get(argv[2], ""), ""
        if argv[:3] == ["npm", "install", "-g"]:
            pkg, _, version = argv[3].rpartition("@")
            if version == "latest":
                if self.update_fails:
                    return 1, "", "EACCES"
                self.installed[pkg] = self.latest.get(pkg, self.installed.get(pkg, ""))
            else:
                if self.rollback_fails:
                    return 1, "", "no such version"
                self.installed[pkg] = version
            return 0, "added 1 package", ""
        if joined == "claude --version":
            return 0, f"{self.native_version} (Claude Code)", ""
        if joined == "claude update":
            self.native_version = self.native_after_update
            return 0, "updated", ""
        if "pong" in joined.lower():
            return (0, "pong", "") if self.pong else (0, "I'd rather not say", "")
        return 0, "", ""


def install(shell: FakeShell, module) -> None:
    module._run = shell.run


async def main() -> int:
    from afon.brain import toolchain as T

    # Keep the real ledger out of this: the module writes known-good versions to ~/.afon.
    import tempfile
    tmp = tempfile.mkdtemp(prefix="afon-toolchain-")
    T.ledger_path = lambda: Path(tmp) / "toolchain.json"  # type: ignore[assignment]

    original_run = T._run

    print("[1] the table matches how these tools are really installed on this host")
    names = [s.name for s in T.TOOLS]
    check("all four managed CLIs are declared",
          names == ["claude-code", "codex", "mcode", "openclaw"], str(names))
    check("claude is treated as a native install",
          next(s for s in T.TOOLS if s.name == "claude-code").kind == "native")
    check("the other three are npm packages",
          all(s.kind == "npm" for s in T.TOOLS if s.name != "claude-code"))
    check("mcode's package name is the real one",
          next(s for s in T.TOOLS if s.name == "mcode").package == "@minimax-ai/code")
    check("claude declares that it CANNOT be rolled back",
          not next(s for s in T.TOOLS if s.name == "claude-code").can_rollback,
          "its native installer has no downgrade command this module can verify")
    check("openclaw declares why it is not pinged",
          bool(next(s for s in T.TOOLS if s.name == "openclaw").no_ping_because),
          "a gap with no stated reason reads as an oversight")
    check("no spec invokes a shell",
          all("sh" != s.binary and "cmd" not in s.binary for s in T.TOOLS))

    print("\n[2] versions are parsed from three different output shapes")
    check("claude's '2.1.288 (Claude Code)'", T.parse_version("2.1.288 (Claude Code)") == "2.1.288")
    check("codex's 'codex-cli 0.160.0'", T.parse_version("codex-cli 0.160.0") == "0.160.0")
    check("mcode's bare '0.6.3'", T.parse_version("0.6.3") == "0.6.3")
    check("a prerelease survives", T.parse_version("1.2.3-beta.4") == "1.2.3-beta.4")
    check("no version is invented from noise", T.parse_version("command not found") == "")

    print("\n[3] a new version is installed and proved")
    shell = FakeShell()
    install(shell, T)
    states = await T.daily_update_check()
    by = {s.name: s for s in states}
    check("the tool with a newer release was updated", by["codex"].action == "updated",
          by["codex"].action)
    check("...from the old version to the new one",
          by["codex"].updated_from == "1.0.0" and by["codex"].installed == "1.0.1", str(by["codex"]))
    check("...and it was pinged", by["codex"].ping == "pong", by["codex"].ping)
    check("a tool already current was NOT touched", by["mcode"].action == "none", by["mcode"].action)
    check("...and was not pinged either", by["mcode"].ping == "skipped",
          "a ping costs money and proves nothing when nothing changed")
    check("openclaw reports not-applicable rather than a false pass",
          by["openclaw"].ping in {"skipped", "not-applicable"}, by["openclaw"].ping)
    check("the update used npm with an explicit @latest",
          any(c[:3] == ["npm", "install", "-g"] and c[3].endswith("@latest")
              for c in shell.calls), str(shell.calls[-3:]))

    print("\n[4] THE BOUND — a release that fails its ping is rolled back")
    shell = FakeShell()
    shell.pong = False
    install(shell, T)
    states = await T.daily_update_check()
    by = {s.name: s for s in states}
    check("the bad release was detected by the ping", by["codex"].ping == "no-pong",
          by["codex"].ping)
    check("...and rolled back", by["codex"].action == "rolled-back", by["codex"].action)
    check("...to the version that was working", shell.installed["@openai/codex"] == "1.0.0",
          shell.installed["@openai/codex"])
    check("...and the state says so for the report", by["codex"].broke, str(by["codex"]))
    rollback = [c for c in shell.calls if c[:3] == ["npm", "install", "-g"]
                and c[3].endswith("@1.0.0")]
    check("the rollback pinned the exact old version", bool(rollback), str(shell.calls[-2:]))

    print("\n[5] where rollback is impossible, it is said and not faked")
    shell = FakeShell()
    shell.native_after_update = "2.2.0"
    shell.pong = False
    install(shell, T)
    states = await T.daily_update_check(tools=(T.TOOLS[0],))
    claude = states[0]
    check("the native tool updated", claude.updated_from == "2.1.288", str(claude))
    check("the ping failed", claude.ping == "no-pong", claude.ping)
    check("no rollback was attempted", claude.action == "updated", claude.action)
    check("...and the report says it needs a look",
          "no verified downgrade" in claude.detail, claude.detail)
    check("...and it counts as broken", claude.broke)

    print("\n[6] a failed install is a failure, not a silent pass")
    shell = FakeShell()
    shell.update_fails = True
    install(shell, T)
    states = await T.daily_update_check()
    by = {s.name: s for s in states}
    check("the install failure is recorded", by["codex"].action == "update-failed",
          by["codex"].action)
    check("...it counts as broken", by["codex"].broke)
    check("...and nothing was pinged after it", by["codex"].ping == "skipped")

    print("\n[7] a quiet run is silent (D-29, D-34)")
    shell = FakeShell()
    shell.latest = dict(shell.installed)      # everything already current
    install(shell, T)
    states = await T.daily_update_check()
    check("nothing was updated", all(s.action == "none" for s in states),
          str([(s.name, s.action) for s in states]))
    check("the report is EMPTY", T.report(states) == "", T.report(states))
    shell = FakeShell()
    install(shell, T)
    states = await T.daily_update_check()
    line = T.report(states)
    check("a run that changed something does speak", bool(line), line)
    check("...and names the version transition", "1.0.0" in line and "1.0.1" in line, line)
    shell = FakeShell()
    shell.pong = False
    install(shell, T)
    line = T.report(await T.daily_update_check())
    check("a broken run leads with trouble", line.lower().startswith("trouble"), line)

    print("\n[8] no credential reaches a child that does not need it")
    os.environ["AFON_FAKE_TOOLCHAIN_SECRET"] = "sk-must-not-leak"
    os.environ["ANTHROPIC_API_KEY"] = "for-claude-only"
    os.environ["OPENAI_API_KEY"] = "for-codex-only"
    claude_env = T._child_env(next(s for s in T.TOOLS if s.name == "claude-code"))
    codex_env = T._child_env(next(s for s in T.TOOLS if s.name == "codex"))
    check("an unrelated secret reaches nobody",
          "AFON_FAKE_TOOLCHAIN_SECRET" not in claude_env
          and "AFON_FAKE_TOOLCHAIN_SECRET" not in codex_env)
    check("no AFON_* setting reaches a child", not any(k.startswith("AFON_") for k in codex_env))
    check("each tool gets its own key", claude_env.get("ANTHROPIC_API_KEY") == "for-claude-only"
          and codex_env.get("OPENAI_API_KEY") == "for-codex-only")
    check("...and not each other's", "OPENAI_API_KEY" not in claude_env
          and "ANTHROPIC_API_KEY" not in codex_env)
    check("npm can still resolve its global prefix", "PATH" in claude_env)
    for key in ("AFON_FAKE_TOOLCHAIN_SECRET", "ANTHROPIC_API_KEY", "OPENAI_API_KEY"):
        os.environ.pop(key, None)

    print("\n[9] the ping is a real acceptance test, not a version read")
    src = Path(T.__file__).read_text(encoding="utf-8")
    check("the pong check is case-insensitive and substring",
          '"pong"' in src and ".lower()" in src,
          "a strict equality check would fail on 'Pong!' and roll back a good release")
    shell = FakeShell()
    install(shell, T)
    verdict, _ = await T.ping(next(s for s in T.TOOLS if s.name == "codex"))
    check("a pong passes", verdict == "pong")
    shell.pong = False
    verdict, detail = await T.ping(next(s for s in T.TOOLS if s.name == "codex"))
    check("an answer without a pong fails", verdict == "no-pong", verdict)
    check("...and the detail quotes what it said instead", "rather not" in detail, detail)
    verdict, why = await T.ping(next(s for s in T.TOOLS if s.name == "openclaw"))
    check("a tool with no ping says not-applicable", verdict == "not-applicable", verdict)
    check("...and gives the reason", "gateway" in why, why)

    print("\n[10] the ledger remembers the last known-good version")
    shell = FakeShell()
    install(shell, T)
    await T.daily_update_check()
    ledger = json.loads(T.ledger_path().read_text(encoding="utf-8"))
    check("a proved version is recorded as known-good",
          (ledger.get("codex") or {}).get("known_good") == "1.0.1", str(ledger.get("codex")))
    check("the run is timestamped", bool(ledger.get("last_run")))
    check("the ledger is plain JSON a person can read at 2 AM",
          isinstance(ledger, dict) and "codex" in ledger)

    print("\n[11] the weekly review proposes and never applies (D-47, D-89)")
    kinds = [k for k, _ in T.IMPROVEMENT_KINDS]
    check("the improvement kinds are declared BY CODE",
          set(kinds) >= {"plugin", "command", "skill_doc", "mcp_server", "permission"},
          "Jev chooses among these; it cannot invent a capability for itself")
    check("'nothing' is one of the options", "nothing" in kinds,
          "without it, every week produces a change whether or not one is warranted")
    check("the module has no install path for a proposal",
          not any(bad in src for bad in ("plugin install", "mcp add", "npm install -g {")),
          "a proposal that could apply itself is not a proposal")

    shell = FakeShell()
    install(shell, T)

    class FakeVerdict:
        selected_id, confidence, outcome = "skill_doc", 0.81, "decided"

    class FakeJudge:
        async def judge(self, request, **kw):
            FakeJudge.seen = request
            return FakeVerdict()

    import afon.brain.judgment as J
    real_service = J.JudgmentService
    J.JudgmentService = lambda *a, **k: FakeJudge()  # type: ignore[assignment]
    try:
        proposals = await T.weekly_improvement_review(tools=(T.TOOLS[1],))
        p = proposals[0]
        check("Jev's pick is recorded", p.jev_kind == "skill_doc", p.jev_kind)
        check("...with its confidence", p.jev_confidence == 0.81)
        request = FakeJudge.seen
        check("every option handed to Jev came from the code's own list",
              {o.id for o in request.options} == set(kinds),
              str(sorted(o.id for o in request.options)))
        check("the question carries MEASURED friction, not an impression",
              "time(s)" in request.question and "failure(s)" in request.question,
              request.question[:140])
        check("the tool was also asked for its own view",
              bool(p.self_answer) or bool(p.self_error), str(p))
        check("...through its non-interactive entry point",
              any(c[:2] == ["codex", "exec"] for c in shell.calls), str(shell.calls[-1:]))
        line = T.review_report(proposals)
        check("the report states that nothing was changed",
              "nothing has been changed" in line.lower(), line[:160])
        check("...and asks before acting", "approval" in line.lower() or "say which" in line.lower(),
              line[-120:])
    finally:
        J.JudgmentService = real_service  # type: ignore[assignment]

    print("\n[12] a Jev outage degrades the review; it does not fail the job")
    class DeadJudge:
        async def judge(self, request, **kw):
            raise RuntimeError("typesafe unreachable")

    J.JudgmentService = lambda *a, **k: DeadJudge()  # type: ignore[assignment]
    try:
        proposals = await T.weekly_improvement_review(tools=(T.TOOLS[1],), ask_tools=False)
        check("the review still returns", len(proposals) == 1)
        check("...with no verdict rather than a guessed one", proposals[0].jev_kind == "")
        check("...and the outcome names the failure", "error" in proposals[0].jev_outcome,
              proposals[0].jev_outcome)
        line = T.review_report(proposals)
        check("the report says Jev had no verdict", "no verdict" in line.lower(), line[:160])
    finally:
        J.JudgmentService = real_service  # type: ignore[assignment]
        T._run = original_run

    print("\n[13] the jobs are scheduled, and the whole thing can be switched off")
    import afon.brain._scheduled_jobs as JOBS
    check("the 24h target exists", callable(getattr(JOBS, "_fire_toolchain_update", None)))
    check("the 168h target exists", callable(getattr(JOBS, "_fire_toolchain_review", None)))
    server_src = (Path(T.__file__).parent / "server.py").read_text(encoding="utf-8")
    check("the daily job is scheduled at 24h", "IntervalTrigger(hours=24" in server_src)
    check("the weekly job is scheduled at 168h", "IntervalTrigger(hours=168" in server_src)
    check("both carry jitter so four hosts do not hit the registry together",
          server_src.count("jitter=") >= 2)
    check("an unattended host mutation is behind a setting",
          "toolchain_autoupdate_enabled" in server_src)
    from afon.config import settings
    check("...and the setting exists", isinstance(settings.toolchain_autoupdate_enabled, bool))

    print(f"\n=== {passed + failed} checks: {passed} passed, {failed} failed ===")
    if not failed:
        print("ALL CHECKS PASSED ===")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
