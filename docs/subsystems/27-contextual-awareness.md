# S27 — Contextual Awareness

> **One line:** One frozen picture of where the owner is and what they are doing for each turn, disclosed when it changes the answer — and never leaving the host.
> **Status:** built, not well structured · **Registry:** S27 · 2/2 floor, 0/3 raise, 0/1 elite
> **Milestones:** M35, M38 · **Decisions:** D-37, D-38, D-61, D-63, D-69

## Purpose

Four sources already answered "where is he and what is he doing" — presence, modes, the
activity tool, the maps tool — and nothing assembled them. Each caller reached for whichever
source it knew, so two halves of one turn could disagree: the answer assuming he is at the
desk while proactivity assumes he has gone (27.F1). This system builds the one object, freezes
it for the turn, and states the assumed context when that context changed the answer
(27.F2).

It also carries the narrowest boundary in the project. Context inference — Deep Work,
Relaxing, Sleeping — is welcome **only because it never leaves the host**, where it
suppresses audio notifications. The moment a derived state is broadcast, logged to a
timeline, or sent anywhere, the same feature becomes surveillance and is removed, not
disabled (D-61). Location is four values — home, desk, away, travelling — across two rooms
only, office and living room, because five rooms is sensor maintenance for nothing (D-37).
A missing sensor holds the last verified state and says so. It does not guess: a guess here
does not merely mislabel a place, it silences or unsilences the whole system, because
proactivity reads the same object.

**Two new inputs, both local reads** (phase H3 in
[../HARDWARE.md](../HARDWARE.md) §5, gated by D-63). An **AirGradient ONE** in the living
room reports CO₂, TVOCs and particulate matter over a **local REST API** — a read, it
never leaves the house, and it is the input the Levoit purifier automates on in H4, which
makes it an S28 sensor before it is a context field. And **three Aqara FP2 mmWave sensors**
give this object room-level context it does not have today: office and living for
presence, hallway for transitions (D-37, D-69, tracked by `43.R5`). The location model
does not move — it stays **home / desk / away / travelling**, with two rooms of real
presence behind it rather than a foreground window title. Both sensors inherit the rules
above: a derived state is welcome only because it never leaves the host, and a missing
sensor holds the last verified state rather than guessing.

**What exists today, stated exactly.** `Situation` carries `place`, `place_source`, `app`,
`in_meeting`, `focus`, `guest`, `lockdown`, `commute`, `part_of_day`, `local_hour` and a
timestamp. The time-of-day buckets are four — morning, afternoon, evening, night. **Deep
Work / Relaxing / Sleeping are not fields in the object**; they are what 27.R2's availability
inference would add, and D-61 decides whether they may be added at all. Read this as a
boundary that has to hold, not a feature that runs. If it is absent, half the system acts on
a different picture of the room from the other half, unreconstructable afterwards.

## Structure

| Path | Role |
|---|---|
| `src/mushegh/brain/situation.py` | `Situation`, `assemble()`, `disclosure()`, `part_of_day()`, `_fuse_place()` |
| `src/mushegh/brain/presence.py` | The **laptop activity poller**: foreground window, idle time, meeting detection. No room and no phone (D-69) — the two-room model arrives with the mmWave sensors |
| `src/mushegh/brain/perception.py` | S26's stamped facts, one input to the fusion |
| `src/mushegh/brain/modes.py` | `focus` / `guest` / `lockdown` / `commute` — behavioural modes, flipped on request |
| `src/mushegh/brain/tools/activity.py`, `tools/maps.py` | Foreground app and place, the remaining two sources |
| `src/mushegh/brain/proactive.py`, `proactive_signals.py` | The consumer that decides whether to speak |
| `src/mushegh/brain/hud.py`, `src/mushegh/brain/turn_trace.py` | Where the assumed context is shown and recorded |

Process: brain, per turn, in the prompt assembly path, before the LLM call. Frozen
deliberately — "a turn's context must not drift under it half-way through, or the
disclosure would describe something that no longer held."

**State.** The situation is per-turn and in-process: not written to a timeline, not sent to
the HUD as a state, not included in any outbound message. That is not an accident of the
current implementation; it is the condition under which 27.R2 is allowed to exist, and
M38's gate checks the audit log for the absence of a broadcast. Place fusion takes every
source with an opinion, never one alone, and records `place_source` so a claim can be
attributed; a gap longer than the poll interval means the poller was not running, and is
treated as unknown rather than as "away".

**Planned, and absent.** Neither new input is integrated. A search for `airgradient`
under `src/mushegh/` returns nothing, and no module here reads a local air-quality REST
endpoint or an mmWave occupancy feed. The AirGradient is a planned read whose obvious
first consumer is S28's purifier automation rather than `Situation`; whether CO₂ is
context at all or purely a sensor is exactly the undecided question, and this document
records the read without inventing the field. `bench/test_room_presence.py`, the `43.R5`
gate covering the room-level half, **does not exist**.

## Goals

1. One context object per turn, frozen, and disclosed when it changes the answer.
   Threshold: **0** turns where an answer used a context the disclosure did not name;
   **0** mid-turn drift.
2. Location is home, desk, away or travelling, and every claim names its source. Threshold:
   **100%** of place claims carry `place_source`.
3. Two rooms: office and living room. Threshold: **0** sensing surfaces in a third room,
   **0** in the bedroom or the bathroom (D-37, D-38).
