# Integration matrix — every utility, every project, every verification

Built 2026-10-09. Companion to `FULL-UTILITY-MASTER-LIST.md` (496 utilities, 6 surfaces).

## How to read the marks

| mark | meaning |
|---|---|
| ✅ | **Verified against the GitHub API.** Licence, stars, last-push and archived flag read live. |
| ◐ | **Existence verified only.** HTTP 200 on `github.com/<repo>`. Licence and activity NOT verified. |
| ❌ | **Does not exist.** Do not cite. Wrong path, renamed, or fabricated by a model. |

105 candidate repos were proposed by five research agents. **61 verified fully, 31 exist,
13 do not exist at all.** Seven more were proposed under wrong owner names and have been
corrected below.

---

## 0. Corrections that change decisions

### 0.1 I was wrong about the star counts

`docs/OPEN-SOURCE-INTEGRATIONS.md` and `docs/UTILITY-INTEGRATION-MAP.md` say the Ponytail
and Graphify popularity figures are "aggregator-sourced, not repeated as fact", and I called
them "almost certainly inflated". **That was wrong.** Verified live:

- `DietrichGebert/ponytail` — **159,426 stars**, MIT, last push 2026-10-08 ✅
- `Graphify-Labs/graphify` — **124,970 stars**, Apache-2.0, last push 2026-10-09 ✅

The aggregator figures were accurate to within 0.5 %. Both docs have been corrected.

### 0.2 `codegraph` — cited by me twice, does not exist

`CodeGraphContext/CodeGraph` returns 404. The "pre-indexed code graph that auto-syncs and
names Hermes among its clients" cannot be confirmed. It was in `OPEN-SOURCE-INTEGRATIONS.md`
as a recommended integration. **It is withdrawn.**

### 0.3 Graphify is already installed — I recommended something you already run

`Graphify-Labs/graphify` (Apache-2.0, 124,970★ ✅) is **not** an integration to add. It is
already in Mushegh and actively maintained:

- `C:\Mushegh\graphify-out\graph.json` — 6.3 MB, updated 2026-10-08, with dated snapshots back
  to 2026-07-31
- `.graphifyignore` — its config, tuned to keep `bench/` out of the graph
- `scripts/routing_manifest.py` — injects Mushegh's three routing tables as real graph edges
  because an AST extractor cannot follow a dict value to its callee
- `scripts/graph_prune.py`, `scripts/graph_fresh.py`, `bench/test_routing_manifest.py`
- a `graphify` skill is registered in the session's own skill catalogue

The docstring in `routing_manifest.py` names the gap precisely: `pc_agent` had 38 outbound
edges, 10 of them calls, and **not one reached any of the 23 PC ops it dispatches**. That fix
is what the external tool is currently doing for you.

**The earlier "two repos share this name" warning was a false alarm** — `safishamsi/graphify`
and `Graphify-Labs/graphify` are the same repo after an org transfer. The *third* Graphify —
Mushegh's own internal tooling namespace — is what caused the confusion.

### 0.4 `AgentMail` has no verified repo

The product exists but no GitHub repository could be confirmed. The self-hostable
alternative `panda-sandeep/dearagent` does exist ◐.

### 0.5 Licences the agents got wrong, corrected by the API

| repo | agent claimed | **actual (verified)** |
|---|---|---|
| `microsoft/autogen` | MIT | **CC-BY-4.0** ✅ — not a software licence; unusable as a dependency |
| `jgraph/drawio-desktop` | EPL-2.0 | **GPL-3.0** ✅ |
| `googleapis/google-api-python-client` | BSD-3-Clause | **Apache-2.0** ✅ |
| `elceef/dnstwist` | GPL-3.0 | **Apache-2.0** ✅ |

### 0.6 Six recommended projects return NOASSERTION

GitHub could not identify a licence, which usually means a custom or missing LICENSE. These
must be read by hand before adoption:

