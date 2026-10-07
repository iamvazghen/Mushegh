# S29 — Automation & Workflow

> **One line:** Everything Afon runs on its own — reminders, macros, saved sequences, scheduled briefs, background loops — listed in one place, dry-runnable before it is enabled, and single-use where it confirms.
> **Status:** built, not well structured · **Registry:** S29 · 4/4 floor, 0/3 raise, 0/1 elite
> **Milestones:** M28 · **Decisions:** D-01, D-09

## Purpose

An automation is anything Afon does without being asked in that turn: a reminder that
fires, a macro that runs a saved sequence, a scheduled brief, a background loop, a
weekly review. This system's job is that the owner can see all of them at once, with
the last run, the next run and the outcome, and can find out what one would do before
switching it on.

It refuses a workflow server. The blueprint proposed Temporal with durable workers and
checkpoints; what exists is `automations.py` plus `scheduler.py` plus `worker.py` on
SQLite and the existing worker, which is the substitution the blueprint-replacement
table in `docs/ARCHITECTURE.md` records. Under D-01, a system that cannot be diagnosed
from a shell in 90 seconds is not worth a server.

If this is absent: the owner's only way to find out what Afon did on its own is to read
a log, and the only way to stop it is to find the right file. That is the failure mode
in D-50's bad Afon — half-baked background actions that force a terminal.

## Structure

- `src/afon/brain/automations.py` — the unified list (29.F4, done). Three unrelated
  kinds of automation that each knew only about themselves are now one table with
  `automations()`, `spoken(rows)`, and `NEVER`/`ON_REQUEST`/`UNKNOWN` for the states
  that must not be guessed at.
- `src/afon/brain/scheduler.py` — a process-wide APScheduler `AsyncIOScheduler`
  persisted to SQLite, so reminders survive a restart. Job targets: `_fire_briefing`,
  `_fire_backlog`, `_fire_objectives`, `_fire_pattern_scan`, `_fire_weekly_review`,
  `_fire_backup`, `_fire_restore_drill`, `_fire_portable_drill`. `cancel_everywhere`
  and `_cancel_on_ticker` are the stop switch.
- `src/afon/brain/worker.py` — `TaskWorker`, the bounded autonomous loop. It refuses to
  send email, publish, spend or delete while running unattended and notes the step
  instead of taking it.
- `src/afon/brain/tools/macros.py` — if/then macros. The parsed comparison operator is
  applied, so `== 0` and `!= 0` no longer mean the same thing (29.F1, `done` in the
  registry, `bench/test_if_then_operator.py`). The registry's only evidence for it is
  `unverified-import` — an imported claim, not a verified run — so there is no dated run
  to record.
- `src/afon/brain/tools/skills.py` — saved sequences. `run_macro` and `invoke_skill` are
  in `CONFIRM_TIER` and are gated dynamically: a macro containing a gated tool reads
  itself back first, a read-only macro does not interrogate the owner
  (`_sequence_needs_confirm` in `src/afon/brain/proactive.py`).
- `src/afon/brain/approvals.py` — `ApprovalQueue`. A deferred outward step becomes an
  approvable action rather than a silent non-action (29.F3, done).
- `src/afon/brain/_scheduled_jobs.py` — module-level job targets so APScheduler can
  serialise them.

Ownership: the brain process, one SQLite file. No broker, no worker fleet, no second
database. Open tasks: `29.R1` dry-run, `29.R2` declared failure policy, `29.R3` voice
authoring with read-back, `29.E1` ten automations for a month.

## Goals

1. Every automation is listable with its last run, next run and outcome — including the
   ones that have never run, which must read "never", not blank.
2. "What would this do" is answerable before an automation is enabled (29.R1).
3. A failure inside an automation is compensated: the failure policy — retry, skip or
   alert — is declared, and a partial run is not left half-applied (29.R2).
4. One confirmation per sensitive mutation, and an approval never carries to the next
   action (D-09, M28).
