"""Verify that every module a system document calls a "surface" is actually wired.

Rule 1 of subsystems/README.md is that a cited path must exist. A path can exist and
still be a lie: ``src/afon/brain/mynews.py`` was on disk, listed as S41's surface, and
nothing in the brain imported it. That is worse than a phantom path, because a phantom
path fails loudly on first read while an unwired module looks like a finished system.

This checks the narrower half that a static import graph can answer honestly: a module
named as a surface of some system should be reachable from the package by import. It
does not decide whether the reachability is *correct* - only whether the document's
structural claim is mechanically true.

Usage:
    python tools/verify_surface_claims.py           # summary
    python tools/verify_surface_claims.py --verbose # per-surface detail
"""

from __future__ import annotations

import argparse
import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DETAILS = ROOT / "docs" / "SYSTEMS-DETAILS.md"
SRC = ROOT / "src"

#: The value is captured to end-of-line only. Under re.S, ".+" swallows the rest of the
#: document and every finding gets attributed to whichever system said "**Surfaces**" first.
SURFACES_RE = re.compile(r"\*\*Surfaces\*\*[ \t]*([^\n]*)")
#: An annotation in the text right after a citation that marks it as deliberately gone.
REMOVED_ANNOTATION_RE = re.compile(
    r"\s*\(\s*[^)]*?\b(?:removed|deleted|cancelled|canceled)\b", re.I
)
PATH_RE = re.compile(r"`([A-Za-z0-9_./-]+)`")


def _module_name(rel_path: str) -> str:
    """`src/afon/brain/mynews.py` -> `afon.brain.mynews`."""
    p = rel_path.removeprefix("src/").removesuffix(".py")
    return p.replace("/", ".")


