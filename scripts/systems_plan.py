"""Maintain the executable part of Mushegh's 50-system plan.

``docs/systems-plan.json`` is the source of truth for system status, task state,
verification, evidence, budgets, economics, and dependencies.  ``docs/SYSTEMS.md``
is a generated dashboard.  ``docs/SYSTEMS-DETAILS.md`` is an archive of the
long-form rationale that preceded this registry.

The migration command exists only to import the legacy document once:

    uv run python scripts/systems_plan.py migrate
    uv run python scripts/systems_plan.py render
    uv run python scripts/systems_plan.py check

Do not edit SYSTEMS.md directly.  Change the registry, add evidence when a task is
completed, then render.  A completed task may retain ``legacy-plan`` evidence from
the migration, but that is visibly weaker than a dated suite, live, or manual run.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
REGISTRY = DOCS / "systems-plan.json"
DASHBOARD = DOCS / "SYSTEMS.md"
DETAILS = DOCS / "SYSTEMS-DETAILS.md"
RUNNER = ROOT / "bench" / "run_all_tests.py"
BENCH = ROOT / "bench"

SYSTEM_RE = re.compile(r"^## (S(\d\d)) \u00b7 (.+)$", re.MULTILINE)
TASK_RE = re.compile(r"^- \[([x ~])\] (\d\d)\.([FRE])(\d+) (.+)$")
TEST_RE = re.compile(r"`(test_[a-z0-9_]+\.py)`")
#: A gate does not have to be named test_*.py — 36.F5's is `check_public_clean.py`, which lives in
#: bench/ like the rest. Dropping those made a real gate read as "marked done but names no gate",
#: which is how the unpark checklist refused on a task that is in fact verified.
SCRIPT_RE = re.compile(r"`([a-z0-9_]+\.py)`")
DONE_RE = re.compile(r"\*done (\d{4}-\d{2}-\d{2})")
TIER_PREFIX = {"**Floor": "F", "**Raise**": "R", "**Elite": "E"}
#: 2026-10-03, owner charter (docs/DECISIONS.md D-02, D-27, D-28, D-47). Until this, the only
#: ways to express "this will never be built" were to delete the task — which loses the record —
#: or to leave it `open` forever, which is how 20 PostgreSQL migration tasks came to sit in the
#: plan beside a decision to abandon them. A cancelled task keeps its gate and its history and
#: leaves the denominator, so "0 of 52 elite" counts only work that is still owed.
#:
#:   cancelled  decided against. Out of scope; removed from every count.
#:   deferred   still owed, not scheduled now (waiting on an owner decision, a credential, or
#:              a prior milestone). Stays in the denominator, stops appearing as "next open".
TASK_STATES = frozenset({"open", "in-progress", "done", "cancelled", "deferred"})
OUT_OF_SCOPE = frozenset({"cancelled"})
#: What is still work. A cancelled or deferred task is never "next".
REMAINING = frozenset({"open", "in-progress"})


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _tier_of(line: str) -> str | None:
    if line.startswith("**Raise / Elite"):
        return None
    for prefix, tier in TIER_PREFIX.items():
        if line.startswith(prefix):
            return tier
    return None


def _first_line(block: str, marker: str) -> str:
    for line in block.splitlines():
        if line.startswith(marker):
            return line[len(marker):].strip()
    return ""


def _status(block: str) -> str:
    line = _first_line(block, "**Status**")
    return line.split(" · **Surfaces**", 1)[0].rstrip(" ·—").strip()


def _table_economics(block: str) -> dict[str, str]:
    lines = block.splitlines()
    for index, line in enumerate(lines):
        if line.startswith("| **") and index:
            cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
            if len(cells) == 6:
                return dict(zip(("confidence", "settled_by", "effort", "owner", "cost", "rollback"), cells))
    return {key: "" for key in ("confidence", "settled_by", "effort", "owner", "cost", "rollback")}


def _bench_scripts() -> set[str]:
    """Every gate script that exists, not only the test_*.py ones. A gate named
    `check_public_clean.py` is as real as a test, and treating it as absent marked 36.F5 a
    planned gate on a check that has been running for weeks."""
    return {path.name for path in BENCH.glob("*.py")}


def _runner_tests() -> tuple[set[str], list[str]]:
    tree = ast.parse(_read(RUNNER))
    assignment = next(
        node for node in tree.body
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "TESTS" for target in node.targets)
    )
    entries = ast.literal_eval(assignment.value)
    scripts = [entry[1] for entry in entries]
    return {name for name in scripts if name.startswith("test_")}, scripts


def _exempt_tests() -> set[str]:
    source = _read(BENCH / "test_registry_complete.py")
    tree = ast.parse(source)
    assignment = next(
        node for node in tree.body
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "EXEMPT" for target in node.targets)
    )
    return set(ast.literal_eval(assignment.value))


def _gate_kind(gate: str, tests: list[str], registered: set[str], exempt: set[str], present: set[str]) -> str:
    if "new `test_" in gate:
        return "planned-test"
    if tests:
        test = tests[0]
        if test in registered:
            return "hermetic-test"
        if test in exempt:
            return "exempt-test"
        if test in present:
            return "unregistered-test"
        return "missing-test"
    return "manual"


def _task_evidence(block: str, checked: bool, source: str) -> list[dict[str, str]]:
    dates = DONE_RE.findall(block)
    if dates:
        return [{"kind": "recorded-note", "date": date, "source": source} for date in dates]
    if checked:
        return [{"kind": "legacy-plan", "source": source}]
    return []


def _dependencies(block: str, sid: str) -> list[str]:
    found = sorted(set(re.findall(r"\bS(\d\d)\b", block)))
    return [f"S{number}" for number in found if f"S{number}" != sid]


_WAVE_ROW = re.compile(r"^\|\s*\*\*(\d+)\s*[-—][^|]*\|([^|]*)\|", re.MULTILINE)


def _waves(text: str) -> dict[str, str]:
    """System -> execution wave, read from the plan's wave table.

    Wave membership is not decoration: `scripts/unpark_check.py` refuses to unpark production
    until every Wave-0 floor is green, and it has to read that list from the plan rather than
    keep its own copy. The first migration dropped waves entirely, which left the unpark gate
    reading a table that no longer existed — it refused every time, and its test still passed
    because the test feeds the parser its own fixture.
    """
    out: dict[str, str] = {}
    for match in _WAVE_ROW.finditer(text):
        for sid in re.findall(r"\bS\d\d\b", match.group(2)):
            out[sid] = match.group(1)
    return out


def parse_legacy(details: Path) -> dict[str, Any]:
    """Import the old Markdown plan once; rendering never calls this function."""
    text = _read(details)
    waves = _waves(text)
    matches = list(SYSTEM_RE.finditer(text))
    registered, _ = _runner_tests()
    exempt = _exempt_tests()
    present = _bench_scripts()
    systems: list[dict[str, Any]] = []

    for match, next_match in zip(matches, matches[1:] + [None]):
        sid, _, title = match.groups()
        end = next_match.start() if next_match else len(text)
        body = text[match.start():end]
        line_base = text[:match.start()].count("\n") + 1
        lines = body.splitlines()
        tier: str | None = None
        tasks: list[dict[str, Any]] = []
        active: dict[str, Any] | None = None

        def close_task() -> None:
            nonlocal active
            if active is None:
                return
            block = "\n".join(active.pop("_lines"))
            gate_match = re.search(r"\*gate:\*\s*(.+)", block)
            gate = gate_match.group(1).strip() if gate_match else ""
            tests = TEST_RE.findall(block)
            # ...plus any other bench script the gate names, but only one that actually exists:
            # the plan mentions plenty of source files in passing, and a passing mention is not
            # a gate.
            for script in SCRIPT_RE.findall(block):
                if script not in tests and (BENCH / script).is_file():
                    tests.append(script)
            active["gate"] = gate
            active["test_names"] = tests
            active["verification"] = _gate_kind(gate, tests, registered, exempt, present)
            active["evidence"] = _task_evidence(block, active["state"] == "done", active["source"])
            tasks.append(active)
            active = None

        for offset, line in enumerate(lines):
            current_tier = _tier_of(line)
            if current_tier or line.startswith("**Raise / Elite"):
                close_task()
                tier = current_tier
                continue
            task = TASK_RE.match(line)
            if task and tier:
                close_task()
                checked, task_system, task_tier, number, task_title = task.groups()
                task_id = f"{task_system}.{task_tier}{number}"
                active = {
                    "id": task_id,
                    "tier": tier,
                    "state": {"x": "done", "~": "in-progress", " ": "open"}[checked],
                    "title": task_title.strip(),
                    "scope": "task",
                    "source": f"docs/SYSTEMS-DETAILS.md:{line_base + offset}",
                    "_lines": [line],
                }
            elif active is not None:
                if line.startswith(("- [", "**", "#", "|")):
                    close_task()
                else:
                    active["_lines"].append(line)
        close_task()

        economics = _table_economics(body)
        systems.append({
            "id": sid,
            "title": title,
            "wave": waves.get(sid, ""),
            "status": _status(body),
            "status_evidence": [{
                "kind": "legacy-plan",
                "source": f"docs/SYSTEMS-DETAILS.md:{line_base + 2}",
                "note": "Imported from the pre-registry plan; replace with a dated recorded run when reviewed.",
            }],
            "surfaces": _first_line(body, "**Surfaces**"),
            "budget": _first_line(body, "**Budget**"),
            "dependencies": _dependencies(body, sid),
            "economics": economics,
            "tasks": tasks,
        })

    return {
        "schema_version": 1,
        "source_of_truth": "This file is authoritative for execution state. Render docs/SYSTEMS.md after editing.",
        "detail_archive": "docs/SYSTEMS-DETAILS.md",
        "systems": systems,
    }


def _split_legacy_memory_initiative(registry: dict[str, Any]) -> None:
    """Retire the one migration-sized checkbox identified in the plan review."""
    system = next(item for item in registry["systems"] if item["id"] == "S30")
    replacement: list[dict[str, Any]] = []
    for task in system["tasks"]:
        if task["id"] != "30.F1":
            replacement.append(task)
            continue
        base = {key: value for key, value in task.items() if key not in {"id", "title", "source", "evidence"}}
        checkpoints = [
            ("30.F1a", "Centralize every persistent path under MUSHEGH_STATE_DIR.", "state-root"),
            ("30.F1b", "Move derived stores and union learned facts without overwrite.", "migration"),
            ("30.F1c", "Prove the migration rejects split-origin and destructive regressions.", "safety cases"),
        ]
        for task_id, title, evidence_note in checkpoints:
            child = dict(base)
            child.update({
                "id": task_id,
                "title": title,
                "scope": "task",
                "source": task["source"],
                "evidence": list(task["evidence"]) + [{
                    "kind": "migration-checkpoint",
                    "source": task["source"],
                    "note": evidence_note,
                }],
            })
            replacement.append(child)
    system["tasks"] = replacement


def _scope_missing_legacy_tests(registry: dict[str, Any]) -> None:
    """Make every planned test declaration local to the task that relies on it."""
    present = _bench_scripts()
    for system in registry["systems"]:
        for task in system["tasks"]:
            missing = [name for name in task["test_names"] if name not in present]
            if not missing:
                continue
            declarations = "; ".join(f"new `{name}`" for name in missing)
            task["gate"] = f"{declarations} - planned gate. {task['gate']}"
            task["verification"] = "planned-test"


def load_registry() -> dict[str, Any]:
    return json.loads(_read(REGISTRY))


def _task_counts(system: dict[str, Any]) -> dict[str, tuple[int, int]]:
    """done / in-scope, per tier.  A cancelled task leaves the denominator — it is decided
    against, so counting it would keep inflating the gap.  A deferred one stays: it is still
    owed, just not scheduled (D-45 counts only what is intended)."""
    return {
        tier: (
            sum(task["state"] == "done" for task in system["tasks"] if task["tier"] == tier),
            sum(task["tier"] == tier and task["state"] not in OUT_OF_SCOPE
                for task in system["tasks"]),
        )
        for tier in ("F", "R", "E")
    }


def _runtime_metrics() -> dict[str, str]:
    registered, scripts = _runner_tests()
    # Three different quantities, which the dashboard used to run together into one
    # sentence ("198 registered test scripts across 201 runner entries (201 distinct
    # scripts)") that reads as a contradiction. The runner also registers checks not named
    # test_*.py, and not every test file on disk is registered — some are exempt on purpose.
    metrics = {
        "runner_entries": str(len(scripts)),
        "registered_tests": str(len(registered)),
        "distinct_scripts": str(len(set(scripts))),
        "tests_on_disk": str(len(list(BENCH.glob("test_*.py")))),
        "exempt_tests": str(len(_exempt_tests())),
    }
    try:
        sys.path.insert(0, str(ROOT / "src"))
        from mushegh.brain.tools import tool_handlers, tool_schemas

        metrics["tool_schemas"] = str(len(tool_schemas()))
        metrics["tool_handlers"] = str(len(tool_handlers()))
    except Exception as error:  # noqa: BLE001
        metrics["tool_schemas"] = f"unavailable ({type(error).__name__})"
        metrics["tool_handlers"] = f"unavailable ({type(error).__name__})"
    return metrics


def render(registry: dict[str, Any]) -> str:
    systems = registry["systems"]
    metrics = _runtime_metrics()
    all_tasks = [task for system in systems for task in system["tasks"]]
    complete = sum(task["state"] == "done" for task in all_tasks)
    # Gate readiness counts work that is still owed. A cancelled task's gate will never run, and
    # reporting it as "planned" is how a decision to abandon something keeps looking like backlog.
    live_tasks = [task for task in all_tasks if task["state"] not in OUT_OF_SCOPE]
    verification = Counter(task["verification"] for task in live_tasks)
    states = Counter(task["state"] for task in all_tasks)
    evidence = Counter(item["kind"] for task in all_tasks for item in task["evidence"])
    # A dark system is code-complete and controls nothing: blocked on a credential, a device or an
    # owner decision. Its tasks are reported separately because counting them as done is the
    # specific way this plan has misled its own author (Jev p=0.85 / P=0.66).
    dark = [system for system in systems if system.get("dark")]
    dark_done = sum(task["state"] == "done" for system in dark for task in system["tasks"])
    dark_live = sum(sum(1 for task in system["tasks"] if task["state"] not in OUT_OF_SCOPE)
                    for system in dark)
    totals = {tier: [0, 0] for tier in ("F", "R", "E")}
    for system in systems:
        for tier, (done, total) in _task_counts(system).items():
            totals[tier][0] += done
            totals[tier][1] += total

    lines = [
        "<!-- Generated by scripts/systems_plan.py. Edit docs/systems-plan.json, then render. -->",
        "# Mushegh Systems Plan",
        "",
        "This is the live execution dashboard. `docs/systems-plan.json` is the authoritative source",
        "for system state, tasks, gates, evidence, budgets, dependencies, and economics. The detailed",
        "design rationale and historical notes live in `docs/SYSTEMS-DETAILS.md`; `TODO.md` is the running",
        "engineering log and may not change execution state on its own.",
        "",
        "## Maintenance",
        "",
        "- Change `docs/systems-plan.json`, add dated evidence for completed work, then run",
        "  `uv run python scripts/systems_plan.py render`.",
        "- Run `uv run python scripts/systems_plan.py check` before committing. It rejects missing or",
        "  unscoped planned tests, duplicate runner entries, invalid task ids, and dashboard drift.",
        "- Evidence kinds: `hermetic-test`, `exempt-test`, `unregistered-test`, `planned-test` and",
        "  `manual` describe a gate.",
        "  `unverified-import` evidence is an imported claim, not a fresh verification record;",
        "  the 95 former `legacy-plan` records were downgraded to it on 2026-09-20 (Jev p=0.88).",
        "  `owner-decision` records a dated instruction from the owner in `docs/DECISIONS.md`. It",
        "  is how a task is cancelled or its scope changed; it is not proof that anything works.",
        "- Task states are `open`, `in-progress`, `done`, plus `cancelled` and `deferred`",
        "  (2026-10-03). `cancelled` is decided against: it leaves every count and is listed",
        "  under Cancelled below. `deferred` is still owed, just not scheduled now, so it keeps",
        "  its place in the denominator and stops appearing as the next open task.",
        "",
        "## Current Snapshot",
        "",
        f"- {len(systems)} systems; {complete} of {len(live_tasks)} live tasks marked done.",
        f"- States: {states['open']} open, {states['in-progress']} in progress, {states['done']} done,",
        f"  {states['cancelled']} cancelled, {states['deferred']} deferred. Cancelled and deferred",
        "  tasks are listed below rather than deleted: the record is worth more than the count.",
        f"- Runner: {metrics['runner_entries']} entries, {metrics['distinct_scripts']} distinct scripts,",
        f"  {metrics['registered_tests']} of them `test_*.py`.",
        f"- Tests on disk: {metrics['tests_on_disk']}, of which {metrics['exempt_tests']} are exempt from the",
        "  hermetic suite (live, benchmark or self-referential).",
        f"- Tools: {metrics['tool_schemas']} schemas, {metrics['tool_handlers']} handlers.",
        f"- Gate readiness: {verification['hermetic-test']} hermetic, {verification['exempt-test']} exempt,",
        f"  {verification['unregistered-test']} outside the suite, {verification['planned-test']} planned,",
        f"  and {verification['manual']} manual.",
        f"- Evidence: {evidence['recorded-note']} dated plan notes, "
        f"{evidence['unverified-import'] + evidence['legacy-plan']} unverified imports.",
        f"- Dark: {len(dark)} systems are code-complete but control nothing, holding {dark_live}"
        f" live tasks ({dark_done} marked done). Listed separately below; counting dark work as done is"
        " how this plan misleads its own author.",
        "",
        "## Systems",
        "",
        "| System | Status | Floor | Raise | Elite | Next open task |",
        "|---|---|---:|---:|---:|---|",
    ]
    for system in systems:
        counts = _task_counts(system)
        # "Next open" means next work, so a cancelled or deferred task never fills this column.
        # Before, `state != "done"` was the test, which offered the owner a Postgres migration
        # task as the next thing to do on a project that had cancelled it.
        next_task = next((task for task in system["tasks"]
                          if task["state"] in REMAINING), None)
        if next_task is None:
            next_text = "-"
        else:
            next_title = next_task["title"].replace("|", "/").strip()
            if len(next_title) > 112:
                next_title = next_title[:112].rsplit(" ", 1)[0] + "..."
            next_text = f"{next_task['id']} {next_title}"
        lines.append(
            f"| {system['id']} {system['title']} | {system['status']} | "
            f"{counts['F'][0]}/{counts['F'][1]} | {counts['R'][0]}/{counts['R'][1]} | "
            f"{counts['E'][0]}/{counts['E'][1]} | {next_text} |"
        )

    settled = [
        (system, {state: [task["id"] for task in system["tasks"] if task["state"] == state]
                  for state in ("cancelled", "deferred")})
        for system in systems
    ]
    settled = [(system, states_) for system, states_ in settled
               if states_["cancelled"] or states_["deferred"]]
    lines.extend([
        "",
        "## Cancelled and deferred",
        "",
        f"{len(settled)} systems carry tasks that are no longer work. **Cancelled** is decided",
        "against and leaves every count; **deferred** is still owed but not scheduled, so it keeps",
        "its denominator and simply stops appearing as the next open task. Both keep their gate",
        "and their history, and each carries an `owner-decision` evidence entry naming the decision",
        "in `docs/DECISIONS.md` — which is the only authority for de-scoping.",
        "",
        "| System | Cancelled | Deferred |",
        "|---|---|---|",
    ])
    for system, states_ in settled:
        cancelled = ", ".join(states_["cancelled"]) or "-"
        deferred = ", ".join(states_["deferred"]) or "-"
        lines.append(f"| {system['id']} {system['title']} | {cancelled} | {deferred} |")

    lines.extend([
        "",
        "## Dark",
        "",
        "Code complete, controlling nothing. Each is unblocked by one credential, one device or one",
        "owner decision rather than by engineering - which is why they are the cheapest available",
        "wins and why they must not be read as progress.",
        "",
        "| System | Blocked on |",
        "|---|---|",
    ])
    lines.extend(
        f"| {system['id']} {system['title']} | {system.get('dark_blocker', '-')} |"
        for system in dark
    )
    lines.extend([
        "",
        "## Totals",
        "",
        f"**Totals: {totals['F'][0]} of {totals['F'][1]} floor tasks green, "
        f"{totals['R'][0]} of {totals['R'][1]} raise tasks, "
        f"{totals['E'][0]} of {totals['E'][1]} elite tasks - {complete} of {len(live_tasks)}.**",
        "",
        f"Excluding the {len(dark)} dark systems: **{complete - dark_done} of "
        f"{len(live_tasks) - dark_live}**. That is the honest figure until a credential, a device"
        " or a decision unblocks them.",
        "",
        "## Evidence Review",
        "",
        "A system status is a judgement, but it must name its evidence. On 2026-09-20 every imported",
        "claim was downgraded to `unverified-import` on the Jev directive (p=0.88, conf 0.84): a status",
        "resting on an imported claim should read as unverified even when that makes this dashboard look",
        "worse - especially then. Replace each with a dated suite, live drill or manual review when the",
        "system is next touched. The archive remains useful context, not proof.",
        "",
    ])
    return "\n".join(lines)


# ---- O5.3: the dependency graph, ratcheted ----------------------------------------------------
#: Measured 2026-09-20 on 50 systems. These are BASELINES, not targets: the existing tangle does not
#: break the build, but it cannot grow. Jev's claim (P=0.69) was that "built, not well structured" on
#: that many systems is the signature of a structural problem and that *it will get worse* - a
#: ratchet is the cheapest thing that can falsify the second half.
#:
#: Lower either number when a cycle or a violation is genuinely resolved. Raising one is a decision
#: that should be argued for in TODO.md, which is the whole point of it being here.
MAX_CYCLIC_GROUPS = 4
MAX_WAVE_VIOLATIONS = 14


def dependency_report(systems: list[dict]) -> dict:
    """Cyclic groups, wave-order violations and self-dependencies in the declared graph.

    A "wave-order violation" is a system that depends on one scheduled in a LATER wave - which means
    the wave numbers and the dependency edges disagree, and one of the two is wrong. S23 sits in
    wave 0 and depends on S32 in wave 6; that plan cannot be executed as written, whichever way it
    is eventually resolved.
    """
    ids = {s["id"] for s in systems}
    dep = {s["id"]: [x for x in (s.get("dependencies") or []) if x in ids] for s in systems}
    # ponytail: int() because waves are stored as strings - "10" < "6" as text.
    wave = {s["id"]: int(s.get("wave", 0)) for s in systems}

    # Tarjan, iterative - the recursive form is fine at 50 nodes but this file is also a linter.
    index: dict[str, int] = {}
    low: dict[str, int] = {}
    on: dict[str, bool] = {}
    stack: list[str] = []
    counter = 0
    groups: list[list[str]] = []
    for root in dep:
        if root in index:
            continue
        work = [(root, iter(dep[root]))]
        index[root] = low[root] = counter
        counter += 1
        stack.append(root)
        on[root] = True
        while work:
            v, it = work[-1]
            advanced = False
            for w in it:
                if w not in index:
                    index[w] = low[w] = counter
                    counter += 1
                    stack.append(w)
                    on[w] = True
                    work.append((w, iter(dep[w])))
                    advanced = True
                    break
                if on.get(w):
                    low[v] = min(low[v], index[w])
            if advanced:
                continue
            work.pop()
            if work:
                low[work[-1][0]] = min(low[work[-1][0]], low[v])
            if low[v] == index[v]:
                comp = []
                while True:
                    w = stack.pop()
                    on[w] = False
                    comp.append(w)
                    if w == v:
                        break
                if len(comp) > 1:
                    groups.append(sorted(comp))

    return {
        "edges": sum(len(v) for v in dep.values()),
        "cycles": sorted(groups),
        "self": sorted(v for v in dep if v in dep[v]),
        "wave_violations": sorted(
            (v, w, wave[v], wave[w]) for v in dep for w in dep[v] if wave[w] > wave[v]
        ),
        "widest_fan_out": max(((len(ws), v) for v, ws in dep.items()), default=(0, "")),
    }


# ---- O1.6: what counts as evidence, and how much of it is real ---------------------------------
#: The closed vocabulary. These were free-form until 2026-09-21, which is not a theoretical problem:
#: 14.R4's evidence was written in the same session with an invented kind and nothing noticed.
#:
#:   unverified-import   an imported claim, carried over from a document. NOT a verification.
#:   recorded-note       a statement written by whoever did the work. Auditable, not proof.
#:   migration-checkpoint a checkpoint left by the 30.F1 migration.
#:   hermetic-green      a bench test passed offline. What most of this repo can currently produce.
#:   runtime-verified    a joined trace, via 31.F5's correlation id, showed it working for real.
#:   owner-decision      a dated instruction from the owner (docs/DECISIONS.md), which is how a
#:                       task is cancelled or its scope changed. Says what was decided, never
#:                       that anything works: it is authority, not proof.
EVIDENCE_KINDS = frozenset({
    "unverified-import", "recorded-note", "migration-checkpoint", "hermetic-green",
    "runtime-verified", "owner-decision",
})

#: Jev p = 0.63: runtime evidence should REPLACE hermetic-green as the definition of done. It is not
#: enforced as a requirement, because Mushegh is parked and zero real turns have ever been measured - a
#: bar nothing can currently clear is a broken build, not a standard (the O5.3 lesson). So it is a
#: floor that only rises: every task proven against a real trace raises this number and none may be
#: quietly un-proven. O5.1 and O6 are what move it; when it approaches the done count, the definition
#: can actually be flipped and this constant deleted.
MIN_RUNTIME_VERIFIED = 0


def evidence_report(systems: list[dict]) -> dict:
    """How the registry's claims are actually supported, by kind."""
    kinds: dict[str, int] = {}
    unknown: list[str] = []
    runtime: list[str] = []
    done_without_runtime = 0
    for system in systems:
        for task in system["tasks"]:
            items = task.get("evidence") or []
            has_runtime = False
            for item in items:
                kind = item.get("kind", "") if isinstance(item, dict) else f"<{type(item).__name__}>"
                kinds[kind] = kinds.get(kind, 0) + 1
                if kind not in EVIDENCE_KINDS:
                    unknown.append(f"{task['id']}:{kind}")
                if kind == "runtime-verified":
                    has_runtime = True
            if has_runtime:
                runtime.append(task["id"])
            elif task["state"] == "done":
                done_without_runtime += 1
    return {"kinds": kinds, "unknown": sorted(set(unknown)), "runtime_verified": sorted(runtime),
            "done_without_runtime": done_without_runtime}


