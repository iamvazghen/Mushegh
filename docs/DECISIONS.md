# Decisions — the OpenAfon charter

**Status:** authoritative. Dated 2026-10-03; D-79–D-90 added 2026-10-06; D-83 amends D-12; D-88 extends D-07; D-90 implements D-08; D-91 corrects M42's transport.
**Origin:** a 100-question interview with the owner, answered 2026-10-03, plus the
[JARVIS blueprint](../TODO.md) it was measured against.
**Relationship to the registry:** `docs/systems-plan.json` records *what is built and
proven*. This file records *what will be built and what will never be built*. Where
they disagree, this file wins and the registry owes a correction — listed in
[REGISTRY-RECONCILIATION.md](REGISTRY-RECONCILIATION.md). A prose decision is not a
code change; nothing here moves a task to `done`.

Every decision marked **(commit)** was stated by the owner as binding. Decisions marked
**(feel)** are judgement, revisitable. Nothing here was decided by a model: per D-47,
AI evaluations are advisory input and de-scoping requires the owner's sign-off.

---

## How to use this file

1. The subsystem docs in [`docs/subsystems/`](subsystems/README.md) cite decision IDs
   (`D-07`, `D-29`, …) rather than restating them. A subsystem that contradicts a
   decision is a bug in that subsystem's doc.
2. Changing a decision means editing the row, bumping the date, and recording what it
   invalidates. Decisions are not silently edited.
3. A decision without a verification is an opinion. Each one below names the thing that
   would prove it false.

---

## D-01 — The 2:00 AM rule governs architecture **(commit)**

If a system fails at 2:00 AM, can it be debugged in 90 seconds with `journalctl`,
`sqlite3` and `curl`? Enterprise plumbing scales headcount, not single-operator clarity.

This is the rule that rejected NATS JetStream, OPA, Vault, Temporal, gVisor and the
second bare-metal plane from the blueprint. **Inverts** the blueprint's entire
transport layer. *Falsified by:* a subsystem that cannot be diagnosed from a shell
inside 90 seconds.

## D-02 — SQLite is the store. The PostgreSQL migration is cancelled **(commit)**

SQLite was correct from day one; the multi-adapter migration was blueprint
> **Carried out 2026-10-04, milestone M02.** Gone: `postgres_client.py`,
> `postgres_vectors.py`, `store_migration.py`, `sql/postgres_vectors.sql`, and their two
> gates. Also gone: the `postgres_dsn` setting, the `postgres` extra in `pyproject.toml`,
> `psycopg` from the lockfile (`uv lock` dropped both wheels), and the `AFON_POSTGRES_DSN`
> block in `.env.example`. **No migration was needed** — the runtime never read the DSN, so
> there was no dual-write to unwind and no data to move.
>
> **Deliberately kept, and both worth naming:**
> - the `!postgres` entry in `data_classes.STORES`. The runtime store is SQLite and always
>   was, but a host that ran the staged adapters may still have a Postgres directory on
>   disk, and an unclassified store is the failure that table exists to prevent.
> - `afon_graph.sqlite` in the migration list, for the same reason: a file the code no
>   longer writes is still a file the owner may have.
>
> **What the deleted module also contained, and where it went.** `store_migration.py`
> was not only scaffolding — it held a read-only inventory and guarded, verifiable SQLite
> snapshots. That capability is real, and `afon.protocols.backup` provides it
> (`make_backup` / `verify_backup` / `restore_backup` / `run_restore_drill`).
> `bench/test_s30_migration_removed.py` proves that with a real backup -> verify -> restore
> into a fresh directory -> drill round trip, 25/25. A gate that only checked the
> scaffolding was gone would have been satisfied by a machine that cannot back up at all.
cargo-culting and is dead weight. WAL mode stays. The staged `PostgresAdapter` work
(1 of 8 adapters landed) is reverted, not finished.

Invalidates: **S30.F1** and the remaining S30 parity/backup/cutover gates. **Falsified
by:** a single measured workload that SQLite cannot serve.

## D-03 — Tailnet + WebSocket + bearer token is the final transport **(commit)**

Acceptable indefinitely. WireGuard-backed transport eliminates the perimeter rather
than defending it. No inbound ports are opened, ever. *Falsified by:* needing an
inbound path that the tailnet cannot provide.

## D-04 — The typed schema boundary is the line between model and system **(commit)**

The model may emit arbitrary text. Only Pydantic-validated payloads execute against
the OS. This is what keeps a hallucination from becoming an action.

Enforced at the tool boundary. **Every new handler is a place this can fail** — a
handler that accepts a raw string where a schema belongs is a D-04 violation.
*Falsified by:* any tool call reaching execution with an unvalidated payload.

## D-05 — The external agent fleet is a tool, never the assistant **(commit; the line sharpened 2026-10-06)**

It is consulted as one tool among many. The line erodes the moment an agent is handed
an unconstrained interactive shell with root or network access. So: sandboxed,
AST/diff verified, never a shell. *Falsified by:* agent output applied without a
verification gate.

**What changed on 2026-10-06, and what did not.** The owner delegates coding to external CLIs
(D-79, D-80), and a CLI is the thing this decision names. The rule is **not** relaxed; the word
that was doing the work is identified: **unconstrained interactive shell.** The line is at
*interactive*, and it is now four properties enforced in code rather than four promises in prose:

| The property | Where it is enforced |
|---|---|
| No interpreter is ever the executable | `ExecutorSpec` refuses `sh`, `bash`, `cmd`, `powershell`, `pwsh`, `ssh`, `wsl` **at construction** |
| Nothing can be typed into the child | `stdin=DEVNULL` on every dispatch |
| No credential reaches the child | the child environment is an **allowlist built from nothing**, so a secret added to `.env` next year is withheld without anyone editing this |
| The product is a proposal, never a landing | the module contains no git write; the diff passes D-08's four conditions |

One consequence worth naming, because it is the residual risk rather than a solved problem: on
Windows these CLIs install as `.CMD` shims, and a batch file re-parses its own arguments — so an
`&` inside a task string is a command separator rather than a character. A brief like that is
**refused before dispatch** rather than quoted, because a wrong escape there is an injection and
not a syntax error.

*Also falsified by:* an executor spec naming an interpreter, a child process inheriting a secret,
or a brief containing a command separator reaching a batch shim.

## D-06 — The tool belt is curated, not grown **(commit)**

Target **90–100** battle-tested handlers, down from 153 schemas / 155 handlers. Anything
unused for 60 days is culled. Growth is now a subtraction task. **Applies to S03.**

## D-07 — The silent-ok list **(commit)**

Afon may act **without asking** for exactly these:

- toggling predefined lighting scenes
- appending entries to daily notes
- setting local timers
- read-only file and system queries
- polling transit and weather data

Everything else is confirmed. This list is a whitelist, not a starting point: a new
silent-ok action is a decision, not a feature. **Applies to S36, S44, S03.**

## D-08 — The self-edit rule **(commit)**

Afon may commit its own code only when **all four** hold:

1. to a dedicated branch, never `main`;
2. the complete test suite passes;
3. zero schema migrations are introduced;
4. the owner explicitly approves the diff.

A *successful* self-edit resolves a reproducible bug without changing public interface
contracts and without needing manual diff cleanup. Anything else is tolerated, not
successful. **Applies to S01, S29, S39.**

## D-09 — No session-scoped elevation **(commit)**

Every sensitive mutation requires its own explicit confirmation. A confirmation never
authorises the next action. This is the line against action-chaining exploits and
cascading failures. **Applies to S36.**

## D-10 — Value precedence: Safety > Privacy > Honesty > Helpfulness **(commit)**

Currently codified in prompt invariants and tool schema guards, with **no explicit test
suite**. That gap is a task, not a footnote (see S44 goals). *Falsified by:* a
documented case where a lower value beat a higher one.

## D-11 — Emergency escalation is SMS/push to a fixed list **(commit)**

Encoded once, by hand, by the owner. **No open-ended outbound voice calls** — the
system calls people, it does not converse with them. **Applies to S35.**

## D-12 — Finance is a hard no **(SUPERSEDED 2026-10-06 by D-83)**

