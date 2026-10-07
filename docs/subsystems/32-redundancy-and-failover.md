# S32 — Redundancy & Failover

> **One line:** Model failover is real and tested; state replication between hosts does not exist, and whether it ever should is an open question for the owner rather than a task.
> **Status:** **partially missing at the architecture level** — model failover is real; there is one host. Replication, promotion and split-brain prevention are deferred pending an owner decision on whether there is ever a second brain host · **Registry:** S32 · 4/4 floor, 0/3 raise, 0/1 elite
> **Milestones:** none of M01–M40 carries `32.R1`–`32.R3`; they are deferred · **Decisions:** D-01, D-46

**The status string in the registry used to be a truncated sentence.** It ended at "there
is one" and was never finished by whoever wrote it. It was repaired on 2026-10-03, when
the charter applied: the three raise tasks are now `deferred` rather than sitting open and
looking like the next thing to do, and the status names the open decision. The honest
reading is still in the task list — all four floor tasks are `done`, all three raise tasks
are deferred and still owed, and the elite task is a drill that has not been run.

## Purpose

Failover here means two different things and they are not equally real.

**Real:** when a model provider rate-limits or drops, `llm.py` walks the configured
chain to the next provider so a single hiccup cannot mute Afon (32.F1, done). When the
brain is unreachable, the edge degrades into declared modes rather than failing
silently (32.F3, done). When a second instance tries to start, one of them refuses
(32.F2, done).

**Not real:** there is one brain host. State replication between hosts, automatic
promotion of the laptop, and split-brain prevention are `32.R1`–`32.R3`, all open, all
deferred, and — this is the point — deferred because **whether there is ever a second
brain host is an undecided architectural question belonging to the owner**, not an
engineering task. Under D-46, speculative work does not get the 8–10 hours a week that
dark and half-built systems need.

So this document records a decision that has not been made. It does not invent a
failover plan, and a plan invented here would be the exact failure D-46 describes:
building an artificial bridge so an undecided question looks like progress.

If the real half is absent: a provider outage takes the voice loop down. That has
happened, and the fallback is `src/afon/edge/degraded_answers.py` — time, reminders and
status, answered locally, with no model.

## Structure

- `src/afon/brain/llm.py` — 971 lines and the only module that knows which vendor is on
  the other end. `settings.llm_chain` is walked primary-first;
  `note_provider_failure` / `note_provider_success` / `provider_cooling` /
  `provider_health` track per-provider state, `_is_permanent_error` stops the walk on a
  failure that will not recover, and `ChainExhausted` is the honest terminal error
  (32.F1, `bench/test_brain_llm.py`, `bench/test_resilience.py`).
- `src/afon/edge/remote_brain.py` — `RemoteBrain`, the "one brain, many places it is
  reached from" path. When `AFON_BRAIN_MODE=remote` (or `auto` and the brain answers),
  the laptop edge stops running its own agent and becomes a thin client. This is the
  nearest thing to promotion that exists, and it is not promotion: it fails closed when
  the brain is down rather than taking over.
- `src/afon/edge/brain_client.py` — the client side of the tailnet WebSocket, one bearer
  token, no inbound ports (D-03).
- `src/afon/edge/degraded_answers.py` — the brain-down path. `answer()` handles time,
  reminders and status from local state with no LLM. `23.R4` measured real offline
  capability at 0.70/4 before this existed; it is better now and still not a brain.
- `src/afon/edge/offline_queue.py` — work queued while the brain was unreachable, drained
  on return. The only existing machinery that resembles reconciliation.
- `src/afon/shared/degraded.py` — the declared modes: `FULL`, `BRAIN_DOWN`, `EDGE_DOWN`.
- Single-instance enforcement (32.F2, `bench/test_singleton_and_macro_guard.py`) plus
  the `run/` pid and lock stores in `src/afon/brain/inventory.py`, and
  `src/afon/edge/_supervisor.py`, which keeps the edge alive and — importantly —
  captures the output that `pythonw.exe` would otherwise discard.
- `deploy/uptime_watch.py` — "the health of the *other* host is known to each host, not
  assumed" (32.F4, done, `bench/test_connectivity.py [32.F4]`). One host's health is
  knowable; two hosts' agreed state is a different problem and does not exist.

Ownership: the brain process plus the edge client. No second database, no consensus
protocol, no leader election.

## Goals

