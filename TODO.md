# Mushegh — Engineering TODO

**Rewritten 2026-10-06.** This file is the **canonical** engineering log and the
next-action list; `docs/MASTER-PLAN.md` is superseded and points here.
Planning at milestone granularity lives in [`docs/ROADMAP.md`](docs/ROADMAP.md) (M01–M40);
what is built and proven lives in `docs/systems-plan.json`; what will and will never be
built lives in [`docs/DECISIONS.md`](docs/DECISIONS.md). This file sequences work and
records what was found. It does not restate decisions — it cites `D-nn`.

> ## Integrity notice — read once
>
> **This file was truncated to 0 bytes at 17:09:48 on 2026-10-06**, not by a commit and not
> by a documented step. Nothing in this repo wrote it; the cause is unidentified. Recovery
> state, stated honestly:
>
> - **Parts A–N survive in git**: `git show HEAD:TODO.md` (3081 lines, through Part N,
>   commit `c43dbc3`). Nothing from that range is lost.
> - **Parts O, P, Q, R and S are gone as prose** — roughly 1,500 lines covering 2026-09-20
>   to 2026-10-04 (the Jev decision seam, the HUD plan, the system-isolated batches). They
>   were never committed.
> - **Their state is not lost.** Every task id, gate, state and evidence record from that
>   work is in `docs/systems-plan.json` (420 tasks), and the conclusions were written into
>   [`docs/DECISIONS.md`](docs/DECISIONS.md) D-72–D-78, [`docs/ROADMAP.md`](docs/ROADMAP.md)
>   and [`docs/subsystems/`](docs/subsystems/README.md) on 2026-10-03/04. What was lost is
>   the narrative of how each was reached, not the plan or the status.
> - **Citations elsewhere now dangle, and resolve against git.**
>   [`docs/HUD-SPATIAL.md`](docs/HUD-SPATIAL.md) cites Parts O, P and R with line numbers, and
>   `docs/SYSTEMS-DETAILS.md` — a frozen archive that is not rewritten — cites Part O as the
>   implementation ordering. Those sections are not in this file any more. Read them with
>   `git show HEAD:TODO.md` for Parts A–N; Parts O–S are only in the lost copy, and their
>   conclusions are in the registry and the decision docs instead.
> - **Recoverable by the owner, not by me:** Windows *Previous Versions* on `C:\Mushegh`
>   (Explorer → Properties → Previous Versions), or an elevated `vssadmin list shadows`.
>   Worth one attempt before this notice is deleted.
>
> **T0.1 — commit the working tree.** 154 changed files and 69 untracked ones are
> single-copy on this laptop, including every new `bench/` gate written since 2026-09-15.
> This is the same failure one step away from repeating. Do this before any new work.

---

## The new direction — 2026-10-06

The owner restated what Mushegh is for: **a Jev-guided brain that routes work to the executor
that is best at it, and owns the voice, the judgement and the typed boundary itself.**

| Domain | Executor | Status today |
|---|---|---|
| Daily life, errands, admin | a **new** OpenClaw fleet, free models (D-87) | transport chosen (CLI over SSH); `src/mushegh/brain/fleet.py` still disabled; agent ids still placeholders |
| Coding | the corporate CLIs, best models (D-87) | contract built; `claude` and `codex` both already on PATH; no adapter calls them yet |
| Finances, taxes, investments, portfolio, salary | Rubo CLI | **D-12 superseded by D-83.** Declared in the routing table; its output is withheld from every store (`financial_position`) |
| Reading, book summarisation | the owner's own SDK, in progress | **not built**, and correctly so until the SDK has a version |
| The web | the existing visible Chromium | built; the Jev-per-step loop is **not** |
| The house | 28 devices, HA coordinator | planned in [`docs/HARDWARE.md`](docs/HARDWARE.md); nothing in the wall |

New decisions recorded for this: **D-79 to D-87** in [`docs/DECISIONS.md`](docs/DECISIONS.md),
which also **supersede D-12** and **sharpen D-05**.
The SDK and open-source survey that sizes each row is
[`docs/EXTERNAL-EXECUTORS.md`](docs/EXTERNAL-EXECUTORS.md).

**The four conflicts this direction created are resolved** — Part X at the bottom records each
one as a charter edit or a code change rather than an open question. Two milestones are built
and gated (M41, M47); the remaining executor work is ~22 h, not the original 54.

---

## Part T — Integrity and the critical path · ~6 h

| ID | Task | Done when | h |
|---|---|---|---|
| T0.1 | Commit the 2026-09-21 → 10-04 working tree in reviewable chunks | `git status` clean; master pushed; the pre-push suite green | 3 |
| T0.2 | One full green suite run | `bench/run_all_tests.py` green end to end; the `bench/test_phase4_system_protocols.py` offline-isolation fix verified in a full run, not a targeted one | 2 |
| T0.3 | ~~Execute the deletions the registry already decided.~~ **CLOSED 2026-10-06 — three were already done and the fourth was wrong.** `postgres_client.py`, `postgres_vectors.py` and `store_migration.py` were deleted on 2026-10-04 under M02, which D-02 already records. `forecast.py` is **not** cancelled and must not be deleted: `46.F1`–`46.F3` are `done`, `bench/test_forecast.py` is registered in the suite, and `tools/day_shape.py` calls it. D-28 removed S46 as a *modelling* system — the module is deterministic arithmetic over a JSONL ledger with no statsmodels, which is what D-28 asked for, not what it forbade | the three are gone; `forecast.py` stays, and this row records why | 1 ✓ |

