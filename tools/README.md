# `tools/` — probes, verifiers and one-off diagnostics

Everything here is a **measurement**, not a gate. Gates live in `bench/` and are registered
in `bench/run_all_tests.py`. A tool in this directory can be wrong without anything going
red, which is why each entry below says what question it answers and — where applicable —
whether it has been *disproved*.

Written during the 2026-10-08 pass over S01, in the order the questions came up.

## Standing verifiers (reusable, currently trustworthy)

| script | question it answers |
|---|---|
| `verify_surface_claims.py` | Is every `**Surfaces**` module in `SYSTEMS-DETAILS.md` actually reachable? Imported, dispatched by path, or launched by a module launcher. **Also imported by `bench/test_doc_integrity.py` section 4 — edit that, not this.** |
| `verify_env_template.py` | Can a fresh machine boot from `.env.example`? Loads `Settings` against it rather than predicting what would happen. |
| `category_coverage.py` | Which categories can the scorecard measure, and is a thin one thin by design or blocked by a credential declaration? |
| `list_tool_names.py` | What does the registry actually contain? Exists because writing a scenario against a tool name that does not exist is worse than not writing it. |
| `probe_unrouted_tools.py` | Which core-advertised tools can no route reach? Superseded by the gate `bench/test_tool_reachability.py`, which asserts the invariant rather than reporting it. |
| `check_hedge_match.py` | Does the calibration scorer see the model's apostrophes? Carries the ASCII-vs-typographic control that motivated the fix in
`src/afon/shared/uncertainty.py`. |
| `audit_exempt_routes.py` | **Audits the new gate itself.** `test_tool_reachability.py` requires every unrouted core tool to be exempt *with a reason*, and those 37 reasons were all written today, from reasoning about each tool's name rather than from testing it. This asks whether a plainly-implying request actually reaches them. Result: **1 of 12.** |
| `probe_jev_live.py` | Can this host reach JEv at all, and is the failure a network or a missing credential? Separate the two, because `JudgmentService` short-circuits before HTTP when the key is absent. |
| `probe_notion_residue.py` | How many `behavioral-suite-temp` rows has the suite left in the owner's real Notion? Read-only. |
| `probe_mode_clear.py` | Does a turn that says "focus mode is off" actually turn it off? Checks state, not the sentence — which is how a false state claim was caught. |

## Diagnostics that earned their keep, kept for the next time

| script | question it answers |
|---|---|
| `measure_jev_arbitration.py` | Does live arbitration fit its 400 ms cap, and how much does it vary? |
| `measure_reuse_benefit.py` | What does reusing an HTTP client buy, measured both ways with the same service and cap? |
| `diagnose_timeout_interval.py` | Is a timeout honoured, measured with teardown excluded? Found that a ~1 s "overshoot" was `aclose()`, not an ignored deadline. |
| `diagnose_jev_transport.py` | What does the JEv HTTP transport actually return, uncapped? |
| `probe_chain_flakiness.py` | Why does a compound chain fail some attempts? **Calls `bs._cleanup()` per turn — without it the probe manufactures a fake crisis** (the fact is already in memory, the model answers from it, and the reply that looks like fabricated tool use is true). |
| `probe_prompt_salience.py` | Is the calibration rule present-but-ignored, or merely not salient? A/B on the live agent. |
| `probe_clarification_drift.py` | Is `needs_clarification` a false positive, or is the request genuinely ambiguous? **Tests the counter-hypothesis too**, which is what stopped it being reported as a brain defect. |
| `probe_clause_plan_for_planning.py` | Does the clause router see a request as tool-shaped, or is there nothing to force? Separates a routing gap from a forcing bug. |
| `probe_planner_reachability.py` | Were the tools the model ignored even on offer? |
| `diagnose_completion_step.py` | What does `_Completion.step` see and decide for a given turn? Wraps the method at runtime; modifies no source. |
| `probe_unknowable_replies.py` | What does the brain actually SAY to an unknowable, and how does the scorer read it? |
| `diagnose_clause_offer.py` | What tool list does a turn advertise, and in what order? |

## Known-defective — do not trust

**`check_memory_state.py`** — written to test whether `STORE.forget()` removes facts, and
it is not a valid instrument. It calls `forget_all` as a *read accessor*, which is
mutating: it deletes facts and then one gets re-learned mid-measurement. Discarded rather
than reported. `check_cleanup_works.py` superseded it and reports `forget()` results
honestly.

**`probe_false_clarification.py`** — measures correctly but was misread by me. It compares
a live `assess_turn` against the reply from a *separate* `respond()`, and JEv is
intermittent, so the two disagree. It is what sent me looking for a "clarification
false positive" that turned out to be my own ambiguous scenario.
`probe_clarification_drift.py` is the one to use.

