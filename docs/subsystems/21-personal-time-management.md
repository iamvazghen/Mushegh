# S21 — Personal Time Management

> **One line:** The shape of the owner's day, and the named reason a day will not work before it starts.
> **Status:** built, not well structured · **Registry:** S21 · 3/3 floor, 0/3 raise, 0/1 elite
> **Milestones:** M22 · **Decisions:** D-62, D-33, D-29

## Purpose

Two capabilities. First, the owner's actual routines — when he is normally doing what, and
which commitments repeat — held in a file he edits. Second, the ability to look at a whole
day and say "this will not work", naming which of the three ways it is broken: an overlap, a
travel gap too short, or no break.

It refuses to run the owner's calendar. An over-constrained day preserves owner-pinned
events, highlights the conflict, and offers focus blocks; it never imposes them, moves a
pinned event, or fills an empty hour. A schedule it decided is one the owner has to unpick,
which is the shape of the half-baked state D-50 forbids.

If it is absent the owner keeps a system that can list events and warn that one is
imminent, and nothing else: a day can be structurally impossible and Mushegh will not say so
until 09:00, when the first clash has already cost something. The second absence is quieter
and worse — the capability is built and unfed. `~/.mushegh/routines.json` holds two dynamic
commitments and no windowed entries, so everything downstream reasons from an empty file.
Timing of the morning brief is **not** this system's business: the learned-wake-pattern idea
is superseded, and the brief fires on the owner's first interaction, rendering silently
(D-33). S21 supplies what it would contain; S17 decides when it appears.

## Structure

Brain-side, in the always-on process, reading the calendar over the same transport as
everything else.

| Path | Role |
|---|---|
| `src/mushegh/brain/schedule.py` | `Clash`, `clashes()`, `spoken()` — the three ways a day is broken |
| `src/mushegh/brain/tools/day_shape.py` | The day-shape tools, deliberately not in the always-advertised `routines.py` |
| `src/mushegh/brain/routine_draft.py` | Drafts land in a file for the owner to adopt, never straight into `routines.json` |
| `~/.mushegh/routines.json` | The owner's routines; read by `src/mushegh/brain/proactive_signals.py` for routine anchors |
| `src/mushegh/brain/anticipation.py` | Calendar look-ahead — reading what is already written down |
| `src/mushegh/brain/goal_deviation.py` | The one path from a stated goal to an interruption, held against the budget |
| `src/mushegh/brain/patterns.py` | Time-of-day and topic patterns from the command log, persisted as L1 facts |
| `src/mushegh/brain/forecast.py` | A forecaster today; D-28 removes it as a modelling system, leaving the deterministic look-ahead |
| `src/mushegh/brain/presence.py`, `src/mushegh/brain/tools/activity.py` | The actual-vs-planned source for 21.R2 |

Flow: the calendar is read through `src/mushegh/brain/google.py` and
`src/mushegh/brain/tools/calendar.py`; `schedule.clashes()` classifies the day; `day_shape`
tools render it; a focus block is proposed, and once accepted `src/mushegh/brain/modes.py`
holds it, silencing audio interruptions for its duration (D-29).

**Calendar sync is not two-way, and the credential is not the one D-62 names.** There is
no CalDAV client anywhere in `src/mushegh/`; the read and create path is a Google OAuth
refresh token shared with Gmail, while M22's done-when is a CalDAV token installed. That is
recorded rather than smoothed over, and it is an open question below. What it stores:
`~/.mushegh/routines.json`, the presence database for actuals, and audit lines for every
schedule tool call. Nothing is written to a pinned event without confirmation.

## Goals

1. An over-constrained day preserves owner-pinned events, names the conflict, and offers a
   focus block rather than imposing one. Threshold: **0** pinned events moved;
   **100%** of double-booked days named, across all **3** clash classes.
2. Routines are the owner's file, and a proposed routine is adopted by reading a draft.
   Threshold: **0** unadopted writes into `routines.json`.
3. Date and time handling survives timezones and phrasings. Threshold: the gate is
   `bench/check_date_robustness.py`, recorded in the registry as 12 tests across 12 clock
   cases; pass on all of them.
4. A focus block suppresses audio interruptions entirely while it runs. Threshold: **0**
   interruptions inside a block (D-29).
