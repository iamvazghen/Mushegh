# S26 — Multi-Modal Perception

> **One line:** The eyes and ears, producing stamped facts about the room and the screen — and nothing that decides what those facts mean.
> **Status:** the seam is built and gated, the hardware is not — mock-only evidence, no detector and no camera · **Registry:** S26 · 3/3 floor, 0/5 raise, 0/1 elite
> **Milestones:** none in [../ROADMAP.md](../ROADMAP.md) · **Decisions:** D-38, D-51, D-61, D-63, D-66

## Purpose

Turn sensors into facts, and keep the fact honest about its own age. `perceive()` returns
presence, visual and activity together, and every element carries a freshness stamp, so a
check from ninety seconds ago cannot be quoted as though it were from two (26.F2, 26.F3).
The division with S27 is in the module: **S26 never decides what a state means; S27 never
touches a camera.**

**The owner's position on this system is that it is probably broken, and the dashboard
disagrees.** `docs/EVIDENCE.md` lists S26 first under "What still owes evidence" — suspected
broken, B1-only evidence. A green `bench/test_perception_snapshot.py` proves the code agrees
with its fake transport, the standing definition of not evidence (D-43). Until a real camera
and a real frame have been through this path, the status string reports what is recorded.

The scope is deliberately narrow and the boundaries are physical, not software. Bedrooms
and bathrooms are air-gapped: permanently off-limits to ambient recording hardware, no
exceptions, regardless of capability, and that constrains this system at the sensor-placement
layer (D-38). The user is one person; guests, family and strangers are out of scope, because
the moment they are in scope ambient mics and room presence become social-surveillance
liabilities (D-51).

**The hardware raises the stakes and imposes a hard constraint** (H6,
[../HARDWARE.md](../HARDWARE.md) §7). Three **Reolink PoE cameras plus a video doorbell**
feed local RTSP into **Frigate** on the Proxmox mini-PC, with a **Google Coral USB
accelerator** in that Mini-PC doing the object and motion work so the detector is not
competing with Whisper and Piper for the same cores. Retention is a **local NAS, 2×4 TB
RAID 1**. That is the shape D-63 asks of hardware: local, placed, read.

And then the constraint that decides this system:

> Detections stay local. **No video frame leaves the house** — never to a vision model,
> never to a logger, never to a crash report. Only event metadata (zone, label, count,
> timestamp) may cross to the brain. (D-66)

This is load-bearing rather than decorative, because the vision chain configured in
`src/afon/config.py` is **cloud-only**: `vision_models` is MiniMax first and Gemini
second, both remote. A frame that reaches that chain has left the house, which makes the
concrete rule this: **`see()` in `src/afon/brain/tools/camera.py` must not become the
detector's output channel by accident.** That is the path that exists today for "what am
I looking at", it is the one path a well-meaning Frigate integration would naturally be
wired into, and it is the single most likely way this hardware plan leaks a frame. The
cloud chain stays for screenshots the owner explicitly asks about, and for nothing else.
`26.R5` tracks it.

**Two practical points the cameras force into the open.** RTSP is local only if the camera
is *configured* that way — Reolink ships with the vendor cloud enabled, so the gate is a
camera with the vendor account disconnected, proven by pulling a stream with the WAN cable
out; a "local" stream that still authenticates against a vendor is not local. And **the
doorbell's two-way audio is a microphone at the front door**, so it needs the same
placement answer as a room satellite under D-38: the owner should know that answering the
doorbell is the one interaction in this house where a guest's voice is captured.

**The guest question, recorded honestly.** Three indoor cameras plus presence sensors plus
a doorbell is the *hardware form* of D-51's single-user assumption: the moment a guest is
recorded, the one-person model stops being a policy and becomes an accident. The plan's
answer is the charter's own — cameras cover the **entry, the garden and the outbuilding**,
and rooms where a guest would be recorded are covered by **presence, not video** (the
mmWave sensors, tracked by `43.R5`). If the owner ever disagrees with that, the honest
move is to **change D-51 in writing**, not to quietly widen the camera list.

