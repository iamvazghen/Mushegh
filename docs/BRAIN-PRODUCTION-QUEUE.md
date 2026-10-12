# Brain Production-Readiness Queue

> **Scope:** everything between today's state and a brain that is production-ready by its own
> charter ([`PURPOSE.md`](../PURPOSE.md), [`DECISIONS.md`](DECISIONS.md), [`EVIDENCE.md`](EVIDENCE.md)),
> per the task catalogue in
> [`subsystems/01-brain-core-intelligence.md`](subsystems/01-brain-core-intelligence.md).
> **Written:** 2026-10-10, after the `C:\Afon` → `C:\Mushegh` move and the graphify run of 2026-10-10.
> **Reading order:** Phase 0 first, always. Nothing below Phase 0 is trustworthy until it is done.

## How to read this

| Marker | Meaning |
|---|---|
| **[OWNER]** | Cannot be completed by an agent. Needs a decision or an approval from Vazghen. |
| **[GATE]** | The run that proves it. A task with no gate is not a task, it is an intention. |
| **→ blocks** | The task cannot start until this one lands. |

Phase 0 restores a runnable system; Phase 1 restores faith in the instruments; Phases 2–5 are the
real work; Phase 6 is hygiene. The ordering is not by importance — it is by **what unblocks the
most per unit of effort**, which is the order the subsystem document settled on and the order the
project's own rules (`docs/PRINCIPLES.md`, rule 1: *never state a fact about the tree without
checking the tree*) demand.

---

## Progress log — live verification, 2026-10-10

Recorded as work completes, so this document doubles as the tracker. **Verified** means it was
run or read in the current working tree; **blocked** means it needs the owner or an external
service.

