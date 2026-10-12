# Your architecture — a map of your own codebase

Read this before changing anything, Mushegh, so you edit the right file. Repo root is `C:\Mushegh`.

## Two processes
- **edge** (`src/mushegh/edge/`) — runs on the laptop: mic → wake word → VAD → STT → sends the final
  transcript to the brain → speaks the streamed reply (TTS). Audio stays local. Entry:
  `python -m mushegh.edge.assistant`. Key files: `assistant.py`, `brain_bridge.py`, `audio_devices.py`,
  `device_profile.py`.
- **brain** (`src/mushegh/brain/`) — your mind: reasoning loop, memory, tools. Can run in-process
  (edge imports it) or as a WebSocket server (`brain/server.py`, `python -m mushegh.brain.server`) so
  the phone/glasses share one brain.

## The brain, file by file
- `agent.py` — `MusheghAgent`: the reasoning loop. Builds the tool list, runs the LLM, executes tool
  calls (max `_max_tool_iters`), trims history, journals on `end_session()`. **This is the core.**
- `llm.py` — `LLMClient`: OpenAI-compatible calls to freellmapi with a model fallback chain
  (`settings.llm_chain`). `complete()` (tool-calling) and `stream()` (token stream).
- `context.py` — `build_system_prompt()`: persona + `memory/*.md` + recent learned facts +
  voice/clarify/confirm rules. `validate_vault()` checks L3. **Editing this changes his whole voice.**
- `memory.py` — `MemoryStore`: L1 learned facts + L2 journal (Markdown). `recall()` blends keyword +
  optional semantic. Module-level `STORE`.
- `cache.py` — L4 hot-cache (`CACHE`): in-process TTL, fail-open. No daemon (O3.2).
- `semantic.py` — L5 optional embedder (`INDEX`); no-op without `sentence-transformers`.
- `proactive.py` — Phase 10 tick: budget, quiet hours, `confirm_required`/`needs_clarification`,
  `CONFIRM_TIER`. `health.py` feeds it; `modes.py` (focus/lockdown) gates it.
- `audit.py` — redacted JSONL trail of every tool call. `fleet.py` — the gated OpenClaw delegation.
- `protocols.py` — password-gated system routines (goodnight/phoenix/ragnarok).

## Tools (`src/mushegh/brain/tools/`) — how you add a capability
Every tool module exports `SCHEMAS` (OpenAI function schemas) + `HANDLERS` (name → async
`handler(args:dict)->str`). They're merged in `tools/__init__.py` `_MODULES`. Each handler **must
degrade gracefully** — return a speakable string, never raise (use `base.py`: `not_configured`,
`tool_error`, `clip`, `http_get/http_post`). See `read_skill('adding-a-tool')`.

## Config & tests
- `config.py` — one `Settings` (pydantic-settings, env prefix `MUSHEGH_`). Every knob lives here.
- `bench/run_all_tests.py` — the gate. Each phase has a `bench/test_phase*.py` (hermetic, prints
  `=== N/N checks passed ===`). Add a test for anything you build and register it in the runner.
- `docs/ROADMAP.md` — phase status. `docs/BENCHMARKS.md` — what to fine-tune.

## Personality & memory (Markdown, no code)
`personality/Mushegh.md` is who you are; `memory/*.md` is what you know about Vazghen. These are
injected into the system prompt — keep edits tight (prompt size is a measured cost).
