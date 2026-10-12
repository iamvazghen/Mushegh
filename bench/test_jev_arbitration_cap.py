"""The arbitration cap is a charter number, and until now no test read it.

Found by `tools/audit_gate_sensitivity.py`, which widens `jev_arbitration_timeout_seconds` from
0.4 s to 5.0 s and re-runs the gates. `test_jev_tool_arbitration.py` **stays green** — because it
injects stub transports (`transport=must_not_call`, `transport=slow`, …) and never reads the
configured cap at all. Nothing else in `bench/` mentions the number either.

That is not an abstract gap. This cap is why **63% of turns lose their Jev decision**
(5,437 recorded failures are literally `timeout_0.4s`), it is what "the verdict must arrive inside
the turn" means in practice (D-92/D-74), and it could have been widened twelvefold by anyone
editing one line, with a fully green suite and no signal at all.

So this gate reads the number instead of the behaviour: the behaviour is already covered
hermetically, and the number is what nothing covered. If the cap should change, this gate is
supposed to fail — that failure is the point, and changing it is meant to be a deliberate act with
a decision attached rather than an accident.

    uv run python bench/test_jev_arbitration_cap.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mushegh.config import settings  # noqa: E402

#: The charter value. 0.4 s is what 5,437 recorded timeouts are measured against and what the
#: subsystem document quotes; changing it means the latency story in those documents is stale.
CHARTER_CAP_S = 0.4

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


def main() -> int:
    cap = float(settings.jev_arbitration_timeout_seconds)
    print("the Jev arbitration cap is a configured number, not only a tested behaviour")

    print("\n[1] the cap still exists and is positive")
    check("the setting is present", hasattr(settings, "jev_arbitration_timeout_seconds"))
    check("the cap is positive", cap > 0, f"{cap}")

    print("\n[2] the cap is the charter value")
    check(f"the cap is still {CHARTER_CAP_S}s", abs(cap - CHARTER_CAP_S) < 1e-9, f"found {cap}")
    check("it is small enough to be a VOICE turn", cap <= 1.0, f"{cap}s")

    print("\n[3] the budget the subsystem document quotes is this number")
    # The recorded failure string embeds the cap, so a cap change leaves every historical
    # `timeout_0.4s` in the judgement log referring to a number the system no longer uses.
    log = ROOT / "docs" / "subsystems" / "01-brain-core-intelligence.md"
    text = log.read_text(encoding="utf-8", errors="replace") if log.is_file() else ""
    check("the subsystem doc still quotes the cap", f"{CHARTER_CAP_S}" in text and "400" in text)

    print(f"\n=== {_passed}/{_passed + _failed} checks passed ===")
    if _failed:
        print("  If this cap is changing on purpose, update the decision that owns it AND the")
        print("  recorded timeouts in ~/.mushegh/jev_judgments.jsonl, which carry the old value.")
    return 1 if _failed else 0


if __name__ == "__main__":
    sys.exit(main())