def collect_imports() -> set[str]:
    """Module names that appear as an *import target* somewhere under src/.

    Deliberately does NOT include a module just because the file exists. That mistake
    makes the whole check vacuous: every file would "reach" itself. A module is
    reachable only when something actually names it in an import statement.
    """
    imported: set[str] = set()
    for py in SRC.rglob("*.py"):
        rel = py.relative_to(SRC).as_posix()
        try:
            tree = ast.parse(py.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imported.add(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.level:
                    # Relative import: resolve against the containing package.
                    base = rel.removesuffix(".py").replace("/", ".")
                    parts = base.split(".")
                    if node.level > len(parts):
                        continue
                    prefix = ".".join(parts[: len(parts) - node.level])
                    target = f"{prefix}.{node.module}" if node.module else prefix
                    imported.add(target)
                elif node.module:
                    imported.add(node.module)
                for alias in getattr(node, "names", []):
                    if node.module:
                        imported.add(f"{node.module}.{alias.name}")
    return imported


def collect_string_literals() -> set[str]:
    """Filenames that appear as real string constants, i.e. dynamic dispatch by path.

    ``protocols.py`` launches its recovery scripts as detached subprocesses by path
    (``subprocess.Popen([sys.executable, _SCRIPT_DIR / proto["script"], ...])``) so they
    survive Afon being killed. Nothing imports them and nothing should.

    This parses string CONSTANTS rather than grepping, which is what separates a genuine
    dynamic reference from prose. A comment mentioning ``mynews.py`` is not a dispatch;
    a dict entry ``"script": "phoenix.py"`` is. Grepping here would excuse the exact
    defect this tool exists to find.
    """
    literals: set[str] = set()
    for py in SRC.rglob("*.py"):
        try:
            tree = ast.parse(py.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                token = node.value.strip()
                if "/" not in token and token.endswith(".py"):
                    literals.add(token)
                    literals.add(token.removesuffix(".py"))
    return literals


LAUNCH_GLOBS = ("*.sh", "*.ps1", "*.vbs", "*.cmd", "*.bat", "*.service")
SKIP_DIRS = {".venv", "venv", "node_modules", ".git", "__pycache__", "logs", "state"}
MODULE_LAUNCH_RE = re.compile(r"-m\s+([A-Za-z_][A-Za-z0-9_.]*)")
SCRIPT_LAUNCH_RE = re.compile(r"python[0-9.]*w?\s+[\"']?([A-Za-z0-9_./\\-]+\.py)")


def collect_launchers() -> tuple[set[str], set[str]]:
    """Modules and scripts started by a launcher rather than imported.

    ``run.sh`` does ``exec uv run python -m afon.edge.edge_lite`` and the scheduled
    task does ``pythonw -m afon.edge.pc_agent``. Those are real, deliberate entry
    points that no import statement will ever mention, so import-graph reasoning alone
    would report them dead. The launcher files are the source of truth for them.
    """
    modules: set[str] = set()
    scripts: set[str] = set()
    for pattern in LAUNCH_GLOBS:
        for path in ROOT.rglob(pattern):
            if any(part in SKIP_DIRS for part in path.parts):
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            modules.update(MODULE_LAUNCH_RE.findall(text))
            scripts.update(SCRIPT_LAUNCH_RE.findall(text))
    return modules, scripts


def make_reachable(imports: set[str], literals: set[str],
                   launched: set[str], scripts: set[str]):
    """Build the reachability predicate from the four collected evidence sets."""

    def reachable(rel_path: str) -> bool:
        mod = _module_name(rel_path)
        # An exact import target. `from afon.brain import mynews` already contributes
        # "afon.brain.mynews", so no ancestor-package fallback is used here: importing
        # `afon` proves nothing about `afon.brain.mynews`, and pretending otherwise
        # makes every module under src/ reachable at once.
        if mod in imports:
            return True
        # Executed by path rather than imported (detached protocols).
        base = Path(rel_path).name
        if base in literals or base.removesuffix(".py") in literals:
            return True
        # Started as `python -m pkg.mod` by run.sh / a scheduled task.
        if mod in launched:
            return True
        # Started as `python path/to/file.py`.
        return rel_path.replace("\\", "/") in scripts or base in scripts

    return reachable


def surface_claims(text: str) -> tuple[list[tuple[str, int]], int]:
    """Every live `Surfaces` citation as (path, line), plus how many were marked removed.

    A citation the document itself annotates as removed is a record, not a claim: S24
    and S30 both cite graph.py as "(removed 2026-10-04, D-26)". Demanding a dead path
    be live would punish the docs for being honest about a deletion.
    """
    claims: list[tuple[str, int]] = []
    historical = 0
    for match in SURFACES_RE.finditer(text):
        # A Surfaces value may wrap onto following lines; stop at a blank line.
        tail = text[match.end() : match.end() + 400]
        block = re.split(r"\n\s*\n", tail, maxsplit=1)[0]
        for raw in PATH_RE.findall(match.group(1) + block):
            if not (raw.startswith("src/afon") and raw.endswith(".py")):
                continue
            idx = tail.find(raw)
            window = tail[idx + len(raw) : idx + len(raw) + 70] if idx >= 0 else ""
            # The citation is wrapped in backticks PATH_RE does not capture, so the
            # window opens with the closing backtick. Strip it or this never matches.
            if REMOVED_ANNOTATION_RE.match(window.lstrip("`").lstrip()):
                historical += 1
                continue
            claims.append((raw, text[: match.start()].count("\n") + 1))
    return claims, historical


#: Control cases. A checker that cannot fail is worse than no checker, and this one was
#: vacuous twice while being written - once by counting a file that merely exists as
#: "imported", once by letting `afon` being imported vouch for everything beneath it.
#: So the teeth are asserted on every run rather than assumed.
CONTROLS = [
    ("src/afon/brain/daily_digest.py", True, "imported by scheduler.py and server.py"),
    ("src/afon/brain/mynews.py", False,
     "the real defect: on disk, named as two systems' surface, imported by nothing"),
    ("src/afon/protocols/phoenix.py", True,
     'never imported; dispatched by path from protocols.py\'s "script" key'),
    ("src/afon/edge/edge_lite.py", True, "started as `python -m afon.edge.edge_lite` by run.sh"),
    ("src/afon/brain/no_such_module_xyz.py", False, "a path that does not exist"),
]


def analyze() -> dict[str, object]:
    """The whole check in one call. `bench/test_doc_integrity.py` calls this directly,
    so the gate and this tool cannot drift apart."""
    text = DETAILS.read_text(encoding="utf-8")
    imports = collect_imports()
    literals = collect_string_literals()
    launched, scripts = collect_launchers()
    reachable = make_reachable(imports, literals, launched, scripts)
    claims, historical = surface_claims(text)
    unwired = [(rel, line) for rel, line in claims if not reachable(rel)]
    controls = [(p, want, got := reachable(p), why) for p, want, why in CONTROLS]
    return {
        "claims": claims,
        "historical": historical,
        "unwired": unwired,
        "controls": controls,
        "bad_controls": [c for c in controls if c[1] != c[2]],
        "reachable": reachable,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    if not DETAILS.is_file():
        print(f"missing {DETAILS}")
        return 1

    result = analyze()
    claims: list[tuple[str, int]] = result["claims"]  # type: ignore[assignment]
    unwired: list[tuple[str, int]] = result["unwired"]  # type: ignore[assignment]
    historical: int = result["historical"]  # type: ignore[assignment]
    reachable = result["reachable"]

    print("  control cases:")
    for path, want, got, why in result["controls"]:  # type: ignore[union-attr]
        ok = got is want
        print(f"    [{'PASS' if ok else 'FAIL'}] {path} -> reachable={got} (want {want}); {why}")

    print(f"checked {len(claims)} surface path(s) across SYSTEMS-DETAILS.md")
    print(f"  reachable            : {len(claims) - len(unwired)}")
    print(f"  NOT reachable        : {len(unwired)}")
    print(f"  skipped as removed   : {historical} (annotated in the document itself)")
    if args.verbose:
        for rel, line in sorted(claims):
            state = "BAD" if (rel, line) in unwired else "OK "
            print(f"  [{state}] {rel}  (SYSTEMS-DETAILS.md:{line})")
    else:
        for rel, line in sorted(set(unwired)):
            print(f"  - {rel}  (SYSTEMS-DETAILS.md:{line})")
    if unwired:
        print("  a 'Surfaces' line names a module nothing imports and nothing dispatches.")
        print("  Either wire it, or remove the claim - a path that exists but is dead is")
        print("  harder to catch than a phantom path, because it reads as finished work.")
    return 1 if (unwired or result["bad_controls"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())