# S46 — Predictive Analytics & Forecasting

> **One line:** a decision record for work that should not happen — no ML forecasting, a
> deterministic calendar look-ahead instead, and gates that fail if a model creeps back in.
> **Status:** **removed by decision 2026-10-03** — no ML forecasting (D-28). A deterministic calendar look-ahead serves scheduling; that logic belongs to S21 and S33 · **Registry:** S46 · 3/3 floor, 0/0 raise, 0/0 elite (all four non-floor tasks `cancelled`)
> **Milestones:** M05 · **Decisions:** D-28, D-42, D-46, D-47

> This document exists so the system is not rebuilt by accident from the blueprint. It is not
> a roadmap. `46.R1`–`46.R3` and `46.E1` were marked `cancelled` on 2026-10-03, each with an
> `owner-decision` record naming D-28. A cancellation is not progress: no task was completed
> by it, and the three floor tasks below still read `done` because they were.

## Purpose

S46 was going to be a modelling system: one predictor, then a second, then trend
extrapolation over screen time, sleep and spend, then a "what if" engine — each gated on the
previous one beating a naive baseline.

**Afon does not forecast.** A deterministic, calendar-backed look-ahead satisfies scheduling
(D-28). Holt-Winters, ARIMA and habit forecasting are blueprint leftovers, and the blueprint
is still circulating and looks authoritative. What remains useful is not a model: it is
arithmetic on a sorted list of today's events — `src/afon/brain/schedule.py`, belonging to
S21, with the planning that consumes it in S33. What breaks if it stays removed: nothing.

## Structure

| Path | What it is | Disposition |
|---|---|---|
| `src/afon/brain/forecast.py` | 46.F1–F3: "will today's plan fit the day", computed in-process with no model; a JSONL ledger scoring every prediction against what happened; a confidence floor below which nothing is spoken | delete or honestly rename under M05 — but it has a live caller |
| `src/afon/brain/tools/day_shape.py` | the only importer: `_forecast_line(events)` calls `forecast.predict_day_fit`, `busy_minutes` and `record`, speaking the line only above the confidence floor | **not deleted by M05** — the day's shape is useful; only the modelling framing goes |
| `bench/test_forecast.py` | the gate for those three tasks; it exists and it passes | delete with the module. A green test for deleted code is the exact trap S15's document describes |
| `forecasts.jsonl` | the ledger, declared in `src/afon/brain/inventory.py` and classified in `src/afon/brain/data_classes.py` | deletion orphans a **declared** store; both declarations have to go with it |
| `src/afon/brain/schedule.py` | 21.F2: overlap, travel and no-break on a sorted day's events. Arithmetic; no model consulted | **keep** — this is where D-28's look-ahead lives |

M05's acceptance line: `forecast.py` deleted or honestly renamed, and no time-series model
under `src/afon/`.

## Goals — anti-goals

1. No time-series model — no Holt-Winters, ARIMA, Prophet or learned habit model — anywhere
   under `src/afon/`.
2. Scheduling is answered by arithmetic on the calendar, and a prediction that could have
   been an assertion is not made.
3. The removed scope stays removed: no second predictor, no trend extrapolation, no "what
   if" engine, and no restoration of the four cancelled tasks without an owner decision.
4. The day's shape is still reported — that is S21's arithmetic, and D-28 removes the
   modelling, not the line.

## Benchmarks

Deletion gates, not quality gates. Each one **fails** if the system reappears. No accuracy
figure is recorded, and none should be: a scoring ledger for a removed system is a number
that outlives its reason.

| Anti-goal | Tier | Command or drill | Threshold | Last measurement |
|---|---|---|---|---|
| 1 | B1 | `grep -rniE "^\s*(import\|from)\s+(statsforecast\|statsmodels\|prophet\|pmdarima\|sktime)" src/afon/` | 0 imports | **0 imports today**, checked 2026-10-03. A loose keyword grep returns 2 hits, both prose in `forecast.py`'s own header |
| 2 | B4 | `src/afon/brain/schedule.py` | overlap, travel and no-break computed in-process, 0 model calls on the path | holds by inspection 2026-10-03; no test asserts it |
| 3 | B1 | `python scripts/systems_plan.py check` | 4 tasks read `cancelled`, 0 read `open`, every cancellation carrying an `owner-decision` record | last run 2026-10-03 with the reconciliation; re-run by M05, not by this document |
| 4 | B4 | `Test-Path src/afon/brain/forecast.py` | absent, and `grep -rn "from afon.brain import forecast" src/afon/` returns nothing | **fails today** — the file is present and `tools/day_shape.py` imports it. This is M05's work |
| 5 | B4 | `python -c "from afon.brain.inventory import undeclared; print(undeclared())"` | 0 undeclared stores, so the deletion leaves no orphaned `forecasts.jsonl` | **fails today** if the module goes without its two declarations; passes while it is intact |

## Failure modes

**A model creeps back in as "just a small one"** — predict a task duration, anticipate a
habit, phrased as convenience. D-28, arrived at from the friendly direction:

    grep -rniE "^\s*(import|from)\s+(statsforecast|statsmodels|prophet|pmdarima|sktime)" src/afon/
    ls -la src/afon/brain/forecast.py bench/test_forecast.py
    python scripts/systems_plan.py check

**The green test makes dead code look alive.** Three `done` rows and a passing suite, so the
dashboard shows green and no removal:

    uv run python bench/test_forecast.py
    python -c "import json;d=json.load(open('docs/systems-plan.json',encoding='utf-8'));print([s['status'] for s in d['systems'] if s['id']=='S46'])"

**"Deterministic look-ahead" gets read as forecasting.** The ledger was built so a forecaster
could be caught being wrong; there is now nothing to catch:

    python -c "from afon.brain import forecast; print(forecast.__doc__.splitlines()[0])"
    grep -rn "forecast" src/afon/brain/ | grep -v "forecast.py:"

**The schedule logic is deleted with the module.** `schedule.py` is S21's, and M05 says "no
time-series model" rather than "delete the predictor". Losing overlap detection to a tidy-up
is a regression with a user-visible cost.

## Open questions

1. Delete `forecast.py` outright, or rename it and keep the ledger? M05's acceptance line
   allows both; the ledger is the only artefact with evidence value, and only if something is
   left scoring.
2. Should `46.E1`'s "beat the naive baseline over a month" be retired or recorded as
   superseded? It owes no evidence, but a cancelled elite row is a claim that something was
   once worth proving.
3. `forecast.py`'s docstring calls `anticipation.py` a calendar look-ahead; it is not — it is
   S14's LLM-backed signal source. Who fixes the stale line, M05's deletion or S14's owner?