**`probe_tool_backed_unknowns.py`** — reports `tools fired: NONE` for prompts whose tools
demonstrably fire. **Its capture does not work in that process**; the agent's own log is
the authority. Used as-is it "proved" Afon invents weather and prices with no tool behind
them, which is false — `run_all_tests`-style log lines show
`_run_one_tool: tool weather(...)` and `_run_one_tool: tool crypto_price(...)` for the same
prompts. Fifth measurement error of the session, and the same shape as the others: right
number, wrong instrument. Read it with the log, never with its own `fired` column.

## Where my own new gate is weaker than it looks

`bench/test_tool_reachability.py` went green at 41 → 0 advertised-but-unrouted tools, and
that number should be read with a caveat I found by auditing it.

The gate requires each unrouted core tool to be exempt **with a stated reason**. It
checks that a reason *exists*. It cannot check that the reason *holds*. And all 37 reasons
were written today, in one sitting, from reasoning about what each tool's name suggests.

`audit_exempt_routes.py` then asked the question the gate does not — does a plainly
implying request reach these tools?

```
What tasks do I have?          -> []                     list_tasks    NOT reached
Read my journal.               -> []                     read_journal  NOT reached
Play some music.               -> []                     play_music    NOT reached
What is playing right now?     -> []                     now_playing   NOT reached
Pause it.                      -> []                     media_pause   NOT reached
What skills do you have?       -> []                     list_skills   NOT reached
What's the weather like?       -> ['weather']            weather       reached
```

**1 of 12.** So the honest description is: *the gate proves there are no silent gaps, and
37 tools now have a documented reason for being silent* — it does not prove those reasons
are right. Some are certainly not. `add_task` is the clearest: routing "add milk to the
shopping list" to a task tool would contradict the recorded decision to keep grocery writes
out of scope, so that exemption is doing real work. Others are simply untested.

Turning that into routes would be a large batch of new inference on the hot path, chosen by
me, on tools with no failing scenario pointing at them. That is exactly the decision the
gate was built to *surface* rather than to make.

## A note on the pattern

Four findings from this pass evaporated on checking: the "unprompted feed is live"
(`mynews`), the calibration cluster, the `safety_email` alarm, and the "fabricated tool
use" probe above. Each looked alarming and each was wrong — twice because the *scenario*
was at fault, once because a probe's own cleanup was missing, once because a timer
included teardown. The tools here exist to make the next reader's first guess cheap to
check. **A result that looks like a defect deserves more scepticism, not less.**
---

## 2026-10-09 — open-source integration research (added later the same day)

### `verify_repos.py <candidates.json> [--out verified.json]`

Turns a bare `owner/repo` string into a record with the fields that actually decide whether a
project can be adopted: licence, stars, last push, archived flag. Groups candidates **by owner**,
because one `search/repositories?q=user:<owner>` call returns every repo for an owner *with full
metadata* — that is how 105 candidates were checked inside a 60-request/hour unauthenticated
budget. Everything it cannot verify is reported in `unverified`, never silently dropped.

Input is `{"owner/repo": "why it was proposed"}` so the reason travels with the candidate.

### `check_repo_exists.py <candidates.json> [out.json]`

`HEAD https://github.com/<owner>/<repo>` — costs nothing from the API budget and answers only
one question: **does this path exist, or did a model invent it?** Proves existence only. Its
output is recorded with `licence_verified: false` so it can never be mistaken for a licence
check.

**Why both exist.** Of 105 candidate projects proposed by five research agents, **13 did not
exist at all** and **7 more were cited under the wrong owner**. `cobotar/cowrie` is now
`cowrie/cowrie`; `pslmodels/taxcalc` — the only candidate for Rubo's tax engine — is not real
at any path. Six agents' worth of confident-sounding repo names would have gone straight into
a document without either script. See `docs/INTEGRATION-MATRIX.md` §0.

**Rate-limit reality worth knowing before you write another one of these:** unauthenticated
GitHub allows 60 core calls/hour and 10 search calls/hour, reset on the hour. Owner-grouped
search is the only way to verify a list longer than ~60 entries in one pass.

---

## 2026-10-10 — the provider liveness check (added after the chain went dark)

### `check_providers.py [--min N] [--all]`

Probes every entry in the shipped model chain and says whether it can answer, with a
diagnosis rather than the word "failed": `402` -> out of credit, `404` -> that model id does
not exist, connection errors -> unreachable from this host.

**Run it before quoting any behavioural number.** Measured on2026-10-10:

```
1 of 8 entries can answer
```

with `test_finetune.py` green throughout, because that gate pins the chain's SHAPE (paid
primary, provider diversity, a free tier before the gateway, gateway as the contiguous tail)
and a shape gate cannot see that six of the eight entries are dead. The behavioural suite then
reported 82.2, 77.8 and 59.1 on three consecutive runs — the last one because the Vercel
gateway ran out of credit mid-run.

**It exits non-zero below `--min` (default 2) but is deliberately NOT a registered gate.** A red
suite caused by a billing state is a fact about the account, not a defect in the code, and
nothing imports it into `run_all_tests.py`. Its default floor is 2 on purpose: one reachable
provider is a primary, not a fallback, and with only one the behavioural score becomes a
measurement of that provider rather than of Afon.
