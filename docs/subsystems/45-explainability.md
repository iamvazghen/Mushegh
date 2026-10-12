# S45 — Explainability & Transparency

> **One line:** Every answer and every unattended action can be explained from the record
> rather than reconstructed afterwards — which is the only reason the audit trail is worth
> keeping at all.
> **Status:** complete for now · **Registry:** S45 · 4/4 floor, 1/10 raise, 0/1 elite
> **Milestones:** M18, M30 · **Decisions:** D-25, D-52, D-22, D-54

## Purpose

"Why did you do that?" must have an answer that comes from what actually happened, not from
a model being asked to narrate its own reasoning afterwards — the one source on the subject
with no access to the facts. It will name a tool it did not call and a site it did not read,
fluently, because the question invites a story and nothing contradicts it.

Three rules carry it. **A superseded memory is tombstoned with an audit line, never silently
wiped** (D-25, `30.R10`) — the more recent explicit correction wins, and the loser is written
down, because silent deletion is how a system loses the ability to explain itself. The
writer landed 2026-10-04, but **nothing yet calls it**: no caller passes the `subject` that
makes a supersession happen, so no supersession has occurred in the running system.
**Confidence is reported where it varies**, and in voice the uncertainty must be
**audible** (D-52): an explicit hedge or a lowered cadence, never assertive delivery of an
uncertain answer. **The vault is the human source of truth** (D-22) — where the record and
the file disagree, the file wins.

If this is absent, the audit trail becomes a liability rather than an asset: a log that is
kept and cannot be read back is a store of things the owner cannot check him against, and
the first accusation he cannot answer is the first one that lands.

## Structure

- `src/mushegh/brain/turn_trace.py` — one row per turn, emitted from a `finally` so a turn that
  refuses early, takes the fast path or raises still leaves evidence. The row carries intent
  class, tools considered, tools fired, prefill tokens and wall-clock per stage, plus
  `sources` and `confidence` for the explainability half (45.F3). Rows go to
  `turns-YYYY-MM-DD.jsonl` under `trace_dir()`, pruned on a `KEEP_DAYS` horizon.
- `src/mushegh/brain/tools/diagnose.py` — `_why_last()` reads the last turn row and answers
  "why did you say that" from it: the tools that fired, the sites actually retrieved,
  whether the reply was hedged or put flat, and the time it took. A tool-free answer says so
  plainly, which is the most useful thing the owner can know when he doubts one (45.F3).
  `diagnose` also takes `turn=<id>` for a specific turn.
- `src/mushegh/brain/audit.py` — `record` / `recent`, one JSON line per action, `_redact`
  scrubbing secret values before the write. Attribution and correlation come from the
  actor and correlation id the action carried. The trail is **append-only and
  best-effort, not tamper-evident**: no hash chain and no signature, and every write is
  wrapped so a failure is dropped rather than raised. Nothing a reader can run today
  proves a line was not edited out of it (`45.R10`).
- `src/mushegh/brain/review.py` — 45.F4, a **projection** over the audit log, exactly like
  `hud.py`: no new datastore, no new process. Unattended is defined by exclusion — any actor
  that is not the owner — so a new autonomous driver cannot be silently missed.
- `src/mushegh/brain/proactive_report.py` — what an unprompted batch did, why, and where to look
  (45.F1). One bounded LLM call writes the prose from the real actions; a deterministic
  fallback keeps the report honest and never-silent if the model is unavailable.
- `src/mushegh/brain/citations.py` — the per-turn ledger of what was actually retrieved, so a
  source Mushegh names is one he opened. Deliberately not re-fetched: a 200 from a page he never
  read is not evidence he read it.
- `src/mushegh/brain/memory.py` and `src/mushegh/brain/recall.py` — the stores an explanation is
  made of. `src/mushegh/brain/forget.py` sweeps every store and then **re-queries**, because the
  only evidence a thing is forgotten is asking for it again and getting nothing back.
