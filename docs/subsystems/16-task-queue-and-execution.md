# S16 — Task Queue & Execution

> **One line:** long work that must not block a voice turn, held in one SQLite file and
> executed by one bounded worker.
> **Status:** built, not well structured · **Registry:** S16 · 3/3 floor, 0/4 raise, 0/1 elite
> **Milestones:** M21 · **Decisions:** D-01, D-02, D-07, D-13, D-31

## Purpose

A fleet delegation that takes twenty minutes should not hold a voice turn open, and it should
not leave the owner wondering whether it is still running. This system runs that work in the
background, keeps a persisted record with the latest progress, answers "how's that going?"
at any time, and delivers a completion note when it finishes.

The shape is the point. The queue is a SQLite table and a worker coroutine. It is not Temporal,
and it is not a broker, because a durable workflow engine is a second thing to be down at 2 AM
and the checkpointing it buys does not pay for itself in a single-operator system (D-01). One
store, one process, one row per task, inspectable with `sqlite3` (D-02, D-54).

The safety line is that the worker **defers every outward action to approval** (16.F2). It may
research, draft, summarise and verify. It may not send, delete, push or run a shell
unattended. That list is not a heuristic in the prompt; it is the set of confirm-gated tools
the worker refuses to call.

If it is absent, a two-minute job either blocks the conversation or disappears silently, and
the owner learns to ask twice.

## Structure

| Path | Role |
|---|---|
| `src/mushegh/brain/tasks.py` | The queue. SQLite at `$MUSHEGH_TASKS_DB_PATH` (default `<repo>/mushegh_tasks.sqlite`), an in-memory mirror for instant reads, `run()` wrapping any coroutine factory with an `on_progress` callback, and `on_complete` set by the server |
| `src/mushegh/brain/worker.py` | `TaskWorker`: a bounded tool loop for research, drafting, summarising, light coding. A step budget **and** a wall-clock budget, declared before the run starts |
| `src/mushegh/brain/governor.py` | The second bound: a shared rolling ledger of calls, spend and runtime across every run |
| `src/mushegh/brain/backlog.py` | A daily routine that pulls overdue and undated-inbox tasks and attempts the safe work on each, commenting the result back. Opt-in, capped per run |
| `src/mushegh/brain/coordination.py` | One row per unit of delegated work — claimed before it is worked, only the holder writes the result |
| `src/mushegh/brain/approvals.py`, `src/mushegh/brain/audit.py` | Where a confirmation is required and where the worker's steps are recorded under an explicit non-owner actor |
| `src/mushegh/brain/scheduler.py`, `src/mushegh/brain/_scheduled_jobs.py` | What fires the backlog pass and the rest |
| `src/mushegh/brain/tools/tasks.py` | The handler belt for capture, status and completion |

Everything is in the **brain** process on the always-on host, which is what lets the queue
survive a restart. Progress is persisted as it streams, so "how's that going?" is a row read,
not a second round trip to whatever is doing the work.

Two things are worth stating because they are easy to get wrong. A per-run budget cannot stop
a scheduler firing well-behaved runs all day — that is what the governor's rolling ledger is
for, and the failure it prevents has already happened on this owner's infrastructure, where
roughly 2,500 messages and roughly 565M tokens went out one well-behaved iteration at a time.
And before this system, a delegation's record was deleted the moment the task succeeded, so
after ten real delegations nothing anywhere could say what had been handed over or whether an
answer came back.

## Goals

1. Long work runs in the background and the owner can ask its status at any time (16.F1).
2. The queue survives a brain restart, and restart and expiry semantics are explicit
   (16.F1).
3. The worker defers every outward-facing or destructive action to approval (16.F2, D-07).
4. An external queue pointer is validated at startup and a stale one fails loudly (16.F3).
5. Dependencies surface as "waiting on" rather than as two unrelated to-dos (16.R1, M21).
6. Priority reflects deadlines and objectives, not insertion order (16.R2, M21).
7. The whole system is one SQLite file and one worker, diagnosable in 90 seconds (D-01,
   D-02).

