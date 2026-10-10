# Utility + integration map — the whole stack

Written 2026-10-09 from the primary sources: `iamvazghen/Rubo` (README), `design.minimax.io`
(site + embedded `__NEXT_DATA__`), `morluto/rea`, and Afon's own tree. **Anything not read
from a primary source is marked unverified.**

---

## 0. The two facts that change the plan

### 0.1 Rubo and Afon already share the same judgement layer

Rubo's README documents `judge()` posting to
`https://api.typesafe.ai/v1/systemone` — **the same JEv endpoint Afon calls.** Three
Rubo tools are pure JEv: `dividend_safety`, `thesis_check`, `news_materiality`.

So this is not two products that might one day share a library. It is **one judgement layer
already serving two agents**, with different policies on each side: Afon uses it for turn
routing and arbitration, Rubo for forward-looking financial probability.

**And Rubo has the calibration harness Afon does not.** `/judgements` scores JEv's
answers with a **Brier score** against what actually happened (a dividend cut a year later
resolves), repeated weekly calls counted once, and shown next to the score of always
guessing the base rate. Every call lands in `.rubo/judgements.jsonl` with model version and
token usage.

Afon, after a full day of work, scores calibration with a **lexical list of 60 hedge
phrases** — which is how it was discovered that four real admissions matched none of the
38 original entries. A Brier score against resolved outcomes is the instrument Afon should
have and does not have. **That is the single most valuable thing Rubo already has.**

### 0.2 MiniMax Design is not open source

