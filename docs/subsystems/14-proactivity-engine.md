# S14 — Proactivity Engine

> **One line:** the part of Afon that speaks unasked, kept inside a hard budget and graded on
> how often it is waved off.
> **Status:** complete for now · **Registry:** S14 · 3/3 floor, 2/6 raise, 0/1 elite
> **Milestones:** M23 · **Decisions:** D-29, D-30, D-31, D-34, D-18, D-50, D-72, D-73

## Purpose

Everything else in Afon waits to be addressed. This is the one module that decides, on its
own, whether to speak first — and the discipline is entirely in what it is measured on.

The objective was wrong as originally written. 14.R1 asks "did the intervention help?", and
that question cannot be answered honestly: a **tolerated** interruption reads as helpful, so
the engine can score well by being tolerated. The charter replaces it — optimise for
**dismissal rate and daily interruption count** (D-30). Those are the numbers a butler can be
held to, and they are the numbers a nagging system fails.

Three rules sit underneath. A refusal is a negative calibration sample: log it, halt the
action immediately, and never argue back (D-31). Afon never brings the owner something unasked
because it seemed interesting (D-34). And unprompted speech has a hard scope — physical
safety and hard calendar count-downs only, with zero unprompted speech for recommendations,
summaries or banter (D-18).

It is "complete for now" and the status is the registry's, not a claim of quality. Four of
the six raise tasks are open — 14.R1, 14.R2, 14.R3 and 14.R6 — and the outcome loop that
would close D-30 is 14.R1, one of them.

## Structure

| Path | Role |
|---|---|
| `src/afon/brain/proactive.py` | The engine: a background tick, a pure decision core (budget, quiet hours, relevance threshold, repeat suppression, day rollover), injectable clock and signal sources |
| `src/afon/brain/proactive_signals.py` | Signal sources: `anticipatory_prep`, `pattern_suggestion`, `weekly_digest` |
| `src/afon/brain/interventions.py` | The single deliberate interruption: media playing **and** a named calendar event inside the lead window. Off by default (`interventions_enabled`) |
| `src/afon/brain/proactive_report.py` | What, why, and the brief reasoning for anything done unprompted; one bounded LLM call with a deterministic fallback |
| `src/afon/brain/delivery.py` | The downstream half — records what happened after the message left |
| `src/afon/brain/loops.py` | Every recurring loop declared statically with a period, a budget and a kill switch |
| `src/afon/brain/governor.py` | The ceiling on autonomous action: calls, spend and wall-clock across all runs |
| `src/afon/brain/presence.py`, `src/afon/brain/modes.py` | Whether now is a sensible moment |

The engine is one process on the brain. Two channels: a listening edge gets a spoken
interjection, otherwise it falls back to an ntfy push. It is fail-quiet throughout — a broken
signal source or a failing emit channel never throws into the tick, and the worst case is
silence.

Feedback learning is per signal **kind**: a reaction folds into a penalty in [0, 0.45] that
raises that kind's effective threshold, with a seven-day half-life so a bad week does not mute
a kind forever. Dismissals bite hardest (`+0.15`), ignores nudge (`+0.05`), acting on a nudge
eases it back (`-0.09`). The reaction classifier is deliberately high-precision: ambiguous
replies are neutral and teach nothing.

**This system owns one Jev seam, and now neighbours a second one with the opposite
behaviour.** The seam here is the explicit two-option question (`JudgmentService.judge()`,
14.R5, done, gate `bench/test_jev_judgment.py`): when Jev cannot answer, it **asks the owner**,
on the full 8s service timeout. That is unchanged, and the arbitration change did not touch it.
The tool-arbitration seam (01.R6, D-72, D-73) lives in **S01**, not here, and when it cannot
answer it **keeps every candidate and says nothing**, inside a 400ms cap. The asymmetry is the
point, and the reason is what each alternative costs: on an explicit question the alternative
to Jev is a guess about the owner's life, so asking is the honest answer; on tool arbitration
the alternative is a working deterministic router, so a marginal improvement is not worth a
second of the owner's turn. Collapsing the two — letting "the model was unsure" read as "the
model decided" — is the failure both decisions are written against. 14.R6, which would bring
Jev to borderline goal-deviation severity, stays open and unchanged, and its registry gate
already requires that outage behaviour not move.

## Goals

1. The engine is graded on dismissal rate and daily interruption count, not on helpfulness
   (D-30, 14.R1).
2. Three audio interruptions per day maximum; exactly zero inside a focus block (D-29, M23).
3. A refusal halts the action, is logged as a negative calibration sample, and is never argued
   with (D-31).
