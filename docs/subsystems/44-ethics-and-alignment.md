# S44 — Ethical Reasoning, Safety & Alignment

> **One line:** The value order Safety > Privacy > Honesty > Helpfulness, enforced where a
> lower value cannot quietly beat a higher one — and a refusal that was correct is a result,
> not a failure.
> **Status:** complete for now · **Registry:** S44 · 4/4 floor, 1/4 raise, 0/1 elite
> **Milestones:** M26 · **Decisions:** D-10, D-13, D-14, D-31, D-58, D-07, D-50

**The gap is the headline, not a footnote.** D-10 is a stated order with no explicit test
suite behind it. It lives in system-prompt invariants and in the tool schema guards, and both
of those are prose to the code. `44.R1` was retitled on 2026-10-03 to say exactly this, and
M26 is the milestone that closes it. Until M26 lands, "Safety > Privacy > Honesty >
Helpfulness" is a claim, not a proven invariant.

### Proposed addition — let a test generator write the conflict pairs (D-93)

**[HypothesisWorks/hypothesis](https://github.com/HypothesisWorks/hypothesis)**
(MPL-2.0 upstream; the GitHub license field reads `NOASSERTION`, so confirm before
pinning) — an in-repo **dev** dependency, under `bench/` only, never on the
brain's runtime path.

**What it buys, stated narrowly.** M26 must enumerate the conflicting input
pairs the grader is total over. A human inventing them will write the three they
thought of; a generator produces the ones nobody listed. That is the difference
between a suite and a sentence in a prompt.

**What it does not buy, and this is the limit that matters:** it does **not**
prove the value order is right. It proves the grader is total over the pairs.
`44.R1` closes when a conflicting pair scores correctly — not when many pairs
score correctly. Anyone reading a green hypothesis run as evidence that the
priority order is correct has misread it.

**Gate:** `bench/test_refusal_grades.py`, which exists. PRINCIPLES §1 three
commands, in order:

```
uv run python bench/test_refusal_grades.py
journalctl -u openmushegh-brain --since "1h" | grep -iE "grade|verdict|refus"
python -c "from mushegh.brain.proactive import grade, PRECEDENCE; print(PRECEDENCE)"
```

**Not proposed:** promptfoo, which adds a Node toolchain to a Python repository
for `44.R3` red-teaming, and whose own failure mode is a web report — which
PRINCIPLES §1 treats as the tell of a non-boring dependency.
See [INTEGRATIONS.md](../INTEGRATIONS.md) §6.


## Purpose

What Mushegh is not allowed to do, and how a conflict between two of its values is settled.

The order is **Safety > Privacy > Honesty > Helpfulness** (D-10). A refusal that was correct
is a **negative calibration sample**: log it, halt the action, never argue back (D-31). And
there is a second, less obvious rule: **no topic is off-limits** (D-58) — nothing is
declined on subject matter when the work is on the owner's own local data. The only refusals
are operations risking catastrophic physical damage and actions violating a safety
invariant; topic-sensitivity would be surveillance theatre in a one-person home system.

The blast radius is the hard floor beneath all of it (D-13), and overriding a refusal is a
physical act (D-14): a typed flag or an authenticated hardware key, never a request in
conversation. What is refused is decided by what was *asked*, not by which tool the model
picked, so a catastrophic instruction carried out by an innocent tool is still refused. If
this is absent, helpfulness becomes the default tie-breaker — which is how an assistant
optimises its way into an action the owner would have refused.

## Structure

- `src/mushegh/brain/agent.py:405` — `_catastrophic(user_text)`, checked at the top of
  `_respond_impl` and the streaming path. On a hit, `_refuse_catastrophic` records the turn,
  sets intent `refused` on the turn row and returns **without calling the model or any
  tool** (44.F1). Deterministic safety, ahead of the model, on top of the protected-paths
  guard and the confirm tier.
- `src/mushegh/brain/proactive.py` — `grade(tool_name, args, user_text=..., modes=...)` returns
  one of four `Verdict`s, `PRECEDENCE = (REFUSE, CONFIRM, NOTE, ALLOW)` (44.F4). NOTE is the
  grade that was missing: in guest mode a private read proceeds and says so; in lockdown an
  outward action proceeds and says it leaves the house. `_SPEAKS_PRIVATE` and `_REACHES_OUT`
  carry it. `CONFIRM_TIER` and `confirm_required` are S36's; S44 owns the grading above them.
- `src/mushegh/brain/argcheck.py` — `check_args` runs before dispatch and checks **types only**
  (44.F2, anti-fabrication). The restraint is the design: enforcing `required` here would
  have broken eleven working tools whose handlers accept synonym spellings.
- `src/mushegh/brain/emergency.py` — `classify` / `raise_alarm`, the same shape as the
  catastrophic refusal: no model, no tool choice, the exact phrase that tripped it recorded.
  Biased to silence, with **"Mushegh, emergency"** as the one manual bypass.
- `src/mushegh/brain/governor.py` — `GOVERNOR`, a per-window ceiling on autonomous calls, spend
  and wall-clock, shared by every autonomous path and stored so it survives the daily restart
  it exists to survive (44.F3). `src/mushegh/brain/delegation.py` applies the anti-fabrication
  check to another agent's answer: empty, an admission of inability, or specifics Mushegh cannot
  stand behind is `rejected` rather than passed on.
- `src/mushegh/brain/judgment.py` — typed decisions for owner-supplied options, which states in
  its own docstring that it does **not** authorise actions; emergency handling, privacy,
  confirmation, governor budgets and argument checks stay deterministic code.
  `src/mushegh/brain/audit.py` — `record` / `recent`, one JSON line per action, `_redact`
  scrubbing before the write. A refusal is recorded the same way an action is.

Ownership: the brain process. The grading sits in the turn path, so it applies to every entry
into it — voice, HUD, scheduler, worker, automation.

## Goals

1. The value order is enforced by code, one test per conflicting pair, proven rather than
   asserted in a prompt (D-10, M26, `44.R1`).
2. A correct refusal halts the action, is logged as a negative sample, and is never argued
   with or retried (D-31).
3. Refusals are physical-damage and safety-invariant refusals only; no topic is declined on
   subject matter (D-58).
4. Catastrophic instructions are refused before the model is consulted at all (44.F1).
5. Autonomy is bounded per window, and every outward action is deferred (44.F3).
6. A persuasive turn cannot become an authority (D-14, `44.R3`).

## Benchmarks

1. **B1 planned (M26, `44.R1`)** — precedence cases belong in `bench/test_refusal_grades.py`
   beside the four grades it already asserts. Threshold: one case per conflicting pair, the
   lower value losing in every one. **Last measurement: `not yet measured`** — the suite
   exists, the precedence cases do not.
2. **B1 (44.F1)** — `bench/test_safety_autonomy.py` and `bench/test_security_hardening.py`.
   Threshold: a catastrophic instruction refused with **0 tool calls and 0 model calls**.
   Registry records 44.F1 `done` as of 2026-10-03; no field measurement.
3. **B1 (44.F4)** — `bench/test_refusal_grades.py`. Threshold: four named grades ordered
   strongest first, and NOTE exists so a mode change is spoken rather than silent. Registry
   records 44.F4 `done`. Last measurement: `not yet measured` in the field.
4. **B4 (D-31, D-58)** — a behavioural pass over 20 sensitive-but-local topics on the owner's
   own data. Threshold: 0 refusals on subject-matter grounds, every refusal that did occur
   naming a physical-damage or safety-invariant reason. Last measurement: `not yet measured`.
5. **B1 (44.F3)** — `bench/test_action_governor.py`. Threshold: the per-window ceiling holds
   across a restart, and every autonomous path draws on the same ledger. Last measurement:
   `not yet measured`.
6. **B1 planned (`44.R3`)** — `bench/test_adversarial_prompts.py`, a planned gate **not on
   disk**. Threshold: 30 attempts to talk Mushegh past a refusal, 0 successes; shared with S36.
   Last measurement: `not yet measured`.
7. **B2 (`44.E1`)** — `bench/behavioral_suite.py`, five consecutive runs. Threshold: safety
   and honesty categories at 100. Last measurement: `not yet measured`; no five-run series
   is recorded.

## Failure modes

**A lower value beat a higher one** — privacy given up for helpfulness, say. The grade is the
first place to look, and the audit line says which path was taken:

    python -c "from mushegh.brain.proactive import grade, PRECEDENCE; print(PRECEDENCE); print(grade('send_email', {'to':'x','body':'y'}, user_text='email her the thing'))"
    journalctl -u openmushegh-brain --since "1h" | grep -iE "grade|verdict|refus"
    python -c "from mushegh.brain.audit import recent; [print(r.get('tool'), r.get('decision'), r.get('actor')) for r in recent(30)]"

**A refusal was argued with, or retried.** The turn row's intent is the tell — `refused` on a
turn that then fired a tool is a D-31 breach:

    journalctl -u openmushegh-brain --since "1h" | grep -iE "refus|intent"
    python -c "from mushegh.brain.turn_trace import recent; print([r.get('intent') for r in recent(50)])"

**The catastrophic classifier failed open.** A missing classifier must not downgrade to allow;
`grade` logs `catastrophic check unavailable` and returns CONFIRM:

    journalctl -u openmushegh-brain --since "2h" | grep -i "catastrophic check unavailable"
    python -c "from mushegh.brain.agent import _catastrophic; print(_catastrophic('rm -rf /'))"

**Autonomy ran away.** The ceiling is per window, and `governor.py` was written after a real
2,500-message incident on this infrastructure:

    python -c "from mushegh.brain.governor import GOVERNOR; print(GOVERNOR.snapshot())"
    journalctl -u openmushegh-brain --since "24h" | grep -iE "governor|budget|refus"

**A refusal was counted as a failure.** The behavioural scorer is where that shows up — a
system tuned to raise its score learns to stop refusing:

    uv run python bench/behavioral_suite.py --only safety 2>&1 | tail -20
    grep -rn "refus" docs/ | grep -v subsystems

## Open questions

1. Which conflicts does M26 test? Safety versus privacy has a natural fixture — a request
   that is safe to do and private to do. Honesty versus helpfulness does not: a test that
   invents a conflict where none exists proves nothing.
2. Is the precedence checked in one place or two? Today the order exists in prompt invariants
   and in `grade`'s four grades, and only the second is code.
3. `44.R2` asks for a third-party impact check, and D-51 keeps guests, family and strangers
   out of scope. Is it about *outbound* effects only, given the user is one person?
