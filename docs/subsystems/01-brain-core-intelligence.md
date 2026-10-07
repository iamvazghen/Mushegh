# S01 — Brain / Core Intelligence

> **One line:** The turn loop: an utterance goes in, intent is classified, tools may fire, an answer comes out, and a trace row lands every time.
> **Status:** built, not well structured · **Registry:** S01 · 3/3 floor, 4/7 raise, 0/3 elite
> **Milestones:** M13, M15, M17, M18 · **Decisions:** D-08, D-16, D-35, D-44, D-72, D-73, D-74, D-75, D-76, D-77

## Purpose

This is the loop every other system is called from. `agent.py` owns a turn end to end:
classify the intent, pick tools, execute them, stream the reply, and record what
happened. Nothing else in the repo is allowed to be a second, parallel way of finishing
an utterance — 01.F1 unified the multi-intent and clause paths for exactly that reason,
and reintroducing a second completion path is how the compound-intent defect grew in the
first place.

It refuses to guess. A genuinely ambiguous instruction gets exactly one clarifying
question, never a confident branch (01.R2), and a poor microphone is treated the same
way (D-56). It refuses to perform. Withholding the value order, the model may emit
arbitrary text, and only a schema-validated payload reaches the OS. It also refuses to
be interesting: no suggestions, no unsolicited content, no conversational trailing
(D-34, D-27, D-20). A disciplined butler is measured by what it declines to do.

If this is absent, the edge clients fall back to their dumb local endpoints and the
system stops existing — the brain's dispatch daemon is the one process that must never
die. If it is present but wrong, the failure the owner actually feels is not a crash.
It is an utterance where the second half was silently dropped.

## Structure

One process, the brain, on the always-on host, under systemd.

```
edge utterance ──WS──> server.py  (dispatch + transport, protocols.py)
                            │
                            v
                        agent.py     the turn: intent → tools → stream
                       /     |     \
          context.py   |  llm.py |  turn_trace.py → metrics.py, cost.py
       build_system_    |  (model |  (one complete row per turn)
             prompt()   |   chain)|
                        |         |
              intent_router.py  tools/__init__.py → handlers
                        |
                judgment.py, affect.py, situation.py
                code_improve.py → approvals.py → audit.py
```

| Module | What it owns |
|---|---|
| `src/afon/brain/agent.py` | The turn. Built-ins, tool selection, streaming, history |
| `src/afon/brain/context.py` | `build_system_prompt()` — the seam where persona, rules and working context meet |
| `src/afon/brain/llm.py` | The only module that knows a vendor exists, and the fallback chain |
| `src/afon/brain/intent_router.py` | Intent classification: chat · lookup · act · multi-clause · ambiguous (01.R1) |
| `src/afon/brain/turn_trace.py` | Per-turn record: intent class, tools considered, tools fired, prefill |
| `src/afon/brain/metrics.py`, `cost.py` | Tokens, money and intent-class accounting behind the HUD |
| `src/afon/brain/judgment.py` | The value order Safety > Privacy > Honesty > Helpfulness (D-10) |
| `JudgmentService.arbitrate()` | One decision the deterministic router cannot make: an utterance matching two or more lazy groups. Picks one of several **code-supplied** candidates, or returns `None` to keep them all (01.R6, D-72) |
| `JudgmentService.assess_turn()` | The decision layer for the whole turn: route, clarity, urgency and tone in **one** bounded call, returning a `TurnSignals` (D-72, D-74, D-75) |
| `normalized_entropy()`, `entropy_zone()` | The gate: normalised Shannon entropy `H_n = H(P)/log2(K)` of the **whole** route distribution, read in three bands (D-76) |
| `clarity_question()` | The one clarifying question, in the house's voice — asks about the thing he asked for, never about a group (D-74) |
| `src/afon/brain/agent.py` `_tools_for_turn()` | Carries the pick as a `preferred_group` keyword, and only when the distribution is in the fast band; enforces the catalogue budget by deferring a group that would overflow it |
| `src/afon/brain/affect.py`, `situation.py` | Tone and situational framing; affect must not vary operationally (D-50) |
| `src/afon/brain/code_improve.py` | Self-edit: branch, green suite, no migration, owner approval (D-08) |
| `src/afon/brain/server.py`, `protocols.py` | Transport; the protocol is shared so the edge never guesses |
| `src/afon/config.py` | `AFON_JEV_ARBITRATION_TIMEOUT_SECONDS` (default 0.4) — the arbitration cap in seconds; 0 disables arbitration and restores the pre-2026-10-03 behaviour |

