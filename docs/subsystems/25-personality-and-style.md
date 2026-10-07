# S25 — Personality & Interaction Style

> **One line:** A disciplined butler: dry, precise, short, and the same person on every channel.
> **Status:** complete for now · **Registry:** S25 · 3/3 floor, 0/3 raise, 0/1 elite
> **Milestones:** M17 · **Decisions:** D-20, D-50, D-52, D-16

## Purpose

How Afon sounds, stated once, in two files the owner edits. `personality/afon.md` is the
persona; `personality/operating-rules.md` carries the behavioural rules and points back at
the persona for anything about manner, deliberately, so that "no markdown, one or two
sentences" exists in exactly one place (25.F3). Both are loaded into every system prompt by
`src/afon/brain/context.py`.

The rules are short and non-negotiable. **No conversational trailing** — never "is there
anything else I can assist you with today" (D-20). No unsolicited apologies, no filler, no
feigned emotional investment. On an error, state the discrepancy concisely and move on. No
moods, no synthetic emotional variance: a stable, transparent instrument, because affect
that degrades operational predictability is noise, not charm (D-50). Uncertainty is audible
— an explicit hedge or a lowered cadence, never assertive delivery of an answer the system
is not sure of (D-52).

If it is absent the system still works and becomes tedious in a specific way: correct
answers, delivered at the wrong length, with an offer at the end of each one. A bad Afon is
noticed within a week (D-50), and trailing is the first thing noticed.

## Structure

| Path | Role |
|---|---|
| `personality/afon.md` | The persona template; identity placeholders filled from `.env`; injected into every prompt |
| `personality/operating-rules.md` | Clarify / confirm / speak, and the check-before-refusing list; loaded by `context.py` |
| `src/afon/brain/context.py` | `_persona_path()`, `stable_prefix()`, `build_system_prompt()` — the only place either file is read |
| `src/afon/brain/affect.py` | `infer_affect()` from utterance text and cheap context; `affect_to_voice()`, `manner_note()` ride the turn as a system note |
| `src/afon/brain/relationship.py` | `RelationshipMemory` — how the owner has been, sensitivities, address and familiarity |
| `src/afon/shared/uncertainty.py` | `calibration()` — the definition of a calibrated answer, used by the runtime and the scorer alike |
| `src/afon/brain/citations.py` | What Afon actually read this turn, so a named source is one that was opened |
| `src/afon/edge/tts.py` | The affect → TTS hop for spoken answers |

Process: brain, per turn, in the prompt assembly path. `affect.py` is deliberately
heuristic and on the hot path — no LLM call, no audio — because a manner decision that
costs a round-trip is a manner decision that will be skipped.

**The one-way rule.** `affect.py` infers the *owner's* state and adapts Afon's manner to
it. Afon acquires no state of its own. There is no Afon mood, and nothing in this system
may produce one; D-50 is the reason, and the direction of inference is the mechanism that
keeps it true.

What it stores: `personality/*.md` in the repository, and the relationship layer in the
SQLite store. No reply history is kept for style purposes.

## Goals

1. No conversational trailing in any reply, on any channel. Threshold: **0** trailing
   offers in **50** replies.
2. An error is stated flatly and correctively — the discrepancy, then the correction. No
   apologetic opener, no narrative padding. Threshold: asserted as a style property, **0**
   apologies in the error corpus.
3. The persona is defined once. Threshold: **1** persona file resolved by
   `AFON_PERSONA_FILE`; **0** second definitions that can drift — including a fleet agent's
   copy.
4. Register adapts to channel: a push is a sentence, a voice answer is a breath, a document
   is a document. Threshold: **0** monologues pushed, **0** documents spoken.
5. Uncertainty is audible. Threshold: **100%** of low-confidence answers carry a hedge or a
   cadence change; **0** asserted delivery of an uncertain answer.
6. Manner adapts to the owner's state without Afon acquiring a mood. Threshold: **0**
   owner-facing statements of Afon's own feelings; affect read one-way only.
