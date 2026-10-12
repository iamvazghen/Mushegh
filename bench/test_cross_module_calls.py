"""Every cross-module attribute a tool calls must exist.

Found by reading a passing tool rather than a failing one. A refactor retired
Google Fit support and deleted `vitals.read_health_file`; `import_health` still
called it. The file still parsed, still imported, still had a registered schema,
and every other gate stayed green -- because nothing called the tool. On a real
request it raised AttributeError, and `tool_error` classified that as a
MALFORMED CALL, so Mushegh told the owner his request was bad when in fact our
own code referenced a function that no longer existed.

That is the worst shape this repo has: a capability the model can see, that
fails every time, and answers with a confident wrong reason. It is the same
family as `routine` and the day-planning tools (advertised, unrouted) and the
`0 THEATRE` audit (claimed to have checked nothing).

What this does: for every tool module, find the brain modules it imported and
the attributes it reaches for on them, and assert those attributes exist. It is
static, so nothing is called and nothing can have a side effect -- the point is
the call graph is resolvable, not that invoking it is safe.

It does NOT prove a handler works. That is what test_error_handling and the
per-tool tests are for. This only proves there is no dangling name, which is the
cheapest possible failure to miss and the one that hides best.

Hermetic, offline, imports only the package.

    uv run python bench/test_cross_module_calls.py
"""

from __future__ import annotations

import ast
import importlib
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
BRAIN = ROOT / "src" / "mushegh" / "brain"
PKG = "mushegh.brain"

passed = failed = 0


def check(ok: bool, name: str, detail: str = "") -> None:
    global passed, failed
    if ok:
        passed += 1
        print(f"  [PASS] {name}")
    else:
        failed += 1
        print(f"  [FAIL] {name}  {detail}")


def imported_modules(tree: ast.Module) -> dict[str, str]:
    """local alias -> dotted module path, for `from mushegh... import x` forms."""
    aliases: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("mushegh"):
            for a in node.names:
                # `from mushegh.brain import vitals` binds `vitals` to the module
                aliases[a.asname or a.name] = f"{node.module}.{a.name}"
        elif isinstance(node, ast.Import):
            for a in node.names:
                if a.name.startswith("mushegh"):
                    aliases[a.asname or a.name] = a.name
    return aliases


def main() -> int:
    files = sorted(BRAIN.rglob("*.py"))
    check(bool(files), "brain modules found to check", str(len(files)))

    unresolved: list[str] = []
    import_errors: list[str] = []
    checked = 0

    for path in files:
        try:
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(path))
        except (OSError, SyntaxError, UnicodeDecodeError) as e:
            import_errors.append(f"{path.name}: {e}")
            continue

        rel = path.relative_to(ROOT / "src").with_suffix("")
        modname = ".".join(rel.parts)
        aliases = imported_modules(tree)

        # Names bound to a MODULE get their attributes resolved; names bound to a
        # plain function or class are the module's own, not ours to check here.
        for local, dotted in aliases.items():
            try:
                target = importlib.import_module(dotted)
            except ModuleNotFoundError:
                # `from mushegh.brain.vitals import Reading` — a symbol, not a module.
                parent, _, leaf = dotted.rpartition(".")
                try:
                    target = importlib.import_module(parent)
                except Exception:
                    continue
                if not hasattr(target, leaf):
                    unresolved.append(f"{path.name}: `{local}` -> {dotted} (import failed)")
                continue
            except Exception as e:  # noqa: BLE001
                import_errors.append(f"{path.name}: importing {dotted} raised {type(e).__name__}")
                continue

            for node in ast.walk(tree):
                if (isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name)
                        and node.value.id == local):
                    checked += 1
                    if not hasattr(target, node.attr):
                        unresolved.append(f"{path.name}:{node.lineno}: {dotted}.{node.attr}")

    print(f"\n[1] every brain module imports ({checked} attribute uses resolved)")
    check(not import_errors, "no brain module fails to import",
          "; ".join(import_errors[:6]))

    print("\n[2] no name a tool calls has been deleted out from under it")
    check(not unresolved, "every cross-module attribute exists",
          "; ".join(sorted(set(unresolved))[:8]))

    print(f"\n  {passed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())