# The fleet — eighteen specialists, eighty-three domains, and no team lead

The thing to unlearn first: **there is no router.** Mushegh used to brief one team lead, `ispir`,
who chose a specialist himself. That agent does not exist — the eight-agent fleet it led was
deleted on 2026-10-08 — and the eighteen-agent fleet that replaced it has no router at all. Each
agent owns a named slice of the eighty-three domains, **exclusively: one owner per domain**. So the
choice of specialist is yours, and getting it right is the job.

`ispir` does not resolve. Neither do `personal` or `business`. `roster.resolve()` refuses an
unknown name rather than sending the brief to the nearest desk, because "the nearest thing" is how
a legal question reaches the media agent.

## Who does what

| Agent | Domain | Some of what they own |
|---|---|---|
| **goharik** | Inbox | triage, reply drafting, ghosting/follow-up, cold-outreach gatekeeping |
| **felo** | Editorial and performance | content frameworks, long-form scripts, hooks and titles, repurposing, editorial calendar |
| **arsen** | Media production | vertical video clipping, ASR timestamps, FFmpeg render QC |
| **lika** | Projects and meeting execution | task sync, stalled-task radar, async standups, delivery risk |
| **tatev** | Personal operations | brain-dump to GTD, energy-based scheduling, task batching, end-of-day rollover |
| **tamara** | Business and vendor operations | SOP synthesis, pre-call dossiers, vendor ToS diffs, SLA |
| **hrach** | Sales and partnerships | buying-signal radar, B2B lead enrichment, event intelligence, partner relations |
| **sergey** | Customer support and onboarding | L1 concierge, onboarding orchestration, churn risk, FAQ upkeep |
| **gagas** | Community | anti-spam/anti-raid, open-source contribution tracking |
| **zara** | Security analysis | attack-surface scanning, phishing detonation, credential-breach surveillance, honeypots |
| **ishkhan** | External intelligence | competitor radar, procurement and grants, brand impersonation, regulatory radar |
| **margo** | Infrastructure operations | daemon watchdog, log anomaly triage, backup verification, TLS/domain expiry |
| **kamo** | Knowledge and research | knowledge-base curation, deep research and synthesis, decision-log archiving |
| **tigran** | Calendar and travel | meeting prep and debrief, travel logistics, cadence, time zones |
| **yana** | People operations | pulse and sentiment, on/offboarding checklists, handbook diffs |
| **mane** | Legal obligations | contract milestones, NDA and signature workflow, filing calendar |
| **davit** | Reputation monitoring | mention and sentiment stream, crisis early warning |
| **arin** | Independent quality reviewer | reviews the others' work; owns no domain, on purpose |

The table above is prose for you. The **authority** is `roster.agents()`, loaded from
`fleet18.json`, which is generated from the vault's `20-Agents/fleet18.json` — what the agents
themselves read. `roster.domains('<agent>')` gives you one agent's exact domain titles when a brief
needs them; `roster.drift()` says when the packaged copy and the vault disagree. If this file and
the JSON ever differ, **the JSON wins.**

## Choosing

- The domain table decides. Pick the agent whose domain **names** the work.
- If two could own it, pick the one whose domain names it more specifically. Security scanning is
  zara's even when it arrives as an infrastructure question.
- `roster.suggest(text)` is a bag-of-words prefilter over domains and utility titles. Use it as a
  second opinion, not as the decision.
- **Arin is the reviewer, not a worker.** Send him finished work to check, never work to do.

## How you reach them — two transports, one interface

`fleet.ask(agent, task)` is the whole interface. Behind it:

- **Nine agents speak A2A** (Agent2Agent 1.0) on the OpenClaw gateway: arsen, sergey, gagas, zara,
  margo, tigran, mane, davit, arin. One bearer token per agent, because the token *is* the peer
  identity — the gateway maps peer `jarvis.<agent>` to that agent through its own bindings, so
  addressing is verified server-side and a wrong token is a 401 rather than a misroute.
- **Nine run as Hermes profiles**: goharik, felo, lika, tatev, tamara, hrach, ishkhan, kamo, yana.
  Hermes ships no A2A server, so these are reached with its one-shot CLI against the profile home
  that holds that agent's charter. Honest rather than dressed up as A2A.

`roster.transport(name)` tells you which, so no caller keeps a list.

**Why this transport closes the consent question for free:** an A2A reply comes back over the HTTP
response to Mushegh. It is not a channel delivery, so an agent answering you **cannot message
Vazghen as a side effect** — including inside quiet hours. The gateway also refuses a slash command
from a peer before any model sees it. The line that the fleet is a tool and never the assistant is
carried by the transport now, not by a prompt asking nicely.

## Briefing one

The agent sees **only the text you send**. Not your context, not the conversation, not the vault.
So the brief carries everything:

> Zara: our Hetzner box 100.1.2.3 exposes SSH on 22 and nothing else should be reachable from
> outside the tailnet. Check the external attack surface and tell me what is listening that
> shouldn't be. If you need credentials, say which — don't guess. Answer as a short list, worst
> first.

That names the agent, the subject, the boundary, the refusal path, and the shape of a good answer.

Then:

- **One agent per brief.** If the work spans two domains, that is two briefs, and say so.
- **Re-voice the answer.** You remain Mushegh. Never adopt an agent's persona or read their
  transcript out verbatim.
- **A stall is not an outage.** If an agent took the work and went quiet you get `FleetStalled`,
  the work comes back to you, and it is **not** re-sent — it may still be running over there, and
  a non-idempotent task done twice is the failure that type exists to prevent. Tell him it stalled,
  and do not re-send without being told to.
- **`fleet_authorized` gates a consult.** The fleet touches shared infrastructure; if it is not
  armed this session, tell him you can consult them and ask.

## Checking they are alive

`fleet.status()` pings all eighteen by real round trip — each agent is asked to say its own name
back. That is deliberate: a gateway being up proves a process runs, not that this agent's config
resolves, its model answers, or its token maps to it. **A liveness check is not a survival check**,
and this fleet has twice reported a healthy unit whose files were already deleted.

    uv run python bench/test_a2a_transport.py --live
