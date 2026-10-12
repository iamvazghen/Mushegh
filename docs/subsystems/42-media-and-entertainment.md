# S42 — Media & Entertainment Control

> **One line:** one answer to "what is playing", a stop that reaches whichever path holds
> it, and a memory of what came before.
> **Status:** built, not well structured; a cloud-free vacuum is planned, not integrated · **Registry:** S42 · 3/3 floor, 0/3 raise, 0/1 elite
> **Milestones:** none assigned · **Decisions:** D-06, D-29, D-18, D-32, D-63

## Purpose

The routing is the part that works, and it is not trivial. Audio leaves Mushegh by two
unrelated routes — a local player process reached over the PC link, and the music room —
so "stop" is a genuinely hard command that has to reach whichever one is actually
holding the device. That is 42.F1, and it exists.

The practical gap is queue and history. "Play that again", "skip", "what was the last
one" are three sentences the owner will actually say, and none of them has an
implementation. That is 42.R1, and its gate is a test that does not exist yet.

Volume ducking during speech does not exist. 42.R2 is open, and a grep for `duck` and
`attenuat` across `src/mushegh/` returns zero matches: nothing attenuates a playback route
when the owner speaks, and nothing restores a level afterwards. It is ordinary open work
in this system, not a consequence of the audio path, and it is listed here so it gets
scheduled instead of assumed. The media behaviour that *is* real is a full stop rather
than a level change — `src/mushegh/brain/interventions.py` calls `media_pause` when a
conflict signal fires, which is triggered by a calendar clash, not by speech.

An autonomous device is also arriving. A **Valetudo-compatible robot vacuum** — a Dreame
or a rooted Roborock — is on the list precisely because Valetudo keeps it **cloud-free**,
and that is the only reason an autonomous device belongs in this house at all: a vacuum
that has to phone a vendor to be told where to clean is not integrated, it is owned
(D-63). It is a new actuator, not an audio feature, so it changes nothing above — there is
still no ducking, 42.R2 is still open with a planned gate, and the vacuum does not make
that gap any smaller.

The rule that makes it safe is **scheduling, not confirmation**. It runs when the house is
empty, never inside a scheduled focus block, and never at night under D-32's quiet hours.
An autonomous device that interrupts a meeting is a worse failure than one that misses a
room, and D-29's budget counts its noise as well as its speech.

There is no discovery here. Mushegh does not choose what to play because it seemed right
(D-27, D-34), and nothing in this system may interrupt the owner unprompted — a track
change is not an interruption, but an announcement about one would be.

If it were absent, the owner uses the media application directly, and the only regression
is that Mushegh can no longer be asked to turn something off.

## Structure

| Path | Process | Role |
|---|---|---|
| `src/mushegh/brain/playback.py` | brain | 42.F2 — the single owner of "is something playing, and where", spanning both unrelated audio routes |
| `src/mushegh/brain/tools/localplay.py` | brain | Local playback that actually produces sound out loud, not a delivered notification |
| `src/mushegh/brain/tools/music.py` | brain | Music playback from free, music-tuned sources, in order of preference |
| `src/mushegh/brain/tools/channels.py` | brain | Channel operations — list, pick, open |
| `src/mushegh/brain/tools/audioout.py` | brain | Output switching: "switch to my headphones" |
| `src/mushegh/edge/switch_audio.py` | edge | The output switch the brain registers, on the laptop side |
| `src/mushegh/brain/voice_io.py` | brain | The speech path whose output is what ducking has to coexist with |
| `src/mushegh/brain/delivery.py` | brain | What actually happened to a play request, per path (13.F3) |

**Data flow.** A play request is resolved to a path, handed to that path, and the
resulting state is written back to the single owner in `playback.py`. Every subsequent
command — stop, pause, "what is playing" — is answered from that owner rather than by
asking each path, which is what makes 42.F2 a real guarantee and not a convention. No
speech-triggered attenuation happens on either path today: the media routes are told
nothing about the speech output's level, and the pause in `interventions.py` is the only
thing that reaches them.

