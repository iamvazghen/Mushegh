# S34 — Health & Wellness Monitoring

> **One line:** The tools exist, a data source now exists — a Garmin Instinct 3 exporting raw
> FIT — and no export has been ingested yet, so nothing here has run against real data.
> **Status:** half-built — tools exist; a data source now exists (a Garmin Instinct 3 exporting raw FIT, 34.R4 un-deferred 2026-10-03) but no export has been ingested yet, and health-crisis journaling stays on the never-store list. · **Registry:** S34 · 3/3 floor, 0/4 raise, 0/1 elite
> **Milestones:** M07 · **Decisions:** D-21, D-24, D-29, D-42, D-57, D-63

## Purpose

Readings about the owner's own body: sleep, activity, screen time, and a weekly
wellness summary built from trends rather than single readings. Health *talk* stays
inside a stated boundary — observations and patterns, never a diagnosis
(`vitals.diagnostic_language`, 34.F3, done).

**The blocker that was blocking a deletion is answered.** One of the three owner decisions
under M07 was *"is there a wearable in the house at all?"* — and there is: a **Garmin
Instinct 3**, ingested as **raw FIT file exports over a USB sync**. No proprietary cloud
API, no vendor lock-in, which is exactly the shape D-57 asks of anything this system
touches. So `34.R4` — generic FIT and Apple Health XML ingest, previously deferred
precisely because no data source existed — is **un-deferred as of 2026-10-03**, and S34
is no longer half-built for a reason that has stopped being true. What it is half-built
for now is narrower and duller: **no export has been ingested yet**, and the Garmin
satisfies D-63's "is it local?" question only because a file on a USB cable is the whole
path.

The rest of the darkness is unchanged. The fitness tools were written against the Google
Fit API, which needs an enablement in a Cloud project that has never been done, and the
replacement reads a file the owner has not exported. `34.F1` is still recorded `done`
with the gate `test_new_integrations.py [fitness]`, and that gate has still never had a
real export in front of it.

Per D-42 the question was never only "how do we wire this" but "should this exist". Under
M07 every dark system gets one of three fates — wire it, complete it, or delete it — and
the deciding input was a question to the owner, not a milestone. The answer is "wire it",
so the deletion argument is closed, and the honest remaining risk has inverted: a system
with a real device behind it and no data in front of it keeps answering plausibly.

The system's ceiling is lower than the blueprint assumed, and that is the charter's
doing, not a shortfall. Unfiltered health-crisis journaling is on the never-store list
(D-24): it never enters a store, at any retention. So the most valuable thing a
wellness system could do — notice a bad week and remember it — is precisely the thing
it is forbidden to do. **And nothing in the code enforces that list yet.** A real export
is the first plausible route for a sensitive note to reach a store, which makes `37.R5`
— the task tracking the absence of enforcement — a precondition for ingesting the first
export rather than a nice-to-have.

If this is absent: nothing breaks. Afon stops claiming a capability it has never
exercised, and the north-star 07:30 brief loses the "sleep" line in the roadmap's
acceptance scenario, which is the one place this system's absence is felt.

## Structure

- `src/afon/brain/vitals.py` — the ingest and the boundary. `read_apple_health(path)`
  parses a real Apple Health export, `Reading` and `Vitals` hold the per-day
  aggregates, `save` / `kept` / `recent(kind, days)` / `spoken` are the storage and
  read-back surface, and `diagnostic_language(text)` is the guard that keeps health
  talk observational. `python -m afon.brain.vitals` runs its selfcheck.
- `src/afon/brain/proactive_signals.py` — `wellbeing_signals` is where nudges become
  counted signals. Break and posture nudges are text-only, capped per day, and charged
  against the D-29 interruption budget; `34.R2` is open, so the cap is declared in the
  charter and not yet in code.
- `src/afon/brain/coaching.py` — the standing focus fields and `coaching_signals`. Per
  D-27 this stays a tool and must not grow into a recommender.
