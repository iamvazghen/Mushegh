# S17 — Morning Brief

> **One line:** one consolidated catch-up, fired by the owner starting his day rather than by a
> clock.
> **Status:** complete for now · **Registry:** S17 · 3/3 floor, 0/3 raise, 0/1 elite
> **Milestones:** M24 · **Decisions:** D-33, D-29, D-18, D-34

## Purpose

Past-due tasks and important unread mail, in one place, once. Not as six separate nudges.

The registry still describes this system as a 06:00 digest, and the charter has moved it.
**The brief is triggered, not scheduled** (D-33): it fires on the first morning device
interaction — the workstation unlock — and the charter has no fixed 06:00 anywhere in it. The
code still has one: 17.F1 is `done` with the gate text "Digest at 06:00", and that un-moved
clock is exactly what M24 changes. The brief renders **silently on screen**, and it speaks
only if the owner explicitly asks. A brief that speaks itself into an empty room at 06:00 is
an interruption, and interruptions are budgeted
(D-29); unprompted speech for summaries is explicitly out of scope (D-18).

The second job is to be honest about its own inputs. A source that is down degrades its own
section and names itself as failed; it never takes the whole brief with it. A section with
nothing worth saying is dropped, and the brief says so in one line rather than padding.

If it is absent, the owner goes back to per-item task and mail nudges — the exact failure this
module was written to stop.

## Structure

| Path | Role |
|---|---|
| `src/afon/brain/daily_digest.py` | The digest itself: past-due tasks plus important unread mail, delivered on at most two channels per local day |
| `src/afon/brain/schedule.py` | The day read as a whole — overlap, travel, no-break. Arithmetic on a sorted list, no model consulted |
| ~~`src/afon/brain/mynews.py`~~ | **Was** "the news section". It is not one, and does not belong in this table — see below |
| `src/afon/brain/tools/day_shape.py` | Drafting routines and checking whether the day holds together |
| `src/afon/brain/presence.py` | The context the trigger reads |
| `clients/hud-spatial/src/App.tsx`, `src/afon/brain/hud.py` | The silent on-screen surface |
| `src/afon/edge/edge_lite.py`, `src/afon/brain/telegram_bridge.py` | The two channels, both of which can carry the brief when it is asked for |

**The news section is gone, and the row is kept struck through rather than deleted** so the
correction is visible. This table claimed `mynews.py` supplied "the news section"; it does
not. `src/afon/brain/daily_digest.py` contains no news, RSS or headline path at all —
`scheduler.py` describes the digest as past-due tasks plus important unread email, which is
everything it actually builds. The module was an *unprompted* proactive signal rather than a
digest section at all, so it belonged to the D-34 breach, and 41.R4 closed that path. The
author of the row conflated an ambient push with the brief; neither the brief nor
`daily_digest.py` ever referenced each other.

Two channels exist because the owner has two situations. The `push` channel is the timed
briefing that reaches a phone with the laptop off; the `edge` channel appends the digest to the
first live-edge turn of the day, so it is heard conversationally the moment he starts talking.
A small JSON state file, `state_dir() / "daily_digest_state.json"`, records which channel
already delivered on which date — so neither repeats within a day and **a brain restart never
re-fires it**.

Every source is fail-quiet: a broken mail or task call drops that part of the digest and
nothing else. The system is "complete for now", which is the registry's word; the trigger
change (M24) is open work, not done work.

## Goals

1. The brief fires on the first morning device interaction, never on a clock (D-33, M24).
2. It renders silently on screen and speaks only when asked (D-33).
3. One delivery per channel per local day, and a restart does not re-fire it (17.F2).
4. A failed source degrades its own section and names the failed source; the brief still
   renders (17.F3).
5. A section with nothing worth saying is dropped, and the brief says so in one line (17.R2).
6. The evening counterpart produces a concise markdown log at 18:00 (M24, 17.R3).
7. The brief never contains an unprompted proposal (D-34, D-27).

## Benchmarks

| Goal | Tier | Command or drill | Threshold | Last measurement |
|---|---|---|---|---|
| 1 | B2 | M24 drill: unlock the workstation at 05:40 and again at 10:00 | the brief appears on first interaction in both cases; 0 deliveries with no device interaction | not yet measured (M24 open) |
| 2 | B2 | M24 drill: unlock, observe, do not ask | 0 audio emitted at fire time; the brief is legible on screen without a spoken word | not yet measured (M24 open) |
| 3 | B1 | `uv run python bench/test_daily_digest.py`, `uv run python bench/test_acknowledgements.py` | 0 duplicate deliveries per channel per local day, including across a simulated restart | registry records 17.F2 done; run not reproduced here — not yet measured |
| 4 | B1 | `uv run python bench/test_daily_digest.py` [source down] | 31/31 per the registry gate note, with the failed source named in the rendered brief | recorded in the registry as 31/31; run not reproduced here |
| 5 | B1 | `uv run python bench/test_daily_digest.py` [empty section] | 0 empty sections rendered; the dropped sections are named in one line | not yet measured (17.R2 open) |
| 6 | B1 | new `bench/test_digest_timing.py` (planned, 17.R3 — does not exist yet) | 18:00 produces a concise markdown log naming what happened, what slipped and what tomorrow needs | not yet measured |
| 7 | B4 | read the rendered brief against `src/afon/brain/recommend.py`'s output shape | 0 proposals in the brief; every line traces to a task, an event or an unread message | holds today — the brief is built from three sources, none of which generate |

The charter has no fixed 06:00, and 17.F1's gate name still says `bench/test_daily_digest.py`
for a 06:00 behaviour. That test is the thing standing between the charter and the code today.

## Failure modes

**Duplicates.** The recorded incident this module was written to stop: the same two lines —
"N past-due tasks", "M important emails" — pushed three or four times each, seven or eight
duplicates a day, because the old nudges were repeat-suppressed for 120 minutes and reset on
every brain restart. If it recurs, the state file is being reset or is unreadable. Diagnose:
`cat ~/.afon/daily_digest_state.json`, then `journalctl -u openafon-brain -n 200 | grep -i
digest`.

**The clock still fires it.** The trigger has not been moved to first-interaction (M24 is
open), so a push can land at 06:00 into an empty room, and the edge channel then delivers the
same content again. Owner symptom: the same two lines, twice, one of them before he is awake.
Diagnose: the scheduler entry in `journalctl`, and the state file's recorded date.

**A source is down and the brief is thin.** Correct behaviour, and it must say which source
failed rather than quietly rendering a shorter brief the owner reads as "nothing happened".
Diagnose: the failed-source name in the rendered output, then the section's own log line.

**It speaks unasked.** A regression against D-33. The budget in S14 is the backstop, and the
budget counts audio interruptions, so an unasked brief is both a charter breach and a budget
spend. Diagnose: `journalctl -u openafon-brain -n 200 | grep -i "via voice"`.

**Padding.** A section with nothing to say still renders, and the brief grows. Harmless once,
 corrosive by the fourth time — it is how a digest becomes an ambient feed (D-34).

## Open questions

1. What is the trigger's edge case: a phone-only morning with the laptop off, where the first
   interaction is a push, not an unlock?
2. Does the trigger reset per day, or per first interaction after the quiet hours end? The
   difference is a 04:00 phone check.
3. 17.R2's relevance filter needs a per-section emptiness test. Is that a count, a
   deterministic filter, or the same relevance threshold the proactive engine already holds?