## Benchmarks

| Goal | Tier | Command or drill | Threshold | Last measurement |
|---|---|---|---|---|
| 1 | B1 | `uv run python bench/test_background_tasks.py`, `uv run python bench/test_task_todos.py` | 0 status queries that miss a live task; 0 tasks with no progress row | registry records 16.F1 done; run not reproduced here — not yet measured |
| 2 | B1 | `uv run python bench/test_task_restart_expiry.py` | 0 tasks lost across a restart; expired tasks are marked, never silently dropped | registry records 16.F1 done; run not reproduced here — not yet measured |
| 3 | B1 | `uv run python bench/test_safety_autonomy.py` | 0 unattended sends, deletes, pushes or shells; every confirm-gated tool deferred | registry records 16.F2 done; run not reproduced here — not yet measured |
| 4 | B1 | `uv run python bench/test_phase11_notion.py` | 38/38 including the 404-as-200 case, per the registry gate note | recorded in the registry as 38/38; run not reproduced here |
| 5 | B1 | new `bench/test_task_dependencies.py` (planned, 16.R1 / M21 — does not exist yet) | a task blocked by another reads "waiting on <task>" in every status surface; 0 blocked tasks shown as actionable | not yet measured |
| 6 | B1 | new `bench/test_task_dependencies.py` [ordering] (planned — does not exist yet) | 20 tasks with mixed deadlines order by deadline, not by insertion | not yet measured |
| 7 | B4 | `sqlite3 "$MUSHEGH_TASKS_DB_PATH" .tables` on the brain host; 0 non-loopback listeners | the queue is one file; no broker, no workflow engine, no second store | holds by construction |

A live end-to-end check exists and is the closest thing to a B2 here: `uv run python
bench/test_live_task_reminder_e2e.py`. `bench/test_work_on_task.py` covers the worker's own
tool loop and is where the 16.R3 milestone-narration case would extend.

## Failure modes

**A task raises.** Recorded as `failed` with the error; it never crashes the brain. The owner
sees a completion note that says it failed, or nothing if the callback never fired. Diagnose:
`sqlite3 "$MUSHEGH_TASKS_DB_PATH" "select id, state, last_progress, error from tasks order by
rowid desc limit 10;"` — that is the first command, and it needs no framework.

**The worker runs away.** Bounded twice, but the per-run bound is the wrong bound for a
scheduled caller. `src/mushegh/brain/governor.py` is what actually stops it. If a run is not appearing in the
ledger, the ledger is not being charged. Diagnose: the governor's rolling window, then
`journalctl -u openmushegh-brain -n 200 | grep -i worker`.

**The queue resets.** `MUSHEGH_TASKS_DB_PATH` points somewhere new, or the mirror and the file
disagree. The owner's symptom is a task he was told is running that no longer exists.

**A stale external pointer.** A Notion database id that 404s used to read as 200 with an empty
body, so the queue reported success against nothing. 16.F3 validates the pointer at startup
precisely so that is loud. Diagnose: the `bench/test_phase11_notion.py` case, then the id in the
config.

**Silent success.** The record of a delegation used to be dropped on completion, so the system
could not report what it had done. `src/mushegh/brain/coordination.py` is the fix; if the shared work record is
empty, the delegation never went through `src/mushegh/brain/coordination.py`.

## Open questions

1. 16.R1 and 16.R2 both need real deadlines on tasks (M21). Which is upstream — S33's capture,
   or the queue's own parsing?
2. Is the in-memory mirror in `src/mushegh/brain/tasks.py` still worth its consistency risk, or should status
   reads go to SQLite now that the row is the record anyway?
3. `src/mushegh/brain/backlog.py` comments worker output onto the owner's tasks unattended. That is a write to
   a system of record — does it need an approval, or is appending a comment inside the
   silent-ok class (D-07)?
