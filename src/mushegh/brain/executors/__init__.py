"""M41 — one contract for every external executor Mushegh delegates to (D-79, D-80, D-85).

The owner's 2026-10-06 direction splits the work by domain: daily life and business go to the
fleet, coding goes to the corporate coding CLIs, money goes to Ruben, reading goes to his own
summarisation SDK. His 2026-10-11 direction sharpened two of those: **coding runs down one ordered
pipeline** -- Claude Code, then mcode, then Mistral Vibe (`CODING_CHAIN`) -- and **frontend work
does not come here at all**, it goes to the Open Design MCP tools (`FRONTEND_ROUTE`). Mushegh keeps
the voice, the judgement, the typed boundary and the audit trail.

**Why one contract instead of four integrations.** Four bespoke clients would mean four cost
accountings, four audit shapes and four failure modes to diagnose at 2 AM — which is the argument
D-01 makes against this whole direction. So every executor is a *row in a table* plus one runner:
an argv template, a domain, a tier, and a parser. `dispatch()` is the only place that spends money,
writes an audit line, or touches a subprocess.

**The four invariants this module exists to hold:**

1. **A brief with no acceptance check is refused before dispatch.** The thing that makes delegation
   safe is knowing what "done" looks like before someone else does the work (D-79, 39.R1 — the
   registry calls the delegation layer "built, thin" precisely because the verification half is
   thin). An un-checkable brief is not a small brief, it is an unverifiable one.
2. **A non-zero exit never reads as success.** `Result.ok` is computed, never passed in. The
   failure this prevents is the one that cost the project a FIFA-26 gaffe in another form: an
   executor that printed something plausible and exited 1.
3. **The child gets no credentials.** `_child_env()` is an allowlist, not a filter — it starts
   empty and adds what a process needs to run. D-80 says an executor receives a brief and a repo,
   never `.env`, the vault, or a biometric template, and an allowlist is the only shape of that
   rule which stays true when a new secret is added to the environment later.
4. **An executor never lands anything.** The product is a transcript and, for coding, a diff. D-08
   owns what happens next — dedicated branch, green suite, no schema migration, the owner's
   explicit approval — and that path is `code_improve.py`, not this module.

`dispatch()` runs one brief through one executor; `dispatch_chain()` walks the fallback chain and
is what "first fallback" and "second fallback" actually mean -- each is tried only when the one
before it FAILED, judged by `Result.ok` and never by prose.

    uv run python bench/test_executor_contract.py
    uv run python bench/test_coding_chain.py
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import time
from enum import Enum
from pathlib import Path

from loguru import logger
from pydantic import BaseModel, Field, field_validator, model_validator

from mushegh.brain import never_store

__all__ = [
    "Brief", "BriefRefused", "Domain", "ExecutorSpec", "Result", "Tier",
    "SPECS", "PARSERS", "CODING_CHAIN", "FRONTEND_ROUTE",
    "available", "candidates", "dispatch", "dispatch_chain", "pick", "resolve",
    "wants_task_file",
    "status",
    "storage_class",
]


class Domain(str, Enum):
    """What kind of work a brief is. The owner's own split, 2026-10-06."""

    CODING = "coding"        # corporate coding CLIs, in the owner's order — see CODING_CHAIN
    FRONTEND = "frontend"    # websites, landing pages, UI/UX, design decisions — Open Design MCP
    DAILY = "daily"          # personal errands and admin — OpenClaw, free models
    BUSINESS = "business"    # corporate and business management — OpenClaw, best models
    FINANCE = "finance"      # finances, taxes, investments, portfolio, salary — Ruben (D-83)
    READING = "reading"      # summarisation — the owner's own SDK (D-86)


class Tier(str, Enum):
    """Which model pool pays for this. Personal work runs on free models by owner's decision."""

    PERSONAL = "personal"
    CORPORATE = "corporate"


class BriefRefused(ValueError):
    """A brief that must not be dispatched. Raised before any process starts."""


class Brief(BaseModel):
    """A unit of delegated work. Validated before anything leaves this process (D-04)."""

    model_config = {"frozen": True, "extra": "forbid"}

    domain: Domain
    task: str = Field(min_length=8)
    #: How Mushegh will know the work is done. Required — see invariant 1 in the module docstring.
    acceptance: str = Field(min_length=4)
    tier: Tier = Tier.PERSONAL
    #: Absolute path the executor may work in. Coding briefs need one; others must not have one.
    repo: str | None = None
    #: Seconds. A delegation with no deadline is never late, which is why it always has one.
    timeout_s: int = Field(default=900, ge=5, le=7200)

    @field_validator("task", "acceptance")
    @classmethod
    def _no_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("must not be whitespace")
        return v.strip()

    @model_validator(mode="after")
    def _tier_matches_domain(self) -> "Brief":
        """The owner's own split, enforced where it is written down rather than discovered later.

        "Coding is taken by the corporate CLI's" - so a coding brief on the personal tier matches
        no executor. Without this it still failed, but as `no configured executor serves
        coding/personal`, which reads as a missing install rather than a contradiction in the
        brief. Refusing here says what to change. The tier is NOT silently upgraded: a brief that
        says personal and means corporate is a caller that has the split wrong, and rewriting it
        quietly is how the free-model pool ends up paying for corporate work.
        """
        if self.domain is Domain.CODING and self.tier is not Tier.CORPORATE:
            raise ValueError(
                "coding goes to the corporate CLIs by the owner's own routing - "
                "pass tier=Tier.CORPORATE"
            )
        return self

    @field_validator("repo")
    @classmethod
    def _repo_absolute(cls, v: str | None) -> str | None:
        if v is None:
            return None
        if not os.path.isabs(v):
            raise ValueError("repo must be an absolute path")
        return v


