"""Can these gates actually fail? A mutation audit, run against the real files.

The external assessment (`docs/JEV-REPORT.md`, 2026-09-20) named **verification theatre** as the
largest process risk at p = 0.78, and said all fifty systems scored **below 0.50** on whether their
gates would catch real failure. Three times in one session a probe reported a confident wrong number
because it could not see what it was naming. So this asks the cheap question directly, per gate:

    break the thing the gate guards  ->  does the gate notice?

Every mutation edits a real file, runs the gate, and restores the file from a byte-exact backup taken
immediately beforehand. The audit is a no-op on exit and prints the restoration check it performed.

    uv run python tools/audit_gate_sensitivity.py
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = ROOT / ".venv" / "Scripts" / "python.exe"


@dataclass
class Mutation:
    name: str
    target: Path            # file to sabotage
    old: str                # text that must be present
    new: str                # replacement
    gate: str               # gate that should notice
    why: str                # what the gate is supposed to be protecting


def _p(rel: str) -> Path:
    return ROOT / rel


CASES: list[Mutation] = [
    Mutation(
        name="trivial reads stop being skipped",
        target=_p("src/mushegh/brain/agent.py"),
        old="        return len(names) == 1 and names[0] in _ZERO_ARG_READS",
        new="        return False  # AUDIT: the skip is disabled on purpose",
        gate="test_jev_call_budget.py",
        why="01.J1's 0.96 recommendation: a router-resolved zero-arg read must spend no Jev call",
    ),
    Mutation(
        name="the arbitration budget is widened 12x",
        target=_p("src/mushegh/config.py"),
        old="jev_arbitration_timeout_seconds: float = 0.4",
        new="jev_arbitration_timeout_seconds: float = 5.0  # AUDIT",
        # The gate that PINS the constant, not the one that exercises the behaviour. These are two
        # different claims and only one of them can fail on this mutation:
        #   test_jev_tool_arbitration.py  injects stub transports and tests behaviour, so it is
        #     designed never to read the shipped number — correct as a test, and useless as the
        #     audit's witness for this case.
        #   test_jev_arbitration_cap.py   reads settings.jev_arbitration_timeout_seconds and pins
        #     it to 0.4, so it goes RED when the number moves. That is 01.J9's actual fix.
        # Pointing this case at the behavioural gate made the audit report a CLOSED finding as
        # open — verified 2026-10-11: with the cap at 5.0, test_jev_arbitration_cap.py is 3/5 and
        # test_jev_tool_arbitration.py is fully green. The tool had started reporting a fixed
        # problem as unfixed, which is the same failure it exists to catch.
        gate="test_jev_arbitration_cap.py",
        why="a Jev verdict that arrives long after the turn is worthless; the cap is the contract",
    ),
    Mutation(
        name="the wizard-state store is undeclared",
        target=_p("src/mushegh/brain/data_classes.py"),
        old='    _s("wizard-state.json", (ORDINARY,), False,',
        # Removing the line entirely, not renaming it: a rename leaves the store DECLARED under a
        # different name, which is a different mutation and taught this audit nothing.
        new='    # AUDIT: the wizard-state store is no longer declared',
        gate="test_data_classification.py",
        why="every store the brain writes must be classified; an undeclared one is how data leaks",
    ),
    Mutation(
        name="the loop registry stops knowing its own loops",
        target=_p("src/mushegh/brain/loops.py"),
        old="DECLARED: tuple[Loop, ...] = (",
        new="AUDIT_NO_DECLARED: tuple[Loop, ...] = ()",
        gate="test_loop_registry.py",
        why="a background loop nobody declared is a loop nobody can switch off",
    ),
]


def run_gate(gate: str) -> bool:
    """True when the gate PASSES. Raises on a broken environment."""
    proc = subprocess.run(
        [str(PY), str(ROOT / "bench" / gate)],
        cwd=str(ROOT), capture_output=True, text=True, timeout=600,
    )
    return proc.returncode == 0


def main() -> int:
    if not PY.is_file():
        print("venv python not found; run through uv.")
        return 2
    backup = Path(tempfile.mkdtemp(prefix="gate-audit-"))
    print("gate sensitivity audit — does each gate go RED when its subject is broken?\n")
    header = f"{'gate':32}{'before':>8}{'after':>8}{'caught?':>10}"
    print(header)
    print("-" * len(header))

    caught = missed = 0
    problems: list[str] = []

    for case in CASES:
        original = case.target.read_text(encoding="utf-8")
        if case.old not in original:
            print(f"{case.gate:32}{'n/a':>8}{'n/a':>10}   ANCHOR TEXT MISSING — audit cannot run")
            problems.append(f"{case.name}: anchor text not found in {case.target}")
            continue

        copy = backup / case.target.name
        shutil.copy2(case.target, copy)
        before_bytes = copy.read_bytes()
        try:
            before = run_gate(case.gate)
            case.target.write_text(original.replace(case.old, case.new, 1), encoding="utf-8")
            after = run_gate(case.gate)
            verdict = "YES" if (before and not after) else ("NO - THEATRE" if before and after else "?")
            if before and not after:
                caught += 1
            elif before and after:
                missed += 1
                problems.append(f"{case.gate} stayed GREEN with {case.name} broken")
            print(f"{case.gate:32}{'pass' if before else 'FAIL':>8}"
                  f"{'pass' if after else 'RED':>8}{verdict:>10}")
        finally:
            # Restore from the BYTES we copied, and verify against those same bytes. Comparing to
            # `original.encode()` is wrong: read_text() applies universal newlines, so re-encoding a
            # CRLF file yields LF and every restore reports as a failure. That bug made four clean
            # restores look broken on the first run.
            shutil.copy2(copy, case.target)
            restored = case.target.read_bytes() == before_bytes
            if not restored:
                problems.append(f"RESTORE FAILED for {case.target}")
            else:
                print(f"{'':32}{'':8}{'restored':>8}{'ok':>10}")

    print(f"\ncaught {caught}/{caught + missed} — a gate that stays green while its subject is "
          f"broken cannot be evidence of anything")
    if problems:
        print("\nproblems:")
        for p in problems:
            print(f"  - {p}")
    else:
        print("every gate tested went RED when its subject was broken, and every file restored.")

    shutil.rmtree(backup, ignore_errors=True)
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main())