`design.minimax.io` is a proprietary desktop app (macOS 13+, Windows 10+ x64, "V.1.0 ·
DIRECTOR'S BUILD") with a paid Media Plan, an Enterprise lane offering on-prem deployment,
and a closed Skills Market. It cannot be vendored or extended as code.

What it *does* offer that matters:

- **Local-first by design** — "Access local files… your work stays yours."
- **Four agents in parallel** — Copy · Image · Video · Audio, per the workflow section.
- **A Skills system** — build your own, or install from the Market.
- **An `Audiobook` skill (v0.3.15)** — *"Turn books into multi-voice audiobooks."*

That last one is adjacent to the **Bookroom SDK** you already own. It is a competitor for
the summarizer-to-audio path, not a dependency, and it is not something to integrate.

---

## 1. Rubo — `iamvazghen/Rubo` (MIT)

**84 tools**, TypeScript on Bun/Node, pi-tui terminal UI + Telegram gateway.

| layer | what it has | open-source integration worth adding |
|---|---|---|
| **Grading engine** | Deterministic 0–100 on two horizons (1–3y, 20+y) from weighted factors in Rubo's own `factors.ts`, renormalised over available data, `<60 %` coverage flagged as thin. Ledger at `scores/<TICKER>.jsonl` | **This pattern is worth copying into Afon.** Afon computes quality in the *model*, not in code. A code-computed, reproducible score with a coverage floor is a category of its own |
| **JEv layer** | `dividend_safety`, `thesis_check`, `news_materiality`; `noul`/`choice`/`score`; cached per question (day/week); every call logged to `judgements.jsonl` | **Port `/judgements` to Afon.** Brier-scoring the arbitration and calibration verdicts against outcomes is the measurement Afon has been reaching for with prose |
| **Meta-tools** | `get_financials`, `get_market_data`, `read_filings`, `stock_screener`, `get_news`, `get_global_stock`, `get_catalyst_calendar`, `get_commodity`, `get_fx_rates`, `get_economic_indicators`, `get_fred_series` | Afon has `crypto_price`, `stock_price`, `fx_rate`, `news_brief`. Rubo's **provider-fallback chains** (`withProviderFallback([Polygon, Finnhub, FMP…])`) and **per-provider disk cache** are better than Afon's single-route chain — port the pattern, not the providers |
| **Leaf tools** | ~60, one per provider, all env-gated | None. This is Rubo's job |
| **Skills (10)** | `dcf-valuation`, `comps-valuation`, `ddm-valuation`, `reverse-dcf`, `earnings-preview`, `position-sizing`, `trade-review`, `macro-regime`, `write-memo`, `x-research` | **None for Afon.** These are finance workflows |
| **Subagents (6)** | `general-purpose`, `research`, `analysis`, **`devils-advocate`**, `macro-overlay`, **`judge`** | **`devils-advocate` and `judge` generalise.** Afon's fleet has no falsifying subagent — every one of its 7 calibration prompts is answered by the same model that would benefit from being wrong. That is the architecture behind the calibration gap |
| **Tax engine** | DE (Abgeltungsteuer 25 % + Soli), AT (KESt 27.5 %), flat-rate elsewhere; W-8BEN, allowance split, Teilfreistellung; new country = one entry + one test | None |
| **Rebalancing** | Tax-aware, FIFO, targets by holding/type/region/sector, fee-aware, quarterly band alerts. *"Rubo never places trades."* | The **"compute the trades, never execute"** line is the right shape for Afon's confirm-gate |
| **Free data, no key** | Frankfurter/ECB, World Bank, FRED (~841 k series), ECB SDMX, BIS, Blockchain.com | **FRED and the BIS policy-rate set are worth adding to Afon** if recession-detection ever moves out of Rubo |
| **Ops** | `bun run health` classifies every provider `ok`/`plan`/`dead`; `/cost cap 5`; `.rubo/scratchpad/*.jsonl` per query; 236-question LangSmith eval | **`health` is the model for Afon's provider gates.** Afon learned this session that groq models 404 and minimax 401s; a health sweep would have said so in one command |
| **Channel profiles** | CLI vs Telegram style, pulled from config into the system prompt | Cheap and worth copying |

---

## 2. Jarvis / Afon — 160 tools, 50 subsystems

| band | state | integration |
|---|---|---|
| Task/PM, Knowledge, Media, Code/CLI, Calendar, Infra | **strong** | **`Graphify-Labs/graphify` is already installed and running in Afon** — see §0.3 of `INTEGRATION-MATRIX.md`. `graphify-out/graph.json` is 6.3 MB, updated 2026-10-08; `.graphifyignore`, `scripts/routing_manifest.py`, `graph_prune.py`, `graph_fresh.py` all drive it. **Do not re-integrate** |
| Inbox triage | **thin** | `Triage` label model; `kill-the-newsletter`; build the follow-up tracker yourself |
| SecOps | **absent** | `Cowrie`, `nuclei`, `subfinder`, `trivy` on a schedule into Afon's security ledger |
| CalibCalibration 63.5, weakest | **real deficit, measured** | **Port Rubo's `/judgements` Brier harness.** Not more prompts |
| Secrets in `.env` | weak | **sops + age**, not Infisical (licence unverified) |

---

## 3. Coding agents — Claude Code and MiniMax Code

Same plugin ecosystem serves both; all four below are local-first.

| tool | licence | why it earns its place |
|---|---|---|
| **REA** `morluto/rea` | **MIT**, 39.9k★, 6.2k forks | *"Reverse engineer anything with agents, from app behavior down to native binaries."* Topics already include `claude-code`, `agent-skills`, `mcp`, `ghidra`, `decompiler`, `binary-analysis`, `ctf`. Ships a lawful-use disclaimer. **The best fit for your "RE skill" requirement** |
| **Ponytail** `DietrichGebert/ponytail` | **MIT** | YAGNI enforcement: standard library first, no speculative abstractions. Claims −54 % code, −20 % cost, −27 % time. Supports Claude Code, Codex, Copilot CLI, OpenCode, Gemini CLI, Cursor, Cline, Windsurf. **Pairs with Graphify as `check before you build`** |
| **Graphify** `Graphify-Labs/graphify` | **Apache-2.0**, 124,970★ ✅ | **Already integrated and running in Afon** — `graphify-out/graph.json` (6.3 MB, 2026-10-08), `.graphifyignore`, `scripts/routing_manifest.py`. The old "two repos share this name" warning was a false alarm; the confusion was with Afon's own internal graphify namespace |
| ~~codegraph~~ | — | ❌ **Withdrawn — 404.** The "auto-syncs, names Hermes" claim could not be confirmed |

**Verified 2026-10-09 against the GitHub API.** Both popularity figures turned out to be
accurate to within 0.5 %, not aggregator inflation:

- `DietrichGebert/ponytail` — **159,426★**, MIT, last push 2026-10-08 ✅
- `Graphify-Labs/graphify` — **124,970★**, Apache-2.0, last push 2026-10-09 ✅

The earlier caution in this document was wrong and is retracted. Licences and capabilities
were corroborated; the star figures were too.

`codegraph` — **withdrawn.** `CodeGraphContext/CodeGraph` returns HTTP 404. The claim that it
auto-syncs and names **Hermes** among its clients could not be confirmed by any source.

---

## 4. MiniMax Design — proprietary, no integrations available

Four parallel agents, node-graph canvas, local-first assets, Skills market. **Nothing here
can be vendored.** Two things worth borrowing as *ideas*:

- **Four specialised agents per production**, each owning one modality — Copy / Image /
  Video / Audio — then merged. Afon's fleet has no modality split.
- **Review checkpoints before irreversible steps** — "At key checkpoints, Agent asks for
  your direction before moving forward." That is the same instinct as Afon's confirm-gate,
  applied to generation rather than to sending.

And one competitive note: its **Audiobook skill** sits on the Bookroom SDK's path.

---

## 5. Agent Fleet — Pydantic-AI, Hermes, OpenClaw (83 utilities)

Per my earlier gap analysis: **~20 of the 83 are Jarvis's**; the business-ops half (sales,
support, legal, procurement) is nobody's job today and should stay that way until the
charter says otherwise.

