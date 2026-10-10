"""45.R10 — the audit trail is verifiable, and says what that does and does not prove.

Until 2026-10-04 `audit.py`'s first line called the trail "tamper-evident" and nothing checked
anything. D-25 and D-43 both warn about that: a claim of a property nothing verifies teaches the
reader to trust a guarantee nobody is making. So this is the first half of the task's either/or —
the JSONL carries an integrity check a reader can run **without the framework**.

What is asserted:

  * **a clean file verifies**, and every line is `chained` — the property the claim rests on
  * **an edited line is found**, and the report says it was edited rather than merely failing
  * **a removed line is found** (the `prev` of the line after it no longer matches)
  * **a reordered pair is found** — reordering is not editing and is still a change to history
  * **a spliced line (a whole foreign line inserted) is found**
  * **a rewritten digest is found** — recomputing the hash to hide an edit does not work, because
    the next line's `prev` no longer matches
  * **the reader needs no framework**: the verifier is pure text-in/data-out and runs as a module
  * **legacy lines are not failures**: a file written before the chain existed verifies as
    unchained, and pretending otherwise would train the reader to ignore a non-zero exit
  * **the limits are asserted, not just described**: truncation of the last line is NOT detected, and
    a wholesale rewrite with recomputed digests is NOT detected. Both are stated in the task and
    here, because the whole point of 45.R10 is that a claim nobody checks is worse than no claim —
    the same applies to its failure modes.
  * **the write path keeps its contract**: `record()` still never raises, and a chain failure loses
    the chain rather than the line

Hermetic: a temp audit dir, synthetic lines, no settings, no model, no network.

    uv run python bench/test_audit_integrity.py
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

_TMP = tempfile.mkdtemp(prefix="afon-audit-")
os.environ["AFON_AUDIT_LOG_DIR"] = str(Path(_TMP) / "audit")

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(ROOT / "src"))

passed = failed = 0


def check(name: str, ok: bool, detail: str = "") -> None:
    global passed, failed
    if ok:
        passed += 1
        print(f"  [PASS] {name}")
    else:
        failed += 1
        print(f"  [FAIL] {name}  {detail}")


def make_file(lines: list[dict], name: str = "2026-10-04.jsonl") -> Path:
    """Write a chained file the way `record()` does, so the fixture cannot drift from reality."""
    from afon.brain.audit_verify import GENESIS, _HASH_FIELD, _PREV_FIELD, line_hash

    prev = GENESIS
    out = []
    for obj in lines:
        obj = dict(obj)
        obj[_PREV_FIELD] = prev
        obj[_HASH_FIELD] = line_hash(obj, prev)
        prev = obj[_HASH_FIELD]
        out.append(json.dumps(obj, ensure_ascii=False))
    p = Path(_TMP) / name
    p.write_text("\n".join(out) + "\n", encoding="utf-8")
    return p


SAMPLE = [{"tool": "remember", "args": {"text": "the garage remote is in the drawer"}, "ok": True},
          {"tool": "look_around", "args": {"prompt": "describe"}, "result": "a kitchen", "ok": True},
          {"tool": "forget", "args": {"q": "rabbit farm"}, "ok": True}]


def main() -> int:
    from afon.brain.audit_verify import (BROKEN, CHAINED, GAP, GENESIS, LEGACY, canonical, line_hash, verify_text)

    print("\n[1] a clean file verifies")
    p = make_file(SAMPLE)
    rep = verify_text(p.read_text(encoding="utf-8"))
    check("every line is chained", rep["counts"][CHAINED] == len(SAMPLE), str(rep["counts"]))
    check("nothing is broken", rep["ok"] and not rep["problems"], str(rep["problems"]))
    check("the count of lines is the count written", rep["lines"] == 3, str(rep["lines"]))
    check("the first line chains onto the genesis value",
          json.loads(p.read_text(encoding="utf-8").splitlines()[0])["prev"] == GENESIS)

    print("\n[2] an edited line is found, and says so")
    lines = p.read_text(encoding="utf-8").splitlines()
    obj = json.loads(lines[1])
    obj["result"] = "the owner's face"                     # the edit nobody should be able to hide
    edited = [lines[0], json.dumps(obj, ensure_ascii=False), lines[2]]
    rep = verify_text("\n".join(edited))
    check("the edit is detected", not rep["ok"], str(rep["counts"]))
    check("...on the right line", rep["problems"][0]["line"] == 2, str(rep["problems"]))
    check("...and the reason names the edit, not just a failure",
          "edited" in rep["problems"][0]["why"], rep["problems"][0]["why"])

    print("\n[3] a removed line is found")
    removed = [lines[0], lines[2]]
    rep = verify_text("\n".join(removed))
    check("the removal is detected", not rep["ok"], str(rep["counts"]))
    check("...and the reason says the chain no longer links",
          "removed" in rep["problems"][0]["why"] or "reordered" in rep["problems"][0]["why"],
          rep["problems"][0]["why"])

    print("\n[4] a reordered pair is found — reordering is not editing and is still a change")
    swapped = [lines[0], lines[2], lines[1]]
    rep = verify_text("\n".join(swapped))
    check("the reorder is detected", not rep["ok"], str(rep["counts"]))

    print("\n[5] a spliced-in foreign line is found, as a GAP")
    spliced = [lines[0], json.dumps({"tool": "delete_everything", "ok": True}), lines[1], lines[2]]
    rep = verify_text("\n".join(spliced))
    check("the spliced line is detected", not rep["ok"], str(rep["counts"]))
    check("...at the line that was added", rep["problems"][0]["line"] == 2, str(rep["problems"]))
    check("...and it is a GAP, not 'tampering'",
          rep["problems"][0]["state"] == GAP, str(rep["problems"][0]))
    check("...and the reason admits the two causes cannot be told apart",
          "could not be chained" in rep["problems"][0]["why"]
          and "one that was inserted" in rep["problems"][0]["why"],
          rep["problems"][0]["why"])
    check("a legacy line is still fine at the START of a file, which is the rule that closes it",
          verify_text("\n".join([json.dumps(SAMPLE[0])] + lines))["counts"][LEGACY] == 1)

    print("\n[6] recomputing the digest to hide the edit does not work")
    # The strongest a tamperer can do without the next line: re-hash the line they changed.
    forged = json.loads(lines[1])
    forged["result"] = "the owner's face"
    forged = {k: v for k, v in forged.items()}
    rehashed = dict(forged)
    rehashed["hash"] = line_hash(rehashed, forged["prev"])
    rep = verify_text("\n".join([lines[0], json.dumps(rehashed, ensure_ascii=False), lines[2]]))
    check("re-hashing the edited line is still caught, because line 3's prev no longer matches",
          not rep["ok"] and rep["problems"][0]["line"] == 3, str(rep["problems"]))

    print("\n[7] the reader needs no framework")
    proc = subprocess.run(
        [sys.executable, "-m", "afon.brain.audit_verify", "--verify", str(p)],
        cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8", errors="replace",
        env={**os.environ, "PYTHONPATH": str(ROOT / "src")}, timeout=120)
    check("the CLI runs and reports VERIFIED", proc.returncode == 0 and "VERIFIED" in proc.stdout,
          f"exit={proc.returncode} {proc.stdout[-160:]}{proc.stderr[-160:]}")
    check("...and it says how many lines are chained", "3 chained" in proc.stdout, proc.stdout[-200:])
    bad = Path(_TMP) / "bad.jsonl"
    bad.write_text("\n".join(edited) + "\n", encoding="utf-8")
    proc2 = subprocess.run(
        [sys.executable, "-m", "afon.brain.audit_verify", "--verify", str(bad)],
        cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8", errors="replace",
        env={**os.environ, "PYTHONPATH": str(ROOT / "src")}, timeout=120)
    check("a tampered file exits NON-ZERO", proc2.returncode == 1, f"exit={proc2.returncode}")
    check("...and says NOT VERIFIED in words", "NOT VERIFIED" in proc2.stdout, proc2.stdout[-200:])
    # "VERIFIED" is a substring of "NOT VERIFIED", so checking for the word proves nothing. Assert
    # the verdict LINE instead, which is what a human or a script actually reads.
    check("...and the verdict line tells the reader not to rely on it",
          proc2.stdout.strip().splitlines()[-1] == "NOT VERIFIED — do not rely on this file",
          proc2.stdout.strip().splitlines()[-1])
    check("...while a clean file's verdict line is exactly VERIFIED",
          proc.stdout.strip().splitlines()[-1] == "VERIFIED",
          proc.stdout.strip().splitlines()[-1])
    src = (ROOT / "src" / "afon" / "brain" / "audit_verify.py").read_text(encoding="utf-8")
    check("the verifier imports nothing from afon (it must not trust the writer)",
          "from afon" not in src and "import afon" not in src)

    print("\n[8] legacy lines are the past, not tampering")
    legacy = Path(_TMP) / "legacy.jsonl"
    legacy.write_text("\n".join(json.dumps(o) for o in SAMPLE) + "\n", encoding="utf-8")
    rep = verify_text(legacy.read_text(encoding="utf-8"))
    check("unchained lines verify as legacy", rep["ok"] and rep["counts"][LEGACY] == 3, str(rep["counts"]))
    proc3 = subprocess.run(
        [sys.executable, "-m", "afon.brain.audit_verify", "--verify", str(legacy)],
        cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8", errors="replace",
        env={**os.environ, "PYTHONPATH": str(ROOT / "src")}, timeout=120)
    check("and a legacy file still exits zero", proc3.returncode == 0, f"exit={proc3.returncode}")
    check("...while saying they are unchained", "legacy" in proc3.stdout, proc3.stdout[-200:])
    check("a legacy line followed by a chain is not reported as tampering",
          verify_text(legacy.read_text(encoding="utf-8") + "\n"
                      + make_file(SAMPLE, "chain.jsonl").read_text(encoding="utf-8"))["ok"])

    print("\n[9] malformed input is reported, not raised")
    for bad_text, why in (("{not json", "not valid JSON"),
                          ('["a list"]', "not an object")):
        rep = verify_text(bad_text)
        check(f"{why} is a broken line, not a crash",
              not rep["ok"] and rep["problems"] and rep["problems"][0]["state"] == BROKEN,
              str(rep["problems"]))
    check("an empty file verifies (nothing to be wrong about)", verify_text("")["ok"])
    check("blank lines are skipped, not counted as broken", verify_text("\n\n")["ok"])

    print("\n[10] the limits are asserted, not just written down")
    truncated = "\n".join(lines[:-1]) + "\n"
    rep = verify_text(truncated)
    check("LIMIT, and it is real: truncating the LAST line is NOT detected", rep["ok"],
          "if this ever becomes detectable, the claim in the docstring is wrong and must be updated")
    # Rebuilding every digest by hand is what a writer with file access can do. Asserted so the
    # module cannot quietly imply it is protected.
    prev = GENESIS
    rebuilt = []
    for o in SAMPLE:
        o = dict(o)
        o["prev"] = prev
        o["hash"] = line_hash(o, prev)
        prev = o["hash"]
        rebuilt.append(json.dumps(o, ensure_ascii=False))
    check("LIMIT, and it is real: a wholesale rewrite with recomputed digests IS NOT detected",
          verify_text("\n".join(rebuilt))["ok"])
    for phrase in ("truncation of the LAST line", "rebuild a perfectly valid chain"):
        check(f"the docstring states the limit: {phrase!r}", phrase in src)

    print("\n[11] the digest does not depend on the formatter")
    line = {"b": 2, "a": 1, "hash": "deadbeef", "ts": "2026-10-04T10:00:00"}
    shuffled = {"ts": "2026-10-04T10:00:00", "hash": "deadbeef", "a": 1, "b": 2}
    check("key order does not change the digest", line_hash(line, GENESIS) == line_hash(shuffled, GENESIS))
    check("...and the hash field itself is excluded (it cannot contain itself)",
          line_hash(line, GENESIS) == line_hash({k: v for k, v in line.items() if k != "hash"}, GENESIS))
    check("...but any content change does change it",
          line_hash(line, GENESIS) != line_hash({**line, "a": 99}, GENESIS))
    check("canonical() is compact, sorted and non-ASCII-preserving",
          canonical({"b": 1, "a": "я"}) == '{"a":"я","b":1}', canonical({"b": 1, "a": "я"}))
    check("non-Latin text survives into the digest input, not escaped",
          "я" in canonical({"a": "я"}))

    print("\n[12] the write path still honours 'auditing never breaks a turn'")
    from afon.brain import audit
    d = Path(_TMP) / "live"
    d.mkdir(exist_ok=True)
    saved_audit_dir = audit._audit_dir
    try:
        audit._audit_dir = lambda: d
        for i in range(3):
            audit.record("remember", {"text": f"fact {i}"}, "Noted, sir.", ok=True)
        out = (d / f"{__import__('datetime').date.today():%Y-%m-%d}.jsonl")
        check("three lines were written", len(out.read_text(encoding="utf-8").strip().splitlines()) == 3)
        # The daily file is named by the OWNER's calendar day, not UTC's. Between 00:00 and 02:00
        # in Europe/Berlin those disagree, and the whole of that window's activity used to land in
        # yesterday's file — found on 2026-10-10 when this line failed at 00:47 local, after
        # surviving every earlier run because it can only fail for two hours a night.
        from afon.brain.audit import _owner_day
        import datetime as _dt
        from zoneinfo import ZoneInfo
        from afon.config import settings as _s

        def _day_at(hour: int, minute: int, tz: str) -> str:
            local = _dt.datetime(2026, 10, 10, hour, minute, tzinfo=ZoneInfo(tz))
            return _owner_day(local.astimezone(_dt.timezone.utc))

        berlin_midnight = _day_at(0, 30, "Europe/Berlin")
        check("00:30 in Berlin is filed on the owner's day, not yesterday's",
              berlin_midnight == "2026-10-10", berlin_midnight)
        check("01:59 — the last minute before UTC catches up — is also the owner's day",
              _day_at(1, 59, "Europe/Berlin") == "2026-10-10", _day_at(1, 59, "Europe/Berlin"))
        check("midday is unaffected", _day_at(12, 0, "Europe/Berlin") == "2026-10-10")
        check("late evening is unaffected", _day_at(23, 30, "Europe/Berlin") == "2026-10-10")
        # An instant that is the 10th in New York is the 11th in Berlin, and it is filed on the
        # OWNER's day — which is the rule. (It would only be wrong if the file followed the
        # instant's own local zone, which is what the UTC bug did in reverse.)
        ny_evening = _day_at(20, 30, "America/New_York")
        check("an instant filed on the owner's day, not the origin zone's (NY 20:30 is Berlin's 11th)",
              ny_evening == "2026-10-11", ny_evening)
        check("the configured owner timezone is the one used",
              (_s.user_tz or "UTC") == "Europe/Berlin")
        check("...and the file verifies end to end", verify_text(out.read_text(encoding="utf-8"))["ok"],
              str(verify_text(out.read_text(encoding="utf-8"))["problems"]))
        # A chain failure must cost the CHAIN, never the line.
        import afon.brain.audit_verify as av
        real = av.line_hash
        av.line_hash = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom"))
        try:
            audit.record("remember", {"text": "still written"}, "ok", ok=True)
        finally:
            av.line_hash = real
        after = out.read_text(encoding="utf-8").strip().splitlines()
        check("a broken chain still writes the line", len(after) == 4, f"{len(after)} lines")
        rep2 = verify_text(out.read_text(encoding="utf-8"))
        check("...and the trail reports a GAP rather than pretending the line is chained",
              rep2["counts"][GAP] == 1 and rep2["counts"][BROKEN] == 0, str(rep2["counts"]))
        check("...which fails verification, so a chain failure can never pass unnoticed",
              rep2["ok"] is False)
    finally:
        audit._audit_dir = saved_audit_dir

    print(f"\n{'=' * 60}")
    print(f"  {passed} passed, {failed} failed")
    print("=" * 60)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
