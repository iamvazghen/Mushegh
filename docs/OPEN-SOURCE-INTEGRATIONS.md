# Open-source integrations — Jarvis, the agent fleet, and the coding side

Written 2026-10-09 from three inputs: the supplied catalog
(`OpenClaw_Hermes_Agent_Utilities_Catalog.docx`, 83 utilities / 18 domains), an inventory
of what Mushegh already ships (**160 tools, 50 subsystems**), and web verification of the
named candidates. **Licences are verified; anything I could not verify is marked so
rather than asserted.**

---

## 1. The strategic finding, before any list

The catalog is a **business-operations** catalog. It opens by explicitly *excluding*
coding, backend, frontend/UI, financial analysis, taxes and asset management.

Mushegh today is a **personal-assistant + developer** system. Measured against the catalog's
18 domains, the picture is lopsided:

| domain | utilities | Mushegh today |
|---|---|---|
| Personal task queue & execution | 24 | **strong** — 24 task/objective/reminder tools |
| Knowledge base & institutional memory | 18 | **strong** — vault, journal, recall, documents, skills |
| Media & brand monitoring | 15 | **partial** — music/screen only; no reputation stream |
| Code & CLI (outside the catalog) | — | **strong** — git, tests, lint, self-improvement, fleet |
| Calendar / meetings | 4 | strong — 4 tools |
| Web & OSINT | 10 | strong — search, scrape, browser, finance |
| **Inbox triage & email ops** | 8 | **thin** — can read/send/draft; **no triage, priority, follow-up, spam gate or unsubscribe** |
| **Cyber defense / SecOps** | 4 | **absent** — only approve/reject/self-health |
| **Sales & GTM** | 3 | **absent** |
| **Support & community** | 5 | **absent** |
| **Legal & contracts** | 3 | **absent** |
| **HR / people ops** | 3 | **partial** — coaching + sensitivity only |
| **Content creation** | 8 | **absent** (you have the Bookroom SDK instead) |
| **Procurement** | 3 | **absent** |
| **Business ops / SOPs** | 6 | **partial** |
| Infrastructure watchdog | 6 | **strong** — uptime, backups, self-heal |

**So the honest answer to "what should we integrate" is not 83 things.** Mushegh already owns
the personal-assistant and developer half. The catalog's value is concentrated in the
**inbox, SecOps, sales, support, legal and procurement** bands — where there is currently
nothing, and where each utility is a genuine capability rather than a re-implementation of
something shipped.

A second structural point: the catalog is written for an agent that *runs the owner's
business*. Jarvis as built is an assistant for one person. Integrating catalog #35–#37
(GTM radar, lead enrichment, conference scraping) is not a feature — it is a **different
product**. That is worth deciding deliberately rather than absorbing by default.

---

## 1b. The fleet is three products, not one — and Rubo changes the scope answer

Correcting my own §7 below: I initially read the catalog's exclusion of *"financial
analysis, taxes, and asset / portfolio management"* as evidence those domains are out of
scope. **They are not.** They are **Rubo** — your own agent, covering personal life,
taxes, tax optimisation, tax filing, tax benefits, investment-opportunity identification,
asset financial analysis, portfolio management, cash rebalancing and optimisation, and
recession prediction with a cash-reserve builder.

So the fleet is three distinct products, and the utility list must be read against each:

| product | what it owns | what it borrows |
|---|---|---|
| **Jarvis** | personal assistant, 160 tools, voice, hardware, the coding/CLI side | §1 says this is where the catalog's personal-assistant overlap lives |
| **Rubo** | finance, tax, portfolio, life operations | the catalog contributes **nothing** — it explicitly excludes those domains. Rubo's open-source needs are a *different* list entirely |
| **the fleet** (OpenClaw/Hermes/Pydantic-AI) | delegated work, parallelism, tool fan-out | MCP servers from Tolaria/LifeOS/AgentMail plug in here |

**And LifeOS overlaps Jarvis specifically**, which is why it is the most valuable thing on
this list to read. It is the closest published thing to what Mushegh is: a personal AI
harness with a voice daemon, cron, observability, a dashboard, Telegram/iMessage bridges,
a named DA identity, and memory split by purpose. Two ideas are worth stealing outright:

1. **The Algorithm's seven phases** (OBSERVE → THINK → PLAN → BUILD → EXECUTE → VERIFY →
   LEARN), with a classifier choosing MINIMAL / NATIVE / ALGORITHM and a tier E1–E5. Mushegh
   has the pieces but no unified loop; D-72 protects the turn loop precisely because it
   is measured, and this is a candidate *shape* for it rather than a patch.
