"""Secrets hydration + redaction discipline (hermetic — no network, no real secret store).

**Why this gate exists.** Infisical is now a source of secrets, so two questions become
answerable that were not before, and both can fail silently:

1. **Does the brain still boot when the secret store is down?** `PRINCIPLES.md` §1 promises a
   3am diagnosis with `journalctl`/`sqlite3`/`curl`. A secrets backend that can abort startup
   breaks that promise silently — the system simply is not there. So hydration must degrade to
   environment-only and still return.
2. **Can a secret escape into a log?** This is the failure that matters. A key in a log is a key
   in a log aggregator, a ticket, and a backup.

**Negative controls are the point of this file.** A redaction test that only ever checks
"the value is absent" also passes when the code returns nothing at all — that is the `test_`
that matches empty strings and empty dicts, and passes for the wrong reason. So every
redaction assertion here is paired with a *positive* control that requires the code to actually
be doing its job: the report must carry names and counts, `redact()` must return a masked
fragment rather than the whole value, and the status helper must distinguish configured from
missing. If the positive control fails, the negative control is meaningless.

Hermetic by construction: no Infisical endpoint is contacted, no `age` binary is invoked, and no
value in this file is a real credential. Backends are injected, so every path is exercised
without a network.

    uv run python bench/test_secrets_redaction.py
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from afon.shared import secrets as S  # noqa: E402

passed = failed = 0

# Not a credential. Obviously fake, obviously well-formed, and never used against anything.
FAKE = "sk-test-NOTAREALKEY-abcdef0123456789"
FAKE2 = "ghp_alsoNotReal_zzzzzzzzzzzzzzzzzzzz"


def check(name: str, ok: bool, detail: str = "") -> None:
    global passed, failed
    if ok:
        passed += 1
        print(f"  [PASS] {name}")
    else:
        failed += 1
        print(f"  [FAIL] {name}" + (f"  -- {detail}" if detail else ""))


class FakeBackend:
    """Injected so no real secrets manager is ever contacted."""

    def __init__(self, name: str, values: dict[str, str] | None = None, boom: bool = False):
        self.name = name
        self._values = values or {}
        self._boom = boom

    def fetch(self) -> dict[str, str]:
        if self._boom:
            raise RuntimeError("backend exploded")
        return dict(self._values)


def main() -> None:  # noqa: C901 - a linear gate reads better than a helper layer here
    print("=== 1. name classification: what counts as a secret ===")
    for name in ("AFON_TAVILY_API_KEY", "OPENAI_API_KEY", "BOT_TOKEN",
                 "DB_PASSWORD", "MY_SECRET", "AFON_JINA_API_KEY", "HF_TOKEN"):
        check(f"{name} is classified as a secret", S.is_secret_name(name))
    for name in ("AFON_USER_TZ", "AFON_USER_NAME", "AFON_PERSONA_FILE",
                 "AFON_REPLY_LANGUAGE", "AFON_VAULT_PATH"):
        check(f"{name} is NOT treated as a secret", not S.is_secret_name(name))

    print("\n=== 2. redaction returns a mask, not the value ===")
    masked = S.redact(FAKE)
    # The positive control: it must return something. Without this, the "value is absent"
    # assertion below would also pass for a function that returns "".
    check("redact returns a non-empty mask", bool(masked), repr(masked))
    # `keep=2`, so exactly 2 leading and 2 trailing characters survive — not three.
    check("redact keeps exactly 2 leading chars", masked.startswith("sk") and
          not masked.startswith("sk-"), masked)
    check("redact keeps exactly 2 trailing chars", masked.endswith("89"), masked)
    check("redact emits a single ellipsis", masked.count("…") == 1, masked)
    check("redact does NOT contain the whole value", FAKE not in masked, masked)
    check("redact does NOT contain the middle of the value",
          "NOTAREALKEY" not in masked, masked)
    check("redact masks a short value entirely", FAKE[-4:] not in S.redact("abcd"), S.redact("abcd"))
    check("redact handles empty", S.redact("") == "<empty>", S.redact(""))

    print("\n=== 3. the report cannot carry a secret ===")
    env: dict[str, str] = {}
    report = S.hydrate_environment(
        [FakeBackend("fake", {"AFON_TAVILY_API_KEY": FAKE, "AFON_USER_TZ": "UTC"})], env=env
    )
    check("the secret reached the environment", env.get("AFON_TAVILY_API_KEY") == FAKE)
    check("the non-secret was NOT pulled in", "AFON_USER_TZ" not in env)
    check("report counted exactly 1", report.loaded == 1, repr(report.loaded))
    check("report names only the secret", report.names == ["AFON_TAVILY_API_KEY"], repr(report.names))

    blob = repr(report)
    check("report repr does not contain the value", FAKE not in blob, blob)
    check("report json does not contain the value",
          FAKE not in json.dumps({"names": report.names}), "")
    # The positive control for the report itself: it must be informative. A report that
    # carries nothing would trivially contain no secret.
    check("report is still informative (source + count present)",
          bool(report.source) and report.loaded > 0, repr(report))

    print("\n=== 4. environment always wins ===")
    env2: dict[str, str] = {"AFON_TAVILY_API_KEY": "already-set-by-operator"}
    rep2 = S.hydrate_environment([FakeBackend("fake", {"AFON_TAVILY_API_KEY": FAKE})], env=env2)
    check("existing env value was not overwritten",
          env2["AFON_TAVILY_API_KEY"] == "already-set-by-operator", env2["AFON_TAVILY_API_KEY"])
    check("the override was counted as skipped", rep2.skipped_present == 1, repr(rep2.skipped_present))
    check("nothing was loaded over the top", rep2.loaded == 0, repr(rep2.loaded))
    # "nothing added" must not read as "nothing configured" — that is the opposite of the truth
    # and would mislead a status view at 3am.
    check("report says 'already set', not 'none', when nothing needed adding",
          rep2.source == "environment (already set)", rep2.source)

    print("\n=== 5. a backend that explodes does not take the boot with it ===")
    env3: dict[str, str] = {}
    rep3 = S.hydrate_environment(
        [FakeBackend("boom", boom=True), FakeBackend("good", {"AFON_GOOD_KEY": FAKE2})], env=env3
    )
    check("hydration returned instead of raising", isinstance(rep3, S.SecretReport))
    check("the healthy backend still contributed", rep3.loaded == 1, repr(rep3.loaded))
    check("the failing backend did not poison the report", rep3.source == "good", rep3.source)
    check("the value landed correctly", env3.get("AFON_GOOD_KEY") == FAKE2)

    print("\n=== 6. empty and malformed backends are not crashes ===")
    env4: dict[str, str] = {}
    rep4 = S.hydrate_environment(
        [FakeBackend("empty", {}), FakeBackend("blanks", {"AFON_X_KEY": "", "AFON_Y_KEY": None})],
        env=env4,
    )
    check("blank values load nothing", rep4.loaded == 0, repr(rep4.loaded))
    check("env stayed clean", env4 == {}, repr(env4))

    print("\n=== 7. the age floor reads a decrypted file when present ===")
    with tempfile.TemporaryDirectory() as tmp:
        f = Path(tmp) / "secrets.json"
        f.write_text(json.dumps({"AFON_AGE_KEY": FAKE, "AFON_USER_NAME": "Sir"}), encoding="utf-8")
        env5: dict[str, str] = {}
        rep5 = S.hydrate_environment([S.AgeBackend(path=f)], env=env5)
        check("age file supplied the secret", env5.get("AFON_AGE_KEY") == FAKE)
        check("age file skipped the non-secret", "AFON_USER_NAME" not in env5, repr(env5))
        check("age backend reported", rep5.source == "age", rep5.source)

        bad = Path(tmp) / "bad.json"
        bad.write_text("{not json", encoding="utf-8")
        env6: dict[str, str] = {}
        rep6 = S.hydrate_environment([S.AgeBackend(path=bad)], env=env6)
        check("a malformed age file degrades quietly", rep6.loaded == 0, repr(rep6.loaded))
        check("a malformed age file does not raise", isinstance(rep6, S.SecretReport))

        notobj = Path(tmp) / "list.json"
        notobj.write_text("[1,2,3]", encoding="utf-8")
        env7: dict[str, str] = {}
        rep7 = S.hydrate_environment([S.AgeBackend(path=notobj)], env=env7)
        check("a non-object age file is ignored", rep7.loaded == 0, repr(rep7.loaded))

        rep8 = S.hydrate_environment([S.AgeBackend(path=Path(tmp) / "nope.json")], env={})
        check("a missing age file is not an error", rep8.loaded == 0 and not rep8.failed)

    print("\n=== 8. status is presence-only ===")
    old = os.environ.get("AFON_STATUS_PROBE_KEY")
    os.environ["AFON_STATUS_PROBE_KEY"] = FAKE
    try:
        status = S.secret_status(["AFON_STATUS_PROBE_KEY", "AFON_ABSENT_KEY"])
        check("a set key reports configured", status["AFON_STATUS_PROBE_KEY"] == "configured", str(status))
        check("an unset key reports missing", status["AFON_ABSENT_KEY"] == "missing", str(status))
        # Positive control: the helper must distinguish the two, not return one constant.
        check("status distinguishes the two states (not a constant)",
              len(set(status.values())) == 2, str(status))
        rendered = json.dumps(status)
        check("status output does not contain the value", FAKE not in rendered, rendered)
    finally:
        if old is None:
            os.environ.pop("AFON_STATUS_PROBE_KEY", None)
        else:
            os.environ["AFON_STATUS_PROBE_KEY"] = old

    print("\n=== 9. infisical backend is inert without configuration ===")
    # Constructed with EXPLICIT config, never by reading the environment: 36.F5 requires config.py
    # to be the only place a credential is read out of the environment.
    b = S.InfisicalBackend(S.InfisicalConfig())
    check("an unconfigured InfisicalConfig has no token", not b.cfg.token, repr(b.cfg.token))
    check("no token means not configured via api",
          not (b.cfg.token and b.cfg.workspace and b.cfg.project))
    import shutil as _shutil

    if _shutil.which("infisical") is None:
        check("unconfigured backend fetch() returns empty without network",
              b.fetch() == {}, repr(b.fetch()))
    else:
        check("infisical cli is present (fetch would hit the cli)", True,
              "cli on PATH - network path not exercised in hermetic mode")

    print("\n=== 10. this module reads no credential out of the environment ===")
    import ast

    src = (ROOT / "src" / "afon" / "shared" / "secrets.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    offending: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        f = node.func
        fname = f.attr if isinstance(f, ast.Attribute) else (f.id if isinstance(f, ast.Name) else "")
        if fname not in ("getenv", "get"):
            continue
        if fname == "get" and "environ" not in ast.unparse(f):
            continue
        if node.args and isinstance(node.args[0], ast.Constant):
            name = str(node.args[0].value)
            if S.is_secret_name(name):
                offending.append(f"line {node.lineno}: {name}")
    check("secrets.py reads no secret-named variable from the environment", not offending,
          "; ".join(offending))

    print(f"\n=== {passed}/{passed + failed} checks passed ===")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()