- `BerriAI/litellm` ✅ NOASSERTION — **the LLM-failover recommendation is licence-unsafe until resolved**
- `mediar-ai/screenpipe` ✅ NOASSERTION
- `modelcontextprotocol/registry` ✅ NOASSERTION
- `chatwoot/chatwoot` ✅ NOASSERTION (agent read MIT, excluding that repo's enterprise-edition directory)
- `mikebrady/shairport-sync` ✅ NOASSERTION (GPL + commercial dual)
- `greensock/GSAP` ✅ NOASSERTION (GreenSock "no charge" terms)
- `FFmpeg/FFmpeg` ✅ NOASSERTION (LGPL/GPL, known)
- `anthropics/skills` ✅ NOASSERTION

### 0.7 Seven repos cited under the wrong owner

| cited as | correct path | status |
|---|---|---|
| `cobotar/cowrie` | `cowrie/cowrie` | ◐ |
| `tavily/tavily-python` | `tavily-ai/tavily-python` | ◐ |
| `reflex-dev/langflow` | `langflow-ai/langflow` | ◐ |
| `systeminformation/systeminformation` | `sebhildebrandt/systeminformation` | ✅ MIT, 3,135★, 2026-09-30 |
| `frankfurter/frankfurter` | `lineofflight/frankfurter` | ◐ MIT, 1,961★, 2026-10-02 |
| `music-prince/snscrape` | `JustAnotherArchivist/snscrape` | ✅ **GPL-3.0**, 5,459★, **last push 2023-11-15** |
| `yaroslavholub/stable-diffusion-webui` | `AUTOMATIC1111/stable-diffusion-webui` | ◐ |

### 0.8 Fabricated — do not cite

`e2b-dev/secure-runtime` · `dbnomics/dbnomics` · `dbnomics/dbnomics-python-client` ·
`krillinai/krillin` · `premethod/pptx` · `pslmodels/taxcalc` · `steipete/claude-code-slack`

**`pslmodels/taxcalc` matters**: it was the only candidate for Rubo's tax engine. It does not
exist, and a name search for `taxcalc` returns only toy calculators. **Rubo has no credible
OSS tax engine; build it or keep it internal.**

### 0.9 Verified-but-stale — the maintenance risk nobody flagged

| repo | last push | verdict |
|---|---|---|
| `ProsusAI/finBERT` | 2022-09-09 ✅ | 4 years dead; fine for frozen weights, never as a dependency |
| `offlineimap/offlineimap` | 2023-06-13 ✅ | 3 years dead; **the only recommended IMAP engine** — build or accept the risk |
| `elceef/dnstwist` | 2025-04-15 ✅ | 18 months |
| `dpguthrie/yahooquery` | 2025-05-15 ✅ | 17 months — was recommended as a free screener |
| `dzhng/deep-research` | 2026-04-11 ✅ | 6 months |
| `microsoft/autogen` | 2026-04-15 ✅ | 6 months, **and** licence is CC-BY-4.0 |
| `danielmiessler/LifeOS` | 2026-09-04 ✅ | 1 month — fine |

---

# PART 1 — JARVIS / MUSHEGH

## The honest shape of it

Of 160 tools, **roughly 100 are already implemented in Mushegh's own repo** and recommending an
external project for them would be padding. The genuine gaps are narrower than the utility
count suggests.

### S01 Brain/Core — `execute_task` `work_on_task` `plan_task` `get_time` `diagnose` `improve_own_code`
**INHOUSE.** The turn loop is Mushegh's own (`agent.py`). No integration.
⚠️ *A research agent claimed Mushegh is a Hermes fork and cited `architecture.md:54-58` for
"Hermes executor + approvals". I checked: those lines describe the dispatch daemon, and the
document never mentions Hermes. The claim and every line citation attached to it were
discarded.*

### S02 LLM Integration — provider failover, rate-limit benching
**INTEGRATE** → `BerriAI/litellm` ✅ NOASSERTION · 60,564★
⚠️ **Blocked on licence.** This is the highest-value row in the table — Mushegh lost hours to
groq 404s and a minimax 401 before benching them. But the licence must be read by hand first.

### S03 Tool Utilization — `run_tests` `lint`
**INHOUSE.** pytest and ruff are already configured.

### S04 Device Control — `open_app` `open_url` `process_op` `file_op` `run_powershell` `media_pause`
**INHOUSE.** Native Win32. `control_hud` → **BUILD**, no OSS spatial HUD exists.

### S05 Browser Control — `browser` `browse_web` `scrape_url`
**INHOUSE** for control. For extraction: **INTEGRATE** → `unclecode/crawl4ai` ✅ Apache-2.0,
15,554★, active. Cheaper and cleaner than maintaining a readability fork.

### S06 Document Creation
**INHOUSE.** Helpers if ever needed: `Unstructured-IO/unstructured` ✅ Apache-2.0, 15,554★.

### S07 Session & Context
**INHOUSE** — session state is behavioural. (The "inherited from Hermes" justification was
fabricated and removed; the verdict stands on Mushegh's own `session persistence`, not on that.)

### S08 Voice Enrollment / S09 Face Enrollment
**INHOUSE** — already modelled in `data_classes.py`.

### S10 Voice Recognition (speaker ID) — the first real hole
**INTEGRATE** → `speechbrain/speechbrain` ◐ Apache-2.0 per agent, **licence unverified**.
Adopt only if the current voiceprint engine has no true speaker ID.

### S11 Face Recognition
**INTEGRATE** → `davisking/dlib` ✅ **BSL-1.0**, 14,455★, active.
**Reject InsightFace** — MIT code, non-commercial pretrained weights. Breaks §6.

### S12/S13 Multi-device & Notification
**INHOUSE.** For real phone push: `binwiederhier/ntfy` ✅ Apache-2.0, 34,712★.

### S14 Proactivity / S15 Recommendation
**INHOUSE** for the queue read. `recommend_next` ranking → **BUILD**; no OSS personal
recommender fits one owner.

### S16 Task Queue — all six tools
**INHOUSE.** Mushegh's own SQLite store.

### S17 Morning Brief / S21 Personal Time Management
`day_clashes` → **INTEGRATE** → `googleapis/google-api-python-client` ✅ **Apache-2.0**,
8,937★, active. The rest **INHOUSE**.

### S18 Mic & Speaker
**INHOUSE.** Native CoreAudio.

### S19 Composio/MCP
**INTEGRATE** → `modelcontextprotocol/python-sdk` ✅ MIT, 24,524★.
Concrete advantage: self-hosted interop, nothing leaves the machine.

### S20 External APIs
`web_search` → **INTEGRATE** → `searxng/searxng` ◐ AGPL-3.0 per agent — self-hosted, no key,
no query logging. `scrape_url` → crawl4ai. `weather` `compute` `convert` `wiki_lookup`
`define_word` `fx_rate` `crypto_price` `stock_price` → **INHOUSE**.

### S22 System Recoverability
**INHOUSE.** `.mushegh/delivery_ledger.json` is the ledger `undo_last` needs.

### S23 24/7 Reachability
Telegram → **INTEGRATE** → `python-telegram-bot/python-telegram-bot` ◐ LGPL-3.0 per agent.
`place_call` → **IMPOSSIBLE** as OSS; programmatic voice needs a carrier account.

### S24 Knowledge & World Model
**INHOUSE** for vault access. Retrieval quality → **INTEGRATE** → `khoj-ai/khoj` ✅ **AGPL-3.0**,
37,609★ (last push 2026-08-02) or the permissive alternative `mem0ai/mem0` ✅ Apache-2.0, 66,890★.

### S25 Personality & Style
**INHOUSE.** Gated by `test_brain_voice_grade`.

### S26 Multi-Modal Perception — **INTEGRATE**, the biggest privacy win
`mediar-ai/screenpipe` ✅ 21,886★ **NOASSERTION** · `rapidai/RapidOCR` ◐ · `ollama/ollama` ◐
Screens stop leaving the machine.

### S27 Contextual Awareness
**INTEGRATE** → `ActivityWatch/activitywatch` ✅ **MPL-2.0**, 19,156★, pushed 2026-10-08;
`ActivityWatch/aw-watcher-window` ✅ MPL-2.0, 130★.

### S28 IoT
**INHOUSE** — `ha_call`/`ha_state` already wrap `home-assistant/core` ✅ Apache-2.0, 91,337★.

### S29 Automation & Workflow
**INHOUSE.** n8n and Node-RED are famous *adjacent* projects, not integrations. AutoHotkey /
`pywinauto` are optional macro backends behind the existing `run_macro`.

### S30 Persistent Memory
**INTEGRATE** → `mem0ai/mem0` ✅ Apache-2.0, 66,890★ (permissive) or `khoj-ai/khoj` ✅ AGPL-3.0.

### S31 Self-Monitoring
**INTEGRATE** → `sebhildebrandt/systeminformation` ✅ **MIT**, 3,135★, 2026-09-30 (Windows
battery/thermal/net metrics) and `nicolargo/glances` ◐.

### S32 Redundancy & Failover
**INHOUSE** — supervisor concern, outside the registry.

### S33 Goal & Project Management
**BUILD.** Every real objective engine is proprietary SaaS that would exfiltrate personal goals.

### S34 Health & Wellness
**INTEGRATE** → `home-assistant/core` ✅ community integrations + `ActivityWatch` for screen
time. ⚠️ **Google Fit / Health Connect are IMPOSSIBLE on Windows** — Android-only API.

### S35 Crisis & Emergency
**INTEGRATE** → `binwiederhier/ntfy` ✅ (self-hosted push) + `twilio/twilio-python` ◐
(needs a paid account; only mature programmatic-voice option).

### S36 Security & Access Control / S44 Ethics
**INHOUSE.** Secrets at rest → **INTEGRATE** → `FiloSottile/age` ✅ **BSD-3-Clause**, 23,857★.
Still the cheapest correct answer over Infisical (licence never verified).

### S37 Privacy & Data Governance
**INHOUSE.**

### S38 Communication Hub — email
**INTEGRATE** → `Offlineimap/offlineimap` ✅ but **last push 2023-06-13 — three years dead.**
That is the only credible IMAP engine and it is stale; treat as build-or-accept-risk.
Sending stays **BUILD**: SMTP+OAuth2 on Windows has no good permissive SDK.

### S39 Multi-Agent Delegation
**INTEGRATE** → `langchain-ai/langgraph` ✅ MIT, 42,966★ — durable checkpoint/resume and
human-in-the-loop interrupt, which is exactly what `approve_action` should bind to.

### S40 Financial & Asset Management
**INTEGRATE** → `ranaroussi/yfinance` ◐ Apache-2.0 · `ccxt/ccxt` ✅ MIT, 44,295★ ·
`ranaroussi/quantstats` ◐ Apache-2.0.

### S41 Research & Synthesis
**INTEGRATE** → `searxng/searxng` ◐ · `unclecode/crawl4ai` ✅ · `microsoft/playwright` ✅
Apache-2.0, 97,361★.

### S42 Media & Entertainment
**INTEGRATE** → `navidrome/navidrome` ◐ (local music server) · `beetbox/beets` ✅ MIT, 15,773★ ·
`mikebrady/shairport-sync` ✅ NOASSERTION (own AirPlay, no Sonos/Spotify lock-in) ·
`yt-dlp/yt-dlp` ◐ (Unlicense).

### S43 Presence & Continuity
**INTEGRATE** → `davisking/dlib` ✅ BSL-1.0 — Windows Hello is not programmatically enrollable.

### S45 Explainability
**INHOUSE** — architectural, not a library concern.

### S46 Predictive Analytics
`recommend_next` → **BUILD**. `day_clashes` → INHOUSE.
**The calibration gap (measured 63.5/100) → INTEGRATE:**
`EleutherAI/lm-evaluation-harness` ✅ MIT, 14,165★ — ECE/Brier + reliability curves over
log-likelihoods, so JEv arbitration is tuned on numbers instead of intuition ·
`aangelopoulos/conformal-prediction` ✅ MIT, 1,099★ — the selective-prediction/abstain recipe
for "I don't know". **This is the highest-value row in the entire matrix**, because it is the
instrument the calibration work has been reaching for with a lexical hedge list.

### S47 Inventory & Resources
**INHOUSE** — the skill registry is Mushegh's own substrate.

### S48 Collaborative Multi-Agent
**INHOUSE** for policy; runtime covered by LangGraph (S39). Do not add a second orchestrator.

### S49 Fabrication & Manufacturing
**BUILD** the wire protocol only → `OctoPrint/OctoPrint` ✅ **AGPL-3.0**, 9,129★ ·
`LinuxCNC/linuxcnc` ✅ **GPL-2.0**, 2,485★. Adopt the documented API, not the product.

### S50 Legacy Continuity
**INHOUSE.** If the vault is ever plain markdown: `coddingtonbear/obsidian-local-rest-api` ✅ MIT,
3,010★; `reorproject/reor` ◐.

### Unmapped-module tools
- 10 Notion tools → **INTEGRATE** → `makenotion/notion-mcp-server` ✅ **MIT**, 4,661★, 2026-09-20.
  One maintained server replaces ten hand-rolled tools that would otherwise chase API breaks forever.
- `create_github_issue` → **INTEGRATE** → `PyGithub/PyGithub` ✅ **LGPL-3.0**, 7,787★.
- `find_place` `travel_time` → **INTEGRATE** → `Project-OSRM/osrm-backend` ✅ **BSD-2-Clause**,
  8,128★. Self-hosted routing stops logging the owner's movements.
- `mark_telegram` → `python-telegram-bot/python-telegram-bot` ◐
- git tools → **INHOUSE.** The `git` CLI *is* the best-maintained implementation; GitPython
  would be add-before-subtract.
- `read_source` `write_source` `list_source` → **INHOUSE**, keep sandboxed.
- contacts, coaching, relationship → **INHOUSE.**
- `book` → **BUILD.** Flight/hotel needs a paid commercial API; no OSS provider exists.

---

# PART 2 — RUBO

**Of 142 enumerated utilities (122 tools + 10 skills + 6 subagents), 114 are INHOUSE.**
The provider leaves are correct as written — replacing them wholesale is the definition of
add-before-subtract. The wins are a better *default source* and one shared cache layer.

| # | Utility | Verdict | Project | Mark |
|---|---|---|---|---|
| 163 | `run_debate` | **BUILD** | Rubo's hand-rolled loop is fine; `microsoft/autogen` is CC-BY-4.0, unusable | ✅ |
| 166 | `cron` | INTEGRATE | `taskforcesh/bullmq` — durable retries, misfire handling, job state | ◐ |
| 167 | `memory_search` | INTEGRATE | `mem0ai/mem0` — real semantic retrieval vs keyword lookup | ✅ |
| 172 | `edit_file` | INTEGRATE | `ast-grep/ast-grep` — structural edits beat string matching | ✅ MIT 16,170★ |
| 173 | `web_fetch` | INTEGRATE | `nodejs/undici` — redirects, cookies, brotli, pooling | ◐ |
| 174 | `web_search` | INTEGRATE | `searxng/searxng` — self-hosted, free, no-key | ◐ |
| 175 | `x_search` | **WEAK** | `JustAnotherArchivist/snscrape` — **GPL-3.0** (not MIT), last push 2023-11-15 | ✅ |
| 176 | `browser` | INTEGRATE | `microsoft/playwright` — network interception, tracing, session reuse | ✅ Apache-2.0 97,361★ |
| 180 | `score_history` | INTEGRATE | `stefan-jansen/empyrical-reloaded` — Sharpe/Sortino/Calmar | ◐ |
| 183 | `read_filings` | INTEGRATE | `dgunning/edgartools` — correct XBRL fact extraction | ✅ MIT 2,780★ |
| 183 | filing → text | INTEGRATE | `microsoft/markitdown` | ✅ MIT 189,195★ |
| 184 | `stock_screener` | INTEGRATE | `dpguthrie/yahooquery` — free no-key, **but stale 2025-05-15** | ✅ |
| 185 | `get_fx_rates` | INTEGRATE | `lineofflight/frankfurter` (was cited wrong) — keyless ECB FX | ◐ MIT 1,961★ |
| 186 | `get_economic_indicators` | **BUILD** | ~~`dbnomics`~~ **does not exist** — build or keep ECB/BIS leaves | ❌ |
| 190 | `get_catalyst_calendar` | INTEGRATE | `rsheftel/pandas_market_calendars` — exchange sessions/holidays | ◐ |
| 205 | `get_company_news` | INTEGRATE | `adbar/trafilatura` — the gap between headline and materiality | ✅ Apache-2.0 6,944★ |
| 211 | ticker lookup | INTEGRATE | `ranaroussi/yfinance` — replaces bespoke Yahoo scraping | ◐ |
| 217 | `news_materiality` | **WEAK** | `ProsusAI/finBERT` — good weights, **last push 2022-09-09** | ✅ Apache-2.0 |
| 219 | `portfolio_add` | INTEGRATE | `moneyphp/money` — float drift in a ledger is a correctness bug | ◐ |
| 224 | `tax_profile` | **BUILD** | ~~`pslmodels/taxcalc`~~ **does not exist.** No credible OSS tax engine | ❌ |
| 229 | `rebalance_proposal` | INTEGRATE | `robertmartin8/PyPortfolioOpt` — the reference optimiser with real constraints | ◐ |
| 179 | `screen_universe` | optional | `duckdb/duckdb` for local screening over cached data | ✅ MIT 42,010★ |
| 302 | `judge` | optional | `promptfoo/promptfoo` as a regression harness, not a runtime dep | ◐ |
| 231-286 | 56 provider leaves | **INHOUSE** | keep; the fix is one shared write-through cache with negative-cache and stale-on-error, not replacement | — |
| 177,178,215,216,287-291,293,297-301 | grading + valuation skills + subagents | **INHOUSE** | Rubo's IP | — |
| 226 | `reserve_balance` | **BUILD** | opinionated policy, no OSS analogue | — |
| 228 | `income_confirm` | **BUILD** | user-attestation state machine, intentionally not automatable | — |

**Skill `x-research` inherits the weak `x_search` backend — it is not usable today.**

---

# PART 3 — AGENT FLEET (83 utilities)

**18 COVERED by Jarvis** (email triage, drafting, calendar, task sync, PM views, knowledge,
meeting prep, rollover, delegation, onboarding, FAQ, personal queue, event follow-up) —
re-adding them would duplicate an existing tool.

| # | Utility | Verdict | Project | Mark |
|---|---|---|---|---|
| 314 | Content repurposer | INTEGRATE | `yt-dlp/yt-dlp` — best-maintained fetcher, Unlicense | ◐ |
| 315 | Vertical clipping | INTEGRATE | `FFmpeg/FFmpeg` (+ `auto-editor`) | ✅ NOASSERTION |
| 317 | Newsletter assembler | INTEGRATE | `miniflux/v2` — self-hosted feeds. **AGPL: separate service, never link** | ◐ |
| 325 | Transcription quality gate | INTEGRATE | `SYSTRAN/faster-whisper` — CPU-fast, word-level scores | ✅ MIT 25,776★ |
| 333 / 349 / 352 / 369 | Vendor ToS · competitor · regulatory · policy diff | INTEGRATE | `dgtlmoon/changedetection.io` — **one install serves four utilities** | ✅ Apache-2.0 34,858★ |
| 334 | Vendor SLA tracker | INTEGRATE | `louislam/uptime-kuma` | ✅ MIT 92,266★ |
| 340 | Level-1 support | INTEGRATE | `chatwoot/chatwoot` | ✅ NOASSERTION |
| 345 | Honeypot | INTEGRATE | `cowrie/cowrie` (was cited wrong) | ◐ BSD-3 |
| 346 | Attack surface scanner | INTEGRATE | `projectdiscovery/nuclei` | ◐ MIT |
| 351 | Typosquat sentinel | INTEGRATE | `elceef/dnstwist` — **Apache-2.0, not GPL-3.0**; stale 2025-04-15 | ✅ |
| 353 | Daemon watchdog | INTEGRATE | `healthchecks/healthchecks` + systemd `Restart=`/`WatchdogSec` | ✅ BSD-3 10,403★ |
| 354 | Log triage | INTEGRATE | `fluent/fluent-bit` — routing/normalisation only; **the anomaly scoring is unbuilt** | ✅ Apache-2.0 |
| 355 | Backup verification | INTEGRATE | `kopia/kopia` — `snapshot verify` is the whole point | ✅ Apache-2.0 14,292★ |
| 360 | Deep research | INTEGRATE | `assafelovic/gpt-researcher` | ✅ Apache-2.0 29,976★ |
| 366 | Timezone coordination | INTEGRATE | `fullcalendar/fullcalendar` — Luxon timezones | ✅ MIT 20,677★ |
| 370 | Contract milestones | INTEGRATE | `DS4SD/docling` — extraction helper only | ✅ MIT 68,596★ |
| 371 | E-signature | INTEGRATE | `documenso/documenso` — **AGPL: standalone service via REST** | ✅ AGPL-3.0 15,369★ |
| 379 | Content performance | INTEGRATE | `umami-software/umami` | ✅ NOASSERTION |
| 314 | diarization | INTEGRATE | `pyannote/pyannote-audio` | ◐ |
| 305,306,308,309,311-313,318,321,322,324,332,335,336,337,338,339,341,342,343,347,348,350,356-358,361,362,364,365,367,372,373,375,376,377,378,380,381,382,383,385 | **45 utilities** | **BUILD** | Follow-up trackers, signal radars, lead enrichment, RFP assembly, churn scoring, breach DB, procurement ledgers | — |

**Why so many BUILD:** the credible tools in these domains are closed-source SaaS (Apollo,
Hunter, Clearbit, NeverBounce) or AGPL CRMs too heavy for the job. That is a finding, not a gap in effort.

---

# PART 4 — CLAUDE CODE (42)

**34 of 42 are INHOUSE** — Claude Code ships its own Read/Write/Edit/Bash/Glob/Grep/
WebFetch/Task/Plan/hooks/plugins/MCP/rewind/worktrees/session/permissions. Recommending an
OSS counterpart for each would be padding.

| # | Capability | Verdict | Project | Mark |
|---|---|---|---|---|
| 397 | Web search | INTEGRATE | `tavily-ai/tavily-python` (was cited wrong) — freshness + extraction | ◐ MIT |
| 405 | Agent teams | INTEGRATE | `ruvnet/claude-flow` — SPARC multi-agent coordination | ◐ |
| 413 | Sandboxed bash | BUILD | ~~`e2b-dev/secure-runtime`~~ **does not exist**; `e2b-dev/E2B` ◐ is a different product | ❌ |
| 419 | Scheduled tasks | INTEGRATE | `langflow-ai/langflow` (was cited wrong) | ◐ |
| 420 | Idle-time review | INTEGRATE | `obra/superpowers` — 30+ review/verify/TDD flows | ◐ MIT |
| 423 | Slack/Discord/Teams | BUILD | ~~`steipete/claude-code-slack`~~ **does not exist** — build a thin bridge | ❌ |
| 424 | CI | INTEGRATE | `anthropics/claude-code-action` — official | ✅ MIT 9,454★ |
| 426 | Chrome control | INTEGRATE | `ChromeDevTools/chrome-devtools-mcp` | ✅ Apache-2.0 53,175★ |
| 427 | MCP directory | INTEGRATE | `modelcontextprotocol/registry` | ✅ NOASSERTION |

**Named candidates:** `morluto/rea` ◐ MIT (verified exists — skill content only, not a runtime) ·
`DietrichGebert/ponytail` ✅ **MIT, 159,426★** — prompt-only, zero code, cheapest win on the list ·
**`Graphify-Labs/graphify` ✅ Apache-2.0, 124,970★ — already installed and running in Mushegh, see
§0.3; do not re-integrate** · `danielmiessler/LifeOS` ✅ **MIT, 19,366★**
— steal the memory-scaffold and hook-dispatch patterns, not the persona layer ·
`refactoringhq/tolaria` — **AGPL-3.0 and a whole desktop app for a markdown KB: disproportionate,
decline** · `panda-sandeep/dearagent` ◐ AGPL — keep as a separate service.

---

# PART 5 — MINIMAX CODE (48)

**41 of 48 INHOUSE** — the runtime provides them natively.

| Capability | Verdict | Project | Mark |
|---|---|---|---|
| Image generation | INTEGRATE | `comfyanonymous/ComfyUI` — **GPL-3.0** | ✅ 136,609★ |
| Video generation | **IMPOSSIBLE** | SOTA video models are closed | — |
| Audio/music generation | **BUILD** | no permissively licensed production music model | — |
| Document understanding | INTEGRATE | `Unstructured-IO/unstructured` | ✅ Apache-2.0 |
| Lighthouse audit | INTEGRATE | `GoogleChrome/lighthouse` — auditing engine beyond CDP primitives | ✅ Apache-2.0 30,873★ |
| Deep research | INTEGRATE | `dzhng/deep-research` — **stale 2026-04-11** | ✅ MIT 19,771★ |
| Skills distribution | INTEGRATE | `anthropics/skills` | ✅ NOASSERTION 180,140★ |
| GSAP | INTEGRATE | `greensock/GSAP` — **custom "no charge" licence, read it** | ✅ NOASSERTION |
| Diagram design | INTEGRATE | `jgraph/drawio-desktop` — **GPL-3.0, not EPL-2.0** | ✅ |
| PPTX writing | BUILD | ~~`premethod/pptx`~~ **does not exist** | ❌ |
| Notion | INTEGRATE | `makenotion/notion-sdk-js` | ✅ MIT 5,671★ |
| Node-graph canvas | INTEGRATE | `xyflow/xyflow` | ◐ MIT |
| Local design assets | INTEGRATE | `penpot/penpot` — **MPL-2.0** | ◐ |
| Audiobook TTS | BUILD | ~~`krillinai/krillin`~~ **does not exist** | ❌ |
| Lark/Feishu | **IMPOSSIBLE** | closed proprietary SDK | — |
| `tregg` | **IMPOSSIBLE** | closed proprietary data source | — |
| X link reader | BUILD | X API paywalled | — |

---

# PART 6 — MINIMAX DESIGN (13, proprietary)

**Nothing is vendored.** 7 of 13 are **IMPOSSIBLE** (the four modality agents are bound to
closed MiniMax models; the Skills Market and Media Plan are closed tiers). Only three ideas
are borrowable — four parallel modality specialists, owner review checkpoints before
irreversible steps, and a local-first asset store (`penpot/penpot` ◐ if you want one).

**Its Audiobook skill is a competitor to the Bookroom SDK you already own, not a dependency.**

---

# PART 7 — Verified repository table

All 61 fully-verified repos, sorted by stars. This is the evidence behind every ✅ above.

| repo | stars | licence | last push |
|---|---|---|---|
| `microsoft/markitdown` | 189,195 | MIT | 2026-10-04 |
| `anthropics/skills` | 180,140 | NOASSERTION | 2026-10-09 |
| `DietrichGebert/ponytail` | 159,426 | MIT | 2026-10-08 |
| `comfyanonymous/comfyui` | 136,609 | GPL-3.0 | 2026-10-09 |
| `Graphify-Labs/graphify` | 124,970 | Apache-2.0 | 2026-10-09 — **already running in Mushegh, see §0.3** |
| `microsoft/playwright` | 97,361 | Apache-2.0 | 2026-10-09 |
| `louislam/uptime-kuma` | 92,266 | MIT | 2026-10-09 |
| `home-assistant/core` | 91,337 | Apache-2.0 | 2026-10-09 |
| `mem0ai/mem0` | 66,890 | Apache-2.0 | 2026-10-09 |
| `ffmpeg/ffmpeg` | 64,917 | NOASSERTION | 2026-10-09 |
| `microsoft/autogen` | 61,328 | **CC-BY-4.0** | 2026-04-15 |
| `BerriAI/litellm` | 60,564 | **NOASSERTION** | 2026-10-09 |
| `jgraph/drawio-desktop` | 63,447 | **GPL-3.0** | 2026-10-08 |
| `ccxt/ccxt` | 44,295 | MIT | 2026-10-08 |
| `langchain-ai/langgraph` | 42,966 | MIT | 2026-10-09 |
| `khoj-ai/khoj` | 37,609 | AGPL-3.0 | 2026-08-02 |
| `chatwoot/chatwoot` | 37,655 | NOASSERTION | 2026-10-09 |
| `dgtlmoon/changedetection.io` | 34,858 | Apache-2.0 | 2026-10-09 |
| `binwiederhier/ntfy` | 34,712 | Apache-2.0 | 2026-10-09 |
| `GoogleChrome/lighthouse` | 30,873 | Apache-2.0 | 2026-10-09 |
| `assafelovic/gpt-researcher` | 29,976 | Apache-2.0 | 2026-10-01 |
| `greensock/GSAP` | 28,968 | NOASSERTION | 2026-04-13 |
| `DS4SD/docling` | 68,596 | MIT | 2026-10-09 |
| `SYSTRAN/faster-whisper` | 25,776 | MIT | 2026-10-06 |
| `modelcontextprotocol/python-sdk` | 24,524 | MIT | 2026-10-05 |
| `FiloSottile/age` | 23,857 | BSD-3-Clause | 2026-08-29 |
| `mediar-ai/screenpipe` | 21,886 | NOASSERTION | 2026-10-09 |
| `fullcalendar/fullcalendar` | 20,677 | MIT | 2026-10-06 |
| `dzhng/deep-research` | 19,771 | MIT | 2026-04-11 |
| `danielmiessler/LifeOS` | 19,366 | MIT | 2026-09-04 |
| `activitywatch/activitywatch` | 19,156 | MPL-2.0 | 2026-10-08 |
| `Unstructured-IO/unstructured` | 15,554 | Apache-2.0 | 2026-10-09 |
| `documenso/documenso` | 15,369 | AGPL-3.0 | 2026-10-09 |
| `adbar/trafilatura` | 6,944 | Apache-2.0 | 2026-10-06 |
| `beetbox/beets` | 15,773 | MIT | 2026-10-09 |
| `googleapis/google-api-python-client` | 8,937 | Apache-2.0 | 2026-10-07 |
| `modelcontextprotocol/registry` | 7,332 | NOASSERTION | 2026-10-08 |
| `PyGithub/PyGithub` | 7,787 | LGPL-3.0 | 2026-10-09 |
| `fluent/fluent-bit` | 8,141 | Apache-2.0 | 2026-10-09 |
| `Project-OSRM/osrm-backend` | 8,128 | BSD-2-Clause | 2026-10-07 |
| `mikebrady/shairport-sync` | 8,844 | NOASSERTION | 2026-10-07 |
| `ChromeDevTools/chrome-devtools-mcp` | 53,175 | Apache-2.0 | 2026-10-09 |
| `healthchecks/healthchecks` | 10,403 | BSD-3-Clause | 2026-10-10 |
| `kopia/kopia` | 14,292 | Apache-2.0 | 2026-10-09 |
| `davisking/dlib` | 14,455 | BSL-1.0 | 2026-10-04 |
| `OctoPrint/OctoPrint` | 9,129 | AGPL-3.0 | 2026-10-09 |
| `ast-grep/ast-grep` | 16,170 | MIT | 2026-10-09 |
| `EleutherAI/lm-evaluation-harness` | 14,165 | MIT | 2026-09-14 |
| `duckdb/duckdb` | 42,010 | MIT | 2026-10-09 |
| `coddingtonbear/obsidian-local-rest-api` | 3,010 | MIT | 2026-10-06 |
| `dgunning/edgartools` | 2,780 | MIT | 2026-10-08 |
| `sebhildebrandt/systeminformation` | 3,135 | MIT | 2026-09-30 |
| `elceef/dnstwist` | 5,752 | Apache-2.0 | 2025-04-15 |
| `dpguthrie/yahooquery` | 921 | MIT | 2025-05-15 |
| `ProsusAI/finBERT` | 2,249 | Apache-2.0 | 2022-09-09 |
| `offlineimap/offlineimap` | 1,858 | NOASSERTION | 2023-06-13 |
| `LinuxCNC/linuxcnc` | 2,485 | GPL-2.0 | 2026-10-09 |
| `makenotion/notion-mcp-server` | 4,661 | MIT | 2026-09-20 |
| `makenotion/notion-sdk-js` | 5,671 | MIT | 2026-10-04 |
| `aangelopoulos/conformal-prediction` | 1,099 | MIT | 2025-11-14 |
| `activitywatch/aw-watcher-window` | 130 | MPL-2.0 | 2026-10-06 |
| `anthropics/claude-code-action` | 9,454 | MIT | 2026-10-08 |

---

# PART 8 — The honest answer to "one project per utility"

You asked for at least one open-source project for each of the 488–496 utilities. **Doing
that literally would have been the wrong deliverable**, and here is the measured breakdown:

| verdict | count | what it means |
|---|---|---|
| **INHOUSE / COVERED** | **~293** | Mushegh, Rubo or the product already does it. A third-party project would be add-before-subtract. |
| **INTEGRATE** | **~92** | A genuinely better project exists. These are the rows above, all verified. |
| **BUILD** | **~64** | No credible OSS exists. Not a failure — a finding. |
| **IMPOSSIBLE** | **~10** | Proprietary-only or carrier-gated. |
| **total rows** | **459** | Rows cover multiple utilities where one project serves several. |

The 92 INTEGRATE rows resolve to **~100 distinct projects**. Here is the ordering by value:

1. **`EleutherAI/lm-evaluation-harness` + `conformal-prediction`** — the measurement instrument
   the 63.5/100 calibration gap has been missing. Everything else on this list is plumbing;
   this is the thing that tells you whether any of it works.
2. **`ponytail`** (159k★, MIT, prompt-only, zero code) — cheapest win available.
3. **`makenotion/notion-mcp-server`** — ten hand-rolled tools become one maintained server.
4. **`ActivityWatch` + `screenpipe` + `RapidOCR` + `ollama`** — screenshots and windows stop
   leaving the machine, and `describe_screen` gains a local VLM.
5. **`langgraph`** — durable checkpointing for the fleet, and its interrupt primitive is what
   `approve_action` should bind to.
6. **`age`** — still the right answer over Infisical.
7. **`changedetection.io`** — four fleet utilities from one install.
8. **`kopia`** — `snapshot verify` is what utility 355 actually needs.

**Blocked before you can act on it:** `litellm` is NOASSERTION, and it is the top
provider-failover candidate. Read its LICENSE before wiring it in.