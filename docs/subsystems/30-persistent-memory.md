# S30 — Persistent Memory

> **One line:** Everything Afon knows, across six stores, answered by one facade — with the Obsidian vault as the human source of truth and SQLite as the runtime cache, and the PostgreSQL migration cancelled rather than finished.
> **Status:** built — **SQLite is the store by decision** (D-02); the PostgreSQL migration is cancelled and its scaffolding deleted. Vault markdown is the human source of truth (D-22) · **Registry:** S30 · 6/6 floor, 0/4 raise, 0/2 elite
> **Milestones:** M02, M04, M19, M29, M30, M32 · **Decisions:** D-02, D-21, D-22, D-25, D-26, D-54

**The registry now agrees with the charter.** `30.F1` and `30.R4`–`30.R9` were marked
`cancelled` on 2026-10-03, each carrying an `owner-decision` record naming D-02 or D-26;
that is why the raise count above reads 0 of 4 rather than 0 of 10. What the cancellation
does *not* do is delete the scaffolding — `postgres_client.py`, `postgres_vectors.py` and
`store_migration.py` are still in the tree, and M02 removes them. The registry records
intent; the filesystem is where code actually goes.

**`30.R10` landed 2026-10-04 and reads `in-progress`, not done.** The tombstone writer
exists: a correction on a declared `subject` supersedes the fact it corrects, and recall
stops returning the loser. **No caller passes a `subject`**, so nothing in the running
system supersedes anything yet — the mechanism is exercised only by its benchmark. Under
D-43 a task needs a green suite *and* seven days of real use, and this has had no week
yet.

## Purpose

Memory is what Afon knows on Monday that it did not know on Sunday, and what it can
still say in 2036 without this framework running: learned facts, a daily journal, the
vault, semantic similarity, open tasks, and — until M04 removes it — an entity graph.

Three rules are load-bearing. **The vault wins**: Obsidian markdown is authoritative,
SQLite is the runtime cache, and every mirror needs a reconciliation path that can lose
an argument to a file (D-22). **Retention is a policy, not a leak**: ephemeral
telemetry, raw chat turns and scratchpads expire after 30 days, structured facts and
curated notes are kept until manually deleted (D-21). **Superseded memories are
tombstoned, never wiped**: the more recent explicit correction beats a historical or
inferred record, and the loser gets an audit line (D-25, `30.R10`).

This is the most-changed system in the charter and most of the change is subtraction.
SQLite was correct from day one; the multi-adapter migration was cargo-culting (D-02).
`src/afon/brain/postgres_client.py`, `src/afon/brain/postgres_vectors.py` and
`src/afon/brain/store_migration.py` are scaffolding to be **deleted** under M02, not
finished. The cross-entity relation layer goes under D-26, which resolves `30.R4`'s 607
unverified inferred edges by removal rather than by verification nobody will do.

If this is absent: Afon forgets, silently and immediately, and every correction becomes
"it will be right next time" — which D-23 exists to forbid.

## Structure

`src/afon/brain/recall.py` is the facade (30.F2, done). `LAYERS` declares every store
memory is allowed to mean: L1 learned facts, L2 journal, L3 vault, L5 semantic
similarity over L1, L5b entity graph, L4 open tasks. `LAYER_TIMEOUT_S` gives each its
own budget — local layers 0.5–1.0 s, network layers 4.0 s — and an unavailable layer is
skipped, never raised. An answer from four stores beats an exception from five.

- `src/afon/brain/memory.py` — L1 learned notes and L2 journal, one file per fact, each
  carrying source, timestamp and confidence (30.F3, done);
  `src/afon/brain/semantic.py` — L5 similarity over L1, folding into L1 rather than
  returning separately.
- The supersession slot (30.R10, D-25) — `remember(text, tags, *, source, confidence,
  subject)`. **`subject` is the supersession key and the caller declares it**: nothing in
  the store can know that "the garage remote is in the kitchen drawer" and "the garage
  remote is under the stairs" are one slot, and inferring that from strings is how a store
  invents a contradiction that was never there — the same discipline as Jev's declared
  labels, enforced by the code rather than guessed by it. Two differing facts on one
  subject: the older **keeps its text** and gains `superseded_by`/`superseded_at` in its
  own front-matter, while one line in `learned/supersessions.jsonl` records both texts, the
  subject, the reason and both filenames. `_iter_notes()` skips superseded notes by
  default (`include_superseded=True` walks history, `_iter_all_notes()` is the unfiltered
  walk), so recall can no longer return a fact the owner corrected, and
  `supersessions()` reads the trail back oldest first.
