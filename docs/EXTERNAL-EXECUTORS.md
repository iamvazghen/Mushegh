# External executors — the SDK and open-source survey

Written 2026-10-06, for the owner's direction of the same date: Mushegh routes work to the
executor that is best at it, and owns the voice, the judgement and the typed boundary
itself. This file sizes each route and names the library that should carry it.

**Authority:** none. [DECISIONS.md](DECISIONS.md) D-79–D-87 carry the decisions this
survey informed; `TODO.md` Parts U–X carry the work. This is the research behind both.

**The filter every row below had to pass** is [PRINCIPLES.md](PRINCIPLES.md) §1 — name the
three commands you would run at 2 AM. A dependency that can only be debugged through its
own dashboard did not make this list.

---

## 1. The rule that decides *how* a capability enters

Three doors, in order of preference, and the order is the whole point:

| Door | When | Cost |
|---|---|---|
| **MCP server** | The capability already ships one | A config line. `src/mushegh/brain/mcp_client.py` already turns any stdio MCP server into namespaced Mushegh tools — `mcp__<server>__<tool>` — with the same schema and handler shape as every native tool |
| **Subprocess adapter** | It ships a non-interactive CLI with machine-readable output | One adapter file implementing the M41 contract |
| **In-repo implementation** | Neither exists, or the external one fails a charter requirement | The full cost, and it needs a reason written down |

We already own the first door, and it is the reason this plan is not eight integrations.
`mcp_client.py` launches **only** servers listed in the `mcp_servers` setting, which is the
security boundary — there is no default server list, and a blank setting means no MCP tools
at all.

---

## 2. The browser — the strongest recommendation in this file

The owner's read is correct on both counts: there is a cluster of Jev browser repos, and
Jev being our engine is exactly why they fit. Their shared architecture is this project's
own charter, arrived at from outside it:

> The page is observed into a **numbered table of elements and the operations available on
> them**. One Jev request picks the operation *and* the target in a single round trip. Jev
> never writes free text — a small text model supplies a field value only when the chosen
> operation is a type. The harness executes.

That is [D-04](DECISIONS.md) (only a typed payload reaches the system) and
[D-72](DECISIONS.md) (the model narrows a surface code produced, and can never widen it) in
a new place. It is not a new idea to evaluate; it is our idea, in a domain where we have
not applied it yet.