- The supersession trail (30.R10, D-25) — `learned/supersessions.jsonl`, one JSON line per
  supersession carrying both texts, the subject, the reason, both filenames and the old
  source; `MemoryStore.supersessions()` reads it back oldest first. It sits beside the notes
  rather than in `audit.py` on purpose: the note glob in `_iter_notes()` must never mistake
  an audit line for a fact, and `audit.py` records tool actions, not beliefs.
- The tombstone itself lives in the superseded note's own front-matter (`superseded_by`,
  `superseded_at`), so the fact's text survives **where the fact was** rather than in a side
  table, and `_iter_notes()` skips it so an explanation can no longer be built on a corrected
  fact. `subject` is declared by the caller: the store cannot know two sentences share a
  slot, and guessing is how a store invents a contradiction that was never there. **No caller
  declares one yet.**

Ownership: the brain process. The trace is written per turn; the audit line is written per
action; the review surface reads both.

## Goals

1. "Why did you do that?" is answerable about the last turn from the record, naming the
   tools fired, the sources read and how firmly the answer was put (45.F3).
2. Every unattended action is visible afterwards, with its actor and correlation id, in one
   place (45.F4).
3. A superseded memory is absent from recall and present in the audit log — tombstoned, not
   wiped (D-25, M30, `30.R10`: 24/24 in `bench/test_supersession.py` on 2026-10-04, and
   `not yet exercised` — no caller passes a `subject`).
4. Confidence is stated where it varies, and audible where it is spoken (D-52, M18, `45.R1`).
5. Spoken answers carry short-form attribution, so the owner knows whether he is hearing
   his calendar or the web (`45.R2`).
6. A turn from the past 30 days can be reconstructed from its stored inputs (`45.R3`,
   `45.E1`).

## Benchmarks

1. **B1 (45.F3)** — `bench/test_why_last_turn.py`. Threshold: the explanation names only
   tools that actually fired and only sources actually retrieved, and distinguishes hedged
   from flat. Registry records 45.F3 `done` as of 2026-10-03. Last field measurement:
   `not yet measured`.
2. **B1 (45.F4)** — `bench/test_unattended_review.py`. Threshold: every unattended action
   appears with its actor and its correlation id, and 0 owner-initiated actions are
   mislabelled as unattended. Registry records 45.F4 `done`; no field measurement.
3. **B1 (45.F1)** — `bench/test_proactive_report.py`. Threshold: the report names the real
   actions and the real trigger, and the deterministic fallback produces a report rather
   than a silence when the model is unavailable. Registry records 45.F1 `done`.
4. **B1 (45.F2)** — `bench/test_phasex_audit_health_modes.py`. Threshold: a full trail
   exists for the day's actions, with secret values redacted before the write. Registry
   records 45.F2 `done`.
5. **B1 (M30, D-25, `30.R10`)** — `bench/test_supersession.py`, 24/24 on 2026-10-04.
   Threshold: store a correction on a declared `subject`, and the superseded memory is
   **absent from recall** — `_iter_notes()` skips it — **and present in the record**: its
   text kept with `superseded_by`/`superseded_at` in its own front-matter, plus one
   `learned/supersessions.jsonl` line naming both texts, the subject, the reason and both
   filenames. Also asserted: an `inferred` fact never supersedes an owner-stated one
   however late it arrives, a `tool` fact may supersede an `inferred` one, and a
   subjectless fact or an identical repeat is untouched. `not yet exercised` — **no
   production caller passes a `subject`**, so the running system produces no supersession;
   the suite and J-07 in `bench/test_journeys.py` drive `remember(..., subject=)`
   directly, the journey at 63 passed, 8 blocked, 0 failed on 2026-10-04. `30.R10` stays
   `in-progress` under D-43, which wants a green suite **and** seven days of real use.
6. **B1 (`45.R1`, M18)** — `bench/test_uncertainty.py [reported confidence]`. Threshold: an
   answer whose confidence varies carries it, and the row records `hedged` rather than
   `flat`. Last measurement: `not yet measured`; the same file's own header records 59–60%
   hedge compliance on two runs of unchanged code, which is why this is still open.