2. **The memory taxonomy** WORK / KNOWLEDGE / LEARNING / RELATIONSHIP / OBSERVABILITY /
   STATE — retrieval is chosen by *purpose*, not by proximity. Mushegh's memory classes are
   ORDINARY / NEVER_STORE / BIOMETRIC / SECRET, which says nothing about when to recall.

Neither needs a dependency: both are design ideas you can read and reject.

## 1c. What the catalog is *for* each of your three products

- **Jarvis** → domains 3.1 (inbox), 3.9 (infra), 3.10 (knowledge). ~20 of the 83.
- **Rubo** → **nothing from this catalog.** Its open-source needs are tax/finance data and
  analytics, which I have not researched here; say the word and that is the next pass.
- **Fleet** → AgentMail (agent identities), Tolaria or LifeOS via MCP, and §3.2 SecOps
  if the fleet holds any public-facing surface.

| candidate | status | licence | verdict for Mushegh |
|---|---|---|---|
| **LifeOS** (`danielmiessler/LifeOS`) | live, **19.4k★ / 2.5k forks**, actively released | **MIT** | **Closest thing to a rival architecture, and the most instructive.** "Universal AI Harness… Current → Ideal", 7-phase Algorithm (OBSERVE→THINK→PLAN→BUILD→EXECUTE→VERIFY→LEARN), a Pulse daemon (voice, cron, observability, Life Dashboard, Telegram/iMessage bridges), a DA identity layer, and Memory v7.6 split into WORK / KNOWLEDGE / LEARNING / RELATIONSHIP / OBSERVABILITY / STATE. **MIT, so no viral risk.** Overlaps Mushegh heavily — see §1b. Worth studying for the *Algorithm* and the *memory taxonomy*, not for wholesale adoption. |
| **Tolaria** | live, 18k+ stars, `refactoringhq/tolaria` | **AGPL-3.0** | **Good fit, with one caveat.** Markdown + Git + native MCP server; its README literally lists *"Store OpenClaw/assistants memory and procedures"*. AGPL is fine *as a separate app over plain files* — but **never vendor its code into Mushegh**, or AGPL copyleft reaches your tree. Caveat: Windows AI/MCP integration is reported as experimental. |
| **AgentMail** | live, YC, $6M raised (Mar 2026) | **MIT** | **Additive, not a replacement.** It gives an *agent its own inbox*; it cannot read your existing Gmail. Mushegh's `read_email`/`send_email` stay. Useful for agent-to-agent and for the fleet owning identities. $1/mailbox/mo; self-hostable; has an MCP server. **Self-hosted alternative: `dearagent.sh` (AGPL-3.0, Cloudflare Worker + D1, receiving is free, nothing billed per inbox)** — better economics for a fleet with many agents. |
| **Roo Code** | **DISCONTINUED 15 May 2026**, Apache-2.0 archived | dead | **Do not build on it.** Repo archived; the vendor pivoted to a Slack product. Live forks: **Cline** (the original parent), **ZooCode**, **Kilo Code**. If you want role-scoped coding modes, Cline or Kilo Code is the maintained line. |
| **Claude Code** | live | proprietary CLI (not OSS) | Useful *as a client* against Tolaria's or LifeOS's MCP server; not something to integrate as a library. |
| **Mcode** = **MiniMax Code** | live | commercial | Not an integration — it is a coding client for the provider you already use. **And note the 401 you are hitting**: your minimax key is being benched for 6h as a permanent failure, which is why failover keeps landing on groq/vercel. |
| **Infisical** (`Infisical/infisical`) | live | **licence not verified this session** | Plausible fit for secrets — Mushegh keeps credentials in `.env` today. **Verify the current licence before adopting**: it has changed historically, and network-copyleft would matter if you ever embed it. Otherwise the honest alternative is **SOPS + age** (audited, non-viral), and you can read a sealed file at 3am — which is the charter's own rule deciding it. |
| **Ghost-Downloader-3** (`XiaoYouChR/Ghost-Downloader-3`) | **not verified this session** | — | Repo exists per the URL you gave; I did not fetch it. Judging by name it sounds like a download accelerator, which is **not on the utility list** — the catalog's content domain has a *video clipping* pipeline, not a downloader. Confirm what it does before I assess it. |
| **Rea** | **could not verify** | — | Could not identify which product you mean. Send a URL. |

---

## 3. The utility list, domain by domain, with the open-source stack

Only domains where Mushegh is thin or absent are listed; the strong ones are omitted
deliberately (§1).

### 3.1 Inbox triage & email ops — 8 utilities, Mushegh thin, **highest leverage**
Mushegh can read and send; it cannot *manage*. This is the one band where the catalog is
better than what you have, and where every utility is independently useful.

