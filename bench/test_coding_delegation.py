"""M43 — a delegated coding change cannot become a commit unless all four D-08 conditions hold.

D-08 is four sentences in a charter: a dedicated branch, a green suite, zero schema migrations,
and the owner's explicit approval. Four sentences enforce nothing. This gate is the difference,
and it is built around the one failure that matters most: **a refused approval must leave the
owner's checkout exactly as it was.** Not "roughly as it was", and not "as it was plus a branch he
has to clean up" — the same commit, the same working tree, byte for byte.

The three near-misses it also exists to catch:

  1. **The owner asked before the suite is green.** An approval request is an interruption (D-29),
     and asking about a change that cannot land spends one on nothing. Order is a correctness
     property here, so the gate records the order the stages ran in.
  2. **A stale approval committing a changed diff.** An approval resolved an hour later approves a
     diff, not a directory. `commit_approved()` re-proves the other three conditions, and this
     gate makes the suite go red *after* the yes to prove it.
  3. **A discard primitive creeping in.** `tools/coding.py` has no reset, clean, stash or
     branch-delete, deliberately. The gate greps for them, because the cheap fix for a dirty
     worktree is exactly the thing that loses the owner's work.

Hermetic: builds a real throwaway git repo in a temp directory, substitutes `dispatch()` with a
stub that writes a file, and injects the suite and the owner's answer. No executor needs to be
installed, no network, and nothing outside the temp directory is written.

    uv run python bench/test_coding_delegation.py
"""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
import tempfile
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


def git(cwd: Path, *args: str) -> str:
    out = subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True)
    return (out.stdout + out.stderr).strip()


def make_repo(root: Path) -> Path:
    repo = root / "repo"
    (repo / "src").mkdir(parents=True)
    (repo / "src" / "thing.py").write_text("VALUE = 1\n", encoding="utf-8")
    git(repo, "init", "-b", "work")
    git(repo, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "--allow-empty", "-m", "x")
    git(repo, "add", "-A")
    git(repo, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-m", "base")
    return repo


class Fingerprint:
    """The owner's checkout, as one comparable value: its commit, its branch and its tree state."""

    def __init__(self, repo: Path) -> None:
        self.head = git(repo, "rev-parse", "HEAD")
        self.branch = git(repo, "rev-parse", "--abbrev-ref", "HEAD")
        self.dirty = git(repo, "status", "--porcelain")
        self.files = sorted(p.name for p in (repo / "src").iterdir())

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Fingerprint) and vars(self) == vars(other)

    def __repr__(self) -> str:
        return f"<{self.branch}@{self.head[:7]} dirty={self.dirty!r} files={self.files}>"


