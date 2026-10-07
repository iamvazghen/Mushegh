# docs/ — the documentation map

Written 2026-10-03. Start here.

| Document | What it is | Authority |
|---|---|---|
| **[DECISIONS.md](DECISIONS.md)** | The charter. **D-01 to D-90**, no gaps — each with its rationale, what it invalidates and what would falsify it. The largest groups are the 2026-10-03 owner interview, the hardware inventory, the Jev arbitration decision and the 2026-10-06 external-executor and toolchain direction (D-79–D-90). The previous wording gave a tally that did not add up to the file, which is why this one counts the range instead | **Authoritative for what will be built** |
| **[PRINCIPLES.md](PRINCIPLES.md)** | Ten judgement rules for proposing anything new | Authoritative for process |
| **[ARCHITECTURE.md](ARCHITECTURE.md)** | What actually exists, and a table of what the JARVIS blueprint proposed and what replaced it | Authoritative for the present |
| **[ROADMAP.md](ROADMAP.md)** | 40 milestones, benchmarked, sized against 8–10 h/week, with the acceptance scenario for a good Tuesday | **The planning surface** |
| **[EXTERNAL-EXECUTORS.md](EXTERNAL-EXECUTORS.md)** | The 2026-10-06 survey behind D-79–D-86: which SDK or open-source project carries each delegated capability, and the three doors a capability may enter through | Reference — research, not authority |
| **[HARDWARE.md](HARDWARE.md)** | The 28-device integration plan: placement, phase order, and the 14 places the hardware contradicts the charter | **Sequencing authority for hardware** |
| **[EVIDENCE.md](EVIDENCE.md)** | The benchmark ladder (B1–B5) and the bar for calling something done | Authoritative for proof |
| **[subsystems/](subsystems/README.md)** | One document per system: description, structure, goals, benchmarks | Reference |
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
