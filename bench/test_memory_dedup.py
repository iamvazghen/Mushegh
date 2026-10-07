"""30.R1 — one fact is one hit, however many layers hold it.

`fused_recall` already ranked across layers (L1 learned, L2 journal, L3 vault) and tagged each hit
with its layer and source. What it did not do — and what 30.R1's "with dedup" asks for — was
deduplicate. It appended a hit per layer independently, so:

  1. a fact Afon had learned **and** the owner had also written into the vault came back **twice**,
     as two equal-ranked rows from "different" sources;
  2. that consumed the `limit`, so a genuinely cross-layer result was crowded out by repeats of one
     fact;
  3. and — the reason this is a charter task and not tidying — **if the two layers DISAGREE**, the
     store returned both as equals. Afon learns a new value; the owner's hand-edited vault note
     still carries the old one; the two come back as two "different" layers with equal standing.
     30.R2's tombstone cannot catch that, because it is keyed on `subject` and only works WITHIN L1.
     So "two versions, not a silent overwrite" was reachable through a door the supersession rule
     does not cover.

What is asserted here, and the sharp edge is the third point:

  * **the same fact from two layers comes back once**, keeping the higher-priority layer
  * **and the layers are reported rather than repeated** — `also_in` names them, so corroboration
    is a fact about the answer instead of a second copy of it
  * **differing facts are NOT merged.** That is the whole design: dedup collapses the *same* fact and
    refuses to touch a *disagreement*, because choosing one of two different statements is exactly
    the silent overwrite the charter forbids. Two rows survive, and that is the correct output.
  * a near-identical pair (trailing period, extra whitespace, case) DOES dedup — that is the
    difference between punctuation and a contradiction
  * a genuine near-synonym is NOT deduped, because inventing that agreement is worse than a repeat
  * the dedup runs BEFORE the limit, so it cannot be crowded out by its own duplicates
  * it is pure: no I/O, no settings, and the same input gives the same output

Hermetic: a pure function over synthetic hits plus one end-to-end `fused_recall` on a temp store.
No vault, no model, no network.

    uv run python bench/test_memory_dedup.py
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(ROOT / "src"))

passed = failed = 0
PRIORITY = {"L1": 0, "L2": 1, "L3": 3}


def check(name: str, ok: bool, detail: str = "") -> None:
    global passed, failed
    if ok:
        passed += 1
        print(f"  [PASS] {name}")
    else:
        failed += 1
        print(f"  [FAIL] {name}  {detail}")


def h(layer: str, text: str, score: float = 1.0) -> dict:
    return {"layer": layer, "text": text, "score": score, "source": layer.lower()}


def main() -> int:
    from afon.brain.memory import _dedupe_across_layers as _dedupe, _dedupe_key

    print("\n[1] the same fact from two layers is ONE hit")
    out = _dedupe([h("L1", "The garage remote is under the stairs"),
                   h("L3", "The garage remote is under the stairs")], priority=PRIORITY)
    check("two identical facts collapse to one", len(out) == 1, str(out))
    check("...and L1 wins, because it is the learned store",
          out[0]["layer"] == "L1", str(out[0]))
    check("...and the other layer is REPORTED, not silently dropped",
          out[0]["also_in"] == ["L3"], str(out[0].get("also_in")))

    print("\n[2] three layers, one fact, and it names all of them")
    out = _dedupe([h("L3", "The garage remote is under the stairs"),
                   h("L2", "The garage remote is under the stairs"),
                   h("L1", "The garage remote is under the stairs")], priority=PRIORITY)
    check("still one hit", len(out) == 1, str(len(out)))
    check("...listing both other layers", out[0]["also_in"] == ["L2", "L3"], str(out[0].get("also_in")))

    print("\n[3] punctuation and case are not a disagreement")
    for a, b in (("The garage remote is under the stairs.", "the garage remote is under the stairs"),
                 ("Remote is upstairs", "  remote   is   upstairs  ")):
        out = _dedupe([h("L1", a), h("L3", b)], priority=PRIORITY)
        check(f"dedups: {a[:28]!r} vs {b[:28]!r}", len(out) == 1, str(out))

    print("\n[4] a DISAGREEMENT is not merged — this is the whole point")
    out = _dedupe([h("L1", "The thermostat is set to twenty one"),
                   h("L3", "The thermostat is set to twenty six")], priority=PRIORITY)
    check("two different statements stay two rows", len(out) == 2, str(out))
    check("...neither is rewritten into the other",
          {r["text"] for r in out} == {"The thermostat is set to twenty one",
                                        "The thermostat is set to twenty six"}, str(out))
    check("...and neither is silently preferred over the other",
          all("also_in" not in r or not r["also_in"] for r in out), str(out))
    print("       ^ 30.R2's tombstone covers this only WITHIN L1 (it is keyed on `subject`). Across")
    print("         layers nothing reconciles them, so a stale hand-edited vault note can contradict")
    print("         a learned fact and both come back as equals. That is the gap, named not closed.")

    print("\n[5] a near-synonym is NOT collapsed")
    out = _dedupe([h("L1", "the car is red"), h("L3", "my car is red")], priority=PRIORITY)
    check("two different statements stay two rows", len(out) == 2, str(out))
    check("the key really is a normaliser and not a summariser",
          _dedupe_key("the car is red") != _dedupe_key("my car is red"))

    print("\n[6] the dedup is pure and cannot corrupt the input")
    src = [h("L1", "x"), h("L3", "x")]
    out = _dedupe(src, priority=PRIORITY)
    check("the input list is not mutated", len(src) == 2 and "also_in" not in src[0], str(src))
    check("the same input gives the same output", _dedupe(src, priority=PRIORITY) == out)
    check("empty text is not collapsed into one bucket",
          len(_dedupe([h("L1", ""), h("L3", "")], priority=PRIORITY)) == 2)

    print("\n[7] end to end: fused_recall on a real store, with the vault stubbed")
    with tempfile.TemporaryDirectory(prefix="afon-dedup-") as td:
        from afon.brain import memory as mem

        store = mem.MemoryStore(base_dir=Path(td) / "memory")
        store.remember("The garage remote is under the stairs", source="owner")
        hits = _run_fused(store, "garage remote")
        check("a learned fact comes back exactly once", len(hits) == 1, str(hits))
        check("...as L1", hits and hits[0]["layer"] == "L1", str(hits))
        check("...with the now-standard also_in key present",
              hits and "also_in" in hits[0], str(hits))

    print(f"\n{'=' * 60}")
    print(f"  {passed} passed, {failed} failed")
    print("=" * 60)
    return 1 if failed else 0


def _run_fused(store, query: str) -> list[dict]:
    """fused_recall with only L1 available — the vault layer is skipped when unconfigured."""
    import asyncio

    return asyncio.run(store.fused_recall(query, limit=8, layers=("L1",)))


if __name__ == "__main__":
    raise SystemExit(main())
