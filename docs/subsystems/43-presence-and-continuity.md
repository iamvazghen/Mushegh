# S43 — Presence & Continuity

> **One line:** the system should know which of two rooms he is in, and carry the goal —
> not the transcript — when he moves or leaves; today it knows no room at all, because
> `presence.py` polls a laptop.
> **Status:** half-built · **Registry:** S43 · 3/3 floor, 0/5 raise, 0/1 elite
> **Milestones:** M34, M35 · **Decisions:** D-37, D-38, D-40, D-39, D-61, D-63, D-69

## Purpose

Two rooms, not five. Office and living room cover 90% of practical automation value, and
five rooms is sensor maintenance for nothing (D-37). This is a decision about what will
*not* be built, and it is the reason this system is tractable: the inventory of presence
hardware is two rooms long.

Bedrooms and bathrooms are air-gapped (D-38) — permanently, no exceptions, regardless of
capability. The charter is careful that this binds at the sensor-placement layer, not the
software layer, and the distinction matters: Mushegh never simulates a room, and a room with
no hardware is a room it knows nothing about, rather than a room it has been told about.

**What the code does today, recorded by D-69.** `src/mushegh/brain/presence.py` is a **laptop
activity poller**. It asks the edge for an `activity_snapshot` — foreground app, window
title, idle minutes — and reports "you're coding in VS Code" or "idle 12 min". It does
**not** know which room the owner is in. It does not track the phone either, and says so
in its own docstring: there is no clean, sanctioned API for that, so it does not pretend
to. Any wording anywhere in this repository that described presence as "BLE plus PIR" was
describing an intention rather than the implementation. **Room presence is what the new
hardware makes possible**; until the sensors are in the house, this system's presence is a
foreground window title.

**The hardware: three Aqara FP2 mmWave sensors** (phase H3 in [../HARDWARE.md](../HARDWARE.md)
§5, gated by D-63 and D-69, tracked by `43.R5`). Two of them are presence — **office and
living**, per D-37. The third goes in the **hallway**, not a bedroom, because a bedroom is
air-gapped under D-38 and a mmWave sensor is ambient hardware. The hallway is the one room
that is *about* transitions, so a person moving toward the front door becomes visible
before they arrive; that is the cheap half of this system's "session follows the owner"
(43.R1). Each sensor clears D-63's three questions in order — local, placed, read-only —
and none of them reports to a vendor cloud.

**Two rules the sensors inherit.** Under D-61 the derived state never leaves the host, and
if a derived state is ever broadcast or logged off-host the feature is **removed, not
disabled** — the same trade the charter makes for S27. And a **missing sensor holds the last
verified state** rather than guessing: a sensor that goes quiet must not quietly become
"away", because the same occupancy object is what silences proactivity elsewhere.

Context migration carries the goal and the working context, not the raw transcript
(D-40, M34). Transcripts produce visual clutter across screen sizes, and the transcript is
the largest, least useful thing to move. Away from home means a phone client over the
tailnet, not a VPS-side stand-in pretending to be a body (D-39) — a server cannot hear
the living room, and an agent that claims to is worse than one that admits it cannot.

If it were absent, the owner re-establishes context every time he moves between rooms or
devices, and returning after a week is indistinguishable from starting over.

## Structure

| Path | Process | Role |
|---|---|---|
| `src/mushegh/brain/presence.py` | brain | The **laptop activity poller** — foreground app, window title and idle minutes, sampled through the laptop agent's `activity_snapshot`. No room, no phone, no sensor (D-69) |
| `src/mushegh/brain/perception.py` | brain | One sensing snapshot in which every fact carries its own age (26.F2, 26.F3) |
| `src/mushegh/brain/situation.py` | brain | 43.F3 — the fused per-turn view: voice, face and device activity, not any single source |
| `src/mushegh/brain/selfmodel.py` | brain | The derived state (Deep Work / Relaxing / Sleeping), which stays on the host (D-61) |
| `src/mushegh/brain/modes.py` | brain | Runtime modes — the lightweight, non-destructive protocols |
| `src/mushegh/brain/context.py` | brain | Where the migrated goal and working context are assembled, and where the transcript is deliberately left behind (D-40) |
| `src/mushegh/brain/pc_link.py`, `src/mushegh/edge/pc_agent.py` | brain + edge | The brain executing on the laptop, and the agent that answers the presence poll |
| `src/mushegh/edge/brain_client.py`, `src/mushegh/edge/offline_queue.py` | edge | The away-from-home phone client over the tailnet, and what it does when the brain is unreachable |

