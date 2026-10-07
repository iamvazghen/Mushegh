# S31 — Self-Monitoring, Diagnostics & Self-Healing

> **One line:** The surface the 2:00 AM rule is written for — four health views that agree, a typed error taxonomy, learned tool reliability, and the trend detection that is still missing.
> **Status:** complete for now · **Registry:** S31 · 5/6 floor, 0/7 raise, 0/1 elite
> **Milestones:** none of M01–M40 names S31; trend detection is unscheduled · **Decisions:** D-01, D-43, D-44

## Purpose

This is the system that answers "what is wrong, and how would I find out at 2 AM". It
checks the brain's own organs, decides which declared degraded mode the host is in,
correlates a failure to a turn, learns which tools have been flaky, repairs what it
can, and says what it cannot repair.

Its standard is D-01: diagnosable in 90 seconds with `journalctl`, `sqlite3` and
`curl`. Every surface here is text, a table, or a one-line spoken summary, because a
dashboard that is down cannot be the diagnosis. Under D-43 a green hermetic suite is
necessary and insufficient, and the D-44 elite bar — 30 days, zero panics, zero
corruption, zero unexpected egress — is this system's real test.

The honest gap: **nothing here watches a trend.** Every check is a point-in-time probe.
A subsystem whose p95 climbs from 120 ms to 900 ms over three weeks is "healthy" on
every probe in this file, and the owner finds out from the barge-in defect instead
(D-49). `31.R1` is the task, its gate `test_metrics.py [trend]` exists, and no
milestone carries it.

If this is absent: a brain failure is a silence. There is no way to tell degraded from
dead, and `src/afon/edge/degraded_answers.py` has no accurate picture to fall back on.

## Structure

Four health surfaces asserted to **agree** (31.F1, done,
`bench/test_health_agreement.py`): a structural check, a functional probe, the HUD, and
the runtime mode. A disagreement means one of them is lying, and the test fails.

- `src/afon/brain/health.py` — the structural check: `_check_vault`, `_check_ticker`,
  `_check_pc_link`, `_check_cache`, `_check_task_queue`, then `check()`,
  `summarize(snapshot)` (one spoken line), `mode_from(snapshot)` (which declared mode
  this host is in — `src/afon/shared/degraded.py` holds `FULL`, `BRAIN_DOWN`,
  `EDGE_DOWN`), `degraded_signals()` and `health_signals()`.
- `src/afon/brain/reliability.py` — the functional probe. `safe_call` wraps any
  awaitable so an exception becomes a short speakable error instead of a dead brain;
  `health_probe()` runs the real dependency checks; `attempt_repair_and_escalate()` is
  the repair path with an escalation latch in `health_escalation.json` (31.R2,
  `bench/test_self_repair.py`).
- `src/afon/brain/hud.py` — `hud_snapshot()` renders the same data for the React HUD in
  `clients/hud-spatial/src/`. Optional; the system is complete without it.
- `src/afon/brain/loops.py` — the background loop registry: `ticks(name)`,
  `snapshot(now)`, `problems(now)`, and `set_period` declaring each loop's period so a
  loop that stopped ticking is visible (31.F4, done, `bench/test_loop_registry.py`).
- `src/afon/brain/tool_reliability.py` — reads the audit trail and reports which tools
  have been flaky: `reliability(days)`, `reliability_summary(limit)`, `flaky_note()`
  (31.F3, done, `bench/test_tool_reliability.py`).
- `src/afon/brain/metrics.py` — 64 lines. Counters plus a rolling 200-sample latency
  window behind the `METRICS` singleton. Deliberately not Prometheus (D-01).
  `src/afon/brain/turn_trace.py` — one row per turn: tools fired, stage timings, sources
  read. **In-process `METRICS` does not survive a restart; this does**, which is why it
  is the only viable substrate for trend detection.
- `src/afon/brain/data_classes.py` and `src/afon/shared/errors.py` — the typed error
  taxonomy and turn correlation (31.F2, done, `bench/test_error_taxonomy.py`).
  `src/afon/edge/audio_watchdog.py` and `src/afon/edge/voice_health.py` — the edge-side
  counterpart, for the device rather than the brain.
- `deploy/uptime_watch.py` — the outside-in complement, and the only surface that can
  report the brain down, because the brain cannot report itself down (M37, which is
  scoped to S23; no milestone in M01–M40 names S31).

Ownership: the brain process owns its own checks; `deploy/uptime_watch.py` runs outside
the host.

## Goals

1. Four health surfaces that agree, so a disagreement is a defect rather than an
   ambiguity (31.F1).
2. A recoverable failure becomes a spoken error and a repair attempt, not a dead
   process, and an unrecoverable one escalates to the owner exactly once (31.R2).