5. Actual-versus-planned is answerable: where the day really went, from the presence layer.
   Threshold: actuals for **100%** of elapsed work hours in a drill day.
6. Energy-aware placement is deterministic, not learned from a time series. Threshold: the
   same input always yields the same placement, with the rule named in the answer.
7. Calendar sync is two-way on **one** credential. Threshold: **1** calendar credential,
   **0** additional ones (D-62).

## Benchmarks

- **G1** · B1 · `bench/test_day_shape.py` [5]-[8] for the clash classes. Threshold: 0 pinned
  events modified, 3/3 classes named. Last: **not yet measured**. 21.F2 is `done` in the
  registry, whose only status evidence is `unverified-import`, so no dated run exists.
- **G2** · B1 · `bench/test_day_shape.py` [1]-[4] plus the draft path in
  `src/mushegh/brain/routine_draft.py`. Threshold 0 writes into `routines.json` without an
  owner adoption. Last: **not yet measured** — the floor is `done` and the file is still
  effectively empty, which is the honest state.
- **G3** · B1 · `bench/check_date_robustness.py`. Threshold 12/12 clock cases. Last: **not
  yet measured**.
- **G4** · B1 · `bench/test_proactive_suppression.py` for the block-suppression property.
  Threshold 0 audio interruptions inside a focus block. Last: **not yet measured**.
- **G5** · B2 · drill: pick yesterday, ask where the time went, compare against the
  calendar. Threshold 100% of elapsed work hours accounted for. No drill written yet
  (21.R2). Last: **not yet measured**.
- **G6** · B2 · a placement proposal and its re-run on the same input. Threshold: identical
  output twice, rule named. No drill written yet (21.R3). Last: **not yet measured**.
- **G7** · B2 · M22's own gate: CalDAV token installed, an over-constrained day preserves
  pinned events and names the conflict. Threshold: **0** pinned events moved, **3/3** clash
  classes named, **1** credential. Neither the token nor a CalDAV client exists. Last: **not
  yet measured**.
- **21.E1** · B3 · a month where every routine commitment either happened or was consciously
  renegotiated. Threshold: **30** days, **0** dropped commitments. Last: **not yet measured**.

## Failure modes

- **`routines.json` is empty or malformed.** Everything that reasons about a normal day
  falls back to defaults, silently, and a bad file is caught and replaced rather than
  reported. Diagnose: `type %USERPROFILE%\.mushegh\routines.json`, then
  `journalctl -u mushegh-brain -n 200 --no-pager | grep -i routines`.
- **The calendar read fails.** The day looks empty, and Mushegh says there is nothing today
  about a day with five meetings — the most damaging sentence this system can produce. The
  not-configured sentinel covers credentials, not a token that has expired. Diagnose:
  `journalctl -u mushegh-brain | grep -i calendar` for the error class, and the token's
  presence in `.env` without printing it.
- **A clash is missed or invented.** A false overlap costs the owner trust in the feature; a
  missed one costs the meeting. Diagnose: `sqlite3 mushegh_tasks.sqlite` for the calls and
  `bench/test_day_shape.py` for the classifier.
- **A focus block becomes a schedule.** The moment Mushegh places the owner's own work without
  being asked, it is editing his day — a defect, diagnosable in the audit lines.
- **Energy-aware scheduling becomes forecasting.** D-28 removed ML forecasting; a placement
  rule that reappears as a learned time series is that work returning under a new name.
  Diagnose: `grep -rni "holt\|arima\|prophet\|statsmodels" src/mushegh/`, which today matches
  only the prose in `src/mushegh/brain/forecast.py` declining them.

## Open questions

1. D-62 names CalDAV as a token; the code's calendar path is a Google OAuth refresh token
   shared with Gmail, and no CalDAV client exists in `src/mushegh/`. Which is the one calendar
   credential M22 installs?
2. `routines.json` is effectively empty and 21.F1 is `done`. Does the owner fill it by hand
   under D-32, or does it get seeded by adopting `src/mushegh/brain/routine_draft.py` drafts?
3. 21.R3 wants hard work placed in the hours it has historically worked. What deterministic
   rule may that use, given the pattern is exactly what D-28 stopped modelling?
