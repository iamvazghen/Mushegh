"""Fix #4 and #3, as they survive the relation layer's removal (M04, D-26).

The reviewer still parses `{"facts": [...], "relations": [...]}` in ONE model call, still
writes the facts to L1, and still accepts the legacy bare-array form. What is gone is the
destination for the parsed relations: the triple store was removed on 2026-10-04, so they
are parsed and then deliberately not stored anywhere, rather than being parsed and lost.
That is the honest shape of the change — the behaviour of *noticing* a relation survives,
because a relation is also a fact; the second store that made it stale does not.

Still verified here:
  * one model call extracts both halves;
  * facts land in L1, and the relations key is tolerated rather than fatal;
  * the legacy bare-array form still works;
  * `_parse_facts` and `_parse_relations` still parse both shapes;
  * L5 semantic recall defaults on and degrades to keyword without an embedder.

Hermetic: temp stores, a fake LLM. No network.

    uv run python bench/test_memory_review_learn.py
"""

from __future__ import annotations

import asyncio
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

passed = failed = 0


def check(name: str, ok: bool, detail: str = "") -> None:
    global passed, failed
    if ok:
        passed += 1
        print(f"  [PASS] {name}")
    else:
        failed += 1
        print(f"  [FAIL] {name}  {detail}")


class FakeLLM:
    def __init__(self, content: str) -> None:
        self.content = content
        self.calls = 0

    async def complete(self, messages, tools=None, temperature=0.6, tool_choice="auto",
                       skip_primary=False):
        self.calls += 1
        return SimpleNamespace(content=self.content, tool_calls=None)


CONVO = [
    {"role": "user", "content": "My rabbit farm is in Armavir, which is in Armenia, and I train at 6am."},
    {"role": "assistant", "content": "Noted, sir."},
    {"role": "user", "content": "Keep replies under two sentences."},
    {"role": "assistant", "content": "Understood, sir."},
]


async def main() -> None:
    from afon.brain.background_review import _parse_facts, _parse_relations, review_and_learn
    from afon.brain.memory import MemoryStore

    print("[1] the reviewer extracts facts AND relations in one call, and keeps the facts")
    obj = ('{"facts": ["the owner has a rabbit farm in Armavir.", '
           '"the owner trains at 6am.", "the owner prefers replies under two sentences."], '
           '"relations": [["rabbit farm","located in","armavir"], '
           '["armavir","located in","armenia"], ["owner","trains at","6am"]]}')
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
        store = MemoryStore(base_dir=Path(d))
        llm = FakeLLM(obj)
        learned = await review_and_learn(CONVO, llm, store=store)
        check("exactly one model call (facts+relations together)", llm.calls == 1, str(llm.calls))
        check("three facts written to L1", store.count() == 3, str(store.count()))
        check("returned the learned facts", len(learned) == 3, str(learned))

        print("\n[2] the parsed relations are no longer stored anywhere — and nothing errors")
        try:
            await review_and_learn(CONVO, llm, store=store)
            check("a second run with a relations key is accepted, not fatal", True)
            check("...and re-running writes no new facts (dedup)",
                  store.count() == 3, str(store.count()))
        except Exception as exc:                                  # noqa: BLE001
            check("a second run with a relations key is accepted, not fatal",
                  False, f"{type(exc).__name__}: {exc}")

        print("\n[3] the relation layer is genuinely gone, so a `graph=` kwarg fails loudly")
        try:
            await review_and_learn(CONVO, llm, store=store, graph=object())
            check("passing graph= raises rather than silently believing it stored", False,
                  "it was accepted")
        except TypeError:
            check("passing graph= raises rather than silently believing it stored", True)
        except Exception as exc:                                  # noqa: BLE001
            check("passing graph= raises rather than silently believing it stored", False,
                  f"{type(exc).__name__} instead of TypeError")

    print("\n[4] backward compat — a legacy bare ARRAY still yields facts, no crash")
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
        store = MemoryStore(base_dir=Path(d))
        legacy = FakeLLM('["the owner likes lofi.", "the owner uses Windows."]')
        learned = await review_and_learn(CONVO, legacy, store=store)
        check("legacy array still learns facts", store.count() == 2, str(store.count()))
        check("_parse_relations on a bare array -> []", _parse_relations('["a","b"]') == [])
        check("_parse_facts still parses the object form",
              set(_parse_facts('{"facts":["x is y."],"relations":[]}')) == {"x is y."})
        check("and the object form still parses relations, for anything that wants them",
              len(_parse_relations(
                  '{"facts":[],"relations":[["a","p","b"],["c","q","d"]]}')) == 2)

    print("\n[5] Fix #3 — L5 semantic defaults ON (graceful)")
    from afon.config import settings
    check("memory_semantic_enabled defaults True", settings.memory_semantic_enabled is True)
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
        store = MemoryStore(base_dir=Path(d))
        store.remember("the owner runs a rabbit farm", tags=["project"])
        hits = store.recall("rabbit farm")   # semantic path exercised; must return the fact
        check("recall works with semantic enabled (no crash)",
              any("rabbit" in h for h in hits), str(hits))

    print(f"\n=== {passed}/{passed + failed} checks passed ===")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
