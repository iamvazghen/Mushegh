# S24 — Knowledge & World Model

> **One line:** Paused. What survives is the honesty about what it does not know; the relation layer that lied is scheduled for deletion.
> **Status:** **removed 2026-10-04 (M04)** — D-26's decision is now carried out, not just recorded. `graph.py` and `tools/graphmem.py` are deleted, the `graph` tool group is unregistered, the L5b recall layer is gone, and `what_i_dont_know` no longer speaks from a store the owner had stopped trusting. `world_model.py` survives: it is goals and events, not relations. **24.F1 moved `done` → `in-progress` on 2026-10-04**: its gate could not run at all (it imported the deleted `graph.py`), and the entity merge it specifies — `same_entity`'s high-threshold difflib match — is implemented and asserted but is called by neither lookup that matters, so "one person, one node regardless of spelling" is not what the system does · **Registry:** S24 · 1/2 floor, 0/0 raise, 0/0 elite
> **Milestones:** M04 · **Decisions:** D-26, D-25, D-22

## Purpose

It existed to hold a model of what the owner is trying to do, so proactivity could reason
forward instead of reacting to hard-coded signals. The model part failed. The vector
knowledge graph "lied constantly by pulling stale, irrelevant semantic noise" and consumed
weeks of indexing for negligible utility (D-26). Losing multi-hop associative queries is
the accepted cost, and the system pauses rather than being scheduled to improve.

Two things survived the experiment, and they are the reason the document exists. Entity
resolution: one person, one node, whatever the spelling or the channel. And the ability to
state what the model does **not** know about an entity when asked — which is the behaviour
that the failed layer most conspicuously lacked, since a graph that answers confidently
from stale edges cannot admit ignorance.

One behaviour moves rather than dies. Belief revision on contradiction, with an audit line
(24.R2), becomes part of S30's tombstone rule: the recent explicit correction wins, the
loser is written to the audit log, nothing is silently deleted (D-25). That is now S30's
work, not this system's.

**The gap, stated plainly.** What exists today is an index of the owner's files with
entity resolution on top. It is not a model of their life. `24.R3` — consulting the model
in the prompt path so it shapes answers rather than only answering tools — is paused, and
so is `24.E1`, the dated, sourced, entity-grounded project briefing. Nobody should read
this document as a claim that Afon knows what the owner is doing.

If it is absent, the owner loses two things and keeps everything else: no admission of
ignorance, and no correction when two stored facts disagree. What must not come back is the
relation layer, and M04 is the record of why.

## Structure

| Path | Role | Fate under M04 |
|---|---|---|
| `src/afon/brain/world_model.py` | `Goal`, `WorldModel`, `what_i_dont_know()` | named for deletion in §B, but it also holds both completed floors — see open questions |
| `src/afon/brain/graph.py` | `GraphMemory`, a no-server sqlite triple store; the 607 inferred edges | **removed 2026-10-04 (M04)** |
| `src/afon/brain/semantic.py` | `VectorStore`, `SemanticIndex`; embedding cosine blended into keyword recall, graceful without embeddings | edge indexing goes; whether the semantic recall goes with it is undecided |
| `src/afon/brain/docstore.py` | The vault mirror | stays; markdown remains authoritative (D-22) |
| `src/afon/brain/contacts.py` | The contact book the entity-resolution gate is measured against | stays |
| `src/afon/brain/tools/graphmem.py` | The tool surface over the graph | **removed 2026-10-04 with its store** |

Storage is ordinary: the graph and the vector index are sqlite files —
`memory_graph_db_path` (default `<repo>/afon_graph.sqlite`) and
`memory_vector_db_path` (default `<repo>/afon_vectors.sqlite`), both configured in
`src/afon/config.py` — plus the vault markdown, which is the human source of truth and wins
every disagreement (D-22). Under D-02 a graph store is not an argument for a second
database.

The deletion is deliberately a subtraction with no replacement: recall keeps working on
keyword and layer lookup, and gets no graph edges back. M04's done-when is explicit —
edge indexing gone, the 607 inferred edges dropped, recall latency holding or improving,
markdown still winning.

## Goals

1. One person, one node, whatever the spelling or the channel. Threshold: **0** duplicate
   person nodes for the owner's own contact set.
2. Asked what is known about an entity, the system says what it does not know. Threshold:
   **100%** of such answers carry an explicit unknown.
3. The relation layer is deleted, not maintained. Threshold: **0** inferred edges, **0**
   graph-edge indexing on the recall path.
4. Recall latency holds or improves after the deletion, on the same query set. Threshold:
   no regression against the recorded pre-deletion p95.
