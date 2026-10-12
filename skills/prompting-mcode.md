# Prompting mcode (MiniMax Code) — the first fallback

`mcode exec` is reached when **Claude Code failed** — a non-zero exit or a parser verdict, never a
hunch (`read_skill('coding-pipeline')`). It is npm `@minimax-ai/code`, and of the three CLIs in the
chain it has the richest non-interactive interface, which changes how you brief it.

## The invocation Mushegh actually uses

```
mcode exec --output-format stream-json --prompt-mode coding --permission smart "<brief>"
```

Measured off its own `--help` on this host, not assumed:

- **`--output-schema <schema>`** takes a JSON Schema file or an inline object and enforces it on
  the final answer. This is the one thing none of the other two can do, and it is worth reaching
  for: it pushes the typed boundary one process outward, so the executor cannot return an
  unvalidated blob even in principle. Use it whenever you need a *shape* back rather than prose.
- **`--prompt-mode coding`** is one of `tui | coding | work`. `coding` is correct for a repo
  brief; the default `tui` is tuned for an interactive session.
- **`--permission smart`** (`smart | full | off`) stays at `smart` on purpose. The executor
  already runs in a throwaway worktree, so `full` would spend the bound and buy nothing.
- **`--cwd`**, **`--timeout`** (`30s`, `2m`), **`--max-steps`** bound the run.
- **`-o / --output-last-message <path>`** writes just the final message to a file — the cheapest
  way to get an answer without parsing a stream.
- **`--file <path>`** attaches a file, repeatable. Better than pasting a file into the brief.
- **`--system-prompt` / `--append-system-prompt`** (and their `-file` variants) replace or extend
  its identity for one process. This is where a standing rule belongs, not in the brief body.

`mcode plugin` exists too, and it matters for the weekly self-review: a proposal can actually land
somewhere.

## How the brief differs from Claude Code's

It is reached **after a failure**, so the most valuable sentence you can add is the one Claude Code
could not get past:

> Claude Code failed this with `ModuleNotFoundError: mushegh` when it ran the test. The suite
> needs `src/` on the path — `bench/*.py` do `sys.path.insert(0, .../src)`. Same task: <brief>.

Carrying the failure forward is the whole point of a fallback. A fallback that re-runs the
identical brief is a retry, and a repeat of a failure is not a second attempt.

Beyond that:

- **Be more explicit about steps than you would with Claude Code.** It follows an instruction
  sequence well; it explores a little less eagerly. Name the files.
- **Use `--output-schema` instead of asking for a format in prose.** "Return JSON with keys
  `changed`, `tests_run`, `passed`" belongs in a schema, where it is enforced.
- **Bound it with `--max-steps`.** An agent with no step ceiling on a brief it cannot do will
  spend the whole timeout discovering that.

## Anti-patterns

| pattern | why it fails |
|---|---|
| Re-sending Claude Code's brief verbatim | that is a retry; carry the failure forward |
| Asking for a format in prose when a schema exists | prose formats drift; `--output-schema` does not |
| Widening `--permission` to `full` | the worktree already is the bound |
| Pasting a long file into the brief | `--file` attaches it without burning the prompt |
| Trusting a cheerful transcript | `Result.ok` comes from the exit code and the parser |

## The parser caveat, stated honestly

mcode advertises `--output-format stream-json`, so the spec reuses Claude Code's
`parse_stream_json`. That parser is tolerant by design — a line that is not JSON is kept as text
rather than dropped — which is the right default for a stream whose exact event names this project
has not yet seen from a long real run. It is recorded as **reused, not verified**. If mcode's
event names turn out to differ, the symptom is a transcript that reads fine with an error that was
never surfaced; give it its own parser then, don't paper over it.
