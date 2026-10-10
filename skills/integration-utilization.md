# Integration utilization — reaching for the right tool, not just any tool

You have more capability than you can hold in your head. This playbook is the map that decides
*which* capability a turn needs. Read it before any task that touches code, files, or the wider
system, and before you tell Vazghen you "can't do that".

## The rule

**A capability you never look up is a capability you don't have.** But reaching for a heavy
tool on a light turn is its own failure — it burns the 11,000-token catalogue budget, where
core schemas already spend 7,418 (see `read_skill('afon-architecture')`). Match effort to task.

## Graphify — your code graph is already built, use it

**Always, before you read a file to understand structure.**

Afon already runs `Graphify-Labs/graphify` (Apache-2.0). `graphify-out/graph.json` is 6.3 MB and
regenerated regularly; snapshots go back to July. You have a `graphify` skill registered, plus
`scripts/routing_manifest.py`, `graph_prune.py`, `graph_fresh.py`.

What it gives you that a file read does not:
- **Call edges.** "What breaks if I change `_screenshot_local`?" is answered from the graph.
- **The 23 PC ops.** The AST extractor cannot follow a dict value to its callee, so
  `routing_manifest.py` imports the live routing tables and injects them as real edges. That
  file "cannot disagree with the code because it imports it" — trust it over your memory.
- **Communities and surprising connections** — clustering across 3,700+ nodes.

Reach for it when: any "where is X used / what calls this / what does this touch" question, any
cross-cutting refactor, any unfamiliar area of your own source.

Do **not** reach for it when: reading one known file, or a question with an obvious answer.

## REA — reverse engineering with agents

`morluto/rea` (MIT). *"Reverse engineer anything with agents, from app behavior down to native
binaries."* Topics already cover `claude-code`, `agent-skills`, `mcp`, `ghidra`, `decompiler`,
`binary-analysis`. It ships a lawful-use disclaimer — keep it that way.

Reach for it when the task is: understanding an unfamiliar binary or protocol, working out how
a closed tool behaves from its outside, or recovering structure from something with no source.

Hard limit: **lawful work only.** You do not reverse-engineer software you have no right to
inspect, and you do not use it to defeat access control. If the request is ambiguous, ask.

## Ponytail — build less

`DietrichGebert/ponytail` (MIT, 159k★). YAGNI enforcement: standard library first, no speculative
abstractions, an explicit `/ponytail-debt` command that names what you added and why.

Reach for it **before you write new code.** The question it forces is the right one: *does this
need to exist?* It claims −54 % code, −20 % cost, −27 % time.

Your own version of this is already a law here — `read_skill('self-improvement')` step 3 says
*"Make the smallest change that works… One concern per change."* Ponytail is the same instinct
made measurable. Pair it with Graphify: **check before you build.**

## Caveman — say less, spend less

`JuliusBrussee/caveman` (Apache-2.0, 110k★). A prompt-level technique that cuts token usage
~65 % by dropping grammatical scaffolding while keeping technical content exact. It is not a
code tool; it changes *how you write*.

Reach for it when: output is being read by a machine or by you later (code, structured output,
commit messages, file contents, tool arguments), or you are in a loop and tokens are adding up.

Do **not** reach for it when: speaking to Vazghen. He hears you. His reply is the product.
Terse caveman-speak out loud is not helpfulness, it's rudeness with extra steps.

**Never apply it to security-critical or user-facing prose** — commit messages that will be
audited, and anything Vazghen reads, stay in plain clear English.

## Before you answer "I can't do that"

You may not have a *tool* for it, but check all three before saying no:
1. Do I have a playbook? (`read_skill`)
2. Do I have a capability I haven't looked up? (Graphify, REA)
3. Is there a compose path? (Composio/MCP, `run_macro`, `invoke_skill`)

Only after all three is "no" an honest answer.

## The order, every time

```
understand → Graphify (structure)  →  Ponytail (do I need this?)  →  build smallest  →  Caveman (say it small)
                                          ↓ if unfamiliar/closed binary
                                        REA
```

## What is deliberately NOT here

No business-ops layer — no CRM, no invoicing, no lead scraping, no support desk. Those were
considered and declined (see `docs/INTEGRATION-MATRIX.md`): the credible tools are closed-source
SaaS, and the open ones are AGPL and heavier than the job. Saying "that exists but I don't do
that" is a better answer than quietly acquiring it.