**T0.2 is a gate, not a chore.** 176 registry tasks are marked done with no runtime
evidence, 0 are runtime-verified, and the last known-good full suite predates two weeks of
work. Every estimate below assumes a trustworthy suite underneath it.

---

## Part U — The executor brain (M41–M46) · **all six built; M42 owes a live round-trip and a coordination row**

Mushegh becomes the router. Each executor is a subprocess or an MCP server behind a typed
adapter, never an interactive shell (D-80), and Jev picks among candidates code produced
(D-81).

| ID | Milestone | Done when | h |
|---|---|---|---|
| M41 | ~~**One executor adapter contract.**~~ **BUILT 2026-10-06, hermetically.** `src/mushegh/brain/executors/__init__.py` — Pydantic `Brief`/`Result`/`ExecutorSpec`, the routing table, `candidates()`/`resolve()`/`dispatch()`. Registry: `39.R1` in-progress | `bench/test_executor_contract.py` **58/58**, registered in the suite. Dark until M42–M45 call it (D-46) | 6 ✓ |
| M42 | **OpenClaw goes live for daily-life work.** Transport **BUILT 2026-10-07** — the local `openclaw agent --agent <id> --message-file <path> --timeout <s> --json` CLI. The agent ids `personal` and `business` are **real and live**, read off the VPS; the **SSH plan is declined** (D-91) because a remote shell re-parses the command string. Registry: `39.R7` | `bench/test_fleet_transport.py` **40/40**, registered — no shell, nothing delivered, the task in a file so a brief with `&` or a quote now runs instead of being refused. **Still owed:** a real errand round-trip (spends money on the fleet — the owner's call) and the `coordination.py` row with a deadline and a verdict | 5 |
| M43 | ~~**Coding delegation lands under D-08.**~~ **BUILT 2026-10-06, hermetically.** `src/mushegh/brain/executors/landing.py` — a `git worktree` per brief, the four conditions in order, and `commit_approved()` as the second half because `ApprovalQueue` is durable rather than blocking. Registry: `39.R4` in-progress; D-90 records what writing it changed about condition 1 | `bench/test_coding_delegation.py` **98/98**, registered. It caught four real defects in my own code, and a fifth came from re-reading the design — see the log. **Blocked on T0.1 for real use:** a worktree is cut from HEAD, and the checkout has 171 uncommitted changes against a HEAD from 2026-09-15, so the path correctly refuses to delegate against code the owner has moved past | 7 ✓ |
| M44 | ~~**A second and third coding executor behind the same contract.**~~ **BUILT 2026-10-06.** `mcode` is one `ExecutorSpec` row, measured from `mcode exec --help` — and it has the richest interface of the three: `--output-format stream-json`, `--output-schema` and an explicit `--permission` policy. No new module, no caller change, which was M41's whole claim. Registry: `39.R1` evidence | `bench/test_executor_contract.py` **109/109** (was 98). It caught a coding brief defaulting to the personal tier, which matched no executor and failed with a message that read as a missing install | 5 ✓ |
| M45 | ~~**Jev picks the executor.**~~ **BUILT 2026-10-06.** `executors.pick()` over `judgment.arbitrate()` with a declared `route_purpose`. `resolve()` stays the authority; `pick()` is the policy, so the refusal and the fallbacks live in different places on purpose. Registry: `39.R5` | `bench/test_executor_arbitration.py` **43/43**, registered — an uninstalled executor is not even present in the outbound payload, and every failure mode (timeout, outage, no key, disabled, a service object that raises) keeps the deterministic choice silently | 6 ✓ |
| M46 | ~~**The prompting layer is Mushegh's, not the executor's.**~~ **BUILT 2026-10-06.** `src/mushegh/brain/executors/briefing.py` — a constraint table in code, the tier derived from `SPECS` rather than restated, the acceptance check rendered last. Registry: `39.R6` | `bench/test_brief_assembly.py` **54/54**, registered. The refusal that is the point: an acceptance check that *restates the task* is refused, and `from_task()` refuses a record with none rather than generating one. Owes the ten recorded briefs, which is real use | 5 ✓ |

**What M41 buys that four bespoke integrations do not:** one place where a cost is charged
against `src/mushegh/brain/governor.py`, one place where an audit row is written, and one
failure mode to debug at 2 AM instead of four (D-01).

---

**The Claude Agent SDK is not a dependency, and that is M43's one real deviation.** M43 was
written as "coding delegation *through the Claude Agent SDK*". The SDK's value is the
subprocess-over-stdio-JSON path with a permission mode — and `executors/__init__.py` already has
exactly that: `claude -p --output-format stream-json` in argv form, an env allowlist built from
nothing, `stdin=DEVNULL`, and a parser whose verdict can fail a run the exit code passed. Adding
the SDK would replace working code with a dependency that re-implements the four invariants the
contract already holds, and would hand the permission decision to a library instead of to D-08.
The thing M43 actually owed was the **landing path**, which is what got built.

---

## Part V — The browser, as a capability rather than a tool (M47–M49) · ~20 h

The owner is right that this is the big unlock, and right about the repo cluster. There is a
real, active family of Jev browser agents, and their architecture is *this project's own
charter arrived at independently*: Jev chooses from an indexed table of observed page
operations and never writes free text; a small text model fills field values only when the
chosen action is a type. That is D-04 and D-72 in a new place.

| ID | Milestone | Done when | h |
|---|---|---|---|
| M47 | ~~**Close the open browser floor first.**~~ **BUILT 2026-10-06, hermetically.** `submit_needs_confirm()` in `src/mushegh/brain/tools/browser.py`, called from `proactive.confirm_required`. Registry: `05.R1` in-progress | `bench/test_browser_submit_confirm.py` **45/45**, registered. Owes D-43's seven days of real use | 4 ✓ |
| M48 | **The Jev-per-step loop inside the existing browser.** Keep `src/mushegh/brain/tools/browser.py` and the visible Chromium on the laptop — that is the part no library gives us. Replace the *decision* inside the loop: observe, build an indexed element table, one Jev call for operation and target, act, verify freshness | A five-step real web task end to end (`05.E1`); a planned gate `bench/test_browser_session.py` carries multi-tab state (`05.R2`) and downloads by path (`05.R3`); the published baseline to beat is roughly 7 s per task | 10 |
| M49 | **Evaluate the MCP route before writing the loop by hand.** `jev-browser` ships as a library, a CLI *and* an MCP server under MIT, with a pause-before-irreversible-action gate — which is `05.R1` for free. `src/mushegh/brain/mcp_client.py` already converts any MCP server into normal Mushegh tools | A one-day spike answers one question in writing: does that MCP server, driving its own Chromium, keep the owner's logged-in profile visible on his own screen? If no, M48 is built in-repo and the spike is recorded as a decline with its reason | 6 |

**M49 runs before M48.** The repo may deliver most of M48 for a config line, and `05.R1` with
it. If it drives a browser the owner cannot see, it fails the one requirement S05 exists for,
and then the loop is ours to write — but that is a measurement, not a guess.

---

## Part W — Hardware · sequencing is not mine to set

**[`docs/HARDWARE.md`](docs/HARDWARE.md) owns the order of all 28 devices** — H1 core, H2
Home Assistant and the read-only sensors, H3 presence and air, H4 actuators, H5 voice
satellites, H6 perception, H7 fabrication — and that order is a property of the house. It is
not re-litigated here. Two things belong in this file:

| ID | Task | Done when | h |
|---|---|---|---|
| W1 | **One correction to the voice-satellite plan.** The Wyoming *satellite* project is no longer maintained upstream; it has been replaced by Linux Voice Assistant on the ESPHome protocol, which is what carries timers, media and stop-wake-word. H5 is still correct about *what* to buy; the protocol a reader would reach for first is retired. Wyoming remains the right protocol for the STT and TTS services themselves | H5's integration path names ESPHome for satellites and Wyoming for services, and a planned gate `bench/test_satellite_protocol.py` asserts no satellite code imports a retired client | 2 |
| W2 | **H2 is the cheapest real win in the whole plan.** One Home Assistant token converts S28 from dark to working and delivers M20, the desk lamp. It needs no new software | M20's benchmark: 50 toggles, p95 under 500 ms, verified live and not mocked | 4 |

Everything else hardware-shaped is blocked on the five open nods in HARDWARE.md §9 — one
Zigbee coordinator, the wake-phrase cut, which circuits the relays own, the camera decision,
and the Mini-PC core split. Those are owner decisions, not engineering.

---

## Part X — RESOLVED 2026-10-06. All four, with what changed.

The owner's instruction was to resolve these as well as they can be resolved and to modify
whatever needed modifying. Each one is now a code change or a charter edit, not an open question.

### 1. Finance — resolved by enforcing the promise, not by narrowing it

D-12 is marked **superseded**; [D-83](docs/DECISIONS.md) is live and carries the broad reading:
finances, taxes, investments, portfolio, salary planning and distribution. What was still only
prose was D-83's own promise that the *figures* stay in Rubo's store, so that is now enforced:

- a fifth `never_store` class, `financial_position`, in `src/mushegh/brain/never_store.py`;
- **declaration-only, with no detector at all** — and this is the design decision worth keeping.
  Every other class is anchored on a label or a format. A financial position has neither: "EUR
  2,400" is a balance, a salary, or what the coffee machine cost, and a pattern would refuse to
  remember the third. The finance executor *knows* what it is holding, so certainty at the source
  replaces a guess at the boundary — which is exactly what `screen(declared=…)` was built for;
- a defect in what shipped yesterday, found while doing this: `_account()` wrote the executor's
  transcript into the audit line unconditionally, which would have put every figure Rubo returned
  into the one file D-83 promises they never reach. A declared payload is now withheld and the
  line carries an HMAC fingerprint instead, so two runs are comparable and nothing is recoverable.

What is still refused is unchanged and deliberate: Mushegh does not **move** money. A transfer is
external dispatch, and D-13 puts that outside the blast radius without the owner physically
present. To change that, strike D-13's fourth bullet on purpose.

### 2. The ARCHITECTURE row — resolved by splitting the decline in two

It was one row declining two different things. `docs/ARCHITECTURE.md` now records the **gVisor
sandbox fleet as still declined** and the **CLI chain as adopted**, with the reason the original
decline no longer applies: it assumed the CLIs were interactive. They are not — `codex exec
--json` with `--output-schema`, `claude -p`, and an Agent-SDK subprocess over stdio JSON are
headless, permission-moded and schema-enforced. "Reversible git beats a container fleet" is still
true and still the design; it was never an argument against a headless process.

### 3. D-05's "never a shell" — resolved by sharpening the decision and typing the rule

D-05's row is amended in place (its own rule: edit the row, record what it invalidates). The word
carrying the weight is **unconstrained interactive shell**, and the line is at *interactive*. Four
properties, each now enforced rather than promised:

| Property | Enforcement |
|---|---|
| No interpreter is the executable | `ExecutorSpec` refuses `sh`/`bash`/`cmd`/`powershell`/`pwsh`/`ssh`/`wsl` **at construction**, not in a test |
| Nothing can be typed in | `stdin=DEVNULL` on every dispatch |
| No credential reaches the child | the environment is an allowlist built from nothing |
| The product is a proposal | no git write in the module; D-08 still owns the landing |

And the residual risk is named rather than solved: on Windows these CLIs install as `.CMD` shims,
a batch file re-parses its own arguments, so a brief containing `&` or a quote is **refused before
dispatch** rather than escaped. A wrong escape there is an injection, not a syntax error.

### 4. Four executors vs the 2 AM rule — resolved twice, because it was two objections

**The diagnosability half.** The objection is only answered if "which executor, does it exist,
what does it serve" is answerable *from the running system*. It now is:
`diagnose(about='executors')` prints one line per executor with its domains, tier, whether it is
installed, where, and whether its output is withheld. One tool call, no source reading.

**The capacity half — and the conflict is partly false.** The original sum was ~54 h against
8–10 h/week. Three things change it:

- **10 h are already banked**: M41 (6) and M47 (4) are built and gated.
- **The remaining estimate drops to ~27 h**, because the four executables are *already installed*
  on this host — `claude`, `codex`, `openclaw` and `rubo` all resolve on PATH — so M42–M44 carry
  no install or auth work, and M45 extends `judgment.py`'s existing `arbitrate()` rather than
  building an arbitration path.
- **M09 and M20 do not compete for these hours at all.** The two milestones that must not freeze
  are the voice re-enrolment (the gate for S08–S11) and the desk lamp (which un-darkens S28), and
  neither is engineering: one needs a quiet room and a calibration sitting, the other needs a Home
  Assistant token. They cost *owner* time, not build time, and can run in parallel.

**The ordering rule, so this cannot quietly become six weeks of nothing else:** no two executor
milestones ship back to back while a Phase-0 deletion (M02–M06) is outstanding. Deletion is
cheaper than construction and is already decided — `T0.3` is three of them in one hour.

## What is still owed, unchanged by any of the above

Not restated here — these are the standing surfaces, and they are authoritative:

- **[`docs/ROADMAP.md`](docs/ROADMAP.md)** — M01–M40, ~156 h. M09 (re-enrol the voice profile
  on good audio) is still the gate for S08–S11, and is still the dullest task on the list.
- **`docs/systems-plan.json`** — 184 open tasks, 23 in progress, 5 deferred, 28 cancelled.
  Most open work sits in S28 (8), S31 (8), S18 (7), S45 (7).
- **[`docs/EVIDENCE.md`](docs/EVIDENCE.md)** — three gates are still missing:
  `bench/test_lock_readonly.py` (`28.R5`), `bench/test_credential_inventory.py` (`36.R4`) and
  `bench/test_room_presence.py` (`43.R5`) do not exist yet, and every hardware benchmark
  stays `not yet measured` until they do.
- **[`docs/REGISTRY-RECONCILIATION.md`](docs/REGISTRY-RECONCILIATION.md) §4** — the code
  behind several cancelled tasks still needs deleting, and three owner decisions are open.

## Log

### 2026-10-07 (T0.1 + M42) — the backlog landed, and the transport plan was wrong

**T0.1 is done.** Three weeks and 173 paths committed on `mushegh/land-2026-10` in seven reviewable
chunks: the charter and registry; the executor brain; the toolchain jobs; Bookroom; the browser
gate and never-store; the graph-gate fix; the graph-memory deletion; and one honest batch of 117
files for which I had no per-file provenance — splitting *that* into themes would have meant
inventing attributions, so it says so in its own message and points at the registry.

**What that unblocked, immediately and measurably.** `landing.py` refuses to cut a worktree while
the checkout has moved past HEAD. Before the commit it reported *171 uncommitted changes*; after,
it returns clean. The delegation path went from unusable to usable by committing, which is exactly
what the refusal was for.

**M42's plan said SSH, and the plan was wrong.** `ssh host "openclaw agent -m '…'"` hands a
command *string* to a shell on the far end, which re-parses it — the same class `_batch_hazard`
refuses for a Windows `.CMD` shim, with a full shell instead of a batch interpreter. The contract's
`_no_interpreter` validator already refused `ssh`, so **the plan and the code contradicted each
other and the code was right.** Declined in D-91; the transport is the local CLI against the
gateway.

**Then `openclaw agent --help` on the live VPS replaced three of my guesses:**

- **`--message-file` exists.** The task goes over in a file, so nothing re-parses it. This is
  strictly better than what it replaces: `_batch_hazard`'s own docstring said the fix was to hand
  the task over in a file rather than guess at quoting. A brief reading *Draft a reply about "the
  boiler" & the rent* used to be **refused**; it now runs, verified byte for byte.
- **`--deliver` defaults to false**, and Mushegh never passes it, nor any channel or recipient. So a
  fleet turn produces a reply and **sends nothing**. The consent gate lives in the transport rather
  than in a prompt — the only place a model cannot be talked out of it.
- **`--timeout` exists**, so the CLI gets the brief's deadline and exits with a transcript instead
  of being killed. A killed process loses the half that matters at 2 AM.

**And the agent ids were never placeholders.** `personal` and `business` are real and have been
throughout. The specs were correct by accident; they are correct on purpose now.

**Two gaps the measurement exposed, reported rather than quietly fixed.** The laptop's `openclaw`
is **2026.2.14** against the VPS's **2026.9.3** — seven months, and the older client may not
have `--message-file` at all. That is precisely what D-88's daily job exists to close, and it has
not run. And **`personal` and `business` both run `minimax/MiniMax-M2.7` as primary** — a paid
model — with a free one only as fallback, which contradicts the stated split of personal-on-free
and corporate-on-best. That is the owner's config on his own host, so it is reported.

### 2026-10-06 (T0.2 + M44–M46) — the suite was not green, and nine reasons why

**T0.2 ran, and it failed: 230 passed, 9 failed.** That is the point of running it rather than
assuming it. The nine, and what each actually was:

| Gate | Cause | Fix |
|---|---|---|
| `check_public_clean` | **4 leaks.** `tools/bookroom.py` read `GEMINI_API_KEY` and `TYPESAFE_API_KEY` straight from `os.environ`, giving four credentials a second home. 36.F5 says one home, and the gate was right | the keys are declared in `mushegh/config.py` with their aliases; the tool asks config |
| `test_loop_registry` | **Both toolchain jobs were running unseen** — no period, no budget, no kill switch, no HUD row. 31.F4 exists for exactly this class and caught my own work from the previous turn | declared in `brain/loops.py` with generous budgets (an npm install is minutes) and the kill switch named |
| `test_catalogue_narrowing` | the `reading` group had no prompt in the 60-prompt corpus, so the Bookroom tool was never exercised by the router measurement | two prompts added, phrased the way he talks; 62 now |
| `test_website_claims` | the published tool list said 151 and the registry says 152 — `book` was missing | regenerated |
| `test_routing_manifest` | `tool:book` and `group:reading` resolved to nothing | the graph was four days stale; rebuilt |
| `test_graph_prune` | 27 unsupported inferred edges, **plus a real test defect** | pruned; defect below |
| `test_cohesion_baseline` | **the two graph gates could not both be green** — see below | the prune now records what it removed |
| `test_systems_plan` | `docs/SYSTEMS.md` was stale against the registry | re-rendered |
| `test_deploy_prune`, `test_website_claims` (2nd) | pass on re-run; they had been collateral | — |

**The test defect is worth naming on its own.** `test_graph_prune` asserted "a real import binding
is what saves an edge" by sampling `kept[0]` — the first surviving cross-file inferred edge. But
`unsupported()` is Python-only *by design*: a `.tsx` or `.sh` edge survives because it is out of
scope, not because a binding saved it. So the check passed or failed on **edge order**, and the
graph rebuild flipped it: the first survivor became `App.tsx -> reducer`, which no import rule had
ever looked at. It now samples only the edges the rule judged, and asserts the property across
**all** of them rather than one lucky first element.

**The two graph gates were in direct contradiction, and had been for some time.**
`scripts/graph_prune.py` edits `graph.json`; only graphify can rewrite `GRAPH_REPORT.md`. So after
a prune the report describes a graph that no longer exists, and `test_cohesion_baseline`'s check 1
— which compares graphify's printed cohesion against its own recomputation — failed on
whichever community had lost an edge near the rounding boundary. Measured both ways: **unpruned,
check 1 passed and `test_graph_prune` failed; pruned, the reverse.** Not satisfiable together.

The fix follows what check 1 is *for*: it is a check on the **formula**, so it has to compare like
with like. The prune now writes `graphify-out/pruned-edges.json`, and check 1 puts those edges back
before recomputing. Every other check still reads the pruned graph, because that is the graph the
project actually uses. All three graph gates are green at once for the first time —
`test_cohesion_baseline` 21/21, `test_graph_prune` 12/12, `test_routing_manifest` 22/22. Worth
noting for later: a prune is **not durable** — any `graphify update` re-extracts the edges it
removed, so this is a repeatable cleanup rather than a one-off.

**Then M44, M45 and M46.** All three were smaller than their estimates because M41's contract held:
M44 is one table row, M45 is one function over the existing `arbitrate()`, M46 is a table and two
functions. The things worth recording:

- **`mcode` has the best interface of the three**, measured not assumed: `stream-json`,
  `--output-schema` *and* `--permission`. It stays on `smart` rather than `full` — the executor
  already runs in a throwaway worktree, so widening it spends the bound and buys nothing.
- **A coding brief defaulted to the personal tier**, matched no executor, and failed as
  *"no configured executor serves coding/personal"* — which reads as a missing install rather
  than a contradiction in the brief. It is refused at construction now, and the tier is **not**
  silently upgraded: quietly rewriting it is how the free pool pays for corporate work.
- **The route question's wording is declared in `judgment.ROUTE_INSTRUCTIONS`**, not passed in.
  A caller that could write its own instructions could widen what the model is asked to decide
  without touching the module a reviewer reads.
- **An acceptance check that restates the task is refused.** `Brief` already rejects an empty one;
  the one that gets past it is the one that reads like diligence and verifies nothing. And
  `from_task()` refuses a record with no check rather than generating one — a generated
  acceptance check is Mushegh marking his own homework.
- **The constraints are chosen for failures a later check cannot undo.** `landing.py` would refuse
  a migration anyway, so telling the executor up front is the difference between a wasted paid run
  and a usable diff; an agent that has already sent an email has done something no gate reverses.

### 2026-10-06 (M43) — the landing path, and four defects it caught in my own code

**What got built.** `src/mushegh/brain/executors/landing.py`, the only path from an external coding
executor to a commit, plus `bench/test_coding_delegation.py` (**91/91**, registered). D-08 is four
sentences in a charter; four sentences enforce nothing, so this is the function they become.
Registry: `39.R4`. Charter: **D-90**.

**The isolation is the design, not a detail.** A coding CLI edits files in its working directory —
it does not hand back a patch to apply (D-80). So pointing one at the owner's checkout would put
the proposal in his tree *before any condition had been tested*, and "a refused approval leaves the
tree untouched" would be false by construction however carefully the branch was named. Each brief
gets its own `git worktree`, outside the repo, on its own new branch. Condition 1 is satisfied by
**where the work happens**.

**Four defects the gate found in code I had just written.** Each is a real failure, not a style
note, and all four came from checks written to be awkward rather than agreeable:

1. The branch name was the clock to the second, so two briefs in the same second collided and the
   **second legitimate delegation was refused**. A random suffix now.
2. A blank worktree path resolved to the current directory — which was `C:\Mushegh`. So
   `commit_approved("")` would have operated on **Mushegh's own repo**. Refused explicitly now, and
   the gate asserts it.
3. Condition 1 was checked by the branch merely not being named `main`. A dirty owner checkout
   passed in as the worktree **would have been committed to**. The check is now provenance: a
   worktree this module did not create is refused, whatever its HEAD says.
4. The migration scan read `git diff HEAD`, which does not show an untracked file — so a
   `CREATE TABLE` in a brand-new module **passed condition 3**. `add --intent-to-add` makes a
   created file visible to a diff without staging its content, which is the only non-destructive
   primitive that closes it.

**Bounds that are the decision.** Nothing is ever discarded: `tools/coding.py` has no reset, clean,
stash or branch-delete because "he can't lose your work" outranks tidiness, and this module's whole
git vocabulary is `worktree add`, `add`, `diff`, `rev-parse`, `commit` — enumerated in the gate, so
a sixth verb has to be added there deliberately. A refusal **leaves the worktree** and says where.
The owner is never asked about a change that cannot land: a red suite or a migration stops before
the approval stage, which the gate asserts by recording stage order — an approval request is an
interruption (D-29), and spending one on a dead change is the waste. And because `ApprovalQueue` is
durable rather than blocking, landing is two calls, with the second **re-proving** the other three:
the gate makes the suite go red after the yes, and makes a `CREATE TABLE` appear in a new file
after it.

**Two things I did not do, and why.** The **Claude Agent SDK was declined** — the contract already
has the subprocess-over-stdio-JSON path with the permission bound, and adding the SDK would replace
working code with a library re-implementing the four invariants and take the permission decision
away from D-08. And **T0.3's `forecast.py` deletion was wrong**: `46.F1`–`46.F3` are `done`, the
gate is registered, `day_shape.py` calls it, and D-28 removed S46 as a *modelling* system while
this module is arithmetic over a JSONL with no statsmodels. The other three files in that row were
already deleted on 2026-10-04. T0.3 is closed as a correction rather than executed.

**A fifth defect, found by re-reading rather than by a test.** `git worktree add … HEAD` hands
the executor the last **commit**, not the owner's working tree. So on a dirty checkout a delegated
change is written against code he has already replaced — and it looks entirely reasonable until it
is merged. Measured: 171 uncommitted changes against a HEAD from 2026-09-15. It now **refuses**
at the isolate stage, with the count and the two one-command fixes. A warning attached to a success
is read as a success, and nobody should pay an executor to work against code that is gone. The
consequence is worth saying plainly: **until the commit happens, this path cannot be used for real
work** — which is correct behaviour and also a dependency.

**Still open.** No external CLI has produced a diff through this path, so the executor half is
proven only against a stub; D-43 wants seven days. And an asymmetry worth naming: `dispatch()` runs
the CLI on the **brain** host while `tools/coding.py` forwards to the **laptop** — the same machine
in development, two machines on the VPS, and unresolved.

### 2026-10-06 (late night) — the toolchain maintains itself, and four facts changed the design

The owner asked for two jobs: a 24 h version check across Claude Code, Codex, OpenClaw and MiniMax
Code that installs a new release and proves it with a **ping that must come back a pong**; and a
168 h review in which Jev says what each tool is missing and the tools are asked themselves.
`src/mushegh/brain/toolchain.py`, `bench/test_toolchain.py` **73/73**, scheduled in `server.py` behind
`toolchain_autoupdate_enabled`. Charter: **D-88** (a bounded extension of D-07's whitelist — an
unattended host mutation is a decision, not a feature) and **D-89** (advisory by construction).
Registry `31.R8`, `31.R9`.

**Four things were measured on the host rather than assumed, and every one of them moved the
design:**

1. **`openclaw --help` timed out at 40 s with no output.** So installed versions come from
   `npm ls -g --json`, not from each CLI: one call answers for all three npm tools and none of
   them can hang a daily job. It is also why OpenClaw gets **no model ping** — its CLI needs the
   gateway and a live agent id — and that gap is declared in its spec so it appears in the report
   instead of reading as an oversight.
2. **Claude Code is a native install** (`~/.local/bin/claude.EXE`, 2.1.288) with no downgrade
   command this project can verify. So `can_rollback=False`, and a failed ping there is reported
   loudly and **not** repaired. Faking a rollback would be worse than naming the gap.
3. **`mcode` is real and installed** — npm `@minimax-ai/code` 0.6.3, with `exec`, `update`,
   `plugin` and `acp` read off its own `--help`. `docs/EXTERNAL-EXECUTORS.md` had it recorded as
   *unverified*; that note is now corrected rather than left to rot. Its `plugin` subcommand is a
   real place a weekly proposal can land.
4. **The three CLIs print versions in three different shapes** — `2.1.288 (Claude Code)`,
   `codex-cli 0.160.0`, and a bare `0.6.3` — so `parse_version()` takes the first semver token
   and refuses to invent one from noise.

**The bounds are the decision, not decoration.** One tool at a time, each proved before the next is
touched, because updating four and pinging four leaves four suspects for one failure. The ping runs
**only when a version changed** — it costs money on three of the four, and proving the path worked
yesterday says nothing about today's release. A failed ping rolls back to the last version that
answered. **A quiet run reports nothing**, because a daily "nothing changed" is an interruption
bought with no information. Residual risk named rather than engineered around: on Windows a running
executable is locked, so an update attempted mid-brief fails and is reported as `update-failed` —
self-limiting, and cheaper than a cross-module lock.

**The weekly review installs nothing, and the gate asserts the absence of an install path** —
which is the only thing that makes the word "proposal" mean anything. `IMPROVEMENT_KINDS` is
declared in code (plugin, command, skill doc, MCP server, permission, model, **nothing**) and Jev
picks among those, so it cannot invent a capability for itself; the `nothing` option is
load-bearing, because without it every week produces a change whether or not one is warranted. Jev
is asked against **measured** friction from the audit trail, applying the 2026-09-20 lesson that
the same question returned confidence 0.19 against a summary and 0.95 against the source. The tools
are asked through their own non-interactive entry points, with the prompt saying out loud that the
answer is advisory.

**A mistake of mine, caught by checking rather than by a gate: I deleted D-87.** The D-86 rewrite
spliced from D-86's heading to D-60's, and D-87 was sitting between them. Counting the decision ids
found a single gap at 87; it is restored. The same count showed `docs/README.md`'s tally had been
wrong before any of this (62+9+2 = 73 claimed, while D-01–D-78 is 78 decisions), so the tally is
replaced with the range, which can be checked.

**And on the Bookroom engine going offline:** the integration was written so that change costs
nothing here. It never reads `BOOKROOM_APP_ROOT` itself, never builds the engine path, and
recognises the missing-engine case from the SDK's own error text — so when the engine ships inside
the package that branch stops firing on its own. Asserted in `bench/test_bookroom_tool.py`, now
61/61, including that the SDK is imported inside a function and never at module level.

### 2026-10-06 (night) — the Bookroom SDK is in, and it moved a decision

The owner handed over `bookroom-sdk` v1.0.0 with a `SKILL.md` in its root. Reading the repository
**changed D-86**: it was written assuming the SDK would enter as an executor adapter, and it enters
as a tool instead. The reasons generalise, which is why they are in the charter and not just here:

1. the SDK's own first rule is that **Python holds the keys in the process**, and Mushegh's brain
   already is that process — a subprocess would marshal `GEMINI_API_KEY` into a child for nothing;
2. the `bookroom` CLI has **no `preflight` subcommand**, and `guide` does not preflight on its way
   in — so the CLI route would lose the one call the SDK says to always make before spending;
3. a study guide is a long **checkpointed** job that resumes from its last finished stage, which is
   not the contract's deadline-and-result shape.

**The line that came out of it, worth keeping:** the executor contract bounds an *agent* —
something that acts on its own judgement. A library is a tool. Routing a library through the
contract buys none of its protections and costs all of its ceremony.

`src/mushegh/brain/tools/bookroom.py` is one tool, `book`, with four actions. The fence: a `guide` is
**refused** until a preflight for that same file has run within thirty minutes, and it is a refusal
rather than an automatic estimate, because the point of the number is that the owner hears it. An
expired estimate is refused like none at all. Only `guide` is confirm-gated — a gate in front of a
cost estimate teaches him to skip the estimate. Three honesty rules from the skill file are
asserted rather than trusted: `quality` is spoken as *n of 16*, a partial run is never worded as a
pass and nor is a missing figure; `claim_audit` is always *lexical overlap, not fact-checking*, with
"verified" and "fact-checked" asserted **absent**. `bench/test_bookroom_tool.py` 57/57; registry
`41.R5`.

**It cannot run on this host yet, and that is the headline rather than a footnote.** The SDK wraps
a *separate* flat-tree application containing `book_pipeline.py`, reached through
`BOOKROOM_APP_ROOT`, and that engine is not in the SDK repository. Every call goes through it —
`extract` and `check` included — so the degradation paths are the first thing the gate covers.
Owner actions: install the package into the brain's interpreter, set `BOOKROOM_APP_ROOT`, set
`GEMINI_API_KEY`, optionally `TYPESAFE_API_KEY` (without it JEv review is skipped, which the tool
says out loud). Per the SDK's own definition of done this is incomplete until a real book produces
a validated report — *"do not report success on the strength of a unit test alone."*

**M44's real work also landed: the parsers.** Each CLI emits a different machine-readable stream,
and parsing is not tidiness — **a JSON event stream read as prose is how a reported failure gets
spoken as a result.** `codex exec --json` emits `turn.failed`, Claude Code's stream-json emits
`is_error`, and `openclaw --json` can carry `status: "ok"` over a failed tool, which is this
project's own recorded trap ("ok hides failures": 7 of 14 crons once hid a failed-tool diagnostic
behind `status=ok`). So a parser verdict can now fail a run the exit code passed, and the gate
drives exactly that case: a process that exits **0** while reporting `turn.failed` comes back
`ok=False` with the executor's own words in `error`. Parsers are tolerant by design — a non-JSON
line is kept, not dropped, because these tools print human notes beside their events and a parser
that discards the unrecognised half is one that loses the error message.
`bench/test_executor_contract.py` 98/98 (was 83).

