"""37.R5 — the never-store set is enforced at the write boundary (D-24).

Charter: *plaintext passwords · raw biometric sensor feeds · banking credentials · unfiltered
health-crisis journaling. These are not retention questions; they never enter a store.*

Until now that sentence existed in `docs/DECISIONS.md` and nowhere in `src/mushegh/` — a grep for
`D-24`, `never_store` and `NEVER_STORE` across the package returned nothing. So the four categories
were prose, and the one thing a prose rule cannot do is refuse anything.

What is asserted here, and why each one is not obvious:

  * **each of the four is refused where the write is attempted**, and nothing lands on disk — not
    in the learned store, not in the journal. A refusal is a RAISE, not a `None`: `remember()`
    already returned `None` for empty text, and a caller that cannot tell a refusal from an empty
    string will believe a refused password was stored.
  * **the audit trail does not become the back door.** This is the half that is easy to miss and
    that made the first half cosmetic. `agent.py` records every dispatched tool call's arguments
    verbatim, and redaction is key-based — so `remember({"text": "my password is ..."})` was
    refused by the store and then written to the trail one layer below the refusal. Both doors are
    now closed, and the trail line is marked `refuse` rather than `allow`.
  * **ordinary facts still store.** A guard that refuses everything passes every refusal assertion
    in this file, which is why the benign battery is here and is roughly as large as the hostile
    one. "I forgot my password again" and "the passcode is that we rotate monthly" must survive.
  * **there is no override**, structurally: no `allow=`, no `force=`, no severity level, on either
    `screen()` or `MemoryStore.remember`. Any override is a bypass with extra steps, and the first
    caller to reach for one would be a bug report rather than a feature.
  * **the refusal is auditable without being a copy.** The fingerprint is an HMAC under a random
    per-process key, so the trail can prove the guard fired without being a place the refused text
    can be recovered from — a bare sha256 of a short password is reversible by dictionary attack,
    which would reintroduce the leak one layer down.
  * **the exception carries no payload** — not in the message, not in `args`, not in `repr`. The
    audit layer renders `str(result)` and loggers render `repr`, so an exception that quoted the
    text would defeat the whole mechanism.
  * **the detector is a floor, and this file says so out loud.** The last group asserts that an
    unlabelled, unformatted secret is NOT caught. That is a real limitation, stated as a test so it
    cannot quietly become a claim of completeness — the ceiling is `declared=`, where a caller that
    knows what it holds names the class itself.

Hermetic: a temp state root and a temp audit dir set before import, no network, no model, no vault.

    uv run python bench/test_never_store.py
"""

from __future__ import annotations

import ast
import inspect
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Set BEFORE mushegh is imported: `settings` is a module-level singleton built at import time, so an
# env var set afterwards is ignored. Both roots point at the temp dir, so this gate cannot write to
# `~/.mushegh` or to the owner's vault even if a line of it goes wrong.
_TMP = tempfile.mkdtemp(prefix="mushegh-never-store-")
os.environ["MUSHEGH_STATE_DIR"] = str(Path(_TMP) / "state")
os.environ["MUSHEGH_AUDIT_LOG_DIR"] = str(Path(_TMP) / "audit")

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(ROOT / "src"))

passed = failed = 0

#: The charter's four, in its order. A fifth or a missing one is a change to D-24, not to a test.
#: The four charter classes, which a pattern can find in prose. `financial_position` was added
#: 2026-10-06 under D-83 and is deliberately NOT here: it has no detector, because "EUR 2,400"
#: is a balance, a salary or the price of a bicycle and prose cannot tell those apart. It is
#: declaration-only, asserted separately below and in bench/test_executor_contract.py.
THE_SET = ("plaintext_password", "raw_biometric_feed", "banking_credential", "unfiltered_health_crisis")

#: One hostile sample per class. The biometric one is a real-length vector because a 3-number
#: "embedding" is not what D-24 means and a guard that fired on it would be the false positive.
HOSTILE = {
    "plaintext_password": "the wifi password is 192.168.1.40",
    "raw_biometric_feed": "the voiceprint embedding is " + ", ".join(["0.31", "-0.12", "0.77"] * 12),
    "banking_credential": "the card on file is 4539 1488 0343 6467",
    "unfiltered_health_crisis": "he said he wanted to kill himself last night",
}