**Data flow.** The edge agent answers a poll; `presence.py` samples foreground and idle
state; `perception.py` assembles one snapshot with ages attached; `situation.py` fuses
the sources into a per-turn view. Derived state stays in `selfmodel.py` on the host and
suppresses audio locally — the moment it is broadcast or logged, it stops being context
and becomes surveillance (D-61). Across devices, `context.py` carries the goal and the
working set. **Nothing on that path knows which room the owner is in.** The house path
does not exist yet: when the mmWave sensors land, an occupancy reading arrives carrying
the sensor that produced it, and everything downstream gets a signal the laptop poll could
never supply.

**Planned, and absent.** `bench/test_room_presence.py` is the `43.R5` gate and **does not
exist**. Neither does any `src/mushegh/` module that reads mmWave occupancy — a search for
`mmwave` under `src/mushegh/` returns nothing. The sensors are hardware, and every occupancy
claim in this document is a design, not a behaviour.

**The honest gap.** Presence fusion exists; migration does not. 43.R1 is open and depends
on the S07/S12 context work, 43.R2, 43.R3, 43.R4 and 43.R5 are open, and 43.R5 is the one
that says plainly what "presence" is today. On the registry's own record this system has no
completed raise task.

**A correction to the briefing, recorded deliberately.** No S43 task is cancelled or
deferred. The cancellations applied to the registry cover S15, S24, S30, S40, S46, S47
and S49, and the deferrals cover S26, S32 and S34; S43 appears in neither list, and the
registry shows all five raise tasks as `open`. So the honest state is "unbuilt", not
"cancelled" — 43.R1 waits on M34, 43.R4 is the one that must not become a second daemon
under D-42, and 43.R5 is the one that replaces a poll with a fact.

## Goals

1. Presence is a fused signal — voice, face and device activity — and no claim rests on
   a single source (43.F3).
2. Departure and return are symmetric, and a return gets a "while you were gone" only
   when there is something worth interrupting for (43.F2).
3. Two rooms: office and living room, and no backlog item to make it five (D-37, M35).
   The third sensor is a hallway transition sensor, not a third room of presence.
4. Bedrooms and bathrooms carry no ambient hardware at all (D-38) — checked as a device
   count, because a constraint nobody counts gets eroded by one well-meaning addition.
5. The active goal and working context migrate across devices; the raw transcript does
   not (D-40, M34, 43.R1).
6. A derived state is never broadcast off-host and never written to a timeline (D-61).
   If one ever is, the feature is removed, not disabled.
7. A week away is not resumed as if it were ten minutes (43.R3).
8. Room presence is a house fact: occupancy is reported per room, the sensor that
   produced it is named, and a bedroom or bathroom sensor is refused at configuration
   time (43.R5, D-69). A missing sensor holds the last verified state and says so.

## Benchmarks

| Goal | Tier | Command or drill | Threshold | Last measurement |
|---|---|---|---|---|
| 1 | B1 | `uv run python bench/test_perception_snapshot.py` [presence fusion] | every presence claim rests on ≥2 agreeing sources; 0 single-source claims | registry records 43.F3 done; run not reproduced here — not yet measured |
| 2 | B1 | `uv run python bench/test_presence_arrival.py` [7] | a return with nothing pending produces no summary; 0 empty digests | registry records 43.F2 done; run not reproduced here — not yet measured |
| 3 | B2 | M35 drill: walk the house, then count the instrumented rooms in the roster | office and living room detected; 0 further rooms instrumented | not yet measured |
| 4 | B4 | count ambient devices per room from the roster the presence layer keeps | bedroom 0, bathroom 0, permanently; 0 exceptions | not yet measured — nothing enforces this in code today, it is a placement rule |
| 5 | B2 | M34 drill: start a task on the phone, finish it at the desk | the active goal and working context are present at the desk; **0 transcript turns** present | not yet measured (43.R1 open, M34 open, blocked on S07/S12) |
| 6 | B4 | `grep -rniE 'broadcast\|publish\|send' src/mushegh/brain/selfmodel.py src/mushegh/brain/situation.py` | 0 sends; a derived state is never written to a timeline or a log the owner did not ask for | not yet measured |
| 7 | B1 | `uv run python bench/test_presence.py` [long absence] | after a simulated week, the resume is a cold-context summary; 0 "as I was saying" continuations | not yet measured (43.R3 open) |
| 8 | B1 planned | `uv run python bench/test_room_presence.py` — the `43.R5` gate, **the file does not exist** | occupancy reported per room with the producing sensor named; 0 bedroom or bathroom sensors accepted at configuration; a missing sensor holds the last verified state and guesses 0 times | not yet measured — no sensor is in the house and nothing in `src/mushegh/` reads occupancy |

