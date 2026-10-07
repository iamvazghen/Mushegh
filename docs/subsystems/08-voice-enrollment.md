# S08 — Voice Enrollment

> **One line:** The owner's voiceprint, currently scoring 0.47 against a 0.60 target — and the reason every identity number downstream is weak.
> **Status:** built, **measurably weak** · **Registry:** S08 · 1/2 floor, 0/3 raise, 0/1 elite
> **Milestones:** M09 — the gate · **Decisions:** D-15, D-24, D-38

## Purpose

Everything that later decides "was that the owner" starts here. The enrolled voiceprint
is the root of the identity chain: the speaker threshold, the three-way verdict, and
every separation number in S10 and S11 inherit its quality. This is the one system where
a weak input is not a weak feature, it is a weak foundation — and the registry says so in
the status string rather than hiding it inside a task.

The current profile scores **0.47** against a 0.60 target. Nobody chose that number:
enrolment recorded whatever the microphone produced, embedded it, and reported
"captured". A clip that was four seconds of room hum, or a segment read while an
extractor fan ran, went into the profile exactly like a good one — and the cost surfaced
weeks later as a threshold that could not be placed, rather than as a message during the
five minutes the owner was sitting at the microphone. 08.F2 is the fix for that half and
it is done: `src/afon/edge/enroll_quality.py` measures duration, level, SNR and variety
per clip *before* it joins the profile. The fourth is the one that catches the case the
others miss — a pure tone can be long, loud and clean and contain no speech at all.

D-15 sets what is at stake. A false "owner" executes destructive actions or leaks
private data; a false "not-owner" costs a typed PIN. The asymmetry is roughly 100:1, so
the threshold moves up and "unsure" must exist as a third verdict. A weak profile makes
that verdict permanent, which is the same as having no identity system at all. D-24 and
D-38 both apply at the sensor layer: raw biometric feeds are never stored, and bedrooms
and bathrooms are air-gapped, permanently, regardless of capability.

**Why this has not been fixed.** M09 is the gate for S08 through S11, and it is open,
because acoustic enrolment needs physical quiet, a fixed microphone position,
calibration and edge debugging — duller than backend code, and not doable from a desk at
23:00. Stating that plainly is the point: while this gate is open, every number in S10
and S11 is weak, and building those first is building on sand.

## Structure

The profile lives on the edge, next to the microphone that produced it.

```
owner reads the script, in a quiet room
   ├──> bench/enroll_voice.py          the enrolment driver
   │      per clip, before it joins the profile: enroll_quality.py
   │      duration · level · SNR · variety → accept or reject with a reason (08.F2)
   ├──> src/afon/edge/speaker_id.py    ECAPA-TDNN, 192-dim, lazy-imported
   │      L2-normalised vector per clip → AFON_SPEAKER_PROFILE
   │      owner vs impostor → the measured band
   └──> src/afon/edge/speaker_gate.py  runtime gate
          accept_bar() is DERIVED from the measured band, not a constant (10.F3)
          borderline (within 0.05) also earns a face check
```

| Concern | Where |
|---|---|
| Enrolment driver | `bench/enroll_voice.py`; parsing in `test_enroll_script_parse.py` |
| Quality gate at capture time (08.F2) | `src/afon/edge/enroll_quality.py` |
| Embeddings, profile store, accept band | `src/afon/edge/speaker_id.py` |
| Runtime accept/reject (S10) | `src/afon/edge/speaker_gate.py` |
| Recognition words in transcripts | `src/afon/edge/proper_nouns.py` |

**Process ownership:** edge. The profile is a local artefact and does not migrate.
**What it stores:** one L2-normalised vector per clip, and the measured impostor band.
Not raw audio (D-24). The voiceprint is gitignored and never leaves the laptop.

## Goals

1. **The owner's voiceprint reaches a median of 0.60 or better** on the identity bench
   over held-out utterances (08.F1, M09) — the gate for S08 through S11.
2. **Enrolment quality is reported at enrolment time**, per clip, and a clip that is too
   short, too quiet, clipped, too noisy or speech-free is rejected with a reason (08.F2).
3. **The accept threshold is derived from the measured band**, not a hand-placed
   constant, so a new profile cannot inherit a threshold calibrated against another.
4. **Enrolment covers multiple conditions** — near mic, across the room, headset, with
   music — as distinct conditions with per-condition medians reported after (08.R1).
