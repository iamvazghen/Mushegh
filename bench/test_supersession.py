"""30.R10 — a conflicting correction supersedes the fact it corrects (D-25).

Deduplicating on identical text is not supersession. Before this, "the meeting is at three"
and then "at four" produced **two** live facts and recall returned both, so the system
answered with a contradiction and looked confident doing it.

What is asserted here, and why each one is not obvious:

  * a subject declared by the caller is the supersession key. Nothing in the store can know
    that two sentences are about the same slot, so the code does not guess — it enforces the
    rule for the slot the caller names. This is the same discipline as Jev's declared labels.
  * the loser is **tombstoned, never deleted**: its text stays on disk with `superseded_by`
    in its front-matter, so "why do you still believe the old one?" has an answer.
  * recall returns **one** fact, not both. A memory that still returns a corrected fact is
    worse than no memory, because the wrong answer arrives with the right confidence.
  * **provenance cannot be traded for recency.** A guess may never overwrite something the
    owner said, however much later it arrives — that asymmetry is the whole rule, and it is
    the one a naive "newest wins" implementation gets wrong.
  * an unrelated fact is untouched by any of this.

Hermetic: a temp store, no network, no model.

    uv run python bench/test_supersession.py
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

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


def live(store):
    return [(n.subject, n.text) for n in store._iter_notes()]          # noqa: SLF001


def main() -> int:
    from afon.brain.memory import MemoryStore

    with tempfile.TemporaryDirectory(prefix="afon-supersession-") as td:
        base = Path(td)

        print("[1] a correction on the same subject leaves ONE live fact")
        store = MemoryStore(base_dir=base / "s1")
        store.remember("The garage remote is in the kitchen drawer", source="owner",
                       subject="garage remote location")
        store.remember("The garage remote is under the stairs", source="owner",
                       subject="garage remote location")
        facts = live(store)
        check("two writes, one live fact", len(facts) == 1, str(facts))
        check("...and it is the newer one", facts and "stairs" in facts[0][1], str(facts))

        print("\n[2] the loser is tombstoned, not deleted")
        all_notes = list(store._iter_all_notes())                        # noqa: SLF001
        check("both notes still exist on disk", len(all_notes) == 2, str(len(all_notes)))
        dead = [n for n in all_notes if n.superseded_by]
        check("exactly one is marked superseded", len(dead) == 1, str(len(dead)))
        check("...its text is preserved, so it can still be explained",
              bool(dead) and "kitchen drawer" in dead[0].text,
              dead[0].text if dead else "none")
        check("...and it names what replaced it",
              bool(dead) and dead[0].superseded_by.endswith(".md"),
              dead[0].superseded_by if dead else "none")

        print("\n[3] the audit trail explains the change")
        trail = store.supersessions()
        check("one audit row", len(trail) == 1, str(len(trail)))
        if trail:
            row = trail[0]
            check("...naming the subject", row.get("subject") == "garage remote location",
                  str(row.get("subject")))
            check("...the old text and the new one",
                  "kitchen drawer" in row.get("old_text", "")
                  and "stairs" in row.get("new_text", ""), str(row)[:120])
            check("...a reason in words", bool(row.get("reason")), str(row.get("reason")))
            check("...and both filenames, so the trail joins to the files",
                  bool(row.get("superseded")) and bool(row.get("by")), str(row)[:120])

        print("\n[4] provenance cannot be traded for recency")
        store2 = MemoryStore(base_dir=base / "s2")
        store2.remember("The thermostat is set to twenty one", source="owner",
                        subject="thermostat setpoint")
        store2.remember("The thermostat is set to twenty six", source="inferred",
                        subject="thermostat setpoint")
        facts2 = live(store2)
        check("an inferred fact does NOT supersede an owner-stated one", len(facts2) == 1, str(facts2))
        check("...and the owner's value stands",
              facts2 and "twenty one" in facts2[0][1], str(facts2))
        check("...no tombstone was written for it", store2.supersessions() == [],
              str(store2.supersessions()))

        print("\n[5] a tool-read fact may not overwrite the owner either, but may overwrite a guess")
        store3 = MemoryStore(base_dir=base / "s3")
        store3.remember("The build finished at 09:14", source="inferred", subject="last build time")
        store3.remember("The build finished at 09:41", source="tool", subject="last build time")
        facts3 = live(store3)
        check("a tool fact supersedes an inferred one", len(facts3) == 1, str(facts3))
        check("...and the newer value wins", facts3 and "09:41" in facts3[0][1], str(facts3))

        print("\n[6] an unrelated fact is untouched by any of this")
        store.remember("He prefers tea in the morning", source="owner")
        facts4 = live(store)
        check("the unrelated fact was added", any("tea" in t for _, t in facts4), str(facts4))
        check("...and the superseding subject still holds exactly one",
              len([f for f in facts4 if f[0] == "garage remote location"]) == 1, str(facts4))
        check("...still with no tombstone added for it",
              len(store.supersessions()) == 1, str(len(store.supersessions())))

        print("\n[7] a fact with no subject is unaffected — no slot was declared")
        store4 = MemoryStore(base_dir=base / "s4")
        store4.remember("The blue mug is chipped", source="owner")
        store4.remember("The red mug is chipped", source="owner")
        check("two subjectless facts both stay live", len(live(store4)) == 2, str(live(store4)))
        check("...and nothing is tombstoned", store4.supersessions() == [], "")

        print("\n[8] the same fact twice on a subject is still a dedup, not a supersession")
        store5 = MemoryStore(base_dir=base / "s5")
        p1 = store5.remember("The router is in the hall", source="owner", subject="router location")
        p2 = store5.remember("The router is in the hall", source="owner", subject="router location")
        check("the second write returns the first note", p1 == p2, f"{p1} {p2}")
        check("...and no tombstone was written", store5.supersessions() == [], "")
        check("...and only one file exists", len(live(store5)) == 1, str(live(store5)))

    print(f"\n=== {passed + failed} checks: {passed} passed, {failed} failed ===")
    if not failed:
        print("ALL CHECKS PASSED ===")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
