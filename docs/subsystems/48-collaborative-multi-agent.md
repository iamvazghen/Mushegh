# S48 — Collaborative Multi-Agent Coordination

> **One line:** One-way delegation to an external router, with a shared work record so a
> delegation leaves evidence — not a coordination layer, and not going to become one.
> **Status:** built, thin — one-way delegation to an external router; no coordination layer · **Registry:** S48 · 3/3 floor, 0/3 raise, 0/1 elite
> **Milestones:** none of M01–M40 carries `48.R1`–`48.E1`; no milestone is assigned to this
> system · **Decisions:** D-05, D-42, D-01, D-46

**A contradiction worth naming up front.** The index in `docs/subsystems/README.md` records
S48's charter effect as `deferred`, and `docs/REGISTRY-RECONCILIATION.md` lists the deferred
tasks as S26, S32 and S34 only. In `docs/systems-plan.json` as it stands on 2026-10-03, all
four of `48.R1`, `48.R2`, `48.R3` and `48.E1` read **`open`**, with empty `evidence` arrays
and no `owner-decision` record. They are not deferred; they are simply not scheduled, and
nothing in the plan says why. This document describes the registry as it is.

## Purpose

The blueprint specified a Redis-backed blackboard where several agents negotiate over shared
work: optimistic locking, peer hand-off, capability assignment. What exists instead is
`src/afon/brain/coordination.py` — a table of work units that a single owner claims, and
`src/afon/brain/delegation.py` — which posts a brief to an **external** router and checks what
comes back.

That is the whole system, and the gap is deliberate rather than unfinished. The external
fleet is a **tool, never the assistant** (D-05): sandboxed, diff-verified, never handed an
unconstrained shell. A coordination layer between agents would need an independent daemon or
a distinct security boundary to justify existing at all (D-42), and coordination without need
is a deadlock source with a support bill — exactly the class of complexity the 2:00 AM rule
rejects (D-01). The blueprint's row in `docs/ARCHITECTURE.md` reads: Redis blackboard
multi-agent coordination → `coordination.py`, one-way, because coordination without need is
a deadlock source.

What breaks if it is absent: delegation leaves no trace. That was the real defect — the
background path wrapped a delegation in a task-queue row that is deleted the moment the work
finishes, so a successful delegation left nothing anywhere saying what was handed over, to
whom, or whether an answer came back.

## Structure

- `src/afon/brain/coordination.py` — the shared work record (48.F1–F3). `post` writes units
  with an id, a brief, a sequence number and a deadline; `claim` takes the next open unit
  through a conditional `UPDATE ... WHERE state='open'` and returns `None` when it lost the
  race; `finish` and `fail` write the result slot only for the holder. The store is
  `store_path("work")`, reached through `dbconn.py`, and **SQLite's own write lock is the
  mutex** — no advisory locking, no lease renewal. A unit with no deadline is never late,
  which is why the delegation layer always sets one.
- `merge(job)` — groups by brief, in posting order, and where two units with the same brief
  come back with different answers, both are kept and the brief is listed as a conflict.
  Nothing is averaged, nothing is picked: averaging two answers produces a third answer
  nobody gave. `Merged.spoken()` is the one owner-facing line.
- `src/afon/brain/delegation.py` — 39.F2/F3. Opens a unit on that record with a deadline,
  closes it with the answer **and a verdict on that answer**. An open unit past its deadline is
  the fire-and-forget detector: a runner went away without writing back.
- `src/afon/brain/fleet.py` — the OpenClaw gateway transport. One tool among many
  (`delegate_to_fleet`), not an identity.
- `src/afon/brain/worker.py` — `TaskWorker`, Afon doing bounded work itself. It is the
  *other* kind of multi-agent: local, budgeted twice, and audited with an explicit non-owner
  actor. It is bounded by the shared ledger in `src/afon/brain/governor.py`.

Ownership: the brain process, one SQLite file. There is no second store, no lock server, no
message bus, and no agent-to-agent channel.

## Goals

1. Every delegated unit has an id, an owner, a state and a result slot, and only the holder
   writes the result (48.F1).
2. Two workers racing for one unit produce one winner (48.F2).
3. Merging is deterministic, and a disagreement between workers is reported as a
   disagreement (48.F3).