| need | integration |
|---|---|
| Agent identities / a11y email | **AgentMail** (MIT — no GitHub repo could be confirmed) or **`panda-sandeep/dearagent`** (AGPL, Cloudflare Worker, 15 MCP tools, exists ✅) |
| Knowledge surface | **Tolaria** (AGPL — disproportionate) or **`danielmiessler/LifeOS`** (MIT, 19,366★ ✅, last push 2026-09-04) |
| Code knowledge across the fleet | **Already in use** — `Graphify-Labs/graphify` (Apache-2.0, 124,970★ ✅) drives `graphify-out/` and the routing manifest. ~~codegraph~~ **withdrawn, 404** |
| Catching the business in your own agents | **`cowrie/cowrie`** + **`projectdiscovery/nuclei`** + `trivy` |
| Shared scheduling across agents | Rubo's gateway pattern: cron lives in one daemon, sessions sync |

---

## 6. What I would start, in order

Re-verified 2026-10-09. Full evidence in [`INTEGRATION-MATRIX.md`](INTEGRATION-MATRIX.md).

1. **`lm-evaluation-harness` + `conformal-prediction`** (MIT ✅) — Brier/ECE and
   reliability curves for JEv arbitration, plus the abstain recipe for "I don't know".
   This is the instrument the measured 63.5/100 calibration category has been missing.
2. **Port Rubo's `/judgements` Brier harness into Afon** — same instrument, already in your
   own codebase, MIT.
3. **Install Ponytail** (MIT, 159,426★ ✅) — prompt-only, zero code, cheapest win available.
   REA (MIT ✅) alongside it if reverse-engineering is a real use case.
4. **`makenotion/notion-mcp-server`** (MIT ✅) — ten hand-rolled Notion tools become one
   maintained server that tracks API changes for you.
5. **`ActivityWatch` + `screenpipe` + `RapidOCR` + `ollama`** — screenshots stop leaving the
   machine and `describe_screen` gains a local VLM.
6. **`langgraph`** (MIT ✅) — durable checkpointing, and its interrupt primitive is what
   `approve_action` should bind to.
7. **Rubo's `health` sweep as a gate** — Afon discovered groq 404s and minimax 401s by
   reading logs; this makes it one command.
8. **Rubo's `devils-advocate` subagent** — the structural answer to "the model argues for
   its own case."

**Blocked:** `litellm`, the top provider-failover candidate, returns **NOASSERTION**. Read its
LICENSE before wiring it in.

**Do not start** with MiniMax Design integrations (none exist) or with the business-ops
half of the 83.

---

## 7. Still unverified — and I will not guess

| item | why |
|---|---|
| `BerriAI/litellm` licence | GitHub returns NOASSERTION. Top failover candidate — read it by hand |
| `mediar-ai/screenpipe` licence | NOASSERTION; recommended for screen privacy |
| Infisical's current licence | changed historically; **use `FiloSottile/age` (BSD-3-Clause ✅) instead** |
| AgentMail's GitHub repo | product exists, no repository confirmed |
| Ghost-Downloader-3 | repo URL seen, not fetched; the name suggests a download accelerator, not a utility |
| `pnpm`-style repo paths for 31 projects | existence confirmed by HTTP 200; **licence not yet read** |