- **Provenance outranks recency** (30.R10). A weaker source never overwrites a stronger
  one: an `inferred` guess arriving late is *refused and not stored*, and the call returns
  the existing note's path — two live facts on one subject is the contradiction this whole
  mechanism exists to prevent. A `tool` fact may supersede an `inferred` one. A naive
  newest-wins implementation gets this backwards, which is why the asymmetry is asserted
  rather than assumed. A fact written **without** a subject behaves exactly as before (a
  differing sentence is just a new fact), and the same fact twice on a subject is still a
  dedup, not a supersession — the second call returns the first note's path and writes no
  audit line.
- `src/afon/brain/graph.py` — L5b, deleted rather than maintained under D-26.
  `src/afon/brain/world_model.py` is named in the same deletion list, but it is not only
  a relation layer: it writes `world_model.json`, which `inventory.py` declares
  `KEEP_FOREVER` and describes as "the owner's goals, projects and deadlines".
- `src/afon/brain/tasks.py` — L4, the open commitments a question about a project means.
  `src/afon/brain/forget.py` — `everywhere(query)` sweeps every store then re-queries to
  confirm the thing is gone; one store's best match is the wrong unit of forgetting.
- `src/afon/brain/inventory.py` — the declared retention table. Each `Store` carries a
  name, what it holds, `retention_days`, who may read it, and where it lives. Declared
  today: 30 days for presence, per-turn traces, jobs and `errors.jsonl`; 90 days for the
  audit log and delegated work; `KEEP_FOREVER` for tasks, objectives, world_model and
  the memory directory; `WHILE_CURRENT` (retention 0, never swept) for state that is only
  true while it is current. `src/afon/brain/maintenance.py` — `sweep_retention
  (dry_run=False)` enforces that table, and `compact_learned`, `cap_learned` and
  `rotate_journals(keep_days=35)` bound growth.
- `src/afon/brain/dbconn.py` — the only DB door. `AFON_STATE_DIR` is the single origin
  (30.F1a–c, all done, and still the right idea even though the migration is dead).

Ownership: the brain process, one SQLite file in WAL mode, one markdown vault.
`docs/S30-MIGRATION.md` becomes a cancellation record, not a runbook.

## Goals

1. One question, one answer: every caller gets a ranked, deduplicated answer from every
   declared layer, with a stalled layer contributing nothing rather than holding the turn.
2. A recall at p95 ≤ 300 ms on the local layers, so auto-recall can run on every turn.
3. Contradiction handling: two stores disagreeing produces "I have two versions" (still
   open, `30.R2`, `30.R1`), and a superseded memory is tombstoned with an audit line
   rather than silently deleted (`30.R10`, built 2026-10-04, D-25).
4. Forgetting as declared policy — 30-day expiry for the ephemeral, keep-forever for
   curated — enforced by a job rather than by intention (`30.R3`, D-21).
5. The vault wins every disagreement, and every cache-mirroring path can lose to a file
   (D-22).
6. The whole store readable in 2036 with `sqlite3` and a text editor, no framework
   (D-54).

## Benchmarks

1. **B5** — recall latency over 30 queries restricted to the local layers (L1, L2, L4,
   L5b), p95 ≤ 300 ms, on the running host, method and date recorded. The threshold is
   already written into `recall.py`'s own docstring. Last measurement:
   `not yet measured`.
2. **B1** — `bench/test_layering.py` extended. Threshold: 0 modules outside the facade
   open a memory store. Registry records 30.F2 `done` as of 2026-10-03; not re-measured
   in the field.
3. **B1 planned** — `bench/test_unified_recall.py` (the `30.R1` gate, not yet written).
   Threshold: over 30 queries, an exact duplicate present in two stores returns once.
   Last measurement: `not yet measured`.