### 2026-10-06 (late) — Part X resolved, and resolving it found a leak I had just shipped

The four conflicts are now charter edits and code changes; Part X records each. The one worth
repeating here is the defect, because it came out of the previous entry's own work rather than out
of the original design: **`_account()` wrote the executor's transcript into the audit line
unconditionally.** D-83's whole promise is that financial figures stay in Rubo's store, and the
audit file is one of the three places it names. A declared payload is now withheld and the line
carries an HMAC fingerprint instead, so two runs stay comparable and nothing is recoverable from
the log. It surfaced by asking what would actually *enforce* D-83 rather than by a test failing —
which is the argument for writing the enforcement instead of the promise.

Second thing worth keeping: the finance never-store class has **no detector, on purpose.** Every
other class is anchored on a label or a format; a financial position has neither. "EUR 2,400" is a
balance, a salary, or what the coffee machine cost, so a pattern would refuse to remember the last
of those — the exact false positive `src/mushegh/brain/never_store.py`'s own docstring warns against.
Declaration beats detection wherever a caller has certainty, and the finance executor has it.

Third: D-05's rule moved from a test into a **type**. `ExecutorSpec` refuses an interpreter at
construction, because a spec is data and data gets edited by whoever adds the next executor. A
grep over the file would not have stopped them.

