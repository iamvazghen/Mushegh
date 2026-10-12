"""Phase 1.5 — proper-noun biasing list + STT wiring.

Asserts the bias list is assembled from configured terms + identity (assistant/owner/address) +
contacts, de-duplicated case-insensitively and capped; that the Whisper builder receives it; and that
the Deepgram builder still constructs even if this build rejects `keyterm` (guarded). Hermetic — a
fake contact book, in-process settings tweaks, no audio, no network.

    uv run python bench/test_proper_nouns.py
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import mushegh.brain.contacts as contacts_mod  # noqa: E402
from mushegh.config import settings  # noqa: E402
from mushegh.edge import proper_nouns  # noqa: E402

passed = failed = 0


def check(name: str, ok: bool, detail: str = "") -> None:
    global passed, failed
    if ok:
        passed += 1
        print(f"  [PASS] {name}")
    else:
        failed += 1
        print(f"  [FAIL] {name}  {detail}")


@dataclass
class _C:
    name: str


class _FakeBook:
    def __init__(self, names):
        self._names = names

    def all(self):
        return [_C(n) for n in self._names]


def main() -> None:
    saved = (settings.stt_hotwords, settings.assistant_name, settings.user_name,
             settings.user_address, contacts_mod.BOOK)
    try:
        settings.stt_hotwords = "Yerevan, Cologne, Rently; Party Map"
        settings.assistant_name = "Mushegh"
        settings.user_name = "Alex"
        settings.user_address = "sir"
        contacts_mod.BOOK = _FakeBook(["Anush", "John Smith"])
        proper_nouns.hotwords_str.cache_clear()

        print("[1] list merges config + identity + contacts")
        lst = proper_nouns.hotwords_list()
        low = [t.lower() for t in lst]
        for term in ["yerevan", "cologne", "rently", "party map", "mushegh", "alex", "sir",
                     "anush", "john smith"]:
            check(f"'{term}' present", term in low, repr(lst))

        print("\n[2] semicolons split, case-insensitive dedup")
        settings.stt_hotwords = "Rently, rently, RENTLY, Mushegh"  # dupes + collides with assistant name
        proper_nouns.hotwords_str.cache_clear()
        lst = proper_nouns.hotwords_list()
        low = [t.lower() for t in lst]
        check("'rently' appears exactly once", low.count("rently") == 1, repr(lst))
        check("'mushegh' appears exactly once despite config+identity", low.count("mushegh") == 1, repr(lst))

        print("\n[3] cap bounds the list")
        settings.stt_hotwords = ", ".join(f"term{i}" for i in range(200))
        proper_nouns.hotwords_str.cache_clear()
        check("respects max_terms cap", len(proper_nouns.hotwords_list(max_terms=25)) == 25)

        print("\n[4] hotwords_str is one space-joined string")
        settings.stt_hotwords = "Yerevan, Cologne"
        contacts_mod.BOOK = _FakeBook([])
        proper_nouns.hotwords_str.cache_clear()
        s = proper_nouns.hotwords_str()
        check("space-joined, contains terms", "Yerevan" in s and "Cologne" in s and "," not in s, repr(s))

        print("\n[5] Deepgram builder constructs with biasing (guard doesn't break the build)")
        settings.stt_hotwords = "Yerevan, Cologne, Rently"
        proper_nouns.hotwords_str.cache_clear()
        if settings.deepgram_api_key:
            try:
                from mushegh.edge.stt import _build_deepgram
                svc = _build_deepgram()
                check("Deepgram STT service built (keyterm applied or safely dropped)", svc is not None)
            except Exception as e:  # noqa: BLE001
                check("Deepgram STT service built", False, f"{type(e).__name__}: {e}")
        else:
            check("Deepgram key not set — skipped build smoke (biasing still wired for Whisper)", True)

        print("\n[6] empty config + no contacts -> just identity terms, never raises")
        settings.stt_hotwords = ""
        settings.assistant_name = "Mushegh"
        settings.user_name = ""
        settings.user_address = ""
        contacts_mod.BOOK = _FakeBook([])
        proper_nouns.hotwords_str.cache_clear()
        lst = proper_nouns.hotwords_list()
        check("degrades to the assistant name alone", [t.lower() for t in lst] == ["mushegh"], repr(lst))
    finally:
        (settings.stt_hotwords, settings.assistant_name, settings.user_name,
         settings.user_address, contacts_mod.BOOK) = saved
        proper_nouns.hotwords_str.cache_clear()

    one_node_per_person()

    print(f"\n=== {passed}/{passed + failed} checks passed ===")
    if failed:
        sys.exit(1)


# ── 24.F1: the names STT hands over resolve to the person the facts are under ──────────────────
# This file's subject is the names Mushegh biases the recogniser toward. The other end of that wire
# is what happens once STT returns one: a proper noun that arrives transliterated ("Вазген") must
# reach the same person, or biasing the recogniser toward a name only makes it better at missing.
#
# **Rewritten 2026-10-04 (D-26, M04). This is a weaker test than the one it replaces, and the loss is
# recorded here rather than hidden.** It ran against `GraphMemory`, so it had been failing to start
# since the relation layer was deleted — the second gate left importing a module that no longer
# exists, found by the full suite while landing 26.R5. A third gate named for 24.F1,
# `test_graph_memory.py`, is not a file any more.
#
# Measuring what the deletion actually cost, rather than assuming:
#
#   * SURVIVES, and is asserted below — the MECHANISM, intact. `shared/entities.same_entity` does
#     exactly what SYSTEMS-DETAILS.md says it does: transliterate, then merge what transliteration
#     cannot settle by a high-threshold difflib match at lookup time, never by rewriting one name
#     into the other. It bridges "Вазген"/"Vazghen" (0.923) and refuses "John Smith"/"Jane Smith"
#     (0.800, under the 0.82 bar) — which is the whole point of the threshold.
#   * DOES NOT reach the owner — the WIRING. `ContactBook.resolve`, the one path that answers "call
#     Вазген", compares with `canonical()` equality and never calls `same_entity`. So the fuzzy merge
#     the floor task specifies is implemented, tested nowhere, and absent from the lookup that
#     matters. `test_contacts.py` (52/52) does not catch this because its fixtures spell the owner
#     consistently.
#   * SAME for the L1 memory store: recall does not canonicalise at all, so a transliterated query
#     misses a fact stored under the other spelling.
#
# Both gaps are wiring, not design, and both are asserted as gaps so they flip and announce
# themselves when fixed. Closing either is a one-line change to a lookup, but it is a change to who
# an outgoing message can be addressed to — merging two different people sends it to the wrong human
# — so it belongs to the owner, not to the repair of a dead test file.
def one_node_per_person() -> None:
    import tempfile

    from mushegh.brain.contacts import ContactBook
    from mushegh.brain.memory import MemoryStore
    from mushegh.shared.entities import canonical, same_entity

    print("\n[24.F1] a transliterated proper noun reaches the person, not a near-miss match")

    check("canonical() transliterates Cyrillic into the Latin the rest of the system stores",
          canonical("Вазген") == "vazgen" and canonical("Vazgen") == "vazgen",
          f"{canonical('Вазген')!r} vs {canonical('Vazgen')!r}")
    check("the merge mechanism transliterates first, so the script never matters",
          same_entity("Вазген", "Vazghen") and same_entity("Вазген", "Vazgen"),
          "transliteration is supposed to settle this before any fuzzy comparison runs")
    check("...and it bridges the Latin spelling variant transliteration cannot settle",
          same_entity("Vazghen", "Vazgen"),
          "SYSTEMS-DETAILS says this merges at lookup time; it does not any more")
    check("...and it still refuses two people who share a surname",
          not same_entity("John Smith", "Jane Smith"),
          "merging two different people sends an outward message to the wrong human")

    with tempfile.TemporaryDirectory() as td:
        book = ContactBook(Path(td) / "contacts.md")
        book.save(contacts_mod.Contact("Vazgen Vardanian", email="v@example.com"))
        book.save(contacts_mod.Contact("Anna Petrova", email="a@example.com"))
        for spelling in ("Вазген", "Vazgen", "vazgen", "Вазген Варданян"):
            found = book.resolve(spelling)
            check(f"the CHANNEL path resolves {spelling!r} to the owner, not to a neighbour",
                  bool(found) and found[0].email == "v@example.com",
                  f"resolve({spelling!r}) -> {[c.name for c in found]}")
        check("the channel path does NOT resolve a stranger onto the nearest person",
              not book.resolve("Zebedee Quinn"),
              "resolving a stranger onto the nearest entry is worse than finding nothing")

        bridging = book.resolve("Vazghen")
        check("KNOWN GAP, asserted as a gap: ContactBook.resolve never calls same_entity, so the "
              "merge the floor task specifies is unreachable from the lookup that matters",
              not bridging,
              "resolve('Vazghen') now finds them — the contacts path is wired to the merge, and "
              "this gap check should be replaced with a capability check")

    with tempfile.TemporaryDirectory() as td:
        store = MemoryStore(base_dir=td)
        store.remember("Вазген owns Lpstrak", source="tool")
        store.remember("Lpstrak is located in Armenia", source="tool")
        texts = [n.text for n in store._iter_notes()]          # noqa: SLF001
        check("the facts are stored under the Cyrillic spelling",
              any("Lpstrak" in t and "Вазген" in t for t in texts), str(texts))
        check("KNOWN GAP, asserted as a gap: L1 recall calls neither canonical() nor same_entity, "
              "so a transliterated query still misses the fact stored under the other spelling",
              not store.recall("Vazgen", semantic=False),
              "recall('Vazgen') now finds it — L1 resolves entities, and this gap check should be "
              "replaced with a capability check")


if __name__ == "__main__":
    main()