4. **B1** — `bench/test_supersession.py` (`30.R10`), 24/24 on 2026-10-04. Threshold: a
   conflicting correction on a declared `subject` leaves exactly **one** live fact; the
   loser keeps its text with `superseded_by`/`superseded_at` in its own front-matter, and
   `learned/supersessions.jsonl` gains one line naming both texts, the subject, the reason
   and both filenames; an `inferred` fact never supersedes an owner-stated one however late
   it arrives, while a `tool` fact may supersede an `inferred` one; a subjectless fact and
   an identical repeat are untouched. `not yet exercised` — the suite drives
   `remember(..., subject=)` directly and **no production caller passes a `subject`**, so
   the running system still supersedes nothing. J-07 in `bench/test_journeys.py` asserts
   the same behaviour: 63 passed, 8 blocked, 0 failed, 2026-10-04.
5. **B2 drill** — M29. A live rotation: ephemeral telemetry, raw turns and scratchpads
   gone; curated notes and `KEEP_FOREVER` stores untouched; nothing on the D-24
   never-store list ever written. Threshold: 0 curated rows removed, 0 rows under 30 days
   removed. Last measurement: `not yet measured`. The dry run is the drill's first line.
6. **B1** — `bench/test_memory_single_origin.py` (30.F1a–c): 46/46 across ten plants, no
   store reverting to the repo copy. Registry record 2026-10-03. Retained even though the
   migration it prepared for is cancelled: the single origin is still the rule.
   `bench/test_layering.py` extended, also recorded `done` 2026-10-03, asserts 0 modules
   outside the facade open a memory store.
7. **B2 drill** — M32: restore a scratch copy and confirm both the vault and the database
   come back legible to `sqlite3` (D-54). Last measurement: `not yet measured`.
8. **B5** — M04 acceptance: recall p95 after the relation layer is deleted holds or
   improves against benchmark 1. Last measurement: `not yet measured`, and unobtainable
   until benchmark 1 is taken.

## Failure modes

**Recall returns nothing, or something stale.** The facade swallows a failing layer by
design, so a dead store is silent. Three commands:

    python -m afon.brain.recall
    journalctl -u openafon-brain -n 200 | grep -iE "recall|embed|jina"
    python -m afon.brain.inventory | head -40

**Two layers disagree and Afon picks one.** Read the vault file first — it wins (D-22) —
then the audit log for what was written when.

**A retention sweep removed the wrong thing.** The dry run is the diagnosis:

    python -c "from afon.brain.maintenance import sweep_retention; print(sweep_retention(dry_run=True))"
    python -c "from afon.brain.inventory import undeclared; print(undeclared())"
    journalctl -u openafon-brain --since "48h" | grep -i maintenance

`WHILE_CURRENT` stores exist because an earlier dry run proposed deleting pending
approvals and live pid files. A store not in `inventory.py` is not swept at all. Memory
growing without bound means `compact_learned` and `cap_learned` are not running; check
with `run_maintenance()`. A Postgres import reappearing is cancelled work (D-02):
`grep -r "postgres" src/afon/` should return nothing after M02, and that is M02's
acceptance condition.

## Open questions

1. Does the `LAYERS` table keep an `L5b` entry after the relation layer is deleted?
   `recall.py` is code and M04 is a milestone; the facade either drops the layer or keeps
   a name that resolves to nothing.
2. Is `world_model.py` part of the relation layer or not? The reconciliation lists it
   for deletion under D-26, and it is the only writer for a `KEEP_FOREVER` store of
   goals and deadlines — and `src/afon/brain/goal_deviation.py` reads its goals from
   `world_model.WORLD`. Deleting it as written destroys data D-22 wants kept and breaks
   a live consumer nothing has reassigned.
3. Who declares the subject, and what is its vocabulary? *Where* a tombstone lives is
   settled: `superseded_by`/`superseded_at` in the superseded note's own front-matter, with
   the trail in `learned/supersessions.jsonl` — two plain files under the memory dir, so a
   supersession still reads in 2036 with a text editor and needs no SQLite table (D-54).
   What is open is the caller: **nothing passes a `subject` yet**, so the rule is built
   and unused, and a free-text subject invents contradictions while an enumerated one is a
   schema the owner has to maintain. The first caller that names a slot decides which it
   is.