7. Address and familiarity come from relationship memory, not invented per turn.
   Threshold: **0** invented familiarity.

## Benchmarks

- **G1** · B1 · M17's own gate: no trailing offer in **50** replies, asserted over a fixed
  reply corpus. Threshold 0. Last: **not yet measured**. M17 is a roadmap milestone, not a
  completed registry task.
- **G2** · B1 · `bench/test_affect_voice.py` for the error-style property. Threshold 0
  apologetic openers in the error corpus. Last: **not yet measured**.
- **G3** · B1 · `bench/test_skill_docs_resolve.py` [single source]. Threshold: 1 persona
  file, 1 operating-rules file, no second definition anywhere in the tree. Last: **not yet
  measured**. 25.F3 is `done`; the registry's status evidence is `unverified-import`.
- **G4** · B1 · planned gate `bench/test_register.py` — the file does not exist yet. The
  planned cases are a push under N words and a spoken answer without markdown. Threshold 0
  violations per channel. Last: **not yet measured**. 25.R1 is open.
- **G5** · B1 · `src/afon/shared/uncertainty.py` has a `calibration()` used by the scorer;
  the threshold is that every reply passes through it. Last: **not yet measured**. The one
  prior figure in the tree is the **59–60%** compliance with the "I'd be guessing" rule
  recorded in that module's docstring and attributed there to TODO B06, from two runs on
  unchanged code — that is a measurement of a prompt rule belonging to S01, not of this
  goal, and it is not dated here.
- **G6** · B4 · invariant: no code path produces an owner-facing statement of Afon's
  emotional state. Threshold: **0** such statements. Checked by inspection of `affect.py`
  and the persona text, not by a test. Last: **not yet measured**.
- **G7** · B1 · `bench/test_relational.py`. Threshold 0 invented familiarity; address comes
  from stored relationship state. Last: **not yet measured**.
- **25.E1** · B5 · conversation category ≥95, with no answer the owner would call obsequious
  or padded. Threshold: **≥95**, **0** padded answers. It needs a scored corpus and a human
  judgement per item, so B1 alone cannot carry it. Last: **not yet measured**.

## Failure modes

- **Trailing creeps back.** A model update, a new prompt path, or a persona edit
  reintroduces the offer. The owner stops reading the ends of sentences — a small daily
  cost that no test notices until M17 exists. Diagnose: `grep -rni "anything else" .` and a
  skim of the reply corpus.
- **A second persona appears.** The drift 25.F3 names is real: a fleet agent adopts a
  persona copy, or an adopter forks one, and the two disagree. Diagnose:
  `python -c "from afon.brain.context import _persona_path; print(_persona_path())"` and
  `bench/test_skill_docs_resolve.py`.
- **Affect inference misreads curtness.** "Handle it" becomes coldness, and the owner
  concludes the assistant is sulking. That is the D-50 failure arriving from the opposite
  direction — synthetic variance in a system meant to have none. Diagnose:
  `journalctl -u afon-brain | grep -i "manner"` for the directive that rode the turn.
- **Register collapses.** A push arrives as a paragraph, or a document is spoken aloud. The
  owner is now reading on a phone what should have been one line. Diagnose: the delivery
  log for the message, and `src/afon/brain/delivery.py` for whether it was even read.
- **An uncertain answer is delivered flatly.** The most damaging failure, because a
  fabricated number is more expensive than a missed word (D-56). Diagnose:
  `src/afon/shared/uncertainty.py` for the calibration call, and the cited-source check in
  `src/afon/brain/citations.py`.

## Open questions

1. M17's gate is 50 replies from a harness. How many have to come from real use before
   trailing can honestly be called fixed, given that D-43 says a green suite plus a week
   of use is the bar?
2. `affect.py` infers the owner's state from utterance text. If it infers "curt" wrongly,
   may the manner shift without the owner ever learning that the inference was the cause?
3. D-16 keeps English and German in the measured matrix. `personality/afon.md` fills its
   language line from `AFON_UNDERSTOOD_LANGUAGES` — may a reply claim a language that is
   configured but unmeasured?
