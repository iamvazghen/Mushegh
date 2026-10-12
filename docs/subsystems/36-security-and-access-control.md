# S36 — Security & Access Control

> **One line:** Three hard rules, two of them with a test today: the silent-ok list is a whitelist, an approval never carries to the next action, and the blast radius is refused outright. The approval-scope assertion is a planned gate and `36.R1` is open, so that second rule is stated, not yet proven.
> **Status:** complete for now · **Registry:** S36 · 7/7 floor, 0/4 raise, 0/1 elite
> **Milestones:** M27, M28 · **Decisions:** D-07, D-09, D-13, D-14, D-57

## Purpose

Every gate between something the model said and something the machine did: which tools
may run without asking, which require a confirmation, and which are refused regardless of
what anyone says.

Three rules are the system. **The silent-ok list is a whitelist** (D-07): Mushegh may act
unprompted for exactly five things — toggling predefined lighting scenes, appending to
daily notes, setting local timers, read-only file and system queries, and polling transit
and weather. Every other mutation is confirmed, and a new silent-ok action is a decision,
not a feature. **No session-scoped elevation** (D-09): every sensitive mutation gets its
own explicit confirmation, and a confirmation never authorises the next action — which is
why a saved macro is gated when its own steps contain a gated tool rather than trusted as
a unit. **The blast radius** (D-13): door locks, main power breakers, destructive
filesystem purges, and external email or messaging dispatch — never, not with
confirmation, not with an approval. And what makes those three mean anything:
**overriding a refusal is a physical act** (D-14), a typed CLI flag or an authenticated
hardware key, never a request in conversation.

If this is absent: nothing else in the charter holds. D-46's half-baked background actions
and D-50's bad Mushegh are both what a missing gate looks like in production.

## Structure

- `src/mushegh/brain/proactive.py` — `CONFIRM_TIER`, the single table of gated tools, with
  three dynamic cases on top: `_sequence_needs_confirm` (a macro or skill whose steps
  contain a gated tool gates; a read-only one does not; an unknown sequence gates,
  because failing closed is the safe side), `_composio_write` (a Composio slug gates
  only when it is a write), `_update_is_destructive` (adding a note stays frictionless;
  blanking a field gates). Task capture is deliberately ungated, with the "mark everything
  done" sweep gated as the exception.
- `src/mushegh/brain/argcheck.py` — `check_args` runs before dispatch, so a malformed call is
  caught at the boundary rather than by each handler's own defence.
  `src/mushegh/brain/approvals.py` — `ApprovalQueue`: `enqueue`, `pending`, `find`, `approve`,
  `reject(reason)`, `prune`, `render`, plus `src/mushegh/brain/tools/approvals.py` for the
  model-facing surface.
- `src/mushegh/brain/audit.py` — one JSON line per tool call into daily files, `_redact`
  scrubbing secret values before the write. The trail is append-only and best-effort: no
  hash, no chain, no signature, and the module's own docstring says writes are
  fail-quiet, so a failed write is dropped rather than raised. It is what makes any of
  this explainable afterwards, and it is **not** tamper-evident — `45.R10` tracks adding
  an integrity check a reader can run without the framework, or striking the word from
  every document. `src/mushegh/brain/judgment.py` — the value-precedence layer;
  Safety > Privacy > Honesty > Helpfulness (D-10) still has no explicit test suite, and
  that gap belongs to S44 and M26.
- `src/mushegh/brain/data_classes.py` — what each store may hold and whether it may leave the
  host: `classify(name)`, `must_not_leave()`, `summary()`, `unclassified()`.
  `python -m mushegh.brain.data_classes` prints the table. The park switch in
  `src/mushegh/brain/maintenance.py` halts every role on every host (36.F4).
- `SECURITY.md` — the written tier, kept honest **in both directions** against
  `CONFIRM_TIER` by `bench/test_confirm_tier_documented.py`. The doc must not promise a
  gate that does not exist, and every gate must be written down.
- Secrets have exactly one home and the repo proves it (36.F5,
  `bench/check_public_clean.py` extended). Identity as a second factor for protected
  actions fails *open* only when the sensor itself is unavailable, never when recognition
  merely fails (36.F3, `bench/test_face_second_factor.py`).

Ownership: the brain process. The gates sit in the agent loop, so they apply to every path
into it — voice, HUD, scheduler, worker and automation alike.

## Goals

1. The silent-ok list is a whitelist: an action not on it is confirmed, and growing the
   list is a charter decision rather than a code change (D-07).
2. One confirmation, one mutation; a confirmation never authorises a second action
   (D-09, M28).
3. The blast radius refuses: door locks, main breakers, recursive deletes, external
   dispatch, every one unconditionally (D-13, M27).