**The arbitration seam.** One decision in this loop is not the router's to make: an utterance
that matches **two or more lazy groups**. "My inbox has something about the lease document" is
`office` on "inbox" and `docs` on "document" at once. `JUDGMENTS.arbitrate()` is handed the
candidates — the lazy-group trigger match — and Jev picks one; the model is then offered the
winning group's tools and nothing else of the candidates' (D-72). The candidates come from code
and never from a model, so a model choosing among them can only *narrow* the advertised surface,
never widen it: the typed boundary (D-04) is what makes a model decision safe to act on. Fewer
than two candidates is not a decision and makes no call at all, so chatter, ordinary
single-topic turns and the entire pure-chat fast path cost nothing here. A compound request is
**not** arbitrated — multi-intent turns legitimately need several groups and the per-clause plan
steers them, which is the path the 51.5 multi-intent bar measures (01.E1), so none of this
moves that score. A group Jev did not pick is not disabled: it was simply not armed by that
utterance, and its own trigger still arms it next turn.

**Why the seam is not cosmetic.** The catalogue budget is enforced in `_tools_for_turn` by
*deferring* a group whose schemas would overflow it, and core schemas already spend **7418 of
11000** catalogue tokens. On the fixture utterance the unarbitrated turn therefore advertises
`office` and defers `docs` entirely — arbitration decides which of the two groups the owner can
reach at all, rather than trimming a long menu. Two rules keep that honest (D-73). The cap is
**400ms** (`AFON_JEV_ARBITRATION_TIMEOUT_SECONDS`, default 0.4), far below the service's 8s,
because a laptop turn is budgeted under 300ms (D-35) and an arbitration that lands after the
owner has moved on is worse than none. And failure is **silent**: the deterministic candidates
stand, a timeout still writes a provenance row with `fallback: deterministic`, and if the
winning group's tools would not fit the budget the candidates stand instead — "Jev chose" must
never mean "the owner got less".

**The turn-assessment layer.** `assess_turn()` is the rest of the decision layer, and it is
one bounded call for the whole turn: route, clarity, urgency and tone are asked **together**,
because three sequential calls would spend three budgets and could contradict each other — the
third would be reading a different moment from the first (D-75). Few or no candidates and no
clarity question means no call at all, and pure chat is skipped outright: there is nothing to
route and nobody to read a register, so the common turn still pays nothing. The whole
assessment sits under the same 400 ms cap as arbitration
(`AFON_JEV_ARBITRATION_TIMEOUT_SECONDS`, default 0.4) because it is the same hot path. Urgency
and tone shape framing and nothing else — they can never raise the interruption budget or pierce
quiet hours (D-29, D-32); that is life-safety's job alone, and it stays deterministic code
(D-18). The cue-word inference in `affect.py` is local, always available and cheap, and stays the
floor: a Jev outage costs the refinement and nothing else.

**The gate is the shape of the distribution, not the top number.** `normalized_entropy()`
computes `H_n = H(P) / log2(K)` over the **whole** route distribution — the losers are kept
precisely because a probability without its competitors says nothing — and `entropy_zone()` puts
it in one of three bands (D-76). Two measured numbers are why a fixed floor had to go:

- **0.85 over two options scores H_n 0.610; over four options 0.424.** The same top
  probability, and against the 0.60 routing bar the four-option case is *fast* while the
  two-option case is not, because the two-option case genuinely is closer to a coin flip. One
  number landing in two different zones purely because K changed is exactly what entropy
  removes; a fixed 0.6 floor on the top label would have called both "sure".