Goal 4 is a B4 because it is a placement invariant rather than a behaviour: no amount of
software correctness substitutes for the sensor not being in the room. Goal 5's threshold
is deliberately a zero on the transcript, not a bound on it. Goal 8 is a B1 rather than a
B4 because `43.R5`'s gate puts the bedroom refusal in the configuration, not in a review —
but it is *planned*, and the number of rooms a room-presence claim can currently name is
one: whichever room the laptop is in, which is not a room the system knows.

## Failure modes

**A sensor appears in the bedroom.** Someone mounts one "because the hardware was
already there". D-38 has no exception clause, and this is the failure in this system that
is hardest to notice and hardest to undo — a household's trust, once spent on a bedroom
microphone, does not come back when the device is removed. Diagnose: the room list in
`src/mushegh/brain/presence.py` and the device roster, then the vendor accounts for anything
not in it.

**The laptop poll is read as presence.** The most likely failure of the next month, because
it needs no mistake: a summary says "you're in the living room" and the truth is that a
window title was in the foreground. Nothing in the code can produce a wrong room claim
today — it produces no room claim at all — so the risk is entirely in the *prose* and in
the owner's expectation. Diagnose: `journalctl -u openmushegh-brain -n 200 | grep -i
activity_snapshot`; if that is what answered, the room was inferred, not read (D-69).

**A sensor drops and the house reads empty.** The hallway sensor loses power, the room
falls to `unknown`, and if the last state is treated as "away" the system goes silent for
a man sitting in the office. This is why 43.R5's gate is explicit that a missing sensor
**holds the last verified state** rather than guessing. Diagnose: the occupancy rows and
their ages, the same way a stale perception is caught today.

**The transcript migrates.** Someone "fixes" the missing context by shipping the history
across, and the desk opens to a wall of text at the wrong screen size. That is D-40
violated in the name of a good intention, and the goal was never the transcript. Diagnose:
`uv run python bench/test_session_identity.py` [migration], then the size of what crossed.

**The server pretends to be a body.** Away from home, the system narrates the living room
from stale state, as though it were there. D-39 rules this out: the phone is the body and
there is no fallback. Diagnose: `journalctl -u openmushegh-brain -n 200 | grep -i presence`,
then the connected device ids — if the laptop is absent, the presence claims are
rehearsals.

**Presence flaps.** Two sources disagree and the room oscillates, so every
context-sensitive behaviour flickers with it — attention suppression, greeting, lighting.
Diagnose: `journalctl -u openmushegh-brain -n 200 | grep -i presence`, then the sample ages
in the perception snapshot, which exist precisely so a stale reading is visible as stale.

**A long absence is resumed as a short one.** The owner returns after a week and the
system continues a thread from Tuesday as though it were live. Diagnose: the departure
timestamp against the last interaction, then the resume record.

## Open questions

1. 43.R4 proposes a live presence key in the brain's own memory, pushed over the existing
   WebSocket. Is that S43's work or S12's transport? D-42 says a new system needs an
   independent daemon or a distinct security boundary, and 43.R4's own note is that it
   needs neither — which is the argument for it existing at all.
2. Is a week away resumed as a cold context with the goal offered, or as a fresh session?
   43.R3 asks the question without answering it, and the two answers produce very
   different first turns.
3. What happens to the laptop activity poll once the mmWave sensors are answering? It is
   a good signal for screen time and a bad one for presence, and the honest options are
   to keep both, labelled by source, or to retire the poll. `43.R5` is written as a
   *replacement* for presence specifically; retiring the foreground-window data is a
   separate decision nobody has recorded.
