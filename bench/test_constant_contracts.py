"""Thirteen shipped numbers that no gate could see. Found by `tools/audit_constant_coverage.py`.

§01.J9 established the pattern with one constant: widen `jev_arbitration_timeout_seconds` from 0.4
to 5.0, and `test_jev_tool_arbitration.py` stays green, because it exercises *behaviour* with
injected transports and never reads the shipped number. `test_jev_arbitration_cap.py` was added to
pin that one.

`audit_constant_coverage.py` scaled the same question to all 268 constants in `config.py` and broke
them for real, in two tranches. Thirteen **stayed green**:

    memory_autorecall_limit  4 -> 40        memory_vault_search_budget_s  6.0 -> 60.0
    autonomy_max_calls       200 -> 2000    copilot_max_steps             6 -> 60
    code_self_improve_max_steps  8 -> 80    intervention_lead_minutes     10 -> 100
    objectives_max_steps     6 -> 60        vault_search_max_results      6 -> 60
    wake_listen_window_s      8.0 -> 80.0    objectives_max                2 -> 20
    vad_enabled              True -> False  memory_recall_limit           5 -> 50
                                autonomy_max_usd            2.0 -> 20.0

None of these is an abstract gap. They are, in order:

  memory_autorecall_limit   the cap on how many memory hits enter ONE turn (agent.py). An
                            injection bug is measured by exactly this number.
  autonomy_max_calls        the governor's call ceiling — the condition `docs/JEV-REPORT.md`
                            scored p=0.89 and named as making unparking safe (01.J8). Its whole
                            justification is a runaway loop already having burned ~565M tokens.
  autonomy_max_usd          the governor's SPEND ceiling. The sibling of the above, and the more
                            dangerous half: a bound on how MUCH runs is not a bound on what it COSTS.
  code_self_improve_max_steps   the bound on the code-writing worker.
  objectives_max_steps      the bounded worker step budget per objective.
  objectives_max            how many objectives a pass advances. Together with the line above, the
                            whole bound on background work per turn.
  wake_listen_window_s      how long the mic stays open after a wake. Voice latency, not a detail.
  vad_enabled               whether voice-activity detection runs at all.
  copilot_max_steps         the co-pilot background worker's budget — "bounded work loop" as a
                            phrase, rather than one.
  intervention_lead_minutes how far ahead of a commitment the owner is warned. Fails by over-warning:
                            a lead too long is noise he learns to ignore, and no gate sees that.
  memory_vault_search_budget_s  the wall-clock budget on a vault search. Search is the slowest
                            thing the owner can ask for, so this number is the feature's latency.
  vault_search_max_results  hits returned before a vault search truncates. Too few and a real
                            answer is cut off, which reads as the answer not existing.
  memory_recall_limit       the cap on hits the recall TOOL returns, sibling to
                            memory_autorecall_limit and the one a caller can reach directly.

So this gate reads the numbers instead of the behaviour. The behaviour is already covered
hermetically; the numbers are what nothing covered. **If one of these should change, this gate is
supposed to fail** — that failure is the point, and the change is meant to be deliberate with a
decision attached rather than an accident that leaves the suite green.

Two things this asserts beyond the literal values, both of which have their own failure mode:

  **Every one of them is still load-bearing.** A setting nothing reads is not a contract, it is a
  comment with a type. If a refactor stops reading a number, this fails rather than letting it sit
  in `config.py` looking enforced for the rest of time.

  **The `getattr` fallbacks agree with the defaults.** `governor.py` reads its ceilings as
  `getattr(settings, "autonomy_max_calls", 200)` — defensive defaults that *duplicate* the
  configured value. That is the same class of blind spot from the other direction: rename the
  setting and the governor silently keeps 200 forever, no error, no test. These numbers are
  asserted equal so a rename cannot pass unnoticed.

    uv run python bench/test_constant_contracts.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mushegh.config import settings  # noqa: E402

#: name -> (shipped value, what it governs, the module that must still read it)
CONTRACTS: dict[str, tuple[object, str, str]] = {
    "memory_autorecall_limit": (
        4, "memory hits injected per turn", "mushegh/brain/agent.py"),
    "autonomy_max_calls": (
        200, "governor call ceiling per window (36.F6)", "mushegh/brain/governor.py"),
    "code_self_improve_max_steps": (
        8, "steps the code-writing worker may take", "mushegh/brain/code_improve.py"),
    "objectives_max_steps": (
        6, "worker step budget per objective", "mushegh/brain/agent.py"),
    "wake_listen_window_s": (
        8.0, "how long the mic stays open after a wake", "mushegh/edge/assistant.py"),
    "vad_enabled": (
        True, "whether voice-activity detection runs at all", "mushegh/edge/assistant.py"),

    # ---- tranche 2: the bounds that decide when work STOPS (01.J14, second pass) ----
    "autonomy_max_usd": (
        2.0, "governor SPEND ceiling per window — the sibling of autonomy_max_calls", "mushegh/brain/governor.py"),
    "memory_vault_search_budget_s": (
        6.0, "wall-clock budget on a vault search — this number IS the feature's latency", "mushegh/brain/memory.py"),
    "copilot_max_steps": (
        6, "step budget for the co-pilot's background worker", "mushegh/brain/agent.py"),
    "intervention_lead_minutes": (
        10, "how far ahead of a commitment the owner gets warned", "mushegh/brain/interventions.py"),
    "vault_search_max_results": (
        6, "hits returned before a vault search truncates", "mushegh/brain/tools/vault.py"),
    "objectives_max": (
        2, "objectives advanced per pass — the sibling of objectives_max_steps", "mushegh/brain/agent.py"),
    "memory_recall_limit": (
        5, "hits the recall TOOL returns — the sibling of memory_autorecall_limit", "mushegh/brain/tools/memory.py"),

    # ---- tranche 3 (01.J14d) --------------------------------------------------------------------
    # Two of these were picked for being safety-relevant rather than merely unguarded: one REMOVES
    # a privileged surface when flipped, the other NARROWS the paths that surface refuses to touch
    # to somewhere that does not exist — a protection that still passes every test.
    "system_tools_enabled": (
        True, "whether the privileged system tools exist at all", "mushegh/brain/tools/system.py"),
    "coding_tools_enabled": (
        True, "whether the coding capability is in the tool belt", "mushegh/brain/tools/coding.py"),
    "system_protected_paths": (
        "C:\\Windows,C:\\Program Files,C:\\Program Files (x86)",
        "the paths the privileged tools refuse to touch", "mushegh/brain/tools/system.py"),
    "memory_semantic_weight": (
        4.0, "how far a semantic hit outranks a lexical one in recall ranking", "mushegh/brain/memory.py"),
    "intervention_urgency": (
        0.9, "the interrupt-vs-queue threshold, between context_override and quiet_override",
        "mushegh/brain/interventions.py"),
    "vad_confidence": (
        0.6, "the Silero speech-probability threshold (0..1)", "mushegh/edge/vad_bargein.py"),
    "jev_timeout_seconds": (
        8.0, "how long a turn waits for its advisor before giving up", "mushegh/brain/judgment.py"),
    "browser_nav_timeout_ms": (
        30000, "Playwright's default timeout for every navigation", "mushegh/brain/tools/browser.py"),
    "backlog_max_tasks": (
        2, "tasks attempted per daily pass — the sibling of copilot_max_steps", "mushegh/brain/agent.py"),
    "a2a_poll_seconds": (
        2.0, "the poll interval that is the floor on every agent-to-agent answer", "mushegh/brain/a2a.py"),
}

#: `getattr(settings, "name", <fallback>)` — the duplicated-default hazard described above.
#: The fallback must equal the configured value or a rename would go unnoticed.
GETATTR_FALLBACKS: dict[str, object] = {
    "autonomy_max_calls": 200,
    # Same hazard, and the more dangerous of the pair: a governor with a pinned call ceiling but a
    # silently-renamed spend ceiling bounds how MUCH runs and never how much it COSTS.
    "autonomy_max_usd": 2.0,
}

_passed = 0
_failed = 0


def check(label: str, ok: bool, detail: str = "") -> None:
    global _passed, _failed
    if ok:
        _passed += 1
        print(f"  PASS  {label}")
    else:
        _failed += 1
        print(f"  FAIL  {label}" + (f"  [{detail}]" if detail else ""))


def _source_text(rel: str) -> str:
    path = ROOT / "src" / rel
    return path.read_text(encoding="utf-8", errors="replace") if path.is_file() else ""


def main() -> int:
    print(f"{len(CONTRACTS)} shipped numbers, read directly instead of inferred from behaviour")

    print("\n[1] each setting still exists and is the shipped value")
    for name, (expected, governs, _reader) in CONTRACTS.items():
        actual = getattr(settings, name, None)
        check(f"{name} is {expected!r}", actual == expected, f"found {actual!r}")
        check(f"{name} is still the number that governs {governs}",
              actual is not None and expected is not None)

    print("\n[2] each one is still READ by the code that depends on it")
    # A setting nothing reads is a comment with a type. Scanned outside config.py so a constant
    # cannot vouch for itself.
    for name, (_expected, governs, rel) in CONTRACTS.items():
        text = _source_text(rel)
        if not text:
            check(f"{rel} exists", False, "file not found")
            continue
        # Either attribute access (`settings.name`) or a getattr fallback — the governor uses
        # the latter, which is why a plain `settings.name` search is not sufficient on its own.
        read = re.search(rf"settings\.{re.escape(name)}\b", text) or \
            re.search(rf"getattr\(\s*settings\s*,\s*[\"']{re.escape(name)}[\"']", text)
        check(f"{rel} reads {name}", read is not None,
              "no reader found — the constant is dead" if read is None else "")

    print("\n[3] defensive getattr fallbacks still match the configured defaults")
    for name, fallback in GETATTR_FALLBACKS.items():
        text = _source_text("mushegh/brain/governor.py")
        found = re.search(
            rf"getattr\(\s*settings\s*,\s*[\"']{re.escape(name)}[\"']\s*,\s*([^)]+)\)", text)
        if not found:
            check(f"governor.py still reads {name} via getattr", False, "pattern gone")
            continue
        actual_fallback = float(found.group(1).strip())
        configured = float(getattr(settings, name))
        check(f"governor's {name} fallback ({actual_fallback:g}) == configured ({configured:g})",
              actual_fallback == configured,
              "a rename would silently keep the old number forever")
        check(f"the literal fallback is the documented {fallback!r}",
              actual_fallback == float(fallback), f"found {actual_fallback:g}")

    print(f"\n=== {_passed}/{_passed + _failed} checks passed ===")
    if _failed:
        print("  If one of these is changing on purpose, change the decision that owns it and")
        print("  the number quoted in docs/subsystems/. Silence here is the bug these gates exist")
        print("  to prevent — see 01.J9 and 01.J14.")
    return 1 if _failed else 0


if __name__ == "__main__":
    sys.exit(main())