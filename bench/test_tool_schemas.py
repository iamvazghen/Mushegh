"""Every advertised tool must be one the model can actually call.

A tool schema is the model's only documentation of a capability. If it is
malformed the call fails at the provider rather than here: a missing `required`
list, a required property that does not exist in `properties`, an empty
description, or a description that stops mid-sentence. None of those raise in
this codebase, and every one of them is invisible in a diff — the tool is
registered, the gate is green, and the failure appears as "the model called it
wrong" with nothing pointing at the schema.

The osint group is why this file exists. Fifteen tools across three modules
shipped with no test that looked at them at all — `test_tool_usage.py` reported
them as "advertised to the model and checked by nothing", and the only reason
other tools escaped the same fate is that their names happen to appear in a
comment somewhere in bench/. That gate counts a mention, not an assertion, which
is a weak signal for the whole registry rather than a gap in fifteen tools.

Hermetic, offline, no imports beyond the registry itself.

    uv run python bench/test_tool_schemas.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from mushegh.brain.tools import tool_schemas, tool_names  # noqa: E402

passed = failed = 0

#: A description shorter than this tells the model when NOT to use the tool badly.
MIN_DESCRIPTION = 40


def check(ok: bool, name: str, detail: str = "") -> None:
    global passed, failed
    if ok:
        passed += 1
        print(f"  [PASS] {name}")
    else:
        failed += 1
        print(f"  [FAIL] {name}  {detail}")


def main() -> int:
    schemas = tool_schemas()
    print(f"\n[1] every advertised tool is callable ({len(schemas)} schemas)")
    check(bool(schemas), "the registry is not empty", str(len(schemas)))

    names: list[str] = []
    malformed: list[str] = []
    thin: list[str] = []
    bad_required: list[str] = []

    for schema in schemas:
        fn = schema.get("function") if isinstance(schema, dict) else None
        if schema.get("type") != "function" or not isinstance(fn, dict):
            malformed.append(f"<not a function schema>: {str(schema)[:60]}")
            continue

        name = fn.get("name")
        if not isinstance(name, str) or not name:
            malformed.append("<no name>")
            continue
        names.append(name)

        desc = fn.get("description") or ""
        if len(desc.strip()) < MIN_DESCRIPTION:
            thin.append(f"{name} ({len(desc.strip())} chars)")

        params = fn.get("parameters")
        if not isinstance(params, dict) or params.get("type") != "object":
            malformed.append(f"{name}: parameters is not an object schema")
            continue

        props = params.get("properties")
        if props is not None and not isinstance(props, dict):
            malformed.append(f"{name}: properties is not an object")
            continue
        props = props or {}

        required = params.get("required")
        if required is not None:
            if not isinstance(required, list):
                malformed.append(f"{name}: required is not a list")
            else:
                missing = [r for r in required if r not in props]
                if missing:
                    bad_required.append(f"{name}: {missing}")

    check(not malformed, "every schema is a well-formed function schema",
          "; ".join(malformed[:6]))
    check(not thin, f"every description is at least {MIN_DESCRIPTION} chars",
          "; ".join(thin[:6]))
    check(not bad_required, "every required property exists in properties",
          "; ".join(bad_required[:6]))

    print("\n[2] the registry is a set, not a bag")
    check(len(names) == len(set(names)), "no duplicate tool names",
          str(sorted({n for n in names if names.count(n) > 1})))
    check(set(names) == set(tool_names()), "schemas and tool_names() agree",
          str(sorted(set(names) ^ set(tool_names()))[:8]))
    bad_name = [n for n in names if not re.fullmatch(r"[a-z][a-z0-9_]*", n)]
    check(not bad_name, "every name is a snake_case identifier", str(bad_name[:6]))

    print(f"\n  {passed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())