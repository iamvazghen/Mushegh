# S41 — Research & Synthesis

> **One line:** research when the owner asks for it, in a session with a budget, with
> every web claim traced to a page that was actually opened.
> **Status:** half-built · **Registry:** S41 · 3/3 floor, 0/4 raise, 0/1 elite
> **Milestones:** none assigned · **Decisions:** D-34, D-58, D-52

## Purpose

Research happens in focused sessions, never as an ambient feed (D-34). Afon never brings
something unasked because it seemed interesting. That is a hard architectural boundary,
not a tone setting: an ambient research surface converts a tool the owner invokes into a
channel that talks to him, and every other decision in this file assumes the request came
from him.

The other constraint is the opposite one. D-58: no topic is off-limits when working on
the owner's own local data — the only refusals are operations risking catastrophic
physical damage or violating a safety invariant, and topic-sensitivity in a single-user
home system is surveillance theatre. So a medical or financial question is answered
plainly. There is no discretion to exercise here, and a refusal on subject matter would
be a bug.

What this system is missing is judgement about sources. Search, fallback, mandatory
citations and a stated budget all exist. Reliability weighting — not every page counts
the same — does not (41.R1), which is why a synthesis today is a well-cited list rather
than an answer that accounts for who is talking.

If it were absent, the owner opens four browser tabs, reads them himself, and writes the
summary by hand. That is the work the system exists to remove, and it is the one part of
Afon's job that genuinely scales with his time.

## Structure

| Path | Process | Role |
|---|---|---|
| `src/afon/brain/citations.py` | brain | 41.F2 — what Afon actually read this turn, so a source he names is one he opened |
| `src/afon/brain/tools/web.py` | brain | 41.F1 — search, scrape and interactive browse, each behind its own key, each degrading instead of failing |
| `src/afon/brain/references.py` | brain | What "it", "that" and "the second one" refer to — the resolution a research turn needs to stay coherent |
| `src/afon/brain/docstore.py` | brain | Local document retrieval over a temporary index, and where a synthesis is filed (41.R3) |
| `src/afon/brain/tasks.py` | brain | Where a research task carries its budget and records that it stopped early (41.F3) |
| `src/afon/brain/semantic.py`, `src/afon/brain/recall.py` | brain | Retrieval over what is already local, before anything leaves the host |
| `src/afon/brain/mynews.py` | brain | An unprompted morning headline surface — **the live example of what D-34 forbids**, see below |
| `src/afon/brain/proactive_signals.py`, `src/afon/brain/delivery.py` | brain | The path any ambient research surface would enter, and the interruption budget it would be charged against |

**Data flow.** A turn requests research, the budget is stated on the task, `web.py`
resolves sources through its fallback chain, `citations.py` records what was actually
fetched, and the answer is composed only from those pages. Synthesis is filed into
`docstore.py` rather than left in the transcript, so it is retrievable later.

**The honest gap, and a live violation.** 41.R1 (reliability weighting) and 41.R2
(contradiction surfacing) are open, so today's synthesis has no way to say that a
forums answer and a primary source do not carry the same weight. Separately,
`src/afon/brain/mynews.py` is a proactive news-of-interest source that once each morning
surfaces top headlines as a proactive signal so Afon mentions them unprompted. That is
content discovery nobody asked for, and D-34 names S41 as a system it applies to. The
module is real and wired, not merely present: `news_signals` is registered as a source in
`src/afon/brain/proactive.py` and fires while `8 <= now.hour < 10`. The honest reading is
that it is a S15-shaped feature that survived in a module the S15 cancellation did not
name. It is not fixed here, but it is no longer unowned: `41.R4` — "No unprompted
content feed: the ambient morning news push is removed, or it fires only as a reply to
something the owner asked for (D-34)" — tracks it, with a planned gate of
`bench/test_no_unprompted_feed.py`.

## Goals

1. Every factual claim sourced from the web carries a citation, and the citation resolves
   to a page that was actually fetched this turn (41.F2).
2. A research task states its budget up front and reports when it stopped early
   (41.F3).