3. Every background loop declares its period and appears with its last tick, so a loop
   that silently stopped is visible (31.F4).
4. A rising p95 or rising retry rate is detected as a **trend** and raised before the
   system fails, not after (31.R1, open).
5. One correlation id per turn, minted at the edge and stamped on every brain stage, so
   a complaint is traceable and the trace joins to the audit line
   (`bench/test_correlation_id.py`, which labels itself `31.F5`; the registry still
   carries the work as open `31.R4`).
6. The budgets act rather than report: a breach of a prefill, catalogue or p95 budget
   triggers its governor instead of being written down (31.R5, open).

## Benchmarks

1. **B1** — `bench/test_health_agreement.py`. Threshold: structural check, functional
   probe, HUD and declared mode report the same state across every fixture; 0
   disagreements. Registry records 31.F1 `done` as of 2026-10-03; no field measurement.
2. **B1** — `bench/test_self_repair.py`. Threshold: every repairable failure shape reaches
   "repaired" without operator action, and an unrepairable one escalates once and does
   not re-page. Registry records 31.F2/31.F3 `done`; 31.R2 (the top five recurring shapes
   from the journal) is open. Last measurement: `not yet measured`.
3. **B1** — `bench/test_loop_registry.py`. Threshold: 0 declared loops missing from the
   snapshot, 0 loops whose last tick exceeds their declared period by more than one
   period. Registry record 2026-10-03.
4. **B1 planned** — `bench/test_metrics.py [trend]`, the 31.R1 gate, extended over
   `turn_trace.py` rows rather than in-process `METRICS`. Threshold: a synthetic series
   with p95 rising monotonically over 30 rows raises exactly one signal before any single
   probe goes red. Last measurement: `not yet measured`.
5. **B1** — `bench/test_correlation_id.py`, 205 lines, hermetic. Threshold: one simulated
   turn, and every record it produces — turn trace, tool call, audit line — carries the
   same id; 0 joins fail. Last field measurement: `not yet measured`; the test proves the
   plumbing agrees, not that a real incident was traced. The registry calls this a
   *planned* gate for `31.R4` while the test's docstring labels it `31.F5`.
6. **B1 planned** — `bench/test_governors.py` (the 31.R5 gate, not yet written).
   Threshold: each budget breach triggers its governor within one turn; 0 breaches
   reported without acting. Last measurement: `not yet measured`.
7. **B3** — the D-44 elite bar, restated as this system's benchmark: 30 consecutive days
   with zero panics, zero data corruption, zero unexpected cloud egress. Last
   measurement: `not yet measured`; M40 is elapsed time, not engineering.
8. **B2 drill** — outside-in liveness. M37 is scoped to S23 and no milestone names S31,
   so no milestone carries this drill: stop the brain, confirm
   `deploy/uptime_watch.py` notices from another host, and that the number it reports is
   one it produced by asking. Last measurement: `not yet measured`.

## Failure modes

**The brain is down and cannot say so.** The only surface that works is the outside-in
one; its absence is the failure.

**Health says green and the system is degraded.** Find the surface that is wrong:

    python -c "from afon.brain.health import check, summarize; print(summarize(check()))"
    python -c "from afon.brain.reliability import health_probe; print(health_probe())"
    python -c "from afon.brain.loops import problems; print(problems())"

**A background loop stopped ticking, or a tool has been quietly flaky.** `loops.problems()`
names the first; `tool_reliability` reads the audit trail for the second:

    python -c "from afon.brain.loops import snapshot; print(snapshot())"
    python -m afon.brain.tool_reliability
    journalctl -u openafon-brain --since "24h" | grep -ciE "tool.*(fail|error)"

**Escalation pages repeat.** The latch lives in `health_escalation.json`; a repeated page
means the latch was not written, and the page itself is the defect.

**A trend is missed.** The standing failure, invisible from all of the above, because
every probe is a point sample. It surfaces as an unrelated symptom — barge-in latency
(D-49) — before it surfaces as a health event.

## Open questions

1. What is the substrate for trend detection: `turn_trace.py` rows, a new rolling table,
   or the journal? `METRICS` is in-process and dies with the daemon, so the in-memory
   p95 that already exists is useless across a restart — and the answer changes what a
   "trend window" even means.
2. Should a governor breach be a signal or a hard stop? `31.R5` says the budgets act.
   Acting on a p95 breach means shedding load, and the only load Afon can shed is the
   owner's own turns.
3. What is the top-five recurring failure list, and who refreshes it? `31.R2` derives it
   from the journal, so the repair surface grows with whatever has been breaking rather
   than with what matters.