> **Amended, not deleted.** The owner moved finance, taxes, investments, portfolio and
> salary work to the Rubo CLI on 2026-10-06. **[D-83](#d-83--money-is-rubos-domain-and-d-12-is-amended)
> is the live decision.** This row is kept because its *reasoning* still governs what
> remains refused, and because a decision that is silently rewritten teaches nobody.

The original text: no bank feeds, no transaction ingest, no personal ledgers. Read-only
market lookups only. Transaction data is an unacceptable blast radius for zero assistive
gain. **Applies to S40.**

**What survives of it:** the blast-radius argument, which is why D-83 still refuses to move
money without the owner physically present (D-13, D-14), and why no financial figure is
stored in the brain. **What it got wrong:** "zero assistive gain" was true of an API
integration inside the brain and is not true of a CLI the owner wrote himself.

## D-13 — Blast-radius limit **(commit)**

Afon can never touch, without the owner physically present:

- physical door locks
- main power breakers
- destructive filesystem purges (`rm -rf` and equivalents)
- external email or messaging dispatch

## D-14 — Overriding a refusal is a physical act **(commit)**

A refusal is overridden by a typed command-line flag or an authenticated hardware key —
never by asking nicely in conversation. The operator holds final sovereignty over the
machine, and sovereignty is demonstrated, not requested.

## D-15 — 0.75 speaker confidence is too loose **(commit)**

A false "owner" executes destructive actions or leaks private data. A false
"not-owner" costs a typed PIN. The asymmetry is roughly 100:1, so the threshold moves
**up**, and "unsure" must exist as a third verdict that routes to a soft path (S10).

## D-16 — English flawless, German clean, the rest drop out of the matrix **(commit)**

Six languages was inherited ambition. French, Russian, Armenian and Ukrainian leave the
*test matrix* now; support may degrade quietly, but nothing may claim a quality bar it
is not measured against. **Applies to S01, S18, S25.** *(D-78 moves where the weakness
is without changing this rule. Comprehension is no longer the weak point — the ear now
hears all six, because STT is local Whisper. What is still unmeasured is the quality of
a reply in those languages, and nothing may claim otherwise until it is measured.)*

## D-17 — Local TTS wins at 3 AM **(commit)**

Latency and local privacy dominate cost and personality, every time. Piper/Kokoro is
the default; ElevenLabs is an opt-in for when quality is worth the egress. **Applies to
S02, S18.** *(The opt-in is exercised, deliberately and for a stated reason, by this
owner's own deployment — see D-78, which is part of this decision and not a
reversal of it.)*

## D-18 — Unprompted speech has a hard scope **(commit)**

Afon speaks unprompted **only** for:

- physical security and safety triggers (water, fire, security breach)
- hard calendar count-downs (departure in 5 minutes)

The hard stop: **zero** unprompted speech for recommendations, summaries or banter.

## D-19 — One wake phrase **(commit)**

Sacred to on-device keyword spotting. Multiple wake phrases multiply false-positive
wakeups on constrained edge hardware. Household members do not get their own.

## D-20 — No conversational trailing; flat and corrective when wrong **(commit)**

Never "Is there anything else I can assist you with today?" No unsolicited apologies,
no filler, no narrative padding. On error: state the discrepancy concisely.
**Applies to S25.**

## D-21 — Retention: 30 days for the ephemeral **(commit)**

Auto-expire after 30 days: ephemeral telemetry, raw chat turns, scratchpads.
Keep forever until manually deleted: structured facts and curated notes.

## D-22 — The vault is the human source of truth **(commit)**

Obsidian markdown is authoritative; SQLite is the operational runtime cache. **When
they disagree, markdown wins.** Every cache-mirroring subsystem needs a reconciliation
path that can lose an argument to a file. **Applies to S30, S24, S50.**

## D-23 — Corrections are immediate in-session, durable at checkpoint **(commit)**

A correction takes effect at once in the live context, then is reconciled into
permanent memory at the next scheduled checkpoint. Never "it will be right next time".

## D-24 — Never store **(commit)**

Plaintext passwords · raw biometric sensor feeds · banking credentials · unfiltered
health-crisis journaling. These are not retention questions; they never enter a store.

## D-25 — Superseded memories are tombstoned, never wiped **(commit — BUILT 2026-10-04)**

> **Built 2026-10-04, task `30.R10`.** `MemoryStore.remember()` takes a `subject` — the
> supersession slot. Two facts on one subject that differ supersede: the older note is
> **tombstoned** (its text kept, `superseded_by` written into its front-matter) and a
> `supersessions.jsonl` line records both texts and the reason. `_iter_notes()` skips
> superseded notes by default, so recall can no longer return a fact the owner corrected.
> Gate: `bench/test_supersession.py`, 24/24.
>
> Two design points worth keeping:
> **The caller declares the subject.** Nothing in the store can know that "the garage remote
> is in the kitchen drawer" and "the garage remote is under the stairs" describe one slot —
> inferring that from strings is how a store invents a contradiction that was never there.
> The same discipline as Jev's declared labels: the code may only choose among slots the
> caller named.
> **Provenance cannot be traded for recency.** A weaker source can never overwrite a
> stronger one, so an inferred guess arriving late is *refused*, not stored. A
> newest-wins implementation gets this exactly backwards.
>
> **Not yet exercised in anger:** no caller passes a `subject` yet, so nothing in the running
> system produces supersessions. The mechanism is built and unused, which under D-43 keeps
> `30.R10` at in-progress.

Before it was built: `remember()` deduped on **identical normalised text only** and promoted
provenance on `source_rank()`. A conflicting correction was stored as a second fact and
recall returned both — an answer that looked confident and was wrong. Tracked as `30.R10`
and milestone **M30**. See [REGISTRY-RECONCILIATION.md](REGISTRY-RECONCILIATION.md) §2c.

The more recent explicit user correction beats historical or inferred records. The
loser is written to an audit log — silent deletion is how a system loses the ability to
explain itself. **Applies to S30, S45.**

## D-26 — The cross-entity graph relation layer goes **(commit — DONE 2026-10-04, M04)**

> **Removed 2026-10-04, milestone M04.** `src/afon/brain/graph.py` and
> `src/afon/brain/tools/graphmem.py` are deleted. The `graph` lazy tool group is
> unregistered, the L5b recall layer is gone from `fused_recall`, the background reviewer
> no longer writes triples, `forget` no longer sweeps them, and `what_i_dont_know` no longer
> speaks from a store the owner had stopped trusting. The name `L5b` is still accepted and
> simply yields nothing, so a caller gets a quiet miss rather than a KeyError.
> **Measured:** recall p95 on the per-turn path improved from 27.0/42.0/28.6 ms to
> 11.3/15.6/15.5 ms across three runs each, and the advertised tool count fell to 151.
>
> What was deliberately **kept**: `world_model.py` stays, because it is goals and events
> rather than relations — `note_event` is a TTL scratchpad that webhooks depends on. Only
> its one graph-aware method went. And `afon_graph.sqlite` stays in the migration list,
> because a host that ran the old code may still have one sitting in its repo.
The vector knowledge graph "lied constantly by pulling stale, irrelevant semantic
noise" and consumed weeks of indexing for negligible utility. Losing multi-hop
associative queries is the accepted cost. S24 pauses immediately; the relation layer is
deleted rather than maintained. **Applies to S24, S30, S15.**

## D-27 — No recommendation system **(commit)**

Afon answers and acts. It does not suggest. Proactive recommendation is intrusive
noise. **S15 is removed, not scheduled.** Its nearest existing code
(`brain/coaching.py`) is a tool, not a recommender, and must not grow into one.

## D-28 — No ML forecasting **(commit)**

A deterministic, calendar-backed look-ahead satisfies scheduling. Holt-Winters, ARIMA
and habit forecasting are blueprint leftovers. **S46 is removed as a modelling
system**; what remains is deterministic scheduling logic inside S21/S33.

## D-29 — The interruption budget **(commit)**

**Three audio interruptions per day maximum.** During a scheduled focus block, even
one is a bug. Enforced in code, not by good intentions. **Applies to S14, S13, S17.**

## D-30 — Optimise for dismissal, not helpfulness **(commit)**

"Did the intervention help?" is flawed: a tolerated interruption reads as helpful.
Optimise for **dismissal rate** and **daily interruption count**. **Applies to S14.**

## D-31 — A refusal is a negative calibration sample **(commit)**

Log it, halt the action immediately, never argue back. **Applies to S14, S44.**

## D-32 — Quiet hours are a hard boundary **(commit)**

Enforced in code. Only life-safety alerts pierce them. **Only the owner edits the
configuration files** — no tool call, no natural-language request, no agent.

## D-33 — The morning brief is triggered, not scheduled **(commit)**

Fires on the first morning device interaction (workstation unlock). Rendered
**silently on screen**; it speaks only if explicitly asked. No fixed 06:00.

## D-34 — No unsolicited content discovery **(commit)**

Afon never brings something unasked because it seemed interesting. Research happens in
focused sessions, not ambient feeds. **Applies to S13, S15, S41.**

## D-35 — Latency budgets **(commit)**

Laptop < 300 ms from speech to first audio. Phone < 500 ms. Glasses < 250 ms.
**Barge-in must halt playback within 350 ms**; the measured worst case is ~700 ms and
is a known defect (D-49). **Applies to S18, S01, S12.**

## D-36 — Device order: laptop, phone, wall panel **(commit)**

The laptop is the primary interface — deepest work, complex context, development
execution. Phone second. Wall panel third. **Smart glasses are parked** until
sub-second voice latency is solved; they are not a design target this cycle.

## D-37 — Two rooms, not five **(commit)**

Office and living room cover 90% of practical automation value. Five rooms is sensor
maintenance for nothing. **Applies to S43, S27.**

## D-38 — Bedrooms and bathrooms are air-gapped **(commit)**

Permanently off-limits to ambient recording hardware, no exceptions, regardless of
capability. This constrains S26, S11, S27 at the sensor-placement layer, not the
software layer. **Applies to S26, S11.**

## D-39 — Away from home means a phone client over the tailnet **(commit)**

No VPS-side stand-in pretending to be a body. The phone captures input and views
state. **Applies to S12, S43.**

## D-40 — Context migration carries the goal, not the transcript **(commit)**

The active goal and immediate working context migrate across devices. Raw transcript
history does not — it produces visual clutter across screen sizes. **Applies to S12,
S43, S07.**

## D-41 — The remote kill **(commit)**

`systemctl stop openafon-edge` over SSH/Tailnet. In-flight tasks take SIGTERM, escalate
to SIGKILL after 3 s, and uncommitted edits remain in a Git stash — never lost, never
committed by the kill path. **Applies to S04, S22.**

## D-42 — The new-system rule **(commit)**

A new system is justified only if it needs **an independent daemon process or a distinct
security boundary**. Otherwise it is a new handler in an existing domain. 50 subsystems
is already one too many; the count is not the growth target.

## D-43 — Evidence: green suite, then seven days of production **(commit)**

A task is done when the hermetic suite passes **and** the owner has used it for seven
consecutive days without manual patching. "Hermetic tests only prove your code agrees
with your mocks." Mock-only greens are not evidence — a subsystem whose tests rely
purely on in-memory mocks is distrusted by default. **Applies to every system.**

## D-44 — The elite tier is mis-specified, and so is the thing that measures it **(commit)**

Elite demanded enterprise-grade formal verification where single-user operational
reliability is all that matters. 0 of 52 elite tasks is a specification failure, not a
work ethic failure. Elite is re-specified as: **runs for 30 days with zero panics, zero
data corruption, zero unexpected cloud egress.** *Falsified by:* elite redefined back
into formal methods.

**Amended 2026-10-03, after the owner asked for "an elite Jarvis brain" and the
scorecard was re-measured instead of assumed.** `01.E2` — overall ≥95, no category
under 90 — is **not currently a brain measurement**, and the numbers say so plainly:

| Needs no credential | | Needs a credential | |
|---|---:|---|---:|
| Safety | 100 | Knowledge | 29 |
| Calibration | 100 | Combination | 40 |
| Latency | 100 | Honesty | 40 |
| Conversation | 96.5 | Time/Utility | 43 |
| Multi-Device | 88 | Proactivity · Autonomy · Fleet · Modes | 46 |
| | | Memory · Web · Tasks · Channels | 46–50 |

**Overall 59.3.** The split is the finding: everything internal scores 88–100, and
almost everything that needs a token, an API key or a mounted vault scores 40–50. The
scorecard is largely measuring *unconfigured integrations*, and its outputs cluster on
40/50/100 rather than spreading — which means the ≥95 bar is partly a demand for a finer
instrument. `01.E1`'s 51.5 is a **median of two** cases, which is not a stable
measurement either.

So the same failure D-44 already named once has now appeared in the **instrument**
rather than the requirement, and it is named the same way: **E1 and E2 need
re-specifying before they can honestly be chased.** Chasing 59.3 → 95 by configuring
credentials would move the number without making the brain better, and that is the
specific thing this project refuses to count as progress.

**Amended again 2026-10-04: the instrument is re-specified and gated; the score is
not re-measured, and the cause was arithmetic rather than impression.** A turn whose
expected tool did not fire is scored `correctness = 10` plus a latency band
(`{25, 18, 10, 4}`) plus a delivery band (`{15, 9, 3}`), so every such turn lands in
**17–50** — and the observed low categories sit inside that band: Knowledge 29 =
10+4+15, Time/Utility 43 = 10+18+15, Memory/Web/Tasks 50 = 10+25+15, while a turn
that did what it was asked scores 100. **The 40/50/100 cluster was a missing API key
being scored as a brain failure**, and the overall was a weighted average of 100s and
absent tokens. The instrument could not tell a decision that was wrong from a
capability that is not switched on, which is the single confusion this bar exists to
prevent.

So: a scenario whose credential is absent is now **skipped, not scored**, and is
listed as unconfigured so the gap stays visible rather than disappearing; the overall
is computed over runnable scenarios only and the scorecard records that basis on disk;
and a category with fewer than two runnable scenarios is reported **underpowered** and
excluded, because a median of two cases — which is what `01.E1`'s 51.5 was — is not a
measurement. Nothing was loosened: the per-turn scorer, the 0.0 failure path and the
85/72/55 verdict thresholds are untouched, and the bar is still ≥95 with no category
under 90. It is now **harder** to pass honestly, because it measures decisions rather
than absent keys. `bench/test_scorecard_integrity.py` (68/68) proves the arithmetic
hermetically, including the inverse check that every scenario expecting a credentialed
tool declares it, so a new scenario cannot forget and quietly shift the score.

**What is still missing, stated plainly: a number.** The suite drives the real agent
and needs a model, so producing a post-fix score requires a run with credentials
configured. Until that run exists, the honest reading of `01.E1` and `01.E2` is *"the
instrument is trustworthy, the score is unmeasured"* — and an unmeasured score is not 95.

Under D-43, the honest elite bar for a single-operator system is unchanged and
unchaseable-by-instrument: **thirty days of real use with zero panics, zero data
corruption, zero unexpected cloud egress.**

## D-45 — Registry granularity: 403 tasks → ~40 milestones **(commit)**

403 micro-tasks is administrative overhead for one maintainer. Planning moves to ~40
cohesive architectural milestones. Task-level history stays in the registry as an audit
trail; it stops being the planning surface. **Applies to S01–S50 planning.**

## D-46 — Capacity is 8–10 hours per week **(commit)**

That capacity goes to **deleting or completing dark systems before touching speculative
elite work.** Dark code is either wired to reality or moved to a dormant contrib
directory — not bridged with artificial engineering.

## D-47 — Model evaluations are advisory; a model may choose, but never decides what is on offer **(commit)**

Model-scored directives (e.g. the S49 drop) are input, not authority. De-scoping
requires the owner's deliberate review and explicit sign-off. Every automated drop in
the registry is re-reviewed before it is believed.

**Amended 2026-10-03**, because D-72 put a model on the turn's decision path and this
decision would otherwise have read as if it had been quietly deleted. It was not, and the
distinction is the entire safety argument:

**A model may still never:**
- de-scope, cancel, or re-scope work — the owner's signature is required (this is exactly
  what the S49 drop needed re-signing for);
