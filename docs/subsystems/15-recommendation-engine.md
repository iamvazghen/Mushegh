# S15 — Recommendation Engine

> **One line:** a decision record for a system that must not exist.
> **Status:** **removed by decision 2026-10-03** — Mushegh answers and acts; it does not suggest (D-27). Nearest neighbours stay as tools and must not grow into a recommender · **Registry:** S15 · 3/3 floor, 0/0 raise, 0/0 elite — the 0 of 0 is real, not an absence: four raise and elite tasks (15.R1, 15.R2, 15.R3, 15.E1) exist and are `cancelled` under D-27, and a cancelled task leaves the denominator ([../EVIDENCE.md](../EVIDENCE.md))
> **Milestones:** M03 · **Decisions:** D-27, D-34, D-26, D-42

> This document exists so the system is not re-added by accident. It is not a roadmap.

## Purpose

There was a system here. It was going to decide what the owner should work on next, what to
read, where to eat, and which of his own habits he was ignoring — and to learn his taste from
whether he accepted the suggestion. Three floor tasks were built against a single domain, with
an explicit reason attached to every recommendation and a log so acceptance could be learned
later.

It is removed. **Mushegh answers and acts; it does not suggest** (D-27). Not scheduled, not
narrowed, not deferred behind a quality bar — removed. Proactive recommendation is intrusive
noise, and the cost is paid by the one person it targets: a butler who keeps surfacing things
his owner did not ask about is a butler who has been fired and does not know it.

The charter makes it binding, and the removal is Phase 0 work (M03) rather than a cleanup
item, which is the correct altitude: this is subtraction, and D-46 puts deleting dark and
wrong systems ahead of building speculative ones.

What breaks if it is absent: nothing. That is the point of the document. Mushegh still answers
"what should I work on", because that is a request, and answering it is not recommending.

## Structure

The code is still on disk, which is the whole risk.

| Path | What it is | Disposition |
|---|---|---|
| `src/mushegh/brain/recommend.py` | 15.F1–F3: one domain ("what should I work on next"), an explicit reason naming the rule and the data it read, a decisions table, and a decline when there is no basis | delete under M03 |
| `bench/test_recommend.py` | The gate for those three tasks; it exists and passes | delete with the module; a passing test for deleted code is the exact shape of the trap |
| `src/mushegh/brain/coaching.py` | **Not a recommender.** A store: level, review log, streak, trend, "is it time to check in" | keep, and keep it boring |
| `src/mushegh/brain/tools/coaching.py` | A registered handler for conversational skill review | keep — it answers a question he asked |
| `src/mushegh/brain/proactive_signals.py` | `pattern_suggestion` — a signal that proposes a one-tap action from a learned pattern | the live temptation; see open question 1 |

The registry status is the decision itself: "**removed by decision 2026-10-03** — Mushegh
answers and acts; it does not suggest (D-27)". [REGISTRY-RECONCILIATION.md](../REGISTRY-RECONCILIATION.md) §2
records the correction, and it was applied on 2026-10-03: all four open tasks (15.R1, 15.R2,
15.R3 and the elite task 15.E1) are `cancelled`, each with an `owner-decision` record naming
D-27. A cancelled task will never be done, so it leaves the denominator — that is why the
raise and elite counts above render 0 of 0 rather than 0 of 4
([../EVIDENCE.md](../EVIDENCE.md)). The three floor tasks stay recorded as historical fact,
not as live work.

Note that `recommend` still appears as a routing keyword in
`src/mushegh/brain/tools/__init__.py`. A keyword is not a recommender, and the group it sits in
is a routing table, but it is on the deletion list for M03.

## Goals

These are anti-goals, and each is written as a prohibition rather than as a capability.

1. No handler anywhere returns an unprompted proposal. Ever.
2. A question the owner asked about what to do next is answered; it is not a recommendation.
3. `src/mushegh/brain/coaching.py` stays a store. It holds state; it does not propose.
4. `src/mushegh/brain/proactive_signals.py` surfaces only what a named trigger already established, and never
   "this looked interesting".
5. The removal is visible in the code, not only in a document.

## Benchmarks

These are deletion gates, not quality gates. Each one **fails** if the system reappears.

| Anti-goal | Tier | Command or drill | Threshold | Last measurement |
|---|---|---|---|---|
| 1 | B1 | new test in `bench/test_recommend.py`, inverted, per M03 ("a test asserts it stays deleted") | 0 handlers reachable that return content the owner did not ask for; the suite fails if `src/mushegh/brain/recommend.py` exists | not yet measured — the test does not exist (M03 open) |
| 2 | B1 | `uv run python bench/test_doc_paths.py`, plus a grep of the registered belt for propose-shaped output | a request-triggered answer is not a proposal; 0 ambient emissions | not yet measured |
| 3 | B4 | `src/mushegh/brain/coaching.py` | the module holds level, log, streak, threshold; 0 ranking, 0 candidate generation | holds today |
| 4 | B4 | `src/mushegh/brain/proactive_signals.py` | 0 signals with an interest-shaped trigger; every signal names a concrete event | holds by inspection today; no test asserts it |
| 5 | B4 | `ls src/mushegh/brain/recommend.py` | file absent | **fails today** — the file is present. This is the work M03 names |

M03's own acceptance line: "No handler proposes unprompted content; a test asserts it stays
deleted (D-27)". Until that test exists, this document is the only thing holding the line, and
a document does not fail a build.

## Failure modes

**Re-added as a feature.** The most likely path. Someone notices that Mushegh knows the owner's
tasks, deadlines and patterns, and concludes a "next up" card is a small, helpful addition.
That is D-27 exactly, arrived at from the friendly direction. The tell is a proposal with no
question behind it.

**Grown from inside a neighbouring module.** Lower probability, higher damage.
`src/mushegh/brain/coaching.py` is the charter's named near-miss: a store that tracks streaks and levels is two
fields away from a coach that tells you what to practise next, unasked.
`pattern_suggestion` is the live version of the same shape. D-27 names both.

**The dead code becomes dark infrastructure.** Code that controls no live path is dark, and
dark work is not a status (D-46). A recommendation module that no handler calls is not an
archaeological record; it is dead weight someone will eventually wire up, because it is
already written and already tested.

**The registry launders it back in.** Three floor tasks sit at `done` with a passing
`bench/test_recommend.py`. Anyone reading `docs/SYSTEMS.md` sees green rows and no removal.
That is the failure this document and the reconciliation file exist to prevent.

## Open questions

1. Is `pattern_suggestion` in `src/mushegh/brain/proactive_signals.py` a notification inside S13's budget, or
   the deleted S15 wearing a signal's clothes? It currently proposes a one-tap action from a
   learned pattern with no owner request behind it.
2. Should `src/mushegh/brain/recommend.py` be deleted outright, or moved to a dormant directory the way D-46
   describes for dark work? Deleting is cleaner; the move preserves an audit trail.
3. The `docs/systems-plan.json` correction recorded in REGISTRY-RECONCILIATION.md was
   applied on 2026-10-03 — all four open tasks are `cancelled` with `owner-decision`
   records. What the correction did not answer: do the three `done` floor rows (15.F1–F3)
   retire as well, or do they stay `done` while M03 waits to delete the module?
