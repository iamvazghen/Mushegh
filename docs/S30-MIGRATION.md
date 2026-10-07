# S30 migration — CANCELLED 2026-10-03

> [!danger] **This migration is cancelled. Do not resume it.**
> The owner reviewed it on 2026-10-03 and called it blueprint cargo-culting and dead
> weight. SQLite was the correct call from day one. This file is a **cancellation
> record**, not a runbook — it exists because `docs/systems-plan.json` cites this path in
> the evidence for `30.F1` and `30.F2`, and because the scaffolding it describes still
> needs deleting.
>
> Decision: **[`docs/DECISIONS.md`](DECISIONS.md) D-02**. Registry corrections:
> **[`docs/REGISTRY-RECONCILIATION.md`](REGISTRY-RECONCILIATION.md) §A**.

---

## The decision

> SQLite was the correct call from day one; Postgres is blueprint cargo-culting. The
> migration is dead weight and should be formally cancelled. (owner, 2026-10-03)

And, in the owner's own list of regrets: *"staging the PostgreSQL multi-adapter
migration."* What is defended instead: *"keeping the primary state machine on SQLite WAL
mode backed by Tailscale networking."*

## Why the blueprint lost

The JARVIS blueprint specified PostgreSQL 16 with pgvector and Apache AGE as the
knowledge substrate. The deciding question was the one that governs every other decision
in this project:

> If it fails at 2:00 AM, can I debug it in 90 seconds with `journalctl`, `sqlite3` and
> `curl`?

`sqlite3` reads the store directly. PostgreSQL needs a server, a connection, a role, a
schema, and a mental model of which of ten stores migrated. For a single operator, the
first is an answer and the second is a project.

Two further reasons, both now decisions:

- **Legacy continuity (D-54).** In 2036 the vault must open as plain markdown and the
  state must be queryable with vanilla command-line tools. A standard SQLite file is
  exactly that; a Postgres cluster is not.
- **The vector work was going anyway (D-26).** The graph relation layer — the main
  motivation for pgvector and AGE — is being deleted for producing stale, irrelevant
  semantic noise. Migrating the substrate that served it would have been expensive work
  in defence of a subsystem that should not exist.

## What was built before the stop (2026-09-21)

Recorded here so the effort is not lost, and so nobody re-derives it:

- **Batch 1 — offline snapshot safety.** `src/afon/brain/store_migration.py` (removed
  2026-10-04, D-02/M02): read-only inventory plus guarded, verifiable SQLite snapshots.
  `dbconn.connect(..., read_only=True)` was the only runtime module extended. 29/29 offline
  snapshot tests. **The snapshot capability itself was not lost** — `afon.protocols.backup`
  provides `make_backup` / `verify_backup` / `restore_backup` / `run_restore_drill`, and
  `bench/test_s30_migration_removed.py` proves it with a real round trip.
- **Batch 2 — client boundary.** An inert, role- and PID-gated PostgreSQL client with an
  optional driver, secret configuration and audit redaction. 37/37 layering and 50/50
  single-origin regressions.
- **Vector adapter staged.** 1 of 8 discovered SQLite-backed stores had an explicit
  PostgreSQL adapter and staging DDL. Not wired into startup; never executed against a
  real PostgreSQL.

Thirteen targeted suites totalled 324 passing checks at the stop. **Live PostgreSQL
evidence was zero.** No production data was copied and no dual-write path ever existed, so
**there is nothing to unwind and no migration to reverse.**

## What was deleted (roadmap M02 — done 2026-10-04)

- `src/afon/brain/postgres_client.py` — removed
- `src/afon/brain/postgres_vectors.py` — removed
- `src/afon/brain/store_migration.py` — removed, after checking as the bullet above asked: nothing
  outside the cancelled migration used its snapshot helper, and the capability itself is
  better served by `afon.protocols.backup` than by keeping scaffolding with a backup
  utility bolted on
- `src/afon/brain/sql/postgres_vectors.sql`
- The optional `psycopg` dependency: the `postgres` extra is out of `pyproject.toml` and
  `uv lock` no longer resolves either psycopg wheel
- The `postgres_dsn` setting, and the `AFON_POSTGRES_DSN` block in `.env.example`
- `bench/test_store_migration_snapshot.py` and `bench/test_postgres_vectors.py` — both
  removed, so neither path resolves any more
- `30.F1`, `30.R5`, `30.R6`, `30.R7`, `30.R8`, `30.R9` in the registry

**Kept, on purpose:** the `!postgres` entry in `data_classes.STORES` and `afon_graph.sqlite`
in the migration list — a host that ran the adapters may still have that file on disk, and
an unclassified store is exactly what that table exists to prevent.

**Proof:** `bench/test_s30_migration_removed.py`, 25/25 — no module, no DSN, no psycopg, and
a real backup → verify → restore → drill round trip through `afon.protocols.backup`.

**Keep** `30.R1` (ranked merge with dedup), `30.R2` (contradiction handling), `30.R3`
(forgetting as policy) — those are memory behaviours, not migration steps.

## What stays true

- SQLite in WAL mode, reached through one module, `src/afon/brain/dbconn.py`.
- The Obsidian vault is the human source of truth; **markdown wins every disagreement**
  with the database (D-22). This was true throughout the migration and is more important
  now that the migration is gone.
- Every store must stay legible to `sqlite3` and a text editor (D-54).
- The laptop stays on its own local database. There is no second store to reconcile
  against, which removes the entire class of problem `30.R8` was written to manage.

## If this ever comes back

It will not be because the blueprint said so. It would need a measured workload that
SQLite cannot serve, on this single machine, for this single user. Until that measurement
exists, this file stays closed.