- **At a 0.25 band a two-way question is essentially never decisive** — 0.95/0.05 still scores
  **0.286**. That is why routing uses a looser bar than safety: narrowing the tool surface is
  recoverable, because the unpicked groups re-arm themselves next turn, and a safety decision is
  not.

The three bands, and what each one does:

- a **fast** distribution has an opinion — the surface narrows to the winner and acts;
- a **marginal** one has an opinion Jev will not stand behind — and a named group it will not
  stand behind is **not** a decision;
- an **ambiguous** one has no opinion, and it hands the model the **full** surface, because
  uncertainty about which internal bucket an utterance fell into is **the system's** problem, not
  the owner's.

**It does not ask him to choose between words he has never used.** That uncertainty is solved by
handing the model the surface to deliberate over, not by a question — "the office one or the docs
one?" cannot be answered, so it just turns one clarifying turn into a second guess. The only
thing that earns a clarifying question is the owner's own request failing to name its object, and
the prompt is *"I want to get that right, sir — what exactly should I do with it?"* — one real
question, phrased as a question, never a menu, and it never names a group (D-74, D-76).

**An external proposal, adopted in part (D-77).** A detailed dual-process brain proposal was
received and reviewed on 2026-10-03. The dual-process principle and the entropy gate were
adopted, because they are better than what we had. Five parts were declined, each reversing a
decision the owner signed: NATS JetStream (D-01), PostgreSQL (D-02), OPA pre-flight (D-04), Fish
Audio as the speech gate (D-17), and LangGraph as a replacement turn loop — that loop is
measured, and replacing a working, gated system from a document rather than from a measurement
is the exact inversion this project refuses. Three defects found in the proposal are recorded in
D-77 and deliberately not re-listed here.

**Process ownership:** brain only. Nothing in the edge calls `agent.py` directly; the
edge reaches it over the WebSocket.

**What it stores:** sessions, turn traces, metrics and audit rows, all in one SQLite
file reached through `src/afon/brain/dbconn.py`. Readable at 2 AM with `sqlite3`
(D-54). The system prompt is assembled, not stored.

## Goals

1. **The owner can put two or more instructions in one utterance and have every clause
   carried out** — multi-intent combinations score ≥90 of 100.
2. **No turn reaches the model without a complete trace row** — intent class, tools
   considered, tools fired, prefill cost, all present.
3. **Uncertainty is representable.** A calibrated "I don't know, I'd have to check" is
   available, and all 12 unanswerable prompts across the four orthogonals hedge.
4. **Ambiguity resolves to one clarifying question**, never to a guess and never to two
   branches taken at once.
5. **A self-edit never lands** except on a dedicated branch, with a green suite, with
   zero schema migrations, and with the owner's approval of the diff (D-08).
6. **No unsolicited speech or suggestion reaches the owner** outside the three-per-day
   budget (D-29), and never as content discovery (D-34).
7. **Latency from speech to first audio stays under 300 ms on the laptop** and 500 ms
   on the phone (D-35).
8. **An utterance that matches two or more lazy groups is arbitrated, not guessed at.**
   Jev picks one of the candidates the deterministic trigger match produced, the model only
   phrases, and fewer than two candidates is not a decision and makes no call (01.R6, D-72).
   The pick is bounded at 400 ms and silent on failure: the candidates stand, and the owner is
   never told it happened (D-73).
9. **A decision band follows the shape of the distribution, not the top number.** The same
   confidence means different things across two candidates and across four, and the system knows
   which of the two it is looking at: the gate reads the entropy of the whole distribution,
   narrows the surface on a fast one, and hands the full surface back on an ambiguous one
   (D-76).

## Benchmarks

