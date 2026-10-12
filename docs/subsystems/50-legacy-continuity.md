# S50 — Legacy Continuity & Knowledge Preservation

> **One line:** In 2036 the owner opens plain markdown files and queries a standard SQLite
> database with vanilla command-line tools, without running this framework — and what
> survives is chosen by policy, not by keeping everything.
> **Status:** half-built — the substrate exists, the continuity policy does not · **Registry:** S50 · 3/3 floor, 0/3 raise, 0/1 elite
> **Milestones:** M07, M32 · **Decisions:** D-54, D-22, D-21, D-46

**This system is dark, and dark is not a status** (D-46). The floor is code-complete and
passing; the raise tier is unstarted; and the thing that would make it real is not code. It
is an owner's decision about **what continuity should preserve, and for whom** — a question
M07 carries, and one that cannot be answered by a benchmark. Until it is answered, the
honest description is a finished export nobody has decided is worth anything.

## Purpose

Preservation that outlives the program. Not a backup — a backup is a tar of this program's
private layout, with sqlite schemas living in the code and a JSONL whose fields are named in
a dataclass, and restoring it needs Mushegh. That is the opposite of preservation.

The requirement is **boring formats** (D-54): every store must be legible to `sqlite3` and
readable in a text editor in 2036, with no framework, no migration tool and no person who
remembers this codebase. Underneath that sits the older rule: **the vault is the human
source of truth, SQLite is the runtime cache, and markdown wins every disagreement** (D-22).
Every cache-mirroring path needs a reconciliation path that can lose an argument to a file.

The missing piece is **curation** (50.R1). What is worth preserving is decided by policy,
not by keeping everything: retention says 30 days for the ephemeral and keep-forever for
curated notes (D-21), and "curated" currently has no definition. A continuity system that
preserves all of it preserves nothing, because the export is then a copy of a state
directory rather than a set of things a person wanted in 2036.

If this is absent: when the framework is abandoned, the knowledge goes with it, and the owner
is left with a tar of someone else's private layout.

## Structure

- `src/mushegh/protocols/portable.py` — 50.F1/F2. `export(dest)` writes memory, journal,
  documents and an audit **summary** as markdown or JSON, plus a README in plain language
  and a MANIFEST carrying a sha256 per file. Three properties, in order: readable without
  the codebase (no pickles, no sqlite, no field that means something only because a class
  says so); honest about what is missing (an absent store is listed as absent, because an
  export that silently omits half the memory looks exactly like an export of half as much
  memory); verified on a schedule. `verify(root)` re-checks the hashes, `run_export_drill()`
  performs the restore drill and `last_drill()` reads the last record.
  The load-bearing check is in `bench/test_portable_export.py`: a **fresh interpreter with
  `mushegh` removed from the path** re-reads the export end to end. Asserting readability from
  inside a process that has already imported the package proves nothing.
- `src/mushegh/brain/memory.py` — the L1 learned notes and L2 journal as one markdown file per
  fact. This is the substrate that makes the export readable: the store is already text.
- `src/mushegh/brain/tools/vault.py` — 50.F3. The vault-write rule is enforced in code, not only
  in a document: `replica_reason(root)` recognises a local copy from the sync marker, and
  `VaultIsReplica` makes `write_note` refuse even when `MUSHEGH_VAULT_WRITABLE` says yes. The
  directory wins over the flag, because the directory is the thing that will lose the note at
  the next pull.
- `src/mushegh/brain/inventory.py` and `src/mushegh/brain/maintenance.py` — declared retention per
  store and the job that enforces it. `sweep_retention` is what D-21 means in practice; it is
  also what will eventually delete something worth keeping if curation is never defined.
- `scripts/merge_memory.py` — the human half of 30.F1. It does not choose between two hosts'
  learned notes; it **unions** them, because a fact only one host was ever told is not stale,
  it is the only copy.
- `src/mushegh/protocols/` alongside it — the export shares the protocols layer, which is where
  the rest of this program's own backups live.

Ownership: the brain process writes the export; the vault remains the authority; `restic`
owns the off-site copy and is not duplicated here.

## Goals

1. The export is readable by a person with no codebase, proved by reading it in a process
   that never imports `mushegh` (50.F1, D-54).
2. The export is restored on a schedule into an empty environment, and the drill is
   recorded (50.F2).
3. The vault-write rule is enforced in code, so a note can never be written to a copy that
   the next sync will delete (50.F3).
4. Curation: a stated policy decides what is preserved, and it can lose an argument against
   keeping everything (50.R1).
5. Provenance on preserved knowledge — when it was learned, from whom, how confident
   (50.R2).
6. A documented and tested migration path for the next format change (50.R3).

## Benchmarks

