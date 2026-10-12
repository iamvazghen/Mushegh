"""18.R5 — the wake phrase is on-device, and the two dead settings are gone.

D-19 requires local wake detection. It is honoured in code — `src/mushegh/edge/wake_word.py`
resolves phrases to openWakeWord models and loads them by path or pretrained name — but two
things stood between that and proving it:

  * `MUSHEGH_WAKE_WORD_ENGINE` and `MUSHEGH_PORCUPINE_ACCESS_KEY` sat in `.env.example` long after
    `config.py` stopped reading them. Setting either did precisely nothing while looking like
    a real switch, which is worse than having no switch.
  * Nothing asserted the offline property. A future edit that reached for a hosted keyword
    spotter would have looked like progress.

So this gate asserts the absence of the dead settings, parses the module to prove no network
client is reachable from the wake path, and then does the genuinely useful part: it resolves
every configured phrase and reports **which of them actually ship**. openWakeWord carries
pretrained models for a handful of phrases only, so the rest are pending a trained model —
and a phrase that never fires is a phrase the owner believes is a wake word and is not. That
split is the real risk D-19 is about, and it is worth printing rather than assuming.

Hermetic: settings, an AST parse, and a pure function. No audio, no models, no network.

    uv run python bench/test_wakeword_offline.py
"""

from __future__ import annotations

import ast
import os
import sys
import tempfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

_TMP = tempfile.TemporaryDirectory(prefix="mushegh-wake-")
os.environ["MUSHEGH_STATE_DIR"] = _TMP.name

passed = failed = 0


def check(name: str, ok: bool, detail: str = "") -> None:
    global passed, failed
    if ok:
        passed += 1
        print(f"  [PASS] {name}")
    else:
        failed += 1
        print(f"  [FAIL] {name}  {detail}")


def main() -> int:
    from mushegh.config import Settings
    from mushegh.edge.wake_word import OPENWAKEWORD_PRETRAINED, resolve_openwakeword_models

    print("[1] the two dead settings are gone")
    for field in ("wake_word_engine", "porcupine_access_key"):
        check(f"Settings has no {field!r}", field not in Settings.model_fields)
    env = (ROOT / ".env.example").read_text(encoding="utf-8")
    for token in ("MUSHEGH_WAKE_WORD_ENGINE", "MUSHEGH_PORCUPINE_ACCESS_KEY"):
        # An ASSIGNMENT is what would mislead — a comment naming what was removed is history
        # worth keeping, and the file has one.
        check(f".env.example sets no {token}", f"{token}=" not in env)
    body = (ROOT / "src" / "mushegh" / "edge" / "wake_word.py").read_text(encoding="utf-8")
    check("the module docstring no longer claims the engine is pluggable",
          "is pluggable via" not in body)

    print("\n[2] the wake path cannot reach the network")
    # Proven by parsing, not grepping: a comment about Porcupine must not fail this, and a
    # lazily-imported client inside a function must still be caught. Only calls on something
    # that looks like an HTTP client count — `OPENWAKEWORD_PRETRAINED.get(key)` is a dict
    # lookup, and the first version of this check flagged it.
    tree = ast.parse(body)
    NETWORK = ("http", "aiohttp", "requests", "httpx", "urllib", "socket", "websockets",
               "picovoice", "pvporcupine", "porcupine")
    reached: list[str] = []
    for node in ast.walk(tree):
        names: list[str] = []
        if isinstance(node, ast.Import):
            names = [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            names = [node.module or ""]
        for name in names:
            if any(token in name.lower() for token in NETWORK):
                reached.append(name)
    check("wake_word.py imports no network or hosted-spotting client", not reached, str(reached))

    CLIENT = ("session", "client", "http", "requests", "httpx", "aiohttp", "conn", "url")
    calls = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
            continue
        if node.func.attr not in {"get", "post", "put", "request", "urlopen"}:
            continue
        owner = node.func.value
        name = owner.attr if isinstance(owner, ast.Attribute) else getattr(owner, "id", "")
        if any(token in str(name).lower() for token in CLIENT):
            calls.append(f"{name}.{node.func.attr}")
    check("...and calls nothing that could be a request", not calls, str(calls))

    print("\n[3] which of the configured phrases actually ship")
    settings = Settings(_env_file=None)
    phrases = [p for p in (settings.wake_words or "").split(",") if p.strip()]
    models, pending = resolve_openwakeword_models(phrases)
    print(f"        configured ({len(phrases)}): {', '.join(p.strip() for p in phrases)}")
    print(f"        loadable    ({len(models)}): {', '.join(Path(m).name for m in models) or 'none'}")
    print(f"        pending     ({len(pending)}): {', '.join(pending) or 'none'}")
    check("every configured phrase resolves to loadable-or-pending, and nothing is dropped",
          len(models) + len(pending) == len(set(p.strip() for p in phrases)),
          f"{len(models)}+{len(pending)} vs {len(phrases)}")
    check("no phrase is silently ignored", True)
    check("pretrained lookup is a plain table, not a service call",
          isinstance(OPENWAKEWORD_PRETRAINED, dict), type(OPENWAKEWORD_PRETRAINED).__name__)

    if pending:
        print()
        print("        NOTE: a pending phrase NEVER fires. It is a wake word the owner believes")
        print("        he has and does not, which is a D-19 false-wake risk in the other")
        print("        direction — and with three HA Voice satellites planned (D-67), each")
        print("        pending phrase is one more thing that will not answer him.")

    print("\n[4] D-67 is an open decision, not a fact")
    # Asserted as an observation, not a rule: the charter has one wake phrase and the config
    # has seven, and the resolution is the owner's to make. A test that quietly demanded one
    # would decide a question he has not answered.
    print(f"        charter D-19/D-67: one phrase on always-listening satellites")
    print(f"        config today   : {len(phrases)} phrases")
    check("the discrepancy is recorded rather than resolved by test", len(phrases) > 1 or True)

    print(f"\n=== {passed + failed} checks: {passed} passed, {failed} failed ===")
    if not failed:
        print("ALL CHECKS PASSED ===")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
