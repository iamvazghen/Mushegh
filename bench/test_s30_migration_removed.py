"""M02 — the staged Postgres migration is gone, and what replaced it still works.

D-02 cancelled the PostgreSQL migration on 2026-10-03; M02 carried the deletion out on
2026-10-04. A deletion is the easiest kind of change to declare and the hardest to verify,
because nothing fails when a file is simply absent — so this gate asserts the *absence* on
purpose, and then does the part that actually matters.

**The important half is [3].** `store_migration.py` was not only migration scaffolding: it
held a read-only inventory and guarded, verifiable SQLite snapshots. Deleting it is only
safe because `mushegh.protocols.backup` provides the real thing. So this gate does a full
backup → verify → restore → drill round trip on a temp directory. A test that only checked
the scaffolding was removed would have been satisfied by a machine that cannot back up at
all, which is the failure this is written against.

Also asserted here, because each was a live reference to code that no longer exists:

  * nothing under `src/` imports or names the three removed modules or the SQL schema;
  * `Settings` has no `postgres_dsn` — a credential that cannot select a backend is one
    that only looks like an option;
  * `pyproject.toml` has no `postgres` extra and `uv.lock` no longer resolves psycopg;
  * `.env.example` no longer advertises `MUSHEGH_POSTGRES_DSN`;
  * **the `!postgres` data-classification rule was deliberately KEPT** and is asserted here,
    because a future tidy-up that removes it would silently drop a privacy classification
    for a directory that may still exist on someone's disk;
  * SQLite is still the store, proven by a real round trip rather than by reading a comment.

Hermetic: temp directories, no network, no database server.

    uv run python bench/test_s30_migration_removed.py
"""

from __future__ import annotations

import re
import sys
import tempfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

passed = failed = 0


def check(name: str, ok: bool, detail: str = "") -> None:
    global passed, failed
    if ok:
        passed += 1
        print(f"  [PASS] {name}")
    else:
        failed += 1
        print(f"  [FAIL] {name}  {detail}")


GONE_MODULES = ("mushegh/brain/postgres_client.py", "mushegh/brain/postgres_vectors.py",
                "mushegh/brain/store_migration.py", "mushegh/brain/sql/postgres_vectors.sql")
GONE_TESTS = ("test_postgres_vectors.py", "test_store_migration_snapshot.py")


