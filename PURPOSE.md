# Purpose — what Afon is for, and what it must never become

**Status:** authoritative for intent. Written 2026-10-09.
**Scope:** this file is the entry point. It does not restate the charter.

This repository already documents itself thoroughly, and that is exactly why a new
developer gets lost in it. Three files answer three different questions, and reading
them in the wrong order wastes a day:

| Question | File |
|---|---|
| **What is this for, and what will it never do?** | **this file** |
| What actually exists and in what shape? | [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) |
| Why is it that way, and what was ruled out? | [`docs/DECISIONS.md`](docs/DECISIONS.md) — 94 binding decisions |
| How do I propose a change without it being rejected? | [`docs/PRINCIPLES.md`](docs/PRINCIPLES.md) |
| What is built vs. merely planned? | [`docs/systems-plan.json`](docs/systems-plan.json) + [`docs/REGISTRY-RECONCILIATION.md`](docs/REGISTRY-RECONCILIATION.md) |
| How does one subsystem work? | [`docs/subsystems/`](docs/subsystems/) — one file per subsystem, citing `D-` ids |

Read this file, then `ARCHITECTURE.md`, then only the subsystem you are touching.
`DECISIONS.md` is a reference you look *into*, not a document you read front to back.

---

## The one-paragraph version

Afon is one person's always-listening companion: a single Python brain on an always-on
host, holding all state in one SQLite database, talking to voice clients over a
WireGuard tailnet. It is **voice-first, self-hosted in state, cloud-only in inference,
and single-owner by design.** It exists so that its owner can think out loud and have
something competent, private and continuously present answer — not so that a company can
run an assistant product. Every architectural choice follows from those four words:
voice-first, self-hosted, single-owner, always-on.

---

## What Afon is for

1. **To be present without being asked.** Most of the value is proactive: noticing,
   reminding, preparing, surfacing. A companion that only answers questions is a worse
   search engine.
2. **To remember across years, not sessions.** Six memory layers exist because the point
   is continuity. An assistant that forgets is a toy.
3. **To be debuggable by one person at 2:00 AM.** See `PRINCIPLES.md` §1. This single
   filter has killed more proposed features here than any other consideration, and it is
   the reason state is one SQLite file rather than a stack of services.
4. **To be the owner's, including when the network is gone.** State is local. Inference
   is not, and that trade-off is deliberate and documented — not an aspiration to fix.

## What Afon must never become

These are not preferences. Each is enforced by a decision in the charter, and a change
that violates one is rejected on sight.

- **Not multi-tenant.** There is exactly one owner. No account system, no tenant
  scoping, no "users" table. Single-owner is a simplifying assumption worth more than
  any feature it blocks.
- **Not a thing that acts without consent.** Nothing outbound is sent without an
  owner-written approval. The consent gate is the reason this project is safe to point at
  a real inbox.
- **Not a store of what it was told to forget.** `never_store.py` exists because the
  ability to say "don't keep that" is load-bearing for a companion. Secrets, biometrics
  and vault contents stay on the owner's machines and never enter a public repo (D-57);
  a financial position is never stored (D-83).
- **Not a product.** `OpenAfon` is an open-source framework others may build on; **Afon**
  is this owner's instance. Features do not get added to serve a hypothetical user.
- **Not a model's project.** AI evaluations are advisory input; de-scoping requires the
  owner's sign-off (D-47). No decision in `DECISIONS.md` was made by a model.

---

## The doctrines a new developer will trip over first

Ordered by how expensive the mistake is. Each cites the decision; the charter has the
reasoning.

### 1. A liveness check is not a survival check

`systemctl is-active` reporting `active` proves a process is running, not that its files
exist or its config still works. On 2026-10-08 a service on the VPS reported healthy for
hours after its entire directory had been deleted, because the process held open file
descriptors. On 2026-10-09 the vault-sync unit was found to be **unstartable** — it had
been running since before a Node upgrade broke it, and nothing had restarted it.

**Verify the thing, not the symptom.** Check files exist; restart the unit and see if it
comes back.

### 2. The vault is the memory; the repo is only code

Durable memory lives in the Obsidian vault, canonical on the VPS at the path recorded in
`memory/environment.md` (that file is the private overlay and is not published). **Do not store
live project memory in this repo and do not copy vault content into it** — link to paths
instead. A local vault copy is a one-way replica that is overwritten; writing there and not
pushing loses the write silently.

**A stale note costs more than no note, because it is trusted.** If a note and the code
disagree, say so explicitly rather than quietly believing either.

### 3. Every credential has exactly one home

For Afon that home is `src/afon/config.py` (36.F5). Not a second `.env`, not a constant,
not a default argument. An executor child's environment is an **allowlist built from
nothing** — never the parent's environment minus a denylist, because a denylist of
secrets is never complete.

### 4. Refuse rather than fabricate

The anti-fabrication protocol is not politeness. A companion that invents a calendar
entry, a price or a fact it did not retrieve is worse than one that says it does not
know, because the owner will act on it. Sentinels like `FLEET_NOT_AUTHORIZED` exist so a
failure is *visible* rather than smoothed into plausible prose.

