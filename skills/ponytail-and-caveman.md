# Ponytail and Caveman — the two disciplines, and which is installed

Both are about spending less, in different currencies. **Ponytail spends less code. Caveman spends
fewer tokens.** They are easy to confuse and they govern different things, so the first thing to be
clear about is what each one actually is on this machine.

| | What it is here | Where |
|---|---|---|
| **Ponytail** | A real, installed Claude Code plugin, v4.7.0 | `~/.claude/plugins/cache/ponytail/ponytail/4.7.0` — commands `/ponytail`, `/ponytail-audit`, `/ponytail-debt`, `/ponytail-gain`, `/ponytail-review`, `/ponytail-help` |
| **Caveman** | A *technique*, not an installed plugin. `JuliusBrussee/caveman`, Apache-2.0, is the reference approach | Already described in `read_skill('prompting')` |

Do not tell Vazghen that caveman is installed. It is a discipline this project borrowed, and
claiming a plugin that is not there is the kind of small false statement that costs trust on
everything else.

## Ponytail — a lazy senior developer, where lazy means efficient

The premise: the best code is the code never written. It is a **ladder**, and you stop at the
first rung that holds.

1. **Does this need to exist at all?** A speculative need is skipped, and you say so in one line.
2. **Does the stdlib do it?** Use it.
3. **Does a native platform feature cover it?** `<input type="date">` over a picker library, CSS
   over JS, a DB constraint over application code.
4. **Does an already-installed dependency solve it?** Use it. Never add a new one for what a few
   lines can do.
5. **Can it be one line?** One line.
6. **Only then**, the minimum code that works.

The ladder is a reflex, not a research project: if two rungs work, take the higher one and move on.

**The rules that follow from it**, and these are the ones to put in a coding brief:

- No abstraction nobody asked for: no interface with one implementation, no factory for one
  product, no config for a value that never changes.
- Deletion over addition. Boring over clever — clever is what someone decodes at 3 a.m.
- Fewest files. Shortest working diff wins.
- Mark a deliberate simplification with a `ponytail:` comment, and when the shortcut has a known
  ceiling, **name the ceiling and the upgrade path**:
  `# ponytail: bag-of-words over domain titles. Embeddings if it misroutes in practice.`
  That comment is the difference between simple-as-intent and simple-as-ignorance.
- **Lazy code without its check is unfinished.** Non-trivial logic — a branch, a loop, a parser,
  a money or security path — leaves ONE runnable check: the smallest thing that fails if the
  logic breaks. An `assert`-based `demo()` or one small `test_*.py`. No frameworks, no fixtures.
  Trivial one-liners need no test; YAGNI applies to tests too.

**Where NOT to be lazy, ever.** Input validation at a trust boundary, error handling that prevents
data loss, security, accessibility basics, and anything explicitly requested. Hardware too: a real
clock drifts and a real sensor reads off, so leave the calibration knob rather than the smaller
model that cannot see the physical world.

And if Vazghen asks for the full version after you proposed the lazy one: **build it, and do not
re-argue.** The pattern is `[did the lazy thing] → skipped: X, add when Y.` One line, then stop.

## Caveman — terse for machines, never for people

Drop grammatical scaffolding, keep every technical fact exactly. Roughly 65 % fewer tokens with no
lost meaning.

```
bad   : Please make sure to update the configuration file so that the retry count is set correctly.
good  : set config.max_retries = 5
```

**Where it applies:** tool arguments, structured output, file contents, a brief to a coding CLI.

**Where it must never apply:**

- anything Vazghen reads or hears — that is `read_skill('voice-style')`'s territory
- a commit message that will be audited: those stay plain English
- any security-relevant text, especially a permission decision

Compressing a permission prompt is how a person approves something they did not read.

## How the two combine in a coding brief

Ponytail decides *what gets built*; caveman decides *how the instruction is phrased*. Both at
once, in a brief to Claude Code:

> `a2a.py`: hoist `settings.a2a_poll_seconds` out of the poll loop. Shortest diff. Stdlib only.
> No new abstraction. Mark any simplification with a `ponytail:` comment naming its ceiling.
> Then run `uv run python bench/test_a2a_transport.py` and show the summary line.

That is terse, checkable, bounded, and it names the discipline rather than hoping for it.

## One boundary worth stating

Ponytail governs what you build, not how you talk. If an explanation is longer than the code,
delete the explanation — **but an explanation Vazghen explicitly asked for is not debt.** A report,
a walkthrough, per-phase notes: give those in full. The rule is against unrequested prose, not
against answering the question.
