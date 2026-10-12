"""M43 — the only path from an external coding executor to a commit (D-08, D-80).

`executors/__init__.py` ends at a transcript and a diff on purpose: invariant 4 says an executor
never lands anything. This module is what happens next, and it is the enforcement of one decision
rather than a feature. **D-08 lets Mushegh commit his own code only when all four of these hold:** a
dedicated branch, a green suite, zero schema migrations, and the owner's explicit approval. Four
conditions written in a charter are a hope; four conditions a function refuses past are a rule.

**The isolation is the design, not a detail.** A coding CLI edits files in its working directory —
it does not hand back a patch to apply. So if the executor were pointed at the owner's checkout,
the proposal would already be sitting in his tree before the first condition had been checked, and
"a refused approval leaves the tree untouched" would be false by construction. Instead each brief
gets its own `git worktree` on its own new branch. The owner's checkout is never read for writing,
never switched, never made dirty — so D-08 condition 1 is satisfied by the *place* the work
happens, not by remembering to branch.

**And nothing is ever discarded.** `tools/coding.py` deliberately has no reset, clean, stash or
branch-delete, because "he can't lose your work" is worth more than tidiness. This module keeps
that rule: the only git writes it performs are `worktree add` (which creates a directory and a
branch and touches nothing that existed) and, once all four conditions hold, `commit` inside that
worktree. A refusal **leaves the worktree where it is** and says where — the owner inspects or
removes it. Accumulating directories is the cost; losing a proposal Mushegh just paid for is not.

**Approval is asynchronous, so landing is two calls.** `ApprovalQueue` is a durable queue the
owner answers in his own time, not a blocking prompt. `delegate_coding()` therefore runs the first
three conditions and stops at the fourth, reporting where the work is. `commit_approved()` is the
second half, and it re-checks the first three rather than trusting that they were true an hour ago.

ponytail: plain `git` argv here instead of routing through `tools/coding.py`. That allowlist exists
to protect the owner's checkout, and these calls are scoped to a directory this module created —
going through the laptop forwarder would also point the writes at the wrong tree, since `dispatch()`
runs the CLI on the brain host.

    uv run python bench/test_coding_delegation.py
"""

from __future__ import annotations

import asyncio
import secrets
import shutil
import time
from pathlib import Path

from loguru import logger
from pydantic import BaseModel

from mushegh.brain.executors import Brief, BriefRefused, Domain, Result, dispatch, pick

__all__ = [
    "Landed", "MIGRATION_PATHS", "MIGRATION_SQL", "STAGES",
    "commit_approved", "delegate_coding", "migration_in", "worktree_root",
]

#: Every stage in order. The outcome names the one that decided it, so a report can never be
#: "it didn't work" — it is always "it stopped at `tests`, and here is why".
STAGES = ("isolate", "dispatch", "diff", "migration", "tests", "approval", "commit")

#: D-08 condition 3. A path fragment here means the diff touches migration machinery.
MIGRATION_PATHS = ("migrations/", "migration/", "alembic/", "sql/", "schema.sql", "schema.prisma")

#: ...and these are the statements that change a schema without living in such a directory. Mushegh's
#: own stores are SQLite created by `CREATE TABLE IF NOT EXISTS` at startup (D-02), so a new table
#: can appear in any module. Matched on added lines only — deleting an old migration is not one.
MIGRATION_SQL = (
    "create table", "alter table", "drop table", "add column", "drop column",
    "create index", "drop index", "rename column", "rename to",
)

GIT_TIMEOUT_S = 120
#: Default budget for the suite D-08 condition 2 requires. The real run takes minutes, and a
#: delegation that gives up before the suite finishes would report red for every green change.
SUITE_TIMEOUT_S = 900