class Result(BaseModel):
    """What came back. ``ok`` is derived from the exit code and never supplied by a caller."""

    model_config = {"frozen": True, "extra": "forbid"}

    executor: str
    domain: Domain
    exit_code: int
    transcript: str = ""
    #: A unified diff the executor proposes. Mushegh never applies one here (D-08).
    diff: str | None = None
    seconds: float = 0.0
    error: str = ""

    @property
    def ok(self) -> bool:
        """Invariant 2. Exit code decides; prose never does."""
        return self.exit_code == 0 and not self.error


class ExecutorSpec(BaseModel):
    """One executor, as data. Adding one is a row here plus a parser, not a module."""

    model_config = {"frozen": True, "extra": "forbid"}

    name: str
    domains: tuple[Domain, ...]
    tiers: tuple[Tier, ...] = (Tier.PERSONAL, Tier.CORPORATE)
    #: argv, with ``{task}`` / ``{acceptance}`` / ``{repo}`` substituted. argv form, never a shell
    #: string: there is no shell here, which is the whole of D-80's "never an interactive shell".
    argv: tuple[str, ...]
    #: Extra environment names this executor is allowed to inherit — its own API key, nothing else.
    env_allow: tuple[str, ...] = ()
    #: True when the executor emits a machine-readable result it enforces itself. Codex's
    #: ``--output-schema`` is the example worth copying: the caller declares the result shape, so
    #: the executor cannot return an unvalidated blob even in principle.
    structured_output: bool = False
    #: Which transcript parser to use, by name. A *name* and not a callable, because a spec is a
    #: frozen Pydantic model and a function field would make it unhashable and unprintable in an
    #: audit line. ``""`` means the output is already prose.
    parser: str = ""
    #: A ``never_store`` class this executor's output always belongs to, or None. D-83 promises that
    #: a financial position stays in RUBEN's store and never reaches memory, the vault or the audit
    #: trail — and a *declaration* is the only honest way to enforce that, because "EUR 2,400" is a
    #: balance, a salary or the price of a bicycle and prose cannot tell them apart. The executor
    #: knows; the boundary would be guessing.
    declares_never_store: str | None = None
    #: Set when the binary IS on this host but the interface in ``argv`` does not exist, so the row
    #: is a statement of intent rather than a route. ``available()`` is then False and ``resolve()``
    #: refuses with this sentence — which is the whole point: a spec whose argv has never been run
    #: is a placeholder, and a placeholder that passes ``shutil.which`` is worse than a missing row,
    #: because it reads as configured right up to the moment somebody needs it.
    unavailable_because: str | None = None

    @field_validator("argv")
    @classmethod
    def _no_interpreter(cls, v: tuple[str, ...]) -> tuple[str, ...]:
        """D-05's line, enforced where a spec is constructed rather than only in a test.

        D-05 says the line erodes "the moment an agent is handed an unconstrained interactive shell
        with root or network access", and D-80 draws that line at *interactive*. A spec is data, and
        data gets edited by whoever is adding the next executor — so the refusal belongs in the type
        rather than in a grep over the file. ``python -c`` stays allowed: it is how the gate drives
        a fake executor, and it is not a shell.
        """
        if not v:
            raise ValueError("argv must not be empty")
        head = v[0].replace("\\", "/").rsplit("/", 1)[-1].lower()
        head = head.rsplit(".", 1)[0] if head.endswith((".exe", ".com")) else head
        if head in {"sh", "bash", "zsh", "dash", "ksh", "fish", "csh", "tcsh",
                    "cmd", "command", "powershell", "pwsh", "wsl", "ssh"}:
            raise ValueError(
                f"{v[0]!r} is a command interpreter; an executor is a non-interactive process "
                "with a diff as its product (D-05, D-80)"
            )
        return v