### 5. Proactivity is gated, not generous

The proactivity engine has thresholds for a reason: the failure mode of a companion is
not silence, it is becoming noise. A heartbeat bug in the old OpenClaw fleet sent ~2,500
Telegram messages in one incident. Budgets live in the database, not in a process.

---

## Boundaries: Afon, the fleet, and Jev

```
    owner
      │  speaks
      ▼
    Afon  ◄── this repository: voice, memory, identity, proactivity, consent
      │
      ├─ tools ──────────────► direct, self-served actions (the common case)
      │
      └─ delegate a JOB ─────► the Jarvis fleet   C:\Users\iamva\projects\jarvis-fleet
                                 18 specialists, 83 utilities, PREPARE-ONLY
                                 → broker + human approval is the only path to an effect
```

**Afon is the coordinator and the voice. The fleet is the staff.** Two rules at the seam:

1. **Delegation is a tool call, never a change of identity.** Afon consults; it does not
   become a specialist, and a specialist never speaks as Afon. This is in
   `src/afon/brain/agent.py` by design — see also `src/afon/brain/fleet.py`.
2. **Afon holds no fleet credentials.** It submits a job under its coordinator identity.
   The fleet holds its own resource-scoped grants.

### ⚠ Known stale: the delegation path targets a deleted system

`src/afon/brain/fleet.py` (437 lines) delegates to the OpenClaw router
`settings.openclaw_router_agent` (default **`ispir`**) over
`settings.openclaw_gateway_url`, with an `openclaw agent --agent ispir … --json` CLI
fallback over SSH. **All of that was deleted on 2026-10-08:** the gateway, the eight
agents, and the `openclaw` CLI itself.

The shipped defaults degrade safely, and that is worth stating precisely rather than
alarming a reader:

| Setting | Default | Effect |
|---|---|---|
| `openclaw_gateway_url` | `""` | the tool reports the bridge is not configured |
| `fleet_authorized` | `False` | consulting needs a per-session OK or `AFON_FLEET_AUTHORIZED` |
| `openclaw_delegation_enabled` | `True` | the `delegate_to_fleet` tool is still advertised |

So the open-source default is fine. **The risk is deployment-local:** if this owner's
`.env` sets `openclaw_gateway_url` (and especially `AFON_FLEET_AUTHORIZED=true`), that
URL now points at nothing, and `delegate_to_fleet` will fail at call time while
`agent.py` still offers to "consult the OpenClaw fleet" — the fabrication failure
doctrine 4 exists to prevent. The `.env` was deliberately not read when writing this
file; **check it.**

Independently stale regardless of `.env`: `vault.py`'s docstring says the fleet
(`ispir`) writes the vault on the VPS. It does not any more — vault writes go to the
canonical VPS path recorded in `memory/environment.md` directly. `web.py` likewise describes
`delegate_to_fleet` as a live route.

**Until `fleet.py` is repointed at the new fleet's admission API** (and the target
renamed off `ispir`), the honest states are: blank the gateway URL, or return an explicit
unavailable sentinel. Do not leave it advertising the old path.

The stale fleet memory docs were moved off the VPS to
`~/backups/stale-fleet-memory/` on 2026-10-09 for this reason — a memory file telling
Afon it has eight specialists on call is actively harmful, not merely out of date.

### Where Jev fits

[`jev-governor`](https://github.com/iamvazghen/jev-governor) is the installable
decision layer: a calibrated System One model chooses the next action, and the generative
model is constrained to that choice **and verified against it**. Afon's own evaluation of
Jev as a *runtime engine* was recorded as declined
([`docs/JEV-REPORT.md`](docs/JEV-REPORT.md)); it is a governor, not a brain. The two
roles are separate and both can be true.

---

## Current state, honestly

- The working tree has uncommitted changes across `bench/` and `TODO.md`; `master` is
  behind the local work.
- **Four commits exist only as patch files**, rescued from a deleted VPS workspace before
  it was destroyed: mic pinned by *name* not index (the Bluetooth-reconnect `-9998` fix),
  clause-routing time patterns, `test_clause_routing.py`, and the B4 gate. They are at
  `C:\Users\iamva\fleet-archive-20261008\fleet-rescue-20261008\OpenWatari-unpushed\` and
  are **not yet applied** — the clone they came from was shallow, so they are
  `git format-patch` output rather than a bundle.
- `jarvis-brain` on the VPS is **inactive** and has been since before the 2026-10-08
  cleanse. Its 10,174 files are intact. This is unrelated to the fleet removal and is its
  own open problem.
- `docs/REGISTRY-RECONCILIATION.md` is the authoritative list of places the registry and
  the charter disagree. Trust it over any individual subsystem doc.

---

## The standard this repo is held to

Two questions, asked of every change:

1. **If it fails at 2:00 AM, can one person debug it in 90 seconds** with `journalctl`,
   `sqlite3` and `curl`?
2. **If the model is wrong here, what happens?** If the answer is "something irreversible
   and outbound", it needs a consent gate, not a better prompt.