class Landed(BaseModel):
    """The outcome of one delegation. ``committed`` is the only thing that means it landed."""

    model_config = {"frozen": True, "extra": "forbid"}

    branch: str = ""
    #: Which of ``STAGES`` decided this outcome.
    stage: str
    committed: bool = False
    #: Why it stopped. Never empty unless it committed — a refusal with no reason reads as fine.
    reason: str = ""
    #: Where the proposal is. Kept on every refusal so nothing Mushegh paid for is thrown away.
    worktree: str = ""
    diff: str = ""
    #: The executor's own result, when it got that far. ``None`` means no process ever started.
    result: Result | None = None

    def model_post_init(self, _ctx: object) -> None:
        if self.stage not in STAGES:
            raise ValueError(f"stage must be one of {STAGES}, not {self.stage!r}")
        if not self.committed and not self.reason.strip():
            raise ValueError("a refusal must say why")


def worktree_root() -> Path:
    """Where delegated worktrees live. Outside the repo, so nothing here is ever a repo change."""
    from mushegh.shared.paths import state_dir

    return state_dir() / "delegated"


async def _git(cwd: str | Path, *args: str, timeout: int = GIT_TIMEOUT_S) -> tuple[int, str]:
    """Run one git command. argv form, no shell, no stdin — the contract's rules, same reasons."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "git", *args,
            cwd=str(cwd),
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        raw, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        return (proc.returncode if proc.returncode is not None else -1,
                (raw or b"").decode("utf-8", "replace").strip())
    except asyncio.TimeoutError:
        return -1, f"git {args[0] if args else ''} exceeded {timeout}s"
    except FileNotFoundError:
        return -1, "git is not installed on this host"
    except Exception as e:  # noqa: BLE001 — a delegation must never take the brain down
        return -1, f"git {args[0] if args else ''} failed to start: {e}"


def migration_in(diff: str) -> str:
    """Non-empty when this diff introduces a schema migration — D-08 condition 3.

    Reads *added* lines only. A diff that deletes an old `CREATE TABLE` is a cleanup, and failing
    it would make the condition unsatisfiable for anyone removing the thing it guards against.
    """
    for raw in (diff or "").splitlines():
        if raw.startswith("+++") or raw.startswith("---"):
            continue
        if raw.startswith(("diff --git ", "rename to ", "rename from ")):
            low = raw.lower()
            for frag in MIGRATION_PATHS:
                if frag in low:
                    return f"the diff touches {frag}"
            continue
        if not raw.startswith("+"):
            continue
        low = raw[1:].lower()
        for stmt in MIGRATION_SQL:
            if stmt in low:
                return f"an added line contains {stmt!r}"
    return ""


async def _full_diff(tree: Path) -> tuple[int, str]:
    """Everything the executor changed, *including files it created*.

    `git diff HEAD` alone does not see an untracked file, and the gate caught what that means:
    an executor that puts `CREATE TABLE` in a brand-new module passed D-08 condition 3, because
    the scan was reading a diff the new file was not in. `add --intent-to-add` records the paths
    without staging content — non-destructive, and the one git primitive that makes a new file
    visible to a diff.
    """
    await _git(tree, "add", "--intent-to-add", "--", ".")
    return await _git(tree, "diff", "HEAD")


async def _default_suite(cwd: Path) -> tuple[bool, str]:
    """D-08 condition 2, run against the worktree rather than the owner's tree.

    Uses the repo's own interpreter: `uv run` inside a fresh worktree would resolve a venv that
    does not exist there and spend minutes building one, which would read as a slow test suite.
    """
    import sys

    rc, out = await _git(cwd, "rev-parse", "--show-toplevel")  # cheap proof the cwd is a worktree
    if rc != 0:
        return False, out
    runner = Path(cwd) / "bench" / "run_all_tests.py"
    if not runner.exists():
        return False, "this repo has no bench/run_all_tests.py, so condition 2 cannot be checked"
    try:
        proc = await asyncio.create_subprocess_exec(
            sys.executable, str(runner),
            cwd=str(cwd),
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            env={**_suite_env(cwd)},
        )
        raw, _ = await asyncio.wait_for(proc.communicate(), timeout=SUITE_TIMEOUT_S)
    except asyncio.TimeoutError:
        return False, f"the suite exceeded its {SUITE_TIMEOUT_S}s budget"
    except Exception as e:  # noqa: BLE001
        return False, f"the suite failed to start: {e}"
    text = (raw or b"").decode("utf-8", "replace")
    tail = "\n".join(line for line in text.splitlines() if "FAIL" in line or "failed" in line)
    return (proc.returncode == 0), (tail[-1500:] if proc.returncode else "")


def _suite_env(cwd: Path) -> dict[str, str]:
    """The suite's environment: this process's, with the worktree's own sources first.

    Not an allowlist like `_child_env` — this is Mushegh's own test suite, not a third-party agent,
    and it legitimately needs the config it always had. The one thing that must be overridden is
    the import path, or the worktree's copy would be tested against the installed package.
    """
    import os

    env = dict(os.environ)
    src = str(Path(cwd) / "src")
    env["PYTHONPATH"] = src + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    env["PYTHONIOENCODING"] = "utf-8"
    return env


def _branch_name() -> str:
    """A name no second delegation can collide with.

    The gate caught the version without the suffix: two briefs in the same second produced the
    same branch, and the second one was *refused* with "that directory already exists" — a
    legitimate delegation failing on a clock resolution.
    """
    return f"mushegh/delegated-{time.strftime('%Y%m%d-%H%M%S')}-{secrets.token_hex(2)}"


async def _base_is_stale(repo: str) -> str:
    """Non-empty when the owner's tree has moved past HEAD, which the worktree would be cut from.

    `git worktree add ... HEAD` gives the executor the last **commit**, not the owner's working
    tree. On this repo that is not a theoretical gap: on 2026-10-06 the checkout carried 171
    uncommitted changes against a three-week-old HEAD, so a delegated diff would have been written
    against code the owner had already replaced - and would have looked perfectly reasonable right
    up to the moment it was merged.

    So it refuses, with the count, rather than warning. A warning attached to a success is read as
    a success; and the two fixes (commit, or stash) both take one command and are the owner's call
    either way. There is deliberately no override flag: when a real reason to delegate against a
    stale base turns up, that reason can be written down then.
    """
    rc, out = await _git(repo, "status", "--porcelain")
    if rc != 0:
        return ""  # cannot tell; _isolate reports the real failure if there is one
    changed = [ln for ln in out.splitlines() if ln.strip()]
    if not changed:
        return ""
    return (f"your checkout has {len(changed)} uncommitted change(s), and a worktree is cut from "
            "HEAD - so anything written here would be built against code you have already moved "
            "past. Commit or stash first and I will delegate against what you actually have")


async def _isolate(repo: str, branch: str) -> tuple[Path | None, str]:
    """Create a worktree on a new branch. Touches nothing that already existed."""
    root = worktree_root()
    try:
        root.mkdir(parents=True, exist_ok=True)
    except Exception as e:  # noqa: BLE001
        return None, f"I couldn't make a place to work: {e}"
    path = root / branch.replace("/", "-")
    if path.exists():
        return None, f"{path} already exists, so I stopped rather than write into it"
    rc, out = await _git(repo, "worktree", "add", "-b", branch, str(path), "HEAD")
    if rc != 0:
        return None, f"I couldn't isolate the work: {out[:400]}"
    return path, ""


async def delegate_coding(
    brief: Brief,
    *,
    chosen: str | None = None,
    run_suite=None,
    ask_owner=None,
) -> Landed:
    """Run a coding brief in isolation and take it as far as D-08 allows without the owner.

    Stops at `approval` by design: the owner's yes is the fourth condition and `ApprovalQueue` is
    durable rather than blocking. ``ask_owner`` may return True (already approved — a replay of a
    resolved queue item), False (refused) or None (asked, not yet answered); the default asks
    nothing and returns None, because enqueuing is the caller's job, not this module's.
    """
    if brief.domain is not Domain.CODING:
        raise BriefRefused("only a coding brief lands as a commit; this path is D-08's, not D-05's")
    if not brief.repo:
        raise BriefRefused("a coding brief must name the repo it may work in")

    if (stale := await _base_is_stale(brief.repo)):
        return Landed(stage="isolate", reason=stale)

    branch = _branch_name()
    tree, why = await _isolate(brief.repo, branch)
    if tree is None:
        return Landed(stage="isolate", branch=branch, reason=why)

    # The executor works in the worktree, never in `brief.repo`. Same brief, different ground.
    scoped = brief.model_copy(update={"repo": str(tree)})
    if chosen is None:
        # M45: Jev picks among the three coding CLIs, inside the list code built. An outage keeps
        # the deterministic first choice and says nothing (D-73) — the owner asked for the work,
        # not for a routing report.
        spec, _arb = await pick(scoped)
        chosen = spec.name
    result = await dispatch(scoped, chosen=chosen)
    if not result.ok:
        return Landed(stage="dispatch", branch=branch, worktree=str(tree),
                      reason=result.error or f"{result.executor} did not finish the work",
                      result=result)

    rc, diff = await _full_diff(tree)
    if rc != 0:
        return Landed(stage="diff", branch=branch, worktree=str(tree), result=result,
                      reason=f"I couldn't read back what was changed: {diff[:300]}")
    if not diff.strip():
        return Landed(stage="diff", branch=branch, worktree=str(tree), result=result,
                      reason=f"{result.executor} finished without changing any file")

    if (found := migration_in(diff)):
        return Landed(stage="migration", branch=branch, worktree=str(tree), diff=diff, result=result,
                      reason=f"D-08 forbids a self-edit that introduces a schema migration — {found}")

    suite = run_suite or _default_suite
    green, failures = await suite(tree)
    if not green:
        return Landed(stage="tests", branch=branch, worktree=str(tree), diff=diff, result=result,
                      reason=f"the suite is not green on this change, so it cannot land. {failures}"
                             .strip())

    verdict = None if ask_owner is None else await _maybe_await(ask_owner(diff))
    if verdict is False:
        return Landed(stage="approval", branch=branch, worktree=str(tree), diff=diff, result=result,
                      reason="you declined the diff, so nothing was committed; the work is still in "
                             f"{tree} if you want another look")
    if verdict is not True:
        return Landed(stage="approval", branch=branch, worktree=str(tree), diff=diff, result=result,
                      reason=f"three of the four conditions hold and I'm waiting on your approval "
                             f"of the diff. It's on branch {branch} in {tree}")

    return await commit_approved(brief, branch=branch, worktree=tree, result=result,
                                 run_suite=run_suite)


async def commit_approved(
    brief: Brief,
    *,
    branch: str,
    worktree: str | Path,
    result: Result | None = None,
    run_suite=None,
) -> Landed:
    """The second half: the owner said yes, so re-prove the other three and commit.

    Re-proving is the point. An approval resolved an hour later is an approval of a diff, and in
    that hour the worktree may have been edited, the branch may have moved, and a schema statement
    may have appeared. Trusting the earlier check would make three of the four conditions describe
    the past rather than the commit.
    """
    # D-08 condition 1, checked as a *place* rather than as a branch name. The gate caught the
    # name version twice over: a blank path resolved to the current directory, which was Mushegh's own
    # repo, and a worktree whose branch merely wasn't called "main" was accepted — so a dirty
    # owner checkout passed in here would have been committed to. A worktree this module did not
    # create is not a dedicated branch, whatever its HEAD says.
    if not str(worktree).strip():
        return Landed(stage="commit", branch=branch,
                      reason="no worktree was named, and an empty path means the current directory")
    tree = Path(worktree)
    try:
        inside = tree.resolve() != worktree_root().resolve() and             worktree_root().resolve() in tree.resolve().parents
    except Exception:  # noqa: BLE001
        inside = False
    if not inside:
        return Landed(stage="commit", branch=branch, worktree=str(tree),
                      reason=f"{tree} is not a worktree I created, so I stopped rather than commit "
                             "into a checkout that isn't mine (D-08 condition 1)")
    if not tree.exists():
        return Landed(stage="commit", branch=branch, reason=f"{tree} is gone, so there is nothing "
                                                            "left to commit")
    rc, head_branch = await _git(tree, "rev-parse", "--abbrev-ref", "HEAD")
    if rc != 0 or head_branch.strip() != branch:
        return Landed(stage="commit", branch=branch, worktree=str(tree),
                      reason=f"that worktree is on {head_branch.strip() or 'an unknown branch'}, "
                             f"not {branch}, so I stopped rather than commit to the wrong place")

    rc, diff = await _full_diff(tree)
    if rc != 0:
        return Landed(stage="diff", branch=branch, worktree=str(tree),
                      reason=f"I couldn't re-read the change before committing: {diff[:300]}")
    if (found := migration_in(diff)):
        return Landed(stage="migration", branch=branch, worktree=str(tree), diff=diff,
                      reason=f"D-08 forbids a self-edit that introduces a schema migration — {found}")
    suite = run_suite or _default_suite
    green, failures = await suite(tree)
    if not green:
        return Landed(stage="tests", branch=branch, worktree=str(tree), diff=diff,
                      reason=f"the suite went red between your approval and the commit. {failures}"
                             .strip())

    rc, out = await _git(tree, "add", "-A")
    if rc != 0:
        return Landed(stage="commit", branch=branch, worktree=str(tree), diff=diff,
                      reason=f"I couldn't stage the change: {out[:300]}")
    from mushegh.config import settings

    who = result.executor if result else "an external executor"
    message = (f"{brief.task[:68]}\n\nDelegated by Mushegh to {who}.\nAcceptance: {brief.acceptance}\n"
               f"Approved by the owner on branch {branch} (D-08).")
    rc, out = await _git(
        tree,
        "-c", f"user.name={settings.git_author_name}",
        "-c", f"user.email={settings.git_author_email}",
        "commit", "-m", message,
    )
    if rc != 0:
        return Landed(stage="commit", branch=branch, worktree=str(tree), diff=diff,
                      reason=f"the commit didn't go through: {out[:300]}")
    _audit(brief, branch, who, diff)
    return Landed(stage="commit", branch=branch, worktree=str(tree), diff=diff, committed=True,
                  result=result)


async def _maybe_await(value):
    """Accept a sync or async ``ask_owner``. One call site, so this is cheaper than two branches."""
    if asyncio.iscoroutine(value) or isinstance(value, asyncio.Future):
        return await value
    return value


def _audit(brief: Brief, branch: str, executor: str, diff: str) -> None:
    """D-80's falsifier: a diff landing with no owner approval recorded in `audit.py`.

    The diff itself is not written — it is the whole proposed change and the audit trail is not a
    patch store. Its size and the files it touched are what a review needs to find the commit.
    """
    files = sorted({line.split(" b/")[-1] for line in diff.splitlines()
                    if line.startswith("diff --git ")})
    try:
        from mushegh.brain import audit

        audit.record(
            "delegate_coding",
            {"branch": branch, "executor": executor, "repo": brief.repo,
             "files": files[:40], "diff_lines": len(diff.splitlines())},
            f"committed to {branch}",
            actor="mushegh:delegate_coding",
            decision="allow",
            rule="D-08 (branch, green suite, no migration, owner approved)",
        )
    except Exception as e:  # noqa: BLE001 — auditing must never break the landing it records
        logger.warning(f"delegate_coding: audit line failed ({type(e).__name__})")


def available() -> bool:
    """Whether this path can run at all. Measured, not asserted."""
    return shutil.which("git") is not None
