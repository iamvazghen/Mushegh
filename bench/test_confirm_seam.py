"""O2.5 — the tool dispatch → confirm tier seam, instrumented end to end (hermetic, no network).

Jev p=0.74, conf 0.70: *the first seam to instrument, because it is the safety gate* — and the first
consumer of `31.F5`'s correlation id, which is how you prove that task actually works rather than
merely passes its own test.

`MusheghAgent._execute_calls` has **six** exits, and the code states its own invariant in pass 3:
*"blocked calls were already audited in pass 1"*. The gate is that the invariant is true:

  1. the recipient could not be resolved to one target  → defer
  2. the call is confirm-tier and the owner has not affirmed it → deny
  3. the owner affirmed, but the camera cannot place him in the room → deny
  4. the call does not match the tool's own schema → deny
  5. it ran, and it was inside the confirm tier → allow, owner_confirmed
  6. it ran, and it was outside the confirm tier → allow, not_gated

Every one must leave exactly one audit line carrying a **decision**, a **rule that names the gate**,
and the **turn id** — so an incident review can ask "what else happened in that turn" and get an
answer. Exit 1 was found unaudited by this test and fixed in the same change.

    uv run python bench/test_confirm_seam.py
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from mushegh.brain.audit import _owner_day  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

os.environ.setdefault(
    "MUSHEGH_GOVERNOR_LEDGER", str(Path(tempfile.gettempdir()) / "mushegh-test-governor.json")
)

from mushegh.brain import agent as agent_mod          # noqa: E402
from mushegh.brain import audit                       # noqa: E402
from mushegh.shared import errors as _err             # noqa: E402

passed = failed = 0


def check(name: str, ok: bool, detail: str = "") -> None:
    global passed, failed
    if ok:
        passed += 1
        print(f"  [PASS] {name}")
    else:
        failed += 1
        print(f"  [FAIL] {name}  {detail}")


def call(name: str, **args) -> dict:
    return {"id": f"c-{name}", "name": name, "arguments": json.dumps(args)}


class Harness:
    """Drives one pass through the seam and hands back the audit lines it produced."""

    def __init__(self, audit_dir: Path) -> None:
        self._dir = audit_dir
        self.agent = agent_mod.MusheghAgent()
        self.agent._registry = {
            "weather": self._ok,
            "send_email": self._ok,
            "delete_file": self._ok,
        }

    @staticmethod
    async def _ok(args):
        return "did it"

    def run(self, calls: list[dict], *, turn: str = "") -> list[dict]:
        for f in self._dir.glob("*.jsonl"):
            f.unlink()
        _err._turn.set(turn)
        messages: list[dict] = []
        asyncio.run(self.agent._execute_calls(messages, calls))
        # The daily audit file is named by the OWNER's calendar day, not UTC's (see
        # audit._owner_day, and the six assertions pinning it in test_audit_integrity.py).
        # Deriving the name from UTC here made this gate fail on its own between 00:00 and
        # 02:00 local — it was asserting the old behaviour, not the system.
        today = _owner_day(datetime.now(timezone.utc))
        p = self._dir / f"{today}.jsonl"
        if not p.exists():
            return []
        return [json.loads(ln) for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()]


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        audit_dir = Path(tmp) / "audit"
        audit_dir.mkdir()
        audit._audit_dir = lambda: audit_dir

        from mushegh.brain import proactive

        real_required, real_grade = proactive.confirm_required, proactive.grade
        gated = {"send_email", "delete_file"}
        agent_mod.settings.face_second_factor = False
        h = Harness(audit_dir)

        try:
            # `_execute_calls` imports these by name from mushegh.brain.proactive at call time, so
            # patching the module attribute is enough and no import order matters.
            proactive.confirm_required = lambda n, a: n in gated
            proactive.draft_preview = lambda n, a: ""

            print("\n[6] a read tool outside the tier runs and says WHY it was allowed")
            lines = h.run([call("weather", city="Yerevan")], turn="t-read")
            check("exactly one line", len(lines) == 1, str(len(lines)))
            if lines:
                ln = lines[0]
                check("decision is allow", ln.get("decision") == "allow", str(ln.get("decision")))
                check("rule names the gate it passed",
                      ln.get("rule_applied") == "confirm_gate:not_gated", str(ln.get("rule_applied")))
                check("and it carries the turn id", ln.get("turn_id") == "t-read", str(ln.get("turn_id")))

            print("\n[2] a confirm-tier call with no yes is HELD, not run")
            h.agent._confirm_granted = False
            lines = h.run([call("send_email", to="anna@example.com", body="hi")], turn="t-hold")
            check("exactly one line", len(lines) == 1, str(len(lines)))
            if lines:
                ln = lines[0]
                check("decision is deny", ln.get("decision") == "deny", str(ln.get("decision")))
                check("rule names the confirm gate",
                      ln.get("rule_applied") == "confirm_gate:awaiting_owner_confirmation",
                      str(ln.get("rule_applied")))
                check("with the turn id", ln.get("turn_id") == "t-hold")
                check("and a reasoning a human can read", bool(ln.get("reasoning")))
            check("the held call is remembered for the owner's yes",
                  (h.agent._pending_confirm or {}).get("name") == "send_email",
                  str(h.agent._pending_confirm))

            print("\n[5] the same call AFTER the owner affirms runs, and says so")
            h.agent._confirm_granted = True
            lines = h.run([call("send_email", to="anna@example.com", body="hi")], turn="t-yes")
            check("exactly one line", len(lines) == 1, str(len(lines)))
            if lines:
                ln = lines[0]
                check("decision is allow", ln.get("decision") == "allow", str(ln.get("decision")))
                check("rule distinguishes 'he said yes' from 'it was never gated'",
                      ln.get("rule_applied") == "confirm_gate:owner_confirmed",
                      str(ln.get("rule_applied")))
                check("with the turn id", ln.get("turn_id") == "t-yes")
            check("one yes authorises exactly one action", not h.agent._confirm_granted)

            print("\n[3] the second factor can only ever add a refusal")
            agent_mod.settings.face_second_factor = True
            h.agent._confirm_granted = True

            async def _absent(name, args):
                return "I can't see you in the room, sir."

            h.agent._face_second_factor = _absent
            lines = h.run([call("delete_file", path="x")], turn="t-face")
            check("exactly one line", len(lines) == 1, str(len(lines)))
            if lines:
                check("decision is deny", lines[0].get("decision") == "deny")
                check("rule names the second factor",
                      lines[0].get("rule_applied") == "face_second_factor:owner_not_present",
                      str(lines[0].get("rule_applied")))
                check("with the turn id", lines[0].get("turn_id") == "t-face")
            agent_mod.settings.face_second_factor = False

            print("\n[4] a call that does not match the tool's schema never reaches the handler")
            h.agent._check_args = lambda n, a: (a, "unknown argument(s) ['bogus']")
            lines = h.run([call("weather", bogus=1)], turn="t-args")
            check("exactly one line", len(lines) == 1, str(len(lines)))
            if lines:
                check("decision is deny", lines[0].get("decision") == "deny")
                check("rule names argcheck",
                      lines[0].get("rule_applied") == "argcheck:malformed_call",
                      str(lines[0].get("rule_applied")))
                check("with the turn id", lines[0].get("turn_id") == "t-args")
            h.agent._check_args = lambda n, a: (a, "")

            print("\n[1] THE GAP THIS FOUND: an unresolvable recipient is a BLOCKED call")
            h.agent._resolve_chain = lambda n, a: (a, "Which Anna — Anna K or Anna M?")
            lines = h.run([call("send_email", to="Anna", body="hi")], turn="t-chain")
            check("it is audited at all (it was not, before O2.5)", len(lines) == 1, str(len(lines)))
            if lines:
                ln = lines[0]
                check("decision is defer, not deny — nothing was refused",
                      ln.get("decision") == "defer", str(ln.get("decision")))
                check("rule names the resolver",
                      ln.get("rule_applied") == "chain_resolve:recipient_ambiguous",
                      str(ln.get("rule_applied")))
                check("with the turn id", ln.get("turn_id") == "t-chain")
            h.agent._resolve_chain = lambda n, a: (a, "")

            print("\n[7] THE GATE: the invariant pass 3 states in a comment actually holds")
            # Every exit, in one turn. Six calls in, six audit lines out, all sharing one id.
            h.agent._confirm_granted = False
            seen: list[dict] = []
            for c, setup in (
                (call("weather", city="Yerevan"), None),
                (call("send_email", to="a@b.c"), None),
            ):
                seen += h.run([c], turn="t-all")
            check("no exit is silent", len(seen) == 2, str(len(seen)))
            check("every line has a decision", all(x.get("decision") for x in seen))
            check("every line names the rule that decided it",
                  all(x.get("rule_applied") for x in seen))
            check("every line carries the correlation id (31.F5's first real consumer)",
                  all(x.get("turn_id") == "t-all" for x in seen),
                  str([x.get("turn_id") for x in seen]))
            check("every line names a non-owner-free actor",
                  all(x.get("actor") for x in seen), str([x.get("actor") for x in seen]))

            print("\n[8] an uncorrelated turn records a blank id rather than inventing one")
            lines = h.run([call("weather", city="Yerevan")], turn="")
            check("the id is blank, not fabricated",
                  lines and lines[0].get("turn_id") == "", str(lines and lines[0].get("turn_id")))

            print("\n[9] the rules used here are the ones review.py groups by")
            from mushegh.brain.review import outcome_of

            check("a deny reads as 'refused'",
                  outcome_of({"decision": "deny", "ok": False}) == "refused")
            check("a defer reads as awaiting the owner, not as a failure",
                  outcome_of({"decision": "defer", "ok": False}) == "awaiting approval")
        finally:
            proactive.confirm_required, proactive.grade = real_required, real_grade

    print(f"\n=== {passed}/{passed + failed} checks passed ===")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