| Project | Shape | Licence | Why it matters here |
|---|---|---|---|
| [`Ying-Kai-Liao/jev-browser`](https://github.com/Ying-Kai-Liao/jev-browser) and [`Alexandr-Kravchuk/jev-browser`](https://github.com/Alexandr-Kravchuk/jev-browser) | Node, Playwright. Ships a **library, a CLI *and* an MCP server** | MIT | The MCP server is the cheap door. It also ships a **pause-before-irreversible-action** gate, which is `05.R1` — the open confirm-before-submit task — arriving for free |
| [`browser-use/jev-ultrafast`](https://github.com/browser-use/jev-ultrafast) | Python, Chrome DevTools Protocol. The indexed action space with one Jev round trip per step | — | The **loop shape to copy** if we build in-repo. Published measurements: a Zürich→London flight search in 7.1 s end to end, browser protocol calls cut from 1,092 to 101 across runs |
| [`smartdio/jev-browser-agent`](https://github.com/smartdio/jev-browser-agent), [`AnotiaWang/awesome-jev`](https://github.com/AnotiaWang/awesome-jev) | Experiments and an index | — | Where to look next; not a dependency |

**What none of them give us, and what we must not trade away.** S05 exists for a *visible*
Chromium on the owner's own screen with a persistent profile that keeps his logins — see
[subsystems/05-browser-control.md](subsystems/05-browser-control.md). A headless agent that
drives its own browser somewhere he cannot see is the cloud path we already have
(`web.browse_web`), and the subsystem doc is explicit that conflating the two is how a
headless fetch ends up answering as though he had been watching his screen.

**So the spike question is one sentence**, and it is M49: can that MCP server drive the
browser the owner is looking at, with his profile? Yes → a config line buys most of M48 and
all of `05.R1`. No → we keep `src/mushegh/brain/tools/browser.py` and the `pc_agent` forwarding,
and port only the decision loop.

**Their stated limits, so we inherit them knowingly:** no shadow roots, iframes, canvas, file
uploads or nested scrolling; a `DONE` verdict needs independent verification; the published
numbers are three runs per task on one browser profile, which is a demonstration and not a
reliability benchmark.

---

## 3. Coding — three CLIs, one contract, and the Agent SDK **declined** on 2026-10-06

> **This section was written as a recommendation and is now a record.** It recommended the Claude
> Agent SDK as the adapter. When M41's contract was built the recommendation did not survive
> contact with it, and the honest thing is to say why rather than to quietly keep the prose.

The Claude Agent SDK spawns the `claude` binary as a **separate OS process** and talks to it over a
stdin/stdout JSON message stream, with CLI permission prompts replaced by an explicit permission
mode — already the shape [D-80](DECISIONS.md) requires. The argument for it was that hand-rolling
`subprocess` would mean reimplementing the stream protocol and the permission handling badly.

**What changed:** `src/mushegh/brain/executors/__init__.py` has that shape *and the three invariants
the SDK does not carry*. `claude -p --output-format stream-json` in argv form, `stdin=DEVNULL` so
there is nothing to hand a shell, an environment allowlist **built from nothing** so a secret added
next year is still withheld, and a parser whose verdict can fail a run the exit code passed. Adding
the SDK now would replace working code with a dependency that re-implements those four and would
move the permission decision from [D-08](DECISIONS.md) into a library. One contract already covers
three CLIs; a second adapter shape for one of them is the integration sprawl
[D-01](DECISIONS.md) exists to refuse.

**What M43 actually owed was the landing path**, and that is what got built:
`src/mushegh/brain/executors/landing.py`, gated by `bench/test_coding_delegation.py`.

| Executor | Non-interactive entry | Machine-readable output |
|---|---|---|
| **Claude Code** | `claude -p` (the Agent SDK was declined — see above) | `--output-format stream-json`; **no `--output-schema` equivalent**, so the adapter does not claim one |
| **Codex CLI** | `codex exec` | `--json` gives a JSONL event stream (`thread.started`, `turn.completed`, `item.*`, `error`); **`--output-schema` enforces a JSON Schema on the result** |
| **MiniMax Code** (`mcode`) | `mcode exec [prompt]` | **Resolved 2026-10-06.** This file previously said no first-party MiniMax coding CLI was confirmed. It exists and is installed here: npm `@minimax-ai/code` 0.6.3, with `exec`, `update`, `plugin` and `acp` subcommands read off its own `--help`. The `plugin` subcommand matters for the weekly review — it is a real place a proposal can land. **And `mcode exec` turns out to have the richest interface of the three**, read off its own `--help`: `--output-format stream-json`, `--output-schema`, `--cwd`, `--timeout`, `--max-steps` and an explicit `--permission smart\|full\|off`. The adapter keeps `smart`: the executor already runs in a throwaway worktree (D-90), so widening the policy spends the bound and buys nothing |

**Codex's `--output-schema` is worth noticing specifically.** It lets the *caller* declare the
result shape, which is the typed boundary pushed one process outward — the executor cannot
return an unvalidated blob even in principle. Where an executor offers that, the M41 adapter
should use it rather than parsing prose.

**What does not change.** [D-08](DECISIONS.md) still governs what happens to the diff: a
dedicated branch, a green suite, zero schema migrations, the owner's explicit approval. The
executor produces a diff; Mushegh never applies one on its own authority.

**Where it lands, corrected.** This section used to say `src/mushegh/brain/code_improve.py` is where
the result lands. That module is the *in-house* loop — Mushegh editing his own source with his own
tools — and it was the wrong home for an external executor's diff, because it has no isolation: it
branches the owner's checkout and lets the worker write into it. A coding CLI edits files in its
working directory and hands back no patch, so the proposal would be in the owner's tree before the
first condition had been tested. The external path is therefore
**`src/mushegh/brain/executors/landing.py`**, which gives each brief its own `git worktree` and leaves
the owner's checkout untouched on every refusal — see [D-90](DECISIONS.md).

---

## 4. The fleet — the transport decision is already written down

`src/mushegh/brain/fleet.py` contains the answer in its own docstring. Connecting to the
OpenClaw gateway as an operator requires either an Origin allowlist with ECDSA device
identity, or presenting as a built-in client id — and the module says plainly that
*presenting as a built-in client to pass the allowlist is exactly what a sanctioned path
should not have to do*. Three honest options are named; **option (a) is the one to take**:
run the official `openclaw agent --agent <id> --json` CLI over SSH.

It needs an SSH permission rule and nothing else, it is the same subprocess-with-JSON shape
as every other executor here, and it requires no spoofing. The fleet stays a tool and never
the assistant ([D-05](DECISIONS.md)).

---

## 5. Finance — a subprocess, inside a line that does not move

Rubo is a local TypeScript/Bun research agent that reads public macro sources and reasons
over them by fixed, reproducible rules. As an executor it is the same shape as the others.

**The constraint is not technical.** [D-12](DECISIONS.md) refuses bank feeds, transaction
ingest and personal ledgers on blast-radius grounds, and
[subsystems/40-financial-and-asset.md](subsystems/40-financial-and-asset.md) draws the line
precisely: *the direction of the write*. A ledger file the owner types himself is data he
already had; an ingested feed is his financial history arriving unasked. Mushegh may read that
file and writes nothing into it.

Research delegated to Rubo sits entirely on the readable side of that line, which is why
[D-83](DECISIONS.md) is written narrowly. Anything that ingests statements or places orders
is a different decision and is not taken here.

---

## 6. Books — built, and it taught the survey something

The SDK arrived on 2026-10-06: `bookroom-sdk` v1.0.0, with a `SKILL.md` in its root. It is wired as
one tool, `book`, with four actions — `check`, `outline`, `preflight`, `guide` — in
`src/mushegh/brain/tools/bookroom.py`, gated by `bench/test_bookroom_tool.py`.

**It did not enter through the executor contract, and that is the useful finding.** Section 1's
three doors are ordered by cost, and this went through the third — not because the others failed to
exist, but because the second was *actively worse*:

| Door | Why not |
|---|---|
| MCP server | The SDK ships an HTTP **facade** (`python -m bookroom_sdk serve`) for other-language clients, which is close. But the facade exists so TypeScript can reach Python without holding the keys; Mushegh's brain already *is* Python, so the facade would add a daemon, a token and a port to avoid a problem we do not have |
| Subprocess executor | The `bookroom` CLI has **no `preflight` subcommand**, and `guide` does not preflight on its way in. The one call the SDK says to always make before spending is unreachable from the CLI. A subprocess would also marshal `GEMINI_API_KEY` into a child |
| In-process | The SDK's own first rule: Python holds the keys in the process, and that is the reference implementation |

**The generalisable rule, which belongs in this survey rather than in the decision:** the executor
contract bounds an **agent** — something that acts on its own judgement. A library is a tool.
Routing a library through the contract buys none of its protections and costs its ceremony. The
next capability that looks like an executor should be asked which of the two it is.

**The constraint the owner had to clear, and no longer has to.** This section
originally read:

> The SDK wraps a **separate** application — a flat tree containing
> `book_pipeline.py` — imported from `BOOKROOM_APP_ROOT`, and that engine is not
> in the SDK repository. Every call reaches it, `extract` and `check` included.
> So: install `bookroom-sdk` into the brain's interpreter; set
> `BOOKROOM_APP_ROOT`; set `GEMINI_API_KEY`; optionally `TYPESAFE_API_KEY`.

**That is resolved (D-94).** The nineteen engine modules the SDK calls are now
vendored into the package and installed as package data, so
`pip install bookroom-sdk` is the whole setup. `BOOKROOM_APP_ROOT` is now an
*optional override* for developing against a live checkout. The owner
prerequisite reduces to: install the package, set a key.

The wrapper was verified rather than assumed. Driven over the same book with the
same provider, the bundled engine and the application tree produce a
**byte-identical `study-guide.md`**, the same PDF text, and identical output for
seven of ten artifacts; fifteen of nineteen modules are byte-exact copies and the
four that are not are documented deviations with recorded reasons.

Two defects were found in the process that only running for real would surface:
two clients with different providers silently shared the engine's
module-level configuration, and a manifest generated by one provider recorded
another. Both are fixed, and the second is why provenance is now derived from the
endpoint rather than hardcoded.

**The two other doors are still closed, and for the same reasons.** A reader
reaching for `pip install` on a *hosted* deployment will still not find a
published package, and the CLI still has no `preflight` subcommand; the
`book` tool in `src/mushegh/brain/tools/bookroom.py` is therefore still correct to
call the SDK in-process. What changed is that the third door no longer requires
a second repository.


## 7. Hardware — one correction, and the libraries that carry each layer

**The correction.** The `wyoming-satellite` project is no longer maintained upstream; it has
been replaced by Linux Voice Assistant, which speaks the **ESPHome protocol** and is what
carries the newer capabilities — media player, stop-wake-word, start/continue conversation,
timers. [HARDWARE.md](HARDWARE.md) §6 is right about *what* to buy for H5; a reader
reaching for the obvious satellite library today would reach for the retired one. Wyoming
itself is not retired — it remains the protocol for the **services** (Whisper, Piper,
openWakeWord) behind Home Assistant's Assist pipeline. Satellites speak ESPHome; services
speak Wyoming.

| Layer | Library | Note |
|---|---|---|
| Voice satellites (H5) | `aioesphomeapi` | The ESPHome protocol client. Replaces the retired satellite path |
| STT / TTS / wake services | the Wyoming protocol | Already our stack in a different dress: openWakeWord, Whisper and Piper are what `src/mushegh/edge/` runs locally |
| Home Assistant (H2–H4) | its REST and WebSocket API | No SDK needed. One token un-darkens S28 and delivers M20, the desk lamp — the cheapest real win in [ROADMAP.md](ROADMAP.md) |
| Zigbee (H2) | `zigpy`, through the ZBT-1 | HARDWARE.md §9 conflict 1: **one** coordinator owns the mesh. Green's radio stays unused |
| Matter (H4) | `python-matter-server` | The smart lock is read-only to Mushegh ([D-65](DECISIONS.md)), and `bench/test_blast_radius_refusal.py` already enforces the HA path |
| Wearable (H5) | a FIT file parser | Garmin FIT export, no vendor cloud — the shape [D-57](DECISIONS.md) wants. Un-defers `34.R4` |
| Local vision (H6) | Frigate with a Coral TPU | Frames never leave the house ([D-66](DECISIONS.md)); `bench/test_no_frame_egress.py` already asserts the seam cannot carry one |

**The multilingual gap this survey can close.** [D-78](DECISIONS.md) keeps cloud TTS because
the local engines are English-only *as wired* — one Piper voice, Kokoro pinned to English —
while the owner speaks five languages. Piper publishes voices for ru, uk, de and fr. What is
missing is not a model but a language-to-voice map and a `match` implementation over it.
That is the work that would retire the exception and return the code default to local, and
it is small.

---

## 8. What this survey declines

- **An agent framework** (LangGraph and its relatives) to hold the executor layer.
  [D-77](DECISIONS.md) already declined LangGraph as the cortex, and the reason applies here
  unchanged: the turn loop is measured and gated, and replacing a working system from a
  document rather than a measurement is the inversion this project refuses. M41's contract
  is one Pydantic protocol and one dispatch function.
- **A second MCP client library.** `src/mushegh/brain/mcp_client.py` is ~200 lines of
  newline-delimited JSON-RPC over a child process and already does `initialize`,
  `tools/list` and `tools/call`. Adding the official SDK would add a dependency to replace
  working code.
- **A message bus, a policy service, or a second database** to coordinate executors.
  Declined already as [D-01](DECISIONS.md), [D-02](DECISIONS.md) and
  [D-04](DECISIONS.md); four subprocesses do not change the argument.

## Sources

- [browser-use/jev-ultrafast](https://github.com/browser-use/jev-ultrafast) ·
  [Ying-Kai-Liao/jev-browser](https://github.com/Ying-Kai-Liao/jev-browser) ·
  [Alexandr-Kravchuk/jev-browser](https://github.com/Alexandr-Kravchuk/jev-browser) ·
  [smartdio/jev-browser-agent](https://github.com/smartdio/jev-browser-agent) ·
  [AnotiaWang/awesome-jev](https://github.com/AnotiaWang/awesome-jev)
- [Run Claude Code programmatically](https://code.claude.com/docs/en/headless)
- [rhasspy/wyoming-satellite](https://github.com/rhasspy/wyoming-satellite) (retirement
  notice) · [Home Assistant — Wyoming protocol](https://www.home-assistant.io/integrations/wyoming/)
