# S03 — Tool Utilization

> **One line:** The belt around the model: 153 schemas today, heading for 90–100, every one validated, and the belt shrinks rather than grows.
> **Status:** complete for now · **Registry:** S03 · 4/4 floor, 4/7 raise, 0/1 elite
> **Milestones:** M27 · **Decisions:** D-04, D-06, D-07, D-13

## Purpose

Tools are the only way the model's text becomes an effect on the machine, so this
system is where the safety argument actually lives. Two invariants carry it. Every
handler is schema-validated (D-04): a handler that takes a raw string where a schema
belongs is a defect, not a shortcut, and only a Pydantic-validated payload reaches the
OS. And the belt shrinks (D-06) — unused for 60 days is culled, because adding a handler
is adding a place this can fail, and 50 subsystems is already one too many.

D-07 is the narrow door. Afon may act **without asking** for exactly five things:
predefined lighting scenes, appends to daily notes, local timers, read-only file and
system queries, and transit/weather polling. That list is a whitelist, not a starting
point. A new silent-ok action is a decision, not a feature. Everything else is
confirmed, and a refusal is final in conversation — overriding one is a physical act, a
CLI flag or a hardware key (D-14).

D-13 draws the outer line: door locks, main power breakers, recursive filesystem
purges, and external email or messaging dispatch are never touched without the owner
physically present. M27 is the milestone that makes each of those a test rather than an
intention.

If this system is absent, the model has no hands, or — worse — it has untyped ones.

## Structure

```
tools/__init__.py   SCHEMAS the LLM sees + HANDLERS name → async handler(args) -> str
        │            per-turn NARROWED group advertised, not the whole belt
        v
tools/base.py       the contract every handler inherits
        │
        ├── argcheck.py     argument validation before dispatch, repair prompt on the first failure
        ├── approvals.py    where a confirmation is required
        ├── audit.py        where the confirmation is recorded
        ├── judgment.py     the value order that can refuse
        └── governor.py     the interference budget
```

| Concern | Where |
|---|---|
| Registry, per-turn narrowing, name→handler map | `src/afon/brain/tools/__init__.py` |
| Handler contract, graceful degradation | `src/afon/brain/tools/base.py` |
| Argument validation | `src/afon/brain/argcheck.py`, `src/afon/brain/tools/approvals.py` |
| Typed failure contract (03.F1) | `tool_failed()`, `is_not_configured()` — no result sentinels |
| Result size ceiling (03.F4) | `agent.py` appends `str(result)`; a ceiling is applied at the boundary |
| Per-handler usage and reliability | `tool_usage.py`, `tool_reliability.py` |
| Catalogue contents and family grouping | `composio_catalog.py`, and the ~50 modules in `src/afon/brain/tools/` |

**Process ownership:** brain. Every handler runs in the brain process, which is why a
handler must never be a shell string.

**What it stores:** per-tool usage counts, success and failure rates, and last-used
timestamps — the inputs to the 60-day cull. Confirmation and refusal records go to
`audit.py`.

### A smaller belt, not a bigger one (D-93)

**The verdict for this subsystem is SUBTRACT, and the re-review confirmed it.**
153 schemas and 155 handlers against a 90–100 target (D-06) is the problem; no
repository fixes it. The correct action is deletion, and this document's open
question 3 — which handlers go first — is the entire job, answered from
`src/afon/brain/tool_usage.py`.

