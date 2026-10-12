# Prompting Open Design — everything the thing looks like

Open Design owns frontend **exclusively**: websites, landing pages, UI, UX, layout, visual
direction, design decisions. Nothing else comes here, and frontend goes nowhere else
(`read_skill('coding-pipeline')`). It is an MCP server, not a CLI, so its tools arrive namespaced
as `mcp__open-design__<tool>` through `mcp_client.py`.

## The one thing that will be wrong

**The registration goes stale every time the app restarts.** `OD_SIDECAR_CLIENT_ENDPOINT` names a
Windows pipe whose hash changes per launch, so a registration written yesterday points at a pipe
that no longer exists and the whole `mcp__open-design__*` namespace is silently *absent* rather
than broken. Measured on 2026-10-11: the registration named one pipe and the live set was three
others, and the route had been dead. The app says it plainly:

> The Open Design MCP registration is missing its runtime connection. Open the app and refresh the
> MCP registration, then restart this MCP session.

So: **no Open Design tools in the registry is a configuration symptom, not an absence.** The fix is

```
uv run python tools/refresh_open_design_mcp.py        # probes the live pipes, rewrites .env
uv run python tools/refresh_open_design_mcp.py --check # report only
```

then restart the brain, because an MCP session holds its own child process. Never tell Vazghen
"I can't do design work" without running that first.

The app also has to be **running**. There is no headless self-bootstrap: without a live endpoint
the CLI exits with the error above.

## The tools, as they really are (22, read off `tools/list`)

They fall into four groups, and the division matters because it tells you what *you* do and what
Open Design does.

Names are written bare below for readability; **call them namespaced** —
`mcp__open-design__list_skills` lists *Open Design's* recipes while the native `list_skills`
lists these playbooks, and the namespace is the only thing that tells them apart.

**Discover (MCP)**, cheap and read-only, do these first: `list_projects` · `get_project` · `get_active_context` · `list_files` · `list_plugins` · `list_agents`

`get_active_context` first: it returns the project and file **Vazghen has open right now**, or
`{active:false, hint:...}` when nothing is. Asking him which project when this would have told you
is a wasted turn.

**Read (MCP)** — `get_artifact` · `get_file` · `search_files`

`get_artifact` bundles the entry file plus every sibling it references — HTML `<script>`/`<link>`/
`<img>`/srcset, JSX imports, CSS `url()`/`@import` — to depth 3, skipping CDNs. One call instead
of six, and you see the page as a page rather than as files.

**Commission (MCP)** — `start_run` · `get_run` · `cancel_run`

This is the important one, and it changes your job. **`start_run` spawns Open Design's own agent**:
you hand it a prompt (optionally a `skill`, `plugin` + `inputs`, `agent`, `model`) and get a
`runId` back immediately. You then poll `get_run(runId)` until the status is terminal
(`queued|running|succeeded|failed|canceled`); on success it returns a `previewUrl` you can open and
an agent message. `list_skills` is **discovery only — OpenDesign runs the skill, not you.**

So for a real design job you do *not* hand-write HTML through the MCP `write_file`. You commission the run
and report the preview. Hand-authoring a landing page file by file is the thing this tool exists
to replace.

**Write (MCP)**: `create_project` · `create_artifact` · `write_file` · `mcp__open-design__delete_file` · `delete_project` · `collect_brief` · `confirm_brief`

- `create_project` then `start_run` against it is the path for something new.
- `create_artifact` creates one entry file and rejects an existing target; `write_file` overwrites
  and tolerates existing targets, so **`write_file` is the right tool for iterating** on a file
  that already exists, and `create_artifact` is the right one for a new entry.
- `collect_brief` / `confirm_brief` render an interactive brief card to Vazghen. Their draft ids
  and nonces are internal widget data — **never read one out to him or ask him to copy it.**
- `delete_project` requires both an explicit project id **and** `confirm:true`, with no
  active-project fallback. It is permanent, it takes the conversations with it, and it is an
  outward-irreversible action: it goes through the approval gate like any other, every time.

Two MCP tools are named for internal compatibility and must not be repeated to him: `start_vela_login` · `get_vela_login_status` — Open Design Cloud browser sign-in.

## How to write the prompt for `start_run`

It is briefing a designer, not specifying a build. The failure mode here is the opposite of a
coding brief: over-specifying the implementation produces something that satisfies the spec and
looks like nothing.

Give it, in this order:

1. **Who it is for and what they should do.** "A landing page for a rabbit-farm wholesale buyer;
   the one action is requesting a price list."
2. **The content that must appear**, as content and not as markup.
3. **The constraint that is actually a constraint** — a brand colour, a language, a required
   logo, a legal line. Name only the ones that are real.
4. **What good looks like**, in one judgeable sentence. This is the acceptance check in design
   clothing, and it is just as necessary here.

Leave out: pixel values, framework choices, class names, and "make it modern".

## Reporting back

The product is a `previewUrl` and a design. Open it, look at it, and tell him what it actually
does — not that a run succeeded. A terminal status of `succeeded` means the agent finished, not
that the page is right; the same distinction as everywhere else in this system.

If the job has a backend half, that half is a separate brief down the coding chain. Say so.