#: The table. Every command below is non-interactive by construction — `codex exec`, `claude -p`,
#: `mcode exec`, `openclaw agent --json`. As of 2026-10-06 all of them ARE on this host (an earlier
#: version of this comment said none was, which measurement contradicted), so `available()` earns
#: its keep differently: it is measured per call with `shutil.which`, which is what keeps D-81's
#: "never name an unconfigured executor" true without a separate check or a setting to drift.
SPECS: tuple[ExecutorSpec, ...] = (
    ExecutorSpec(
        name="claude-code",
        domains=(Domain.CODING,),
        tiers=(Tier.CORPORATE,),
        argv=("claude", "-p", "{task}", "--output-format", "stream-json", "--verbose"),
        env_allow=("ANTHROPIC_API_KEY",),
        parser="stream_json",
    ),
    ExecutorSpec(
        name="mcode",
        domains=(Domain.CODING,),
        tiers=(Tier.CORPORATE,),
        # Measured from `mcode exec --help` on this host (@minimax-ai/code 0.6.3), not assumed.
        # It is the richest of the three interfaces: `--output-format stream-json`, `--output-schema`
        # and an explicit `--permission` policy, which is exactly the shape D-80 asks for. The
        # policy stays at its default `smart` rather than `full`: the executor already runs inside a
        # throwaway worktree (D-90), so widening it would buy nothing and spend the bound.
        argv=("mcode", "exec", "--output-format", "stream-json", "--prompt-mode", "coding",
              "--permission", "smart", "{task}"),
        env_allow=("MINIMAX_API_KEY",),
        structured_output=True,
        # Reuses claude's parser deliberately: both advertise `stream-json`, and `parse_stream_json`
        # is tolerant by design — a line that is not JSON is kept as text rather than dropped, which
        # is the correct default for a stream whose exact event names this project has not yet seen
        # from a real run. The registry records that as unverified rather than claiming it.
        parser="stream_json",
    ),
    ExecutorSpec(
        name="vibe",
        domains=(Domain.CODING,),
        tiers=(Tier.CORPORATE,),
        # Mistral Vibe 2.26.1, measured from its own `--help` on this host. `-p` is programmatic
        # mode: send the prompt, print the result, exit. `--output json` emits one JSON ARRAY of
        # session entries (not JSONL like the other two), which is why it has its own parser.
        # `--smart-approve` is the bounded policy, the same choice mcode's `--permission smart`
        # makes: the executor already runs in a throwaway worktree (D-90), so `--auto-approve`
        # would spend the bound and buy nothing. `--time-limit` lets it write its export and exit
        # with a transcript rather than being killed by `dispatch()` — a killed process loses the
        # thing that explains what happened.
        argv=("vibe", "-p", "{task}", "--output", "json", "--smart-approve",
              "--time-limit", "{timeout}"),
        env_allow=("MISTRAL_API_KEY",),
        parser="vibe_json",
    ),
    # Both agent ids below were PLACEHOLDERS until 2026-10-07, when the fleet config on the VPS
    # was read: `personal` and `business` are real, live agents and have been all along (the full
    # roster is ispir, finance, security, realty, business, creative-research, dev-systems,
    # personal). Two things found at the same time are worth carrying here rather than in a doc:
    #
    #   * `--message-file <path>` exists, so the task does NOT have to be an argv string. On
    #     Windows `openclaw` resolves to a `.CMD` shim whose arguments a command interpreter
    #     re-parses, which is why `_batch_hazard` refuses a brief containing `&` or a quote. A file
    #     removes the hazard instead of refusing the brief - which is exactly the fix that
    #     function's own docstring named. `{task_file}` is substituted by `dispatch()`.
    #   * `--deliver` defaults to FALSE, and Mushegh never passes it. So an agent turn produces a
    #     reply and sends nothing to any channel - the owner-consent property for free, in the
    #     transport rather than in a prompt. `test_fleet_transport.py` asserts the flag's absence.
    #
    # `--timeout` is given the brief's own deadline so the CLI exits with a transcript instead of
    # being killed by `dispatch()`; a killed process loses the thing that explains what happened.
    # CORRECTED 2026-10-11: these two named `personal` and `business`, which were real agents of
    # the EIGHT-agent fleet deleted on 2026-10-08. They do not exist in the eighteen-agent fleet
    # that replaced it, so both specs addressed nobody. Their roles are now owned by `tatev`
    # (Personal operations, A05) and `tamara` (Business and vendor operations, A06) — read off the
    # live roster, not guessed. `mushegh.brain.roster` is the authority on who owns what; this
    # table is the authority on how a BRIEF is dispatched, and the two answer different questions:
    # a consult goes through `fleet.ask` over A2A, a brief with an acceptance check comes here.
    ExecutorSpec(
        name="openclaw-personal",
        domains=(Domain.DAILY,),
        tiers=(Tier.PERSONAL,),
        argv=("openclaw", "agent", "--agent", "tatev", "--message-file", "{task_file}",
              "--timeout", "{timeout}", "--json"),
        # The gateway binds the tailnet, so a CLI off the brain host needs these two to reach it.
        # A URL and a token are not the owner's secrets - they are how this executor is addressed -
        # but the allowlist withholds by default, so they had to be named.
        env_allow=("OPENCLAW_GATEWAY_URL", "OPENCLAW_GATEWAY_TOKEN"),
        parser="openclaw_json",
    ),
    ExecutorSpec(
        name="openclaw-business",
        domains=(Domain.BUSINESS,),
        tiers=(Tier.CORPORATE,),
        argv=("openclaw", "agent", "--agent", "tamara", "--message-file", "{task_file}",
              "--timeout", "{timeout}", "--json"),
        env_allow=("OPENCLAW_GATEWAY_URL", "OPENCLAW_GATEWAY_TOKEN"),
        parser="openclaw_json",
    ),
    # R.U.B.E.N. — Return Unified Balance Equity Network. The portfolio manager, tax optimiser and
    # asset analyser: everything financial. Rubo until 2026-10-12, Antoine before that; the shim on
    # PATH is `ruben` now.
    ExecutorSpec(
        name="ruben",
        domains=(Domain.FINANCE,),
        # MEASURED 2026-10-12: `ruben ask --file <path>` is a one-shot added to the RUBEN repo
        # (`src/ask.ts`) for exactly this row — answer on stdout, exit 1 with the reason on stderr,
        # and an LLM failure is a failure rather than an "Error: ..." answer. Tools that need
        # approval are denied, since nobody is there to approve them. The task goes by file
        # because `ruben` is a `.CMD` shim and a file removes the batch hazard (see `_batch_hazard`).
        argv=("ruben", "ask", "--file", "{task_file}"),
        # The shim resolves its checkout from the environment and exits 1 with "No RUBEN checkout
        # found. Set RUBEN_REPO" without it. A path is not a credential, so it is allowed through —
        # but it had to be named, because the allowlist withholds by default. RUBEN reads its own
        # MiniMax key from its repo's `.env`, so no key crosses this boundary.
        env_allow=("RUBEN_REPO",),
        # D-83. Every figure RUBEN returns is a financial position, so the declaration is on the
        # executor rather than on each answer: a per-answer decision is one someone forgets.
        declares_never_store=never_store.FINANCIAL_POSITION,
    ),
)

#: The owner's coding pipeline, in his order: **Claude Code is the main tool, mcode is the first
#: fallback, Mistral Vibe is the second.** Every piece of code work — backend, scripts, git — goes
#: down this chain, and the chain is tried in order on FAILURE, not chosen between.
#:
#: Why this is a named constant rather than "the order of the rows above": a declared pipeline that
#: is really tuple order is a pipeline somebody reorders by accident while adding an executor. It is
#: also why `pick()` does not arbitrate on coding — the order is a decision the owner made, and a
#: model that is allowed to prefer the second entry has quietly replaced it.
#:
#: Codex was in this table until 2026-10-11 and is not any more. It was not failing; it was not in
#: the owner's pipeline, and three CLIs that can all edit a repo is two more audit shapes to
#: diagnose at 2 AM than the brief needs (D-01).
CODING_CHAIN: tuple[str, ...] = ("claude-code", "mcode", "vibe")

