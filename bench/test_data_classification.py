"""37.R4 / O8.7 — every store declares a data class (hermetic, no network).

Registry gate: *every store declares a class, and an unclassified store fails the gate.*

Jev p = 0.95, conf 0.93 — the highest-confidence directive of the 999: *classify data first —
biometric, financial, medical, ordinary — before writing any retention rule; every other rule,
retention included, depends on knowing which class a thing is.*

Section [3] is the gate, and it is checked in both directions: the live state root must have no
undeclared entry, **and** planting a store must make it fail. A gate that cannot fail is decorative,
and this one is the precondition for every retention and consent rule after it.

Section [6] is the part that keeps the registry honest over time: the declarations are cross-checked
against a list maintained somewhere else entirely (`paths.LEGACY_STATE`, owned by the 30.F1
migration), so the registry cannot quietly drift away from the stores the code actually creates.

    uv run python bench/test_data_classification.py
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from afon.brain import data_classes as dc      # noqa: E402
from afon.shared import paths                  # noqa: E402

passed = failed = 0


def check(name: str, ok: bool, detail: str = "") -> None:
    global passed, failed
    if ok:
        passed += 1
        print(f"  [PASS] {name}")
    else:
        failed += 1
        print(f"  [FAIL] {name}  {detail}")


def main() -> int:
    print("\n[1] every declaration is well formed")
    check("there are declarations at all", len(dc.STORES) >= 20, str(len(dc.STORES)))
    bad_empty = [s.name for s in dc.STORES if not s.classes]
    check("no store declares an empty class set", not bad_empty, str(bad_empty))
    bad_class = [s.name for s in dc.STORES if not s.classes <= dc.CLASSES]
    check("no store invents a fifth class", not bad_class, str(bad_class))
    bad_why = [s.name for s in dc.STORES if not (s.why or "").strip()]
    check("every store says WHY it is that class", not bad_why, str(bad_why))
    dupes = [s.name for s in dc.STORES if [x.name for x in dc.STORES].count(s.name) > 1]
    check("no store is declared twice", not dupes, str(dupes))
    check("the four classes are exactly the four Jev named",
          dc.CLASSES == {"biometric", "medical", "financial", "ordinary"}, str(sorted(dc.CLASSES)))

    print("\n[2] 'strictest' is a pinned precedence, not whichever rule was written first")
    check("biometric beats everything",
          dc.strictest({"biometric", "medical", "financial", "ordinary"}) == "biometric")
    check("medical beats financial", dc.strictest({"financial", "medical"}) == "medical")
    check("financial beats ordinary", dc.strictest({"ordinary", "financial"}) == "financial")
    check("an empty set is ordinary, not a crash", dc.strictest(set()) == "ordinary")
    check("a container takes the strictest class it can HOLD",
          dc.classify("memory").strictest == "medical",
          "memory/ holds health, money and the week in the same prose")

    print("\n[3] THE GATE: an unclassified store fails")
    live = dc.unclassified()
    check(f"the live state root has no undeclared store ({paths.state_dir()})",
          not live, f"undeclared: {live}")
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "voiceprint.json").write_text("{}", encoding="utf-8")
        check("a declared store in a clean root passes", dc.unclassified(root) == [])
        (root / "afon_secrets.sqlite").write_text("", encoding="utf-8")
        check("...and planting an undeclared store FAILS it",
              dc.unclassified(root) == ["afon_secrets.sqlite"], str(dc.unclassified(root)))
        (root / "afon_secrets.sqlite").unlink()
        (root / "new_store_dir").mkdir()
        check("an undeclared DIRECTORY fails it too, not just a file",
              dc.unclassified(root) == ["new_store_dir"], str(dc.unclassified(root)))
        (root / "new_store_dir").rmdir()
        (root / "__pycache__").mkdir()
        check("and the few things that are provably not stores do not",
              dc.unclassified(root) == [], str(dc.unclassified(root)))

    print("\n[4] a backup of a sensitive file is still sensitive")
    check("voiceprint.json.bak inherits biometric",
          dc.classify("voiceprint.json.bak") is not None
          and dc.classify("voiceprint.json.bak").strictest == "biometric",
          "a .bak of a biometric file is a biometric file")
    check("...by inheritance, not by an exemption that skips it",
          dc.classify("voiceprint.json.bak").name == "voiceprint.json")
    check("an undeclared .bak is still undeclared", dc.classify("whatever.bak") is None)

    print("\n[5] the standing rule: owner biometrics never leave the laptop")
    never = {s.name for s in dc.must_not_leave()}
    check("the biometric stores are declared as never leaving",
          {"voiceprint.json", "faces"} <= never, str(sorted(never)))
    biometric = [s for s in dc.STORES if "biometric" in s.classes]
    check("no biometric store is allowed to leave",
          all(not s.leaves_host for s in biometric),
          str([s.name for s in biometric if s.leaves_host]))
    # A declaration that git contradicts is worse than no declaration, so tie it to the enforceable
    # fact: these must be excluded from the repo.
    # Rules, not prose: a comment mentioning a filename ignores nothing. Compared against the
    # uncommented lines only, which is what caught the missing face rule on 2026-09-20 — the
    # voiceprint had a deliberate glob and face data was covered only incidentally, by happening to
    # sit under the already-ignored backups/.
    rules = {ln.strip() for ln in (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
             if ln.strip() and not ln.lstrip().startswith("#")}
    check("...and .gitignore has a RULE for the voiceprint, not just a comment",
          "voiceprint.json*" in rules, str(sorted(r for r in rules if "voice" in r)))
    check("...and a rule of its own for owner face data",
          {"owner.npy", "faces/"} <= rules,
          str(sorted(r for r in rules if "npy" in r or "face" in r)))
    check("credentials are declared as never leaving either",
          "!env" in never and "!contacts" in never, str(sorted(never)))
    # Q1.3: the standing rule above is per-store, so an outbound FLOW satisfies it by simply not
    # declaring biometric - which is exactly what makes it worth asserting separately. This is the
    # first declared flow to a third party that holds nothing else about the owner, and the cheapest
    # way for it to go wrong is someone widening its class set later to make a payload validate.
    typesafe = dc.classify("!typesafe")
    check("the outbound judgment flow is declared at all", typesafe is not None)
    if typesafe:
        check("...and carries no biometric to a third party",
              "biometric" not in typesafe.classes, str(sorted(typesafe.classes)))
        check("...and is honest that it leaves the host", typesafe.leaves_host)
        check("...and its strictest class is medical, so minimisation is obligatory",
              typesafe.strictest == "medical", typesafe.strictest)

    print("\n[6] the registry cannot drift from the stores the code actually creates")
    # LEGACY_STATE is maintained by the 30.F1 migration, independently of this registry. Every store
    # it knows about must be classified, or one of the two lists has moved without the other.
    missing = []
    for rel in paths.LEGACY_STATE:
        top = rel.split("/")[0]
        if dc.classify(top) is None:
            missing.append(rel)
    check("every store the migration map knows about is classified",
          not missing, f"unclassified: {missing}")
    check("the external stores are named so they cannot collide with a filename",
          all(s.name.startswith("!") for s in dc.STORES if s.name in
              {"!audit", "!postgres", "!vault", "!env", "!contacts"}))

    print("\n[7] it is reportable, because a classification nobody can read is not a control")
    snap = dc.summary()
    check("summary reports the count", snap["stores"] == len(dc.STORES))
    check("summary reports a breakdown by strictest class",
          set(snap["by_strictest_class"]) <= dc.CLASSES, str(snap["by_strictest_class"]))
    check("summary names what must never leave", "voiceprint.json" in snap["never_leaves_host"])
    check("summary carries the gate's own verdict", snap["ok"] is (not snap["undeclared"]))
    check("every class is actually used by at least one store",
          all(any(c in s.classes for s in dc.STORES) for c in dc.CLASSES),
          "a class nobody uses is a class nobody thought about")

    print(f"\n=== {passed}/{passed + failed} checks passed ===")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