| Item | State | Evidence |
|---|---|---|
| Repo relocated to `C:\Mushegh` | **verified** | `git rev-parse --show-toplevel` → `C:/Mushegh`; branch `afon/land-2026-10`; `core.hooksPath=scripts/githooks` intact |
| `import mushegh` works | **verified** | `mushegh OK -> C:\Mushegh\src\mushegh` |
| Goodnight marker no longer hardcoded | **verified** | `brain/protocols.py:45` derives `_EDGE_STOP_MARKER` from `_REPO_ROOT` |
| **0.2 — scheduled tasks migrated** | **DONE 2026-10-10** | All four are `Mushegh*` and correct: `MusheghEdge` → `C:\Mushegh\.venv\Scripts\pythonw.exe -m mushegh.edge.assistant` · `MusheghPcAgent` → `-m mushegh.edge.pc_agent` · `MusheghEdgeRefresh` → `C:\Mushegh\scripts\restart_edge.ps1` · `MusheghEdgeGuard` **Ready** (was Disabled). No `Afon*`/`Watari*`/`Jarvis*` remain. **Goodnight and phoenix are no longer no-ops** |
| **0.3 — edge "down" was wrong** | **corrected** | Not down: **deliberately parked**. `mushegh edge: parked by C:\Users\iamva\.mushegh\MAINTENANCE — parked 2026-08-13 by owner request: nothing in production until the TODO list is done`. 0 `pythonw` is the *correct* state. This queue is what unparks it |
| **2.1 / 2.2 — loop-keyed client map** | **already implemented** | `tools/base.py:302-376`: `_CLIENTS` keyed by loop + content signature. The subsystem doc's *"which wart to carry is the owner's call"* is **stale** — the answer was already built |
| Client reuse actually works | **verified** | Repeat call returns the **same** client; equivalent headers reuse; different headers create a new one; a second event loop does not reuse the first loop's client |
| **2.3 — live arbitration inside the cap** | **CLOSED 2026-10-10** | `tools/measure_jev_arbitration.py`, live: **median 236 ms, 14/15 inside the 400 ms cap**, min 196 ms. Doc baseline was 961 ms and **0/8**. Outcomes `decided` with real winners |
| **2.2b — clients were never closed** | **DONE** | Added `aclose_http_clients()`; the old sync `close_http_clients()` only cleared the map, so sockets were left to the GC. Wired into the brain's shutdown (`server.py`, inside the serving loop — the only loop the clients are bound to) |
| **2.3b — cold start** | **DONE, proven** | Added `prewarm_client()`; fired at startup for the Jev endpoint. Measured: handshake 1165 ms, then the **first** arbitration came back at **233 ms, inside the cap, `decided`** (was 2002 ms / `unavailable`). A status error is treated as a *successful* warm — the socket is the point, and reporting it as failure would warn on every boot |
| 2.4 — no transport regression | **verified** | `test_jev_tool_arbitration` 38/38 · `test_jev_turn_assessment` 48/48 · `test_jev_judgment` 26/26 — unchanged |
| **Preflight's real bug** | **diagnosed** | `bash` on PATH is `C:\WINDOWS\system32\bash.exe` — the **WSL launcher**, which mounts the drive at `/mnt/c` and cannot resolve `C:/...` at all. Run under **Git Bash** preflight passes cleanly (exit 0, `=== preflight OK ===`) in ~8 s. The runner already prefers Git Bash for exactly this reason; the earlier 120 s timeout was contention, not a defect |
| **Speaker gate false failure** | **fixed + proven** | `[10.F3]` matched the bare string `speaker_threshold`, so `subsystems.py` — which *names* the key in the S10 registry and never reads it — failed a gate it obeys. Now detects attribute **access**. Verified: readers = `{speaker_id.py}`; a synthetic second reader **fails** the gate; a mere mention does not. `test_phase5_identity_bench.py` **70/70, exit 0** |
| `psycopg` / `redis` absence | **verified — correct as-is** | Deliberately removed 2026-10-04 (D-02/M02; `pyproject.toml:58-61`), `uv lock` re-run to match. Nothing imports them. My earlier reinstall was a mistake, reverted |
| Registry audit (S01) | **done** | `01.F2`/`01.F3` carry `hermetic-green` + dates. `01.R1`–`01.R4` are `recorded-note` **2026-09-14** — four weeks stale (task 1.2). `01.R6`/`01.R7`/`01.R8` carry `hermetic-green` with **no date at all** |
| 0.1 — delete empty `C:\afon` | **blocked — needs admin** | The holder is **two elevated VS Code processes** (PID 44876 started 2026-10-07, PID 50356 started 2026-10-03). They survive closing every window, refuse non-forced termination, and return *Access is denied* even to `taskkill /F` from a normal session; Restart Manager cannot enumerate them. The folder is **empty** and harmless. From an **elevated** PowerShell: `taskkill /PID 44876 /F; taskkill /PID 50356 /F` — or it clears on the next reboot |
| **0.4 — goodnight marker gate** | **DONE** | `bench/test_protocol_smoke.py` **53/53, exit 0**. The live registry resolves `_EDGE_STOP_MARKER` to `C:\Mushegh\logs\edge_stopped_by_owner`; no `C:\Afon` string remains in `goodnight`'s `pc_command` |
| **0.5 — code graph refreshed** | **DONE** | `graphify update .` → **6539 nodes, 11305 edges, 400 communities**. Report title is now *"Graph Report - Mushegh"*, and `.graphify_root` was a bare `.` — now the absolute `C:\Mushegh` |
| **`transit` was invisible to the router gate** | **fixed** | `test_catalogue_narrowing.py` failed *"every lazy group is exercised — ['transit']"*: `transit` shipped as one of 27 lazy groups with 38 triggers and **zero** corpus coverage. Added 2 prompts (both proved to route first try before being written) and updated the count 62 → 64. **32/32, exit 0** |
| **Speaker gate false failure** | **fixed + proven** | `[10.F3]` matched the bare string `speaker_threshold`, so `subsystems.py` — which *names* the key in the S10 registry and never reads it — failed a gate it obeys. Now detects attribute **access**. Proven: readers = `{speaker_id.py}`; a synthetic second reader **fails**; a mere mention does not. `test_phase5_identity_bench.py` **70/70, exit 0** |
| **Website drift from the rename** | **fixed** | `test_website_claims.py` was **5/10**: pages cited `personality/afon.md` and `src/afon/edge/device_profile.py` (both phantom), the skills list named `afon-architecture` instead of `mushegh-architecture`, and the generated tool data was stale (152 vs 156, missing the 4 `transit_*` tools). Paths fixed, skill renamed, data regenerated → **10/10, exit 0** |
| **This queue document** | **fixed** | `test_doc_paths.py` caught my own phantom citation (`docs/PURPOSE.md`; the file is at the repo root) → **34/34, exit 0** |
| `docs/SYSTEMS.md` stale | **fixed** | Generated dashboard, never hand-edited: `scripts/systems_plan.py render` → `test_systems_plan.py` **18/18, exit 0** (it had also been failing on the stale `GRAPH_REPORT.md`) |
| `psycopg` / `redis` absence | **verified — correct as-is** | Deliberately removed 2026-10-04 (D-02/M02; `pyproject.toml:58-61`), `uv lock` re-run to match. Nothing imports them. My earlier reinstall was a mistake, reverted |
| Registry audit (S01) | **done** | `01.F2`/`01.F3` carry `hermetic-green` + dates. `01.R1`–`01.R4` are `recorded-note` **2026-09-14** — four weeks stale (task 1.2). `01.R6`/`01.R7`/`01.R8` carry `hermetic-green` with **no date at all** |
| 1.x — full suite baseline | **257 tests, 8 failures found, 7 fixed** | Run in 5 batches (a single run is reaped by the environment mid-flight; `TESTS` is sliced from `run_all_tests` without touching `bench/`). **Batch 1 (0–55) 55/0 · Batch 2 (55–110) 53/3 · Batch 3 (110–165) 53/3 · Batch 4 (165–220) 56/0 · Batch 5 (220–257) 36/2** |
| 1.2 / 1.4 — registry evidence refreshed | **DONE (one honest exception)** | `01.R2` 51/51 · `01.R3` 38/38 · `01.R4` 23/23 — all four-week-stale `recorded-note` claims now carry `hermetic-green` dated 2026-10-10. `01.R6/R7/R8` had **`hermetic-green` with no date at all**; they now carry 2026-10-03 (the date their own notes claimed) plus today's 38/48/26. `docs/SYSTEMS.md` re-rendered. `test_systems_plan` 18/18, `test_registry_complete` 23/23 |
| **01.R1 cost check** | **RESOLVED — owner ruled 2026-10-10** | **Keep the 500 µs budget; gates only count on a quiet machine.** The measurement was fixed to best-of-N (a single wall-clock span over 8400 calls spanned 97–2829 µs across seven identical loops — it was measuring the machine, not the classifier). The **number was not moved**, so the gate reports honestly red whenever a second agent, the Docker stack, ollama or OneDrive are running. That is the intended behaviour of a performance budget, not a defect to paper over |
| **4.1 — the 01.F1 gate** | **RESOLVED — owner ruled 2026-10-10** | **Assert on what actually ran.** Verified before ruling, not after: the gate had *already* been converted off the fake LLM's `fired` list and now asserts that every tool the clause plan names appears in the execution log, with the model's call list reported beside it. **10/10**, and `test_clause_routing.py` **28/28**. The subsystem doc's 8/10 and the registry's `unverified-import` are both corrected; the registry now carries a dated `hermetic-green`. The decision ratified the code rather than justifying it |
| **4.3 — `combo_web_memory`: corrected measurement, and a corrected finding** | **PROBE WAS BROKEN — my first report here was WRONG** | `tools/probe_chain_flakiness.py` read `bs._CAPTURE` but **never installed `audit.record = bs._patched_record`**, which only happens inside `behavioral_suite.main()`. Nothing was ever written to the capture list, so **every run reported `tools fired: []` and "missing tool(s)" regardless of what the brain did.** I reported "6/6 at 19.0, zero tools, the agent claiming it saved something it never saved" — that was an artefact of the instrument, not a defect in Mushegh. Fixed 2026-10-11 (the patch is installed before the first agent is built). **True measurement, 5 runs: 55.0 / 63.0 / 63.0 / 63.0 / 63.0, median 63.0**, latency 9.9–15.8 s against a 14 s budget |
| **4.3b** | ~~**OWNER CALL: effect vs identity.**~~ **RESOLVED 2026-10-11 — EFFECT** | The owner ruled a planned clause is satisfied by any tool that does the job. Implemented as **one deliberate pair** in `behavioral_suite.TOOL_EQUIVALENTS` (`web_search` is met by `wiki_lookup`) — narrow on purpose: a general "any lookup counts" rule would forgive a turn that ran the wrong *kind* of tool, and this suite's history is of measurements that turned out to be about the harness. **Every substitution is printed**: `~ clause met by substitution: ['web_search'] -> ['wiki_lookup']`, so acceptance is visible rather than silent. `test_scorecard_integrity` 76/76 unchanged. Diagnosis it answered: every run fires `remember` and `wiki_lookup`; only `web_search` never fires, and the completion pass does force it by name before the model answers with `wiki_lookup` | — done | **[GATE]** the scorer reports each substitution |
| **5.1b — the "primary unavailable" warning was lying** | **RESOLVED 2026-10-11** | The median-5 run logged 20 warnings suggesting a failing LLM provider. With stderr captured (`cmd /c "... > file 2>&1"` — PowerShell's `*>` drops a native process's stderr here), the truth: **35 invocations, ZERO model failures, `failed_over_count=0` on every call** — yet 18 were answered by a non-primary model. Cause: `complete(skip_primary=True)` (`llm.py:602`), which B4 uses at `agent.py:1877` **after the primary dodges a forced tool call**. Nothing was unavailable; the caller had asked to skip it. The warning compared against `self._chain[0]` unconditionally and called every non-primary answer an outage. **Fixed**: it now distinguishes a B4 skip, a narrow tier (`only`), a prepend escalation, and a genuine outage. This also explains the compound-turn latency — a forced pass costs a primary attempt **plus** a B4 retry, two round trips — and it replaces my earlier `_SlowFirstToken` hypothesis, which was wrong |
| Fixes from that run | **7 of 8, each verified green** | `transit` corpus coverage (32/32) · speaker-threshold detection (70/70) · this document's phantom citation (34/34) · website rename drift (10/10) · `docs/SYSTEMS.md` regenerated (18/18) · VPS ticker + both systemd units renamed (23/23, 11/11) · graph prune + cohesion baseline (12/12, 21/21) · citations gate now tests both the guard and the paywall (46/46) · loop registry classified the new spawn site (27/27) · `wizard_state` delegates to the one owner of the state root (49/49) · **LLM failover warning now names the real cause** (`test_llm_routing` 20/20, `test_llm_failover_speed` 10/10, `test_llm_chain_exhausted` 10/10) |
| **4.4** | ~~**The authoritative run.**~~ **DONE 2026-10-11 — GOAL 1 MET at 96.5** | Under the effect ruling, median-5, sandboxed: `combo_time_memory` **100.0**, `combo_web_memory` **93.0** (was 63.0), **Combination 96.5 → PRODUCTION-READY** against the ≥90 bar. Log `logs/combination-effect2.txt`. **Stated plainly so nobody misreads it: the brain did not change** between the 81.5 run and this one — same turn, same tools fired. The instrument stopped counting a correct substitution as a fabrication. The sequence **51.5 → 89.0 → 81.5 → 96.5** is as much a warning as a result: 81.5 was the number finally measured honestly, 96.5 is the number measured *correctly*, and quoting only the last would claim 15 points of improvement that never happened. Variance also resolved: `[40, 93, 63, 100, 93]` → `[63 ×5]` → a stable 93 | — done | **[GATE]** Combination ≥90 at median-5 — **passed 96.5** |
| **The 40-or-100 variance is GONE — replaced by a stable 63** | **verified** | The recorded spread was `combo_web_memory [40, 93, 63, 100, 93]`. It is now `[63, 63, 63, 63, 63]`. The turn no longer *sometimes* works; it **deterministically** answers with `wiki_lookup` instead of the planned `web_search`. That is what queue item 4.3 asked for — "make it land consistently, not 40-or-100" — and it is met, just not in the direction hoped: the flakiness became a fixed shortfall. `combo_time_memory` also rose from a recorded 85.0 to **100.0** |
| **Instrument fix: the suite never isolated the conversation** | **DONE** | `_cleanup()` forgot test facts and cleared modes but left `<state>/mushegh_session.json`, so a fresh agent resumed the previous turn — `_cleanup`'s own docstring calls that "half an isolation fix", and this was the other half. Added `isolate_session()`: the suite now owns a session file **in temp** (not the state root, which `test_data_classification` scans) and `_cleanup` unlinks it. **The owner's real session is never touched** |
| **5.5 — goal 6, no unsolicited speech** | **hermetic half DATED 2026-10-11** | `test_no_unprompted_feed.py` **10/10, exit 0** (the behavioural half — `mynews.py` stays on disk, its signal function still callable for a focused session). The D-29 number is consistent across all three places that state it: charter default **3**, `.env.example` `MUSHEGH_PROACTIVE_DAILY_BUDGET=3 ("D-29: three, not six")`, and the gate reads it out of `DECISIONS.md`. Still open: a dated END-TO-END run against the running system (≤3/day, 0 inside a focus block) — that is a live measurement, not a gate |
| **6.8 — refresh the subsystem doc's stale numbers** | **DONE 2026-10-11, in two passes** | First pass: `01.E1` carries the median-5, plus a new **01.E1b** replacing the page the old `40-in-five` variance got — it records the spread's disappearance, `combo_time_memory` at 100.0, the pair at 81.5, that the remaining gap is a scoring-specification question, the full list of causes ruled out, and **the wrong "zero tools" report that started the investigation**. Second pass, found by re-reading the benchmark table against the registry rather than trusting either: goals **1, 2 and 3 were all stale** — goal 1 still said 89.0 after today's 81.5, and goals 2 and 3 still carried an `unverified-import` caveat the registry had not carried since 2026-10-07. All three now carry dated runs: `test_metrics` **78/78**, `test_trace_completeness_live` **14/14**, `test_uncertainty` **46/46**. Goal 4 measured hermetic (5.4 above). **Two goals remain `not yet measured`, and both need the edge unparked** (self-edit needs the owner's approval of a diff; unsolicited-speech needs a live day) |
| **The last failure** | **RESOLVED — suite is now 257/257 green** | `test_data_classification` was 34/35. Two separate things were behind it: `wizard-state.json` **was** a real code gap (the wizard wrote a store nothing declared) and is now declared in `data_classes.py`; the other 6 entries were the owner's own unreferenced files. Per the owner's decision they were **moved, not deleted**, to `C:\Users\iamva\.mushegh-quarantine\` — `afon_session.json`, `afon_tasks.sqlite.bak-20261010-111312`, and the four July scripts (`load-secrets.ps1`, `start-edge.ps1`, `test_chain.ps1`, `uptime-watch.ps1`). Gate: **35/35, exit 0** |

---

## Phase 0 — Restore the working baseline

Today's move left three things broken. All three are cheap; all three block honest measurement.

| # | Task | Who | Gate |
|---|---|---|---|
| **0.1** | Close the VS Code window whose workspace is `C:\Afon`, then delete the empty leftover directory `C:\afon`. | **[OWNER]** | `Test-Path C:\afon` → `False` |
| **0.2** | Run the scheduled-task migration **elevated**: `powershell -ExecutionPolicy Bypass -File C:\Mushegh\scripts\finish_afon_rename.ps1` | **[OWNER]** (UAC) | Script prints `No Afon*/Watari*/Jarvis* tasks remain.` |
| **0.3** | Confirm the edge actually came up after 0.2: `Get-ScheduledTask ? TaskName -match Mushegh` all Ready/Running, and four `pythonw` processes (supervisor + worker × `MusheghEdge` + `MusheghPcAgent`). | agent | **[GATE]** process list matches `TESTING_GUIDE.md` §0.3 |
| **0.4** | Re-assert the goodnight marker path end to end. `brain/protocols.py` now derives it from `_REPO_ROOT` (fixed today, was hardcoded `C:\Afon\logs\...`); confirm `scripts/install_edge_guard.ps1` and `scripts/edge_guard.ps1` read the same file — they do, and `restart_edge.ps1` clears it. | agent | **[GATE]** `bench/test_protocol_smoke.py` green |
| **0.5** | Refresh the code graph: `graphify update .`. The stored `GRAPH_REPORT.md` is titled *"Graph Report - Afon"* and `.graphify_root` holds a bare `.` rather than the absolute scan root the skill writes. | agent | **[GATE]** report title reads `Mushegh`; `git rev-parse HEAD` matches `built_at_commit` |

**Why 0.2 matters more than it looks.** Every code path that names a task expects the canonical
names: `protocols.py` goodnight stops `MusheghEdge` and phoenix starts `MusheghEdgeRefresh`,
`restart_edge.ps1` restarts `MusheghPcAgent` + `MusheghEdge`, `autostart.py` reports them, and
`SOP.md` / `TESTING_GUIDE.md` assert them. The registered tasks are still `AfonEdge`,
`AfonPcAgent`, `AfonEdgeRefresh`, `AfonEdgeGuard` (the last one **Disabled**) and point at a
directory that no longer exists with a module that no longer exists. **Goodnight and phoenix are
currently silent no-ops.**

---

## Phase 1 — Re-establish the baseline (do not trust pre-move numbers)

> Today the virtualenv was rebuilt: `uv sync --frozen --all-extras` replaced the stale `afon`
> editable install with `mushegh`, upgraded `ntgcalls` 2.2.2 → 2.2.5, and `psycopg` /
> `psycopg-binary` / `redis` were reinstalled by hand because they are **not in `uv.lock`**.
> Any measurement taken before today ran on a different environment. Do not compare across the
> move until the gates below have been re-run and dated.

| # | Task | Who | Gate |
|---|---|---|---|
| **1.1** | **RESOLVED 2026-10-10 — no action, and my earlier "fix" was wrong.** The three packages `uv sync` pruned (`psycopg`, `psycopg-binary`, `redis`) were **deliberately removed on 2026-10-04** under D-02/M02, with `uv lock` re-run to match; `pyproject.toml:58-61` records it. Verified: nothing in `src/`, `bench/` or `tools/` imports any of them. Reinstalling them (done during the rename, reverted afterwards) put the environment back out of line with the charter. | — done | **[GATE]** `uv sync` leaves the venv exactly as the lockfile declares |
| **1.2** | Re-run and **date** the four claims whose evidence kind is `recorded-note` (four weeks old): `01.R1` `test_intent_classes.py` (30) + 42 labelled · `01.R2` `[ambiguous]` + `test_pure_chat_tools.py` (51) · `01.R3` `test_goal_attribution.py` (38) · `01.R4` `test_registry_complete.py` (21). | agent | **[GATE]** each green with today's date in the subsystem doc + registry |
| **1.3** | Re-confirm the gates closed on 2026-10-07 still close in the rebuilt env: `test_uncertainty.py` (34/34), `test_trace_completeness_live.py` (14/14), `test_clause_attribution.py`. | agent | **[GATE]** all green |
| **1.4** | Fix the stale evidence fields. The subsystem doc records that `01.F2`'s registry evidence said `unverified-import` when the gate was real — the same stale-field pattern is in `docs/systems-plan.json` for other rows. | agent | **[GATE]** `bench/test_registry_complete.py` (21) green |
| **1.5** | Run the full pre-push suite once at the new path. Hooks path survived the move (`core.hooksPath=scripts/githooks`); prove the hook itself still resolves. Never `--no-verify`. | agent | **[GATE]** `scripts/githooks/pre-push` exits 0 |

---

## Phase 2 — The transport defect that makes arbitration a no-op

**This is the single highest-leverage item in the queue.** `tools/base.py:292` builds an
`httpx.AsyncClient` **per request**, so every outbound call pays a fresh TLS handshake before the
provider is even asked. Measured 2026-10-08, same service, same cap, same payload, connection
handling the only variable:

| transport | median | inside the 400 ms cap | outcome |
|---|---|---|---|
| the project's own | **961 ms** | **0 / 8** | `unavailable` |
| one client kept alive | **232 ms** | **8 / 8** | **`decided`** |

Cold calls measured 1174 ms and 1167 ms; the same call warm measured 597, 226 and 424 ms. **About a
second of the turn budget is spent on the socket.** `01.R6`, `01.R7` and `01.R8` are configured on
and never fire.

| # | Task | Who | Gate |
|---|---|---|---|
| **2.1** | ~~**Owner decision** on which wart to carry for client lifecycle.~~ **RESOLVED — already implemented, no decision needed.** `tools/base.py:302-376` builds the loop-keyed client map the doc asked for. Verified working: same client reused within a loop, per-loop isolation, header-signature keyed. | — done | **[GATE]** passed 2026-10-10 |
| **2.2** | ~~Implement the chosen option.~~ **Already done.** Recorded so nobody re-litigates it: the blast radius (124 call sites / 58 modules) was crossed by a one-line change at the single call site `base.py:398`. | — done | **[GATE]** reuse probe green |
| **2.2b** | **New, from today's run:** wire `close_http_clients()` (`base.py:343`) into brain shutdown. It is defined and **called from nowhere**, so clients are only reclaimed by GC when a loop dies. | agent | **[GATE]** shutdown path calls it; no client outlives the server |
| **2.3** | ~~Re-measure arbitration live.~~ **CLOSED 2026-10-10.** `tools/measure_jev_arbitration.py`: **median 236 ms, 14/15 inside the 400 ms cap** (baseline: 961 ms, 0/8). Outcomes `decided` with real winners — `mushegh.brain.reminders`, `mushegh.brain.tools.calendar`. | — done | **[GATE]** passed |
| **2.3b** | **New defect, from today's run — cold start.** The *first* arbitration after the brain starts returned `unavailable` at **2002 ms**: a cold TLS handshake before the provider is reached. Every warm call then landed inside the cap. So the first turn after a restart silently gets no narrowing. Decide: warm the client at startup, or accept and document it. | agent proposes, **[OWNER]** confirms | **[GATE]** first call after start is inside the cap, or the gap is documented |
| **2.4** | Re-run `bench/test_jev_tool_arbitration.py`, `test_jev_turn_assessment.py`, `test_jev_judgment.py` and confirm no regression in the non-Jev HTTP tools that share the transport. | agent | **[GATE]** 38/38, 48/48, 26/26 unchanged |
| **2.5** | Re-run the live trace probes the transport fix makes newly meaningful — `probe_jev_live.py`, `diagnose_jev_transport.py` — and write down whether narrowing now happens on a real ambiguous turn. | agent | **[GATE]** provenance row shows a narrowed surface on at least one real turn |
| **2.6** | Serve the **D-43 seven-day bar**: seven consecutive days of real use before any `hermetic-green` claim is trusted. Wall-clock, not effort. Also closes the open question of whether arbitration's silent fallback ever hides a wrong surface in production. | time + **[OWNER]** | **[GATE]** seven dated daily runs |
| **2.7** | Re-check the interaction with **D-35**: arbitration's 400 ms cap versus the sub-300 ms laptop turn budget, now that arbitration actually fires. If both cannot hold, that is an owner decision about which budget wins. | **[OWNER]** | Recorded decision |

---

## Phase 3 — Calibration (the dominant drag, 63.5 and unmoved)

The subsystem doc's most valuable sentence: the "40.0 across the board" is **at least three
different things**, and the first two were never the same problem.

| outcome | count | what it is |
|---|---|---|
| calibrated | 3 | the limit is admitted — the scorecard is right |
| **grounded** | **4** | a live tool answered it and the scorer counted accuracy as fabrication |
| genuinely flat | 5 | no tool involved, no hedge — a real deficit |

| # | Task | Who | Gate |
|---|---|---|---|
| **3.1** | **Owner decision — relabel.** A forecast inside seven days, a lookable price, a journal the brain holds, and a dated web figure are *answerable*, and the model answers them from real data. Relabelling which prompts count as unknowable is a specification decision and was deliberately left un-taken. | **[OWNER]** | Decision recorded in `docs/systems-plan.json` + subsystem doc |
| **3.2** | Apply the relabelling **only after 3.1**, and add the model's real observed replies to `test_uncertainty.py`'s calibrated set as control cases, so the lexicon is validated against reality and the existing "flat answer" + "answerable control" cases still fail as they should. | agent → blocked by 3.1 | **[GATE]** `test_uncertainty.py` grows past 34/34 and stays green |
| **3.3** | **Owner decision — architecture.** Prompting is measured exhausted (`probe_prompt_salience.py`: as shipped 0/12, rule restated 0/12 — *identical*). Two options: (a) add a fifth `answerable: true|false` verdict to Jev's one bounded call so the turn can hedge **before** generating — this changes the one-call contract **D-92 and D-72 protect**; or (b) accept it as a known, measured deficit left on the board at 40.0. A deterministic surface-pattern pre-classifier was considered and rejected — it fires on "next Tuesday" as readily as "did it rain last Tuesday". | **[OWNER]** | Decision recorded in `DECISIONS.md` |
| **3.4** | Implement 3.3(a) if chosen — one verdict added to the existing single call, 400 ms cap unchanged, never more than one call. | agent → blocked by 3.3 | **[GATE]** `test_jev_turn_assessment.py` updated and green; live A/B |
| **3.5** | Re-measure the Calibration category live, median-5, and record the honest split: how much was instrument, how much is deficit. | agent | **[GATE]** category re-scored with the split stated, not just a total |
| **3.6** | Close goal 3 for real. `calibration()` is recorded in `turn_trace.py` and **nothing in the turn loop reads it** — the loop *measures* calibration and does not *act* on it. Whether 3.3(a) closes this depends on the verdict being consulted inside the loop, not merely produced. | agent → blocked by 3.4 | **[GATE]** `agent.py` demonstrably changes behaviour on a failed verdict |

---

## Phase 4 — Goal 1: multi-intent ≥90, and the 01.F1 gate disagreement

| | |
|---|---|
| **Bar** | Combination **≥90 / 100**, median-5 (the gate's own protocol) |
| **Last measurement** | **89.0** — one point short, 2026-10-08 (median-3 reads 92.5; do not quote the flattering sample) |
| **Shape** | `combo_time_memory` 85.0 `[79, 85, 100, 93, 85]` · `combo_web_memory` 93.0 `[40, 93, 63, 100, 93]` |

One run in five lands at **40** on the web→memory chain, and whether that run is inside the sample
decides whether the goal reads as met.

| # | Task | Who | Gate |
|---|---|---|---|
| **4.1** | ~~**Owner decision — the 01.F1 gate.**~~ **RESOLVED 2026-10-10: assert on executions.** Verified before the ruling — the gate had already been converted, and reads 10/10 (clause_routing 28/28). Its docstring records why: *"the end-to-end checks below used to assert on the fake LLM's `fired` list — that is the wrong signal... The gate's own comment is the right instruction: assert the PLAN."* The subsystem doc and registry have been corrected to match. | — done | **[GATE]** 10/10, 28/28, dated |
| **4.2** | Implement 4.1's choice and re-run. Two theories are already retired and must not be re-tried: advertised tool order is not the problem (reordering made it *worse*, 7/10), and the completion pass is not inert. | agent → blocked by 4.1 | **[GATE]** `test_clause_completion.py` + `test_clause_routing.py` green and dated |
| **4.3** | Attack the actual variance: `combo_web_memory` must land consistently, not 40-or-100. Follow the method that worked — instrument, do not guess; `tools/probe_chain_flakiness.py` exists for this. | agent | **[GATE]** spread across 5 runs visibly narrower than `[40, 93, 63, 100, 93]` |
| **4.4** | The authoritative run: `bench/behavioral_suite.py` **median-5**, live, and record `combo_time_memory` / `combo_web_memory` / `Combination` explicitly. | agent | **[GATE]** Combination ≥ 90.0 **or** a written statement that it is not met, with the cause |

---

## Phase 5 — The goals that are still unmeasured

Every row below is `not yet measured` in the subsystem doc's benchmark table. A goal with no dated
run is a claim, not a capability.

| # | Task | Who | Gate |
|---|---|---|---|
| **5.1** | **Latency (D-35, goal 7) — the METHOD is fixed; the number is not taken** | **method DONE 2026-10-11** | Neither existing gate measures M13: `test_latency_budget.py` is a one-round-trip regression tripwire, and `test_latency_guard.py` says outright *"There is no mic in CI, so this can't measure a real TTFW."* Written the protocol down instead: **[`LATENCY-METHOD.md`](LATENCY-METHOD.md)** + **`bench/latency_corpus.json`** — 30 utterances per device across seven turn classes (`reflex`, `chat`, `tool`, `compound`, `adversarial`, `long`), the conditions a number is only comparable under, p50/p95/mean/n, median of three passes, and what is excluded (reflex turns with no STT mark, and barge-in which is M12/D-49's separate budget). **Budgets are D-35's, not the method's** — the doc says so explicitly so it can never be used to argue the budget. Gated by `bench/test_latency_method.py` **30/30**, registered in the runner. **The gate earned its place on its first run**: it caught the phone batch holding 29 utterances, not 30. **Still blocked on the run itself** — the edge is parked by `MAINTENANCE`, and measuring end-to-end latency needs a live voice loop | — method done; run blocked on the owner | **[GATE]** p95 per device, dated, once the edge is unparked |
| **5.2** | **`knowledge_note_read` expectations are wrong, not the brain.** A document read legitimately takes 27.1 s and 1296 characters; the scorer grades it against a 10 s / 700-character *lookup* budget. Decide and record the correct expectation for a read-and-summarise turn. | **[OWNER]** | Documented expectation per turn shape |
| **5.3** | **D-08 self-edit end to end (goal 5).** The four conditions are implemented and the classifier is gated; what is not gated is a real self-edit through `ApprovalQueue.commit_approved()`, which needs **the owner's approval of a diff**. An agent manufacturing its own approval is exactly what D-08 forbids. | **[OWNER]** | **[GATE]** a real self-edit landed on its branch with an approval row in `audit.py`, zero migrations |
| **5.4** | **Goal 4 — ambiguity resolves to one clarifying question** | **hermetic half MEASURED 2026-10-10** | `test_intent_classes.py` **30/30** and `test_pure_chat_tools.py` **51/51**. The load-bearing checks are section [4]: *"the first ambiguous turn asks ONE question"* and *"a DIFFERENT ambiguous request still gets its own question"*, plus [3] where `'send it'`, `'delete that'` and `'can you cancel it'` are all ambiguous with nothing behind them, while a pointer *with* its object is not. Stated precisely in the doc: this proves the ASK is singular and not repeated — it does **not** prove a live turn never emits a second one. That remains a live measurement, and `probe_false_clarification.py` / `probe_clarification_drift.py` exist because the Jev outage failure mode is *questions*, not lost narrowing | — hermetic done; live half open | **[GATE]** ≤1 question per ambiguous turn, live, dated |
| **5.5** | **Goal 6 — no unsolicited speech.** The D-29 number is settled (default **3**, `.env.example` **3**, gate reads it out of `DECISIONS.md`) and the focus-block half is behavioural and green (`open=1 focus=0`). It still needs a dated end-to-end run against the running system. | agent | **[GATE]** ≤3/day, 0 inside a focus block |
| **5.6** | **`01.E3` journeys** — real gate (82 passed, 6 blocked), seven-day bar not met. Fold into the 2.6 clock. | agent + time | **[GATE]** seven days |
| **5.7** | **Re-run the whole behavioural suite** after Phases 2–4 land. Categories currently below 75: Calibration 63.5 · Proactivity 67.5 · Honesty 70.0 · Modes 71.5 · Fleet 73.0 · Autonomy 73.0 · Memory 73.2 · Combination 78.0 · Knowledge 79.0. | agent | **[GATE]** dated scorecard with per-category runs stored |

---

## Phase 6 — Production hardening

| # | Task | Who | Gate |
|---|---|---|---|
| **6.1** | ~~**Owner decision — task-store residue.**~~ **RESOLVED 2026-10-11 — the claim was stale** | Re-probed read-only with `tools/probe_task_store.py`: the live store holds **6 rows, not 307**, and **6 failed rows, not 265** — every one the identical text `look into something`, the residue of repeated failed work attempts. The store has been cleaned since the subsystem document was written, so the "307 rows / 42 open groceries" picture no longer holds and is **not** a decision for the owner to act on. If the six bother you they are six deletions in one table | — resolved; nothing to decide | Store clean, or explicitly kept |
| **6.2** | ~~**Owner decision — Notion residue.**~~ **RESOLVED 2026-10-11 — stale too** | Re-probed with `tools/probe_notion_residue.py` (read-only by design): **0 occurrences of `behavioral-suite-temp`** on the real board, not 6. The leak is fixed and the rows are gone — there is no board to clean and no deletion for an agent to refuse, so the decision this item asked for **no longer exists** | — resolved; nothing to decide | Board clean, or explicitly kept |
| **6.3** | ~~**Keep gates off the owner's live data.**~~ **DONE 2026-10-11 — enforced in the suite AND the probe** | `behavioral_suite.py` **refuses to run against the owner's state root** (`guard_live_state`): exit 2 with instructions, unless `--allow-live-state` or `MUSHEGH_STATE_DIR` points elsewhere. Verified: live root + no flag → **refused, exit 2**; sandboxed → **runs, exit 0**, session in temp; `--allow-live-state` parses. This suite is not hermetic and was never going to be — it writes learned facts to the memory store and three scenarios reach the real Notion board, which has already cost six `behavioral-suite-temp` rows and 265 failed task-store rows. **A rule living in a doc comment is not a rule; the default is now safe.** `tools/probe_chain_flakiness.py` got the same guard — it runs real turns and calls `_cleanup`, and leaving it unguarded would have repeated the "probe doesn't match the suite" bug that produced today's false zero-tools finding. Verified: probe refuses live (exit 2), runs sandboxed (exit 0, reproduces 63.0 with `['wiki_lookup','remember']`). Hermetic gates unaffected: `test_intent_classes` 30/30, `test_uncertainty` 46/46, `test_calibration_metrics` 55/55, `test_scorecard_integrity` 76/76 | — done | A suite run provably leaves no residue |
| **6.3b** | ~~**The same guard is owed to four more probes.**~~ **DONE 2026-10-11** | `probe_grounded_unknowns.py`, `probe_prompt_salience.py`, `probe_unknowable_labels.py` and `probe_tool_backed_unknowns.py` all run REAL turns and call `behavioral_suite._cleanup`, which forgets facts in the live memory store — the suite was guarded and these were not, which is precisely the "probe doesn't match the suite" shape that produced today's false zero-tools finding. All four now call `bs.guard_live_state(...)` and accept `--allow-live-state`. Verified: **each exits 2 with the refusal against the live state root**; with `MUSHEGH_STATE_DIR` set to a sandbox the guard passes and all four modules import cleanly; the live path still raises `SystemExit(2)`. Ruff clean. `probe_prompt_salience.py` needed the import hoisted into `main()` because it only imported the suite inside a `finally` block | — done | All live probes guard, or are documented live-only |
| **6.4** | ~~**Sweep the `afon` name.**~~ **DONE 2026-10-11 across 49 website files**, plus the VPS ticker and both systemd units (renamed the same day — `install*.sh` already referenced the new names, so **both VPS deploy paths were broken** until then). Every rewrite was verified against the working tree *before* it was applied: **254 `AFON_*` env vars** → `MUSHEGH_*` (preflight asserts that prefix) · **35 `afon.<module>` paths** → `mushegh.*` (`mushegh.edge.assistant`, `.brain.voice_io` import) · **8 `afon_*.sqlite`** → `mushegh_*.sqlite` (`store_path('graph')` → `mushegh_graph.sqlite`) · `afon-setup` → `mushegh-setup` (the venv ships `mushegh-setup.exe`) · `backups/afon-memory-*.zip` → `mushegh-memory-*` (`protocols/backup.py` writes the latter) · `~/.afon` → `~/.mushegh` · `.afon-browser` → `.mushegh-browser` (the directory exists) · `afon_session.json` → `mushegh_session.json` · `AfonPcAgent` → `MusheghPcAgent` (that is the task's name since today's migration) · prose `Afon` → `Mushegh`. Gates: `test_website_claims` 10/10, `test_doc_paths` 34/34, `test_doc_integrity` 8/8. Still open: the `bench/ifixai_*_afon.yaml` fixtures | — done | No unexplained `afon` outside the recorded exceptions |
| **6.4b** | **What was left is now measured: the tree HAS the bump; production is unverified** | `website/package.json` carries `next: ^14.2.35` and `website/node_modules/next` resolves to **14.2.35**, React **18.3.1** (not 19) — so D-96's patch reached the tree exactly as recorded. **Only `vercel --prod` remains unverified**, and that is the owner's deployment to make. **Still unresolved:** the site is described under `openafon.vercel.app` and the git remote is `iamvazghen/OpenWatari` — the repo has been Jarvis → Watari → Afon → Mushegh and the org was never carried along. Rewriting it to "OpenMushegh" would invent a GitHub account that may not exist, so it is left visible rather than guessed | **[OWNER]** | Repo/org naming decided once; production deploy status known |
| **6.5** | **`llm-agent-mine.tmp.py`** — a 154 KB temporary file at the repo root, currently inside the code graph as a community node. Confirm it is disposable, then remove it via the recoverable-delete path. | agent (after **[OWNER]** glance) | Gone from the graph on next refresh |
| **6.6** | **`.kilo/worktrees/disco-satin/` — investigated, NOT removed** | **Investigated 2026-10-11. The decision is now informed rather than a shrug.** It is a real git worktree — 533 files, 5.8 MB — and the rename **broke it**: `git worktree list` reports it at the old path `C:/Afon/.kilo/worktrees/disco-satin` marked **`prunable`**, and its `.git` file still points at `C:/Afon/.git/worktrees/disco-satin`, which no longer exists. The checkout is also incomplete (190 files that its own commit contains are missing). **No unmerged commits**: its `ab9aae2` is an ancestor of HEAD and `HEAD..ab9aae2` is empty. But it holds **6 untracked files main does not have**, and one matters: **`docs/NEXT-UPGRADE-DECISION.md`** — decision **P6.3 (2026-07-10)**, *"Stay on Next 14 … do NOT upgrade to Next 16 / React 19 now"*, with the `npm audit` reasoning and the feature-gating table. **That record was in the worktree only; `docs/` in main had no `*UPGRADE*` file at all. RECOVERED 2026-10-11 as **`D-96`** in `DECISIONS.md`** — *"The website stays on Next 14…"*, with the provenance stated in the entry itself and the "not redeployed at the time" caveat preserved (it has still not been verified that 14.2.35 reached production). `D-01..D-96`, no gaps. The other five (`bench/test_graph_memory.py`, `bench/test_memory_graph_learn.py`, `personality/afon.md`, `skills/afon-architecture.md`, `src/afon/`) are historical — they test or belong to the graph-memory subsystem main deleted on purpose in `3cb0258` (D-26, M04), and to the pre-rename layout | **[OWNER]** — confirm D-96's wording; the record is now safe regardless | D-96 stands; then `git worktree prune` and the worktree goes |
| **6.7** | **Decide the graph's `bench/` blindness once, on purpose.** `.graphifyignore` excludes `bench/` because it was 28% of nodes and 32% of communities, and the stated trade is *"the graph can no longer answer 'which test covers X'"*. That trade is defensible **because** tests are named after their subject — but it also means no graph query can answer "what covers the brain". If that question matters, build a full graph to a separate output rather than re-enabling it in place. | **[OWNER]** | Decision recorded in `.graphifyignore` |
| **6.8** | **Refresh the subsystem doc's stale numbers.** It still carries the "51.5 against ≥90" sentence, the 74.2/74.5/75.5 progression, and the 2026-10-08 dates. It is a living document; bring the benchmark table to the post-Phase-5 state. | agent | Doc and `systems-plan.json` agree |

---

## Definition of done

The brain is production-ready when **all** of these hold:

1. Phase 0 complete — no stale `afon` task, path, package or directory anywhere in the running system.
2. Phase 1 complete — every gate in the subsystem doc has a **dated run** on the current environment, and no registry row claims `unverified-import` or `recorded-note` evidence for work that has since been run.
3. Phase 2 complete — arbitration fires inside its cap in production, and the D-43 clock is served.
4. Phase 3 complete — calibration is either closed by architecture or recorded as an accepted, honestly-scored deficit. **Not** closed by widening a lexicon until the number moved.
5. Phase 4 complete — Combination ≥90 at median-5, and the 01.F1 gate disagreement settled by the owner, not by an agent editing a gate.
6. Phase 5 complete — goals 2, 3, 4, 5, 6, 7 each have a dated measurement.
7. Phase 6 complete — no test writes to the owner's live data without saying so.

**The bar is not the score.** A score can be raised by fixing the instrument; the charter says so
explicitly, and the subsystem document is a day-long record of what that looks like. The bar is
that every claim in the benchmark table is a **dated run of the thing it claims**, made by an
instrument that was fixed wherever it was previously lying.