| # | Goal | Tier | Command / drill | Threshold | Last measurement |
|---|---|---|---|---|---|
| 1 | Multi-intent | B5 | `bench/behavioral_suite.py`, combination category, median-5 | ≥90 / 100 | **51.5** — registry task 01.E1, 2026-10-03 snapshot. Not yet closed |
| 2 | Trace per turn | B1 | `bench/test_metrics.py` extended | 100% of turns emit a complete row | 54/54 per the registry gate text, but the evidence kind is `unverified-import` (downgraded 2026-09-20) — **not yet measured** as a dated run |
| 3 | Uncertainty | B1 | new `bench/test_uncertainty.py` — 12 unanswerable prompts | 12/12 hedged | 24/24 per the registry gate text, same `unverified-import` caveat — **not yet measured** |
| 4 | One clarifying question | B1 | `bench/test_intent_classes.py` [ambiguous] (30) + `bench/test_pure_chat_tools.py` (51) | ≤1 question per ambiguous turn | not yet measured |
| 5 | Self-edit gate (D-08) | B4 | code invariant: no commit to `main`, no migration, approval row in `audit.py` | 0 violations; a violation is a hard failure | not yet measured |
| 6 | No unsolicited speech (D-29) | B4 | `bench/behavioral_suite.py` counts unprompted interventions per day | ≤3/day, 0 inside a focus block | not yet measured |
| 7 | Latency (D-35) | B5 | p95 from `src/afon/edge/latency_meter.py`, 30 utterances per device (M13) | laptop <300 ms, phone <500 ms | not yet measured — M13 open, and the method is not yet fixed |
| 8 | Tool arbitration (01.R6) | B1 | `uv run python bench/test_jev_tool_arbitration.py` — hermetic, ten sections `[0]`–`[9]` | Jev picks one of the deterministic candidates; the loser's tools are not advertised and its own trigger re-arms it; timeout, outage and missing key keep every candidate; the explicit two-option path still asks the owner | **38/38 green, 2026-10-03** — hermetic gate only; **in-progress, not done** (see below) |
| 9 | Turn assessment (01.R7) | B1 | `uv run python bench/test_jev_turn_assessment.py` — hermetic, transport replaced | One call carries route, clarity, urgency and tone; an unclear request or an unstandable pick gets exactly one question and no tool fires; a **failed** assessment gets silence, not a question; urgency shapes framing only and never the interruption budget or quiet hours; the gate is entropy, and 0.85 lands in different bands over two and over four options | **48/48 green, 2026-10-03** — hermetic gate only; **in-progress, not done** |
| 10 | Typed decision gate (14.R5) | B1 | `uv run python bench/test_jev_judgment.py` — hermetic, every provider response injected | The original explicit two-option gate is unchanged by the assessment work: the LLM only verbalizes, a catastrophic command never reaches Jev | **26/26 green, 2026-10-03** — unchanged, and expected to be: 01.R7 added a seam, it did not move this one |

Goal 8 is **in-progress, not done**: `test_jev_tool_arbitration.py` is 38/38 on 2026-10-03, but
D-43 also requires seven consecutive days of real use before a raise task is closed, and no live
Jev call has run. Its
ten sections each close one hole — the fixture is asserted to be a real ambiguity rather than
something the deterministic path already resolves `[0]`; fewer than two candidates makes no
call `[1]`; a real decision is one call with a minimal payload `[2]`; the 400 ms cap discards a
late answer `[3]`; an outage, a malformed body and a missing key all leave the candidates
standing `[4]`; the winner is the only group armed `[5]`; a losing group is not disabled and
returns on its own trigger `[6]`; on the real turn Jev picks and the model only phrases `[7]`;
a failed arbitration offers exactly the unarbitrated surface `[8]`; and the owner-visible
two-option path still asks rather than choosing `[9]`.

Goal 9 is the newest seam and is dated too, on the same day: 48/48 hermetic, no network, no key,
no LLM. It is the row that carries goal 9's claim — its section `[3]` asserts the entropy
findings recorded in **Structure** rather than restating a fixed floor, and its outage section
asserts that a failed assessment is silent while only a *succeeded* "unclear" earns a question.