5. **Confidently-identified turns extend the profile**, with a cap and a decay (08.R2).
6. **A second known voice can be enrolled and named** (08.R3).
7. **Separation holds across a week of real turns with no manual threshold edits**
   (08.E1) — the D-43 bar.

## Benchmarks

| # | Goal | Tier | Command / drill | Threshold | Last measurement |
|---|---|---|---|---|---|
| 1 | **Profile quality (M09)** | B5 | `bench/test_phase5_identity_bench.py`, 20 held-out utterances | owner median ≥0.60; enrolment passes the SNR floor | **0.47** against a 0.60 target, recorded in the docstring at `src/afon/edge/enroll_quality.py:3` and in the comment at `bench/enroll_voice.py:165`. 08.F1's gate is `test_phase5_identity_bench.py` — owner median ≥0.60 — and 08.F1 carries no evidence record, so the number is not in the registry. It carries **no date** in the source, so treat it as a code-recorded value, not a dated run. The M09 re-measurement is **not yet measured** |
| 2 | Quality at capture | B1 | `bench/test_enroll_script_parse.py` extended, twelve plants | 12/12 decided correctly, each with a reason | 42/42 per the registry gate text; evidence kind `unverified-import` — **not yet measured** as a dated run |
| 3 | Derived threshold | B4 | Invariant: `accept_bar()` derives from the profile's own band; a hand-placed constant is a hard failure | 0 constant thresholds | not yet measured |
| 4 | Multi-condition enrolment | B5 | `bench/test_phase5_identity_bench.py` [per-condition medians] | ≥0.60 median in each of 4 conditions, reported separately | not yet measured — 08.R1 open, and no enrolment corpus exists in the repo |
| 5 | Continuous refinement | B1 | a planned `test_voice_profile_drift.py`, which does not exist | cap and decay honoured; 0 unbounded growth | not yet measured — nothing built |
| 6 | Guest enrolment | B1 | a voice sibling of `test_face_identity_separation.py` | a second named voice never matches the owner | not yet measured — 08.R3 open |
| 7 | Separation over a week (08.E1) | B3 | Seven consecutive days of real turns, every decision scored (D-43) | 0 manual threshold edits across the week | not yet measured — the B3 bar, unmet |

Two numbers appear here and only two. **0.47** is the current voiceprint score, quoted
from the module that owns the problem; **0.60** is the target, and it appears in the goal
and the benchmark so the two cannot drift. Everything else is a target with no
measurement, and goal 7 is the D-43 bar, which nothing here has met.

## Failure modes

**A bad clip enters the profile.** A fan, a fridge, traffic or a dial tone gets embedded
and reported as captured. The cost appears weeks later as a threshold that cannot be
placed, and the owner cannot tell which clip caused it. When the quality gate is
bypassed, re-enrol rather than adjust the threshold — a threshold moved to fit a bad
profile hides the bad profile.

**The threshold is hand-placed.** Someone tunes the accept bar to make today's turns
pass. Then a borderline score is a third of the band wide, the 0.05 margin no longer
means anything, and every borderline decision routes to a face check that also cannot be
placed. Diagnose by comparing `accept_bar()` against the profile's measured band.

**The owner is refused.** The false "not-owner" branch. D-15's asymmetry makes it about
100:1 cheaper than the alternative, so this is a tradeoff and not a bug — but at 0.47 it
happens constantly, and the owner's response is to stop using voice, which is the outcome
the system exists to prevent.

**A guest's command executes.** The impostor clears a band that is too low. This is the
false-owner branch, and it can execute destructive actions or leak private data.

**The profile decays.** Voice, room and microphone all change. Without capped refinement
(08.R2) the profile ages and refusals climb — visible only as a rising refusal rate,
which is why the score distribution matters as much as the median.

## Open questions

1. M09 needs 20 held-out utterances and a quiet room, and nothing in the repo is a
   usable enrolment corpus. Where should one come from — a deliberate recording session,
   or turns captured in normal use?
2. 08.R1 wants per-condition medians across four conditions, while only one condition was
   ever enrolled. Re-enrol all four at once, or extend the existing profile condition by
   condition while it is still below target?
3. The 0.47 figure has no date in the source. Before S10 is rebuilt on top of it, the
   profile should be re-measured and dated — otherwise S10's thresholds are calibrated
   against an unverified number.
