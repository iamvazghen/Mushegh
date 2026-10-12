# S19 — Composio / MCP Integration

> **One line:** Reach the apps the owner has already connected, and the MCP servers he runs, without spending the turn's tool budget on either.
> **Status:** built, not well structured · **Registry:** S19 · 3/3 floor, 0/3 raise, 0/1 elite
> **Milestones:** none in [../ROADMAP.md](../ROADMAP.md) · **Decisions:** D-62, D-04, D-06

## Purpose

Composio fronts thousands of OAuth-managed actions across the apps the owner has connected
— GitHub, Slack, Drive, Sheets, Linear. Advertising them all would spend the whole per-turn
schema budget before the model picked a tool, so this system exposes **two** tools and a
catalogue summary instead. The failure it exists to prevent is written down at the top of
`src/mushegh/brain/composio_catalog.py`: with no visibility of what is available, the model
answers "I can't do that" about work one `composio_find_tools()` call away.

The MCP half is the same idea from the other side. An external stdio server joins Mushegh's
normal tool registry instead of getting a second execution path of its own.

It refuses two things. It refuses to offer an app that is not connected — the search is
scoped to the owner's active toolkits. And it refuses to imply capability it cannot back:
without a key, both paths return `is_not_configured` and nothing softer. If this system
were absent the owner would keep a working assistant with a narrower belt; what would
break is breadth, and the honest failure is a spoken "not configured", never a
plausible-sounding error.

## Structure

All of it runs **in the brain process** on the always-on host. There is no second daemon
and no distinct security boundary, so under D-42 this is a part of the S03 tool belt
rather than a system that justifies itself.

| Path | What it holds |
|---|---|
| `src/mushegh/brain/tools/composio.py` | The two schemas — `composio_find_tools`, `composio_run_tool` — plus `_context()` (user id + active toolkits) and toolkit keyword hints |
| `src/mushegh/brain/composio_catalog.py` | Disk-cached catalogue: `refresh()`, `compact_summary()`, `long_tail_lookup()`, `invalidate()` |
| `src/mushegh/brain/mcp_client.py` | `StdioMCPServer`, `MCPRegistry`, `to_openai_schema` — JSON-RPC 2.0 over a child process's stdio, no new dependency |
| `src/mushegh/brain/tool_usage.py` | Durable per-tool call counts, the input to the D-06 cull |
| `src/mushegh/brain/_scheduled_jobs.py` | The off-hot-path job that refreshes the catalogue |

Flow on a turn: the utterance is classified, `src/mushegh/brain/intent_router.py` picks tool
names, `schemas_by_name()` in `src/mushegh/brain/tools/__init__.py` narrows the advertised
family, and the model either calls `composio_find_tools` (a search across connected apps,
served from the cached catalogue) or an MCP tool whose schema was converted by
`to_openai_schema`. Writes are confirm-gated; reads run directly.

What it stores: `~/.mushegh/composio_catalog.json`, the durable usage counts, and one audit
line per call under `audit/`. The credential is `MUSHEGH_COMPOSIO_API_KEY` in `.env`, which is
gitignored and never in the repo.

**Credential budget (D-62).** The charter admits exactly four tokens — Home Assistant,
CalDAV, Matrix, one weather/transit API. The Composio key is not among them, and neither
is any per-app key; Composio's argument is that one credential fronts many OAuth grants the
owner already made. Every further app connected through it has to beat that four-token
list, and S19 does not get a vote in that argument. D-62 was amended on 2026-10-03 because
the first draft described the wrong machine, and the amended credential table now names
S19 among the systems its inventory task (`36.R4`) must account for.

## Goals

1. Only connected apps reach the model. Threshold: **0** unconnected toolkits in any
   narrowed family.
2. A missing credential or unconnected account returns `is_not_configured`, never a
   plausible-sounding failure. Threshold: **100%** of unconnected cases.
3. The catalogue the model reads is a compact summary backed by a disk cache, never the
   raw action list. Threshold: **≤1** account/catalogue fetch per turn regardless of how
   many times `find_tools` is called.
4. MCP tools pass the same schema validation as local handlers (D-04). Threshold:
   **100%** converted and validated, **0** raw-string handlers.