Two raise tasks are **deferred as speculative and surveillance-adjacent**
([../REGISTRY-RECONCILIATION.md](../REGISTRY-RECONCILIATION.md) §C): 26.R2 screen
understanding and 26.R3 anomaly detection, something unusual in the room being *noticed*.
Neither is cancelled; neither should consume the 8–10 hours a week before the dark systems
are settled (D-46). What survives is 26.R1: audio scene classification, feeding the speaker
gate. Without this system the assistant is blind, which is an acceptable way to be. What is
not acceptable is a camera path that looks alive and has never seen a frame.

## Structure

The eye is at the desk, not in the brain; the brain assembles what arrives.

| Path | Role |
|---|---|
| `src/afon/brain/detector.py` | 26.R5 — the detector's output channel. `accept()` is the only door a detection comes through, and it admits zone, label, count, timestamp and nothing else (D-66) |
| `src/afon/shared/redact.py` | The frame-side redaction rule, shared by the error journal, the audit trail and the detector ingress. A frame is not a secret, so no credential scrubber can see one |
| `src/afon/brain/perception.py` | `Fact`, `Perception`, `record_voice()`, `record_visual()`, `reset_visual()`, `perceive()` |
| `src/afon/brain/tools/camera.py` | `look_around` — grab a frame, hand it to a vision model, answer a question about it (26.F1) |
| `src/afon/brain/tools/multimodal.py` | Laptop screenshot plus OCR, for "what is on my screen" |
| `src/afon/edge/pc_agent.py` | The laptop-side executor that actually reaches the camera and the display |
| `src/afon/edge/stt.py`, `wake_word.py`, `vad_bargein.py` | The audio side the scene classifier would consume |
| `src/afon/edge/audio_devices.py`, `audio_watchdog.py`, `device_profile.py` | Which device, is it healthy, may barge-in fire here |
| `src/afon/edge/speaker_gate.py`, `speaker_id.py` | The gate that 26.R1 exists to feed |
| `src/afon/config.py` | The vision chain — `vision_models` is MiniMax then Gemini, both cloud, so any frame that reaches it has left the house (D-66) |

Flow: an on-demand turn asks a question; the pc_agent op grabs a frame or a screenshot; the
fact is recorded with a timestamp; `perceive()` returns it beside the presence and activity
facts; a caller states the age. Nothing is persisted — raw sensor feeds are never stored, not
even with a retention period (D-24). There is no camera in a bedroom or a bathroom, by
decision, and no code path that would want one. There is one subject: the owner.

**The seam is now real; the hardware is not.** `26.R5` built the boundary that a detector's output
must pass and gated it (`bench/test_no_frame_egress.py`, 53/53 on 2026-10-04). What that means is
narrow and worth stating precisely, because the difference is the whole point of the rule:
`src/afon/brain/detector.py` is the **only** function in the repository that turns a detector result
into something the brain holds, and it refuses any payload with a key outside
`{zone, label, count, at, camera}` and any value that looks like frame bytes, a data URI, an image
path or a bare base64 blob. Values are checked as well as keys, because `{"label": "data:image/jpeg;
base64,…"}` is schema-valid and is still a frame.

Two findings from writing that gate are worth more than the feature:

* **A frame was reaching the crash report, through no deliberate act at all.**
  `LLMClient.see` puts the JPEG into a data URI, an SDK error quotes the request it failed on, and
  the error journal's 600-character message clip wrote the first 600 characters of that image to
  `errors.jsonl` beside the stack trace. The credential scrubber could never have caught it —
  base64 is not a credential and `b64` is not a password. `src/afon/shared/redact.py` is that rule,
  shared by the error journal, the audit trail and the detector ingress, and it says `<withheld>`
  rather than `<redacted>`: one means a secret leaked, the other means the value was never ours to
  write.
* **The `see()` question is answered by a runtime tripwire, not by an import check.** `LLMClient.see`,
  `look_around` and the camera capture op are replaced with functions that record a call and raise,
  and the whole accept-and-publish path is run; none of them fires. An import check would have been
  defeated by a lazy import inside a branch this particular test did not take.