5. Belief revision writes an audit line and never silently overwrites. Threshold: a
   superseded fact is **0** present in recall and **1** present in the audit log (D-25).
6. Markdown wins every disagreement between the vault and the database. Threshold: **100%**
   of conflicts resolved to the file (D-22).
7. The model is consulted in the prompt path only if it earns it. Paused, so: **0** new
   work on 24.R3 rather than a threshold.

## Benchmarks

- **G1** · B1 · `bench/test_proper_nouns.py` and `bench/test_contacts.py` — the registry
  records 22 and 41 cases respectively, with no date attached. Threshold 0 duplicate person
  nodes. Last: **not yet measured**.
- **G2** · B1 · `bench/test_world_model.py` — the registry records 36 cases, no date.
  Threshold 100% of "what do you know about X" answers carry an explicit unknown. Last:
  **not yet measured**.
- **G3** · B1 · planned structural test: nothing on the recall path opens the graph store.
  No such test exists; `bench/test_graph_memory.py` tests the store this milestone
  deletes, so it goes with it. Threshold 0 opens. Last: **not yet measured**.
- **G4** · B5 · recall p95 over a fixed query set, before and after the deletion. Threshold:
  no regression against the recorded pre-deletion p95. Same set, same hardware, both numbers
  recorded. No run has been taken; M04 requires it. Last: **not yet measured**.
- **G5** · B1 · `bench/test_world_model.py` for the revision half, with the tombstone half
  verified in S30's own gate. Threshold 0 silent overwrites. Last: **not yet measured**.
- **G6** · B1 · no dedicated test named; the property is that a mirror can lose to a file.
  Threshold: **100%** of conflicts resolved to the markdown. Last: **not yet measured**.
- **G7** · none — deliberately. 24.R3 is paused under D-26, and a benchmark here would be a
  reason to keep working on a deleted layer.
- **24.E1** · B3 · a dated, sourced, entity-grounded briefing for "what's going on with this
  project". Threshold: **100%** of claims dated and sourced, **0** unsourced assertions.
  Paused with the system. Last: **not yet measured**.

## Failure modes

- **A stale inferred edge is quoted as fact.** The worst failure this system ever had, and
  the reason for D-26: a confident, wrong, well-formatted relation the owner cannot tell from
  a true one. Diagnose: `sqlite3 afon_graph.sqlite "select count(*) from triples;"` at the
  configured `memory_graph_db_path`, and the tool name in the audit lines.
- **Deleting the layer breaks recall.** The honest risk, because every green test in this
  area is B1-only and a mock agrees with whatever the code does (D-43). Diagnose: M04's
  own p95 comparison over the same query set, and `bench/test_memory_autorecall.py` for
  the recall path that must survive.
- **A contradiction is resolved silently.** The recent correction wins and the old fact
  disappears with no trace, so the system can no longer explain itself. That is a D-25
  violation. Diagnose: the audit log for the revision, and
  `sqlite3 afon_vectors.sqlite` for what recall still holds.
- **The database and the vault disagree.** Markdown must win (D-22). Diagnose: compare the
  file and the row; the file is correct by definition, and the cache is a cache.
- **Something re-adds a graph tool.** `src/afon/brain/tools/graphmem.py` was the handle, and
  a green `bench/test_graph_memory.py` made deletion look like a regression. Both were
  removed 2026-10-04 with the store, not against the decision.

## Open questions

1. ~~REGISTRY-RECONCILIATION.md §B names `src/afon/brain/world_model.py` for deletion, and
   both completed floors (24.F1 entity resolution, 24.F2 the unknown) live in that file.
   Which survives M04 — the file, or the two behaviours moved elsewhere?~~ **Answered in part
   2026-10-04.** `world_model.py` survives and 24.F2 stands. 24.F1 did not, and not because of
   the file: it depended on the *relation layer* for its "one node" half, so deleting the graph
   deleted the capability while the task stayed marked `done` with a gate that could no longer
   start. It is now `in-progress` with the loss stated. The surviving half — the fuzzy merge in
   `shared/entities.same_entity` — works and is asserted; what is missing is that
   `ContactBook.resolve` and L1 recall never call it. That is a wiring decision about who an
   outbound message may be addressed to, so it is the owner's, and it is the one open item left
   here.
2. Is losing multi-hop associative queries still a theoretical cost, or did the owner
   actually ask for one of those queries and get a worse answer?
3. M04 says "delete the graph relation layer" and §B says "semantic edge indexing". Those
   are narrower than deleting `src/afon/brain/semantic.py`, which is also the only layer
   that retrieves by meaning rather than keyword. Is the semantic recall staying?