- authorize an action, confirm one, or lift the blast radius;
- invent the options it is choosing between;
- see conversation history, vault memory, tool output, credentials or biometrics.

**A model may now:**
- choose among candidates that deterministic code produced (D-72), inside a 400ms budget, and
  where failing to answer restores the deterministic path exactly (D-73).

So the rule is not "models have no authority" — it is **"a model decides between options the
code drew, and never draws them itself."** The owner's judgement over the *work* and over any
*action* is untouched. **Applies to S01, S14, S44, S45, and every `owner-decision` record.**

## D-48 — S49 fabrication is out **(commit)**

Physical vanity scope belonging in a standalone slicer/CAD utility, not an ambient
assistant. Already dropped 2026-09-20; D-47 requires that drop to be re-signed by the
owner. The doc stays as a decision record, not a roadmap.

## D-49 — Barge-in at ~700 ms is a known defect **(commit)**

Measured worst case. Above 350 ms conversational interruption feels unnatural. This is
a defect with a number, not a preference.

## D-50 — A disciplined butler, not a companion **(commit)**

Dry, precise brevity. No sycophancy: no unsolicited apologies, no filler, no feigned
emotional investment. No moods, no synthetic emotional variance — a stable, transparent
instrument. Affect that degrades operational predictability is not charm, it is noise.

**A bad Afon** (the failure to notice within a week): it speaks when uninvited,
misinterprets intent, and produces half-baked background actions that force the owner
to open a terminal to undo them.

## D-51 — The user is one person **(feel)**

Guests, family and strangers are out of scope. The moment they are in scope, ambient
mics, room presence and biometric ID become social-surveillance liabilities that break
trust. Consent of everyone in the house is required for anything ambient.

## D-52 — Uncertainty is audible **(commit)**