What is still **not** claimed: there is no detector. A search for `frigate`, `reolink` or `coral`
under `src/afon/` returns nothing, there is no RTSP client, no accelerator and no camera, and the
gate asserts all of that in its own final section so it cannot be forgotten. "The detector still
works" remains an untested claim about hardware nobody has connected, and the H6 plan in
[../HARDWARE.md](../HARDWARE.md) §7 is still a plan.

## Goals

1. One snapshot returns presence, visual and activity together. Threshold: **0** callers
   that read a raw fact instead of the snapshot.
2. No fact can pretend to be newer than it is. Threshold: **0** facts without a freshness
   stamp; a stale fact is always labelled stale.
3. An on-demand question about what the owner is looking at is answered from a real frame.
   Threshold: **≥90%** correct across a mixed set (26.E1).
4. Bedrooms and bathrooms carry no ambient sensing hardware. Threshold: **0** sensing
   surfaces in those rooms — a placement property, verified by a room walk, not a test.
5. One person is in scope. Threshold: **0** identities, profiles or enrolments beyond the
   owner.
6. Media audio is not the owner's speech. Threshold: **0** television or film audio
   accepted as an owner turn.
7. Screen understanding and anomaly detection stay deferred. Threshold: **0** work started
   on 26.R2 or 26.R3, with the deferral on the record in §C.
8. No video frame leaves the house, and only event metadata — zone, label, count,
   timestamp — reaches the brain. Threshold: **0** frames to a remote model, a log or a
   crash report; with egress blocked the detector still produces events (D-66, `26.R5`).
9. `see()` is not reachable from the detector's output channel. Threshold: **0** paths from
   a Frigate event to `src/afon/brain/tools/camera.py` (D-66, `26.R5`).
10. Cameras cover the entry, the garden and the outbuilding; a room a guest would occupy is
    covered by presence, not video. Threshold: **0** cameras pointed at such a room (D-51).

## Benchmarks

- **G1** · B1 · `bench/test_perception_snapshot.py` — the registry records 36 cases with
  no date. Threshold 0 un-stamped facts. Last: **not yet measured** — exactly the B1-only
  evidence EVIDENCE.md flags.
- **G2** · B1 · `bench/test_perception_snapshot.py` [staleness] for the age property.
  Threshold 0 stale facts presented as current. Last: **not yet measured**.
- **G3** · B5 · 26.E1's mixed set: ask what the owner is looking at, score the answers
  against the frame. Threshold ≥90% over the set, with the set named. No scored run is
  recorded in this repository. Last: **not yet measured**.
- **G4** · B2 · a written room walk listing every sensing surface and its room. No such list
  exists, so the bedroom and bathroom sensor count is recorded nowhere. Threshold 0. Last:
  **not yet measured**.
- **G5** · B1 · planned gate `bench/test_speaker_verdict.py` [scene] — the file does not
  exist. Threshold 0 media-audio turns accepted as owner speech. Last: **not yet
  measured**. 26.R1 is the one raise task that survived the §C deferral.
- **G6** · B4 · invariant: no raw frame or raw audio feed is written to disk or to a store
  (D-24). Threshold: **0** writes; a write is a hard failure, not a setting. Last: **not yet
  measured**.
- **G7** · none — deliberately. A benchmark for deferred work is a reason to do it.
- **26.R4** · a one-way SSE event stream for live turns is not deferred and is not
  perception: it is a transport change, and the one task here that would put a standing
  stream of frames on the wire. Threshold: none set. Last: **not yet measured**.
- **G8** · B1 · `bench/test_no_frame_egress.py` — the `26.R5` gate. Threshold: with egress
  blocked the detector still produces events; 0 frames reach a remote model, a log or a crash
  report; 0 paths from the detector's output into `see()`. Last: **53/53 on 2026-10-04** — the
  channel admits metadata only, `see()` is proven unreachable at runtime by a tripwire, and both
  the error journal and the audit trail are asserted end to end. This measures the *seam*, not the
  hardware: no detector, no camera, no accelerator.