#: Frontend work does not come here at all. Websites, landing pages, UI, UX and design decisions
#: go to the **Open Design MCP server**, which is already wired as namespaced `mcp__open-design__*`
#: tools through `mcp_client.py` — a design surface, not a subprocess that returns a diff. A
#: `Domain.FRONTEND` brief is therefore refused by `resolve()` with this sentence rather than
#: falling through to a coding CLI, because a coding CLI *will* happily rewrite a landing page and
#: the result is the thing the split exists to prevent.
FRONTEND_ROUTE = (
    "frontend work (websites, landing pages, UI/UX, design decisions) goes to the Open Design MCP "
    "tools, not to a coding CLI — use the mcp__open-design__* tools, and send the backend half of "
    "the job here as a separate coding brief"
)

#: Windows batch shims. `npm` and `uv` both install CLIs as `.CMD` wrappers — on this machine
#: `codex`, `openclaw` and `ruben` all resolve to one — and a batch file's arguments are re-parsed
#: by the command interpreter, so a `&` or a quote inside a task string is a command-injection
#: surface rather than a character. The whole purpose of this module is to be the safe boundary, so
#: it fails closed: see `_batch_hazard`.
_BATCH_SUFFIXES = (".cmd", ".bat")
_CMD_METACHARACTERS = ('&', '|', '<', '>', '^', '"', '%', '\r', '\n', '`')

#: Names a child process needs merely to start. Everything outside this list is withheld, including
#: every Mushegh setting — the brief is the interface, not the environment.
_ENV_BASE = (
    "PATH", "HOME", "USERPROFILE", "SystemRoot", "SystemDrive", "COMSPEC",
    "TEMP", "TMP", "TMPDIR", "LANG", "LC_ALL", "TZ", "PATHEXT",
)


def _child_env(spec: ExecutorSpec) -> dict[str, str]:
    """Invariant 3 — an allowlist, built up from nothing.

    A denylist would be wrong in a way that only shows up later: it is correct until somebody adds
    a secret to the environment, and then it is silently wrong. This is the same reasoning the
    never-store guard uses, applied to a process boundary instead of a write boundary.
    """
    env = {k: os.environ[k] for k in _ENV_BASE if k in os.environ}
    for k in spec.env_allow:
        if k in os.environ:
            env[k] = os.environ[k]
    return env


def _no_route(brief: Brief) -> str:
    """Why this brief has nowhere to go — the specific reason when there is one.

    "no configured executor serves finance/personal" reads as a missing install and sends the
    reader looking for something to apt-get. When the row exists and its interface does not,
    `unavailable_because` is the actual answer, so it is the one that gets said.
    """
    blocked = [s for s in SPECS
               if brief.domain in s.domains and brief.tier in s.tiers and s.unavailable_because]
    if blocked:
        return "; ".join(f"{s.name}: {s.unavailable_because}" for s in blocked)
    return f"no configured executor serves {brief.domain.value}/{brief.tier.value}"


def _refuse_frontend(brief: Brief) -> None:
    """Frontend work never enters this table, and every entry point says so the same way.

    One helper rather than three copies of the check: `resolve`, `pick` and `dispatch_chain` are
    all entry points, and the first version of this only guarded two of them — so a frontend
    brief sent down the chain was refused with "no configured executor serves frontend/personal",
    which reads as a missing install and sends the next reader looking for an executor to add.
    """
    if brief.domain is Domain.FRONTEND:
        raise BriefRefused(FRONTEND_ROUTE)


def available(spec: ExecutorSpec) -> bool:
    """Is this executor actually usable? `which` is the configured check — no setting to drift.

    ``unavailable_because`` outranks the binary being present, because "installed" and "has the
    interface this row claims" are different facts and only the second one makes it a route.
    """
    if spec.unavailable_because:
        return False
    return shutil.which(spec.argv[0]) is not None


def candidates(brief: Brief, *, require_available: bool = True) -> list[ExecutorSpec]:
    """Every executor that serves this brief's domain and tier.

    This is the list D-81 hands to Jev. Code produces it; Jev may only narrow it. An executor that
    is not installed is not a candidate at all, so arbitration cannot name one.
    """
    out = [s for s in SPECS if brief.domain in s.domains and brief.tier in s.tiers]
    if require_available:
        out = [s for s in out if available(s)]
    if brief.domain is Domain.CODING:
        # The owner's order, not the table's. An executor missing from CODING_CHAIN is not a
        # candidate at all, so nothing can route coding work to a CLI he did not pick — "all of
        # the code work goes down this pipeline" is a rule about exclusivity, not just order.
        order = {name: i for i, name in enumerate(CODING_CHAIN)}
        dropped = [s.name for s in out if s.name not in order]
        if dropped:
            # Loud, because this is the one place a correctly-added executor can vanish. Silence
            # here would make "I added it and nothing happened" the next maintainer's afternoon.
            logger.warning(
                f"executor: coding spec(s) {dropped} are not in CODING_CHAIN {list(CODING_CHAIN)} "
                "and will not be dispatched; add the name to the chain to enable it"
            )
        out = sorted((s for s in out if s.name in order), key=lambda s: order[s.name])
    return out


