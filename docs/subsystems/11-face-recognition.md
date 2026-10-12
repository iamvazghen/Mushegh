# S11 — Face Recognition

> **One line:** a second factor for the one person in the room, used only where a camera is
> allowed to be.
> **Status:** built, not well structured · **Registry:** S11 · 3/3 floor, 0/3 raise, 0/1 elite
> **Milestones:** M09 (the gate for S08–S11); no milestone names S11 directly · **Decisions:** D-38, D-51, D-24, D-10

## Purpose

The laptop camera is a second factor, not a primary one. It answers "is the owner the person
in front of the screen" when a decision is worth a second look, and it does that locally: no
frame leaves the machine, and the durable artefact is an embedding and a verdict, never an
image (11.R3, D-24).

The hard part is not the matching, it is the conditions. The interesting cases are a
backlit window, a half-turned head, and glasses — not a passport photo under studio light. A
recogniser that only works on a posed, frontal, well-lit face is a decoration (11.R1).

Two boundaries are not software preferences. Bedrooms and bathrooms are permanently off-limits
to ambient hardware, regardless of capability (D-38) — that is a sensor-placement rule, and it
is enforced by where the camera physically is, not by a setting anyone can pass. And there is
no guest or family scope: the user is one person, and ambient biometric identification of
anyone else in the house is a surveillance liability rather than a feature (D-51).

If it is absent, nothing breaks that the owner would notice today — which is precisely why it
is dangerous. It becomes a second factor nobody relies on, or worse, one that fires wrongly
and is learned to be ignored.

## Structure

| Path | Role |
|---|---|
| `src/mushegh/brain/tools/camera.py` | The whole camera surface: `look_around` (vision model, local frame), `visual_presence` (OpenCV haar cascade face count, local, yes/no + count), heavy calls in a thread so the loop keeps breathing |
| `bench/test_security_hardening.py` | Where 11.R3 is to be asserted: frames never persisted |

This is a **brain** module, not an edge one. The camera is opened on demand, handed to the
tool, and closed; nothing streams continuously. Degradation is explicit: no webcam, camera
busy, or access blocked yields a calm spoken line, never a crash.

The recognition backend is ArcFace, wired with a legacy LBP fallback (11.F2). The fallback
matters: an ArcFace profile and an LBP comparator produce no match, so a fallback that
engages silently turns every face check into a soft path. That is why S09's enrolment has to
agree with the backend in use before any of this is worth measuring.

The frame never lands in SQLite (D-02, D-24). The laptop is the sensor, the brain host is
the store, and the only thing that crosses is a count, a verdict, and a timestamp.

## Goals

1. "Nobody there" and "can't tell" are different answers with different consequences (11.F1).
2. A printed photograph or a phone screen does not pass (11.F3, liveness).
3. Recognition holds at real desk conditions — backlight, partial profile, glasses — at
   ≥90% owner recall (11.R1).
4. A verdict is taken over N frames, not one (11.R2).
5. Frames are never persisted; only embeddings and verdicts are, asserted rather than assumed
   (11.R3).
6. The sensor lives in office or living room, and nowhere else (D-37, D-38).

## Benchmarks

| Goal | Tier | Command or drill | Threshold | Last measurement |
|---|---|---|---|---|
| 1 | B1 | `uv run python bench/test_camera.py`, `uv run python bench/test_face_second_factor.py` | 0 cases where "can't tell" is reported as "nobody there" | registry records 11.F1 done; run not reproduced here — not yet measured |
| 2 | B1 | `uv run python bench/test_face_liveness.py` — **the registry names no test here** | 0 of the printed-photo and phone-screen fixtures accepted | registry records 11.F3 done, but its `gate` field is the literal string `new`, so this file is sourced to nothing in the registry; run not reproduced here — not yet measured |
| 3 | B1 | `uv run python bench/test_face_recognition.py` (fixture set to be extended) | ≥90% owner recall across backlight, partial-profile and glasses fixtures | not yet measured |
| 4 | B1 | `uv run python bench/test_camera.py` [fusion] | 1 verdict per N frames; N recorded, 0 single-frame verdicts | not yet measured (11.R2 open) |
| 5 | B1 | `uv run python bench/test_security_hardening.py` (to be extended) | 0 image bytes written to any store; embeddings only | not yet measured (11.R3 open) |
| 6 | B4 | walk the sensor list | no camera in a bedroom or bathroom, and none may be added by configuration | not yet measured — structural claim, unverified: the placement argument is real, but no run and no date records it |

Two cross-checks exist and are worth naming because they are the ones that can catch a
false accept: `uv run python bench/test_face_arcface_backend.py` (backend actually in use)
and `uv run python bench/test_face_identity_separation.py` (owner and impostor are separable
at all). Both are B1 and neither has been run on this machine's camera — see open question 1.

## Failure modes

**The fallback backend engages.** ArcFace unavailable, LBP loads, an ArcFace profile is
compared against an LBP reference, and the result is a non-match every time. The owner sees a
confirm gate that never opens and no explanation of why. Diagnose: `journalctl -u
openmushegh-brain -n 200 | grep -i arcface`, then `uv run python
bench/test_face_arcface_backend.py`, then `uv run python bench/test_face_recognition.py`.

**Lighting.** A backlit window inverts the face and the count returns nothing. The owner sees
`visual_presence` report an empty room while he is sitting at the desk, and presence-based
nudging correctly stops. That is the safe direction, and it is still a defect. Diagnose:
`uv run python bench/test_face_recognition.py` on the extended fixture set.

**Liveness regression.** Without it, a photograph on the desk is a key. The registry records
liveness as done (11.F3); if a future backend change replaces the check, a photo passes and
nothing in the logs says so. Diagnose: `uv run python bench/test_face_liveness.py` — this is
the one test in this system that must never be skipped.

**Scope creep toward ambient.** The tempting extension is a camera in more rooms, or a
per-person profile for a visitor. Both cross D-38 and D-51 and neither is a code question.

## Open questions

1. `bench/test_face_arcface_backend.py` is a wired-backend test, and 11.F2 records ArcFace as
   done — but S09's enrolment has never been run on this backend. Is there an ArcFace profile
   on disk at all, or only code?
2. ≥90% owner recall is a recall bar. A second factor whose cost is a false accept needs a
   stated false-accept rate too; what is the paired threshold, and is a 20-frame fixture set
   enough to place it?
3. What is N for multi-frame fusion (11.R2), and does the frame budget cost more latency than
   the desk conditions are worth?