7. **B2 (`45.E1`, `45.R3`)** — the audit replay drill: pick a turn from the past 30 days and
   reconstruct its inputs from the trail. Threshold: the tool set and source set match what
   the turn reports. Last measurement: `not yet measured` — the drill has not been run, and
   the 30-day window is wider than the trace's own `KEEP_DAYS = 14`, so a replay older than
   two weeks has no row to read.
8. **B1 planned (`45.R10`)** — new `bench/test_audit_integrity.py` (does not exist yet).
   Threshold: a verification step a reader can run without the framework reports a removed
   or edited audit line — or, failing that, the file is documented as best-effort and every
   document stops calling it tamper-evident. Last measurement: `not yet measured`; the
   trail carries no integrity check today (D-25, D-43).

## Failure modes

**An explanation that is a story.** The check is whether the named tools appear in the turn
row, not whether the sentence is plausible:

    python -c "from mushegh.brain.turn_trace import last; r=last(); print(r.get('tools_fired'), r.get('sources'), r.get('confidence'))"
    journalctl -u openmushegh-brain --since "1h" | grep -iE "why|last_turn|diagnose"

**A secret reached the audit log.** `_redact` runs before the write, so a raw value means the
redaction list missed a key:

    python -c "from mushegh.shared.paths import audit_dir; print(audit_dir())"
    grep -rlE "(token|key|secret)=" "$(python -c "from mushegh.shared.paths import audit_dir; print(audit_dir())")" | head
    python -c "from mushegh.brain.audit import recent; print(recent(3))"

**A memory vanished with no trace.** That is the D-25 failure, and it is invisible by
construction — which is why the check looks for the tombstone rather than the absence. The
writer is `30.R10`'s, so the first command asks whether it is still in the tree; the trail
is empty when nothing has superseded anything yet, which on a fresh install is exactly what
it should be:

    grep -rln "superseded_by" src/mushegh/          # the tombstone writer, if it is still there
    python -c "from mushegh.brain.memory import MemoryStore; print(MemoryStore().supersessions()[-3:])"
    python -c "from mushegh.brain.recall import LAYERS; print(list(LAYERS))"
    journalctl -u openmushegh-brain --since "7d" | grep -iE "supersed|correct"

**An unattended action is missing from the review.** Unattended is defined by exclusion, so a
driver that runs without recording its actor is invisible by construction:

    python -c "from mushegh.brain.review import unattended_runs; print(len(unattended_runs(1)))"
    journalctl -u openmushegh-brain --since "24h" | grep -c "actor="

**A turn row is incomplete, so the explanation is confidently wrong.** `REQUIRED` in
`turn_trace` is the contract, and the completeness count is the diagnosis:

    python -c "from mushegh.brain.turn_trace import summary; print(summary(50))"
    ls -la "$MUSHEGH_STATE_DIR"/traces/
    journalctl -u openmushegh-brain --since "24h" | grep -i "turn_trace"

## Open questions

1. Who declares the subject? The physical question is answered and answered the same way
   S30 answers it: the tombstone lives in the superseded note's own front-matter
   (`superseded_by`, `superseded_at`) and the trail in `learned/supersessions.jsonl` — two
   plain files under the memory dir, legible in 2036 with a text editor, so D-54 is served
   without the SQLite table and without giving up the per-note record. Open instead: **no
   caller passes a `subject`**, so the rule is built and unused, and the vocabulary is
   undecided. Two documents must not answer this differently.
2. Is `45.R3` decision replay the same work as M30's tombstone assertion, or does replay
   need inputs the trace does not keep? The row records what fired, not what the model was
   shown.
3. How much of the trail survives the 30-day ephemeral expiry (D-21)? A turn explained
   from a file that retention already swept is the same failure as a memory wiped in
   silence, one layer up.
