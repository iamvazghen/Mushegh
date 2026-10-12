# S10 — Speaker Recognition

> **One line:** deciding whether the voice that just spoke is the owner's, before the brain is
> allowed to act on the sentence.
> **Status:** built, not well structured · **Registry:** S10 · 3/3 floor, 0/3 raise, 0/1 elite
> **Milestones:** M09, M11 · **Decisions:** D-15, D-24, D-51

## Purpose

Mushegh hears a wake phrase, transcribes, and only then asks who spoke. This system is that
question. It sits after speech-to-text, scores the utterance against the enrolled voiceprint,
and drops the transcript when the voice is not the owner's, so the brain never acts on it. A
stranger, the television, and a podcast all end in the same place: silence.

The threshold is the whole system, and the current one is too loose (D-15). A false "owner"
executes a destructive action or leaks private material; a false "not-owner" costs a typed PIN.
That is roughly a 100:1 asymmetry, so the bar moves up, and a third verdict — **unsure** —
has to exist and route to a soft path. Never a refusal, never a grant.

Two things it refuses to be. It is not a security boundary on its own: the real boundaries are
the confirmation gate (D-07, D-09) and the typed schema (D-04). And it is not a resident
detector: there is one enrolled person, because the user is one person and guests are out of
scope (D-51).

If it is absent, the television commands the laptop, and nothing in the system notices.

## Structure

| Path | Role |
|---|---|
| `src/mushegh/edge/speaker_id.py` | ECAPA-TDNN embedding, 192-dim, lazy import; the pure decision `should_accept()` and the bar derivation `derive_threshold()` |
| `src/mushegh/edge/speaker_gate.py` | Rolling audio buffer; when the STT emits a frame the buffer is embedded and compared; a non-match drops the transcript |
| `src/mushegh/edge/enroll_quality.py` | Per-clip admission: long enough, loud enough, clean enough, actually speech |
| `bench/enroll_voice.py` | Writes the voiceprint, then measures owner against impostor and records that band |
| `src/mushegh/shared/paths.py` | `state_dir()`, the one root for state on this host |

The voiceprint is a small JSON file at `$MUSHEGH_SPEAKER_PROFILE` — a list of L2-normalised
embeddings, not a mean vector, plus a `separation` block holding the owner and impostor scores
measured against *those* vectors. All of this runs in the **edge** process, where the owner is;
the brain receives a transcript or silence and never sees the biometric.

Two facts about the code that the registry does not record. The accept bar is
`settings.speaker_threshold`, default **0.30** (`src/mushegh/config.py`), used only when the
profile carries no measured separation; D-15 names **0.75**. And `should_accept()` returns
`True` when the feature is off, no profile exists, or the `identity` extra is not installed.
The gate fails **open** by construction. That is the documented degradation contract of the
rest of Mushegh, applied to the one component where fail-open is the expensive direction.

## Goals

1. The gate scores the **utterance**, not the room (10.F1).
2. Three verdicts — owner, not-owner, unsure — with unsure routed to a soft path that is
   neither a refusal nor a grant (M11, D-15).
3. The bar is derived from the enrolled profile's measured separation, not a constant (10.F3).
4. A cold start does not mis-score the first utterance (10.F2).
5. Broadcast media — television, music — never passes the gate (10.R3).
6. A false owner is treated as the expensive error everywhere in this system.

## Benchmarks

| Goal | Tier | Command or drill | Threshold | Last measurement |
|---|---|---|---|---|
| 1 | B1 | `uv run python bench/test_speaker_gate_scoping.py` | a second speaker in the same room never scores above the bar | registry records 10.F1 done; run not reproduced here — not yet measured |
| 2 | B1 | new `bench/test_speaker_verdict.py` (planned, M11 — does not exist yet) | 0 false-owner matches in 100 impostor trials; unsure never resolves to grant or refusal | not yet measured |
| 3 | B5 | `uv run python bench/test_phase5_identity_bench.py`, then read `separation` in the profile JSON | derived bar inside the measured band; a band narrower than `MIN_SEPARATION = 0.10` is reported as unsplittable rather than given a bar | enrolled voiceprint scores **0.47** against a 0.60 target, per the `src/mushegh/edge/enroll_quality.py` docstring — that figure belongs to S08 (M09), so every threshold here is provisional. not yet measured for S10 |
| 4 | B1 | `uv run python bench/test_speaker_warmup.py` | 0 mis-scored first utterances across a cold start | registry records 10.F2 done; run not reproduced here — not yet measured |
| 5 | B1 | new `bench/test_speaker_verdict.py` [broadcast fixture] (planned — does not exist yet) | 0 of 20 television and music clips pass the gate | not yet measured |
| 6 | B4 | `should_accept()` in `src/mushegh/edge/speaker_id.py` | a raised bar is the only lever; no code path lowers a bar at runtime without a profile rewrite | not yet measured — structural claim, unverified: the argument is a reading of the code, with no run and no date |

## Failure modes

**The identity extra is missing or no profile is enrolled.** `verify()` accepts everything, the
gate becomes a no-op, and the system looks healthy while being open. The owner sees a
stranger's sentence answered as his own. Diagnose: `journalctl -u openmushegh-edge -n 200 |
grep -i "speaker profile"`, then `ls "$MUSHEGH_SPEAKER_PROFILE"`, then `uv run python
bench/test_speaker_gate_scoping.py`. No log line for the profile means no gate.

**Cold start.** The first utterance is embedded against a buffer that has not filled. Registry
records this as fixed (10.F2); if it regresses, the owner sees Mushegh ignoring him once after
every restart, and learning to re-speak more loudly.

**The bar is stale.** A profile rewritten with `--append` deliberately drops the old
`separation` block, because those numbers described vectors that no longer exist. Until
re-measured the gate falls back to the setting and says so in the log. Diagnose: the
`separation` key in the profile JSON, then re-run `uv run python bench/enroll_voice.py`.

**Wrong direction of error.** A profile that cannot separate owner from impostor produces a bar
that passes both. The owner then sees random commands refused and random commands obeyed, and
trust in the voice path collapses — which is why M09 is the gate for S08–S11, not a
nice-to-have.

## Open questions

1. `should_accept()` fails open. For the one component where a false accept is 100x more
   expensive than a false reject, is fail-open still the right contract, or should a missing
   backend drop to push-to-talk instead (D-56)?
2. 10.R2 (diarization, two speakers in the room) attributes each utterance. Does that land
   before or after the three-way verdict, and does a second speaker get a soft path or
   silence?
3. D-15 names 0.75; the code falls back to 0.30. Which number is the decision actually about —
   and does the derived bar (goal 3) make the constant moot?