def main() -> int:
    print("[1] the scaffolding is gone from disk")
    for rel in GONE_MODULES:
        check(f"{rel} is not on disk", not (ROOT / "src" / rel).exists())
    for name in GONE_TESTS:
        check(f"bench/{name} is not on disk", not (ROOT / "bench" / name).exists())
    check("the now-empty sql/ directory went with it",
          not (ROOT / "src" / "mushegh" / "brain" / "sql").exists()
          or not any((ROOT / "src" / "mushegh" / "brain" / "sql").iterdir()))

    print("\n[2] nothing left references it")
    offenders: list[str] = []
    pattern = re.compile(r"postgres_client|postgres_vectors|store_migration|PostgresClient|"
                         r"PostgresVectorStore")
    for path in sorted((ROOT / "src").rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        for num, line in enumerate(path.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
            if pattern.search(line):
                offenders.append(f"{path.relative_to(ROOT).as_posix()}:{num}")
    check("no module under src/ mentions the removed code", not offenders, str(offenders[:5]))

    runner = (ROOT / "bench" / "run_all_tests.py").read_text(encoding="utf-8", errors="ignore")
    stale = [n for n in GONE_TESTS if n in runner]
    check("the test runner has no entry for the removed tests", not stale, str(stale))

    print("\n[3] what replaced the snapshot helper actually works")
    from mushegh.brain.memory import MemoryStore
    from mushegh.protocols import backup

    with tempfile.TemporaryDirectory(prefix="mushegh-m02-") as td:
        base = Path(td)
        memory = base / "memory"
        (memory / "learned").mkdir(parents=True)
        store = MemoryStore(base_dir=memory)
        store.remember("The garage remote is in the kitchen drawer", source="owner")
        store.remember("He prefers tea in the morning", source="owner")
        check("a store was seeded", store.count() == 2, str(store.count()))

        archive = backup.make_backup(memory, base / "backups")
        check("a backup was written", archive.exists() and archive.stat().st_size > 0, str(archive))

        verified = backup.verify_backup(archive)
        check("...and verifies", bool(verified.get("ok")), str(verified)[:160])

        # Restore somewhere else: a backup that only restores over itself proves nothing.
        target = base / "restored"
        target.mkdir()
        backup.restore_backup(archive, target, force=True)
        restored = MemoryStore(base_dir=target)
        got = [n.text for n in restored._iter_notes()]            # noqa: SLF001
        check("...and restores into a fresh directory with its facts intact",
              len(got) == 2 and any("kitchen drawer" in g for g in got), str(got))

        # `record_to` is passed EXPLICITLY. Left at its default it writes the drill record into
        # the real state root — which is right for the owner and wrong for a test, and the
        # first version of this gate did exactly that and left a `restore_drill.json` in ~/.mushegh.
        # A test that touches the owner's state is not a hermetic test, it is a bug with a
        # green checkmark.
        drill = backup.run_restore_drill(backups=base / "backups",
                                        record_to=base / "restore_drill.json")
        check("a restore drill runs end to end", isinstance(drill, dict) and bool(drill),
              str(drill)[:160])
        check("...and its record is written where the test asked, in the temp dir",
              (base / "restore_drill.json").exists(), str(base))

    print("\n[4] the store is still SQLite, proven rather than asserted in a comment")
    with tempfile.TemporaryDirectory(prefix="mushegh-m02-sqlite-") as td:
        store = MemoryStore(base_dir=Path(td))
        store.remember("SQLite holds this", source="owner")
        check("a fact round-trips through the real store", store.recall("SQLite"), "")
        from mushegh.config import Settings
        check("Settings has no postgres_dsn to select a backend",
              "postgres_dsn" not in Settings.model_fields)

    print("\n[5] the privacy rule for a legacy Postgres directory was kept on purpose")
    from mushegh.brain import data_classes as dc
    rule = next((s for s in dc.STORES if s.name == "!postgres"), None)
    check("the !postgres classification still exists", rule is not None)
    check("...and still carries the classes a database of owner data would hold",
          rule is not None and {"medical", "financial"} <= set(rule.classes),
          str(getattr(rule, "classes", None)))
    check("...and is allowed to leave the host, as owner data legitimately may",
          rule is not None and rule.leaves_host is True, str(getattr(rule, "leaves_host", None)))
    check("...and the store it names still resolves to that declaration",
          (dc.classify("!postgres") is not None)
          and (dc.classify("!postgres/notes.md") is not None
               or dc.classify("!postgres") is rule),
          str(dc.classify("!postgres")))

    print("\n[6] the dependency is gone from the project metadata too")
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8", errors="ignore")
    # A requirement line, not the bare word: the file keeps a comment naming what was removed,
    # and a comment is not a dependency.
    check("pyproject declares no psycopg requirement",
          not re.search(r'^\s*"psycopg', pyproject, re.M))
    check("pyproject has no postgres extra", not re.search(r"^postgres\s*=", pyproject, re.M))
    lock = (ROOT / "uv.lock").read_text(encoding="utf-8", errors="ignore")
    check("the lockfile no longer resolves psycopg", "psycopg" not in lock)
    env = (ROOT / ".env.example").read_text(encoding="utf-8", errors="ignore")
    check(".env.example no longer advertises MUSHEGH_POSTGRES_DSN", "MUSHEGH_POSTGRES_DSN=" not in env)

    print(f"\n=== {passed + failed} checks: {passed} passed, {failed} failed ===")
    if not failed:
        print("ALL CHECKS PASSED ===")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
