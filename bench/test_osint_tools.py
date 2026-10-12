"""Per-tool coverage for the osint group — fifteen tools, one assertion each.

The group (osint, osint_person, osint_advanced) shipped with nothing that looked
at it. `test_tool_usage.py` reported all fifteen as "advertised to the model and
checked by nothing", and `test_catalogue_narrowing.py` reported the group itself
as unexercised by the router corpus. Two gates, one cause: a new lazy group
arrived without a single test written alongside it.

The gate that caught it counts a tool as covered when its name appears anywhere
in bench/ — including in a comment, which is how tools like `weather` pass. That
is a weak signal for the registry as a whole, so this file is deliberately not
built to satisfy it. It asserts something per tool instead:

  * the tool is registered, and registered under the osint group rather than core;
  * it has a callable schema with a usable description;
  * it has a handler;
  * and — the part that actually matters — the group carries a trigger that
    reaches it.

That last one is the defect this repo has been bitten by twice (see
test_tool_reachability.py: `routine` and the day-planning tools were advertised
and unrouted). A tool with no trigger is a tool the owner can never summon, and
nothing else in the suite would say so.

Hermetic: reads the registry only, makes no network call.

    uv run python bench/test_osint_tools.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from mushegh.brain import tools as T  # noqa: E402

passed = failed = 0

GROUP = "osint"

#: tool -> (module that must define it, a word that must appear in its triggers or
#: its schema description, so the tool is reachable by something the owner says).
#:
#: The second element is the assertion that carries the weight: it is what makes
#: "registered" mean "reachable".
OSINT_TOOLS: dict[str, tuple[str, str]] = {
    "convert_currency": ("osint", "currency"),
    "whois_lookup": ("osint", "whois"),
    "ip_geolocate": ("osint", "geolocat"),
    "ssl_cert_info": ("osint", "cert"),
    "search_arxiv": ("osint", "arxiv"),
    "dns_lookup": ("osint_person", "dns"),
    "email_verify": ("osint_person", "email"),
    "phone_info": ("osint_person", "carrier"),
    "username_search": ("osint_person", "username"),
    "website_info": ("osint_person", "website"),
    "breach_check": ("osint_advanced", "breach"),
    "reverse_ip_lookup": ("osint_advanced", "reverse ip"),
    "github_profile": ("osint_advanced", "github"),
    "business_lookup": ("osint_advanced", "company"),
    "hash_lookup": ("osint_advanced", "hash"),
}


def check(ok: bool, name: str, detail: str = "") -> None:
    global passed, failed
    if ok:
        passed += 1
        print(f"  [PASS] {name}")
    else:
        failed += 1
        print(f"  [FAIL] {name}  {detail}")


def main() -> int:
    group_modules = {m.__name__.rsplit(".", 1)[-1] for m in T._LAZY_GROUPS[GROUP]}
    schema_by_name = {s["function"]["name"]: s for s in T.tool_schemas()}
    triggers = " ".join(T.LAZY_GROUP_TRIGGERS.get(GROUP, ())).lower()

    print(f"\n[1] the group is the shape the registry declares ({len(OSINT_TOOLS)} tools)")
    check(
        group_modules == {m for m, _ in OSINT_TOOLS.values()},
        "the osint group holds exactly the modules these tools come from",
        f"modules={sorted(group_modules)}",
    )

    print("\n[2] every tool is registered, has a schema, and a handler")
    missing, thin, unhandled = [], [], []
    for tool in OSINT_TOOLS:
        schema = schema_by_name.get(tool)
        if schema is None:
            missing.append(tool)
            continue
        if len((schema["function"].get("description") or "").strip()) < 40:
            thin.append(tool)
        if not callable(getattr(T, f"{GROUP}_handler", None)) and tool not in _all_handler_names():
            unhandled.append(tool)

    check(not missing, "every osint tool is in the live registry", str(missing))
    check(not thin, "every osint tool describes itself to the model", str(thin))
    check(not unhandled, "every osint tool has a handler", str(unhandled))

    print("\n[3] every tool is REACHABLE — registered is not the same as summonable")
    unreachable = [
        f"{tool} (no '{needle}')"
        for tool, (_, needle) in OSINT_TOOLS.items()
        if needle not in triggers
    ]
    check(
        not unreachable,
        "each tool has a trigger phrase the owner could actually say",
        "; ".join(unreachable),
    )

    print(f"\n  {passed} passed, {failed} failed")
    return 1 if failed else 0


def _all_handler_names() -> set[str]:
    """Every name in any tool module's HANDLERS mapping."""
    names: set[str] = set()
    for modules in T._LAZY_GROUPS.values():
        for module in modules:
            handlers = getattr(module, "HANDLERS", None)
            if isinstance(handlers, dict):
                names.update(handlers)
    return names


if __name__ == "__main__":
    raise SystemExit(main())