async def main() -> int:  # noqa: PLR0915 — one linear gate reads better than ten helpers
    import mushegh.brain.executors.landing as L
    from mushegh.brain.executors import Brief, Domain, Result, Tier

    src = (Path(__file__).resolve().parents[1]
           / "src/mushegh/brain/executors/landing.py").read_text(encoding="utf-8")

    # ── D-08 condition 3, in isolation: what counts as a migration ────────────────────────────
    print("\n-- condition 3: schema migrations --")
    check("an added CREATE TABLE is a migration",
          bool(L.migration_in("+++ b/a.py\n+    db.execute('CREATE TABLE t (x int)')\n")))
    check("...case-insensitively",
          bool(L.migration_in("+++ b/a.py\n+ cur.execute('create table if not exists t (x)')\n")))
    check("an ALTER TABLE is a migration",
          bool(L.migration_in("+++ b/a.py\n+ ALTER TABLE users ADD COLUMN x\n")))
    check("a file under migrations/ is a migration",
          bool(L.migration_in("diff --git a/migrations/003_x.sql b/migrations/003_x.sql\n")))
    check("an alembic file is a migration",
          bool(L.migration_in("diff --git a/alembic/versions/a.py b/alembic/versions/a.py\n")))
    check("an ordinary change is not",
          not L.migration_in("+++ b/a.py\n+VALUE = 2\n-VALUE = 1\n"))
    check("a REMOVED create table is not a migration",
          not L.migration_in("+++ b/a.py\n-    db.execute('CREATE TABLE t (x int)')\n"),
          "deleting the thing the rule guards against must not be forbidden by the rule")
    check("the +++/--- headers are not read as content",
          not L.migration_in("+++ b/sql/x.py\n--- a/sql/x.py\n+VALUE = 2\n"),
          "a +++ line starts with + and would otherwise match every path fragment")
    check("the reason names what was found",
          "create table" in L.migration_in("+++ b/a.py\n+ CREATE TABLE t\n").lower())

    # ── the Landed type refuses to describe a refusal with no reason ──────────────────────────
    print("\n-- the outcome type --")
    check("a refusal with no reason is rejected",
          _raises(lambda: L.Landed(stage="tests"), Exception))
    check("an unknown stage is rejected",
          _raises(lambda: L.Landed(stage="nonsense", reason="x"), Exception))
    check("a commit needs no reason", L.Landed(stage="commit", committed=True).committed)
    check("every stage name is in STAGES",
          set(L.STAGES) == {"isolate", "dispatch", "diff", "migration", "tests", "approval",
                            "commit"})

    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        repo = make_repo(root)
        trees = root / "trees"
        L.worktree_root = lambda: trees  # type: ignore[assignment]

        order: list[str] = []

        def stub_dispatch(write: dict[str, str] | None, ok: bool = True, err: str = ""):
            async def _d(brief, *, chosen=None):
                order.append("dispatch")
                for rel, text in (write or {}).items():
                    p = Path(brief.repo) / rel
                    p.parent.mkdir(parents=True, exist_ok=True)
                    p.write_text(text, encoding="utf-8")
                return Result(executor="claude-code", domain=brief.domain,
                              exit_code=0 if ok else 2, transcript="did it",
                              error=err if not ok else "")
            return _d

        def suite(green: bool):
            async def _s(cwd):
                order.append("tests")
                return green, ("" if green else "test_x 1 failed")
            return _s

        def owner(answer):
            async def _a(diff):
                order.append("approval")
                return answer
            return _a

        def brief(task="raise VALUE to two in src/thing.py") -> Brief:
            return Brief(domain=Domain.CODING, task=task, tier=Tier.CORPORATE,
                         acceptance="src/thing.py reads VALUE = 2", repo=str(repo))

        # ── refusals before anything starts ──────────────────────────────────────────────────
        print("\n-- refused before a process starts --")
        order.clear()
        check("a non-coding brief never reaches this path",
              await _refuses(L, Brief(domain=Domain.FINANCE, task="rebalance the portfolio",
                                      acceptance="a report exists")))
        check("...and nothing ran", order == [], str(order))

        print("\n-- a dirty owner checkout is a stale base, and is refused --")
        L.dispatch = stub_dispatch({"src/thing.py": "VALUE = 2\n"})  # type: ignore[assignment]
        (repo / "src" / "owner_wip.py").write_text("WIP = True\n", encoding="utf-8")
        before = Fingerprint(repo)
        order.clear()
        got = await L.delegate_coding(brief(), run_suite=suite(True), ask_owner=owner(True))
        check("A WORKTREE IS NOT CUT FROM HEAD WHILE THE OWNER HAS MOVED PAST IT",
              not got.committed and got.stage == "isolate", f"{got.stage}: {got.reason}")
        check("...and the refusal counts the changes rather than gesturing at them",
              "1 uncommitted change" in got.reason, got.reason)
        check("...and says what to do about it",
              "commit or stash" in got.reason.lower(), got.reason)
        check("NO EXECUTOR WAS PAID TO WORK AGAINST STALE CODE", order == [], str(order))
        check("no worktree was created for it", not got.worktree, got.worktree)
        check("the owner's own work in progress is untouched",
              Fingerprint(repo) == before and (repo / "src" / "owner_wip.py").exists())
        (repo / "src" / "owner_wip.py").unlink()
        check("a clean checkout proceeds again",
              (await L.delegate_coding(brief(), run_suite=suite(True),
                                       ask_owner=owner(True))).committed)

        # ── the happy path: all four hold ────────────────────────────────────────────────────
        print("\n-- all four conditions hold --")
        before = Fingerprint(repo)
        L.dispatch = stub_dispatch({"src/thing.py": "VALUE = 2\n"})  # type: ignore[assignment]
        order.clear()
        got = await L.delegate_coding(brief(), run_suite=suite(True), ask_owner=owner(True))
        check("it committed", got.committed, got.reason)
        check("the stage is commit", got.stage == "commit", got.stage)
        check("the branch is a dedicated one, not the working branch",
              got.branch.startswith("mushegh/delegated-") and got.branch != before.branch, got.branch)
        second = L._branch_name()
        check("two branch names in the same second do not collide",
              second != L._branch_name(),
              "the clock-only version refused a legitimate second delegation")
        check("the suite ran before the owner was asked",
              order.index("tests") < order.index("approval"), str(order))
        check("the executor ran before the suite", order.index("dispatch") < order.index("tests"))
        check("the commit is on that branch",
              git(Path(got.worktree), "rev-parse", "--abbrev-ref", "HEAD") == got.branch)
        check("the branch has exactly one new commit",
              len(git(Path(got.worktree), "log", "--oneline", f"{before.head}..HEAD")
                  .splitlines()) == 1)
        check("the commit message names the acceptance check",
              "VALUE = 2" in git(Path(got.worktree), "log", "-1", "--pretty=%B"))
        check("the commit message names the executor",
              "claude-code" in git(Path(got.worktree), "log", "-1", "--pretty=%B"))
        check("the worktree is outside the repo",
              repo not in Path(got.worktree).parents, got.worktree)
        check("THE OWNER'S CHECKOUT IS UNCHANGED BY A SUCCESSFUL LANDING",
              Fingerprint(repo) == before, f"{before} -> {Fingerprint(repo)}")
        check("the owner's branch does not have the commit",
              git(repo, "rev-parse", "HEAD") == before.head)

        # ── a refused approval ───────────────────────────────────────────────────────────────
        print("\n-- the owner declines --")
        before = Fingerprint(repo)
        order.clear()
        got = await L.delegate_coding(brief(), run_suite=suite(True), ask_owner=owner(False))
        check("it did not commit", not got.committed)
        check("it stopped at approval", got.stage == "approval", got.stage)
        check("A REFUSED APPROVAL LEAVES THE OWNER'S CHECKOUT UNTOUCHED",
              Fingerprint(repo) == before, f"{before} -> {Fingerprint(repo)}")
        check("no commit exists on the branch",
              git(Path(got.worktree), "log", "--oneline", f"{before.head}..HEAD") == "")
        check("the proposal is kept, not discarded", Path(got.worktree).exists())
        check("the reason says where it is", got.worktree in got.reason, got.reason)
        check("the diff is reported back", "VALUE = 2" in got.diff, got.diff[:200])

        # ── not yet answered ────────────────────────────────────────────────────────────────
        print("\n-- the owner has not answered yet --")
        got_pending = await L.delegate_coding(brief(), run_suite=suite(True), ask_owner=None)
        check("an unanswered approval is not a refusal in substance, but is not a commit",
              not got_pending.committed and got_pending.stage == "approval")
        check("it says three of four hold", "three of the four" in got_pending.reason,
              got_pending.reason)
        check("it names the branch so the owner can look",
              got_pending.branch in got_pending.reason)

        # ── condition 2: a red suite ────────────────────────────────────────────────────────
        print("\n-- condition 2: the suite is red --")
        before = Fingerprint(repo)
        order.clear()
        got = await L.delegate_coding(brief(), run_suite=suite(False), ask_owner=owner(True))
        check("it did not commit", not got.committed)
        check("it stopped at tests", got.stage == "tests", got.stage)
        check("THE OWNER WAS NEVER ASKED ABOUT A CHANGE THAT CANNOT LAND",
              "approval" not in order, str(order))
        check("the failures are reported, not just the verdict",
              "test_x 1 failed" in got.reason, got.reason)
        check("the owner's checkout is untouched", Fingerprint(repo) == before)

        # ── condition 3: a migration ────────────────────────────────────────────────────────
        print("\n-- condition 3: the diff adds a migration --")
        before = Fingerprint(repo)
        order.clear()
        L.dispatch = stub_dispatch(  # type: ignore[assignment]
            {"src/thing.py": "VALUE = 2\ndb.execute('ALTER TABLE t ADD COLUMN x')\n"})
        got = await L.delegate_coding(brief(), run_suite=suite(True), ask_owner=owner(True))
        check("it did not commit", not got.committed)
        check("it stopped at migration", got.stage == "migration", got.stage)
        check("THE SUITE WAS NEVER RUN FOR A DIFF THAT CANNOT LAND",
              "tests" not in order, str(order))
        check("the owner was never asked", "approval" not in order, str(order))
        check("it cites D-08", "D-08" in got.reason, got.reason)
        check("the owner's checkout is untouched", Fingerprint(repo) == before)

        # ── the executor itself failed ──────────────────────────────────────────────────────
        print("\n-- the executor failed --")
        before = Fingerprint(repo)
        L.dispatch = stub_dispatch(None, ok=False,  # type: ignore[assignment]
                                   err="claude-code exceeded its 900s deadline")
        got = await L.delegate_coding(brief(), run_suite=suite(True), ask_owner=owner(True))
        check("it stopped at dispatch", got.stage == "dispatch", got.stage)
        check("the reason is the executor's own error",
              "900s deadline" in got.reason, got.reason)
        check("a failed executor is never reported as a landing", not got.committed)
        check("the owner's checkout is untouched", Fingerprint(repo) == before)

        # ── the executor changed nothing ────────────────────────────────────────────────────
        print("\n-- the executor changed nothing --")
        L.dispatch = stub_dispatch({})  # type: ignore[assignment]
        got = await L.delegate_coding(brief(), run_suite=suite(True), ask_owner=owner(True))
        check("it stopped at diff", got.stage == "diff", got.stage)
        check("an empty change is not a success", not got.committed)
        check("it says no file changed", "without changing any file" in got.reason, got.reason)

        # ── a NEW file counts as a change ───────────────────────────────────────────────────
        print("\n-- a new file is a change, not an empty diff --")
        L.dispatch = stub_dispatch({"src/new.py": "X = 1\n"})  # type: ignore[assignment]
        got = await L.delegate_coding(brief(), run_suite=suite(True), ask_owner=owner(True))
        check("an untracked new file is not read as 'nothing changed'",
              got.committed, f"{got.stage}: {got.reason}")
        check("the new file is in the commit",
              "src/new.py" in git(Path(got.worktree), "show", "--name-only", "--pretty=", "HEAD"))

        # ── commit_approved re-proves the other three ──────────────────────────────────────
        print("\n-- a stale approval is re-proved, not trusted --")
        L.dispatch = stub_dispatch({"src/thing.py": "VALUE = 2\n"})  # type: ignore[assignment]
        staged = await L.delegate_coding(brief(), run_suite=suite(True), ask_owner=None)
        before = Fingerprint(repo)
        got = await L.commit_approved(brief(), branch=staged.branch, worktree=staged.worktree,
                                      run_suite=suite(False))
        check("an approval cannot land a change whose suite has since gone red",
              not got.committed and got.stage == "tests", f"{got.stage}: {got.reason}")
        check("it says the suite went red after the approval",
              "between your approval and the commit" in got.reason, got.reason)

        tree = Path(staged.worktree)
        (tree / "src" / "late.py").write_text("db.execute('DROP TABLE users')\n", encoding="utf-8")
        got = await L.commit_approved(brief(), branch=staged.branch, worktree=tree,
                                      run_suite=suite(True))
        check("A MIGRATION IN A FILE THE EXECUTOR CREATED IS STILL A MIGRATION",
              not got.committed and got.stage == "migration", f"{got.stage}: {got.reason}")
        (tree / "src" / "late.py").unlink()

        got = await L.commit_approved(brief(), branch=staged.branch, worktree=tree,
                                      run_suite=suite(True))
        check("with all three re-proved, the approval lands", got.committed, got.reason)
        check("the owner's checkout is still untouched", Fingerprint(repo) == before)

        print("\n-- condition 1 is checked at the commit, not only at the branch --")
        got = await L.commit_approved(brief(), branch="work", worktree=repo, run_suite=suite(True))
        check("it refuses to commit into the owner's own checkout",
              not got.committed, got.reason)
        check("...naming the branch mismatch rather than committing to the wrong place",
              "not work" in got.reason or "rather than commit" in got.reason, got.reason)
        check("the owner's checkout survived being passed in as the worktree",
              Fingerprint(repo) == before, f"{before} -> {Fingerprint(repo)}")

        got = await L.commit_approved(brief(), branch="gone", worktree=trees / "nope",
                                      run_suite=suite(True))
        check("a vanished worktree is reported, not crashed through",
              not got.committed and "gone" in got.reason, got.reason)

        # ── the audit line (D-80's falsifier) ──────────────────────────────────────────────
        print("\n-- the audit line D-80 requires --")
        lines: list[tuple] = []

        class FakeAudit:
            @staticmethod
            def record(tool, args, result, **kw):
                lines.append((tool, args, result, kw))

        import mushegh.brain as _brain
        real_audit = _brain.audit
        _brain.audit = FakeAudit  # type: ignore[assignment]
        L.dispatch = stub_dispatch({"src/thing.py": "VALUE = 3\n"})  # type: ignore[assignment]
        got = await L.delegate_coding(brief(), run_suite=suite(True), ask_owner=owner(True))
        _brain.audit = real_audit
        check("a landing writes an audit line", got.committed and len(lines) == 1, str(lines))
        if lines:
            tool, args, _res, kw = lines[0]
            check("the line names the rule it was permitted under",
                  "D-08" in kw.get("rule", ""), kw.get("rule", ""))
            check("the line is attributed to the delegation, not the owner",
                  kw.get("actor") == "mushegh:delegate_coding", str(kw.get("actor")))
            check("the line names the branch and the executor",
                  args.get("branch") == got.branch and args.get("executor") == "claude-code")
            check("the line names which files changed",
                  "src/thing.py" in str(args.get("files")), str(args.get("files")))
            check("the DIFF BODY is not written to the audit trail",
                  "VALUE = 3" not in str(args), "the audit log is not a patch store")

        # ── the default suite, on a repo that has none ────────────────────────────────────
        print("\n-- the default suite --")
        green, why = await L._default_suite(repo)
        check("a repo with no bench/run_all_tests.py cannot satisfy condition 2",
              not green and "run_all_tests" in why, why)
        check("...and says so rather than reporting red",
              "cannot be checked" in why, why)

    # ── the source itself: no discard primitive, no push, no credential ──────────────────
    print("\n-- what this module must never contain --")
    for banned in ("reset --hard", '"reset"', '"clean"', '"stash"', "branch -D", '"push"',
                   '"checkout"'):
        check(f"no {banned}", banned not in src,
              "tools/coding.py has no discard primitive by design; neither does this")
    # The whole git vocabulary this module is allowed, enumerated — so a verb added later has to
    # be added here too, deliberately, rather than arriving in a diff nobody reads twice.
    allowed = {"worktree", "add", "commit", "diff", "rev-parse"}
    used = {v for v in ("worktree", "add", "commit", "diff", "rev-parse", "rm", "mv", "merge",
                        "rebase", "cherry-pick", "revert", "switch", "restore", "gc", "prune",
                        "filter-branch", "update-ref", "symbolic-ref", "fetch", "pull", "remote")
            if f'"{v}"' in src}
    check("it uses no git verb outside its declared vocabulary",
          used <= allowed, f"unexpected: {sorted(used - allowed)}")
    check("...and it does use the ones it declares", used == allowed, f"missing: {sorted(allowed - used)}")
    check("no shell: every git call is argv",
          "shell=True" not in src and "create_subprocess_shell" not in src)
    check("the child gets no stdin", src.count("DEVNULL") >= 2)
    check("the migration scan sees files the executor created",
          "--intent-to-add" in src, "git diff HEAD does not show an untracked file")
    check("the suite runs against the WORKTREE's sources, not the installed package",
          "PYTHONPATH" in src and 'Path(cwd) / "src"' in src)
    check("the worktree lives outside the repo",
          "state_dir()" in src, "a worktree inside the repo would itself be a repo change")
    check("delegate_coding never commits directly — it calls the second half",
          "commit_approved(" in src.split("async def commit_approved")[0])
    check("the module is honest about being reachable only with git",
          "shutil.which" in src)

    print(f"\n=== {passed + failed} checks: {passed} passed, {failed} failed ===")
    if not failed:
        print("ALL CHECKS PASSED ===")
    return 1 if failed else 0


def _raises(fn, exc) -> bool:
    try:
        fn()
    except exc:
        return True
    except Exception:  # noqa: BLE001
        return False
    return False


async def _refuses(L, brief) -> bool:
    from mushegh.brain.executors import BriefRefused

    try:
        await L.delegate_coding(brief)
    except BriefRefused:
        return True
    except Exception:  # noqa: BLE001
        return False
    return False


if __name__ == "__main__":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    raise SystemExit(asyncio.run(main()))