The one conditional: if the "core schemas already spend 7418 of 11000 catalogue
tokens" figure must be **exact** rather than estimated,
**[openai/tiktoken](https://github.com/openai/tiktoken)** (MIT) would make it so,
imported in one function behind the budget check in `_tools_for_turn()`. It is not
proposed now, because no gate is waiting on the precision.

**A narrower belt is a faster, less confidently wrong Afon**, which is the
symptom this document names. See [INTEGRATIONS.md](../INTEGRATIONS.md) §2.


## Goals

1. **No tool reaches execution with an unvalidated payload** (D-04); every handler
   takes a validated model, not a raw string.
2. **The belt is 90–100 handlers**, with anything unused for 60 days culled rather than
   left to rot (D-06).
3. **Only the five D-07 silent-ok actions run without asking**; every other action asks
   exactly once, on the first attempt.
4. **Door locks, main power breakers, recursive deletes, and external dispatch all
   refuse** (D-13) — one test each, no exceptions and no "the intent was clear" argument.
5. **A missing argument produces a question, not a fabrication** (03.F2), with at most
   one repair prompt per turn.
6. **A failing tool returns a typed failure**, and a tool whose integration is not
   configured says so rather than raising (03.F1).
7. **Wrong-tool selection is under 2%** of turns, and no tool result blows up the
   prompt (03.E1, 03.F4).

## Benchmarks

| # | Goal | Tier | Command / drill | Threshold | Last measurement |
|---|---|---|---|---|---|
| 1 | Schema validation (D-04) | B4 | Code invariant: `tools/base.py` contract; a raw-string handler is a hard failure | 0 unvalidated paths to execution | not yet measured |
| 2 | Belt size (D-06) | B5 | Count SCHEMAS and HANDLERS in `src/afon/brain/tools/` | 90–100 handlers; 0 unused ≥60 days | 153 schemas / 155 handlers per the charter — **above the target, shrinking** |
| 3 | Silent-ok list (D-07) | B4 | `bench/test_confirm_tier_documented.py`; the list is a whitelist | exactly 5 categories; any 6th is a test failure | not yet measured |
| 4 | Blast radius (D-13, M27) | B4 | One refusal test each for locks, breakers, recursive delete, external dispatch | 4/4 refuse, 0 conditional | not yet measured — M27 open |
| 5 | Missing argument asks | B1 | `bench/test_missing_arg.py` | 0 fabricated arguments; ≤1 repair prompt per turn | not yet measured |
| 6 | Typed failure | B1 | `bench/test_no_result_sentinels.py`, `bench/test_tool_failure_guard.py` | 0 sentinel strings reaching the model | not yet measured |
| 7 | Wrong-tool rate and result ceiling | B5 | `bench/behavioral_suite.py` per-turn tool audit (03.E1); `bench/test_tool_result_ceiling.py` (15) | <2% wrong-tool; 15/15 on the ceiling | not yet measured. The 03.E1 gate names the 74.8 diagnosis as superseded, and no current figure is recorded |

Goal 2 is the one with a number, and it is a number in the wrong direction: the charter
records 153 schemas and 155 handlers against a 90–100 target, so growth here is a
subtraction task and the cull has not happened. Goal 7's `74.8` is named in the
registry as the *original* diagnosis, explicitly superseded; no replacement figure has
been measured, so the benchmark carries no number at all.

## Failure modes

**A handler takes a raw string.** The model emits `{"path": "..."}` and something
downstream does the wrong thing with it. This is a D-04 violation and it is the reason
`tools/base.py` is read before writing a handler, not after.

**The belt grows instead of shrinking.** A new handler is added for a one-off request,
then never used, then becomes a place a prompt injection can reach. The symptom is a
catalogue too wide to choose from, which shows up as latency and as wrong-tool
selection. Diagnose: count the handlers, then read `tool_usage.py` for last-used
timestamps.

**A destructive action proceeds on a confident intent.** The worst outcome this system
exists to prevent. D-13 makes it a refusal, not a judgement call — intent clarity is not
a defence. Reproduce with the four M27 tests once they exist.

**An unconfigured integration raises.** The tool explodes instead of saying "that isn't
configured yet", and a missing credential becomes a crash rather than a sentence
(03.F1). `bench/test_no_result_sentinels.py` is the alarm.

**A tool result floods the prompt.** `agent.py` appends `str(result)` and an
unbounded result silently eats the context window, so the answer degrades for no visible
reason. The ceiling test catches it in the suite, not in the field.

## Open questions

1. 03.R1 (two-stage selection: a cheap router picks a family of 10–20, the model picks
   within it) is open and its gate `bench/test_catalogue_narrowing.py` does not exist
   yet. It is the lever for goal 7 and it needs the script before the number means
   anything.
2. D-06 sets a 60-day cull window. No record says who runs the cull, or what happens to
   a handler that is unused but load-bearing for a documented capability.
3. The belt is 153 schemas against a 90–100 target. Which handlers are the first to go,
   and is that list written down anywhere yet?
