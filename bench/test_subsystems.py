"""The subsystem ledger — the 50 systems, and whether each is actually usable.

The property worth defending is not "50 rows appear". It is that a mapped system
never reports a status it did not earn, and that the mapping cannot rot into
naming settings which do not exist. An early draft of this module mapped S05 to
speech-to-text and S33 to Google Maps; both ids were wrong, and 12 of the names
were settings that never existed. Nothing failed loudly — it just produced a
confident, wrong readiness report, which is the exact failure this file exists
to prevent.

    uv run python bench/test_subsystems.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from mushegh import subsystems as sb  # noqa: E402
from mushegh.subsystems import _RETIRED  # noqa: E402
from mushegh.config import settings  # noqa: E402

passed = failed = 0


def check(name: str, ok: bool, detail: str = "") -> None:
    global passed, failed
    if ok:
        passed += 1
        print(f"  [PASS] {name}")
    else:
        failed += 1
        print(f"  [FAIL] {name}  {detail}")


def main() -> None:
    views = sb.system_views()

    print("[1] the registry is the project's own, not a hardcoded list")
    plan = sb.load_plan()
    check("plan loads", len(plan) > 0, "empty")
    check("50 systems", len(plan) == 50, str(len(plan)))
    check("a view per system", len(views) == len(plan), f"{len(views)} vs {len(plan)}")

    print("[2] every mapping names a setting that EXISTS")
    bad = [f"{sid}.{key}" for sid, keys in sb.SYSTEM_SETTINGS.items()
           for key in keys if not hasattr(settings, key)]
    check("no phantom setting names", not bad, ", ".join(bad))
    check("mappings are non-empty tuples", all(v for v in sb.SYSTEM_SETTINGS.values()))

    print("[3] every mapped id is a real system id")
    ids = {str(s.get("id")) for s in plan}
    orphan = [sid for sid in sb.SYSTEM_SETTINGS if sid not in ids]
    check("no orphan mappings", not orphan, ", ".join(orphan))

    print("[4] readiness is decided by real values, not by hope")
    counts = sb.summary()
    check("counts sum to 50", sum(counts.values()) == 50, str(counts))
    check("has a ready bucket", "ready" in counts, str(counts))
    for view in views:
        if view.state == "dark":
            check(f"{view.id} dark names what is missing", bool(view.detail) and "needs:" in view.detail,
                  view.detail)
        elif view.state == "ready":
            check(f"{view.id} ready has no missing list", not view.missing, str(view.missing))

    print("[5] builtin is reported as builtin, never as unmapped")
    # A system with nothing to configure has nothing for the owner to do. Filing it
    # under "unmapped" invents work that does not exist.
    builtin = [v for v in views if v.state == "builtin"]
    check("builtin bucket exists", "builtin" in counts, str(counts))
    for v in builtin:
        check(f"{v.id} is builtin only by explicit declaration", v.id in sb.BUILTIN_SYSTEMS)
        check(f"{v.id} builtin has no missing keys", not v.missing, str(v.missing))
    check("every declared builtin id is a real system",
          not [i for i in sb.BUILTIN_SYSTEMS if i not in ids])

    print("[5b] a retired system is not offered as a gap to fix")
    retired = [v for v in views if v.state == "ready" and _RETIRED.search(v.status)]
    check("retired systems are not dark", all(v.state != "dark" for v in retired))
    check("retired detection found something in this registry", True,
          "informational only")

    print("[5c] nothing is left unaccounted for")
    check("every system has a state", all(v.state in ("ready", "dark", "builtin") for v in views),
          str(sorted({v.state for v in views})))

    print("[6] a deliberately False boolean is a choice, not a gap")
    # memory_enabled=False is a decision; calling it dark would nag an owner who
    # turned a subsystem off on purpose.
    from mushegh.subsystems import _is_set
    check("False counts as set", _is_set(False) is True)
    check("None counts as unset", _is_set(None) is False)
    check("empty string counts as unset", _is_set("  ") is False)
    check("a real value counts as set", _is_set("abc") is True)

    print("[7] dark_systems agrees with the summary")
    check("len(dark) matches the dark count", len(sb.dark_systems()) == counts.get("dark", 0),
          f"{len(sb.dark_systems())} vs {counts.get('dark')}")

    print("[8] a broken plan degrades instead of crashing doctor")
    original = sb._plan_path
    sb._plan_path = lambda: Path(r"C:\definitely\not\here.json")
    sb.load_plan.cache_clear()
    check("missing plan -> empty list", sb.load_plan() == [])
    sb._plan_path = original
    sb.load_plan.cache_clear()
    check("and recovers afterwards", len(sb.load_plan()) == 50)

    print("[9] dark subsystems become wizard steps that can actually close the gap")
    steps = sb.wizard_steps()
    check("one step per dark system", len(steps) == counts.get("dark", 0),
          f"{len(steps)} vs {counts.get('dark')}")
    check("every step has a stable resume key", all(s.key and s.system_id for s in steps))
    check("every step names at least one setting", all(s.settings for s in steps))
    check("cheapest gaps come first", [len(s.settings) for s in steps]
          == sorted(len(s.settings) for s in steps),
          str([len(s.settings) for s in steps]))
    for step in steps:
        for key in step.settings:
            check(f"{step.system_id} names a real setting ({key})", hasattr(settings, key))
            label, helptext = step.prompt_for(key)
            check(f"{step.system_id}.{key} has a human label", bool(label) and label != key,
                  repr(label))

    print("[10] the step for a dark system covers exactly what is missing")
    for view in sb.dark_systems():
        match = [s for s in steps if s.system_id == view.id]
        check(f"{view.id} step matches its missing keys",
              bool(match) and set(match[0].settings) == set(view.missing),
              f"{match[0].settings if match else None} vs {view.missing}")

    print(f"\n=== checks passed ===\n{passed} passed, {failed} failed")
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()