1. A provider outage does not mute Afon: the chain moves to the next configured
   provider without losing the turn.
2. A permanent provider failure stops the walk rather than retrying a doomed call.
3. Exactly one brain and one edge run; the second to start refuses.
4. The brain being down is a declared mode with a local answer, not a silence, and each
   host's view of the other's health is measured rather than assumed. **Undecided:**
   whether a second brain host exists at all — and everything above survives either
   answer.

## Benchmarks

1. **B1** — `bench/test_brain_llm.py` and `bench/test_resilience.py`. Threshold: with the
   primary provider forced to fail, the chain reaches a working provider and the turn
   completes; a permanent error short-circuits the walk. Registry records 32.F1 `done`
   as of 2026-10-03; no field measurement.
2. **B1** — `bench/test_singleton_and_macro_guard.py`. Threshold: a second brain or edge
   instance refuses to start, 0 times. Registry record 2026-10-03.
3. **B1** — `bench/test_degraded_modes.py` (32.F3, done). Threshold: in each declared
   mode, exactly the documented answers are available and nothing else claims to work.
   Note this file is also the planned gate for `32.R2` promotion and `32.R3` reconcile,
   which do not exist.
4. **B1** — `bench/test_connectivity.py [32.F4]`. Threshold: each host's view of the
   other's health is a measurement, not a cached assumption. Registry records 32.F4
   `done`, with the evidence kind `recorded-note`: a note, not a drill against the
   running system, which is why this is B1 and not B2. Last measurement:
   `not yet measured`.
5. **B2 live drill** — `32.E1`, and the one benchmark here worth keeping. Pull the VPS
   for an hour with the edge running. Pass condition: Afon stays usable (time,
   reminders and status answer; capture works), the offline queue drains on return, and
   nothing is duplicated or lost in the queue. Threshold: 0 lost actions, 0 duplicates,
   1 hour. Last measurement: `not yet measured` — the drill has not been run and is not
   in any milestone.
6. **No benchmark, by design** — `32.R1` replication, `32.R2` promotion, `32.R3`
   split-brain. Their gates (`bench/test_backup_restore.py [cross-host]`,
   `bench/test_degraded_modes.py [promotion]`, `[reconcile]`) are named and unwritten.
   A benchmark here would be a commitment to an architecture nobody has chosen.

## Failure modes

**Every provider is down.** `ChainExhausted` propagates and the turn fails honestly
rather than hanging. The edge answers time, reminders and status from
`degraded_answers.py`. Three commands:

    journalctl -u openafon-brain -n 200 | grep -iE "chain|provider|exhaust"
    python -c "from afon.brain.llm import provider_health; print(provider_health())"
    curl -s -o /dev/null -w '%{http_code}\n' "http://<brain-host>:<port>/healthz"

**The brain is unreachable and the edge has nothing cached.** The honest degradation is
thin: `degraded_answers.answer()` covers time, reminders and status, and a question
needing a model gets a refusal. `bench/test_degraded_modes.py` is the contract for
exactly where that line sits.

**Two brains.** Should be impossible (32.F2). If it happens, something bypassed the
check — look at the `run/` pid and lock stores:

    python -m afon.brain.inventory | grep -i run
    journalctl -u openafon-brain --since "1h" | grep -iE "singleton|lock|already running"

**The offline queue does not drain.** `offline_queue.py` drains on reconnect; a queue
that grows is an edge that reconnected without draining, and the symptom is a delayed
action rather than a lost one.

**The brain host is gone for good.** This is the case with no answer. There is no second
host, no promotion, no replica. `32.E1` bounds how long that is survivable (an hour, per
the drill); beyond an hour the answer is the open question below, not a plan.

## Open questions

1. **Is there ever a second brain host?** This is the question the whole raise tier is
   waiting on, and it is the owner's to answer. The three reasonable answers — a warm
   standby VPS, laptop promotion, or deliberately none — have wildly different costs and
   only one of them is four hours.
2. If the answer is yes: is the second host a *cold* backup (restore from the M32 drill)
   or a *warm* replica? A warm replica is `32.R1`, which is a distributed-systems
   problem this system has explicitly declined to have (D-01).
3. If the answer is no: does `32.E1` become the acceptance test for v1.0 (M40), or does
   an hour of downtime stay an accepted risk? Right now it is neither, which is why it
   has never been run.
