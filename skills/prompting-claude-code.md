# Prompting Claude Code — the main coding tool

`claude -p` is where every piece of code work starts (`read_skill('coding-pipeline')`). It is an
*agent*, not a code generator: it reads files, runs commands, and decides what to look at next. So
the brief that works is a brief you would give a competent engineer who has never seen the repo —
not a specification of the diff you already imagined.

## The invocation Mushegh actually uses

```
claude -p "<brief>" --output-format stream-json --verbose
```

Measured facts about that, not assumptions:

- **`-p` / `--print` is what makes it non-interactive.** Without it you get a session that waits.
- **`--output-format stream-json` needs `--verbose`.** One JSON object per line; the `result`
  event carries the final answer, and `is_error` / a `subtype` ending in `error` is a failure
  *even when the process exits 0*. `parse_stream_json` enforces that.
- **There is no `--output-schema`.** mcode has one, Claude Code does not, and the spec does not
  claim one. If you need a guaranteed shape, say so in the brief and verify it yourself.
- **stdin is closed** (`DEVNULL`), so it cannot ask you a question mid-run. A brief that depends
  on a clarification will fail rather than wait, which is why the brief must be self-contained.
- Useful when the work needs it: `--add-dir` for a second directory, `--allowed-tools` to narrow
  what it may do, `--append-system-prompt` to add a standing rule for one run.

## What a good brief looks like

The single highest-leverage habit is the same one `read_skill('prompting')` names: **make the task
checkable.** Claude Code will run the check itself if you give it one.

> In `src/mushegh/brain/a2a.py`, the A2A poll loop re-reads `settings.a2a_poll_seconds` every
> iteration. Hoist it once before the loop. Then run `uv run python
> bench/test_a2a_transport.py` and show me the summary line. Do not touch the hermes path.

Four things that brief has and a weak one does not:

1. **The file and the symbol.** Not "the polling code".
2. **The change, as an outcome.** "Hoist it once before the loop", not "refactor for efficiency".
3. **The check, by command.** It can run it, so it will, and then its claim is evidence.
4. **A boundary.** "Do not touch the hermes path" prevents the helpful extra diff.

## What it is good at, and where to spend the brief

- **Multi-file reasoning.** It will follow a call through four modules. Say the entry point and
  let it walk — listing the files yourself usually makes the result worse.
- **Running its own verification.** Name the test command and it closes the loop.
- **Reading before writing.** It will, if the brief gives it a reason to.

Where briefs go wrong here:

- **Describing a diff instead of a goal.** You will get your diff, including the part you got
  wrong. State the behaviour you want and the constraint, and let it choose the seam.
- **Open-ended scope.** "Clean up the brain module" is an afternoon of unreviewable changes.
  One behaviour per brief.
- **Omitting the bound.** Name the retry count, the cap, the timeout. A brief that leaves a
  number open gets a plausible number invented.
- **No mention of tests.** Then it writes none, and you have an unverifiable diff.

## Discipline to carry in

Say so in the brief, explicitly, because the default is to add:

> Shortest working diff. Stdlib before a dependency. Delete rather than add where you can. Mark
> a deliberate simplification with a comment that names its ceiling. One runnable check, no
> framework.

That is `read_skill('ponytail-and-caveman')` compressed to a paragraph, and it is worth the
tokens every time.

## After it returns

`Result.ok` is the verdict — derived from the exit code and the parser, never from how confident
the transcript sounds. A transcript that says "done!" with `is_error` set is a failure. If it
failed, the chain moves to mcode; if it timed out, it does **not**, because it may still be
writing in that worktree.

The diff is a proposal. It is never applied on your authority.