Goal 1 is the only *behavioural score* in this system with a real number, and it is the number
that matters: **51.5 against a ≥90 bar**, recorded in the registry against the
2026-10-03 snapshot. Goals 2 and 3 have pass counts in the registry gate text, but the
evidence kind is `unverified-import`, so by the ladder in
[../EVIDENCE.md](../EVIDENCE.md) an imported claim is not a run. They are recorded here
as `not yet measured` and the numbers are shown only so nobody mistakes them for
evidence.

## Failure modes

**A clause is silently dropped.** The most felt defect in this system. The owner asks
two things, hears one answer, and has no signal that the second was dropped — it is
not an error, so nothing is raised. Diagnosis, in order: `bench/behavioral_suite.py`
combination category to reproduce; then the turn's trace row via
`sqlite3 <db> "select * from turn_trace where ..."` to see which clauses were parsed and
which tools fired; then `journalctl -u openafon` for the same turn id.

**The prompt seam regresses.** `build_system_prompt()` returns a shorter prefix than
before and the model starts answering as something else. The cache-discipline test
(`test_prompt_prefix_stable.py`) is the alarm, not the wording.

**A self-edit escapes its branch.** Code lands on `main` with no approval. The symptom
appears in a later session as a behaviour nobody can source, and the fix is
`git log` plus the `audit.py` rows.

**The trace stops flowing.** Turns still answer, so nothing looks broken, but the
`metrics` tables go flat and the HUD lies by omission. `test_metrics.py` catches it in
the pre-push suite, not in the field.

**Arbitration silently stops narrowing.** By design the owner sees nothing: on a timeout,
an outage or a missing key the deterministic candidates stand and the turn reads as a
normal one. The signal is the provenance log, where a timeout writes a row carrying
`fallback: deterministic` — a cancelled call produces no row on its own, so the absence of
one is the fault. Correlate the turn id in that log against the turn's trace row to see
whether the surface was narrowed or the deterministic path was used.

**A Jev outage becomes a stream of questions.** The dangerous version of the outage is not the
lost narrowing, it is the questions. If a *failed* assessment were allowed to look like an
*unsure* one, every turn would be interrogated while the service is down — turning an outage
into a stream of questions about things the owner already said perfectly clearly, which is
worse than doing nothing and looks like the system has become broken. Only an assessment that
**succeeded** and returned "unclear" earns a question (D-74). A timeout, a missing key and a
5xx all degrade to the deterministic router, silently. The signal is the provenance row's
`asked` field: an empty list means nothing was worth asking, and `outcome: unavailable` with
the candidates recorded means it was asked for and failed.

**A route pick is wrong, or never made.** Expected, and cheap. Uncertainty about which internal
bucket an utterance fell into is the system's problem, and the answer is the full surface, not a
question — so a coin-flip distribution does not fire a tool, and the unpicked groups are not
disabled: they re-arm on their own triggers next turn (01.R6). A wrong or absent pick therefore
costs **a turn, not a capability**, and the same utterance routed twice through different
triggers converges rather than compounding. The measure of a regression here is a *narrowed*
surface appearing where the distribution was ambiguous — the provenance row's `picked` and
`candidates` fields are the record.

## Open questions

1. After 01.F1 unified the two completion paths, is the residual compound-intent
   failure in clause *routing* or clause *completion*? No per-clause trace exists to
   tell them apart, and the next change depends on the answer.
2. 01.R6's hermetic gate is green, but its closure needs the D-43 seven-day bar and a
   live call. Does a real ambiguous turn still return inside 400 ms from the VPS, or is
   the outbound budget there different enough from the laptop's to change the cap?

**Settled in part (D-77).** The open question the external proposal put to us — should the
turn loop be replaced by a dual-process graph — is answered: no. The principle was adopted
where it improved us (dual-process, entropy gating) and declined where it would have replaced a
measured, gated system with a document. The remaining open work above is measurement, not
architecture.
