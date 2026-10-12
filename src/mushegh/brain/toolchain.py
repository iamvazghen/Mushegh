"""The executor toolchain keeps itself current, and once a week asks how it could be better.

Two jobs, both the owner's ask of 2026-10-06:

* **every 24 h** — check Claude Code, Codex, OpenClaw and MiniMax Code for a new version, install
  it, and prove the path still works with a ping that must come back as a pong. A version that
  fails its ping is **rolled back** where the package manager allows it.
* **every 168 h** — ask what each tool is *missing*: a plugin, a command, a skill document, an MCP
  server, a permission. Jev ranks candidates code produced; the tools themselves are asked what
  they would add; nothing is applied. See :func:`weekly_improvement_review`.

**Everything below was measured on this host rather than assumed**, because the obvious version of
this module is a table of plausible commands and the obvious version is wrong:

| Tool | How it is installed | What `--version` does |
|---|---|---|
| `claude` 2.1.288 | native, `~/.local/bin/claude.EXE` | prints the version |
| `codex` | npm `@openai/codex` | prints `codex-cli <v>` |
| `mcode` | npm `@minimax-ai/code` | prints the bare version |
| `openclaw` | npm `openclaw` | **hangs.** `openclaw --help` timed out at 40 s with no output |

That last row decides the design. The installed version of an npm tool is read from
``npm ls -g --json`` and not from the CLI, because one of the four cannot answer, and a version
check that hangs once a day is worse than none. It is also why OpenClaw gets **no model ping**: its
CLI needs the gateway and a live agent id, so a daily ping would either hang or spend tokens to
learn nothing. Its health check is that the binary and its version are readable.

**The asymmetry worth knowing before trusting this:** npm can roll back, so a failed ping restores
the previous version. Claude Code is installed by its own native updater and this module has no
verified downgrade command for it, so a failed ping there is **reported loudly and not repaired**.
Pretending otherwise would be the worse failure.

**Why the ping is not daily.** A model round trip costs money on three of the four. It runs only
when a version actually *changed*, which is also the only moment it answers anything: proving the
path worked yesterday tells you nothing about today's release.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from loguru import logger

from mushegh.shared.paths import state_dir

#: Seconds a version probe may take. Generous: npm on Windows is slow and a false "missing" would
#: read as an uninstalled tool.
PROBE_TIMEOUT_S = 90
#: Seconds an update may take.
UPDATE_TIMEOUT_S = 600
#: Seconds a ping may take. A coding CLI starting cold on Windows is not quick.
PING_TIMEOUT_S = 180

#: The word the ping must come back with. Lower-cased substring match: these tools wrap an answer
#: in pleasantries and a strict equality check would fail on "Pong!" and roll back a good release.
PONG = "pong"
PING_PROMPT = "Reply with exactly one word: pong"


@dataclass(frozen=True)
class ToolSpec:
    """One managed CLI. Every field here was read off this machine, not inferred."""

    name: str
    #: ``npm`` tools are version-checked and updated through npm, which is also what makes a
    #: rollback possible. ``native`` tools own their own updater.
    kind: str
    #: The executable as it appears on PATH.
    binary: str
    #: npm package name, for ``kind == "npm"``.
    package: str = ""
    #: argv that prints the installed version, for ``kind == "native"``.
    version_argv: tuple[str, ...] = ()
    #: argv that updates a native tool.
    update_argv: tuple[str, ...] = ()
    #: argv that sends one prompt and prints the answer. Empty means this tool is not pinged.
    ping_argv: tuple[str, ...] = ()
    #: Environment names the child may inherit beyond the base set.
    env_allow: tuple[str, ...] = ()
    #: False when no verified downgrade command exists.
    can_rollback: bool = True
    #: Why there is no ping, when there is none. Stated so the gap is visible in a report.
    no_ping_because: str = ""


TOOLS: tuple[ToolSpec, ...] = (
    ToolSpec(
        name="claude-code", kind="native", binary="claude",
        version_argv=("claude", "--version"),
        update_argv=("claude", "update"),
        ping_argv=("claude", "-p", PING_PROMPT),
        env_allow=("ANTHROPIC_API_KEY",),
        # The native installer has no downgrade command this module can verify, so it does not
        # claim one. A failed ping is reported rather than silently "fixed".
        can_rollback=False,
    ),
    ToolSpec(
        name="codex", kind="npm", binary="codex", package="@openai/codex",
        ping_argv=("codex", "exec", PING_PROMPT),
        env_allow=("OPENAI_API_KEY",),
    ),
    ToolSpec(
        name="mcode", kind="npm", binary="mcode", package="@minimax-ai/code",
        # `mcode exec [prompt]` runs one prompt without the TUI — read off `mcode --help`, not
        # guessed. `mcode update` also exists, but npm is used so a rollback stays possible.
        ping_argv=("mcode", "exec", PING_PROMPT),
        env_allow=("MINIMAX_API_KEY",),
    ),
    ToolSpec(
        name="openclaw", kind="npm", binary="openclaw", package="openclaw",
        no_ping_because=("its CLI needs the gateway and a live agent id; `openclaw --help` timed "
                         "out at 40s with no output on this host, so a daily ping would hang or "
                         "spend tokens to learn nothing"),
    ),
)

#: Where the last known-good versions live, so a rollback has something to roll back to and a
#: report can say what changed. One small JSON file, readable with `cat` at 2 AM (D-01).
def ledger_path() -> Path:
    return state_dir() / "toolchain.json"


def _base_env() -> dict[str, str]:
    """The same allowlist discipline as the executor contract: build up, never filter down."""
    keep = ("PATH", "HOME", "USERPROFILE", "SystemRoot", "SystemDrive", "COMSPEC",
            "TEMP", "TMP", "TMPDIR", "LANG", "LC_ALL", "TZ", "PATHEXT", "APPDATA",
            "LOCALAPPDATA", "NPM_CONFIG_PREFIX")
    return {k: os.environ[k] for k in keep if k in os.environ}


def _child_env(spec: ToolSpec) -> dict[str, str]:
    env = _base_env()
    for name in spec.env_allow:
        if name in os.environ:
            env[name] = os.environ[name]
    return env


async def _run(argv: list[str], *, timeout: float, env: dict[str, str] | None = None,
               cwd: str | None = None) -> tuple[int, str, str]:
    """Run one process with no shell and nothing on stdin. Never raises."""
    resolved = shutil.which(argv[0]) or argv[0]
    try:
        proc = await asyncio.create_subprocess_exec(
            resolved, *argv[1:],
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env or _base_env(),
            cwd=cwd,
        )
    except FileNotFoundError:
        return 127, "", f"{argv[0]} is not installed"
    except Exception as e:  # noqa: BLE001
        return 126, "", f"{argv[0]} could not start: {e}"
    try:
        out, err = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        try:
            proc.kill()
        except Exception:  # noqa: BLE001
            pass
        return 124, "", f"{argv[0]} exceeded {int(timeout)}s"
    return (proc.returncode if proc.returncode is not None else -1,
            (out or b"").decode("utf-8", "replace").strip(),
            (err or b"").decode("utf-8", "replace").strip())


_SEMVER = re.compile(r"(\d+\.\d+\.\d+(?:-[0-9A-Za-z.\-]+)?)")


def parse_version(text: str) -> str:
    """The first semver-looking token in a line of CLI output.

    Needed because the four tools disagree: `claude --version` prints
    ``2.1.288 (Claude Code)``, `codex --version` prints ``codex-cli 0.160.0``, and
    `mcode --version` prints a bare ``0.6.3``.
    """
    match = _SEMVER.search(text or "")
    return match.group(1) if match else ""


async def npm_installed() -> dict[str, str]:
    """Installed global npm packages, as ``{package: version}``.

    Read from npm rather than from each CLI because one of the four hangs when asked. One npm call
    answers for all three npm tools, which also keeps the daily job to a handful of processes.
    """
    code, out, err = await _run(["npm", "ls", "-g", "--depth=0", "--json"],
                               timeout=PROBE_TIMEOUT_S)
    if not out:
        logger.warning(f"toolchain: npm ls returned nothing (exit {code}) {err[:200]}")
        return {}
    try:
        data = json.loads(out)
    except ValueError:
        # npm prints warnings before the JSON often enough that this is worth surviving.
        start = out.find("{")
        try:
            data = json.loads(out[start:]) if start >= 0 else {}
        except ValueError:
            logger.warning("toolchain: npm ls output was not JSON")
            return {}
    deps = data.get("dependencies") or {}
    return {name: str((info or {}).get("version") or "") for name, info in deps.items()}


async def npm_latest(package: str) -> str:
    """The newest published version of a package, or "" when the network says nothing."""
    code, out, err = await _run(["npm", "view", package, "version"], timeout=PROBE_TIMEOUT_S)
    if code != 0:
        logger.warning(f"toolchain: npm view {package} failed ({code}) {err[:160]}")
        return ""
    return parse_version(out) or out.strip()


@dataclass
class ToolState:
    """What this job learned about one tool on one run."""

    name: str
    installed: str = ""
    latest: str = ""
    updated_from: str = ""
    action: str = "none"        # none | updated | update-failed | rolled-back | rollback-failed
    ping: str = "skipped"       # skipped | pong | no-pong | error | not-applicable
    detail: str = ""

    @property
    def broke(self) -> bool:
        return self.action in {"update-failed", "rollback-failed"} or self.ping == "no-pong"

    @property
    def changed(self) -> bool:
        return self.action in {"updated", "rolled-back"}


async def installed_version(spec: ToolSpec, npm_map: dict[str, str] | None = None) -> str:
    if spec.kind == "npm":
        return (npm_map or {}).get(spec.package, "")
    code, out, err = await _run(list(spec.version_argv), timeout=PROBE_TIMEOUT_S,
                                env=_child_env(spec))
    if code != 0:
        logger.warning(f"toolchain: {spec.name} --version exit {code} {err[:160]}")
        return ""
    return parse_version(out)


async def ping(spec: ToolSpec) -> tuple[str, str]:
    """Send a ping and require a pong. Returns ``(verdict, detail)``.

    This is the owner's own acceptance test for an update: a tool whose binary runs but whose model
    path is broken is a tool that will fail on the first real brief instead of here.
    """
    if not spec.ping_argv:
        return "not-applicable", spec.no_ping_because
    code, out, err = await _run(list(spec.ping_argv), timeout=PING_TIMEOUT_S,
                                env=_child_env(spec))
    body = f"{out}\n{err}".lower()
    if PONG in body:
        return "pong", ""
    if code != 0:
        return "error", f"exit {code}: {(err or out)[:200]}"
    return "no-pong", f"answered without a pong: {(out or err)[:200]}"


async def update(spec: ToolSpec, *, to: str = "latest") -> tuple[bool, str]:
    """Install a version. ``to`` is a version string or ``latest``."""
    if spec.kind == "npm":
        argv = ["npm", "install", "-g", f"{spec.package}@{to}"]
    else:
        if to != "latest":
            return False, f"{spec.name} has no verified downgrade command"
        argv = list(spec.update_argv)
    code, out, err = await _run(argv, timeout=UPDATE_TIMEOUT_S, env=_child_env(spec))
    if code != 0:
        return False, f"exit {code}: {(err or out)[:300]}"
    return True, (out or "")[:300]


def _load_ledger() -> dict[str, Any]:
    try:
        return json.loads(ledger_path().read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 — a missing or corrupt ledger is a first run
        return {}


def _save_ledger(data: dict[str, Any]) -> None:
    try:
        path = ledger_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=1, sort_keys=True), encoding="utf-8")
    except Exception as e:  # noqa: BLE001
        logger.warning(f"toolchain: could not write the ledger: {e}")


async def daily_update_check(*, tools: tuple[ToolSpec, ...] | None = None,
                             allow_update: bool = True) -> list[ToolState]:
    """The 24-hour job: find new versions, install them, and prove the path still works.

    Order matters and is deliberate: **one tool at a time, each proved before the next is touched.**
    Updating all four and then pinging all four would leave four suspects for one failure.
    """
    specs = tools if tools is not None else TOOLS
    ledger = _load_ledger()
    npm_map = await npm_installed() if any(s.kind == "npm" for s in specs) else {}
    states: list[ToolState] = []

    for spec in specs:
        state = ToolState(name=spec.name)
        state.installed = await installed_version(spec, npm_map)
        if not state.installed:
            state.detail = "not installed on this host"
            states.append(state)
            continue

        known_good = str((ledger.get(spec.name) or {}).get("known_good") or "")

        if spec.kind == "npm":
            state.latest = await npm_latest(spec.package)
            needs = bool(state.latest) and state.latest != state.installed
        else:
            # A native updater is its own check: there is no separate "is there a newer one" call,
            # so the honest shape is to run it and compare the version before and after.
            needs = True

        if not needs or not allow_update:
            if state.installed and not known_good:
                ledger.setdefault(spec.name, {})["known_good"] = state.installed
            states.append(state)
            continue

        before = state.installed
        ok, detail = await update(spec)
        after = await installed_version(
            spec, await npm_installed() if spec.kind == "npm" else None)
        state.detail = detail

        if not ok:
            state.action = "update-failed"
            states.append(state)
            continue
        if after == before:
            # A native updater that found nothing to do. Not a failure, and not worth a word.
            state.installed = after or before
            ledger.setdefault(spec.name, {})["known_good"] = state.installed
            states.append(state)
            continue

        state.installed, state.updated_from, state.action = after, before, "updated"
        state.ping, ping_detail = await ping(spec)
        if ping_detail:
            state.detail = ping_detail

        if state.ping in {"pong", "not-applicable"}:
            ledger.setdefault(spec.name, {})["known_good"] = after
        elif spec.can_rollback and before:
            rolled, roll_detail = await update(spec, to=before)
            state.action = "rolled-back" if rolled else "rollback-failed"
            state.detail = f"{state.detail} | rollback: {roll_detail}"[:600]
            if rolled:
                state.installed = before
        else:
            state.detail = (f"{state.detail} | no verified downgrade for {spec.name}; it is left "
                            f"on {after} and needs a look")[:600]
        states.append(state)

    ledger["last_run"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    _save_ledger(ledger)
    _audit_run(states)
    return states


def _audit_run(states: list[ToolState]) -> None:
    try:
        from mushegh.brain import audit

        for s in states:
            if s.action == "none" and s.ping == "skipped":
                continue      # nothing happened; an audit line per quiet day is noise
            audit.record(
                tool=f"toolchain:{s.name}",
                args={"from": s.updated_from, "to": s.installed, "action": s.action},
                result=f"ping={s.ping} {s.detail}"[:500],
                ok=not s.broke,
                actor="mushegh:toolchain",
                decision="allow",
                rule="D-88 bounded auto-update of the four managed CLIs",
            )
    except Exception as e:  # noqa: BLE001
        logger.warning(f"toolchain: could not write the audit lines: {e}")


def report(states: list[ToolState]) -> str:
    """One line for the owner, or an empty string when there is nothing worth saying.

    D-29 and D-34 together: a daily job that reports "nothing changed" every day is a daily
    interruption bought with no information. Silence is the correct output of a quiet run.
    """
    broke = [s for s in states if s.broke]
    changed = [s for s in states if s.changed and not s.broke]
    if not broke and not changed:
        return ""
    parts: list[str] = []
    if broke:
        parts.append("Trouble, sir: " + "; ".join(
            f"{s.name} {s.action}" + (" and did not answer the ping" if s.ping == "no-pong" else "")
            + (f" — {s.detail[:160]}" if s.detail else "") for s in broke))
    if changed:
        parts.append("Updated: " + "; ".join(
            f"{s.name} {s.updated_from} → {s.installed}"
            + (" (ping ok)" if s.ping == "pong" else
               " (no ping on this one)" if s.ping == "not-applicable" else "")
            for s in changed))
    return " ".join(parts)


# ── the weekly review ─────────────────────────────────────────────────────────────────────────

#: The improvement kinds a tool can actually receive. **Code produces this list**; Jev ranks it.
#: That ordering is D-47 and D-81 in one place: a model may choose among what the system already
#: knows how to do, and may never invent a capability for itself.
IMPROVEMENT_KINDS: tuple[tuple[str, str], ...] = (
    ("plugin", "install or enable a plugin the tool already supports"),
    ("command", "add a reusable command or alias for a task that recurs"),
    ("skill_doc", "write a skill or AGENTS.md document so the tool stops being re-briefed"),
    ("mcp_server", "connect an MCP server so the tool can reach a system it cannot today"),
    ("permission", "widen or narrow what the tool is allowed to do without being asked"),
    ("model", "change which model or provider the tool uses"),
    ("nothing", "leave this tool alone; the friction is elsewhere"),
)

#: What each tool is asked about itself. A read-only question with no repo and no write path.
SELF_QUESTION = (
    "You are being asked one question about your own setup, and the answer is advisory only — "
    "nothing will be installed or changed automatically. In at most 120 words: what ONE addition "
    "to your own configuration would most reduce the friction in the work you are given — a "
    "plugin, a reusable command, a skill or AGENTS.md document, an MCP server, or a permission? "
    "Name it, say what it would cost, and say what would break if it were wrong."
)


@dataclass
class ToolProposal:
    """One week's answer for one tool. Advisory, both halves of it."""

    name: str
    jev_kind: str = ""
    jev_confidence: float | None = None
    jev_outcome: str = ""
    friction: dict[str, int] = field(default_factory=dict)
    self_answer: str = ""
    self_error: str = ""