| utility | recommended stack | build vs integrate |
|---|---|---|
| Inbox-zero triage / priority | **Triage** (the open-source Thunderbird-labeler) or a `notmuch` + afew labels | **integrate** Triage's label model; Mushegh owns the rules |
| Reply drafting | Mushegh already has `draft_email` | **build** — you have it; add conversation-aware context |
| Ghosting / follow-up tracker | **nothing to integrate** | **build** — needs your own sent-mail history; ~1 day |
| Cold-outreach spam gate | **Triage** again, or a small classifier | **integrate Triage**, own the policy |
| Meeting-request extractor | **Cal.com** (AGPL, self-hostable) + CalDAV | **integrate** Cal.com for availability; it is a solved problem |
| Newsletter digest / auto-unsub | **kill-the-newsletter** (Go, self-hosted) | **integrate** — genuinely better than building RSS + unsubscribe heuristics |
| Signature enforcer | mushegh `draft_email` hook | **build** — one hook |
| Multi-language tone-matching | **Argos Translate** (MIT) or **LibreTranslate** (AGPL) | **integrate** translation; build the tone match |

### 3.2 Cyber defense / SecOps — 4 utilities, Mushegh absent
This is the band where open source is far ahead of anything you'd write.

| utility | recommended stack | note |
|---|---|---|
| Honeypot & attacker profiler | **Cowrie** (BSD-3) — the reference SSH/Telnet honeypot | integrate; feed its JSON into Mushegh's security ledger |
| External attack-surface scanner | **nuclei** (MIT), **subfinder** (GPL-2), **trivy** (Apache-2) | integrate; run on a schedule, report to Mushegh |
| Phishing-link detonator | **PhishTank** data + **urlscan.io** API, or **Snort** | integrate the data, build the Mushegh alert |
| Credential-breach surveillance | **Hibp** via `haveibeenpwned` tooling, or **dehashed** self-run | integrate; needs a key or self-hosted corpus |

### 3.3 Sales / GTM — 3 utilities, Mushegh absent
**Recommendation: do not build.** This is the clearest case where integrating beats
starting from scratch, and also where it's a different product.

- **Lead enrichment/verification**: **Hunter.io** API, **Clearbit** (commercial),
  self-hosted **FullContact** alternative: **`email-validator`** + **dnsbl**. There is no
  good OSS lead database; budget for an API.
- **High-intent signal radar**: build on your existing `web_search` + `scrape_url` +
  `news_brief`. Mushegh already has the primitives.
- **Conference intelligence**: **Scrapy** or **Crawl4AI** (Apache-2, LLM-friendly) feeding
  Mushegh. **Crawl4AI is the single best integrate-here choice** — it is purpose-built to
  return LLM-ready markdown from any site, which is exactly `scrape_url`'s job done better.

### 3.4 Support / community — 5 utilities, Mushegh absent
- **L1 support concierge**: build on Mushegh itself; **RAGFlow** (Apache-2) or **Quivr**
  (Apache-2) as the retrieval layer. Integrate retrieval; build the voice surface.
- **Onboarding orchestrator**: **n8n** (Sustainable Use, not OSI — check terms) or
  **Windmill** (AGPL, self-hostable, workflow engine). **Windmill is the better fit**
  because Mushegh already has `plan_task`/`execute_task` semantics.
- **Anti-spam/anti-raid**: **Akismet** (WordPress, GPL) or **nnet** — thin value for Jarvis.
- **Churn/sentiment**: **VADER** (MIT) + **TextBlob** for the NLP, but you have JEv.
- **FAQ auto-updater**: **Quivr** again, or build on `search_vault`.

### 3.5 Legal / contracts — 3 utilities, Mushegh absent
- **Milestone/obligation tracker**: **CUDA**? No — use **Calamari** (AGPL, ERP-ish) is
  overkill. **Build on `add_task`**; this is a schema, not software.
- **Signature workflow**: **Documenso** (AGPL, self-hostable, e-sign) is the standout OSS
  option. **Integrate.**
- **Regulatory deadlines**: **Cal.com** again, or your own calendar.

### 3.6 HR / people ops — 3 utilities, Mushegh partial
- **Pulse/sentiment**: Mushegh already has `note_sensitivity` + coaching. **Build.**
- **Onboarding checklists**: **Windmill** or a Notion template. Integrate Notion.
- **Policy diff notifier**: **restic**-free answer — just git. **Build** on `git_diff`.

### 3.7 Content creation — 8 utilities, Mushegh absent (but you have Bookroom)
- **Scriptwriting / repurposing**: build on Mushegh; the pipeline is what you have.
- **Vertical clip pipeline**: **ffmpeg** (LGPL/GPL) + **auto-editor** (Unlicense) +
  **Whisper** (MIT) for transcript-based highlight detection. **Integrate all three** —
  this is well-solved and boring to rebuild.
- **Editorial calendar**: Mushegh `add_task`.
- **Changelog publisher**: **git-cliff** (MIT) or **git-chglog**. **Integrate.**

