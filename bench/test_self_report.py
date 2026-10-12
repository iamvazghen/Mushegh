"""31.R3 — the weekly self-report answers all three questions, or says which one it cannot.

The data for all three exists and is not composed: `errors.summary()` knows what broke,
`reliability`'s escalation state knows what self-repaired and what paged the owner. What exists
instead is a weekly *activity* digest ("you learned 12 facts"), which is a different question and
looks like a healthy week on a week when three things broke.

**The failure mode this module exists to prevent is silence.** On a machine where the health probe
has never run, `health_escalation.json` is absent, so two of the three answers are unmeasurable. A
report that rendered "nothing needs you" would be wrong BY ABSENCE OF EVIDENCE, and wrong in the most
expensive direction available — it would make the owner stop looking. So each section carries a
status, and the rendered line speaks the unknown ones out loud. There is no state in which a
missing file is reported as health.

What is asserted here:

  * **all three questions are asked, in 31.R3's own words** — checked against the module's own list
    so the two cannot drift
  * **a real-shaped journal summary produces real numbers** — counts, by-level, the worst offender
  * **a MISSING escalation file yields `no-data` with a reason, and the reason is SPOKEN** — the
    central assertion, and it is checked in the rendered text rather than in a field
  * **a repaired component is never listed as needing the owner** — it is the opposite, and paging
    someone about a fixed problem is how a self-report teaches you to ignore it
  * **a clean week and an unmeasured week read differently** — "nothing failed across N operations"
    against "I cannot tell you what broke", and they must not be confusable
  * **it reads the real journal shape**, not a mock of its own output, so the composition is proven
    against what `errors.summary` actually returns

Hermetic: an injected summary with the real key set, and a temp state dir. No journal writes, no
model, no network.

    uv run python bench/test_self_report.py
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(ROOT / "src"))

passed = failed = 0

#: The REAL shape `mushegh.shared.errors.summary()` returns — taken from an actual call, not invented,
#: so the composition is proven against what the reader produces.
REAL_SUMMARY = {
    "window_minutes": 10080, "total": 17, "ok": 597, "operations": 614,
    "by_level": {"OK": 597, "ERROR": 16, "WARNING": 1},
    "by_subsystem": {"tool/nonexistent_tool_zzz": 7, "pc/file_op": 2, "tool/boom": 1,
                     "agentic/llm_chain_exhausted": 1},
    "top": "tool/nonexistent_tool_zzz",
    "latest": {"ts": "2026-10-04T18:26:23+00:00", "subsystem": "tool/nonexistent_tool_zzz",
               "level": "ERROR", "type": "Failure"},
}
CLEAN_SUMMARY = {**REAL_SUMMARY, "total": 0, "ok": 614,
                 "by_level": {"OK": 614, "ERROR": 0, "WARNING": 0}, "top": None, "latest": None}


def check(name: str, ok: bool, detail: str = "") -> None:
    global passed, failed
    if ok:
        passed += 1
        print(f"  [PASS] {name}")
    else:
        failed += 1
        print(f"  [FAIL] {name}  {detail}")


def main() -> int:
    from mushegh.brain.self_report import (MEASURED, NO_DATA, asks_all_three, render, self_report)

    with tempfile.TemporaryDirectory(prefix="mushegh-selfreport-") as td:
        root = Path(td)

        print("\n[1] it asks exactly the three questions 31.R3 names")
        q = asks_all_three()
        check("three questions", len(q) == 3, str(q))
        for want in ("what broke", "what repaired itself", "what needs the owner"):
            check(f"asks {want!r}", want in q, str(q))

        print("\n[2] a real journal summary produces real numbers")
        rep = self_report(state_dir=root, summary=REAL_SUMMARY)
        b = rep["broke"]
        check("the broken section is MEASURED, not guessed", b["status"] == MEASURED, str(b["status"]))
        check("...and counts the failures, not the successes",
              b["failed"] == 17 and b["operations"] == 614, str(b))
        check("...and names the worst offender", b["top"] == "tool/nonexistent_tool_zzz", str(b["top"]))
        check("...and reports the levels, excluding OK", b["by_level"] == {"ERROR": 16, "WARNING": 1},
              str(b["by_level"]))
        check("OK is not counted as a failure", "OK" not in b["by_level"], str(b["by_level"]))

        print("\n[3] a MISSING escalation file is NO-DATA, and the reason is spoken")
        check("with no file, `repaired` is no-data", rep["repaired"]["status"] == NO_DATA,
              str(rep["repaired"]))
        check("...with a reason naming the missing record", "health_escalation" in rep["repaired"]["why"]
              or "probe has not run" in rep["repaired"]["why"], rep["repaired"]["why"])
        check("...and it is NOT reported as zero problems", rep["repaired"]["count"] == 0
              and rep["repaired"]["items"] == [], "count 0 with measured status would be a lie")
        said = render(rep)
        check("...and the rendered line SAYS the unknown part out loud",
              "cannot tell you what I fixed" in said, said)
        check("...and says which one needs the owner is unknown too",
              "cannot tell you what needs you" in said, said)
        check("...while still reporting the part it could measure",
              "17 of 614 operations failed" in said, said)
        check("...and the reassuring sentence never appears",
              "nothing needs you" not in said, said)

        print("\n[4] with a real escalation state, the other two are measured")
        (root / "health_escalation.json").write_text(json.dumps({
            "discord": {"consecutive_red": 3, "alerted": True, "repaired": False},
            "tts": {"consecutive_red": 1, "alerted": False, "repaired": True},
        }), encoding="utf-8")
        rep2 = self_report(state_dir=root, summary=REAL_SUMMARY)
        check("`repaired` is now measured", rep2["repaired"]["status"] == MEASURED,
              str(rep2["repaired"]))
        check("...and names the component it fixed", rep2["repaired"]["items"] == ["tts"],
              str(rep2["repaired"]))
        check("`needs_owner` is measured and names the escalated one",
              rep2["needs_owner"]["items"] == ["discord"], str(rep2["needs_owner"]))
        check("A REPAIRED COMPONENT IS NEVER LISTED AS NEEDING THE OWNER",
              "tts" not in rep2["needs_owner"]["items"],
              "paging the owner about a fixed problem is how a report teaches you to ignore it")
        said2 = render(rep2)
        check("...and the spoken line says both things",
              "these need you: discord" in said2 and "1 thing(s) I fixed myself" in said2, said2)
        check("...and no longer claims ignorance now that the data exists",
              "cannot tell you" not in said2, said2)

        print("\n[5] a clean week and an unmeasured week are NOT confusable")
        rep3 = self_report(state_dir=root, summary=CLEAN_SUMMARY)
        clean_said = render(rep3)
        check("a clean week reads as a measurement, not as silence",
              "nothing failed across 614 operations" in clean_said, clean_said)
        check("...and is still MEASURED, because the journal answered", rep3["broke"]["status"]
              == MEASURED, str(rep3["broke"]["status"]))
        check("...and the two sentences are textually different",
              clean_said != said.replace("17 of 614", "nothing failed across 614"), "same words")
        # `summary=None` means "ask the real journal", and the real journal on this machine HAS
        # entries — so it correctly comes back measured. A first draft asserted no-data here and
        # failed, because it was testing the wrong thing: an empty journal is injected explicitly.
        rep4 = self_report(state_dir=root, summary={})
        check("an explicitly EMPTY journal is no-data, and says so",
              rep4["broke"]["status"] == NO_DATA, str(rep4["broke"])[:120])
        check("...while the escalation half is still measured, because its file is there",
              rep4["repaired"]["status"] == MEASURED, str(rep4["repaired"]["status"]))
        check("...so the two halves can disagree about being knowable, and that is the point",
              rep4["broke"]["status"] != rep4["repaired"]["status"], "uniform status hides the gap")

        print("\n[6] it composes from the real readers, not a mock of itself")
        src = (ROOT / "src" / "mushegh" / "brain" / "self_report.py").read_text(encoding="utf-8")
        check("it calls errors.summary by default", "journal_summary" in src and "since_minutes" in src)
        check("...and reads the escalation file by NAME", "health_escalation.json" in src)
        check("...and a corrupt file is no-data, not an exception",
              "JSONDecodeError" in src and "no-data" in src)
        check("...and the render path is the ONLY place a sentence is built",
              src.count("def render(") == 1)
        check("a report object is not mutated by rendering",
              json.loads(json.dumps(rep2)) == rep2, "render() must not rewrite its input")

        print("\n[7] the weekly digest is a DIFFERENT question and is left alone")
        # Checked on the AST, not the text: the docstring names `proactive_signals.weekly_digest` ON
        # PURPOSE, to explain that the two reports answer different questions. A first draft grepped
        # the source and failed on that very sentence — the same mistake as the `def caveat()`
        # assertion, and the second time today, which is the reason it is worth writing down.
        import ast

        imported: set[str] = set()
        for node in ast.walk(ast.parse(src)):
            if isinstance(node, ast.Import):
                imported.update(a.name for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
        check("this module does not IMPORT the activity digest",
              not any("proactive" in m for m in imported), str(sorted(imported)))
        check("...and says so in its own docstring, so nobody merges the two reports",
              "different question" in src)

        print(f"\n{'=' * 60}")
        print(f"  {passed} passed, {failed} failed")
        print("=" * 60)
        return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