`test_executor_contract.py` 83/83 (was 58), `test_never_store.py` 53/53 (was 50), `test_doc_paths`
27/27, `test_layering` 38/38, `test_audit_integrity` 45/45, registry re-rendered. Ruff is clean on
everything touched; seven pre-existing errors remain in files this work did not open
(`src/mushegh/brain/emergency.py`, `src/mushegh/brain/governor.py`, `src/mushegh/brain/tools/routines.py`,
`src/mushegh/brain/tools/stock.py`, `src/mushegh/edge/voice_health.py`,
`src/mushegh/protocols/portable.py`) and are left alone rather than swept into an unrelated change.

### 2026-10-06 (evening) — the contract and the browser gate, and three things found by running them

**The owner restated the split and broadened one half of it.** Coding to the corporate CLIs;
personal domains (email drafting, document drafting, business management) to a **new** OpenClaw
fleet on free models, corporate to OpenClaw on the best models; **finances, taxes, investments,
portfolio, salary management and distribution** to Rubo; summarisation to his own SDK. The finance
half had been flagged as needing a deliberate nod because D-12 refused it; he restated the broad
reading, so **D-12 is now marked superseded and [D-83](docs/DECISIONS.md) is the live decision**,
with the blast-radius half of D-12's reasoning kept: Mushegh reads, computes, models and drafts
across all of it, and does not **move** money, because a transfer is external dispatch and D-13
puts that outside the radius without the owner physically present. **D-87** records the tier rule.