def resolve(brief: Brief, *, chosen: str | None = None) -> ExecutorSpec:
    """Pick the executor for a brief. ``chosen`` is Jev's verdict, and it is checked, not trusted.

    D-81: a brief whose domain matches no configured executor is **refused**, never sent to the
    nearest thing. The nearest thing is how a coding brief ends up at a finance agent.
    """
    _refuse_frontend(brief)
    cands = candidates(brief)
    if not cands:
        raise BriefRefused(_no_route(brief))
    if chosen is None:
        return cands[0]
    for s in cands:
        if s.name == chosen:
            return s
    # An arbitration naming something outside the candidate list is the one failure D-72's shape
    # exists to make impossible. Refuse loudly rather than silently falling back.
    raise BriefRefused(f"{chosen!r} is not among the candidates for this brief")


async def pick(brief: Brief, *, correlation_id: str = "",
               service: object | None = None) -> tuple[ExecutorSpec, object | None]:
    """M45 - Jev chooses among the executors code already offered. D-73, D-76 and D-81 in one shape.

    `resolve()` is the authority and `pick()` is the policy, which is why the fallbacks live here
    and the refusal lives there. Three bounds, each the reason this is safe on a paid path:

    * **Code builds the list.** `candidates()` returns only executors whose domain and tier match
      the brief *and* whose binary is on this host. Jev cannot name an executor that is not
      installed, because an uninstalled one was never on the ballot (D-81).
    * **Silence keeps every candidate.** A timeout, an outage or a disabled service returns the
      deterministic first choice with nothing said - the arbitration budget is 400 ms and the
      correct failure mode is carrying on exactly as before (D-73). An executor choice is also
      none of the owner's business: he asked for the work, not for a routing report (D-34).
    * **A flat distribution is not an opinion.** `Arbitration.arbitrated` is already gated on the
      entropy zone (D-76), so a near-tie reads as "no winner" and the deterministic order stands.
      A coin flip dressed as a decision is worse than an arbitrary rule, because it is believable.

    Fewer than two candidates costs no call at all, which is the common case today: only coding
    has three, and every other domain has exactly one.
    """
    _refuse_frontend(brief)
    cands = candidates(brief)
    if not cands:
        raise BriefRefused(_no_route(brief))
    if len(cands) == 1:
        return cands[0], None
    if brief.domain is Domain.CODING:
        # No arbitration on coding, and this is the whole reason CODING_CHAIN is a constant. The
        # owner named Claude Code the main tool with two fallbacks behind it; a model allowed to
        # prefer the second entry has replaced that decision with a preference, and it would do so
        # invisibly, because an executor choice is deliberately not reported to him (D-34).
        # Fallback happens on FAILURE, in `dispatch_chain`, which is a different question.
        return cands[0], None

    try:
        if service is None:
            from mushegh.brain.judgment import JUDGMENTS

            service = JUDGMENTS
        arb = await service.arbitrate(
            brief.task, [s.name for s in cands],
            correlation_id=correlation_id, route_purpose="executor",
        )
    except Exception as e:  # noqa: BLE001 - an arbitration outage is a normal outcome (D-73)
        logger.debug(f"executor arbitration unavailable ({type(e).__name__}); keeping {cands[0].name}")
        return cands[0], None
    if arb is None or not arb.arbitrated:
        return cands[0], arb

    try:
        return resolve(brief, chosen=arb.winner), arb
    except BriefRefused:
        # Jev returned a name that was not on the ballot it was given. That is a protocol fault,
        # not a routing preference, so it is logged rather than spoken and the deterministic
        # choice stands. Refusing the whole brief would let an upstream bug cancel real work.
        logger.warning(f"executor arbitration named {arb.winner!r}, which was not a candidate")
        return cands[0], arb


def _write_task(brief: Brief) -> Path:
    """Put the brief's text where an executor can read it without a shell seeing it.

    Mode 0600 where the platform honours it: the brief is the owner's business, not the machine's.
    """
    import tempfile

    fd, name = tempfile.mkstemp(prefix="mushegh-brief-", suffix=".txt", text=True)
    path = Path(name)
    with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(brief.task)
    try:
        os.chmod(path, 0o600)
    except OSError:  # noqa: S110 - Windows ignores the mode; the temp dir is already per-user
        pass
    return path


def _argv(spec: ExecutorSpec, brief: Brief, task_file: str = "") -> list[str]:
    """Substitute the brief into the spec's argv. The executable is resolved to a real path.

    ``{task_file}`` is the one substitution that is not a plain string: `dispatch()` writes the
    task to a temporary file and passes its path, which is how an executor that supports it
    (`openclaw agent --message-file`) sidesteps the batch-shim re-parsing hazard entirely rather
    than having the brief refused for containing a quote.
    """
    repl = {
        "{task}": brief.task,
        "{acceptance}": brief.acceptance,
        "{repo}": brief.repo or "",
        "{task_file}": task_file,
        "{timeout}": str(brief.timeout_s),
    }
    argv = [repl.get(part, part) for part in spec.argv]
    argv[0] = shutil.which(argv[0]) or argv[0]
    return argv


def wants_task_file(spec: ExecutorSpec) -> bool:
    """Whether this executor reads its task from a file rather than from argv."""
    return "{task_file}" in spec.argv


def _batch_hazard(argv: list[str]) -> str:
    """Non-empty when running this argv would hand a metacharacter to a command interpreter.

    Only substituted values can carry one — the spec's own flags are ours — but the check is on
    the whole argv because a spec is data and data gets edited. The refusal is deliberate and
    narrow: it fires only when the executable is a batch shim, so a native binary is unaffected.

    ponytail: refuses rather than escapes. Quoting rules for a batch file are famously not
    composable, and a wrong escape here is an injection rather than a syntax error. If a brief
    legitimately needs a `&`, the fix is to hand the task on stdin or in a file — not to guess at
    quoting.
    """
    exe = (argv[0] or "").lower()
    if not exe.endswith(_BATCH_SUFFIXES):
        return ""
    for arg in argv[1:]:
        bad = [c for c in _CMD_METACHARACTERS if c in arg]
        if bad:
            return (f"{argv[0]} is a batch shim and the brief contains {bad!r}, which a command "
                    "interpreter would re-parse")
    return ""


