# S40 — Financial & Asset Management

> **One line:** what the owner holds, valued from his own file — and a system that
> refuses to hold his transactions.
> **Status:** **narrowed by decision 2026-10-03** — read-only market alerts on watched symbols only. Transaction ingest is a hard no (D-12). · **Registry:** S40 · 3/3 floor, 0/1 raise, 0/0 elite
> **Milestones:** M06 · **Decisions:** D-12

## Purpose

This system is being narrowed by decision, not failing. D-12 is unambiguous: no bank
feeds, no transaction ingest, no personal ledgers — read-only market lookups only — and
the reasoning is the part that matters, because it is a blast-radius judgement rather
than a capability judgement. Transaction data is an unacceptable blast radius for zero
assistive gain. Everything a ledger would tell the owner, he already knows; everything
that would go wrong with it, he cannot undo.

"No personal ledgers" is about **who writes the rows**, not about whether a ledger file
may exist, and the distinction is load-bearing because this system ships one: the
owner's own hand-written holdings file, whose shape is `ledger.example.beancount`, is
permitted and is the only ledger there is. What is forbidden is **ingest** — reading
transactions, statements or bank feeds into a ledger Mushegh holds. A file the owner types
is data he already had and chose to write down; an ingested feed is his financial
history arriving unasked, in a shape no person reads. The line is drawn at the direction
of the write, not at the format: Mushegh may read that file, and writes nothing into it.

So most of this document's goals are anti-goals. They are written as capabilities
precisely so they can be tested: a system that refuses is a system with a passing
benchmark, and "we decided not to build it" leaves nothing to regress.

What survives is one thing. `40.R1` — a threshold move on a watched symbol raises a
counted proactive signal — is the only raise task that survives the narrowing, and it is
narrow on purpose: a price, a threshold the owner set, and one signal charged against
the daily interruption budget like every other.

If this system were absent, almost nothing would break, and that is the point rather than
an embarrassment. The registry's "missing as a system" is the accurate description of a
system that was never supposed to be built.

## Structure

| Path | Process | Role |
|---|---|---|
| `src/mushegh/brain/portfolio.py` | brain | 40.F1–F3 — reads a ledger the owner controls, values it with a read-only quote lookup, and moves nothing |
| `src/mushegh/brain/tools/portfolio.py` | brain | One tool, one read: `portfolio_snapshot`. No client, no credential, no parameter that takes an amount or a destination |
| `ledger.example.beancount` | repo | The plain-text Beancount shape the ledger is expected to take; the owner's real file is local and not in the repo |
| `bench/test_portfolio.py` | bench | Holds the whole finance family to the absence of a mutating tool |
| `src/mushegh/brain/proactive_signals.py` | brain | Where a threshold crossing would raise the one counted signal (40.R1) |
| `src/mushegh/brain/stock.py`, `src/mushegh/brain/tools/stock.py` | brain | **Not this system**, despite the name: these are the inventory tools for S47 |

The naming trap in the last row is worth stating loudly, because "stock" reads as
securities and is in fact household inventory. A reader who greps for the finance code
will find it in `portfolio.py`, not in `stock.py`.

**Data flow.** The brain process reads the owner's plain-text ledger, resolves prices by
a read-only lookup, and returns a spoken snapshot. Every value carries its as-of time and
its source, and a stale price says so rather than being presented flatly (40.F3). There
is no write path in this system, and the module docstrings say so explicitly — the
absence is asserted by a test rather than merely true, which is the whole of 40.F2.

**The cancellations are applied.** 40.R2 (spending awareness from statements), 40.R3
(subscription and recurring-charge detection) and 40.E1 (a monthly financial brief) are
rows in the cancelled-tasks table of `docs/REGISTRY-RECONCILIATION.md` — 29 tasks
cancelled across S15, S24, S30, S40, S46, S47 and S49 — and all three need transaction
data. `docs/systems-plan.json` carries all three in state `cancelled` — the planner grew
the state that the reconciliation said it lacked. The
system's status string says the same thing in the registry's own words: narrowed by
decision, read-only market alerts on watched symbols only. 40.R1 is the one surviving
raise task, so the floor is 3/3, the raise is 0/1, and there is no elite task left to
pass.

### Proposed addition — make the one permitted ledger actually parse (D-93)

The single permitted artefact is `ledger.example.beancount`, a *format shape*, and
the holdings read against it is `not yet measured`. That is the whole gap.

**[beancount/beancount](https://github.com/beancount/beancount)** (GPL-2.0,
6.0k★, pushed 2026-08-23) — in-repo import. A library, not an executor, so it
bypasses the executor contract by `EXTERNAL-EXECUTORS.md` §6's own rule.

**A base addition, not a capability.** It replaces a hand-rolled parser for a
format this repository already names, and it makes no goal reachable that is not
already listed. What it buys is that a date the owner mistyped in his own file
stops becoming a confidently spoken wrong number.

**It stays on the readable side of the D-12 line, which is the whole constraint.**
A ledger file the owner types himself is data he already had; Mushegh may read it
and writes nothing into it. Nothing here changes that, and nothing here may.

**Licence, recorded rather than inherited:** GPL-2.0, acceptable for a private,
never-distributed install, a real obligation if Mushegh is ever shared (D-57, D-60).
It belongs in `THIRD_PARTY_NOTICES.md` when adopted.

**Gate:** `bench/test_portfolio.py`, which exists and is `not yet measured`.
PRINCIPLES §1 three commands, in order:

```
uv run bean-check ledger.beancount
uv run python bench/test_portfolio.py
journalctl -u openmushegh-brain -n 100 | grep -i quote
```

**What must not come with it:** any bank feed, statement ingest, or order
placement. That is a different decision and is not taken here.

See [INTEGRATIONS.md](../INTEGRATIONS.md) §2 and §6.


## Goals

1. **No transaction ingest path exists anywhere** — no bank feed, no statement parser,
   and no ledger Mushegh writes into. The owner's own hand-written holdings file is the one
   permitted ledger and the only one; ingest is the forbidden half. Anti-goal, and a
   failure of it is a defect (D-12).
2. **No mutating tool exists in the finance family** — no amount parameter, no
   destination, no credential, no second function. Anti-goal (40.F2).
3. The one read: what the owner holds, valued from his own plain-text file (40.F1).
4. Every value carries its as-of time and source, and a stale price is reported as stale
   (40.F3).
5. A watched symbol crossing a threshold the owner declared raises exactly one counted
   proactive signal (40.R1, M06).
6. That signal is charged against the daily interruption budget like any other, and a
   financial alert does not get a private channel past it (D-29, D-30).
7. The cancellations stay applied: 40.R2, 40.R3 and 40.E1 are not quietly re-opened as
   "small" features.

## Benchmarks

| Goal | Tier | Command or drill | Threshold | Last measurement |
|---|---|---|---|---|
| 1 | B4 | `grep -rlniE 'plaid|open_banking|bank_feed|ofx|statement_parser' src/mushegh/` | 0 ingest modules; 0 credentials for a financial institution | not yet measured |
| 2 | B1 | `uv run python bench/test_portfolio.py` [no mutating tool in the finance family] | 0 handlers that write; 0 parameters taking an amount or a destination; 1 tool in the family | registry records 40.F2 done; run not reproduced here — not yet measured |
| 3 | B1 | `uv run python bench/test_portfolio.py` | a snapshot returns holdings and values with no credential configured; 0 network calls to a financial API | registry records 40.F1 done; run not reproduced here — not yet measured |
| 4 | B1 | `uv run python bench/test_portfolio.py` [staleness] | every value carries an as-of and a source; a price past its declared TTL is reported as stale; 0 silently old values | registry records 40.F3 done; run not reproduced here — not yet measured |
| 5 | B1 | `uv run python bench/test_proactive_thresholds.py` [finance kind] | a crossing raises exactly 1 signal; a non-crossing tick raises 0; each crossing counted once | not yet measured (40.R1 open) |
| 6 | B1 | `uv run python bench/test_proactive_thresholds.py` [budget] | a finance signal cannot push the day's audio count past 3, and never fires inside a focus block | not yet measured |
| 7 | B1 | `grep -n '"40\.\(R2\|R3\|E1\)"' docs/systems-plan.json` | all three carry state `cancelled`; 0 reverted to `open` | registry records all three as `cancelled`; not reproduced by a named test here — not yet measured |

Goals 1, 2 and 7 cannot fail quietly, which is the point of writing anti-goals as
capabilities. Goal 1's grep is a tripwire for a small, named set of ingest libraries; it
is not a proof of absence, and a novel ingest path would slip past it. Goal 2 is the one
that actually holds the line, because it is a test over the tool family.

## Failure modes

**Someone adds a statement importer.** The obvious feature — "paste your bank statement
and I will categorise it" — reads as helpfulness and is exactly what D-12 forbids. The
cost is that the blast radius becomes the owner's finances. Diagnose:
`grep -rniE 'statement|categor|transaction' src/mushegh/brain/`, then
`uv run python bench/test_portfolio.py` and read which assertion failed.

**A stale price is read as current.** The snapshot answers with a number that was true
three days ago, and the owner makes a decision on it. This is the failure 40.F3 exists to
prevent and the one most likely to be believed. Diagnose: the as-of in the spoken
output, then `journalctl -u openmushegh-brain -n 100 | grep -i quote`.

**The tool grows a parameter.** One added `amount` argument, or one convenience
"function", and the read-only property the whole system rests on is gone while the tool
name still says `portfolio_snapshot`. Diagnose: read
`src/mushegh/brain/tools/portfolio.py` — it is meant to stay small enough to read in one
screen, which is the cheapest test there is.

**The cancellation is quietly reverted.** The registry records 40.R2 and 40.R3 as
`cancelled`, and under D-46 capacity pressure a cancelled task reads like unfinished
cheap work rather than a closed question. It is not: the reason was a blast radius, not a
scheduling preference, and un-cancelling it reopens a decision the owner has already made
under D-12. Diagnose: `grep -n '"40\.' docs/systems-plan.json`, then read the S40 row of the cancelled-tasks
table in `docs/REGISTRY-RECONCILIATION.md` before treating any of the three as
available.

## Open questions

1. M06's gate needs both halves — no ingest path anywhere, and a watched-symbol alert
   that works — and only the first is settled. Does 40.R1 ship as the last task in a
   narrowed system, or is the narrowing taken as the answer and 40.R1 cancelled too?
2. Is the watched-symbol list a file the owner edits by hand, or something a tool call
   can change? D-32's precedent, where only the owner edits configuration, points to a
   file.
3. Does a threshold crossing speak, or only render? D-29 counts audio interruptions and
   D-18 has no financial category, so a spoken price alert is currently unclassified
   rather than permitted.