5. Per-tool call counts survive the daily restart, so D-06 culling is decided on data.
6. One declared timeout and retry policy, shared with S20, not one per module. Threshold:
   **0** tool modules opening their own HTTP client.
7. MCP server health and last-success are readable by the owner. Threshold: **1**
   last-success timestamp per configured server, **0** "unknown".

## Benchmarks

- **G1** · B1 · gate `bench/test_catalogue_narrowing.py` — planned, the file does not exist
  yet (19.R1). Threshold 0 unconnected toolkits. Last: **not yet measured**.
- **G2** · B1 · `bench/test_composio_connect.py`, `bench/test_composio_accounts.py`,
  `bench/test_no_result_sentinels.py`. Threshold 100% of unconnected-account cases return
  the not-configured sentinel. Last: **not yet measured**. 19.F3 is `done` in the registry,
  but the system's only status evidence is `unverified-import`, so there is no dated run to
  record here.
- **G3** · B1 · `bench/test_composio_context_cache.py`. Threshold ≤1 `/connected_accounts`
  call per turn and 0 memoised failures. Last: **not yet measured**.
- **G4** · B1 · `bench/test_mcp_client.py`. Threshold: every advertised MCP tool converts
  and validates. Last: **not yet measured**.
- **G5** · B1 · `bench/test_tool_usage.py`. Threshold: counts survive a process restart.
  Last: **not yet measured**.
- **G6** · B1 · `bench/test_api_policy.py`, the table in `src/mushegh/brain/tools/base.py`.
  Threshold 0 self-declared HTTP clients outside the policy. Last: **not yet measured**.
- **G7** · B5 · last-success per MCP server, read from the HUD surface. Threshold: **1**
  timestamp per configured server, **0** "unknown". No drill written yet (19.R2). Last: **not
  yet measured**.
- **19.E1** · B3 · three real Composio-backed workflows running unattended for seven
  consecutive days with no manual repair — the D-43 bar. Threshold: **3** workflows, **7**
  days, **0** manual repairs. Last: **not yet measured**.

## Failure modes

- **No key, or the key is wrong.** The router advertises nothing useful and the turn ends
  in a spoken not-configured note. The owner sees Mushegh declining work it has done before.
  Diagnose: `python -c "from mushegh.config import settings; print(bool(settings.composio_api_key))"`,
  then `journalctl -u mushegh-brain -n 200 --no-pager | grep -i composio`.
- **Catalogue stale or missing.** `~/.mushegh/composio_catalog.json` absent or older than the
  last app connection; the model falls back to "I can't" because the summary is empty.
  Diagnose: `ls -l ~/.mushegh/composio_catalog.json` and the same journal grep for
  `composio_catalog.refresh`.
- **Composio 5xx or rate limit.** A remote outage becomes a failed turn. The policy table
  classifies it as `unavailable` and retries as declared; if the retry budget is spent the
  turn reports the failure rather than inventing a result. Diagnose: the audit lines under
  `audit/`, filtered on the tool name.
- **MCP child process dies mid-call.** The turn errors. There is no supervisor, so the
  failure repeats until the brain restarts. Diagnose: `journalctl -u mushegh-brain | grep -i
  mcp` — the gap is that this is the one failure here with no repair path (19.R2).
- **The belt grows sideways.** Every connected app widens what the model can be offered.
  The counter is usage: `sqlite3 "$MUSHEGH_TASKS_DB_PATH"` for the task queue — the default is
  blank in `src/mushegh/config.py:445`, which means `<repo>/mushegh_tasks.sqlite` (stated the same
  way in `src/mushegh/brain/tasks.py:9`) — and `src/mushegh/brain/tool_usage.py` for what was
  actually called, which is what D-06 culling reads.

## Open questions

1. Does the Composio key earn a place beside the four tokens in D-62, or is S19 the first
   thing to go if the answer is no?
2. Composio and MCP are two mechanisms behind one file name. They share a schema boundary
   and nothing else — worth splitting, or worth describing honestly as one router?
3. 19.R3 is shared with S20, which is dark. Does that work wait for the M07 outcome, or is
   it S19's to finish alone?