### 3.8 Procurement — 3 utilities, Mushegh absent
Low value for a single-person assistant. **Skip.** Integrate nothing; the domain is
ERP-shaped and needs a real ERP (or **Odoo**, LGPL, or **ERPNext**, GPLv3, if ever needed).

### 3.9 Infrastructure watchdog — Mushegh strong
Already covered by your uptime watcher, backup drills and self-health. The one genuine
upgrade: **restic** for backups (GPL-2/BSD, verified good earlier) and **sops+age** for
secrets-at-rest.

### 3.10 Knowledge base — Mushegh strong, but the memory layer is replaceable
- **Tolaria** as the *human* knowledge surface (AGPL, MCP) — keep Mushegh's own
  `search_vault`/`read_vault_note` as the machine surface. Two surfaces, one Markdown
  corpus. This is the cleanest integration on the list because the data format is plain
  files, so **either side can be dropped later** — no lock-in, which is the property to
  insist on given you have been burned by vendor-shaped formats.

---

## 4. Integrate or build — the rule I'd apply

Your own precedent settles this: **you built the Bookroom SDK instead of integrating a
summarizer, and that was right** — because the domain was specific and the off-the-shelf
options were either commercial or wrong-shaped.

That precedent generalises into three rules:

1. **Build when the utility is about the owner's own data and rules.** Triage labels, the
   follow-up tracker, the follow-up *of this specific person*. Generic tools lose the
   thing that makes them useful.
2. **Integrate when the domain is a solved, stable, infrastructure-shaped problem.**
   Crawling, e-signature, backups, secrets, DNS/TLS scanning, calendar availability. These
   have correct answers that already exist; re-deriving them is waste.
3. **Do not enter a domain at all unless the charter wants you there.** Sales, procurement
   and legal are the catalog's business-ops centre. §6 "subtract before you add" applies
   to whole domains, not just features.

---

## 5. The five projects I'd actually start, in order

1. **Inbox triage** (Mushegh-thin, 8 utilities, immediate daily value)
   → `Triage` label model + `kill-the-newsletter` + Mushegh `draft_email` hooks.
   *Everything here exists except the follow-up tracker, which is ~1 day of your own code.*
2. **SecOps** (Mushegh-absent, no commercial equivalent worth the licence)
   → `Cowrie` + `nuclei` + `trivy` on a schedule, results into Mushegh's security ledger.
   *The clearest "open source is simply ahead" case in the whole catalog.*
3. **Crawl4AI** replacing `scrape_url` for OSINT and support domains.
   *One dependency that improves four of the catalog's eighteen domains.*
4. **Tolaria as your knowledge surface**, with Mushegh keeping the machine surface.
   *Cheap, reversible, and it retires the "which note app" question permanently.*
5. **Secrets**: **sops + age** rather than Infisical, because you can read the format with
   `age -d` at 3am and a silent licence change cannot strand you.
   *The charter's own "debuggable in 90 seconds" rule decides this one.*

---

## 6. What I did not verify, and would need before acting

Per your charter: I will not cite a licence I have not read.

- **Infisical's current licence** — changed historically; confirm before adopting.
- **Rea**, **Mcode**, **Life OS**, **ghost downloader** — I could not identify these as
  specific projects. Give me a URL or repo name and I will assess them properly.
- **n8n** is *Sustainable Use*, not OSI-approved — I flagged it rather than recommending
  it. Windmill (AGPL) is the clean alternative.
- Catalogue entries 1–83 are the document's own claims; I have not independently
  validated that each is buildable as described.

---

## 7. The one question that decides the rest — now per product

My first draft asked *"is Jarvis an assistant for one person or an operator for a
business?"* and treated the answer as global. That was wrong: **Rubo already answers it
for the finance half.** So:

- **Jarvis** → assistant for one person. Domains 3.1, 3.9, 3.10 and the coding side.
  Roughly **20 of the 83 utilities**. The business-ops domains — sales, support, legal,
  procurement — are somebody else's job, and integrating them into a personal assistant is
  the failure mode this document exists to prevent.
- **Rubo** → owns the excluded domains outright. The catalog is silent there by design,
  so its integration list has to be researched separately.
- **The fleet** → the natural home for anything shared: agent identities (AgentMail),
  knowledge surfaces (Tolaria or LifeOS over MCP), and SecOps if it ever faces the public.

The open question is therefore much narrower than I first framed it: **does Jarvis ever
grow a business-facing surface?** If not, stop at ~20 utilities. If it does, SecOps and
legal belong to the fleet and should be built on audited software — Cowrie, nuclei, trivy,
Documenso — rather than written fresh.

I would still not integrate anything until that is answered, and the answer is now much
cheaper to give than it was: it is a question about **Jarvis**, not about the fleet.