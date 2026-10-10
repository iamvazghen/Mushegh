# docs/ — the documentation map

Written 2026-10-03. Start here.

| Document | What it is | Authority |
|---|---|---|
| **[DECISIONS.md](DECISIONS.md)** | The charter. **D-01 to D-95**, no gaps — each with its rationale, what it invalidates and what would falsify it. The largest groups are the 2026-10-03 owner interview, the hardware inventory, the Jev arbitration decision and the 2026-10-06 external-executor and toolchain direction (D-79–D-91). D-92 to D-95 are the 2026-10-07 turn architecture, the fifty-subsystem re-review, the Bookroom packaging change, and the 2026-10-09 secrets ordering. The previous wording gave a tally that did not add up to the file, which is why this one counts the range instead | **Authoritative for what will be built** |
| **[PRINCIPLES.md](PRINCIPLES.md)** | Ten judgement rules for proposing anything new | Authoritative for process |
| **[ARCHITECTURE.md](ARCHITECTURE.md)** | What actually exists, and a table of what the JARVIS blueprint proposed and what replaced it | Authoritative for the present |
| **[ROADMAP.md](ROADMAP.md)** | 40 milestones, benchmarked, sized against 8–10 h/week, with the acceptance scenario for a good Tuesday | **The planning surface** |
| **[EXTERNAL-EXECUTORS.md](EXTERNAL-EXECUTORS.md)** | The 2026-10-06 survey behind D-79–D-86: which SDK or open-source project carries each delegated capability, and the three doors a capability may enter through. §6 was corrected on 2026-10-07: the Bookroom external-application blocker is withdrawn (D-94) | Reference — research, not authority |
| **[INTEGRATIONS.md](INTEGRATIONS.md)** | The 2026-10-07 re-review of all fifty subsystems: 11 base additions, 1 significant improvement, 6 already covered, and what was declined and why. Every repo and every cited path verified before it was written down | Reference — evidence behind D-92 to D-94 |
| **[FULL-UTILITY-MASTER-LIST.md](FULL-UTILITY-MASTER-LIST.md)** | What Afon, Rubo, Claude Code, MiniMax Code and MiniMax Design can each do — ~496 capabilities, counted from the live registry and the source trees, not recalled | Reference — the capability surface |
| **[INTEGRATION-MATRIX.md](INTEGRATION-MATRIX.md)** | For each of those capabilities: the verdict (already implemented / integrate / build / impossible) and the project. **§0 is the corrections list** — 13 candidate repos did not exist, 7 more were cited under the wrong owner, and 6 licences were wrong. Read §0 before trusting any row | Reference — evidence, and the record of what was wrong |
| **[OPEN-SOURCE-INTEGRATIONS.md](OPEN-SOURCE-INTEGRATIONS.md)** | The build-vs-integrate rules and the candidate evaluation behind the matrix | Reference — research, not authority |
| **[UTILITY-INTEGRATION-MAP.md](UTILITY-INTEGRATION-MAP.md)** | The same survey in product-shaped form: what each product should adopt, borrow as a pattern, or decline | Reference |
| **[HARDWARE.md](HARDWARE.md)** | The 28-device integration plan: placement, phase order, and the 14 places the hardware contradicts the charter | **Sequencing authority for hardware** |
| **[EVIDENCE.md](EVIDENCE.md)** | The benchmark ladder (B1–B5) and the bar for calling something done | Authoritative for proof |
| **[subsystems/](subsystems/README.md)** | One document per system: description, structure, goals, benchmarks | Reference |
| **[S01-STATUS.md](S01-STATUS.md)** | **Orientation for the current subsystem, 2026-10-10**: what is green, the ten defects found and fixed, why the behavioural number is currently not quotable, and what is blocked on whom. Start here before touching 01.E1 or 01.E2 | Reference — read first |
| **[REGISTRY-RECONCILIATION.md](REGISTRY-RECONCILIATION.md)** | What the 2026-10-03 charter changed in `systems-plan.json`: 29 cancelled tasks, 6 deferred, 9 rewritten statuses, and the owner decisions still open | Record of an applied change |
| **[SYSTEMS.md](SYSTEMS.md)** | The generated execution dashboard | Generated — never hand-edit |
| **[systems-plan.json](systems-plan.json)** | The registry: 50 systems × 403 tasks with gates and evidence | **Authoritative for what is built and proven** |
| [SYSTEMS-DETAILS.md](SYSTEMS-DETAILS.md) | The frozen 341 KB rationale archive the registry cites by line number | Historical. Do not rewrite — evidence records point into it |
| [JEV-REPORT.md](JEV-REPORT.md) | 999 model judgements, four rounds. **Advisory input only** (D-47) | Historical |
| [HUD-SPATIAL.md](HUD-SPATIAL.md) | The React HUD client: status, canvases, remaining integration | Reference |
| [home-assistant.md](home-assistant.md) | Home Assistant setup and verification. Cited by `src/afon/brain/tools/smarthome.py` | Operational |
| [MASTER-PLAN.md](MASTER-PLAN.md) | The superseded 2026-06-24 snapshot. Kept only so old citations resolve | Superseded |
| [S30-MIGRATION.md](S30-MIGRATION.md) | **Cancellation record**, not a runbook (D-02) | Historical |

---

## The four things to read, in order

1. **[DECISIONS.md](DECISIONS.md)** — what this system will and will never do.
2. **[ARCHITECTURE.md](ARCHITECTURE.md)** — what is actually running.
3. **[ROADMAP.md](ROADMAP.md)** — what happens next, and what "done" means for each.
4. **[subsystems/](subsystems/README.md)** — the per-system detail, if you need it.

## The three questions every document here answers

- **What is this for?** A purpose you could repeat to a stranger.
- **How will I know it works?** A benchmark with a threshold, a method, and a date.
- **What did it cost, and what did it refuse to do?** The deletions matter as much as
  the code.

## Ground rules for writing here

- **Cite only paths that exist.** `bench/test_doc_paths.py` enforces this for every
  file in this directory, and it exists because a roadmap once asserted a script that
  had never existed and the claim propagated to four places before anyone noticed.
- **A number needs a method and a date.** "Under 300 ms" measured how, on what day, over
  how many runs? See [EVIDENCE.md](EVIDENCE.md).
- **A decision without a decision ID is an opinion.** Cite `D-nn` from
  [DECISIONS.md](DECISIONS.md).
- **Generated means generated.** [SYSTEMS.md](SYSTEMS.md) comes from
  `systems-plan.json` via `scripts/systems_plan.py`; `docs/systems-plan.json` is
  authoritative for execution state. Edit the registry, then render.
- **Deletion is a legitimate outcome.** A subsystem doc may end in "this should not
  exist", and four of them do.