def _friction(name: str, *, limit: int = 400) -> dict[str, int]:
    """How this tool has actually misbehaved, from the audit trail rather than from an impression.

    Jev is given measured friction, not a vibe. The 2026-09-20 lesson applies directly: a question
    asked against a *summary* came back at confidence 0.19, and the same question asked against the
    source came back at 0.95.
    """
    counts = {"runs": 0, "failures": 0, "timeouts": 0, "refusals": 0}
    try:
        from mushegh.brain import audit

        for row in audit.recent(limit=limit):
            tool = str(row.get("tool") or "")
            if not tool.endswith(name) and name not in tool:
                continue
            counts["runs"] += 1
            if not row.get("ok", True):
                counts["failures"] += 1
            blob = f"{row.get('result') or ''}".lower()
            if "exceeded" in blob or "deadline" in blob or "timed out" in blob:
                counts["timeouts"] += 1
            if str(row.get("decision") or "") not in ("allow", ""):
                counts["refusals"] += 1
    except Exception as e:  # noqa: BLE001
        logger.warning(f"toolchain: could not read friction for {name}: {e}")
    return counts


async def _ask_jev(name: str, friction: dict[str, int]) -> ToolProposal:
    """Ask Jev which improvement kind would help this tool most, among the kinds code declared."""
    proposal = ToolProposal(name=name, friction=friction)
    try:
        from mushegh.brain.judgment import DecisionOption, DecisionRequest, JudgmentService

        question = (
            f"The external tool '{name}' is used to do delegated work. Over the last period it was "
            f"called {friction.get('runs', 0)} time(s), with {friction.get('failures', 0)} "
            f"failure(s), {friction.get('timeouts', 0)} timeout(s) and "
            f"{friction.get('refusals', 0)} refusal(s). Which single change to the tool's own "
            f"setup would most reduce that friction?"
        )
        request = DecisionRequest(
            question=question,
            options=tuple(DecisionOption(id=kind, text=f"{kind}: {text}")
                          for kind, text in IMPROVEMENT_KINDS),
            kind="toolchain_improvement",
        )
        verdict = await JudgmentService().judge(request)
        proposal.jev_kind = verdict.selected_id or ""
        proposal.jev_confidence = verdict.confidence
        proposal.jev_outcome = verdict.outcome
    except Exception as e:  # noqa: BLE001 — a weekly advisory must never take the brain down
        logger.warning(f"toolchain: Jev review failed for {name}: {e}")
        proposal.jev_outcome = f"error: {type(e).__name__}"
    return proposal