1. **B1 (50.F1)** — `bench/test_portable_export.py`. Threshold: the export is written, and
   re-read end to end by a fresh interpreter with `mushegh` off the path; every file in the
   manifest has a matching sha256; an absent store is listed as absent. Registry records
   50.F1 `done` as of 2026-10-03. Last field measurement: `not yet measured`.
2. **B1 (50.F2)** — `bench/test_backup_restore.py` and the drill in
   `src/mushegh/protocols/portable.py`. Threshold: a restore into an empty environment returns
   both the vault and the database legible to `sqlite3` (D-54). Registry records 50.F2
   `done`; the *drill* on a schedule is what M32 lands. Last measurement: `not yet measured`.
3. **B1 (50.F3)** — `bench/test_vault_search.py [50.F3]`. Threshold: a replica refuses the
   write whatever the flag says, 0 markdown files written, and one writer path exists so the
   rule cannot be walked around. Registry records 50.F3 `done`.
4. **B1 planned (`50.R1`)** — the export's `[curation]` case: a policy names what is
   preserved, and the export reflects it. Last measurement: `not yet measured` — there is no
   policy, which is why the system is dark rather than half-finished.
5. **B1 planned (`50.R2`)** — the `[provenance]` case: preserved knowledge carries when it
   was learned, from whom, and with what confidence. Last measurement: `not yet measured`.
6. **B1 planned (`50.R3`)** — the `[migration]` case: a format change has a documented, tested
   path forward. Last measurement: `not yet measured`.
7. **B2 (`50.E1`)** — the cold-start drill: a new machine, the export, and nothing else, and
   a working Mushegh is rebuilt from it. Threshold: no access to the original host, no import of
   this framework's internals. Last measurement: `not yet measured` — this is the benchmark
   that would settle whether the system is worth anything, and it has never been run.
8. **B3** — seven consecutive days of real use with no manual patching (D-43) applies to the
   export as much as to any capability. Last measurement: `not yet measured`.

## Failure modes

**The export needs Mushegh to read.** The one failure the whole system exists to prevent, and
the one that is invisible from inside the framework:

    python -c "from mushegh.protocols.portable import verify; from mushegh.shared.paths import state_dir; print(verify(state_dir()/'export'))"
    ls -la "$MUSHEGH_STATE_DIR"/export/ 2>/dev/null || python -c "from mushegh.protocols.portable import last_drill; print(last_drill())"
    journalctl -u openmushegh-brain --since "30d" | grep -iE "export|drill|manifest"

**An export silently omits half the memory.** The manifest is the check — a store listed
under `absent` is honest, a store missing from `files` is a lie:

    python -c "import json;from mushegh.shared.paths import state_dir;m=json.loads((state_dir()/'export'/'MANIFEST.json').read_text());print(len(m['files']), m['absent'])"
    python -c "from mushegh.brain.inventory import undeclared; print(undeclared())"

**A note was written to the vault replica and lost at the next pull.** `replica_reason` is
the diagnosis, and the sync marker is the evidence:

    python -c "from mushegh.brain.tools.vault import replica_reason; from mushegh.config import settings; print(replica_reason(settings.vault_path))"
    journalctl -u openmushegh-brain --since "7d" | grep -iE "vault|replica|writable"
    ls -la "$VAULT_PATH"/.vps-sync.ps1 2>/dev/null

**A retention sweep removed something worth keeping.** The dry run is the diagnosis, and it
is the reason curation is the open question rather than a nice-to-have:

    python -c "from mushegh.brain.maintenance import sweep_retention; print(sweep_retention(dry_run=True))"
    python -c "from mushegh.brain.inventory import report; print(report())"
    journalctl -u openmushegh-brain --since "48h" | grep -i maintenance

**Two hosts' memories are merged and something is chosen rather than unioned.** The merge
direction is the whole argument: a fact only one host was told is not stale, it is the only
copy. Choosing between hosts silently deletes something the owner said:

    python scripts/merge_memory.py            # prints its own usage
    journalctl -u openmushegh-brain --since "7d" | grep -iE "merge|memory"

## Open questions

1. **What is continuity for, and for whom?** M07's question, and the one that decides whether
   the rest of this document is work or ceremony. Preserving the owner's own memory for the
   owner's own use needs a different answer from "so the framework is adoptable" (D-57,
   D-60), and the export is currently built for the second.
2. What is "curated"? D-21 keeps curated notes forever and expires the ephemeral after 30
   days, and curation is the word the policy hangs on. Without a definition, the keep-forever
   set is whatever happened to be written.
3. Does the export include the audit log, or only its summary? `portable.py` writes a summary
   today; D-25 wants a supersession to survive and be explainable, and a summary is not a
   survival.
