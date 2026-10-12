# Registry reconciliation — APPLIED 2026-10-03

This file used to be a work order against `docs/systems-plan.json`. It has been carried
out. It is now the record of what changed, and the short list of what did not.

**Authority for the change:** the owner interview of 2026-10-03, transcribed as
[DECISIONS.md](DECISIONS.md). **De-scoping is an owner's act** (D-47), which is exactly
why this needed a new state rather than a quiet edit.

---

## 1. The planner learned to say "no"

`scripts/systems_plan.py` accepted only `open`, `in-progress` and `done`. There was no way
to record "this will never be built" that kept the history — so 20 PostgreSQL migration
tasks sat in the plan beside a decision to abandon them, and the dashboard kept offering
one of them as the next thing to do.

Two states were added, and they mean different things:

| State | Means | Effect on counts |
|---|---|---|
| `cancelled` | Decided against. Out of scope. | Leaves every count, including the denominator |
| `deferred` | Still owed, not scheduled now | Keeps its denominator, stops appearing as "next open" |

A third change makes a cancellation honest: the **`owner-decision` evidence kind**, and a
validation rule that refuses any `cancelled` or `deferred` task without one. Otherwise
"cancelled" would be the cheapest way to make a number look better, which is the failure
mode this plan was built to prevent.

`scripts/unpark_check.py` was updated in step: a cancelled floor is no longer a permanent
blocker on unparking, because the gate asks whether the *intended* floor is green.

## 2. What was applied to the registry

| Change | Count | Systems |
|---|---:|---|
| Tasks `cancelled` | 29 | S15, S24, S30, S40, S46, S47, S49 |
| Tasks `deferred` | 6 | S26, S32, S34 |
| System statuses rewritten | 9 | S15, S24, S30, S32, S34, S40, S46, S47, S49 |
| Task titles rewritten | 6 | 01.E1, 10.R1, 17.R1, 34.R2, 35.R1, 44.R1 |

**Before:** 180 of 403 tasks done. **After:** 180 of **374 live** tasks done — 29 out of
scope, 6 still owed. Elite moved from "0 of 52" to "0 of 46" purely by removing work that
is no longer intended; nothing was completed by this change.

### Cancelled

| System | Tasks | Why |
|---|---|---|
| S15 | `15.R1` `15.R2` `15.R3` `15.E1` | Recommendations are removed (D-27). `15.E1` targeted a 50% acceptance rate for a system that must not exist |
| S24 | `24.R1` `24.R2` `24.R3` `24.E1` | **Decided AND executed 2026-10-04 (M04).** `graph.py` and `tools/graphmem.py` are gone, the `graph` tool group is unregistered, the L5b recall layer is removed, and recall p95 improved from 27.0/42.0/28.6 ms to 11.3/15.6/15.5 ms. `24.R2`'s belief revision folded into S30's supersession rule, which is now built (30.R10) |
| S30 | `30.F1` `30.R4` `30.R5` `30.R6` `30.R7` `30.R8` `30.R9` | The PostgreSQL migration (D-02). `30.R4`'s 607 unverified edges are resolved by deletion, not verification (D-26) |
| S40 | `40.R2` `40.R3` `40.E1` | Transaction ingest is a hard no (D-12). `40.R1`, a watched-symbol alert, survives |
| S46 | `46.R1` `46.R2` `46.R3` `46.E1` | No ML forecasting (D-28) |
| S47 | `47.R1` `47.R2` `47.R3` `47.E1` | Fully missing, and its replenishment pipeline was built and never used (D-42) |
| S49 | `49.F1` `49.F2` `49.F3` | Dropped, now re-signed by the owner (D-47, D-48). The decision record is the subsystem document |

### Deferred

| System | Tasks | Why |
|---|---|---|
| S26 | `26.R2` `26.R3` | Screen understanding and anomaly detection: speculative and surveillance-adjacent. `26.R1`, audio scene classification into the speaker gate, stays live |
| S32 | `32.R1` `32.R2` `32.R3` | Waiting on an unanswered question: is there ever a second brain host? |
| S34 | `34.R4` | FIT/Apple Health ingest: waiting on whether a wearable exists in the house |

### Retitled, not cancelled

| Task | Change |
|---|---|
| `35.R1` | Escalation is notify → SMS/push to a fixed list → third party. **No outbound voice calls** (D-11) |
| `34.R2` | Nudges are text-only, capped, charged against the interruption budget: zero audio (D-29) |
| `17.R1` | Brief is triggered by the first morning interaction, silent, spoken on request only (D-33) |
| `10.R1` | The 0.75 threshold moves up — a false "owner" executes or leaks, a false "not-owner" costs a PIN (D-15) |
| `44.R1` | Safety > Privacy > Honesty > Helpfulness, and the order needs an explicit test suite (D-10) |
| `01.E1` | Restated as compound intent handled without a clarifying round-trip |