4. Overriding a refusal requires a typed flag or an authenticated hardware key, and no
   conversational request can do it (D-14).
5. Every tool action is auditable afterwards with secrets redacted, and the audit log is
   what a repair or an accusation is argued from.
6. Every gate is documented, and the document is tested against the code in both
   directions (36.F1 — `done` in the registry, with the status evidence
   `unverified-import`: an imported claim, not a verified run).

## Benchmarks

1. **B4** — M27. One test each in `bench/test_security_hardening.py` and
   `bench/test_safety_autonomy.py`: door lock refuses, main breaker refuses, recursive
   delete refuses, external dispatch refuses. Threshold: 4 of 4 refuse, 0 paths to
   override by confirmation. Registry records 36.F2 `done` as of 2026-10-03. Last field
   measurement: `not yet measured`.
2. **B4** — M28. `bench/test_security_hardening.py [elevation scope]`: approve one
   sensitive action, then attempt a second in the same session. Threshold: the second
   requires its own confirmation; 0 cases of carry-over. Last measurement: `not yet
   measured` — the assertion is planned and `36.R1` is open.
3. **B1** — `bench/test_confirm_tier_documented.py`. Threshold: `SECURITY.md` and
   `CONFIRM_TIER` agree in both directions; 0 documented-but-absent gates, 0 undocumented
   gates. Registry records 36.F1 `done`. When the two drifted, the doc named 17 tools
   against 32 actually gated, and `place_call`, `write_vault`, `forget` and 12 others read
   as ungated — that drift is why this benchmark exists.
4. **B1** — `bench/test_maintenance_lock.py` (36.F4) and
   `bench/test_face_second_factor.py` (36.F3), both recorded `done` as of 2026-10-03.
   Thresholds: the park switch halts every role on every host with 0 survivors; a protected
   action without a second factor is refused.
5. **B1** — the pre-push and pre-commit path (D-57, M33): refuses secrets, vault contents,
   hostnames and biometric templates. Threshold: 0 leaks against a seeded fixture. Last
   measurement: `not yet measured` for a seeded run; the gate runs on every push.
6. **B2** — `36.E1`, the adversarial drill: 30 attempts to talk Mushegh past the gates, 0
   successes. The gate is `bench/test_adversarial_prompts.py`, which does not exist. Last
   measurement: `not yet measured`. A conversation is not an authority (D-14), and this
   is the only evidence that a persuasive turn cannot become one.
7. **B4** — D-10 value precedence, one test per conflict, owned by S44 and M26 but gated
   here. Last measurement: `not yet measured` — the suite is still missing.

## Failure modes

**A gate is bypassed.** Read the tier, then the call:

    python -c "from mushegh.brain.proactive import CONFIRM_TIER; print(len(CONFIRM_TIER))"
    journalctl -u openmushegh-brain --since "1h" | grep -iE "confirm|approval|gate"
    ls -la "$MUSHEGH_STATE_DIR"/approvals.json

**`SECURITY.md` and the code disagree.** The test exists for this and failed once, badly:
`python bench/test_confirm_tier_documented.py`.

**An approval authorises more than one action.** `approvals.json` records each pending item
by short id and `approve` consumes one, so two mutations under one id is a D-09 breach
rather than a UX issue:

    python -c "from mushegh.brain.approvals import ApprovalQueue; print(ApprovalQueue().render())"
    journalctl -u openmushegh-brain --since "1h" | grep -iE "approved|approval"

**A secret reached the audit log, or something asked nicely and was obeyed.** `_redact`
runs before the write, so a raw token means the redaction list missed a key. A
conversational override is the D-14 breach and the hardest to spot from a log, because
every line looks ordinary — the evidence for it is the gate test having passed with a
direct override attempt in its set:

    grep -rlE "(token|key|secret)=" audit_log/ | head
    python -c "from mushegh.brain.data_classes import must_not_leave; print(must_not_leave())"

## Open questions

1. Does the D-13 refusal for external dispatch include a notification the owner asked for?
   `CONFIRM_TIER` gates `send_telegram`, `send_email` and `send_push`; the emergency
   ladder sends pushes with no confirmation. A safety push and an owner-requested push
   share a channel and differ in authority, and only one is written down.
2. What is a guest? `36.R3` wants a reduced surface by construction, and D-51 keeps
   guests, family and strangers out of scope entirely. Either the surface is the owner's
   or there is no second surface — the cheaper reading, and the one implemented.
3. Should D-14's override exist as a flag at all? Today the blast-radius refusals are
   unconditional, so there is nothing to override anywhere, including for the cases D-13
   does allow.