- **G9** · B4 · a camera pulled with the WAN cable out, vendor account disconnected.
  Threshold: the stream resolves locally or the camera is not integrated. This is a
  bench drill with a physical cable, not a test file. Last: **not yet measured**.
- **G10** · B4 · a written camera list: one line per camera, its room, and what it covers.
  Threshold 0 cameras in a bedroom, a bathroom, or a room a guest would occupy. No such
  list exists. Last: **not yet measured**.

## Failure modes

- **Green tests, dead camera** are the standing failure, and the reason the owner doubts this
  system: `bench/test_perception_snapshot.py` passes against a fake transport while the
  pc_agent op fails on the real machine. Diagnose: run the op by hand —
  `journalctl -u afon-brain | grep -i "vision\|screenshot\|perceive"`, then the pc_agent
  log, and confirm a frame actually arrives.
- **A stale fact quoted as current.** "You're at your desk" from a check twenty minutes ago.
  Diagnose: the stamp in the trace — `src/afon/brain/turn_trace.py` records what a turn
  assumed.
- **A television speaks and the gate believes it.** Reading the live gate log, 186 of 742
  real gate decisions (25%) were accepted, and the accepted transcripts include a film
  playing in the room plus Italian, French and German media audio — the gate was
  forwarding a television to the brain as though the owner had said it (`TODO.md`). That
  is a share of accepted *real* decisions, not an impostor-trial set: in those 742 the
  owner and not-owner are not two populations, they are one. Impostor trials are the
  distinct construct in M11 / D-15. The cause was the gate embedding its whole 6 s
  rolling window, which made the score measure the window's noise floor; the fix was to
  delimit the utterance with the VAD frames the pipeline already emits. That 25% is not
  re-measured anywhere, and 26.R1 is the fix that does not exist yet. Diagnose:
  `journalctl -u afon-brain | grep -i "speaker\|scene"`.
- **A sensor is placed in an air-gapped room.** No software check can catch this, which is
  why it is a placement-layer decision (D-38) and why goal 4 has no test. Diagnose: the
  physical device list, which does not exist.
- **An image leaves the host.** A VLM call is an egress event, and under the new hardware it
  is the *default* behaviour of the configured chain rather than an exception: every model in
  `vision_models` is remote. Two specific surfaces now exist, and both were closed by 26.R5
  rather than by policy. The first is a detector whose output reached for `see()` because
  "the frame is right there" — `detector.py` admits no frame and has no path to any vision
  call, asserted at runtime. The second is a frame attached to a crash report, where a stack
  trace wrote the first 600 characters of the JPEG next to the trace: that was **real**, not
  hypothetical, and `shared/redact.py` now withholds it. Diagnose:
  `uv run python bench/test_no_frame_egress.py`, then the audit lines for the vision tool
  (which carry a `<withheld>` marker and never frame bytes), and note that frames are still
  not stored (D-24, D-66).
- **The doorbell answers a guest and records them.** The doorbell is a camera and a
  microphone at the front door, which makes it the only surface in this house that captures
  someone who was not the owner by design. Under D-38 and D-51 it needs the same placement
  answer as a room satellite, and the answer has to be written down rather than assumed.
  Diagnose: the camera list, which does not exist.
- **A deferred task quietly resumes.** 26.R2 and 26.R3 are `deferred` in the registry —
  still owed, not cancelled, and not next. Diagnose: §C in the charter against the task
  states.

## Open questions

1. The record does not say whether any VLM path has run against a real camera on real
   hardware, or only against the fake transport. Which is it — and if it is only mocks, is
   26.F1 `done` a status that should change?
2. 26.R4 wants a one-way SSE event stream so a 15-second poll can become a live turn. Is
   that a perception surface, or a transport change belonging to S01 or S12? It is the one
   open task here that would add a standing stream of visual events.
3. The evidence for 26.R1's necessity is recorded in `TODO.md`; the gate that would prove
   the fix is a planned test file that does not exist. Why does the defect have a
   measurement and the fix not a test?