## 2b. Tasks the docs audit added (2026-10-03)

A fact-checking pass over all 50 subsystem documents — cross-read against the charter, the
registry, the roadmap and the code — found that seven charter rules had **no task at
all**. A gap with no task has no owner and no gate, which is how a good intention becomes
a silent omission. They are now tracked work:

| Task | Rule | What the audit found |
|---|---|---|
| `28.R4` | D-13 | `lock` and `garage_door` are **confirm-gated** in `smarthome.py`, not refused. A typed confirm is not physical presence — a live blast-radius gap, and the most serious finding in the pass. Scoped to what D-13 actually names: alarm, cover, climate and water heater keep the confirm-gated middle tier, which the charter does not forbid |
| `37.R5` | D-24 | The never-store set existed only as prose. A grep for `D-24` / `NEVER_STORE` across `src/mushegh/` returns nothing |
| `41.R4` | D-34 | `mynews.py` is a live unprompted 08:00–10:00 feed, wired at `proactive.py:927`. No task tracked it. **Since fixed:** the task was added, 41.R4 removed the registration, and `bench/test_no_unprompted_feed.py` is green 10/10 (2026-10-04). The row is kept as written because this file is the dated record of what the audit found |
| `18.R4` | D-17 | `MUSHEGH_ELEVENLABS_API_KEY` is configured, so local TTS is not actually the default the decision requires |
| `18.R5` | D-19 | `MUSHEGH_PORCUPINE_ACCESS_KEY` is configured, so the wake word is a cloud call, not on-device spotting |
| `36.R4` | D-62 | The environment carries ~15 third-party credentials, not the four D-62 named. Every one needs a row mapping it to a decision |
| `45.R10` | D-25, D-43 | Two documents called the audit trail "tamper-evident". `audit.py` is append-only JSONL with fail-quiet writes and no hash chain — either it gets an integrity check or the word is struck everywhere |

Registry total is now **410 tasks**. D-62 was amended in the same pass to describe the
credential surface that exists rather than the one that was intended.

**M04 and M02 are both done.** The registry records intent, and on 2026-10-04 both became
deletion rather than intent:

- **M04 (2026-10-04):** the graph relation layer — `src/mushegh/brain/graph.py` and
  `src/mushegh/brain/tools/graphmem.py` are removed, along with the `graph` lazy tool group and
  the L5b recall layer. Recall p95 on the per-turn path improved from 27.0/42.0/28.6 ms to
  11.3/15.6/15.5 ms, and the advertised tool count fell to 151.
- **M02 (2026-10-04):** the staged migration — `postgres_client.py` and
  `postgres_vectors.py` are removed, along with the `postgres_dsn` setting, the `postgres`
  extra, `psycopg` from the lockfile, and the `MUSHEGH_POSTGRES_DSN` block. No migration was
  needed: the runtime never read the DSN. `store_migration.py` is removed too, after
  checking as this file asked — nothing outside the cancelled migration used its snapshot
  helper, and `mushegh.protocols.backup` provides the capability properly.
  `bench/test_s30_migration_removed.py` proves it with a real backup → verify → restore →
  drill round trip, 25/25.

**Kept on purpose in both cases:** the `!postgres` classification rule and
`mushegh_graph.sqlite` in the migration list. A host that ran the old code may still have those
files, and a store nobody classified is the failure that table exists to prevent.

**Removed 2026-10-04 (M04), for the record:** the graph relation layer
(`src/mushegh/brain/graph.py` and `src/mushegh/brain/tools/graphmem.py`, plus the `graph` lazy
tool group and the L5b recall layer). **`src/mushegh/brain/world_model.py` was deliberately
kept** — it is goals and events, not relations, and `note_event` is a TTL scratchpad that
webhooks depends on. Only its one graph-aware method went.

**[SYSTEMS-DETAILS.md](SYSTEMS-DETAILS.md) stays frozen.** The planner stores evidence
`source` values as line numbers into it, so rewriting it would silently invalidate every
evidence record in the registry.

**No task was marked done.** A cancellation is not progress; the done count did not move.

## 2c. Two charter rules were written but never built (found 2026-10-04)

Mapping the twelve coherence journeys against the code asked a question nobody had asked:
does the code do what this file says it does? In two places it does not, and both are the
failure this project exists to catch — **a decision recorded as a decision was read
downstream as a change made.**