async def dispatch(brief: Brief, *, chosen: str | None = None) -> Result:
    """Run one brief through one executor. The only place in this module that starts a process.

    Refuses before dispatch when the brief is not dispatchable (invariant 1), derives success from
    the exit code (invariant 2), hands the child an allowlisted environment (invariant 3), and
    returns a diff it does not apply (invariant 4).
    """
    if not brief.acceptance.strip():
        raise BriefRefused("a brief with no acceptance check is not dispatchable")
    if brief.domain is Domain.CODING and not brief.repo:
        raise BriefRefused("a coding brief must name the repo it may work in")
    if brief.domain is not Domain.CODING and brief.repo:
        raise BriefRefused(f"a {brief.domain.value} brief must not carry a repo path")

    spec = resolve(brief, chosen=chosen)
    # A task handed over in a file is never re-parsed by anything, so it is written before the
    # argv is built and removed in the `finally` below whatever happens.
    handoff: Path | None = None
    if wants_task_file(spec):
        handoff = _write_task(brief)
    argv = _argv(spec, brief, task_file=str(handoff) if handoff else "")
    hazard = _batch_hazard(argv)
    if hazard:
        if handoff is not None:
            handoff.unlink(missing_ok=True)
        raise BriefRefused(hazard)
    started = time.monotonic()
    code, out, err = -1, "", ""
    proc = None
    try:
        proc = await asyncio.create_subprocess_exec(
            *argv,
            stdin=asyncio.subprocess.DEVNULL,   # no TTY, no REPL, nothing to hand a shell to
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=brief.repo or None,
            env=_child_env(spec),
        )
        raw_out, raw_err = await asyncio.wait_for(proc.communicate(), timeout=brief.timeout_s)
        code = proc.returncode if proc.returncode is not None else -1
        out = (raw_out or b"").decode("utf-8", "replace")
        err = (raw_err or b"").decode("utf-8", "replace")
    except asyncio.TimeoutError:
        err = f"{spec.name} exceeded its {brief.timeout_s}s deadline"
    except FileNotFoundError:
        err = f"{spec.name} is not installed on this host"
    except Exception as e:  # noqa: BLE001 — an executor must never take the brain down with it
        err = f"{spec.name} failed to start: {e}"

    finally:
        # Reap whatever is still alive. `wait_for` cancels `communicate()` when the deadline
        # passes, but it does NOT kill the child or close its pipes — so a timed-out executor used
        # to leave a live process and an open transport behind. That is a handle leak in a
        # long-running brain, and on Windows Proactor it also raises `ResourceWarning: unclosed
        # transport` at interpreter shutdown, whose `__del__` repr then throws `ValueError: I/O
        # operation on closed pipe` MID-FLUSH. That truncation is not cosmetic: it is how
        # `test_coding_chain.py` passed standalone and lost its own "checks passed ===" summary
        # under `run_all_tests.py`, where stdout is a pipe — so the suite searched the full output,
        # found no needle, and reported FAIL for a gate that had exited 0 and passed everything.
        if proc is not None and proc.returncode is None:
            try:
                proc.kill()
            except (ProcessLookupError, OSError):
                pass  # already gone; reaping below is what matters
            try:
                await proc.wait()
            except Exception:  # noqa: BLE001 — reaping is best-effort and must never raise here
                pass
        if handoff is not None:
            handoff.unlink(missing_ok=True)

    # Parse before judging. A JSON event stream read as prose is how a reported FAILURE gets
    # spoken as a result: codex emits `turn.failed` and openclaw can carry `status: ok` over a
    # failed tool, so the parser's verdict has to be able to fail a run the exit code passed.
    transcript, parse_error = _parsed(spec, out)
    result = Result(
        executor=spec.name,
        domain=brief.domain,
        exit_code=code,
        transcript=transcript,
        diff=_extract_diff(out),
        seconds=round(time.monotonic() - started, 3),
        error=parse_error or _error_line(spec, code, transcript, err),
    )
    _account(brief, spec, result)
    return result


async def dispatch_chain(brief: Brief) -> tuple[Result, list[Result]]:
    """Run a brief down its fallback chain and return ``(final, attempts)``.

    For coding that chain is :data:`CODING_CHAIN` — Claude Code, then mcode, then Mistral Vibe —
    and this is where "first fallback" and "second fallback" actually mean something: each is
    tried only when the one before it **failed**, judged by ``Result.ok``, which is derived from
    the exit code and the parser's verdict and never from prose.

    Three things it deliberately does not do:

    * **It does not retry a timeout.** A deadline that passes means the executor may still be
      editing files in that worktree; handing the same brief to a second CLI in the same place is
      how two agents edit one tree. Same reasoning as the fleet's takeback.
    * **It does not hide the failures.** Every attempt comes back, so the audit line and the
      owner's answer can say "Claude Code failed, mcode did it" rather than reporting a clean run.
    * **It does not fall back on a REFUSAL.** A brief with no acceptance check, or a frontend brief,
      is wrong in a way the next executor cannot fix, so :class:`BriefRefused` propagates.
    """
    _refuse_frontend(brief)
    attempts: list[Result] = []
    for spec in candidates(brief):
        result = await dispatch(brief, chosen=spec.name)
        attempts.append(result)
        if result.ok:
            return result, attempts
        if "deadline" in result.error:
            logger.warning(
                f"executor: {spec.name} hit its {brief.timeout_s}s deadline; NOT falling back — "
                "it may still be writing in that worktree"
            )
            return result, attempts
        logger.info(f"executor: {spec.name} failed ({result.error[:90]}); trying the next in line")
    if not attempts:
        raise BriefRefused(_no_route(brief))
    return attempts[-1], attempts