def validate(registry: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    systems = registry.get("systems", [])
    expected = [f"S{number:02d}" for number in range(1, 51)]
    actual = [system.get("id") for system in systems]
    if actual != expected:
        errors.append(f"systems must be S01..S50 in order, found {actual[:5]}...")

    registered, scripts = _runner_tests()
    exempt = _exempt_tests()
    present = _bench_scripts()
    duplicates = sorted(name for name, count in Counter(scripts).items() if count > 1)
    if duplicates:
        errors.append(f"runner has duplicate scripts: {duplicates}")

    seen_tasks: set[str] = set()
    for system in systems:
        sid = system.get("id", "")
        if not system.get("status_evidence"):
            errors.append(f"{sid} has no status evidence")
        if not isinstance(system.get("dependencies"), list):
            errors.append(f"{sid} dependencies must be a list")
        for task in system.get("tasks", []):
            task_id = task.get("id", "")
            if task_id in seen_tasks:
                errors.append(f"duplicate task id {task_id}")
            seen_tasks.add(task_id)
            if not re.fullmatch(r"\d\d\.[FRE]\d+[a-z]?", task_id):
                errors.append(f"invalid task id {task_id}")
            if not task_id.startswith(sid[1:] + "."):
                errors.append(f"{sid} owns mismatched task {task_id}")
            if task.get("tier") != task_id.split(".")[1][0]:
                errors.append(f"{task_id} tier disagrees with its id")
            if task.get("state") not in TASK_STATES:
                errors.append(f"{task_id} has invalid state")
            if task.get("scope") != "task":
                errors.append(f"{task_id} must be a bounded task, not an untyped initiative")
            if not task.get("gate"):
                errors.append(f"{task_id} has no named gate")
            tests = task.get("test_names", [])
            kind = task.get("verification")
            if kind == "planned-test":
                if not tests or "new `test_" not in task["gate"]:
                    errors.append(f"{task_id} has an unscoped planned gate")
                for name in tests:
                    if name not in present and f"new `{name}`" not in task["gate"]:
                        errors.append(f"{task_id} must mark missing {name} as new on the same gate")
            elif kind == "hermetic-test":
                if not tests or tests[0] not in registered:
                    errors.append(f"{task_id} claims a hermetic test that is not registered")
            elif kind == "exempt-test":
                if not tests or tests[0] not in exempt:
                    errors.append(f"{task_id} claims an exempt test without an exemption")
            elif kind == "unregistered-test":
                # A real script the hermetic runner does not carry: check_public_clean.py,
                # behavioral_suite.py, compare_stores.py. It is weaker evidence than a registered
                # test — nothing runs it on push — but calling it "manual" would hide a script that
                # exists, and calling it invalid rejected six gates that do run.
                if not tests or tests[0] not in present:
                    errors.append(f"{task_id} names a gate script that is not in bench/")
            elif kind == "manual":
                if tests:
                    errors.append(f"{task_id} has a test but calls its gate manual")
            else:
                errors.append(f"{task_id} has an invalid verification kind {kind}")
            if task["state"] == "done" and not task.get("evidence"):
                errors.append(f"{task_id} is done without evidence")
            # A cancellation is a decision, so the decision has to be on the record next to it.
            # Without this, "cancelled" becomes the cheapest way to make a number look better.
            if task["state"] in {"cancelled", "deferred"} and not any(
                isinstance(item, dict) and item.get("kind") == "owner-decision"
                for item in task.get("evidence") or []
            ):
                errors.append(f"{task_id} is {task['state']} without an owner-decision record")

    # O5.3: the graph is checked here rather than in a bench test because a dependency
    # declaration is registry data, and this function is what the registry has to pass.
    # O1.6: evidence kinds are a closed vocabulary, and the count of REAL proof only rises.
    ev = evidence_report(systems)
    if ev["unknown"]:
        errors.append(f"evidence kinds outside the vocabulary: {ev['unknown'][:6]}")
    if len(ev["runtime_verified"]) < MIN_RUNTIME_VERIFIED:
        errors.append(f"{len(ev['runtime_verified'])} runtime-verified tasks, floor is "
                      f"{MIN_RUNTIME_VERIFIED} - proof was removed, not added")
    graph = dependency_report(systems)
    if graph["self"]:
        errors.append(f"systems depend on themselves: {graph['self']}")
    if len(graph["cycles"]) > MAX_CYCLIC_GROUPS:
        errors.append(f"{len(graph['cycles'])} cyclic dependency groups, baseline is "
                      f"{MAX_CYCLIC_GROUPS}: {graph['cycles']}")
    if len(graph["wave_violations"]) > MAX_WAVE_VIOLATIONS:
        worst = graph["wave_violations"][:4]
        errors.append(f"{len(graph['wave_violations'])} wave-order violations, baseline is "
                      f"{MAX_WAVE_VIOLATIONS}: {worst}")
    return errors


def command_migrate() -> int:
    if not DETAILS.exists():
        raise SystemExit(f"{DETAILS} is required; copy the legacy plan there before migrating")
    if REGISTRY.exists():
        raise SystemExit(f"{REGISTRY} already exists; migration refuses to overwrite it")
    registry = parse_legacy(DETAILS)
    _split_legacy_memory_initiative(registry)
    _scope_missing_legacy_tests(registry)
    _write_json(REGISTRY, registry)
    DASHBOARD.write_text(render(registry), encoding="utf-8")
    return 0


def command_render() -> int:
    registry = load_registry()
    errors = validate(registry)
    if errors:
        print("Cannot render an invalid registry:")
        print("\n".join(f"- {error}" for error in errors))
        return 1
    DASHBOARD.write_text(render(registry), encoding="utf-8")
    return 0


def command_check() -> int:
    registry = load_registry()
    errors = validate(registry)
    expected = render(registry)
    if not DASHBOARD.exists() or _read(DASHBOARD) != expected:
        errors.append("docs/SYSTEMS.md is stale; run scripts/systems_plan.py render")
    if errors:
        print("SYSTEMS plan check failed:")
        print("\n".join(f"- {error}" for error in errors))
        return 1
    tasks = sum(len(system["tasks"]) for system in registry["systems"])
    print(f"SYSTEMS plan check passed: {len(registry['systems'])} systems, {tasks} bounded tasks.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("migrate", "render", "check"))
    args = parser.parse_args()
    return {"migrate": command_migrate, "render": command_render, "check": command_check}[args.command]()


if __name__ == "__main__":
    raise SystemExit(main())