| Rule | What the docs said | What the code does |
|---|---|---|
| **D-26** (S24) | "the relation layer is deleted, not paused" | `src/mushegh/brain/graph.py` is live: `add` :99, `remove` :113, `neighbors` :134, `related` :150 all work, and five modules import it — `memory.py:415`, `forget.py:132` and `:176`, `background_review.py:25`, `world_model.py:278`, `tools/graphmem.py:11`. The `graph` group is still advertised to the model. Deleting it is roadmap **M04**, and it has not been started |
| **D-25** (S30) | superseded memories are "tombstoned, never wiped" | `MemoryStore.remember()` at `memory.py:124` deduped on **identical normalised text only**. A *conflicting* correction was stored as a second fact and recall returned both. `grep -rn "tombstone" src/mushegh/` found only turn-cancellation code. **RESOLVED 2026-10-04 — see the update below** |

Both were written by this session's own charter pass, which is what makes them worth
writing down rather than quietly fixing. The S30 and S45 documents were already honest
about the tombstone gap — they say so in their benchmark rows — so the false claims lived
in the charter, in the registry status string and in the subsystem index, and those are
what changed.

**Update, 2026-10-04 — both halves are now built.** D-25 has a writer (`MemoryStore.remember()`
takes a `subject`; a differing fact supersedes; the loser is tombstoned with its text kept
and an audit line recording both texts and the reason; `_iter_notes()` skips superseded notes
so recall cannot return a corrected fact; and a **weaker source is refused rather than
stored**, because provenance cannot be traded for recency — 24/24 on
`bench/test_supersession.py`, task `30.R10`). D-26 has been carried out: `graph.py` and
`tools/graphmem.py` are gone, the `graph` lazy group is unregistered, the L5b layer is gone
from `fused_recall`, the background reviewer no longer writes triples, `forget` no longer
sweeps them, and `what_i_dont_know` no longer speaks from a store the owner had stopped
trusting. **Measured:** recall p95 on the per-turn path improved from 27.0/42.0/28.6 ms to
11.3/15.6/15.5 ms across three runs each, and the advertised tool count fell to 151.

## 4. Owner decisions still open

**Resolved 2026-10-03 by the hardware inventory:** *"is there a wearable in the house?"*
The answer is a **Garmin Instinct 3** exporting raw FIT. `34.R4` is un-deferred, S34's status
no longer claims a missing data source, and the export is D-57-shaped: no vendor cloud, no
proprietary API. One down, six added.

### Still open, and still cheap

Two questions that block *deletions* rather than work:

1. **Is there ever a second brain host?** (S32) — replication, promotion and split-brain
   prevention all wait on it.
2. **Who is on the emergency list, and what is each stop condition?** (S35) — the owner said
   they would encode it once, by hand. It has not been written down, and `35.R1` is blocked
   on it. **The hardware makes this urgent rather than optional**: two smoke/CO detectors
   and three water sensors arriving without stop conditions defined is a worse system than
   no detector at all.

### New, from the hardware

Four decisions the inventory forces. Each is recorded in
[HARDWARE.md §9](HARDWARE.md#9-where-this-hardware-contradicts-the-charter); three are
written into the charter as **proposed** and need the owner's signature.

3. **Which circuits may a Shelly plug switch?** (D-68) — appliance circuits only, never the
   main breaker and never anything on the UPS-backed core. The proposed line is drawn; the
   owner confirms which circuits are in scope.
4. **Does the smart lock stay read-only, and is the NFC tag the path back?** (D-65) — the
   plan assumes yes to both. `28.R5` tracks the read-only enforcement.
5. **One wake phrase on three always-listening satellites?** (D-67) — the code has seven
   phrases and the charter says one. Three satellites multiply false wakes threefold.
6. **Does S49 stay dropped now that a printer exists?** (D-70) — the revisit trigger's first
   half is met, its second half ("wanting a slicer it can call") is not. The recommendation
   is to keep it dropped, and under D-47 that needs the owner's sign-off rather than mine.

And one that is not a decision but a consequence worth stating plainly: **the configured
vision chain is cloud-only** (MiniMax, Gemini, Groq). D-66 forbids video frames from leaving
the house, so the `see()` path in `src/mushegh/brain/tools/camera.py` must not become the
detector's output channel. `26.R5` tracks it.

## 5. Follow-ups outside `docs/`

Three files outside this directory still describe the old world. Left untouched, listed
here so they are not lost:

- `CONFIGURATION.md` cites `docs/S30-MIGRATION.md` for "the remaining parity, backup and
  authorized-cutover gates". That file is now a cancellation record.
- `README.md` describes `docs/MASTER-PLAN.md` as "the long-range shape" and lists
  `NEXT-UPGRADE-DECISION.md`, which is gone.
- `TODO.md` should gain a dated entry recording that the plan lost 29 tasks to owner
  decisions, so the engineering log and the registry agree about what happened.
