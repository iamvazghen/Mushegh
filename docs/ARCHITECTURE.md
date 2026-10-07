# Architecture — what actually exists

The authoritative description of the running system, as opposed to
[JARVIS blueprint](#what-the-blueprint-proposed-and-what-replaced-it) proposals this
project declined. Written 2026-10-03.

**Read this for shape. Read [DECISIONS.md](DECISIONS.md) for why. Read
[PRINCIPLES.md](PRINCIPLES.md) for how to propose changes.**

---

## The one-paragraph version

A single Python process — the brain — runs on an always-on host and holds all state in
one SQLite database. Voice clients (the edge) run wherever the owner is: laptop first,
then phone, then a wall panel. They stream audio and events to the brain over a
WebSocket carried by a WireGuard tailnet, authenticated with a bearer token. The brain
routes an utterance to an LLM, the LLM may call tools, tools act through a Pydantic
schema boundary, and results come back as text. There is no message broker, no
container runtime, no policy service, no secrets manager, and no second database.

---

## Topology

```
┌──────────────── EDGE — where the owner is ───────────────┐
│  src/afon/edge/                                          │
│  wake_word.py · vad_bargein.py · aec.py · audio_gate.py │
│  stt.py · tts.py · speaker_id.py · speaker_gate.py       │
│  brain_bridge.py (client) · latency_meter.py             │
│  pc_agent.py · offline_queue.py · degraded_answers.py    │
└──────────────────────────┬──────────────────────────────┘
                           │ WebSocket over tailnet
                           │ bearer token, no inbound ports
┌──────────────────────────▼──────────────────────────────┐
│ BRAIN — always-on host, one process, systemd             │
│  src/afon/brain/server.py      dispatch + transport      │
│  src/afon/brain/agent.py       the turn loop             │
│  src/afon/brain/llm.py         model client + fallbacks  │
│  src/afon/brain/context.py     prompt assembly           │
│  src/afon/brain/tools/         schemas + handlers        │
│  src/afon/brain/memory.py      six-layer store           │
│  src/afon/brain/dbconn.py      the only DB door          │
└──────────────────────────┬──────────────────────────────┘
                           │
                    ┌──────▼──────┐
                    │  SQLite WAL │  one file, sqlite3 CLI
                    └─────────────┘

  HUD — clients/hud-spatial/src/ (React) — optional, read-mostly
  deploy/uptime_watch.py — outside-in liveness check
```

**The process that must never die** is the brain's dispatch daemon. If it cannot
restart, the edge clients fall back to dumb local endpoints and the system stops
existing (D-01 rationale, Q14).

---

## Components

### Transport — `src/afon/brain/server.py`, `src/afon/brain/protocols.py`, `src/afon/shared/`

One WebSocket protocol, one bearer token, carried by a tailnet. No inbound firewall
ports exist to attack, which is the entire security argument (D-03). Protocol
messages are defined in `src/afon/protocols/` and shared by both sides so the edge
never guesses.

### The turn loop — `src/afon/brain/agent.py`, `context.py`, `llm.py`

`agent.py` owns the turn: intent classification, tool selection, tool execution,
streaming the reply. `context.py` assembles the system prompt and the working context
(`build_system_prompt()` is the seam). `llm.py` is the only place that knows which model
vendor is on the other end, and it holds the fallback chain.

**Who decides the tool.** Three layers, in order, and the order is the design:

1. **The deterministic router** picks the surface. `intent_router.forced_tools()` is a
   keyword table — all 25 routes resolve to exactly one tool, and `forced_tools()` can never
   return two names, so this layer is a filter and not a chooser. `groups_for_text_ranked()`
   decides which lazy groups an utterance activates, subject to a 11000-token catalogue budget
   that core schemas alone already spend 7418 of.
2. **Jev arbitrates what the router could not.** When an utterance activates two or more
   groups, `judgment.py` asks Jev to choose among those candidate groups, and only the
   winner's tools reach the model. Candidates come from the trigger match, so the model
   choosing within them can narrow the surface but never widen it (D-04, D-72). The budget is
   **400ms** and failure is **silent** — the candidates stand (D-73). Fewer than two
   candidates is not a decision and costs no call.
3. **The model phrases, and picks within what it was given.** It cannot reverse the
   arbitration and it cannot reach a group the router did not surface.

The loop has to be fast and boring. The open defect in it is compound-intent handling
at roughly half strength (S01).

### The tool belt — `src/afon/brain/tools/`

`__init__.py` advertises a narrowed schema group per turn rather than the whole belt,
and maps schema names to handlers. `base.py` holds the contract every handler inherits.
`argcheck.py` guards arguments.

Two invariants, both load-bearing:

- **Every handler is schema-validated** (D-04). A handler that takes a raw string is a
  defect.
- **The belt shrinks** to 90–100 handlers; anything unused for 60 days is culled (D-06).

### State — `dbconn.py`, `memory.py`, `recall.py`, `semantic.py`, `docstore.py`

SQLite in WAL mode, reached through exactly one module. The owner reads and writes the
same database with `sqlite3` from a shell, which is the whole point (D-02, D-54).

`memory.py` holds the six layers; `recall.py` and `semantic.py` are retrieval;
`docstore.py` is the vault mirror. The vault's markdown is authoritative and the
database is a cache, so every mirror needs a reconciliation path that can lose to a
file (D-22).

### Self-modification — `code_improve.py`, `approvals.py`, `audit.py`

Afon reads and edits its own source, runs its own tests, and produces reversible git
work. It commits only to a dedicated branch, only with a green suite, only without
schema migrations, and only with the owner's explicit approval of the diff (D-08).
`approvals.py` is where a confirmation is required, `audit.py` where it is recorded.

**Since 2026-10-06 the code may also be written elsewhere.** `src/afon/brain/executors/` is one
typed contract over the external CLIs the owner delegates coding to (D-79, D-80, D-87), and it is a
*proposal* layer and nothing more: an executor returns a transcript and a diff, no shell is
invoked, and the child's environment is an allowlist built from nothing so no credential reaches
it. Three modules, three jobs:

- `executors/__init__.py` — the table and the runner. `dispatch()` is the only place that starts a
  process, spends money or writes an audit line. `pick()` lets Jev choose among the candidates
  *code* produced, and keeps the deterministic first choice silently on any failure (D-73, D-81).
- `executors/briefing.py` — what the executor is told. A constraint table in code, so a caller can
  neither write the constraints nor drop them, and an acceptance check that merely restates the
  task is refused (D-79).
- `executors/landing.py` — the only path from a diff to a commit. Each brief gets its own
  `git worktree`, so D-08 condition 1 is satisfied by *where* the work happens rather than by
  remembering to branch, and a refused approval leaves the owner's checkout byte-identical (D-90).

**`code_improve.py` and `landing.py` are not the same path, and the difference matters.**
`code_improve.py` is Afon editing his own source with his own tools, branching the owner's
checkout. That is correct for an in-house loop and wrong for an external one: a coding CLI writes
files in its working directory and hands back no patch, so pointing one at the owner's tree would
put the proposal there before any condition had been tested. External work therefore never touches
that tree at all.

### Proactivity — `proactive.py`, `proactive_signals.py`, `interventions.py`, `delivery.py`

Signals are collected, scored, and delivered within a hard budget: three audio
interruptions per day, zero inside a focus block (D-29). A refusal is a negative
calibration sample and is never argued with (D-31). The objective is dismissal rate,
not helpfulness (D-30).

### Safety and governance — `argcheck.py`, `approvals.py`, `judgment.py`, `governor.py`, `emergency.py`, `audit.py`

Argument checking, confirmation gates, value judgement, the interference governor, the
safety-critical escalation path, and the audit trail that makes any of it explainable
afterwards. The value order Safety > Privacy > Honesty > Helpfulness lives here and
still needs an explicit test suite (D-10).

### Presence and devices — `presence.py`, `devices`, `pc_link.py`, `hud.py`

Device roster, remote control of a laptop, and the HUD. **Presence today is a laptop
activity poller**: `presence.py` asks the edge for an `activity_snapshot` and reports the
foreground app and idle minutes. It does not know which room the owner is in, and it does
not track the phone — the module says there is no sanctioned API for that, so it does not
pretend to. Room presence is what the planned mmWave sensors make real
([HARDWARE.md](HARDWARE.md) H3, [DECISIONS.md](DECISIONS.md) D-69).

### Resilience — `reliability.py`, `vitals.py`, `health.py`, `maintenance.py`, `audio_watchdog.py`, `degraded_answers.py`, `offline_queue.py`

Vitals and health for the brain; a watchdog for audio; and the degradation paths that
make a missing credential say "that isn't configured yet" instead of crashing. This is
the code that answers the 2:00 AM question.

### The external fleet — `fleet.py`, `delegation.py`, `coordination.py`, `brain/executors/`

Consulted as a tool, never as the assistant. Sandboxed and diff-verified; no
unconstrained shell, ever (D-05). `coordination.py` is the thin shared-state layer —
and it is one-way delegation, not real multi-agent coordination (S48).

`brain/executors/` is where D-05's rule is now enforced in a type rather than promised in prose: an
`ExecutorSpec` whose first argv element names a command interpreter is refused at construction, the
child's environment is an allowlist built from nothing, and `stdin` is `DEVNULL` so there is
nothing to type into. `diagnose(about='executors')` answers which executor serves which domain and
whether it is installed — the 2 AM question for this layer (D-01).

### The HUD — `clients/hud-spatial/src/`

React canvases over a read-mostly snapshot API. Optional: the system is complete
without it. Its own status and remaining integration work are in
[HUD-SPATIAL.md](HUD-SPATIAL.md).

---

## Storage model

| Store | What lives there | Authority |
|---|---|---|
| SQLite (WAL) | Everything operational: sessions, tasks, memory layers, settings, audit | Runtime cache |
| Obsidian vault | Markdown notes, daily notes, curated facts | **Source of truth** (D-22) |
| Git | Code, and every self-edit as a reversible branch | Source of truth for the codebase |

There is no second database. `postgres_client.py`, `postgres_vectors.py` and
`store_migration.py` are cancelled migration scaffolding under D-02 — the registry marked
them `cancelled` on 2026-10-03 and they are to be deleted, not finished
([REGISTRY-RECONCILIATION.md](REGISTRY-RECONCILIATION.md)).

## Deployment

- Brain: `scripts/deploy_vps.sh` — brain only, never secrets.
- Edge: `scripts/restart_edge.ps1`, `scripts/install_edge_service.ps1`,
  `scripts/edge_guard.ps1`.
- Liveness from outside the host: `deploy/uptime_watch.py` — because "up" reported by
  the thing that is up is not evidence (S23).
- Git hooks are redirected to `scripts/githooks`; the pre-push gate runs the full suite
  and is not bypassed.

## What the blueprint proposed and what replaced it

The JARVIS blueprint specified a two-plane, event-driven system. Every row below was
declined under the 2:00 AM rule (D-01). This table is the single most useful thing in
this file, because the blueprint is still circulating and looks authoritative.

| Blueprint | What exists instead | Why |
|---|---|---|
| NATS JetStream event fabric, CloudEvents protobuf envelope | One WebSocket protocol, one process | A 90-second shell diagnosis beats a distributed trace |
| PostgreSQL 16 + pgvector + Apache AGE | SQLite WAL + markdown vault | Readable in 2036 with `sqlite3` (D-02, D-54) |
| Open Policy Agent + HashiCorp Vault | Pydantic schemas, `argcheck.py`, `.env`, git-crypt | Four moving parts replaced by a type system |
| Temporal durable workers + workflows | `automations.py`, `scheduler.py`, `worker.py` | Checkpointing is not worth a server |
| gVisor sandbox fleet, Claude→Codex→MCode chain | **half adopted 2026-10-06.** The sandbox fleet stays declined; the CLI chain is adopted through `src/afon/brain/executors/` | Reversible git still beats a container fleet — but the decline also assumed the CLIs were interactive, and they are not. `codex exec --json`, `claude -p` and an Agent-SDK subprocess are headless, permission-moded and schema-enforced, so D-80 can keep what the decline was protecting without refusing the capability |
| Redis Stack ephemeral state | SQLite | One store to inspect |
| LiteLLM proxy router | `llm.py` with a fallback chain | The router was a second failure domain |
| ONNX classifier cascade, Jev cloud arbitration | Direct intent routing | A calibrated classifier was needed only because the event bus was |
| React 19 Command Deck + Go ingest gateway | `clients/hud-spatial` + REST snapshot | The gateway existed to absorb a firehose that does not exist |
| Vendor TTS (Fish Audio) with prosody tags | Piper/Kokoro local, `tts.py` | Latency and privacy dominate at 3 AM (D-17) |
| Redis blackboard multi-agent coordination | `coordination.py`, one-way | Coordination without need is a deadlock source (S48) |

## The honest gaps

- **Compound intent is at half strength** (S01). This is the most felt defect.
- **Barge-in worst case is ~700 ms** against a 350 ms budget (D-49, S18).
- **The voice profile is measurably weak** and face enrolment has never run on the
  current backend (S08, S09) — the reason the owner has not re-enrolled is that it
  requires physical quiet and edge debugging, which is duller than writing backend code.
- **Six systems are dark**: code that controls nothing (D-46).
- **The handover package does not exist**: no reproducible bare-metal setup, no edge
  audio tuning guide (D-55).
- **The delegation layer is built and still dark at the turn loop.** `brain/executors/` now holds
  the contract, the arbitration, the brief assembly and the landing path, each hermetically gated —
  but **nothing in the turn loop calls any of it**, and no external CLI has produced a diff through
  it. Dark code is not progress (D-46). What remains is the OpenClaw transport (M42), which is
  blocked on the new fleet's real agent ids, and then one real delegation end to end.
- **Three charter rules are not honoured by the code yet**, each now tracked rather than
  merely noted: the never-store set is prose, not enforcement (`37.R5`); an unprompted
  morning news feed ships in the proactive path (`41.R4`); and the environment carries
  cloud TTS and cloud wake-word keys where D-17 and D-19 specify local
  (`18.R4`, `18.R5`, `36.R4`).
- **The door-lock blast radius is now enforced.** `ha_call` refuses `lock` and
  `garage_door` before a request is built, verified by
  `bench/test_blast_radius_refusal.py` (29/29 on 2026-10-03). It was the most serious gap
  the docs audit found: the code confirm-gated them, and D-13 requires physical presence
  rather than a second "yes". `28.R4` stays **in-progress** — the hermetic gate is green,
  but D-43's seven-day bar is outstanding and Home Assistant is still dark.
- **The plan owed the charter a correction** — 29 cancelled tasks and 6 deferred ones were
  applied to the registry on 2026-10-03, but the code behind several of them still needs
  deleting, and three owner decisions are still open
  ([REGISTRY-RECONCILIATION.md](REGISTRY-RECONCILIATION.md) §4).
