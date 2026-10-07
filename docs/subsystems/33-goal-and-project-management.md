# S33 — Goal & Project Management

> **One line:** A spoken sentence becomes an accurately parsed task with its real deadline in the daily note — and a stalled objective raises one counted signal, not a reminder stream.
> **Status:** built, not well structured · **Registry:** S33 · 3/3 floor, 0/3 raise, 0/1 elite
> **Milestones:** M19, M21, M25 · **Decisions:** D-29, D-45

## Purpose

This system carries what the owner is actually trying to get done: multi-day
objectives with milestones and target dates, so "stalled" is computable rather than
felt, and the open tasks that serve them, so a question about a project reaches the
commitments as well as the facts (layer L4 in
[30-persistent-memory.md](30-persistent-memory.md)).

It holds the north-star loop. Speak at the desk during a deep-work block; the phrase is
parsed into a task with a real deadline and lands in the daily note **without
interrupting** (M19). The acceptance scenario in `docs/ROADMAP.md` is the test: 20
spoken tasks produce 20 correct note entries, 0 lost, 0 duplicated.

The budget shaping everything here is D-29, the three-a-day interruption budget, which
applies to S14, S13 and S17 — this system charges its signals against that budget rather
than setting one of its own. The one-signal rule is M25's own, not a decision's: a stalled
objective must raise **one counted signal**, not a reminder stream. A system that nags is a
system the owner mutes, and a muted butler is D-50's bad Afon: half-baked background state
that has to be undone from a terminal. Stall detection that fires on a schedule is a
reminder with extra steps.

If this is absent: tasks are heard and forgotten, and "I have been stuck on this for a
week" is something the owner notices rather than something the system surfaces. The
09:00–12:30 block in the north-star Tuesday loses its silent half.

## Structure

- `src/afon/brain/objectives.py` — 420 lines, and the only place a multi-day goal is
  held. `ObjectiveBook` persists to `objectives.json`: `assign`, `active`, `find`,
  `set_status`, `append_progress(note, deferred)`, `add_milestone(text, target)`,
  `complete_milestone`, `next_milestone`, and `stall_reason(obj, now)` — the function
  that makes "stalled" a computation, with `STALE_DAYS = 7` (33.F1, 33.F2, `done` in the
  registry, `bench/test_objectives.py`). 33.F1's status evidence is `unverified-import` —
  an imported claim, not a verified run. `advance_objectives(llm, registry, tools)` is the bounded
  step that moves one forward; `spoken_objectives_report` reads it back.
- Attribution: `attribution(task)`, `turn_attribution(user_text, book)`,
  `why_this_turn` and the auditable `attribution_report`. Every task names its
  objective or is explicitly ad-hoc (33.F3, done, `bench/test_goal_attribution.py`).
- `src/afon/brain/tasks.py` — the open commitments behind L4. `TaskQueue` over
  `afon_tasks.sqlite`, a `KEEP_FOREVER` store: `add`, `update`, `get`, `active`, with
  `normalize_priority`, `human_deadline` and `elapsed_s`.
- `src/afon/brain/tools/objectives.py` — the model-facing tool surface, subject to the
  typed boundary (D-04). `drop_objective` and `complete_objective` are in
  `CONFIRM_TIER`; milestone additions are not, because capture is deliberately
  frictionless.
- `src/afon/brain/goal_deviation.py` — the **one** path from a stated goal to an
  interruption, 296 lines. Every other proactivity source is structurally unable to
  interrupt: `BASE_URGENCY` is a hardcoded literal per source, this one computes
  urgency from days-to-deadline and adds `SUSTAINED_BONUS` and `PROLONGED_BONUS` up to
  `URGENCY_CEILING = 0.94`. It writes `goal_deviation_log.jsonl` capped at
  `_MAX_LINES = 5000`, and `confirm` / `held` / `voiced` exist so a dismissed signal
  does not return as a new one. Note the coupling: `goal_deviation_signals` reads its
  goals from `world_model.WORLD`, not from `objectives.py`, and `world_model.py` is on
  D-26's deletion list — see the S30 open questions.
- `src/afon/brain/scheduler.py` — `_fire_objectives` and `_fire_weekly_review` are the
  scheduled entry points (`33.R3`); `src/afon/brain/proactive.py` and
  `proactive_signals.py` deliver the counted signal inside the D-29 budget.

Ownership: the brain process. `objectives.json` and `afon_tasks.sqlite`, both
`KEEP_FOREVER` in `src/afon/brain/inventory.py`, plus the daily note in the vault, which
D-22 makes authoritative. Open tasks: `33.R1` stall detection, `33.R2` conflict
detection, `33.R3` weekly review, `33.E1` a quarter with nothing going stale unnoticed.

## Goals

