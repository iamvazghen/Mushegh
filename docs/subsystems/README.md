# subsystems/ — one document per system

Fifty documents, one per registry entry in `docs/systems-plan.json`. Written
2026-10-03 so that every system has a stated purpose, a real structure, goals that
can be checked, and benchmarks.

**Read [../DECISIONS.md](../DECISIONS.md) first.** Each document cites decision IDs
(`D-07`, `D-29`) rather than restating them, so the charter stays the single place
where a decision is changed.

---

## The shape of a system document

Every file follows this skeleton. Consistency is the point: fifty documents that look
alike can be scanned, diffed, and checked by a script.

```markdown
# S07 — Session & Context Management

> **One line:** what this system is for, in the owner's terms.
> **Status:** built, not well structured · **Registry:** S07 · 3/3 floor, 3/3 raise, 0/1 elite
> **Milestones:** M19, M24, M31 · **Decisions:** D-23, D-40

## Purpose
Why this exists, what it refuses to do, and what breaks for the owner if it is absent.

## Structure
Where the code is (real paths only), what the data flow is, and which process owns it.

## Goals
Each goal is a capability, not a task. Where a goal carries a number, the number is
repeated in the benchmark so the two cannot drift.

## Benchmarks
B-tier from ../EVIDENCE.md, a threshold, a method, and the last measurement with its
date — or `not yet measured`, honestly.

## Failure modes
What breaks, what it does instead, and what the owner would see.

## Open questions
Three at most. A doc with no open questions is a doc that stopped thinking.
```

### Rules

1. **Real paths only.** Every `src/afon/...` path cited must exist. Verify before
   citing — a phantom path in a subsystem doc is worse than no path, because it will
   be trusted.
2. **Decisions, not vibes.** Where the charter constrains a system, cite the `D-nn`.
3. **A goal without a benchmark must say so.** "No benchmark yet — needs a live drill"
   is an acceptable line. A goal with a benchmark that cannot fail is decoration.
4. **Status is copied from the registry**, not invented. If the registry is stale, say
   so in the doc rather than papering over it.
5. **Deletion is a valid outcome.** Four of these systems should not exist
   (S15, S46, S47, S49) and one has a decided deletion that is **not yet executed** (S24 —
   the relation layer is still live in code; see `../REGISTRY-RECONCILIATION.md` §2c).
   Their documents record why, so nobody re-adds them by accident.

---

## The fifty