async def _ask_tool(spec: ToolSpec, proposal: ToolProposal) -> None:
    """Ask the tool itself, through its own non-interactive entry point.

    This is a **read** brief: no repo, no write path, no diff. The answer is prose for the owner to
    read, and the only thing it can cause is an approval request he may decline.
    """
    if not spec.ping_argv:
        proposal.self_error = spec.no_ping_because or "this tool has no non-interactive entry point"
        return
    argv = list(spec.ping_argv[:-1]) + [SELF_QUESTION]
    code, out, err = await _run(argv, timeout=PING_TIMEOUT_S, env=_child_env(spec))
    if code != 0 or not out.strip():
        proposal.self_error = f"exit {code}: {(err or out)[:200]}"
        return
    proposal.self_answer = out.strip()[:1500]


async def weekly_improvement_review(*, tools: tuple[ToolSpec, ...] | None = None,
                                    ask_tools: bool = True) -> list[ToolProposal]:
    """The 168-hour job: Jev ranks code-declared improvements; the tools add their own view.

    **Nothing here is applied, and that is the design rather than a limitation.** D-47 is explicit
    that a model evaluation is advisory input and that de-scoping — or scoping *up* — is the
    owner's. Installing a plugin, adding an MCP server or widening a permission changes what the
    system is willing to do, which is exactly the class of decision a model never makes here. So
    this produces a report and queued approvals, and the owner's "yes" is the thing that acts.
    """
    specs = tools if tools is not None else TOOLS
    proposals: list[ToolProposal] = []
    for spec in specs:
        friction = _friction(spec.name)
        proposal = await _ask_jev(spec.name, friction)
        if ask_tools:
            await _ask_tool(spec, proposal)
        proposals.append(proposal)
    _save_review(proposals)
    return proposals