**`05.R1` — and the subsystem doc had the defect backwards.** `docs/subsystems/05-browser-control.md`
said a spend was one voice command away. In fact `browser` was in `proactive.CONFIRM_TIER` with no
dynamic rule, so `confirm_required` fell through to its final `return True` and **every** browser
action confirmed — `read` and `open` included. Both are real failures and they are different ones:
a gate that never fires lets a purchase through; a gate that fires on every page read teaches the
owner to say yes without reading it, after which the one that mattered is waved through with the
rest. That second failure is what `ha_call`'s own comment in `proactive.py` names for lamps, and it
costs more here because this browser carries his logged-in sessions. The rule now: navigation and
reading flow, `fill`/`type` flow and **arm** the gate, `click`/`press` confirm when armed, when the
key is Enter, or when the target names a commit. 45/45. The doc is corrected rather than quietly
rewritten, and it did **not** end up extending `test_confirm_tier_documented.py` as planned — that
file asserts the doc and `CONFIRM_TIER` agree, which is a different question from when the gate
fires, and the doc-consistency check has to stay able to fail on its own.

**M41 — and the gate caught my own bug before the owner could.** A non-zero exit with empty stderr
produced an **empty error line**. `Result.ok` was still correct, so nothing was unsafe, but a
delegation would have been reported as failed with no statement of what happened — which is the
shape that gets read as "probably fine". `_error_line()` can no longer be empty on a failure.