- `src/afon/brain/daily_digest.py` — the 07:30 surface where a sleep figure would
  appear. `34.R1` (sleep feeding S17's adaptive timing) is open and its gate,
  `bench/test_digest_timing.py`, does not exist.

Ownership: the brain process, one JSON vitals store under `AFON_STATE_DIR`. No daemon,
no new security boundary, and by D-42's own test that is an argument against S34
existing as a separate system rather than for it.

**What lands, and where.** The Garmin export is a **raw file** in the vault; the derived
numbers — sleep totals, activity aggregates, trends — become **curated facts**. That is
D-21's split between what expires and what is kept, and it is the argument for a file on
a USB cable rather than a vendor feed: the file is the evidence, the curated facts are the
product, and the file's own retention is a question nobody has answered yet.

Open tasks: `34.R1` sleep tracking, `34.R2` nudges, `34.R3` weekly wellness summary,
`34.R4` generic FIT and Apple Health XML ingest (**un-deferred 2026-10-03**; its gate is
a planned `bench/test_health_ingest.py` that does not exist yet), `34.E1` a month of
nudges.

## Goals

1. Ingest a real wearable export into the same store, whatever the device
   (`34.R4`, un-deferred 2026-10-03) — and until one arrives, admit there is no data.
2. Health talk stays observational: patterns and readings, never a diagnosis (34.F3).
3. Break and posture nudges are text-only, capped per day, and charged against the
   interruption budget — **zero audio** (D-29, `34.R2` rewritten).
4. A weekly wellness summary reports trends, not single readings (`34.R3`).
5. Nothing on the D-24 never-store list is ever written, at any retention — including
   unfiltered health-crisis journaling, and enforced in code rather than by intent
   (`37.R5`).
6. The raw FIT export stays a raw file and the derived numbers become curated facts
   (D-21): the file is the evidence, the facts are what Afon is allowed to keep.

## Benchmarks

1. **B1** — `bench/test_new_integrations.py [fitness]`, `bench/test_phase12_utility.py`
   [34.F2]. Threshold: screen-time and activity signals are real and dated, never
   estimated. Registry records 34.F1/34.F2 `done` as of 2026-10-03, and the evidence
   kind is `recorded-note` — a note, not an import, and still not a verified run. The
   gate has never run against a real export. Last live measurement:
   `not yet measured`.
2. **B1** — `bench/test_companion_safety.py` [34.F3]. Threshold: a set of clinical
   prompts produces 0 diagnostic language and 0 treatment advice. Registry record
   2026-10-03. Last measurement: `not yet measured`.
3. **B1 planned** — `bench/test_health_ingest.py` (the `34.R4` gate, not yet written; the
   task was un-deferred 2026-10-03). Threshold: a FIT file and an Apple Health export
   ingest to the same schema with identical field names. Last measurement:
   `not yet measured` — **no export exists**, and the Garmin has not been synced.
4. **B4** — `bench/test_proactive_thresholds.py` [wellness kind] (the `34.R2` gate).
   Threshold: 0 wellness nudges are audio, ≤ the daily cap in total, and exactly 0
   inside a focus block. Last measurement: `not yet measured` — M23 owns the budget
   assertion and has not been run.
5. **B1 planned** — `bench/test_coaching.py` extended (the `34.R3` gate). Threshold: a
   weekly summary quotes ≥ 1 trend across ≥ 2 weeks and 0 single-day readings in
   isolation. Last measurement: `not yet measured`.
6. **B4** — `bench/test_new_integrations.py [fitness]` rerun against a *real* export
   rather than a fixture. Distinct from benchmark 1, which asks whether the signals are
   dated and real; this asks whether the ingest survives a file the vendor actually
   produced. Threshold: 0 fields silently dropped, 0 timestamps parsed as local time.
   Last measurement: `not yet measured`.
7. **B3** — `34.E1`: a month of nudges with ≥50% acceptance and zero the owner calls
   nagging. Note D-30's objection: acceptance rate is the wrong metric, because a
   tolerated nudge reads as accepted. Dismissal rate is the honest one. Last
   measurement: `not yet measured`.
8. **B4** — D-24, asserted in code. Threshold: 0 rows for any never-store class, checked
   against `src/afon/brain/inventory.py`'s declared classes at every retention sweep, plus
   0 unfiltered health-crisis rows in the vitals store. Last measurement:
   `not yet measured`; **nothing in the code enforces the list today**, and `37.R5` is the
   task that tracks that gap (M29 owns the sweep). This benchmark is a precondition for
   ingesting the first real export, not a follow-up to it.
9. **B4** — the D-21 split. Threshold: the raw FIT file is stored as a raw file and is
   not rewritten in place; derived figures enter the store as curated facts with a stated
   provenance. Last measurement: `not yet measured`.

## Failure modes

**The tool answers about a source that has not been synced.** This is the current state and
it is the most dangerous failure here, because the tool is real and the answer is
plausible. Having a Garmin in the house makes it *more* dangerous, not less: the wearable
question is answered, so the system looks ready, and the only thing still missing is a
file on a cable. Three commands:

    python -m afon.brain.vitals
    python -m afon.brain.inventory | grep -iE "vital|health|fit"
    journalctl -u openafon-brain -n 200 | grep -iE "vitals|health|fitness|fit"

**A nudging turn starts.** Only possible once a data source exists. The D-29 counter
is the check:

    journalctl -u openafon-brain --since "24h" | grep -icE "wellness|nudge|break"
    python -c "from afon.brain.coaching import coaching_signals; print(len(coaching_signals()))"

**Health talk drifts into advice.** `diagnostic_language` is the guard and
`bench/test_companion_safety.py` is the regression. A failure here is a D-10 Safety >
Helpfulness breach, not a wording nit.

**An export parses to nothing.** `read_apple_health` returning zero readings is
indistinguishable from a malformed file unless the count is checked, and the difference
is a week of wrong "no activity" claims.

## Open questions

1. **The wearable question is answered — so what is now open is the file.** There is a
   Garmin Instinct 3 and no export. Is the raw FIT file itself ephemeral under D-21
   (expiring in 30 days with the rest of the raw telemetry) or evidence that is kept?
   The curated derived facts are clearly the "kept forever" side, but the split has never
   been written down, and it is the question `34.R4`'s ingest has to answer.
2. Does the D-24 never-store list get enforced **before** the first real export is
   ingested? `37.R5` tracks the absence of enforcement and the Garmin makes the absence
   reachable, so the honest sequencing is enforcement first, ingest second — but nobody
   has said so in a place the code will read.
3. How does a wellness summary stay useful when the charter forbids remembering the bad
   weeks? D-24 removes the most valuable thing a wellness system could do, so the
   honest answer may be that this system reports numbers and nothing else, and should say
   so in what it says.