5. An automation authored by voice is read back verbatim before it is saved (29.R3).
6. No runaway chain: a macro cannot trigger itself, and a second brain or edge cannot
   start beside the first.

## Benchmarks

1. **B1** — `bench/test_skill_runtime.py` extended with the listing assertion.
   Threshold: 100% of registered automations carry a last run, a next run and an
   outcome; 0 automations render an unknown state as a blank. Registry records 29.F4
   `done` as of 2026-10-03; no field measurement.
2. **B1 planned** — `bench/test_automation_dryrun.py` (not yet written; named as the
   29.R1 gate). Threshold: a dry run of every registered automation names >= 1 action
   and executes 0 tools. Last measurement: `not yet measured`.
3. **B1** — `bench/test_if_then_operator.py` and
   `bench/test_singleton_and_macro_guard.py`. Threshold: `== 0` and `!= 0` produce
   opposite branches across the fixture set, and 0 self-triggering macros are admitted.
   Registry records 29.F1/29.F2 `done` as of 2026-10-03; not re-measured in the field.
4. **B4** — one approval, one action. `bench/test_approvals.py`, then the M28 gate
   `bench/test_security_hardening.py [elevation scope]` (planned).
   Threshold: 0 cases where a single approval authorises a second mutation. Last
   measurement: `not yet measured`.
5. **B1 planned** — `bench/test_automation_authoring.py` (not yet written; the 29.R3
   gate). Threshold: 0 voice-authored automations saved without a verbatim read-back.
   Last measurement: `not yet measured`.
6. **B3** — 29.E1. Ten owner-authored automations running for one month with 0 misfires
   and a monthly review actually read. Last measurement: `not yet measured`; D-43's
   seven-day bar has not been attempted for this system.

## Failure modes

**An automation fires at the wrong time or not at all.** The scheduler is persisted, so
the usual cause is a job whose target raised. List what Afon thinks it is running:

    python -c "from afon.brain.automations import automations, spoken; print(spoken(automations()))"
    journalctl -u openafon-brain --since "24h" | grep -iE "scheduler|apscheduler|job"
    python -m afon.brain.automations

**A macro does something twice.** The macro guard covers self-triggering, and
`run_macro` is confirm-gated when its steps contain a gated tool. A repeat that survives
both is a chain the guard does not model — read the audit log for the two calls, and
treat it as a D-09 defect rather than a tuning problem.

**An outward action silently did not happen.** `TaskWorker` refuses email, publish,
spend and delete while unattended and queues the step in `approvals.py`. The owner sees
nothing happen and no error. Check the queue:

    python -c "from afon.brain.approvals import ApprovalQueue; print(ApprovalQueue().pending())"
    grep -c . audit_log/*.jsonl | tail -1

**A scheduled job silently duplicated a manual action.** `_cancel_on_ticker` is the
guard. If both paths ran, the failure is that the manual invocation did not cancel the
scheduled one — the audit log shows two calls with the same arguments minutes apart.

**Everything is listed and nothing is visible.** The list is a spoken and printed
surface only. There is no notification that an automation fired, deliberately: D-29 caps
audio at three interruptions a day, and an automation firing is not a reason to spend
one.

## Open questions

1. Does compensating rollback mean a compensating *undo*? A failed multi-step macro can
   either roll back the steps it already took or leave them and report which ones
   landed. The second is far simpler and arguably more honest; nothing has been decided.
2. How many automations is too many? D-06 culls tools unused for 60 days. The same rule
   for automations would delete deliberately seasonal ones, so either the rule or the
   expectation of a growing list is wrong.
3. Should voice authoring be allowed at all? `29.R3` is the only route by which a
   non-trivial automation can be created, and it is also the only route by which a
   misheard sentence becomes a standing instruction. A read-back is the mitigation; the
   question is whether a read-back of a nine-step macro is something a person can
   actually check.