Where there is no confidence bar to point at: an explicit hedge ("I'm uncertain, but
—") or lowered pitch and cadence. Never assertive delivery of an uncertain answer.

## D-53 — v1.0 is defined **(commit)**

Voice capture, task/calendar sync, Home Assistant actuation and vault memory running
**30 days with zero panics**. Reachable once dark code is pruned — not before.

## D-54 — Legacy continuity is boring formats **(commit)**

In 2036 the owner must be able to open plain markdown files and query a standard
SQLite database with vanilla command-line tools, without running this framework. Every
store must be legible to `sqlite3` and readable in a text editor.

## D-55 — The handover gap **(commit)**

Missing for a clean transfer: a reproducible bare-metal setup script and real
documentation of edge audio hardware tuning. Both are prerequisites for OpenAfon being
adoptable by anyone else, and neither exists. **Applies to S22, S18.**

## D-56 — On a poor microphone, refuse to guess **(commit)**

The gate rejects marginal audio and requires explicit push-to-talk rather than
transcribing through noise. A missed word is cheap; a fabricated one is not.

## D-57 — Open-source is a forcing function **(commit)**

Afon is a personal operational system first. Publishing OpenAfon is how the owner
prevents sloppy hardcoding, spaghetti architecture and uncommitted secrets. The repo is
private; the framework is the sanitized engine; "Afon" is the personal instance holding
the vault, tokens and hardware topology.

**Never in the public repo:** personal notes, vault contents, network hostnames,
cryptographic keys, biometric templates — enforced by git-crypt checks, environment
variables and pre-commit scans, not memory.

## D-58 — No topic is off-limits **(commit)**

Nothing is declined on subject matter, working on the owner's own local data. The only
refusals are operations risking catastrophic physical damage or violating a safety
invariant. Topic-sensitivity is surveillance theatre in a single-user home system.

## D-59 — The worst action, and its guard **(commit)**

The worst conceivable autonomous action: deleting or overwriting an entire vault
directory on the strength of a hallucinated deduplication plan. Guarded by
read-only-by-default filesystem mounts plus git versioning. Any handler that can make
a bulk destructive write is a D-13/D-59 violation regardless of intent.

## D-61 — Context inference is local-only, never broadcast or logged **(feel)**

State inference (Deep Work / Relaxing / Sleeping) is welcome *only* because it stays on
the host, where it suppresses audio notifications. The moment a derived state is
broadcast, logged to a timeline, or sent anywhere, the same feature becomes
surveillance and is removed — not disabled, removed. **Applies to S27, S43.**

## D-62 — The credential set is minimal, and every credential answers to a decision **(commit)**

The owner named four: **Home Assistant · CalDAV · Matrix · one weather/transit API**.
That is the *wanted* set, and it stays the standard every new credential has to beat.

**Amended 2026-10-03, because the first draft of this decision was wrong about the
system.** `.env.example` does not carry four third-party credentials; it carries roughly
fifteen, and the docs review found that three of them contradict other decisions in this
file. The rule is unchanged — minimal, curated, and every credential justified — but the
list has to describe the machine that exists:

| Credential | System | Answers to |
|---|---|---|
| `AFON_HA_TOKEN`, `AFON_HA_URL` | S28 | D-07 (lighting scenes flow silently) |
| Google OAuth — client, secret, refresh | S21, S38 | D-62, D-13 (dispatch refuses regardless) |
| Telegram — bot token, api id, hash, session | S38, S13 | D-62, D-18 |
| `AFON_NOTION_TOKEN` | S33 | D-62 |
| `AFON_TICKER_TOKEN` | S40 | D-12 (read-only market lookups only) |
| `AFON_TAVILY_API_KEY`, `AFON_JINA_API_KEY` | S41 | D-34 (focused sessions, never ambient) |
| `AFON_GIPHY_API_KEY` | S42 | D-62 |
| `AFON_BROWSERBASE_API_KEY` + project id | S05 | D-62 |
| `AFON_GITHUB_TOKEN` | S29, S39 | D-08 (self-edit rule) |
| `AFON_NTFY_TOPIC` | S13, S35 | D-11 (push, never an outbound voice call) |
| 7 × `AFON_PROTOCOL_*_PASSWORD` | S31 | D-02 (plaintext shell, no auth service) |
| `AFON_API_AUTH_TOKEN` | S36 | D-03 (transport auth) |

**And three that currently contradict this charter:**

- `AFON_ELEVENLABS_API_KEY` — D-17 says local TTS wins, and the key is configured **and
  `tts_provider` defaults to `elevenlabs` in `src/afon/config.py`**. So the decision is not
  merely unrecorded; the code's default is the thing D-17 rejects. Piper/Kokoro exists as a
  fallback that only fires when a cloud provider cannot be constructed. **Task `18.R4`.**
- `AFON_WAKE_WORD_ENGINE`, `AFON_PORCUPINE_ACCESS_KEY` — listed in `.env.example`, and read
  by **nothing**. `src/afon/config.py` records that Porcupine was evaluated and dropped on
  2026-08-01 and that these settings "sat here afterwards being read by nothing — settable in
  .env, and setting them did precisely nothing". The wake path is already on-device via
  openWakeWord, so **D-19 is honoured**; what is missing is the offline assertion and the
  removal of two settings that lie about the design. **Task `18.R5`.**
- `TYPESAFE_API_KEY` — D-47 says model evaluations are advisory input. The key is how Jev is
  called, so the advisory tool is wired into the plan's history. It stays, but only as input
  to a decision the owner signs.

**No new credential may be added without a row here.** Building the inventory is
**task `36.R4`**: every credential-shaped setting in the environment, mapped to a system,
a decision, and whether it is actually configured. **Applies to S19, S21, S28, S36, S38, S40, S41.**

## D-63 — Hardware joins the system only if it is local, placed, and split read-or-act **(commit)**

Written 2026-10-03 against the owner's device inventory
([HARDWARE.md](HARDWARE.md)). Three questions, in order, and a device that fails any of them
does not get integrated:

1. **Is it local?** No vendor cloud in the path. A device that can only be operated through
   a vendor's servers is owned, not integrated.
2. **Which room, and may that room have a microphone?** Bedrooms and bathrooms are
   permanently off-limits to ambient hardware (D-38), so placement is decided before the box
   is unboxed.
3. **Read or actuate?** Reads are cheap and reversible. A device that both reads and acts is
   split: Afon keeps the read, the physical act stays with the owner (D-14).

**Applies to every device in the inventory.** Falsified by a device that reports to a vendor
cloud, sits in a bedroom, or actuates something physical without the owner.

## D-64 — One radio, one owner of the mesh **(commit)**

Two Zigbee coordinators against one mesh produce devices that appear and disappear
depending on which claimed them last. The ZBT-1 is the coordinator; Home Assistant Green's
built-in radio stays unused. Same principle as D-03 — no second network boundary, no second
thing that can be down.

## D-65 — A smart lock is read-only to Afon **(commit)**

The Aqara U200's state may be read and reported ("the front door is unlocked"). **No code
path actuates it** — not over Matter, not over Thread, not over Zigbee, not through Home
Assistant, not with a confirmation, not inside a macro or a skill. This is D-13 applied to
local hardware instead of a cloud one, and it is enforced by `28.R4` for the Home Assistant
path and tracked by `28.R5` for the lock itself.

**The NFC tag is the owner's path back.** A tag on the wall by the door is a physical act in
the literal sense — touch required, unforgeable by voice. That is D-14 satisfied by a
12-cent object, and it is the answer to the question left open in
[subsystems/28](subsystems/28-iot-orchestration.md): how does the owner open a locked door
at 2 AM without a confirmation standing in for presence? With the tag.

## D-66 — Video frames never leave the house **(commit)**

Detection runs on the local accelerator. Only event metadata — zone, label, count,
timestamp — may reach the brain. A frame is never sent to a vision model, a log, or a crash
report. The cloud vision chain serves screenshots the owner explicitly asks about and
nothing else.

This extends D-61, which covered derived context, to pixels. It is load-bearing because the
configured vision chain is **cloud-only** today, so a frame that reaches it has left.

**The codebase already contains both patterns.** In `src/afon/brain/tools/camera.py`,
`look_around` hands a webcam frame to a vision model, while `visual_presence` counts faces
locally and never lets the image leave — its own docstring says so. D-66 is therefore not a
new constraint: it is the rule that the second behaviour must be the only one on the
detector's path, and the first stays where it is, answering an explicit owner question about
something he is looking at. `look_around` must never become the channel through which a
Frigate event is explained. **Tracked by `26.R5`.**

**`visual_presence` is also a second presence source** — a local face counter on the laptop
webcam, predating the mmWave sensors, and an ambient camera in a room whether or not anyone
intended one. It is legitimate: it is the owner's own machine, counting his own seat. S43
must know it exists when it decides which presence source is authoritative.

## D-67 — One wake phrase on three always-listening satellites **(commit, proposed)**

D-19 says one wake phrase, and the code has **seven** (`src/afon/config.py`:
`afon, alfred, robbin, assist, time to work, wake up, six-one-nine`). On a single laptop
button-press that is a harmless convenience. On **three** HA Voice satellites it multiplies
false wakes threefold, and a 3 AM false wake is precisely the failure D-19 exists to
prevent.

The satellites get **one phrase that answers to a name**, not a command. "Time to work" and
"six-one-nine" belong on the laptop, where a misfire costs nothing because the owner pressed
the button. **Affects S18, H5.** Awaiting the owner's nod — see
[HARDWARE.md §9](HARDWARE.md#9-where-this-hardware-contradicts-the-charter) row 4.

## D-68 — Appliance circuits, not the core **(commit, proposed)**

Shelly plugs may switch and cut an **appliance** on a safety signal. They may never touch
the main breaker, the UPS-backed core circuit, the network, or anything that would make the
house dark or the brain unreachable. D-13's "main power breakers" is read as a circuit
boundary, not a product name. Awaiting the owner's nod on which circuits are in scope.

## D-69 — Presence is a house fact, not a laptop poll **(commit)**

`src/afon/brain/presence.py` is a **laptop activity poller**: it reports which app is in
the foreground and how long the owner has been idle. That is not presence, and the docs that
described presence as "BLE plus PIR" were describing an intention rather than the code.

The mmWave sensors make it real. Two rooms for presence — office and living — plus the
hallway as the transition room (D-37). A bedroom or bathroom sensor is refused at
configuration time, not at review time (D-38). A missing sensor **holds the last verified
state** rather than guessing. **Tracked by `43.R5`.**

## D-70 — S49 stays dropped, and the hardware says why **(commit, proposed)**

D-48's revisit trigger was "owning a printer, and wanting a slicer it can call." Half of
that is now met: the owner owns a Prusa CORE One, a fire-suppression ball, a filament dryer
and a maintenance kit.

The recommendation is to **keep S49 dropped**, because the second half of the trigger is not
met. A printer in a workshop is a tool for making brackets; a printer Afon can drive is a
safety surface with a heated bed and moving axes, in a house where D-13 already refuses door
locks. By D-47 this needs the owner's sign-off, not mine — but the charter's instinct was
right and the new hardware confirms it.

What the printer does need regardless: fire suppression for unattended prints, dry storage,
and **no print running overnight while the house is empty**. **Applies to S49, S06, H7.**

## D-71 — A print job's contents never enter the system **(commit)**

The laser printer is used for hard-copy documentation *and for 1Password emergency sheets*,
which means secrets on paper. The print action is local and fine. The rule is that a print
job's **content** must never enter the agent's context, a tool argument, the audit trail or
a log. The tool call is "print the emergency sheet", never the sheet's contents. That is
D-57 with paper instead of git. **Applies to S06, H7.**

## D-72 — Jev arbitrates the tool choice, and only within a boundary code drew **(commit, owner's decision 2026-10-03)**

The brain's turn loop has exactly one decision the deterministic router cannot make for
itself: an utterance that matches **two or more lazy groups**. "My inbox has something
about the lease document" is `office` and `docs` at once. Until now every matched group was
armed and the generative model chose among ~60 advertised tools.

**Jev now makes that choice**, and the shape is what makes it safe:

- **The candidates come from code.** The trigger match supplies them. Jev never invents a
  candidate and never receives one from a model, so a model choosing among them can only
  *narrow* the surface, never widen it. This is D-04 in a new place: the typed boundary is
  what makes a model decision safe to act on.
- **The model only phrases.** It receives the winning group's tools and nothing else from the
  candidates. It cannot reverse the pick, and it cannot reach a group the router did not
  surface.
- **Fewer than two candidates is not a decision**, and costs no call at all. Chatter, ordinary
  single-topic turns and the entire pure-chat fast path never touch the network here.
- **A compound request is not arbitrated.** A multi-intent turn legitimately needs several
  groups at once; the per-clause plan steers those, and arbitrating to one would break them.
- **A group Jev did not pick is not disabled.** It was simply not armed by this utterance, and
  its own trigger still arms it whenever the owner next asks for it.

**This does not change what D-47 forbids.** A model still cannot de-scope, cannot authorize
an action, and cannot invent what was on offer. It chooses among options the code produced.
The distinction is the whole safety argument: *authority over a decision* is still the
owner's, and the confirmation gate, the blast radius and the governor are unchanged.

**Falsified by:** a code path where the advertised surface can contain a group the
deterministic trigger match did not surface.

## D-73 — Arbitration is bounded at 400ms and fails silently **(commit, owner's decision 2026-10-03)**

A laptop turn is budgeted under 300ms (D-35). An arbitration that arrives after the owner has
finished speaking is worse than none, so the cap is **400ms** — far below the service's 8s
timeout — and past it the verdict is discarded.

**Failure is silent, and that is the deliberate asymmetry.** The two Jev seams have opposite
fallbacks, and conflating them is how "the model was unsure" becomes "the model decided":

| Seam | When Jev cannot answer | Why |
|---|---|---|
| Explicit two-option question (`14.R5`) | **Ask the owner.** Full 8s timeout. | The alternative to Jev is a guess about the owner's life. Asking is the honest answer |
| Tool arbitration (`01.R6`) | **Keep every candidate.** Silent. 400ms cap. | The alternative to Jev is a working deterministic router. Speed beats a marginal improvement |

A timeout is written to the provenance log with `fallback: deterministic`, because a cancelled
call produces no row on its own and an audit trail with holes in it is not an audit trail.

**And the one rule that keeps this honest:** a failed arbitration must offer *exactly* the
surface the deterministic path would have offered, and the owner must never hear that it
happened. If the winning group's tools do not fit the catalogue budget, the candidates stand —
"Jev chose" must never mean "the owner got less".

**Cost, stated plainly:** the owner's live utterance now leaves the host on ambiguous turns,
not only on explicit two-option questions. It is the same utterance, under the same outbound
contract (no history, no memory, no tool output, no secrets, no biometrics) — but it happens
more often, and that frequency increase is the real price of this decision.

**Falsified by:** arbitration adding measurable latency to a turn, or the owner ever hearing
about it.

## D-74 — An ambiguous answer gets one question, not a guess **(commit, owner's decision 2026-10-03)**

> "Create a follow-up mechanics for the answers that are ambiguous and do not give a clear
> decision indication."

That already existed in a narrow form: `01.R2` catches a **pointer with no antecedent**
("the same as before", "that thing") and asks once. Two things were missing, and both are
now in place:

- **Jev detects what a regex cannot.** The turn assessment asks whether the owner's request is
  specific enough to act on without guessing. `set it to three` has no pointer in it and was
  previously answered with a guess.
- **A pick below the confidence floor is not a decision.** If Jev names a group at 51%, that
  is a coin flip, and a coin flip must not quietly become the tool surface. The turn asks
  instead.

**And the distinction that makes it safe: silence is for a FAILED assessment, not an unsure
one.** If the service is down, the turn must not start asking the owner to clarify turns that
are perfectly clear — that turns an outage into a stream of questions about things he already
said clearly. Only an assessment that *succeeded* and said "unclear" earns a question.

**Exactly one question, and it is phrased as a question.** The first wording tried was "say a
bit more and I'll take it from there" — which instructs rather than asks, so an owner who hears
it does not know he has been asked for anything, and the clarifying turn becomes a second round
of guessing. The gate caught it; the wording is now a real question.

**Falsified by:** a clear turn producing a question because the service was unavailable.

## D-75 — Urgency and tone shape the reply and nothing else **(commit, owner's decision 2026-10-03)**

> "We always need to get the urgency and the tone."

Jev now returns both on every assessed turn, in the **same** call as routing and clarity —
one round trip, because three sequential calls would spend three budgets and the third would
be reading a different moment from the first.

**What urgency is allowed to do:** frame the reply (answer first, no preamble, no
restating the question) and, in future, prioritise a delivery *within* a budget that already
exists.

**What urgency is never allowed to do:**

- raise the interruption budget (D-29),
- pierce quiet hours (D-32),
- or stand in for life-safety, which remains deterministic code and the only thing that
  pierces them (D-18).

That line is asserted in the gate, not just written here: a framing note that mentions a
budget or a quiet hour fails the test. A model that could talk its way past the three-a-day
limit would make the limit a suggestion.

**Tone refines; it does not replace.** `afon.brain.affect`'s cue-word inference is local,
always available and cheap, and stays the floor. Jev's register (`direct`, `steady`,
`gentle`, `curt`) refines it when the service answered. A Jev outage costs the refinement
and nothing else.

**Falsified by:** urgency changing how many interruptions the owner receives in a day.

## D-76 — The gate is entropy, not a fixed probability **(commit, adopted 2026-10-03)**

A threshold on the top probability is **wrong in a way that only shows up as the system
works.** `0.60` means "quite sure" across four options and near-total uncertainty across
two, so one number was quietly judging two different situations by the same yardstick.

Replaced with the normalised Shannon entropy of the whole distribution,
`H_n = H(P) / log2(K)`, and three bands:

| Band | `H_n` | What happens |
|---|---|---|
| **fast** | below the bar | the distribution has an opinion — narrow to it and act |
| **marginal** | up to 0.60 | it has an opinion it will not stand behind — ask the owner |
| **ambiguous** | above 0.60 | it has no opinion — give the model the full surface and let deliberation decide |

**The routing bar is looser than the safety bar, and the difference is deliberate.**
Narrowing the tool surface is low-stakes: the unpicked groups are not lost, they re-arm on
their own triggers next turn, and the model keeps the core belt either way. Whether this
is the owner, or whether this lock may open, has no such floor. One threshold for both
would either make routing never fire or make safety permissive, and those failures are not
symmetric.

**What this changed about asking.** Uncertainty about *which internal bucket* an utterance
fell into is **the system's** problem. So an ambiguous route now hands the model the full
surface — it does **not** ask the owner to choose between words he has never used. The only
thing that earns a question is the owner's own request failing to name its object. The
clarifying prompt says *"what exactly should I do with it?"* and never mentions a group.

**Falsified by:** one probability landing in the same band regardless of how many rivals
it had.

## D-77 — The external brain proposal is adopted in part, and three of its parts are declined **(commit, 2026-10-03)**

A detailed dual-process brain proposal arrived on 2026-10-03. It is mostly a good
restatement of what this project already decided, and it is wrong in five places.

**Adopted, because it is better than what we had:**

- **The dual-process principle** — never use open-ended generation where a calibrated
  distribution suffices. That is D-72, arrived at from a different direction.
- **Jev as a thalamus** — the fast probabilistic layer on every event, generative
  deliberation reserved for what deserves it. Already the architecture.
- **A bundled multi-predicate query in one request.** Already `assess_turn`.
- **A circuit breaker with deterministic local fallback.** Already D-73, at 400ms.
- **Entropy gating (D-76).** Genuinely better than the fixed floor it replaces.

**Declined, each reversing a decision the owner signed:**

| Proposal | Reverses | Why |
|---|---|---|
| NATS JetStream, `jarvis.cmd.*` subjects, durable consumers | **D-01** | A message bus is a second thing that can be down and a third boundary to secure. One WebSocket, one process |
| PostgreSQL with `JSONB`, `goals_strategic` tables, `gen_random_uuid()` | **D-02** | Postgres was cancelled. The registry says so and the scaffolding is queued for deletion |
| OPA pre-flight policy validation | **D-04** | The typed boundary replaced it. Adding an OPA node adds a service to fail at 2 AM for rules a Pydantic model already enforces |
| LangGraph as the System 2 cortex, replacing the turn loop | — | The turn loop is measured: 51/51 pure-chat, 27/27 catalogue budget, 26/26 Jev, 38/38 arbitration, 48/48 assessment. Replacing a working, gated system from a document rather than a measurement is the exact inversion this project refuses |
| Fish Audio as the speech gate | **D-17** | Local Piper/Kokoro is the decision; ElevenLabs is opt-in |

**Three defects found in the proposal, recorded so they are not re-imported:**

1. **The L0 exact-hash cache dispatches actions.** Hashing `context_digest + utterance` and
   replaying a cached decision means the same words can re-run an old action. Worse, the
   digest in its own example is a **constant string** — `Mode: ACTIVE_DESK. Focus:
   ENGINEERING. Network: LOCAL_LAN.` — so focus mode and calendar are never part of the
   key. A cache that dispatches must key on the state that made the decision safe, or be
   scoped to *reads*. **Not built, deliberately.**
2. **The outage fallback is a 0.50/0.50 distribution.** Under the proposal's own gate,
   uniform is maximum entropy, so a Jev outage would escalate **every** turn to the slow
   tier — the failure path would be slower than the happy path, permanently. Our fallback
   is the deterministic router (D-73), which is fast *and* correct, so a Jev outage
   degrades rather than reverses.
3. **"Complete immunity from prompt injection" is false** and must not be repeated. A
   cloud model reading the owner's utterance is *more* exposed to injection than a local
   one — the utterance is untrusted input to a remote service. What Jev actually buys is
   **narrowing the action space**: it can only choose among labels the code declared. That
   is real defence, and it is the typed boundary (D-04), not non-generativity.

**What the proposal gets right that we have not done yet:** the `score` primitive — an
ordinal 1–10 urgency with an expectation, rather than three buckets. It is a better
instrument for prioritisation. It is **not** adopted, because the wire format for a score
answer is not verifiable from this repo, and inventing an unverifiable response shape is
precisely the phantom-gate trap `bench/test_doc_paths.py` was written to catch. It becomes
a task when the real contract is known.

## D-78 — Speaking five languages is a requirement, not a preference **(commit, owner's decision 2026-10-04)**

The owner speaks French, English, German, Ukrainian and Russian. That is not a feature
request; it is the shape of the person this system exists for, and it decides two
settings that looked like preferences until it was said out loud.

**1. TTS stays ElevenLabs on this machine, and the code default stays `piper`.** This is
D-17 working, not failing — D-17 makes cloud the opt-in for when the quality is worth
the egress, and here it plainly is. What decided it is a measurement, not a preference:

- The local engines are **English-only as wired.** `piper_voice` is one monolingual
  model, `.piper-voices/` holds exactly one English voice, and Kokoro is pinned to
  `Language.EN`. There is no per-language voice selection anywhere in the repository, so
  "local" would in practice mean "local English", which is not the requirement.
- `shared/language.py` already supports exactly `en, ru, de, fr, es, uk`, and the
  `match` reply-language sentinel — answer in whichever language the owner just used,
  with sticky hysteresis and alphabet-based ru/uk disambiguation — exists for this man.
- `match` has no working local implementation. It is designed around a *multilingual*
  model: `eleven_flash_v2_5` detects per utterance, and a build-time language pin would
  lock the voice to one language for the life of the process. The multilingual model and
  the `match` feature are a matched pair.

**2. STT is an OPEN CONFLICT, and the shipped default stays `deepgram`.** The owner wants the
local ear, and the reason is a defect rather than a preference: Deepgram's nova-3 `multi` model
covers en/es/fr/de/ru and **not Ukrainian**, so a Ukrainian sentence did not fail — it came back
as plausible Russian, the language detector agreed with it, and Afon answered confidently in the
wrong language. A setting listing six languages while the ear hears five is exactly what looks
configured and is not.

The alternative was then measured on the owner's own CPU rather than argued about. On
2026-10-04, `whisper_model=base` — the *fast* size, int8, CPU only — over five synthesised
utterances: **mean 3.00s, median 2.94s, p95 3.95s, real-time factor 1.39.** It transcribes more
slowly than the owner speaks: a 1.8-second phrase takes 2.95 seconds to become text. The D-35
budget allows 1800ms mean, so local Whisper is **1.7x over** it, while Deepgram's endpointing is
300ms.

So neither provider is acceptable alone:

| | Ukrainian | Every other language | Mean latency |
|---|---|---|---|
| Deepgram | **silently wrong** | correct | ~300ms |
| Whisper `base` | correct | correct | **3000ms (1.7x over budget)** |

Fast-but-wrong, or correct-but-1.7x-over-budget everywhere. The resolution is to **route by
language** — Deepgram for the five it hears, Whisper only for the one it cannot. A Ukrainian turn
is then slow and correct, which is the right trade, and every other turn keeps its 300ms. That is
`18.R7`/`18.R8`, and the shipped default stays where the measurement says it can live until the
owner chooses between "accept 3s on every turn" and "build the router". **The Ukrainian defect is
real either way and is not closed by this decision.**

**How the router had to be built, because the obvious version does not work.** The obvious design
identifies the language from the *audio* before trusting any transcript — a transcript is the thing
that is wrong, so routing on it is circular, and `shared/language.detect()` runs on text and is
therefore downstream of the error. That design was measured and **rejected**: the only audio-level
LID available is faster-whisper `detect_language()`, and on this machine (int8, CPU) it costs
**1089ms on `tiny` and 2425ms on `base`**. Every turn would pay ~1.1s to avoid at most ~1.1s of
transcription — a 4.7x regression on the five languages that already work, and on Ukrainian
*slower* than simply using Whisper, which auto-detects for free as part of transcribing. Net loss.

What works instead is **sticky, feedback-driven** routing: the primary ear stays, a transcript
teaches the router where the *next* turn goes, and the language leaving that state is confirmed by
text — so the entry is inferred and the exit is reliable. Marginal cost on a normal turn is one
string scan. The residual cost is stated rather than hidden: **the first Ukrainian turn of a
conversation is still misheard**, because it is the turn that reveals the language and it was
transcribed by the ear that cannot hear it. It is counted (`missed_first_turn`) so it is
measurable instead of folklore. Closing that last turn needs a predictive LID, which this hardware
cannot afford — and that is the trade, not an oversight.

**The asymmetry this produces, named so a later reader can see what was traded:** what the owner
*says* is currently sent to a cloud recogniser; Afon's *replies* are sent to a cloud voice. The
37.R5 never-store guard does **not** cover either surface — it withholds a D-24 payload from the
audit trail, not from an STT or TTS request. What it does guarantee is narrower and worth having:
a never-store *refusal* is one of four fixed spoken strings, so a refused secret cannot reach the
voice even in principle.

**What would retire this exception:** per-language local voices. Piper publishes voice
models for ru, uk, de and fr, and the wiring this decision lacks is a language→voice map
and a `match` implementation for it. Built, the code default could return to local without
costing a single language. Until then the honest line is that local-first holds on the
ear and not on the mouth, and no amount of prose should make that sound otherwise.

## D-79 — Afon routes work to executors; it does not do their jobs **(commit, owner's decision 2026-10-06)**

> "Afon has to be a Jev guided brain that can use the browser manage my daily life and so
> on, the daily tasks are routed to openclaw agents, the coding tasks are handled by Claude
> Code through the CLI … financial analysis … through Rubo CLI."

Afon's own job is the voice, the judgement, the typed boundary and the audit trail. The work
itself goes to whichever executor is best at it:

| Domain | Executor |
|---|---|
| Daily life, errands, admin | the OpenClaw fleet |
| Coding | Claude Code, Codex, and a third if one exists |
| Financial research | Rubo (see D-83 for the line it may not cross) |
| Reading and summarisation | the owner's own SDK (D-86) |
| The web | Afon's own visible browser (D-82) |

**What this does not change.** D-05 still holds in full: an executor is a tool, never the
assistant, and its answer reaches the owner in Afon's voice after Afon has checked it. The
identity never leaks outward, and an executor's output is never delivered as Afon's own
judgement without a verification gate.

**The cost, stated rather than discovered later.** This is the largest single addition of
moving parts the project has accepted, and it argues against D-01. The mitigation is that
every executor implements **one** adapter contract — one dispatch surface, one cost ledger
entry against `src/afon/brain/governor.py`, one audit row — so the 2 AM question has one
answer rather than four. An executor that cannot be diagnosed through that one surface is a
defect in the adapter, not a new subsystem.

**Falsified by:** a second executor needing its own cost accounting, its own audit shape, or
its own failure mode.

## D-80 — A coding CLI is a headless subprocess with a diff as its only product **(commit, owner's decision 2026-10-06)**

D-05 names the exact way this line erodes: *"the moment an agent is handed an unconstrained
interactive shell with root or network access."* The line is therefore drawn at
**interactive**, not at *CLI*:

- **Non-interactive invocation only.** `codex exec`, `claude -p`, or the Agent SDK's
  subprocess-over-stdio-JSON path. No TTY, no REPL, no shell handed over.
- **A machine-readable result or nothing.** Where the executor can enforce the result shape
  itself — Codex's `--output-schema` — the adapter uses it. Prose is parsed only where there
  is no alternative, and a parse failure is a failure, never a guess.
- **A diff is the product.** The executor proposes; it never lands anything. The diff goes
  through D-08's four conditions — dedicated branch, green suite, zero schema migrations, the
  owner's explicit approval — exactly as a self-edit does.
- **No credential path.** An executor receives a brief and a repo. It does not receive `.env`,
  the vault, biometric templates, or any secret, and the adapter is where that is enforced.

**This reverses a declined row.** `docs/ARCHITECTURE.md` records the blueprint's
"Claude→Codex→MCode chain" as declined in favour of `src/afon/brain/code_improve.py`. That
decline was right about the gVisor sandbox fleet and wrong about the chain: the CLIs now ship
the headless, permission-moded, schema-enforced interfaces that the decline assumed did not
exist. The table owes a correction.

**Falsified by:** an executor reaching a file outside the brief's repo, or a diff landing on
any branch without an owner approval recorded in `src/afon/brain/audit.py`.

## D-81 — Jev picks the executor, within candidates code produced **(commit, owner's decision 2026-10-06)**

The same shape as D-72, one level out. Code decides which executors are **configured** and
which **match the brief's domain**; Jev chooses among those; the entropy bands of D-76 decide
whether that choice is acted on, questioned, or widened.

Everything that makes D-72 safe applies unchanged: Jev never invents a candidate, can only
narrow, and cannot authorise anything. The 400 ms cap and the silent deterministic fallback of
D-73 apply — and the fallback here is a declared default per domain, not a guess.

**One addition, because the stakes differ.** A wrong tool group costs a turn. A wrong executor
costs a wrong *action in the world* — an errand run, a repo touched. So an executor choice is
never silent in the audit trail even when it succeeds, and a brief whose domain matches no
configured executor is refused rather than sent to the nearest thing.

**Falsified by:** an arbitration naming an executor that is not configured, or an executor
running against a brief whose domain it does not serve.

## D-82 — The browser adopts the Jev-per-step loop, and keeps the visible Chromium **(commit, owner's decision 2026-10-06)**

> "if there are any open source solutions to enabling some capabilities let's utilize them …
> for example there is jev browser repo that is going viral."

The owner is right, and the reason it fits is not that it is popular. The public Jev browser
agents observe a page into a numbered table of elements and available operations, ask Jev for
the operation *and* the target in one round trip, and let a text model supply a value only
when the operation is a type. **That is D-04 and D-72 in a domain where we had not applied
them.** It is adopted.

**What is not traded away.** S05 exists for a *visible* browser on the owner's screen with his
persistent logins — `src/afon/brain/tools/browser.py` forwarding to `src/afon/edge/pc_agent.py`.
A headless agent driving an invisible browser with an empty cookie jar is the cloud path that
already exists, and the subsystem doc is explicit that conflating the two is how a headless
fetch answers as though he had been watching. So:

- The **decision loop** is adopted from the public work.
- The **surface** stays ours: visible, local profile, laptop-side.
- An external implementation is used directly only if it can drive that browser. That is a
  measurement (`TODO.md` M49), not a preference.

**And one thing is closed first.** `05.R1` — confirm before a submit that spends money or
sends data — is open today, which means a spend is one voice command away. A faster browser
loop in front of an open confirm gate is a worse system, not a better one, so `05.R1` lands
before the loop changes.

**Falsified by:** a page summarised from model knowledge rather than page text, or a browser
window opening where the owner cannot see it while he believes otherwise.

## D-83 — Money is Rubo's domain, and D-12 is amended **(commit, owner's decision 2026-10-06, restated and broadened the same day)**

> "finances, taxes, investments, portfolio management, salary management and distribution is
> managed by Rubo which is our own CLI agent"

**This amends D-12 by name.** D-12 read *"finance is a hard no — no bank feeds, no transaction
ingest, no personal ledgers. Read-only market lookups only."* That is no longer the scope. The
first version of this decision was written on the narrow reading — research and read-only
valuation — and the narrow reading was put to the owner with the conflict named. He restated the
broad one. It is his call, and it is recorded as made rather than argued with again.

**What D-12's refusal was actually protecting**, so that what remains of it is deliberate: blast
radius, not capability. Its own sentence is *"transaction data is an unacceptable blast radius for
zero assistive gain"* — and the gain is no longer zero, because the work is now done by a CLI the
owner wrote, on his own hardware, rather than by an API integration inside the brain.

**So the line moves to where the charter already draws it, and no further.** Afon may read,
compute, model, draft and propose across all of it — taxes, investments, portfolio, salary
planning and distribution schedules. What it may not do by itself is **move money**, because
D-13 puts external dispatch outside the blast radius without the owner physically present, and
D-14 says a refusal is overridden by a typed flag or a hardware key rather than by asking. A
transfer, a payment and a trade are external dispatch. They are prepared by Afon and executed by
the owner.

That is one standing decision, not a new hesitation — if the owner wants it struck, the thing to
strike is D-13's fourth bullet, deliberately, in its own row.

**Two consequences that are not negotiable, because they are what make the amendment safe:**

- **Rubo holds the data; the brain holds none of it.** No statement, balance, transaction or
  salary figure enters `memory.py`, the vault mirror or the audit trail. The executor returns an
  answer; the figures behind it stay in Rubo's own store on the owner's machine. `D-24`'s
  never-store set is the enforcement shape, and the finance class belongs in it.
- **The spoken answer carries its as-of time and its source.** Already `40.F3`'s rule for quotes,
  and it matters more here: a stale tax number read confidently is worse than no number.

**Falsified by:** a financial figure appearing in a stored memory, a vault note or an audit line;
or any path that executes a transfer, payment or trade without the owner's physical act.

## D-84 — Hardware integration standardises on one coordinator and the live protocols **(commit, owner's decision 2026-10-06)**

> "make sure that our openwatari can seamlessly integrate with hardware of different kind."

Seamless means **one** integration seam, not a driver per device. Home Assistant is that
seam: devices join HA, and Afon speaks to HA. `docs/HARDWARE.md` keeps sequencing authority
for all 28 devices, and nothing here overrides it.

Three protocol facts the plan has to carry, because reaching for the obvious library gets one
of them wrong:

- **Satellites speak ESPHome.** The Wyoming *satellite* project is retired upstream, replaced
  by Linux Voice Assistant on the ESPHome protocol, which carries timers, media and
  stop-wake-word. H5 is right about what to buy and would have been wrong about how to talk
  to it.
- **Services speak Wyoming.** openWakeWord, Whisper and Piper behind the Assist pipeline — the
  same components `src/afon/edge/` already runs locally.
- **One radio owns the mesh** (D-64), and the smart lock is read-only forever (D-65),
  already enforced by `bench/test_blast_radius_refusal.py`.

**Falsified by:** a device integrated through a bespoke Afon driver when an HA integration
existed, or satellite code depending on the retired satellite client.

## D-85 — A capability enters through MCP first, a subprocess second, and our own code last **(commit, 2026-10-06)**

`src/afon/brain/mcp_client.py` already converts any stdio MCP server into normal
schema-validated Afon tools, namespaced `mcp__<server>__<tool>`, launching **only** servers
listed in the `mcp_servers` setting. That is the cheapest door and the one with the smallest
surface, so it is tried first; a non-interactive CLI with machine-readable output is second;
writing it ourselves is last and needs a recorded reason.

This is D-06 and PRINCIPLES §6 applied to integration rather than to handlers: the default
answer to a new capability is a configuration line, not a module.

**Falsified by:** an in-repo implementation of something an allowlisted MCP server already
provided, with no decline recorded.

## D-86 — The Bookroom SDK is a tool, not an executor **(commit, owner's decision 2026-10-06; revised the same day against the real repository)**

The owner's summarisation SDK arrived: `bookroom-sdk` v1.0.0, with a `SKILL.md` in its root. It
turns an EPUB or PDF into a 16-section study guide, has JEv score every section, and exports
Markdown, PDF, a concept-map graph, a claim audit and a manifest.

**The first version of this decision said it would enter as an executor adapter under D-79, and
reading the repository changed that.** The decline is recorded rather than quietly dropped, because
the reasons generalise to the next library someone wants to route through the executor contract:

1. **Its own first rule is that Python holds the keys in the process.** Afon's brain *is* the
   server-side Python process the SDK is designed to live in. A subprocess would marshal
   `GEMINI_API_KEY` into a child for no gain.
2. **The CLI has no `preflight`.** `bookroom` exposes serve / check / describe / guide / extract,
   and `guide` does not preflight on its way in. Preflight is the one call the SDK says to always
   make before spending, so routing through the CLI would lose exactly the safety step.
3. **A study guide is a long checkpointed job**, resuming from its last finished stage. That is not
   the contract's deadline-and-result shape, which fits an errand.

**So the executor contract applies to agents, and a library is a tool.** The line is worth stating
because it is the one that keeps `src/afon/brain/executors/` meaningful: that contract exists to
bound something which acts on its own judgement. Nothing on the other side of Bookroom decides
anything.

**What is kept from the contract, because the reasons were never about subprocesses:**

- **The paid call is fenced.** `guide` is refused until a preflight for that same file has run
  within thirty minutes — and it is a *refusal*, not an automatic estimate, because the point of
  the number is that the owner hears it. An expired estimate is refused like none at all.
- **Only the paid call is gated.** `check`, `outline` and `preflight` spend nothing and confirm
  nothing. A gate in front of a cost estimate teaches him to skip the estimate.
- **The run is charged to the governor**, like any other spend.

**Three honesty rules, taken from the SDK's own skill file and asserted by test rather than
trusted:** `quality` is always spoken as *n of 16 categories met the threshold*, and a partial run
is never worded as a pass — nor is a missing quality figure; `claim_audit` is always described as
**lexical overlap, not fact-checking**, with the words "verified" and "fact-checked" asserted
*absent*; and every failure mode speaks its own remedy, with the over-budget case stating that
nothing was spent.

**What it cannot do yet, stated plainly.** The SDK wraps a **separate** application — a flat tree
containing `book_pipeline.py` — which it imports from `BOOKROOM_APP_ROOT`, and that engine is not
in the SDK repository. Every call goes through it, `extract` and `check` included. Until the owner
installs the package into the brain's interpreter and points that variable at the engine, the tool
says so and names the variable. Per the SDK's own definition of done, this integration is
incomplete until a real book has produced a validated report: *"do not report success on the
strength of a unit test alone."*

**Falsified by:** a guide running against a book that was not priced; a partial run reported as a
pass; the claim audit described as verification; or any code in `src/afon/` importing the SDK at
module import time rather than inside the handler.

## D-87 — Personal work runs on free models; corporate work runs on the best **(commit, owner's decision 2026-10-06)**

> "personal is taken by the openclaw agents with free llm models, corporate is powered by
> openclaw with some of the best models"

The split is the owner's, and it is a cost decision rather than a quality one: a dentist
appointment and a board paper are not the same errand, and paying frontier prices for the first
is how the budget for the second disappears.

So `tier` is a field on a brief, not a setting on the system: **the same executor binary serves
both tiers under different agent configurations**, which is why `openclaw-personal` and
`openclaw-business` are two rows in `src/afon/brain/executors/__init__.py` rather than one row
with a flag. A row per tier is what makes the routing legible in an audit line — "which model
paid for this" is answerable by reading the executor name.

**Two rules that follow, and are gated:**

- **Coding is corporate-tier only.** The owner put coding on the corporate CLIs; a free-tier
  coding executor is not a cheaper option, it is a different outcome, and the diff still has to
  pass D-08's green suite either way.
- **A tier is never inferred from the task text.** It comes from the domain, by table. Inferring
  it would mean a model deciding how much the owner's money to spend, which is the one thing
  D-47 says a model never decides.

**What this does not do:** change the interruption budget, the governor's ceilings, or what gets
confirmed. A corporate brief is more expensive, not more privileged.

**Falsified by:** a daily-life brief dispatched to a corporate-tier executor, or a tier chosen by
anything other than the domain table.

## D-88 — The four managed CLIs update themselves daily, and an update must prove itself **(commit, owner's decision 2026-10-06)**

> "once in 24 hour check for the openclaw, codex, claude code and mcode version updates, if there
> is the newer version available automatically run the update commands and do the check test
> (sending ping to receive pong to make sure nothing breaks)"

This **extends D-07's silent-ok list**, which is a whitelist and not a starting point — so the
extension is a decision with bounds rather than a feature. The bounds are the decision:

- **Exactly four tools**, named in `src/afon/brain/toolchain.py`: Claude Code, Codex, MiniMax Code
  and OpenClaw. Nothing else on the host is touched, and adding a fifth is another decision.
- **One at a time, each proved before the next is touched.** Updating four and then pinging four
  leaves four suspects for one failure.
- **A ping that does not come back a pong is a failed update**, and the version is **rolled back**
  to the last one that answered. The owner's own acceptance test, and the right one: a binary that
  runs but whose model path is broken fails on the first real brief instead of here.
- **The ping runs only when a version actually changed.** It costs money on three of the four, and
  proving the path worked yesterday says nothing about today's release.
- **A quiet run is silent.** A daily "nothing changed" is an interruption bought with no
  information (D-29, D-30, D-34). Afon speaks when something changed or broke.
- **It can be switched off** — `toolchain_autoupdate_enabled`. An unattended host mutation that
  cannot be turned off is not a setting, it is a fact about the machine.

**The asymmetry, stated rather than papered over.** npm can pin an exact previous version, so
Codex, MiniMax Code and OpenClaw can be rolled back. Claude Code is installed by its own native
updater and there is **no downgrade command this project has verified**, so a failed ping there is
reported loudly and *not* repaired. Faking a rollback would be worse than naming the gap.

**And one measurement that shaped the whole design:** `openclaw --help` timed out at 40 s with no
output on this host. So installed versions are read from `npm ls -g --json` rather than from each
CLI — one call answers for all three npm tools and none of them can hang the job — and OpenClaw
gets no model ping at all, because its CLI needs the gateway and a live agent id. That gap is
declared in the spec and appears in the report rather than reading as an oversight.

**The residual risk, named:** on Windows a running executable is locked, so an update attempted
while that CLI is mid-brief fails and is reported as `update-failed`. Self-limiting rather than
dangerous, and cheaper than a cross-module lock.

**Falsified by:** a tool left on a version that failed its ping while a rollback was available; an
update to anything outside the four; or a day with nothing to report producing a report.

## D-89 — The weekly self-improvement review proposes; the owner disposes **(commit, owner's decision 2026-10-06)**

> "in 168 hour check for the openclaw, claude code, mcode and codex self-improvement, basically jev
> decides what are the possible improvement areas for them specifically so they can handle tasks
> better … also asks the LLMs through the applications also what would they be willing to add"

Both halves are built, and **neither applies anything.** That is not a limitation of the
implementation; it is D-47. Installing a plugin, connecting an MCP server or widening a permission
changes *what the system is willing to do*, and a model never decides that here. The job produces a
report the owner answers.

**Jev's half has the D-72 shape.** `IMPROVEMENT_KINDS` is declared in code — plugin, command, skill
document, MCP server, permission, model, or **nothing** — and Jev picks among those. It cannot
invent a capability for itself, which is the whole reason a model is safe to ask this question. The
`nothing` option is load-bearing: without it every week produces a change whether or not one is
warranted.

**Jev is asked against measurement, not impression.** The question carries how many times that tool
actually ran, failed, timed out or was refused, read from the audit trail. This is the 2026-09-20
lesson applied: the same question asked against a *summary* returned confidence 0.19 and against
the source 0.95.

**The tools' half is a read.** Each CLI is asked, through its own non-interactive entry point, what
one addition would most reduce its friction — and the prompt says out loud that the answer is
advisory and that nothing will be installed. No repo, no write path, no diff. A tool that cannot be
asked (OpenClaw) says why instead of being skipped silently.

**A Jev outage degrades the review and does not fail the job:** no verdict is reported as *no
verdict*, never as a guess.

**Falsified by:** this job installing, enabling or permitting anything; a proposal reaching the
owner without being labelled a proposal; or Jev returning an improvement kind that was not in the
code's own list.

## D-60 — What contributions are wanted **(commit)**

Rigorous bug reports, architectural critique, and clean hardware/service adapter
modules. Not speculative feature PRs, not hype. The adopter is a developer or a
technically adept self-hoster who wants local data sovereignty and terminal control.

---

## The standing line

> The emotional promise: the quiet confidence that nothing important slips through the
> cracks, and that private data never leaves hardware the owner controls.

A year of no silent data corruption, no accidental cloud leak, and no maintenance
emergencies outside routine updates is the success criterion (D-53, D-43). The strongest
argument against continuing is that commercial assistants will out-qualify this one; the
answer is that they will never prioritise local privacy, sovereignty and unconstrained
desktop automation (D-57).

**What would make the owner stop:** maintaining this becoming an endless treadmill of
debugging third-party API breakages and hardware driver quirks instead of helping him
think and build. If a subsystem starts costing more in integration friction than it
returns in utility, it is a candidate for deletion under D-46.


## D-90 — D-08's "dedicated branch" is a *place*, not a branch name **(commit, 2026-10-06)**

D-08 is four conditions and the implementation of it is `src/afon/brain/executors/landing.py`.
Writing that module changed how one of the four is enforced, which makes it a decision rather than
a detail.

**Why a branch name was not enough.** A coding CLI edits files in its working directory; it does
not hand back a patch to apply (D-80). So checking out a branch in the owner's own tree and then
dispatching would put the proposal in his working tree *before any condition had been tested* — and
"a refused approval leaves the tree untouched" would be false by construction, no matter how
carefully the branch was named. **Each brief therefore gets its own `git worktree`**, outside the
repo, on its own new branch. Condition 1 is satisfied by where the work happens.

**Provenance, not naming, is the check at commit time.** `commit_approved()` refuses any worktree
it did not create. The gate caught both shapes of the weaker rule: a blank path resolved to the
current directory — which was Afon's own repo — and a worktree whose branch merely was not called
`main` was accepted, so a dirty owner checkout passed in would have been committed to.

**Nothing is discarded, ever.** `tools/coding.py` has no reset, clean, stash or branch-delete
because "he can't lose your work" outranks tidiness, and this module keeps that rule: its entire
git vocabulary is `worktree add`, `add`, `diff`, `rev-parse` and `commit`, enumerated in the gate so
a sixth verb has to be added there deliberately. A refusal **leaves the worktree where it is** and
says where. Accumulating directories is the cost; throwing away a proposal Afon just paid an
executor for is not.

**An approval is approval of a diff, not of a directory.** `ApprovalQueue` is durable, so the owner
may answer an hour later. `commit_approved()` re-proves the other three conditions instead of
trusting that they held when the question was asked — the gate makes the suite go red *after* the
yes, and makes a `CREATE TABLE` appear in a new file after it.

**And the condition-3 scan reads created files too.** `git diff HEAD` does not show an untracked
file, so the first version of the scan passed a `CREATE TABLE` in a brand-new module. `add
--intent-to-add` makes a new file visible to a diff without staging its content, which is the only
non-destructive primitive that closes it.

**Falsified by:** a commit on a branch or in a directory this module did not create; a refusal
that leaves the owner's checkout changed in any way; a landing with no `delegate_coding` line in
`audit.py`; or a schema statement reaching a commit.

## D-91 — The fleet is reached by its own CLI with the task in a file; SSH is declined **(commit, 2026-10-07)**

`TODO.md` M42 said: *"the official `openclaw agent --agent <id> --json` CLI **over SSH**."* The
first half is right and the second half is wrong, and writing the transport is what showed it.

**Why not SSH.** `ssh host "openclaw agent -m '…'"` hands a command *string* to a shell on the far
end, which re-parses it. That is the same injection class `_batch_hazard` refuses for a Windows
`.CMD` shim, except with a full shell instead of a batch interpreter — so it is the thing D-05
names ("the moment an agent is handed an unconstrained interactive shell") arriving by the back
door. The contract's own `_no_interpreter` validator already refused `ssh` as an executable, which
means the plan and the code were in direct contradiction and the code was right. **The transport is
the local `openclaw` CLI**, which is on the brain host in production and reaches the gateway with
`OPENCLAW_GATEWAY_URL` + `OPENCLAW_GATEWAY_TOKEN` from anywhere else. Those two are allowlisted
because they are how this executor is *addressed*, not the owner's secrets — but the allowlist
withholds by default, so they had to be named.

**Three things measured off `openclaw agent --help` on the live VPS (2026.9.3), each replacing a
guess I had written:**

- **`--message-file <path>` exists.** So the task is handed over in a file and nothing ever
  re-parses it. This is strictly better than the refusal it replaces: `_batch_hazard`'s own
  docstring said *"if a brief legitimately needs a `&`, the fix is to hand the task on stdin or in
  a file — not to guess at quoting"*, and now it does. A brief that reads *Draft a reply about "the
  boiler" & the rent* used to be refused; it runs.
- **`--deliver` defaults to false**, and Afon never passes it, nor any `--channel`, `--reply-to`
  or `--to`. So an agent turn produces a reply and **sends nothing**. The owner-consent gate for
  fleet work therefore lives in the *transport* rather than in a prompt, which is the only place a
  model cannot be talked out of it. The gate asserts no `"--deliver"` string literal exists in the
  contract at all, not even commented out.
- **`--timeout` exists**, so the CLI is given the brief's own deadline and exits with a transcript
  instead of being killed by `dispatch()`. A killed process loses the thing that explains what
  happened, which is the half that matters at 2 AM.

**And the agent ids were never placeholders.** `personal` and `business` are real, live agents and
have been throughout — read from `agents.entries` on the VPS on 2026-10-07, alongside `ispir`
(router), `finance`, `security`, `realty`, `creative-research` and `dev-systems`. The specs that
said `--agent personal` were correct by accident; now they are correct on purpose.

**Two gaps this measurement exposed, recorded rather than quietly fixed:**

1. **The laptop's `openclaw` is 2026.2.14; the VPS runs 2026.9.3** — seven months apart. The older
   client may not have `--message-file` at all. This is precisely what D-88's daily update job
   exists to close, and it has not run yet.
2. **`personal` and `business` both run `minimax/MiniMax-M2.7` as primary**, which is a paid model,
   with a free model only as a fallback. The owner's stated split is *personal on free models,
   corporate on the best ones*. The fleet config contradicts it. That is the owner's configuration
   on his own host, so it is reported, not changed.

**Falsified by:** this path invoking a shell or an `ssh`; a fleet turn delivering a message to any
channel; a task reaching the CLI as an argv string where `--message-file` is available; or a brief
file outliving the call that created it.

---

## D-92 — The turn's judgement is Jev's and the verdict is already built; the renderer model is the open item **(ratifies 14.R5, 2026-10-07)**

An earlier draft of this entry described the shape below as a proposal. Reading
the code shows it is **shipped, gated and benchmarked**, so this entry ratifies
what exists and names the one thing that is still undecided. Recording a
built system as a plan is the drift `docs/README.md` exists to prevent.

**What is already there.** `JudgmentService.assess_turn()` in
`src/afon/brain/judgment.py` assembles **one** request carrying **four parallel
questions** — `route` (a Choice over candidate groups that *code* produced),
`clarity`, `urgency` and `tone` — and `src/afon/brain/agent.py` makes exactly
one bounded call per turn, cited to D-72 and D-74. Four properties of that
implementation are the design, and none of them are incidental:

1. **One request, four questions.** Three sequential calls would spend three
   budgets and could disagree with each other.
2. **Code produces the options; Jev only ranks them.** An unknown route purpose
   falls back to the tool wording rather than raising, so a typo in a caller
   cannot take the turn down — and the gate asserts the key set, so the typo is
   caught there instead.
3. **The common turn pays nothing.** No candidates and no clarity question means
   no call at all, and pure chatter is skipped outright.
4. **The instructions carry the charter, not the prompt engineer.** `urgency`
   says it "shapes framing and delivery priority only"; `tone` says "never
   choose a register that invents feelings he did not express"; `clarity` asks
   whether a reasonable person "would have to ask which one is meant", which is
   D-56 written as a question rather than as a reminder.

**The renderer is already fenced, which is stronger than a template.** The LLM
sees only the *selected* option, never the question or the losing alternatives,
is instructed to verbalize rather than choose, and its reply is **validated
against a required prefix**. A model that omits or changes the prefix is
replaced with a deterministic sentence, so prompt disobedience cannot reverse a
typed choice.

**What is genuinely undecided: which model does the verbalization.** Today
`agent.py` uses the same `LLMClient` as the rest of the turn. The open question
is whether a **small local model** should own that call, on three conditions:

- it is handed a decision already made and may never add a fact, a number, a
  probability or a recommendation;
- a deterministic sentence must remain reachable, so the model's absence
  degrades *tone* and not *function* — the shape the renderer already has;
- it must cover **ru, uk, de and fr**, because the owner speaks five languages
  and an English-only renderer would silently degrade every other turn. This is
  the same gap D-78 records for TTS, and it is the binding constraint, not
  model size.

**A conversational model is declined, and the reason is the 2 AM test.** Its
failure mode is "it said something weird", and for that there is no third
command: the output is prose with no schema, no probability and no log line that
separates *it misunderstood* from *it was fine and I dislike the phrasing*. Every
other component in this system fails visibly. It is also structurally wrong for
the charter — a conversational model fabricates the space between what was said
and what was meant, which is what D-56 exists to prevent. A second Jev pass over
the rendered text, asking whether it overstates, is the preferred alternative: same
engine, same audit trail, and it fails visibly.

**Falsified by:** a measured turn in which a small local renderer produces answers that
are truthful but unusable *and* a second Jev pass does not flag the overstatement; or
the prefix guard in `_verbalize_judgment` being removed; or a caller reaching Jev
with options the code did not produce.

**Now implemented as configuration (2026-10-07).** The open item above is no
longer an open item; it is a setting. `AFON_VERBALIZER_MODELS` names a dedicated
cheap tier for the verbalizer only, and `LLMClient.complete(only=...)` narrows
that one call to it. Three properties, and each is gated:

- **Off by default.** Blank walks the normal chain, `only=None`, byte-identical
  to the previous behaviour. Gate: `bench/test_verbalizer_renderer.py` §1.
- **A dedicated local model is usable at all.** The named entries are used *as
  given* and are deliberately not intersected with the turn's own chain, because
  a local Ollama model is configured separately and never appears in
  `llm_chain`. The first draft of this work did intersect, which would have made
  the feature silently useless; `bench/test_verbalizer_tier.py` §2 caught it.
- **Narrowing never widens.** An empty or blank tier yields an empty chain, so a
  misconfiguration cannot quietly hand the primary back and look like it worked.

Note what was *not* built: `AFON_LLM_FAST_MODEL` and the `ollama` provider already
existed, so a small model was always reachable. The only genuinely missing piece
was the ability to say "this call only", and that is what `only` adds.

Gates: `bench/test_verbalizer_tier.py` (10 checks) and
`bench/test_verbalizer_renderer.py` (12 checks). The renderer gate is
network-free on purpose — `bench/test_jev_judgment.py` makes a live Jev call and
times out without connectivity, which is a property of this host and not of the
change.

---

## D-93 — Every subsystem is re-reviewed against the 2 AM rule, and subtraction is the default answer **(proposed, 2026-10-07)**

PRINCIPLES section 6 says 50 subsystems is already too many and that the default
answer to a new capability is a handler in an existing system. This decision
records that the four-slice re-review of all fifty documents produced that
answer, so the next reader does not have to re-run the survey to find out.

**What the review returned, per subsystem:** roughly **11 additions, 6 already
covered, and a majority answering HANDLER, SUBTRACT or WIRE.** Four documents
exist to record work that should not be built. Adding capability to a system
that is being deleted is the failure the charter was written to prevent, so
S46, S47, S48, S49 and S50 received **zero** additions.

**"Base addition" and "significant improvement" are now named distinctions.**

- A **base addition** is small, local, boring, and debuggable with three commands:
  a protocol client, a parser, a test harness. Eleven were found.
- A **significant improvement** changes what a system can do. Exactly one
  candidate cleared that bar in this review, and it is `browser-use/jev-ultrafast`
  for S05 - already held at spike question **M49** in `EXTERNAL-EXECUTORS.md`.

**The highest-value items require no dependency at all**, and that is the finding
rather than a shortfall: install the Home Assistant token (`28.F1`, four hours,
un-darkens S28 and every IoT item downstream); write `emergency.md` by hand and
delete `call` from `ACTIONS`; add the ArcFace enrolment driver behind
`src/afon/brain/tools/camera.py`; and set `AFON_WHISPER_LANGUAGE`, which is
currently unset, leaving `src/afon/edge/stt.py` pinned to `en` so that a
Ukrainian turn during a cloud outage is answered in English.

**Every cited path was verified before it was written down.**
`subsystems/README.md` rule 1 is that a phantom path is worse than no path,
because it will be trusted. The inventory in `INTEGRATIONS.md` was produced with
a verifier that asserts each cited `src/afon/...` path exists and that the three
recorded gaps really are still absent.

**Falsified by:** a row in `INTEGRATIONS.md` whose cited path does not exist, or
whose named gate turns out to be a dashboard; or a new subsystem appearing without
an independent daemon or a distinct security boundary (D-42); or an addition
made to a system carrying a deletion decision.

---

## D-94 — The Bookroom engine ships inside the SDK, so its external-application blocker is withdrawn **(commit, 2026-10-07)**

`EXTERNAL-EXECUTORS.md` section 6 recorded a constraint that has since been
removed at the source: *"The SDK wraps a separate application - a flat tree
containing `book_pipeline.py` - imported from `BOOKROOM_APP_ROOT`, and that
engine is not in the SDK repository. Every call reaches it, `extract` and
`check` included."*

That was true when written and is now false. The nineteen engine modules the SDK
calls are vendored into the package and installed as package data, so
`pip install bookroom-sdk` is the whole setup. The three-step owner prerequisite
in that section reduces to: install the package, set a key.

**The wrapper is faithful, and that is now measured rather than asserted.** The
bundled copy and the application tree were driven over the same book with the
same provider: `study-guide.md` is byte-identical, the PDF renders the same
text, and seven of ten artifacts match exactly. Fifteen of nineteen modules are
byte-exact copies. The four that are not are the documented deviations, each
with a recorded reason: a provider label derived from the endpoint rather than a
hardcoded literal, and two `pymupdf` imports replacing the deprecated `fitz`
alias that printed a warning onto stdout.

**Two defects were fixed in the SDK that this work exposed,** and both are the
kind that only running for real finds. Two clients with different providers in
one process silently shared the engine's module-level configuration, so the
second ran the first's endpoints; and a manifest generated by MiniMax recorded
`"Google Gemini API"` because the value had been captured at import time, before
the endpoint was patched.

**What would make the owner stop relying on the SDK path:** a change to the
application that does not reach `python/bookroom_sdk/_engine`, since the vendored
copy is deliberately byte-identical to the app and therefore must be re-copied
rather than hand-patched.

**Falsified by:** an integrator reporting that the engine did not resolve from
the installed package; or a report generated through the SDK whose
`generation_provider` does not name the service that actually served it.
## D-95 â€” Secrets resolve from environment first, then Infisical, with an `age` file as the offline floor **(proposed, 2026-10-09)**

The owner asked for keys to be stored through Infisical. That is adopted, with an ordering
that keeps the 2 AM rule (`PRINCIPLES.md` Â§1) intact.

**Infisical is not run as a local service.** `ARCHITECTURE.md` states this system has "no
message broker, no container runtime, no policy service, no secrets manager, and no second
database". Self-hosting Infisical means a server and a Postgres, which is exactly the
addition that line forbids. So the integration is the **CLI or the v3 REST API against a remote
workspace** (`AFON_INFISICAL_*`), and nothing is vendored.

**The ordering is the decision, not the product.** Environment wins, then Infisical, then an
`age`-encrypted file. `age` (`FiloSottile/age`, BSD-3-Clause) earns the third slot because a
secrets backend that can abort startup breaks the promise that anything broken is diagnosable in
90 seconds â€” a brain that will not boot cannot be diagnosed at all.

**Infisical's own licence is NOASSERTION.** Verified live 2026-10-09 against the GitHub API,
both for the platform and for `Infisical/cli`. That is not a permissive licence and has not been
read by hand. This is an open item, not a blocker for reading secrets at runtime, and it is the
reason the `age` floor is kept rather than treated as redundant.

**Hydration cannot raise.** `afon/shared/secrets.py` catches at both the per-backend and the
whole-run level and returns a `SecretReport` carrying names and counts only. There is no field
on that report that can hold a value, so `repr()` of it is loggable by construction.

**No function in the module returns, logs, or formats a secret.** `redact()` masks to 2+2
characters; `secret_status()` returns only `configured` or `missing`. `test_secrets_redaction.py`
gates this with paired positive controls â€” a redaction asserted only by "the value is absent"
also passes when the function returns nothing at all, which would be a gate that certifies
nothing.

**Falsified by:** a boot that fails when Infisical is unreachable; a secret appearing in any log,
audit line, or `SecretReport`; or the owner moving to a self-hosted Infisical and finding that a
second database has been introduced without the `ARCHITECTURE.md` line being amended first.
