# Prompting Mistral Vibe — the second fallback

`vibe -p` is reached when **both Claude Code and mcode failed**
(`read_skill('coding-pipeline')`). By the time work gets here, two agents have already tried, so
the brief you write is not the original one — it is the original *plus what the other two learned*.

## The invocation Mushegh actually uses

```
vibe -p "<brief>" --output json --smart-approve --time-limit <seconds>
```

Measured off `vibe --version` 2.26.1 and its own `--help` on this host:

- **`-p` / `--prompt` is programmatic mode**: send the prompt, print the result, exit. Without it
  you get the interactive TUI.
- **`--output json` emits ONE JSON array of session entries — not JSONL.** This is the one real
  difference from the other two and the reason it has its own parser. A real one-turn run returned
  three entries: `{"type":"message","role":"user"}`, `{"type":"reasoning"}`, and
  `{"type":"message","role":"assistant","content":[{"type":"text","text":...}]}`. The answer is the
  **assistant** message's text; the user entry is your own prompt echoed back, and reading it as a
  result is how a prompt gets reported as an answer.
- **`generationStatus` is its own verdict.** Anything other than `completed` — interrupted by
  `--max-turns`, `--max-price` or `--time-limit` — is a run that stopped early, and its partial
  transcript must not read as a result. `parse_vibe_json` fails the run on it.
- **`--smart-approve`** is the bounded policy; `--auto-approve` / `--yolo` allow every tool call.
  Stay on `--smart-approve`: the worktree is already the blast radius.
- **`--time-limit <seconds>`** makes it write its export and exit **3** rather than be killed. A
  killed process loses the thing that explains what happened, so prefer this to `dispatch()`'s
  deadline doing it.
- **Real budget ceilings exist and are unique to this tool**: `--max-price <dollars>`,
  `--max-tokens N`, `--max-turns N`. Use `--max-price` on an open-ended brief — it is the only
  one of the three CLIs that will stop itself when a job turns out expensive.
- **`--worktree [NAME]`** and **`--workdir DIR`** — it can make its own worktree. The executor
  already does, so do not stack them.
- **`--prompt-file PATH`** reads the brief from a file: use it when the brief contains quotes.
- **`--output-dir DIR`** writes `export.json` with the effective config, token usage, cost and
  stop reason. That file is the honest record of what a run cost.

## What the brief should carry

Everything the first two learned, in one place:

> Two attempts failed. Claude Code could not resolve the import (`ModuleNotFoundError: mushegh`);
> mcode fixed that and then its patch failed `bench/test_a2a_transport.py` on the "one owner per
> domain" assertion, because it added a utility id that already existed. The task: <brief>.
> Constraint: do not add a utility id — the roster is generated from the vault, so the fix is in
> `scripts/sync_fleet_roster.py` or nowhere.

Note what that does: it narrows the solution space with evidence. Two failures are two eliminated
approaches, and handing them over is more valuable than restating the goal.

Then:

- **Set `--max-price`.** Third attempts are where cost runs away unnoticed.
- **Keep the scope smaller than the original brief.** If the whole job failed twice, send the
  smallest piece of it that would unblock you, and do the rest yourself.
- **Ask for the reasoning in the answer.** It emits a `reasoning` entry; a brief that says "say
  which approach you rejected and why" turns the third attempt into information even when it
  also fails.

## Anti-patterns

| pattern | why it fails |
|---|---|
| Sending the original brief a third time | three identical attempts is one attempt, three times |
| Reading the whole JSON array as the transcript | the user entry is your own prompt; only `role: assistant` is an answer |
| Treating `generationStatus != "completed"` as a short answer | it is a run that stopped early — a failure |
| `--auto-approve` because two tries failed | permission was never the reason |
| No `--max-price` on an open-ended third attempt | this is the one tool that would have stopped itself |

## When all three have failed

Say so plainly and stop. Three agents failing the same brief is information about the **brief**,
not about the tools: it usually means the goal is underspecified, the acceptance check is wrong,
or the change belongs somewhere other than where it was aimed. Re-read
`read_skill('architecture-modelling')` and rewrite the brief before spending a fourth run.
