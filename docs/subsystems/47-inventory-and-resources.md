# S47 — Inventory & Resource Management

> **One line:** a decision record for work that should not happen — a stock table was built,
> the replenishment pipeline on top of it was never used, and the whole thing is cancelled.
> **Status:** **removed by decision 2026-10-03** — fully missing, and the replenishment pipeline built inside it was never used (D-42) · **Registry:** S47 · 3/3 floor, 0/0 raise, 0/0 elite (all four non-floor tasks `cancelled`)
> **Milestones:** M06 · **Decisions:** D-42, D-46, D-47

> This document exists so the system is not rebuilt by accident from a passing test suite. It
> is not a roadmap.

**The registry and the charter agree.** `47.R1`, `47.R2`, `47.R3` and `47.E1` were marked
`cancelled` on 2026-10-03, each carrying an `owner-decision` record. (The index in
`docs/subsystems/README.md` cites "Q25" for this system; no `Q-nn` series exists anywhere in
the charter, so the citation resolves to nothing and is left uncopied here.)

## Purpose

S47 was going to know what the house runs out of, predict when, and remind the owner to buy
it. A stock table with add, consume and query was built first, seeded with the one category
Afon can fill in without asking anybody — the owner's own disk and backups — and everything
above that table was cancelled.

**Cancelling cost little because nothing above the table was ever used.** Unlike S46, where a
live handler still called the module, S47's remainder is not wired to anything: no reorder
path ran, no category was added, no location was tracked, and the replenishment pipeline the
floor tasks anticipated was never called. D-42 is why this reads as a decision rather than a
failure — a new system needs an independent daemon or a distinct security boundary, and an
inventory table inside the brain process is neither. What breaks if it stays removed: nothing
the owner has ever missed.

**The table itself is not inert, and this document should not pretend otherwise.**
`run_maintenance()` calls `seed_self()` in the daily hygiene job, so disk and archive
readings are taken whether or not anyone looks at them. The *seeding* is live; the
*capability* is unused. M06's deletion has a caller to reconcile.

## Structure

| Path | What it is | Disposition |
|---|---|---|
| `src/afon/brain/stock.py` | 47.F1–F3: one `items` table in the state store, seeded by `seed_self()` from disk and archive sizes the owner can read today. Two refusals are the interesting half: it never invents stock, and it refuses a depletion estimate it cannot support (a rate needs two consumption events far enough apart) | delete under M06, or keep as a bare table. `src/afon/brain/maintenance.py` calls `seed_self()` from `run_maintenance()`, so the deletion has a caller to reconcile |
| `src/afon/brain/tools/stock.py` | two handlers, `check_stock` and one for recording a change. Deliberately **not** confirm-gated, for the same reason task capture is not — an inventory only works if recording costs less than remembering | delete with the module, or keep ungated |
| `bench/test_inventory.py` | the gate for 47.F1–F3; exists and passes | delete with the module. A passing test for a removed system is the exact trap S15 and S46 both describe |
| `src/afon/brain/inventory.py` | **Not this system.** S37's generated declaration of every store under the state root, with retention and who may read it | keep, and do not confuse the two — the names collide and the deletion pass will hit the wrong file |

## Goals — anti-goals

1. No reorder reminder, no depletion estimate spoken aloud, and nothing that interrupts on a
   supply level (D-07, D-29).
2. No location tracking, no second or third category, and no growth of the table by
   convenience.
3. A removed system stays removed: the four cancelled tasks are not restored without an
   owner's decision (D-47).
4. If anything here is ever rebuilt, it comes back as a handler in an existing domain, not
   as a fifty-second system (D-42).

## Benchmarks

These are deletion gates. Each one **fails** if the system reappears or lingers.

| Anti-goal | Tier | Command or drill | Threshold | Last measurement |
|---|---|---|---|---|
| 1 | B1 | `python scripts/systems_plan.py check` | 4 tasks read `cancelled`, 0 read `open`, and every cancellation carries an `owner-decision` record | last run 2026-10-03 as part of the reconciliation; re-run by M06, not by this document |
| 2 | B4 | `ls src/afon/brain/stock.py src/afon/brain/tools/stock.py` | both absent | **fails today** — both are present. This is the work M06 names |
| 3 | B1 | `grep -rn "stock" src/afon/brain/tools/__init__.py` | 0 registered handlers | not yet measured for M06; the handlers are registered today |
| 4 | B3 | the honest evidence of non-use: the replenishment half of the system — 90 days with 0 reorder reminders raised, 0 categories added beyond the seeded one, 0 location queries answered | 0, 0, 0 — a capability nobody used | **not yet measured** as a count; the decision rests on the owner's account that the pipeline was built and never used, and no production figure is quoted in this repository |

## Failure modes

**Rebuilt as "a small useful thing".** The likely path is a voice request to remind the owner
about a consumable, which sounds like two lines of glue on a table that already exists:

    ls -la src/afon/brain/stock.py src/afon/brain/tools/stock.py
    grep -rn "stock" src/afon/brain/tools/__init__.py
    python -c "import json;d=json.load(open('docs/systems-plan.json',encoding='utf-8'));print([t['state'] for s in d['systems'] if s['id']=='S47' for t in s['tasks']])"

**The wrong file gets deleted.** `src/afon/brain/inventory.py` is S37's store declaration and
lives a keystroke away from this system's name. Deleting it takes the retention table, the
sweep and the undeclared-store gate with it:

    python -c "from afon.brain.inventory import undeclared; print(undeclared())"
    ls src/afon/brain/inventory.py src/afon/brain/stock.py

**A green test implies a live capability.** `47.F1`–`47.F3` are recorded `done` and
`bench/test_inventory.py` passes, so the dashboard shows three green rows and no removal.
The same test asserts `seed_self()` runs in the daily hygiene job — so "green" also means
the daily job still takes a reading nobody asked for:

    uv run python bench/test_inventory.py
    python -c "import json;d=json.load(open('docs/systems-plan.json',encoding='utf-8'));print([s['status'] for s in d['systems'] if s['id']=='S47'])"
    journalctl -u openafon-brain --since "7d" | grep -i hygiene

**It creeps in through a neighbouring domain.** Adding a household-goods category because
the owner mentioned it once is `47.R3`, cancelled — and a category nobody uses is the shape
D-46 calls dark work: code that controls nothing, written and tested, waiting to be
justified by the next request.

## Open questions

1. Delete the module and its handler, or keep the table as an unprompted read-only query?
   M06 names S47 but not which half goes. The ungated `check_stock` handler is the only part
   with a user-visible shape, and `run_maintenance()`'s daily `seed_self()` call is the part
   still running.
2. If the table is kept, does it need a retention declaration in `src/afon/brain/inventory.py`
   to stay out of the undeclared-store gate?
3. Does cancelling `47.R1`'s "reorder reminder into S16" close that door on S16 too, or must a
   genuinely needed reorder be re-argued from scratch later?