4. A delegation is tracked to a deadline, so a runner that dies is detectable rather than
   invisible (S39's fire-and-forget detector).
5. *Not a goal:* capability-based assignment, an aggregated owner-facing status, and
   cross-worker failure isolation (`48.R1`–`48.R3`). They are open, unscheduled, and no
   milestone carries them. A peer-negotiation layer would need the justification D-42
   refuses to grant.

## Benchmarks

1. **B1 (48.F1)** — `bench/test_coordination.py [record]`. Threshold: every unit carries an
   id, owner, state and result slot, and a non-holder cannot write the slot. Registry records
   48.F1 `done` as of 2026-10-03. Last field measurement: `not yet measured`.
2. **B1 (48.F2)** — `bench/test_coordination.py [no double claim]`. Threshold: two real
   threads racing for one unit, one winner, asserted by the test rather than by reading the
   SQL. Registry records 48.F2 `done`.
3. **B1 (48.F3)** — `bench/test_coordination.py [merge]`. Threshold: several answers become
   one deterministic result, and two workers who disagree are reported as disagreeing — 0
   averages, 0 silent picks. Registry records 48.F3 `done`.
4. **B1 planned (`48.R1`)** — `bench/test_coordination.py [assignment]`. Threshold: a unit is
   routed by declared capability rather than by a fixed worker name. Last measurement:
   `not yet measured` — the case is named in the plan and the suite does not assert it.
5. **B1 planned (`48.R2`)** — the same suite's `[status]` case: one owner-facing line for a
   job in flight. Last measurement: `not yet measured`. `Merged.spoken()` is the nearest
   thing that exists, and it is written but unwired.
6. **B1 planned (`48.R3`)** — the `[isolation]` case: one worker's failure leaves the rest of
   the job reportable. Last measurement: `not yet measured`; `fail()` records a failed unit
   but nothing yet retries or re-routes around it.
7. **B2 (`48.E1`)** — one genuinely multi-worker job (research, then draft, then review)
   completed with a single owner-facing report. Threshold: one report, no duplicated work, no
   unit left open. Last measurement: `not yet measured` — the drill has not been run and no
   milestone asks for it.

## Failure modes

**A unit is stuck `held` — a runner died.** This is the fire-and-forget detector working:

    sqlite3 "$AFON_STATE_DIR"/afon_work.sqlite "select id,job,owner,state,claimed_at,deadline_at from units where state='held' order by claimed_at;"
    python -c "from afon.brain.coordination import unfinished; print([(u.id,u.owner) for u in unfinished()])"
    journalctl -u openafon-brain --since "24h" | grep -iE "delegat|unit|fleet"

**A disagreement was averaged away.** If two answers became one, `merge` was bypassed — a
caller string-concatenating its own results:

    python -c "from afon.brain.coordination import merge; m=merge('j'); print(m.conflicts, m.agreed, m.missing)"
    sqlite3 "$AFON_STATE_DIR"/afon_work.sqlite "select job,count(*) from units group by job;"

**The fleet's answer was passed on unchecked.** The anti-fabrication verdict is the marker;
`rejected` means the answer was an admission of inability or an assertion Afon cannot stand
behind:

    sqlite3 "$AFON_STATE_DIR"/afon_work.sqlite "select verdict,count(*) from units where state='done' group by verdict;"
    journalctl -u openafon-brain --since "7d" | grep -iE "delegat|rejected|verdict"

**The thin layer starts growing a coordination protocol.** The tell is a second store, a
lock server, or a message passing between workers rather than to the owner:

    ls src/afon/brain/ | grep -iE "blackboard|consensus|leader|raft"
    python scripts/systems_plan.py check
    grep -rn "peer\|negotiat" src/afon/brain/ | head

**A job needed a peer and Afon delegated to one router anyway.** Honest failure rather than
a bug: with one external router, "ask another agent" is a second opinion at best. The
diagnosis is a job with a long `held` tail and no capability routing.

## Open questions

1. Should `48.R1`–`48.R3` be moved to `deferred` in the registry, the way S32's raise tasks
   are? They read `open` with no evidence, which puts them in the "next thing to do" queue for
   a system whose remaining scope the charter has effectively declined. A `deferred` state
   with an `owner-decision` record is the honest form.
2. Does anything read `Merged.spoken()`? The owner-facing status line (`48.R2`) may already
   be written and unwired, which would make it cheap to close — or a dead surface to delete.
3. If the external fleet is ever given a second agent that can address the first, does that
   change the D-42 answer? Today delegation is one-way by construction, which is what keeps
   it inside the tool boundary.