4. Every signal kind is asserted *reachable* — a dormant kind is a bug, because a kind that
   silently stopped generating and a kind that is being correctly restrained both read as zero
   (14.F3).
5. Every autonomous act produces a report: what, why, and the reasoning (14.F2).
6. Nothing arrives because it seemed interesting (D-34).
7. Every recurring loop declares a period, a budget and a kill switch before it starts.

## Benchmarks

| Goal | Tier | Command or drill | Threshold | Last measurement |
|---|---|---|---|---|
| 1 | B2 | seven-day run of the live engine; read the per-kind stats block | dismissal rate and daily interruption count recorded for 7 days; 0 kinds whose `shown` count is high and whose `held_*` counts are all zero | not yet measured (14.R1 open) |
| 2 | B1 | `uv run python bench/test_proactive_windows.py` | ≤3 audio interruptions per local day; exactly 0 inside a focus block | registry records 13.F1 done, whose gate is these two scripts; 14.F1's gate is `test_phase10_proactive.py` + `test_proactive_learning.py`; run not reproduced here — not yet measured |
| 3 | B4 | `src/afon/brain/proactive.py` refusal path | a refusal sets the halt before any emit; 0 argument turns recorded; the sample is written as negative | structural, holds today |
| 4 | B1 | `uv run python bench/test_proactive_thresholds.py` | 19/19 signal kinds reachable; per the registry note, eight fired in that run and eleven were handed off | recorded in the registry gate note as 19/19; run not reproduced here — not yet measured in this doc |
| 5 | B1 | `uv run python bench/test_proactive_report.py` | every autonomous act yields a report; 0 silent autonomous actions | registry records 14.F2 done; run not reproduced here — not yet measured |
| 6 | B4 | grep the tick loop for sources that fire with no trigger | 0 signals whose trigger is "interesting"; 0 recommendations, summaries or banter in the unprompted set | holds by inspection of `src/afon/brain/proactive_signals.py` today |
| 7 | B1 | `DECLARED` in `src/afon/brain/loops.py` | every listed loop has a period, a budget and a kill switch; 0 undeclared recurring loops | not yet measured |

Also written: `uv run python bench/test_phase10_proactive.py` and `uv run python
bench/test_proactive_learning.py`, the latter covering the feedback loop that goal 1 needs.
Two planned gates do not exist yet — `bench/test_proactive_timing.py` (14.R2) and the focus
case in `bench/test_proactive_suppression.py` (14.R3, blocked on S27 context).

## Failure modes

**It speaks when uninvited.** This is the first symptom of a bad Afon in D-50, and it is the
one the owner notices inside a week. Cause is almost always a budget or quiet-hours path that
bypassed the engine — a `src/afon/brain/scheduler.py` reminder, not the tick. Diagnose: `journalctl -u
openafon-brain -n 300 | grep -i "proactive\["` and check every line's channel, then the
per-kind hold reasons.

**It goes quiet after refusals.** The penalty mechanism working as designed: repeated
dismissals raise a kind's bar until it stops. The danger is the second-order one — a real
deadline goes unheard because a kind was penalised in a bad week. The seven-day half-life
bounds it; the owner can also zero a penalty. Diagnose: the per-kind `penalty` and `updated`
fields in the persisted engine state under `state_dir()`.

**The tick never ran.** A loop that never started leaves no entry, so the surface reads clean
precisely when it should read alarming — the reason `src/afon/brain/loops.py` keeps a *static* declaration
next to the live registry. Diagnose: compare `DECLARED` against the running jobs in
`journalctl -u openafon-brain`.

**A signal source dies quietly.** Broken sources are skipped, which is correct, and the
effect is a kind that stops generating. Goal 4 exists to catch exactly this. Diagnose: the
`held_*` counters — restrained and never-generated must be distinguishable.

**The budget resets on restart.** Suppression and the day's counter are persisted for
precisely this; a regression reintroduces the duplicate-morning-messages bug from S17.

## Open questions

1. 14.R1 wants outcome feedback, but the only ground truth is a reaction classifier over the
   next turn. Is dismissal count a sufficient objective, or does it need a positive signal
   that is not "he acted on it"?
2. `pattern_suggestion` in `src/afon/brain/proactive_signals.py` proposes a one-tap action from a learned
   pattern. Is that a notification (S13's budget) or the recommendation system D-27 removed?
3. 14.R2 wants a learned timing model. Given a seven-day half-life on the penalty, is timing
   worth a second learning loop, or should effort go to the focus-state suppression in 14.R3?
