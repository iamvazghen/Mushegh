"""Every source file must decode as UTF-8 and parse — before any gate that reads it.

Five gates in this suite walk the source with `ast.parse` and `continue` on
`SyntaxError`; several more read with `errors="replace"`. That is a reasonable
local guard — a file mid-edit is not that gate's business, as
test_proactive_thresholds.py says — but it has a consequence nobody chose: when a
file is broken, the gate that was supposed to be checking a property *of that
file* skips it and reports green over a smaller population than its own output
implies. `test_layering.py` can print PASS while saying nothing at all about
`brain/tools/fitness.py`.

That is the same shape as the audit that once printed `0 THEATRE` having audited
nothing: a check that silently drops its subject still counts as a check that ran.

So this gate owns the precondition the others assume. It is deliberately dumb —
walk `src/`, decode strictly, parse, report every offender with a file and a
line. No imports, no fixtures, no network: it must work on exactly the tree that
has just been broken, which is the only moment anyone needs it.

Two distinct failures, deliberately reported separately because they have
different causes:

  * not valid UTF-8 — a single stray byte, usually an em-dash pasted from a
    cp1252 editor and written without re-encoding. The file cannot even be
    opened by Python, so every importer fails with a confusing codec error that
    points at a byte offset rather than at the file.
  * does not parse — a real syntax error, mid-edit or not.

Hermetic, offline, ~1s.

    uv run python bench/test_source_compiles.py
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"

passed = failed = 0


def check(ok: bool, name: str, detail: str = "") -> None:
    global passed, failed
    if ok:
        passed += 1
        print(f"  [PASS] {name}")
    else:
        failed += 1
        print(f"  [FAIL] {name}  {detail}")


def main() -> int:
    if not SRC.is_dir():
        check(False, "src/ exists", str(SRC))
        print(f"\n  {passed} passed, {failed} failed")
        return 1

    files = sorted(SRC.rglob("*.py"))
    print("\n[1] the tree this suite gates on is readable")
    check(bool(files), "src/ has Python files to check", f"0 found under {SRC}")

    undecodable: list[str] = []
    unparseable: list[str] = []
    for path in files:
        rel = path.relative_to(ROOT)
        try:
            source = path.read_text(encoding="utf-8")
        except UnicodeDecodeError as e:
            # The byte offset is in the file; the useful part is which file and
            # what the offending byte is, because the decode error a caller sees
            # names neither clearly.
            undecodable.append(f"{rel}: byte {e.start:#04x} ({path.read_bytes()[e.start]:#04x})")
            continue
        try:
            ast.parse(source, filename=str(rel))
        except SyntaxError as e:
            undecodable_safe = rel.as_posix()
            unparseable.append(f"{undecodable_safe}:{e.lineno}: {e.msg}")

    check(
        not undecodable,
        "every source file is valid UTF-8",
        f"{len(undecodable)} file(s) are not: " + "; ".join(undecodable[:6]),
    )
    check(
        not unparseable,
        "every source file parses",
        f"{len(unparseable)} file(s) do not: " + "; ".join(unparseable[:6]),
    )

    print("\n[2] a broken file cannot hide behind a gate that skips it")
    # The five `except SyntaxError: continue` sites above are the reason this
    # file exists. If the tree is clean they are harmless; if the tree is not,
    # they are how a broken module gets a vacuous PASS. Assert the precondition
    # those gates assume rather than trying to rewrite each of them.
    check(
        not (undecodable or unparseable),
        "the gates that `continue` past a SyntaxError have a complete population",
        f"{len(undecodable) + len(unparseable)} file(s) would be skipped by them",
    )

    print(f"\n  {passed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())