def _error_line(spec: ExecutorSpec, code: int, out: str, err: str) -> str:
    """Why this failed, in one line — and never empty when it did fail.

    Written because the gate caught the opposite: an executor that printed to stdout and exited 3
    produced `exit_code=3` with `error=""`. `Result.ok` was still correct, so nothing was unsafe —
    but the owner would have been told a delegation failed with no statement of what happened, and
    a failure with no error line is the shape that gets read as "probably fine".
    """
    if err.strip():
        return err.strip()
    if code != 0:
        return f"{spec.name} exited {code} without writing to stderr"
    if not out.strip():
        return f"{spec.name} exited 0 but produced no output"
    return ""


def _extract_diff(text: str) -> str | None:
    """Pull a unified diff out of a transcript, if there is one. Never applies it."""
    for marker in ("diff --git", "--- a/"):
        i = text.find(marker)
        if i >= 0:
            return text[i:].strip() or None
    return None


# ── parsers ───────────────────────────────────────────────────────────────────────────────────
#
# Each coding CLI emits a different machine-readable stream, and the reason to parse rather than
# print it raw is not tidiness: a JSON event stream read as prose is how a *failure* gets spoken as
# a result. Codex emits `turn.failed` and `error` events while still exiting 0 in some shapes, so
# the parser has to be able to say "this run failed" independently of the exit code.
#
# All three are deliberately tolerant. A line that is not JSON is kept as text rather than dropped:
# these tools print human notes alongside their events, and a parser that silently discards the
# unrecognised half is a parser that loses the error message.


def _parse_lines(text: str) -> list[dict | str]:
    """Split a stream into parsed JSON objects and plain lines, in order."""
    import json

    out: list[dict | str] = []
    for line in (text or "").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped[0] in "{[":
            try:
                parsed = json.loads(stripped)
            except ValueError:
                out.append(stripped)
                continue
            out.append(parsed if isinstance(parsed, dict) else {"_list": parsed})
        else:
            out.append(stripped)
    return out


def _texts_of(obj: object) -> list[str]:
    """Every string that looks like something a person would read, at any depth."""
    found: list[str] = []
    if isinstance(obj, dict):
        for key, value in obj.items():
            # `reply`/`replyText`/`response` were added 2026-10-07 for the fleet. The exact key
            # `openclaw agent --json` uses is NOT documented and no real run has been made, so the
            # set is widened rather than guessed at: a key this misses leaves the raw JSON line as
            # the transcript, which reads as noise, while a key it includes too eagerly only ever
            # adds a string a person could read. Erring toward reading is correct here.
            if key in {"text", "message", "content", "summary", "result", "output", "answer",
                       "reply", "replyText", "response"}:
                if isinstance(value, str) and value.strip():
                    found.append(value.strip())
                else:
                    found.extend(_texts_of(value))
            else:
                found.extend(_texts_of(value))
    elif isinstance(obj, list):
        for item in obj:
            found.extend(_texts_of(item))
    return found


def parse_stream_json(text: str) -> tuple[str, str]:
    """Claude Code's ``--output-format stream-json``: one JSON object per line.

    Returns ``(transcript, error)``. An event whose ``subtype`` or ``is_error`` marks a failure sets
    the error even when the process exited 0, because "it printed something" is not "it worked".
    """
    pieces: list[str] = []
    error = ""
    for item in _parse_lines(text):
        if isinstance(item, str):
            pieces.append(item)
            continue
        if item.get("is_error") or str(item.get("subtype") or "").endswith("error"):
            error = error or "; ".join(_texts_of(item)) or "the executor reported an error"
        if item.get("type") == "result" and item.get("result"):
            pieces.append(str(item["result"]))
            continue
        pieces.extend(_texts_of(item))
    return "\n".join(dict.fromkeys(p for p in pieces if p)), error


def parse_codex_jsonl(text: str) -> tuple[str, str]:
    """Codex's ``exec --json``: a JSONL event stream.

    The documented events are ``thread.started``, ``turn.started`` / ``turn.completed`` /
    ``turn.failed``, ``item.started`` / ``item.completed``, and ``error``. A ``turn.failed`` or an
    ``error`` is a failure regardless of the exit code.
    """
    pieces: list[str] = []
    error = ""
    for item in _parse_lines(text):
        if isinstance(item, str):
            pieces.append(item)
            continue
        kind = str(item.get("type") or item.get("event") or "")
        if kind == "error" or kind.endswith(".failed"):
            error = error or "; ".join(_texts_of(item)) or f"codex reported {kind}"
            continue
        pieces.extend(_texts_of(item))
    return "\n".join(dict.fromkeys(p for p in pieces if p)), error


def parse_openclaw_json(text: str) -> tuple[str, str]:
    """``openclaw agent --json``: one JSON document, or JSONL when streaming.

    The fleet's own convention is the trap worth guarding: a frame can carry ``status: "ok"`` while
    a tool inside it failed, which is recorded in the project's memory as *"ok hides failures"* —
    7 of 14 crons once had a failed-tool diagnostic sitting behind ``status=ok``. So an ``error``
    field anywhere in the payload wins over a cheerful status.
    """
    pieces: list[str] = []
    error = ""
    for item in _parse_lines(text):
        if isinstance(item, str):
            pieces.append(item)
            continue
        for key in ("error", "err", "failure"):
            value = item.get(key)
            if value:
                error = error or (value if isinstance(value, str) else "; ".join(_texts_of(value)))
        pieces.extend(_texts_of(item))
    return "\n".join(dict.fromkeys(p for p in pieces if p)), error