3. Search, scrape and browse degrade through a typed fallback chain rather than failing
   the turn (41.F1).
4. Source reliability is weighted, so a low-quality page cannot outrank a primary source
   for the same claim (41.R1) — the open work.
5. Disagreement between sources is surfaced rather than silently resolved in favour of
   one (41.R2).
6. A synthesis is filed and retrievable, not left to evaporate from the transcript
   (41.R3, with S06).
7. Research is requested, never ambient (D-34); where the sources do not settle the
   question, the uncertainty is audible (D-52).

## Benchmarks

| Goal | Tier | Command or drill | Threshold | Last measurement |
|---|---|---|---|---|
| 1 | B1 | `uv run python bench/test_citations.py` | 100% of web-sourced factual claims carry a citation; every citation resolves to a fetched page; 0 uncited | registry records 41.F2 done; run not reproduced here — not yet measured |
| 2 | B1 | `uv run python bench/test_citations.py` [7] | a task that exhausts its budget says so; 0 silent truncations | registry records 41.F3 done; run not reproduced here — not yet measured |
| 3 | B1 | `uv run python bench/test_web_fallback.py` | a dead primary key falls through the chain and returns a degraded answer; 0 hard failures of the turn | registry records 41.F1 done; run not reproduced here — not yet measured |
| 4 | B1 | `uv run python bench/test_citations.py` [weighting] | a low-weight source cannot outrank a high-weight one for the same claim; 0 comparisons made without weights | not yet measured (41.R1 open — no weighting exists to test) |
| 5 | B1 | `uv run python bench/test_citations.py` [conflict] | two disagreeing sources produce both plus a stated disagreement; 0 silently chosen winners | not yet measured (41.R2 open) |
| 6 | B1 | `uv run python bench/test_document_create.py` [research output] | a filed synthesis is retrievable by title; 0 orphaned files | not yet measured (41.R3 open) |
| 7 | B4 | `grep -rlniE 'mynews\|news_digest\|research_digest' src/afon/brain/`, then the planned `bench/test_no_unprompted_feed.py` (41.R4 — does not exist yet) | 0 modules that surface research unprompted | not yet measured — `src/afon/brain/mynews.py` matches today, which is the D-34 tension recorded above |

Goal 7's threshold is currently expected to fail. It is written anyway, because a system
that states its own violation is in better shape than one that omits the check, and
because the alternative is a doc that reads as though the boundary holds.

## Failure modes

**A confident answer with a citation that does not support it.** The model has been
handed a page of text and will happily attribute a claim to it. 41.F2 exists for exactly
this, and the failure is invisible to the owner because the citation looks real.
Diagnose: `uv run python bench/test_citations.py`, then read the fetched page in the turn
record for that turn.

**Research becomes a feed.** The owner asks for research once and now receives unprompted
material each morning. That is D-34, and it is the shape of the recommendation system
S15 was removed for rather than a new feature. Diagnose: the grep in goal 7, then
`journalctl -u openafon-brain -n 200 | grep -iE 'proactive|signal'`.

**The budget is never stated and the answer stops silently.** A truncated result reads as
a complete one, and the owner acts on a partial answer. Diagnose: the task row for the
research turn, via
`python -c "from afon.config import settings; print(settings.tasks_db_path)"` and a
`select` on that store.

**A subject-matter refusal appears.** A medical or financial question declined because of
its topic. That is D-58, and it is a defect in judgement, not caution — the refusals that
do exist are physical-damage and safety-invariant ones.

## Open questions

1. Where does source weight come from: a declared list the owner curates, or an
   observation of what he re-checks? 41.R1's gate is a test, so the weight has to be
   readable data rather than a judgement the model makes per turn.
2. Is the research budget per task or per turn, and does an early stop count as success
   or failure in the task record? 41.F3 requires the report and does not say which.
3. Does a filed synthesis go through S06's document path or straight into the vault?
   D-22 makes markdown authoritative, so the question is which file wins — and the
   answer changes what `docstore.py` has to reconcile.