1. A spoken sentence becomes a task with a real, structured deadline, written to the
   daily note without interrupting (M19, M21).
2. Every task names the objective it serves, or is explicitly ad-hoc — no unattributed
   commitments (33.F3).
3. "Stalled" is computed from a milestone's target date, not inferred from tone
   (33.F2).
4. A stalled objective raises exactly one counted signal, and a dismissed signal does
   not return as a new one (M25, D-29).
5. Two objectives competing for the same hours are surfaced as a conflict rather than
   discovered as a dropped one (33.R2).
6. A weekly review states what moved, what did not, and what to drop (33.R3).

## Benchmarks

1. **B2 drill** — the north-star loop, M19. Speak 20 tasks with deadlines during a
   focus block. Threshold: 20 correct entries in the daily note, 0 lost, 0 duplicated,
   0 audio interruptions during the block. Last measurement: `not yet measured`.
2. **B1 planned** — `bench/test_objective_stall.py` (the `33.R1` gate, not yet written).
   Threshold: a milestone past its target date raises exactly one signal; the same
   condition on the next tick raises zero further signals. Last measurement:
   `not yet measured`.
3. **B1** — `bench/test_objectives.py` and `bench/test_goal_attribution.py`. Thresholds:
   `stall_reason` returns a reason for every stale objective, and 0 tasks are
   unattributed. Registry records 33.F1–33.F3 `done` as of 2026-10-03; no field
   measurement.
4. **B5** — interruption cost of goal deviation, against the D-29 budget. Threshold: goal
   deviation accounts for ≤ 1 of the 3 permitted daily audio interruptions, and exactly 0
   inside a focus block. Last measurement: `not yet measured` — M23 owns the budget
   measurement and has not been run.
5. **B1 planned** — `bench/test_objective_stall.py [conflict]` (the `33.R2` gate).
   Threshold: two objectives with target dates inside the same day are reported as
   competing, 0 silent losses. Last measurement: `not yet measured`.
6. **B2** — `bench/test_protocol_reports.py` extended (the `33.R3` gate): a weekly review
   is produced, read, and names at least one thing to drop. Threshold: 0 weeks where the
   review is produced and unread. Last measurement: `not yet measured`.
7. **B3** — `33.E1`: a quarter in which no objective goes stale unnoticed for more than a
   week. Last measurement: `not yet measured`.

## Failure modes

**A spoken task lands without its deadline.** The north-star loop's failure mode, and
the one that erodes trust fastest because it looks like success in the moment:

    sqlite3 "$AFON_STATE_DIR/afon_tasks.sqlite" "select title, deadline from tasks order by started_at desc limit 10;"
    journalctl -u openafon-brain --since "1h" | grep -iE "deadline|parse|attribut"
    python -c "from afon.brain.objectives import OBJECTIVES; print(OBJECTIVES.active())"

**An objective is stalled and nothing was said.** Detection and delivery are different
questions, and this is a delivery one:

    python -c "from afon.brain.objectives import OBJECTIVES; [print(o.slug, o.stall_reason(o)) for o in OBJECTIVES.active()]"
    python -c "from afon.brain.goal_deviation import log_path; print(log_path())"
    python -c "from afon.brain.goal_deviation import held, voiced; print('held', len(held()), 'voiced', len(voiced()))"

**Signals repeat after a dismissal.** `held()` and `voiced()` are the dedupe; a repeat
means the key changed, which is a key-stability defect in `goal_deviation.py`.

**A task belongs to no objective.** `attribution_report` exists for exactly this:

    python -c "from afon.brain.objectives import attribution_report, OBJECTIVES; from afon.brain.tasks import TaskQueue; print(attribution_report(OBJECTIVES, TaskQueue().active()))"

**Everything is urgent.** `URGENCY_CEILING` is 0.94 and the bonuses are additive, so
prolonged work approaches the ceiling by construction. A week of sustained stalling makes
every objective look urgent, spending the interruption budget on the owner instead of on
the work.

## Open questions

1. What is the deadline unit when the owner says "next week"? `33.F1` records a
   structured deadline as done, but the resolution rule for a vague relative date is the
   part that decides whether M19 passes, and no decision states it. D-56 is the
   poor-microphone audio gate and says nothing about dates; D-52 asks for an uncertain
   answer to be audible, which is a speaking rule and not a parsing one. The
   conservative branch is currently unwritten.
2. Is a stalled objective a signal or a weekly-review line? M25 says one counted signal,
   but an objective due in three weeks does not warrant an interruption, and the
   threshold between the two is not written down.
3. Should conflict detection be an objective feature at all? `33.R2` asks Afon to tell
   the owner two things compete — judgement about the owner's own priorities, which is
   the same ground D-27 clears the recommendation engine from.
