# S09 — Face Enrollment

> **One line:** The owner's face references and the ArcFace backend that is wired but has never enrolled a single embedding.
> **Status:** built, **never run on the current backend** · **Registry:** S09 · 1/2 floor, 0/4 raise, 0/1 elite
> **Milestones:** M10 · **Decisions:** D-24, D-38

## Purpose

Face enrolment exists to make the identity chain three-way: the voice gate can say
"unsure" (D-15), and a borderline voice decision is supposed to earn a face check instead
of a guess. That only works if there is a real face profile behind it. Today there is
not one, and the registry says so in the status string rather than softening it.

The ArcFace backend is wired, tested and imported — SCRFD for detection, ArcFace for a
512-d embedding, both behind the optional `vision` extra and both lazily loaded, with a
warning and a fallback when the extra is missing. What does not exist is an ArcFace
*enrolment*. `owner.npy` holds legacy **LBP** histograms: a spatially-blocked texture
signature computed in numpy, which is a workable descriptor and not a face recogniser in
the sense D-15 requires. 09.F1 is the entire gap, and it is open.

The other half is solid, and it is what makes 09.F2 done. Enrolment rejects unusable
captures **at capture time**: no face, two faces, too dark. That matters more than a pass
rate, because an unusable capture that enters the profile is discovered weeks later as a
threshold that cannot be placed — the same failure S08 documents, and the reason
`enroll_quality.py` exists on the voice side.

D-24 and D-38 are hard limits. Bedrooms and bathrooms are permanently off-limits to
ambient recording hardware, no exceptions, regardless of capability (D-38) — a
sensor-placement rule, not a software one. Raw biometric sensor feeds are never stored
(D-24). What is kept is a derived reference, a vector and not a video.

**Why this has not been run.** Same reason as S08: enrolment needs physical quiet,
calibration, and edge debugging on hardware that has to be pointed at a face. It cannot
be done from a desk, and it is duller than writing backend code. It is the reason the
downstream face numbers in S11 are unproven rather than merely low. M10 is the milestone,
and it has not been performed.

## Structure

The references live on the machine with the camera.

```
camera + light, owner present
   └──> src/afon/brain/tools/camera.py
          _capture_burst()   warmup, min_brightness — the light gate
          _detect_faces()    SCRFD when the extra is present
          capture_verdict()  09.F2: no face / two faces / too dark → reject NOW
          liveness_verdict() frame-to-frame difference

   current references:  owner.npy — legacy LBP histograms, via _lbp_hist() /
                       _face_signature() (numpy, no extra dep) and _owner_refs()
   target backend:      _arcface() — SCRFD + ArcFace, lazy, `uv sync --extra vision`
                       _embed_faces() → 512-d embeddings; warns and falls back to LBP
```

| Concern | Where |
|---|---|
| Capture, detection, verdict, enrolment | `src/afon/brain/tools/camera.py` |
| Legacy LBP references (the current `owner.npy`) | `_lbp_hist`, `_face_signature`, `_owner_refs` in the same module |
| ArcFace backend (wired, unused for enrolment) | `_arcface`, `_embed_faces`, `_owner_embeddings` |
| Unusable-capture rejection (09.F2) | `capture_verdict()`; `test_face_recognition.py` extended, ten plants |
| Backend actually loadable | `bench/test_face_arcface_backend.py` |
| Household separation (09.R3) | `bench/test_face_identity_separation.py` |

**Process ownership:** the edge owns the camera and the reference store; capture and
enrolment handlers live in the brain's tool package, so a turn can trigger enrolment but
the bytes never leave the machine with the camera. **What it stores:** one `.npy` of
derived references under the state directory. Not raw frames, not video (D-24).

## Goals

1. **A real ArcFace owner embedding exists and is loadable** (09.F1, M10), and the
   legacy LBP reference is retired rather than left to shadow it.
2. **Unusable captures are rejected at capture time** — no face, two faces, too dark —
   with a reason the owner can act on (09.F2).
3. **Enrolment is a multi-condition capture set**, per-condition scores reported after
   (09.R1).
