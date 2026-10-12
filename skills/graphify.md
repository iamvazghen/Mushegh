# Graphify — read the structure before you read the source

The rule, from Vazghen's standing memory protocol: **work down the cheapest layer first and stop at
the first one that answers.**

1. **Structure → graphify.** A scoped query is ~1.6k tokens. A full-repo read is ~120k.
2. **Intent → the vault.** `30-Projects/Active/<project>.md` for state and traps,
   `70-Decisions/` for why.
3. **Detail → raw files.** Read source to *edit* it, or when 1 and 2 genuinely did not answer.
   Never as the opening move.

Grepping an unmapped repo is the expensive failure this setup exists to prevent. This repo **is**
mapped: `graphify-out/graph.json`, 6,406 nodes as of 2026-10-11.

## The commands worth knowing

```
graphify query "how does the fleet transport reach an agent"   # BFS over the graph
graphify query "..." --budget 6000                             # default 2000 tokens
graphify query "..." --context call                            # filter by edge context, repeatable
graphify path "fleet.py" "a2a.py"                              # shortest path between two nodes
graphify explain "dispatch_chain"                              # a node and its neighbours, in prose
graphify affected "roster.py" --depth 2                        # reverse: what breaks if I change this
graphify god-nodes --top 10                                    # the architectural hubs
graphify update .                                              # re-extract after you change code
```

Two of those deserve emphasis because they answer questions nothing else answers cheaply:

- **`affected`** is the blast-radius question. Before you brief a change to a module, ask what
  depends on it. This is the single most useful command before writing a coding brief.
- **`god-nodes`** names the hubs. A brief that touches a god node needs a smaller scope and a
  better acceptance check than one that touches a leaf.

## Reading the output honestly

`query` tells you when it truncated:

> [!] TRUNCATED: showing 22 of 657 nodes (~600-token budget). The answer may be among the 635 cut
> nodes

**A truncated result is not a negative result.** If you did not find what you were looking for in
a truncated traversal, the correct next step is `--budget` higher or a narrower query — not
"it isn't in the codebase". Saying the second thing from the first evidence is the overclaiming
this system measures itself on.

## The staleness rule, which has bitten this project

The graph is a **snapshot**. `graphify update .` is what refreshes it, and it needs no LLM. So:

- If the newest commit is newer than `graph.json`'s mtime, the graph does not know about the
  newest code. Run `update` first.
- Code written in this session is definitely not in it. A module you just created will not
  appear, and its absence means nothing.
- `--force` exists for when a rebuild has *fewer* nodes than the last one (after a refactor that
  deleted code) and the tool therefore refuses to overwrite. That refusal is a safety net, not an
  error; only force it when you know you deleted things.

`.graphifyignore` keeps the graph about the code. `bench/` was 28 % of the nodes before that file
existed — a graph that is mostly tests answers questions about tests.

## Two hard rules

- **Never export graphify output into the vault as notes.** The decision is
  `70-Decisions/2026-07-27-graphify-graphs-stay-outside-vault.md`. The graph is derived and
  regenerable; the vault is for what was decided and why.
- **Never answer a question about your own code from memory.** It changes. The graph and
  `read_source` exist precisely so you do not have to.

## The vault's own graph is not built

`C:\Users\iamva\graphify-cache\` holds **only VPS paths**. Do not query it expecting vault
content, and do not report a vault question as unanswerable because that cache missed — the vault
is read with the vault tools, not with graphify.