**The honest gap.** There is no history. `playback.py` knows what is playing now and
where; it does not know what came before, so "play that again" has nothing to be again.
The planned `bench/test_media_queue.py` is the gate for 42.R1 and 42.R2 and does not
exist. A second gap is structural rather than missing: the two paths are separate
processes, so any queue that lives only in the brain is wrong for the path that does not
ask it.

**What is not here yet.** The vacuum has no path in the table above. Valetudo runs the
cleaning on the device itself; a room-specific routine would be a schedule plus a start
command from a system that already knows what the house is doing, and neither exists. Its
one scheduling input — "the house is empty" — is today a laptop activity poller rather
than a house fact, so the safe default until room presence lands is that the routine does
not run at all.

### Proposed addition — a vacuum that is not a new daemon (D-93)

**[Hypfer/Valetudo](https://github.com/Hypfer/Valetudo)** (Apache-2.0, 9.8k★,
pushed 2026-09-25) — subprocess adapter over its HTTP API.

**Why this one survives D-42 when a music server would not.** Valetudo is
firmware that runs **on the vacuum**, not a service Mushegh would own and operate.
It is the rare dependency that adds a capability without adding a thing to be
down at 2 AM.

**It is the strongest un-darkening candidate in this subsystem.** A cloud-free
vacuum is planned, not integrated, and the household-cleaning routine has a date
and no actuator behind it.

**What stays in-repo, and why.** Queue and history, and volume ducking during
speech, remain handlers in `src/mushegh/brain/tools/music.py` and
`src/mushegh/brain/tools/localplay.py`. This document's own open question 1 is right
that a brain-side queue is the wrong shape for the path that never asks it — a
vacuum cleaned on a schedule, not queued by speech.

**Gate:** the planned `bench/test_media_queue.py`, which does not exist yet. One
confirmation pass against valetudo.cloud is required **before** an adapter is
written, because the API surface is not read in this review. PRINCIPLES §1 three
commands, in order:

```
curl -s http://<vacuum-host>/api/v1/status | jq
journalctl -u valetudo -n 100
journalctl -u openmushegh-brain -n 100 | grep -i vacuum
```

**Not proposed:** mopidy, which is the obvious answer for the music side and is
a *server* — a new daemon under systemd, refused by D-42 and §1. S42's routing
already works without one.

See [INTEGRATIONS.md](../INTEGRATIONS.md) §2 and §6.

## Goals

1. Stop reaches whichever path is playing, local or music room, and leaves the other
   alone (42.F1).
2. Exactly one owner answers "what is playing", and the answer names the path (42.F2).
3. Volume and mute mean the same thing on every path, including after a device switch
   (42.F3).
4. Queue and history exist, so "play that again", "skip" and "what was the last one" all
   have answers (42.R1) — the real gap in this system.
5. Playback ducks under speech and restores afterwards (42.R2) — open work owned here, not
   a behaviour inherited from the audio path, and unimplemented today.
6. A play request that was accepted actually produced sound; delivery is reported rather
   than assumed.
7. The media handlers survive the 60-day cull or are deleted — they do not sit dark
   (D-06).
8. **Room-specific routines on a cloud-free vacuum**, started by schedule rather than by
   request, never inside a focus block and never after dark (D-32). For this one actuator
   the boundary is *when it runs*, not whether to ask: a cleaning robot does not need a
   confirmation, it needs a time it is allowed to start.

## Benchmarks