**Two things only a real run could tell me.** First: **all four executables are already installed
on this host** — `claude`, `codex`, `openclaw` and `rubo` all resolve on PATH — so the first
draft's check that none was installed was false the moment it was written, which is precisely the
`unverified-import` failure the evidence vocabulary exists to name. Availability is now measured
against the host. Second: `codex`, `openclaw` and `rubo` all resolve to Windows **`.CMD` shims**,
and a batch file's arguments are re-parsed by the command interpreter — so an `&` or a quote inside
a task string is a command-injection surface rather than a character, in the one module whose whole
job is to be the safe boundary. `_batch_hazard()` refuses such a brief before dispatch rather than
attempting to quote it, because a wrong escape there is an injection and not a syntax error. Running
`rubo` also showed it resolves its checkout from `RUBO_REPO`, which the allowlist had stripped.

Ruff clean. `test_layering` 38/38, `test_doc_paths` 27/27, registry check passes, `SYSTEMS.md`
re-rendered. **Neither task is `done`:** both are `in-progress` with `hermetic-green` evidence,
because D-43 wants seven consecutive days of real use and nothing calls `dispatch()` yet.

## The rule this file now carries

Six parts of this log were lost because they lived in one uncommitted file on one laptop.
**A conclusion that is not in the registry, a decision doc or a commit does not exist.**
Write the state where it belongs, then write the narrative here.