4. **Re-enrolment is non-destructive**: the old set is kept and restorable (09.R2).
5. **A second enrolled face never matches the owner** (09.R3) — household separation.
6. **Zero owner false-negatives across a day of desk sessions** (09.E1).
7. **No raw frame is stored**, and no capture path reaches an air-gapped room.

## Benchmarks

| # | Goal | Tier | Command / drill | Threshold | Last measurement |
|---|---|---|---|---|---|
| 1 | **ArcFace enrolment (M10)** | B2 | Enrol on ArcFace, then enrol and match 10/10 at desk lighting, with backlight and partial-profile cases recorded | 10/10 matches; a real owner embedding present and loadable | not yet measured — the backend is wired and tested, but no ArcFace enrolment has been performed on it |
| 2 | Unusable capture rejected | B1 | `bench/test_face_recognition.py` extended, ten plants | 10/10 decided correctly, each with a reason | 35/35 per the registry gate text, ten plants including the positive case; evidence kind `unverified-import` — **not yet measured** as a dated run |
| 3 | Multi-condition set | B5 | `bench/test_phase5_identity_bench.py`, per-condition scores after enrolment | a score reported for each of ≥3 conditions | not yet measured — 09.R1 open |
| 4 | Non-destructive re-enrolment | B1 | `bench/test_backup_restore.py` extended | old set restored after a failed re-enrolment | not yet measured — 09.R2 open |
| 5 | Household separation | B1 | `bench/test_face_identity_separation.py` | 0 matches of a second enrolled face to the owner | not yet measured — 09.R3 open |
| 6 | A day of desk sessions (09.E1) | B5 | a recorded run of `test_face_recognition.py` against a day of real frames | 0 owner false-negatives across the day | not yet measured — the day has not been recorded |
| 7 | Never store raw feeds (D-24, D-38) | B4 | Invariant: no raw frame written to disk; no capture path reachable in a D-38 room | 0 raw frames persisted; 0 air-gapped code paths | not yet measured |

There is **no measured number in this document**, and that is the accurate state. The
registry gate texts carry pass counts — 35/35 on the capture plants — but their evidence
kind is `unverified-import`, and by the ladder in [../EVIDENCE.md](../EVIDENCE.md) an
imported claim is not a run. Every benchmark here is a target. M10's 10/10 is a
threshold, not a result.

## Failure modes

**The legacy LBP reference shadows the real backend.** ArcFace loads, the module logs
"face recognition: ArcFace + SCRFD loaded", and the owner believes recognition is on the
new backend while matching still runs against the old texture signatures. Nothing fails;
the system is simply quietly wrong. This is the risk of 09.F1 being open, and it is why
the status says "never run on the current backend" rather than "partial".
**An unusable capture enters the profile.** Too dark, no face, two faces. Rejection at
capture time (09.F2) prevents it; when bypassed, the cost surfaces weeks later as a
threshold that cannot be placed.

**Re-enrolment destroys the working profile.** The owner re-enrols, the new set is worse,
and there is no way back. 09.R2 is open, so this is currently possible: the reference is
one file and overwriting it is one call.

**The owner is not recognised in his own room.** A false negative at the desk. 09.E1
exists because this has never been measured over a real day, so the honest answer is that
the false-negative rate is unknown, not low. A household member matching is the opposite
branch, the one D-15's asymmetry makes expensive, and 09.R3 is unbuilt — so there is no
evidence that it does not happen.

**A capture path points at the wrong room.** D-38 is enforced physically, not by this
code. The software obligation is that no capture path can be coaxed into an air-gapped
room, and no test asserts that today.

## Open questions

1. M10 wants 10/10 at desk lighting plus backlight and partial-profile cases recorded,
   but no capture corpus exists. Does one get recorded deliberately, or is the first real
   week of desk frames the corpus?
2. 09.R1 (multi-condition) and 09.R2 (non-destructive) are both unbuilt and both touch
   the same single reference file. Should re-enrolment land first, so a multi-condition
   set can be captured without risking what exists?
3. S08's M09 and S09's M10 are both open, and the voice gate's borderline path routes to
   a face check. With neither profile in target condition, is D-15's "unsure" verdict the
   only coherent path — or does one gate have to close before the other is measurable?