4. Derived state never leaves the host. Threshold: **0** broadcasts, **0** timeline rows,
   **0** outbound messages carrying one — checked against the audit log, not asserted
   (D-61, M38).
5. A missing sensor holds the last verified state. Threshold: **0** guesses; a stale place
   is labelled stale.
6. Availability inference drives suppression, not speech. Threshold: **0** audio
   interruptions inside a derived focus state (D-29).
7. Context history answers "what was I doing when X happened". Threshold: answerable for
   **≥95%** of X within the retention window.
8. Indoor air quality is context where it changes the answer: CO₂, TVOC and particulate
   readings come from a local read that never leaves the house. Threshold: **0** readings
   that reach a vendor, and every reading carries the room and the age it came from.
   Not yet measured — the AirGradient is not integrated.

## Benchmarks

- **G1** · B1 · `bench/test_context_object.py` — the registry records 35 cases with no
  date. Threshold 0 mid-turn drift, 0 undisclosed contexts. Last: **not yet measured**.
  27.F1 and 27.F2 are `done`; the status evidence is `unverified-import`.
- **G2** · B1 · `bench/test_presence_arrival.py` extended with the source-naming case.
  Threshold 100% of place claims carry a source. Last: **not yet measured**.
- **G3** · B2 · M35's drill: a room walk plus a written device list, two rooms only.
  Threshold 0 devices outside office and living room; no such list exists. Last: **not yet
  measured**.
- **G4** · B4 · M38's own gate: grep the audit log for any derived state leaving the host.
  Threshold 0 occurrences over a full day of real turns. Last: **not yet measured**. This
  is a live check, not a hermetic test.
- **G5** · B1 · `bench/test_context_object.py` [history] is the named gate for 27.R3, but
  the case is not written. Threshold 0 guesses on a missing-sensor drill. Last: **not yet
  measured**.
- **G6** · B1 · `bench/test_proactive_suppression.py` [availability]. Threshold 0 audio
  interruptions inside a derived focus state. Last: **not yet measured**.
- **G7** · B3 · "what was I doing when X happened" answerable. Threshold: **≥95%** of X
  inside D-21's 30-day window. Last: **not yet measured**.
- **27.E1** · B3 · a day in which no interruption lands at a wrong moment and no answer
  assumes the wrong context. Threshold: **0** mis-timed interruptions, **0** wrong-context
  answers — a log review, not a test. Last: **not yet measured**.
- **G8** · B1 planned · the AirGradient read: CO₂, TVOC and PM2.5 from the local REST API,
  with the room and the sample age attached. Threshold: 0 readings that leave the house, 0
  readings presented without an age. No ingest module and no gate file exist for this yet;
  the sensor is not in the house. Last: **not yet measured**.
- **G9** · B1 planned · `bench/test_room_presence.py` (the `43.R5` gate) — **the file does
  not exist**. Threshold: the room a place claim names is backed by a named sensor, and a
  missing sensor yields a stale place rather than a guess. Last: **not yet measured**.

## Failure modes

- **Two halves of a turn disagree.** The answer assumes the desk, proactivity assumes away.
  The honest test of the fix is a log review, and nothing asserts the age of a stale place.
  Diagnose: `journalctl -u mushegh-brain | grep -i situation` and the trace row in
  `src/mushegh/brain/turn_trace.py`.
- **A sensor goes quiet and the system infers "away".** Everything then goes silent for a
  laptop that is merely asleep. Diagnose: `sqlite3 mushegh_presence.sqlite` (the path
  `store_path("presence")` resolves) for the last poll, and the poll-gap guard.
- **A derived state leaks** into an audit row, a HUD frame, or a push. Under D-61 that is
  not a bug to fix but a feature to remove: the action is deleting the inference, not
  sanitising the output. Diagnose: the audit log for a state field where no owner-set mode
  appears.
- **Context history becomes a surveillance timeline.** 27.R3 wants a history and D-61
  forbids a timeline of derived states. They are compatible only if the history records what
  the owner did and the modes they set, never what the system inferred. Diagnose: read the
  history schema before the first row is written.
- **Granularity creeps.** A third room appears because a sensor was cheap; D-37 makes rooms
  a decision, not a budget line. Diagnose: the device list, which does not exist yet.
- **A stale air reading becomes a decision.** The AirGradient is a read with a sample age,
  and a CO₂ number from two hours ago is a number without meaning. If the purifier
  automates on it — which is the H4 plan — a stale reading is an actuator firing on a
  fiction, and unlike a wrong place claim it moves something in the room. Diagnose: the
  age on the reading next to the automation that consumed it (D-63, D-61).

## Open questions

1. Deep Work / Relaxing / Sleeping are not fields in `Situation` today — the time-of-day
   buckets are four. When 27.R2 adds them, which surface must be forbidden from reading them
   for D-61 to stay true rather than merely intended?
2. The object is frozen per turn, so a long turn answers with a context that has aged. Is
   re-assembly at the end of a turn allowed, and does the disclosure get corrected or does
   the answer stand on the context it was generated from?
3. 27.R3 wants a context history and D-61 forbids a timeline of derived states. Is a
   history of the owner's own actions and self-set modes a different artefact, or is this a
   contradiction waiting for whoever writes the schema?