| # | System | Status (2026-10-03) | Charter effect |
|---|---|---|---|
| S01 | [Brain / Core Intelligence](01-brain-core-intelligence.md) | built, not well structured | M31 · D-08, D-16, D-35, D-44 |
| S02 | [LLM Integration](02-llm-integration.md) | complete for now | D-17 |
| S03 | [Tool Utilization](03-tool-utilization.md) | complete for now | M27 · D-04, D-06, D-07, D-13 |
| S04 | [Device Control](04-device-control.md) | complete for now | M36 · D-13, D-41 |
| S05 | [Browser Control](05-browser-control.md) | complete for now | D-07 |
| S06 | [Document Creation](06-document-creation.md) | half-built | — |
| S07 | [Session & Context](07-session-and-context.md) | built, not well structured | M19, M31, M34 · D-23, D-40 |
| S08 | [Voice Enrollment](08-voice-enrollment.md) | built, measurably weak | **M09 — the gate** |
| S09 | [Face Enrollment](09-face-enrollment.md) | built, never run on this backend | M10 · D-38 |
| S10 | [Speaker Recognition](10-speaker-recognition.md) | built, not well structured | M11 · D-15 |
| S11 | [Face Recognition](11-face-recognition.md) | built, not well structured | D-38 |
| S12 | [Multi-Device Coordination](12-multi-device-coordination.md) | built, not well structured | M34 · D-36, D-39, D-40 |
| S13 | [Notification Management](13-notification-management.md) | built, not well structured | M20, M23, M38 · D-07, D-29 |
| S14 | [Proactivity Engine](14-proactivity-engine.md) | complete for now | M23 · D-29, D-30, D-31 |
| S15 | [Recommendation Engine](15-recommendation-engine.md) | **removed by decision 2026-10-03** | D-27 |
| S16 | [Task Queue & Execution](16-task-queue-and-execution.md) | built, not well structured | M21 · D-07 |
| S17 | [Morning Brief](17-morning-brief.md) | complete for now | M24 · D-33 |
| S18 | [Microphone & Speaker](18-microphone-and-speaker.md) | complete for now | M12–M16 · D-17, D-35, D-49, D-56 |
| S19 | [Composio / MCP Integration](19-composio-mcp-integration.md) | built, not well structured | D-62 |
| S20 | [External API Integrations](20-external-api-integrations.md) | dark | **M07** |
| S21 | [Personal Time Management](21-personal-time-management.md) | built, not well structured | M22 · D-62 |
| S22 | [System Recoverability](22-system-recoverability.md) | complete for now | M36, M39 · D-41, D-55 |
| S23 | [24/7 Reachability](23-24-7-reachability.md) | complete, parked by design | M37 |
| S24 | [Knowledge & World Model](24-knowledge-and-world-model.md) | **decided; the deletion is not done yet (M04)** | D-26 |
| S25 | [Personality & Interaction Style](25-personality-and-style.md) | complete for now | M17 · D-20, D-50 |
| S26 | [Multi-Modal Perception](26-multi-modal-perception.md) | built, not well structured | D-38, D-61 · R2/R3 deferred |
| S27 | [Contextual Awareness](27-contextual-awareness.md) | built, not well structured | M35, M38 · D-37, D-61 |
| S28 | [Environmental / IoT Orchestration](28-iot-orchestration.md) | dark | **M20** |
| S29 | [Automation & Workflow](29-automation-and-workflow.md) | built, not well structured | M28 · D-09 |
| S30 | [Persistent Memory](30-persistent-memory.md) | built | M29, M30, M32 · D-02, D-21, D-22, D-25 |
| S31 | [Self-Monitoring & Healing](31-self-monitoring-and-healing.md) | complete for now | trend detection |
| S32 | [Redundancy & Failover](32-redundancy-and-failover.md) | partially missing | deferred · open decision |
| S33 | [Goal & Project Management](33-goal-and-project-management.md) | built, not well structured | M19, M21, M25 |
| S34 | [Health & Wellness](34-health-and-wellness.md) | half-built, no data source | **M07 — decide or delete** |
| S35 | [Crisis & Emergency Response](35-crisis-and-emergency.md) | half-built | **M07** · D-11 |
| S36 | [Security & Access Control](36-security-and-access-control.md) | complete for now | M27, M28 · D-07, D-09, D-13 |
| S37 | [Privacy & Data Governance](37-privacy-and-data-governance.md) | half-built | M27 · D-24 |
| S38 | [Communication Hub](38-communication-hub.md) | built, not well structured | D-13, D-62 |
| S39 | [Multi-Agent Delegation](39-multi-agent-delegation.md) | built, thin | D-05, D-08 |
| S40 | [Financial & Asset Management](40-financial-and-asset.md) | narrowed by decision 2026-10-03 | D-12 |
| S41 | [Research & Synthesis](41-research-and-synthesis.md) | half-built | D-34, D-58 |
| S42 | [Media & Entertainment](42-media-and-entertainment.md) | built, not well structured | — |
| S43 | [Presence & Continuity](43-presence-and-continuity.md) | half-built | M34, M35 · D-37, D-38, D-40 |
| S44 | [Ethical Reasoning & Alignment](44-ethics-and-alignment.md) | complete for now | M26 · D-10 |
| S45 | [Explainability & Transparency](45-explainability.md) | complete for now | M30 · D-25, D-52 |
| S46 | [Predictive Analytics](46-predictive-analytics.md) | **removed by decision** | D-28 |
| S47 | [Inventory & Resource Management](47-inventory-and-resources.md) | **removed by decision** | D-42, Q25 |
| S48 | [Collaborative Multi-Agent](48-collaborative-multi-agent.md) | built, thin | deferred |
| S49 | [Fabrication & Manufacturing](49-fabrication-and-manufacturing.md) | **dropped** | D-48 |
| S50 | [Legacy Continuity](50-legacy-continuity.md) | half-built, dark | **M07** · D-54 |

---

## Three things this folder knows that the dashboard does not
1. **A `cancelled` or `deferred` status is a decision, not an omission.** Since
   2026-10-03 the registry has carried both states, and a cancellation is refused by
   `scripts/systems_plan.py` unless it names the decision in
   [`../DECISIONS.md`](../DECISIONS.md). Five of the fifty documents below exist to record
   work that should not be built (S15, S24, S46, S47, S49); the dashboard says so, and
   these files say why, so nobody re-adds them by accident.
2. **A dark system is not a finished one.** S20, S28, S34, S35 and S50 are code-complete
   and control nothing, or control nothing yet. Their documents say which, because
   "complete for now" in a status column is how a credential never gets installed (D-46).
3. **A device in the house is not an integrated device.** 28 boxes are planned in
   [`../HARDWARE.md`](../HARDWARE.md), and a system with hardware pointed at it is still
   `not yet measured` until the sensor is in the wall. The mmWave sensors change what S43
   can claim, the smoke detectors change what S35 must have written down first, and the
   smart lock is the one device Afon may read and never actuate (D-65).

## Adding or removing a system

A new system needs an independent daemon process or a distinct security boundary
(D-42). Otherwise it is a handler in an existing domain, and the correct action is to
extend that domain's document instead of creating a fifty-first file.
