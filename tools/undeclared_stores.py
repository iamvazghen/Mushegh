"""Which stores does the code WRITE that no `Store` declaration covers?

`bench/test_data_classification.py` answers this the obvious way: walk the live
state root and complain about anything undeclared. That is correct and it is also
late — it only sees a store once a feature has actually run on this machine and
written the file.

Found the hard way on 2026-10-12. Verifying a fix to `import_health` without
sandboxing `MUSHEGH_STATE_DIR` wrote a real `vitals.json` into the owner's
~/.mushegh, and the gate went red on it. The gate was right — `vitals.save()`
had always written that file — but the discovery was accidental, and the owner
would have hit the same red the first time they imported a health export, with
no code change to point at.

This is the static version of that question: grep src/ for the literal filename
each store path is built from, and report the ones no declaration names.

It is a DIAGNOSTIC, not a gate, and it is deliberately not registered in
run_all_tests.py:

  * Declaring a store means choosing its data class (BIOMETRIC / MEDICAL /
    FINANCIAL / ORDINARY) and whether its bytes may leave the host. That is a
    privacy judgement per store, not a mechanical one, and thirteen of them is a
    decision rather than a patch.
  * The scan is textual. A store built from a computed name will not be found,
    so "no undeclared stores" would be a weaker statement than it looks. Read
    the list before trusting the absence.

Two things this accounts for, both of which are easy to get wrong:

  * a leading "!" names an EXTERNAL store, so `state_dir() / "audit"` matches a
    declared `!audit` and is NOT undeclared;
  * a literal containing "/" is a subdirectory, not a store file, and is skipped.

    uv run python tools/undeclared_stores.py [--paths]
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mushegh.brain.data_classes import STORES  # noqa: E402

DECLARED = {s.name for s in STORES}
EXTERNAL = {n[1:] for n in DECLARED if n.startswith("!")}

#: The one shape every store path has: state_dir() / "name". Extend deliberately,
#: and note that a computed name will not match.
PATTERN = re.compile(r'state_dir\(\)\s*/\s*"([^"]+)"')


def scan() -> dict[str, set[str]]:
    found: dict[str, set[str]] = {}
    for path in sorted((ROOT / "src").rglob("*.py")):
        text = path.read_text(encoding="utf-8", errors="replace")
        for match in PATTERN.finditer(text):
            name = match.group(1)
            if "/" in name or name.startswith("."):
                continue  # a subdirectory, not a store file
            found.setdefault(name, set()).add(str(path.relative_to(ROOT)))
    return found


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--paths", action="store_true", help="print every match, not just undeclared")
    args = ap.parse_args(argv)

    found = scan()
    undeclared = {
        n: v for n, v in found.items() if n not in DECLARED and n not in EXTERNAL
    }

    print(f"declared stores : {len(DECLARED)}  (of which {len(EXTERNAL)} external, '!'-prefixed)")
    print(f"store literals  : {len(found)} found in src/")
    print()

    for name in sorted(found):
        if name in EXTERNAL:
            status = "EXTERNAL"
        elif name in DECLARED:
            status = "declared"
        else:
            status = "UNDECLARED"
        if status == "UNDECLARED" or args.paths:
            print(f"  {status:<10} {name:<26} {sorted(found[name])[0]}")

    print()
    if undeclared:
        print(f"{len(undeclared)} store(s) the code writes that no declaration names.")
        print("Each one turns bench/test_data_classification.py red the first time that")
        print("feature runs on a machine — which is how vitals.json was found.")
    else:
        print("every store literal in src/ has a declaration.")
    return 1 if undeclared else 0


if __name__ == "__main__":
    raise SystemExit(main())