def parse_vibe_json(text: str) -> tuple[str, str]:
    """Mistral Vibe's ``-p --output json``: ONE JSON array of session entries, not JSONL.

    Measured against a real run rather than assumed: three entries came back for a one-turn
    prompt — ``{"type": "message", "role": "user"}``, ``{"type": "reasoning"}``, and
    ``{"type": "message", "role": "assistant", "content": [{"type": "text", "text": ...}]}``.
    So the answer is the **assistant** messages' text, and the other roles are echo.

    Two failures this has to catch, because the exit code does not:

    * ``generationStatus`` on the last entry is the executor's own verdict. Anything other than
      ``completed`` — interrupted by ``--max-turns``, ``--max-price`` or ``--time-limit`` — is a
      run that stopped early, and reading its partial transcript as a result is exactly the
      "it printed something, so it worked" mistake the other two parsers guard.
    * Echoing the prompt back is not an answer, so the user entry never reaches the transcript.
    """
    text = text.strip()
    if not text:
        return "", ""
    try:
        entries = json.loads(text)
    except json.JSONDecodeError:
        # Not the documented shape. Keep the output rather than losing it; the exit code and
        # `_error_line` still decide whether this run passed.
        return text, ""
    if not isinstance(entries, list):
        return text, ""
    pieces: list[str] = []
    error = ""
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        status = str(entry.get("generationStatus") or "")
        if status and status != "completed":
            error = error or f"vibe stopped early ({status})"
        if entry.get("role") == "assistant":
            pieces.extend(_texts_of(entry.get("content")))
    return "\n".join(dict.fromkeys(p for p in pieces if p)), error


PARSERS: dict[str, object] = {
    "stream_json": parse_stream_json,
    "codex_jsonl": parse_codex_jsonl,
    "openclaw_json": parse_openclaw_json,
    "vibe_json": parse_vibe_json,
}


def _parsed(spec: ExecutorSpec, raw: str) -> tuple[str, str]:
    """Apply the spec's parser, falling back to the raw text rather than losing it."""
    fn = PARSERS.get(spec.parser) if spec.parser else None
    if fn is None:
        return raw.strip(), ""
    try:
        transcript, error = fn(raw)  # type: ignore[operator]
    except Exception as e:  # noqa: BLE001 — a parser bug must not lose the executor's output
        logger.warning(f"executor: {spec.parser} parser failed ({e}); using the raw transcript")
        return raw.strip(), ""
    return (transcript or raw.strip()), error


def _account(brief: Brief, spec: ExecutorSpec, result: Result) -> None:
    """One cost entry and one audit line per dispatch, success or not (D-79, D-81).

    D-81 is explicit that an executor choice is never silent in the audit trail *even when it
    succeeds*, because a wrong executor costs a wrong action in the world rather than a wasted
    turn. Both calls are best-effort: accounting must never be the reason a delegation fails.
    """
    try:
        from mushegh.brain.governor import Governor

        Governor().charge(calls=1, seconds=result.seconds)
    except Exception as e:  # noqa: BLE001
        logger.warning(f"executor: could not charge the governor: {e}")
    try:
        from mushegh.brain import audit

        # D-83, and a defect in the first version of this function: it wrote `result.transcript`
        # into the audit line unconditionally, which would have put every balance and salary figure
        # RUBEN returned into the one file D-83 promises they never reach. A never-store class is
        # withheld here the way 37.R5 withholds one from the store — the audit line records that a
        # delegation happened and what it cost, and the fingerprint lets two runs be compared
        # without the figures being recoverable from the log.
        declared = spec.declares_never_store
        if declared:
            body = never_store.SPOKEN.get(declared, never_store.REASONS.get(declared, ""))
            payload = (f"[withheld: {declared}] {body} "
                       f"fingerprint={never_store.fingerprint(result.transcript)}")
        else:
            payload = (result.transcript or result.error)[:2000]
        audit.record(
            tool=f"executor:{spec.name}",
            args={"domain": brief.domain.value, "tier": brief.tier.value,
                  "task": brief.task, "acceptance": brief.acceptance, "repo": brief.repo},
            result=payload,
            ok=result.ok,
            actor="mushegh:executor",
            decision="allow",
            rule="D-79/D-80 delegated execution; the diff is not applied here"
                 + (f"; output withheld under D-83/{declared}" if declared else ""),
        )
    except Exception as e:  # noqa: BLE001
        logger.warning(f"executor: could not write the audit line: {e}")


def storage_class(spec_or_name: ExecutorSpec | str) -> str | None:
    """The ``never_store`` class a consumer must declare when handling this executor's output.

    Exists so a caller cannot forget. A consumer that writes an executor result anywhere durable
    passes this to ``never_store.screen(text, declared=...)``, and a finance answer is refused —
    which is D-83's promise, enforced at the write boundary rather than asserted in prose.
    """
    if isinstance(spec_or_name, str):
        spec = next((s for s in SPECS if s.name == spec_or_name), None)
        return spec.declares_never_store if spec else None
    return spec_or_name.declares_never_store


def status() -> list[dict[str, object]]:
    """The 2:00 AM answer for this subsystem, as data (D-01).

    The standing objection to four executors is that it is four more things that can be down, and
    the mitigation is only real if "which one, is it installed, and what does it serve" is
    answerable from the running system in one step rather than by reading this file. One row per
    executor; exposed to the owner through the `diagnose` tool.
    """
    return [
        {
            "name": s.name,
            "domains": [d.value for d in s.domains],
            "tiers": [t.value for t in s.tiers],
            "installed": available(s),
            "path": shutil.which(s.argv[0]) or "",
            "structured_output": s.structured_output,
            "withholds": s.declares_never_store or "",
        }
        for s in SPECS
    ]