def _save_review(proposals: list[ToolProposal]) -> None:
    ledger = _load_ledger()
    ledger["last_review"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    ledger["review"] = [
        {"tool": p.name, "jev": p.jev_kind, "confidence": p.jev_confidence,
         "outcome": p.jev_outcome, "friction": p.friction,
         "self": p.self_answer, "self_error": p.self_error}
        for p in proposals
    ]
    _save_ledger(ledger)


def review_report(proposals: list[ToolProposal]) -> str:
    """The weekly note. Always says it is advisory, because it always is."""
    if not proposals:
        return ""
    lines = ["Weekly toolchain review, sir — all of this is a proposal, nothing has been changed."]
    for p in proposals:
        bits = [f"**{p.name}**"]
        if p.jev_kind and p.jev_kind != "nothing":
            conf = f" (confidence {p.jev_confidence:.2f})" if p.jev_confidence is not None else ""
            bits.append(f"Jev would {p.jev_kind}{conf}.")
        elif p.jev_kind == "nothing":
            bits.append("Jev would leave it alone.")
        else:
            bits.append(f"Jev had no verdict ({p.jev_outcome or 'unavailable'}).")
        if p.friction.get("runs"):
            bits.append(f"{p.friction['runs']} run(s), {p.friction.get('failures', 0)} failed.")
        if p.self_answer:
            bits.append(f"It says: {p.self_answer[:400]}")
        elif p.self_error:
            bits.append(f"It could not be asked: {p.self_error[:160]}")
        lines.append(" ".join(bits))
    lines.append("Say which of these you want and I will prepare it for your approval.")
    return "\n".join(lines)