#: The benign battery. Each of these is a sentence a real owner actually says, and each contains a
#: word from the set. They are the precision half of the rule.
BENIGN = [
    "I forgot my password again, sir — the one for the router",
    "the passcode is that we rotate monthly, at the start of the quarter",
    "he pinpoints the exact figure on the card, which is how I knew it was wrong",
    "I want to die of embarrassment when the bill arrives",
    "his voice was low today, which is not like him",
    "the voiceprint file is in the faces folder, not the memory folder",
    "he runs at the gym on Mondays and Thursdays",
    "the garage remote is in the kitchen drawer",
    "his pulse-ox reading was 98 this morning, which is normal for him",
    "IBAN is on the invoice, not in my head — check the paperwork",
]


def check(name: str, ok: bool, detail: str = "") -> None:
    global passed, failed
    if ok:
        passed += 1
        print(f"  [PASS] {name}")
    else:
        failed += 1
        print(f"  [FAIL] {name}  {detail}")


def main() -> int:
    from mushegh.brain import audit, never_store
    from mushegh.brain.memory import MemoryStore
    from mushegh.brain.never_store import NeverStoreRefused, screen
    from mushegh.brain.tools.base import ErrorKind, classify_error
    from mushegh.shared.paths import audit_dir

    print("\n--- the set itself ---")
    check("the four D-24 classes exist, in the charter's order",
          never_store.DETECTABLE == THE_SET, f"got {never_store.DETECTABLE}")
    check("the charter's four are still the detectable set, and nothing crept in",
          set(never_store.NEVER_STORE) - set(THE_SET) == {never_store.FINANCIAL_POSITION},
          f"got {never_store.NEVER_STORE}")
    check("D-83's finance class is declaration-only — no pattern can fire on it",
          never_store.FINANCIAL_POSITION not in never_store.DETECTABLE
          and not never_store.screen("the portfolio is worth 41,280").refused,
          "a detector here would refuse to remember what the coffee machine cost")
    check("...and declaring it refuses the write",
          never_store.screen("balance 41,280",
                             declared=never_store.FINANCIAL_POSITION).refused)
    check("every class has a spoken refusal for the owner",
          all(c in never_store.SPOKEN for c in never_store.NEVER_STORE))
    check("every class has a reason for the log",
          all(c in never_store.REASONS for c in never_store.NEVER_STORE))

    print("\n--- refused at the write boundary ---")
    with tempfile.TemporaryDirectory(prefix="mushegh-ns-store-") as td:
        store = MemoryStore(base_dir=td)
        for cls, payload in HOSTILE.items():
            try:
                store.remember(payload)
                check(f"remember() refuses {cls}", False, "it returned — the write was attempted")
            except NeverStoreRefused as refused:
                check(f"remember() refuses {cls}", refused.cls == cls,
                      f"refused as {refused.cls!r}")
            except Exception as e:  # noqa: BLE001
                check(f"remember() refuses {cls}", False, f"raised {type(e).__name__}: {e}")
        check("nothing reached the learned store", store.count() == 0,
              f"{store.count()} note(s) on disk")

        for cls, payload in HOSTILE.items():
            try:
                store.journal_append(payload)
                check(f"journal_append() refuses {cls}", False, "it returned")
            except NeverStoreRefused as refused:
                check(f"journal_append() refuses {cls}", refused.cls == cls,
                      f"refused as {refused.cls!r}")
            except Exception as e:  # noqa: BLE001
                check(f"journal_append() refuses {cls}", False, f"raised {type(e).__name__}: {e}")
        check("no journal day was created", store.journal_days() == [], f"{store.journal_days()}")

        print("\n--- a refusal is not an empty string ---")
        check("an empty fact still returns None, not a refusal",
              store.remember("   ") is None)
        try:
            store.remember("")
            check("a refused write raises rather than returning None", True)
        except NeverStoreRefused:
            check("a refused write raises rather than returning None", True)
        except Exception as e:  # noqa: BLE001
            check("a refused write raises rather than returning None", False, type(e).__name__)

    print("\n--- ordinary facts are unaffected (the precision half) ---")
    with tempfile.TemporaryDirectory(prefix="mushegh-ns-benign-") as td:
        store = MemoryStore(base_dir=td)
        stored = 0
        for text in BENIGN:
            try:
                if store.remember(text) is not None:
                    stored += 1
                else:
                    check(f"stores: {text[:44]}", False, "returned None")
            except NeverStoreRefused as refused:
                check(f"stores: {text[:44]}", False, f"refused as {refused.cls}")
        check(f"all {len(BENIGN)} ordinary facts stored", stored == len(BENIGN), f"{stored} stored")

    print("\n--- the audit trail does not become the back door ---")
    secret = "the wifi password is 192.168.1.40"
    audit.record("remember", {"text": secret, "tags": ["note"]}, "Noted, sir.", ok=True)
    audit.record("remember", {"text": "he works Tuesdays"}, "Noted, sir.", ok=True)
    audit.record("stash", {"creds": {"note": secret}}, "saved", ok=True)
    audit.record("look_around", {"prompt": "describe"}, f"seen: {secret}", ok=True)

    d = audit_dir()
    lines = [json.loads(ln) for f in sorted(d.glob("*.jsonl"))
             for ln in f.read_text(encoding="utf-8").splitlines() if ln.strip()]
    raw = "".join(f.read_text(encoding="utf-8") for f in sorted(d.glob("*.jsonl")))
    mine = [ln for ln in lines if ln.get("tool") in ("remember", "stash", "look_around")]

    check("the trail recorded the calls", len(mine) >= 4, f"{len(mine)} line(s)")
    refused_lines = [ln for ln in mine if ln.get("decision") == "refuse"]
    check("a refused payload is marked decision=refuse", len(refused_lines) >= 3,
          f"{len(refused_lines)} of {len(mine)}")
    check("a refused call is not recorded as ok=true",
          all(ln.get("ok") is False for ln in refused_lines))
    check("the rule names the class",
          any("never_store:plaintext_password" in (ln.get("rule_applied") or "") for ln in refused_lines),
          str([ln.get("rule_applied") for ln in refused_lines]))
    check("a nested payload is caught as well as a top-level one",
          sum(1 for ln in refused_lines if "creds" in json.dumps(ln.get("args"))) == 1,
          "the nested args line was not refused")
    check("THE SECRET IS NOWHERE IN THE TRAIL", secret not in raw and "192.168.1.40" not in raw,
          "the payload reached the audit log")
    check("a benign call is still recorded with its arguments",
          any((ln.get("args") or {}).get("text") == "he works Tuesdays" for ln in mine))
    check("the withheld marker carries the class and a fingerprint",
          any("withheld" in json.dumps(ln.get("args")) and "fingerprint" in json.dumps(ln.get("args"))
              for ln in refused_lines))

    print("\n--- there is no override ---")
    sig = inspect.signature(screen)
    banned = {"allow", "force", "override", "unsafe", "skip", "ignore", "permit", "bypass"}
    check("screen() has no bypass parameter",
          not (set(sig.parameters) & banned), f"has {sorted(set(sig.parameters) & banned)}")
    rparams = set(inspect.signature(MemoryStore.remember).parameters)
    check("MemoryStore.remember has no bypass parameter",
          not (rparams & banned), f"has {sorted(rparams & banned)}")
    jparams = set(inspect.signature(MemoryStore.journal_append).parameters)
    check("MemoryStore.journal_append has no bypass parameter",
          not (jparams & banned), f"has {sorted(jparams & banned)}")
    try:
        store.remember("anything at all", force=True)  # type: ignore[call-arg]
        check("passing a bypass keyword is a TypeError", False, "it was accepted")
    except TypeError:
        check("passing a bypass keyword is a TypeError", True)
    except Exception as e:  # noqa: BLE001
        check("passing a bypass keyword is a TypeError", False, f"{type(e).__name__}: {e}")
    try:
        screen("harmless", declared="ordinary")
        check("an unknown declared class is rejected, not ignored", False, "it was accepted")
    except ValueError:
        check("an unknown declared class is rejected, not ignored", True)

    print("\n--- declared raises the ceiling ---")
    v = screen("swordfish", declared="plaintext_password")
    check("a declared class refuses text no pattern would match", v.refused == "plaintext_password",
          f"got {v.refused!r}")
    check("declaring a class the text does not trip still refuses (declaration is enough)", v.ok is False)

    print("\n--- the fingerprint identifies without revealing ---")
    a, b = screen("my password is hunter2"), screen("my password is hunter2")
    c = screen("my password is hunter3")
    check("the same text fingerprints identically", a.fingerprint == b.fingerprint)
    check("a different text fingerprints differently", a.fingerprint != c.fingerprint)
    check("the fingerprint is 12 hex chars",
          len(a.fingerprint) == 12 and all(ch in "0123456789abcdef" for ch in a.fingerprint),
          a.fingerprint)
    marker = never_store.withheld(a)
    check("the marker contains no part of the secret", "hunter2" not in marker, marker)

    print("\n--- the exception carries no payload ---")
    raised = None
    with tempfile.TemporaryDirectory(prefix="mushegh-ns-exc-") as td:
        st = MemoryStore(base_dir=td)
        try:
            st.remember(HOSTILE["plaintext_password"])
        except NeverStoreRefused as e:
            raised = e
    check("the refusal was raised", raised is not None)
    if raised is not None:
        rendered = " ".join([str(raised), repr(raised), " ".join(map(str, raised.args))])
        check("no part of the secret in the message, repr or args",
              "192.168.1.40" not in rendered and "wifi password" not in rendered, rendered[:120])
        check("the exception still says which class and where",
              raised.cls == "plaintext_password" and "remember" in raised.where, str(raised)[:100])
        check("classify_error files it as REFUSED, not UNKNOWN",
              classify_error(raised) is ErrorKind.REFUSED)

    print("\n--- no path persists one ---")
    src = (ROOT / "src" / "mushegh" / "brain" / "memory.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    additive: set[str] = set()
    deleting: set[str] = set()
    nodes: dict[str, ast.FunctionDef] = {}
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for sub in ast.walk(node):
            if not isinstance(sub, ast.Call) or not isinstance(sub.func, ast.Attribute):
                continue
            if sub.func.attr in ("write_text", "writelines", "write"):
                additive.add(node.name)
            elif sub.func.attr == "unlink":
                deleting.add(node.name)
        nodes[node.name] = node

    # Deletion cannot persist a secret — it is the safe direction, and `forget` is the tool that
    # implements D-25's right to be forgotten. Listed so that a future ADDITIVE writer has to be
    # added here deliberately rather than appearing unnoticed beside the existing four.
    check("the deletion methods are forget/redact, which only remove",
          deleting <= {"forget", "forget_all", "redact_journal"}, f"unexpected: {sorted(deleting)}")

    expected_additive = {"remember", "journal_append", "redact_journal", "_tombstone",
                         "_rewrite_provenance"}
    check("the additive writers are the five this file knows about",
          additive == expected_additive, f"got {sorted(additive)}")

    for guarded in ("remember", "journal_append"):
        seg = ast.get_source_segment(src, nodes[guarded]) or ""
        check(f"{guarded}() screens its own content", "_never_store_screen" in seg, seg[:80])

    # `redact_journal` writes a file but cannot introduce anything: the value it writes is exactly
    # the lines it read, minus the ones that matched. Asserted on the source rather than trusted,
    # because "it only ever removes" is the kind of claim that quietly stops being true.
    redact = ast.get_source_segment(src, nodes["redact_journal"]) or ""
    check("redact_journal() writes back only what it read, minus matches",
          'day.write_text("".join(keep), encoding="utf-8")' in redact
          and "keep = [ln for ln in lines" in redact, redact[-200:])

    # The two metadata rewriters can only be handed a note that was ALREADY screened when it was
    # written, which is checkable as a claim about their signatures: neither takes free text. If
    # one ever grows a `text=` parameter, a payload could enter through the rewrite path and this
    # assertion is the thing that says so.
    for rewriter, allowed in (("_tombstone", {"self", "note", "by", "slot"}),
                              ("_rewrite_provenance", {"self", "note", "source", "confidence"})):
        params = set(inspect.signature(getattr(MemoryStore, rewriter)).parameters)
        check(f"{rewriter}() takes no free text, so it cannot introduce a payload",
              params == allowed, f"has {sorted(params)}")

    ns_tree = ast.parse((ROOT / "src" / "mushegh" / "brain" / "never_store.py").read_text(encoding="utf-8"))
    imports = {a.name for node in ast.walk(ns_tree) if isinstance(node, ast.Import)
               for a in node.names} | {node.module for node in ast.walk(ns_tree)
                                       if isinstance(node, ast.ImportFrom) and node.module}
    check("the guard module imports nothing from mushegh (it is pure)",
          not any(str(m).startswith("mushegh") for m in imports), f"imports {sorted(imports)}")

    print("\n--- the detector is a floor, and this file does not claim otherwise ---")
    check("an unlabelled, unformatted secret is NOT caught (a real, stated limitation)",
          screen("hunter2").ok, "the filter over-claims; D-24's ceiling is `declared=`")
    check("a credential in an unlabelled sentence is NOT caught either (same limitation)",
          screen("use hunter2 for the wifi").ok)
    check("which is exactly why the declared path exists and is tested above",
          screen("use hunter2 for the wifi", declared="plaintext_password").refused
          == "plaintext_password")

    print(f"\n{'=' * 60}")
    print(f"  {passed} passed, {failed} failed")
    print("=" * 60)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