| Goal | Tier | Command or drill | Threshold | Last measurement |
|---|---|---|---|---|
| 1 | B1 | `uv run python bench/test_localplay_routing.py` | a stop on the active path ends playback; 0 orphans; the idle path is untouched | registry records 42.F1 done; run not reproduced here — not yet measured |
| 2 | B1 | `uv run python bench/test_localplay_routing.py` [7] | exactly one owner answers, naming the path; 0 conflicting states between paths | registry records 42.F2 done; run not reproduced here — not yet measured |
| 3 | B1 | `uv run python bench/test_audio_output_switch.py` [7] | volume and mute are one concept across paths, including after a switch; 0 divergent semantics | registry records 42.F3 done; run not reproduced here — not yet measured |
| 4 | B1 | new `bench/test_media_queue.py` (planned, 42.R1 — does not exist yet) | "play that again" returns the previous item; "what was the last one" names it; history survives a restart; 0 wrong items | not yet measured |
| 5 | B1 | new `bench/test_media_queue.py` [ducking] (planned, 42.R2 — does not exist yet) | speech attenuates the media path within its budget, and the previous level is restored after; 0 stuck-at-muted | not yet measured — 42.R2 open, 0 matches for `duck`/`attenuat` in `src/mushegh/`; the conflict-driven `media_pause` is a separate behaviour and does not satisfy this row |
| 6 | B1 | `uv run python bench/test_localplay_routing.py` [delivery] | an accepted play request reports played or failed; 0 accepted-but-silent results | not yet measured |
| 7 | B4 | per-handler call counts from `src/mushegh/brain/tool_usage.py` for the media handlers | each media handler is either used within 60 days or deleted; 0 dark handlers | not yet measured — durable counts exist, the 60-day cull has not been run |
| 8 | B1 | new `bench/test_vacuum_schedule.py` (planned, room-specific routines — does not exist yet) | a room routine starts only outside a focus block and outside quiet hours; 0 vendor-cloud calls on any path; 0 starts while the house is occupied | not yet measured — no vacuum is installed |

Goal 5 states no budget because none exists: nothing in the audio path attenuates a
playback route today, so quoting an attenuation level or a restore window here would be
inventing a figure this system does not have.

## Failure modes

**Nothing is playing and something is.** The owner says stop and hears silence, because
the state owner and the actual process disagree — the characteristic failure of two audio
routes that were never one system. Diagnose:
`uv run python bench/test_localplay_routing.py`, then
`journalctl -u openmushegh-brain -n 100 | grep -i play` for the path the owner last touched.

**Two paths fight over the output.** Both hold the device and neither yields, so the owner
hears Mushegh and the music at once, or neither. A conflict signal's `media_pause` is the
only thing that reaches a route today; attenuation, which would be the gentler answer, is
42.R2 and does not exist. Diagnose:
`journalctl -u openmushegh-brain -n 100 | grep -i audio`, then the resolved endpoint that
`src/mushegh/edge/device_profile.py` classified.

**A play request is accepted and nothing happens.** The request is treated as delivered
because the call returned, and the owner is left waiting for a sound that was never
produced. Diagnose: the delivery record rather than the request, since the request
succeeding proves nothing.

**The handlers go dark.** The belt is 153 schemas heading to 90–100 (D-06), and a media
handler unused for 60 days is a deletion candidate. Deletion is a valid outcome here, not
a failure; leaving it dark is the failure. Diagnose: the durable counts in
`src/mushegh/brain/tool_usage.py`, then the catalogue.

**"Play that again" returns the wrong thing.** Adjacent rather than actual, the owner
corrects it once and then stops asking. 42.R1 is open, so this is a known-open state
rather than a regression — recorded here so it is not mistaken for a bug in the
retrieval.

**The vacuum runs while the owner is working.** The safety argument for this device is
scheduling, so a routine that fires inside a focus block or after dark loses the whole
premise — it is the one failure here with no confirmation standing behind it, and it is
also the quietest, because a robot on carpet is easy to talk over. Check the schedule
rather than the device. The mirror-image failure is a routine that never runs at all
because "the house is empty" is still inferred from a laptop poll; missing a room is the
better of the two.

## Open questions

1. Where does queue and history live — in the brain's store, or beside each playback
   process? The two paths are unrelated processes, so a single brain-side queue would be
   wrong for whichever path does not consult it.
2. Is "play that again" the previous *item* or the previous *request*? A request may have
   been an album, a channel or a search, and the two readings give different answers.
3. Is ducking the right shape for goal 5 — a level change the audio path drives, or a
   pause the media path takes itself? Nothing attenuates today, so the question is still
   open, and answering it in one place is how a capability avoids being owned by nobody.
