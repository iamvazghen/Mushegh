"""D-86 — the Bookroom summarizer is reachable, and the one call that spends is fenced.

The owner's SDK turns an EPUB or PDF into a 16-section study guide with JEv review and
Markdown/PDF/concept-map/claim-audit exports. Its own skill file carries three rules that are
easy to agree with and easy to quietly break, so each is a check here:

  1. **Always preflight before spending.** The SDK's CLI has no `preflight` subcommand and its
     `guide` command does not preflight on the way in, so the requirement cannot be inherited — it
     has to live in this seam. An unpriced book is refused, and the refusal is a refusal rather
     than an automatic estimate, because the point of the number is that the owner *hears* it.
  2. **Report `quality` honestly.** A run where some of the 16 categories fall below threshold is
     a legitimate outcome. It must not be spoken as a full pass, and a missing quality figure must
     not be spoken as one either.
  3. **`claim_audit` is lexical overlap, not fact-checking.** It is never described as verification.

Plus the Afon-side rules: the paid action is confirm-gated and the free ones are not (a gate in
front of a cost estimate teaches the owner to skip the estimate), and a missing SDK or a missing
engine degrades to a spoken "not configured" instead of raising into the turn loop.

Hermetic: the SDK is **stubbed** in `sys.modules`. The real one wraps a separate application —
a flat tree containing `book_pipeline.py`, reached through `BOOKROOM_APP_ROOT` — which is not in
the SDK repository, so every real call needs an engine this host does not have. That is exactly
why the degradation paths are tested first.

    uv run python bench/test_bookroom_tool.py
"""

from __future__ import annotations

import asyncio
import sys
import types
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

passed = failed = 0


def check(name: str, ok: bool, detail: str = "") -> None:
    global passed, failed
    if ok:
        passed += 1
        print(f"  [PASS] {name}")
    else:
        failed += 1
        print(f"  [FAIL] {name}" + (f"  <- {detail}" if detail else ""))


# ── the stub ──────────────────────────────────────────────────────────────────────────────────

class _Err(RuntimeError):
    pass


class ConfigError(_Err):
    pass


class UnsupportedSourceError(_Err):
    pass


class ExtractionError(_Err):
    pass


class BudgetExceededError(_Err):
    pass


class QuotaError(_Err):
    def __init__(self, msg: str = "", retry_after_seconds: int = 90) -> None:
        super().__init__(msg)
        self.retry_after_seconds = retry_after_seconds


class ValidationError(_Err):
    pass


class _Obj:
    def __init__(self, data: dict) -> None:
        self._data = data
        for k, v in data.items():
            setattr(self, k, v)

    def as_dict(self, **_kw) -> dict:
        return self._data


class _FakeRoom:
    """Records what was called, so the gate can prove nothing was spent on a refused path."""

    def __init__(self) -> None:
        self.calls: list[str] = []
        self.health = {"ok": True, "status": "ready"}
        self.raise_on_guide: Exception | None = None
        self.quality = {"met": 16, "total": 16}
        self.artifacts = {"markdown": "r.md", "pdf": "r.pdf", "claim_audit": "a.json"}
        self.extract = types.SimpleNamespace(extract=self._extract)
        self.summarize = types.SimpleNamespace(preflight=self._preflight,
                                               study_guide=self._study_guide)

    def check(self):
        self.calls.append("check")
        return _Obj(dict(self.health))

    def _extract(self, source, include_text=False, options=None):
        self.calls.append("extract")
        return _Obj({"metadata": {"title": "Meditations"},
                     "sections": [{"title": f"Book {i}"} for i in range(1, 13)]})

    def _preflight(self, source, options=None):
        self.calls.append("preflight")
        return _Obj({"estimated_llm_input_tokens": 412_000,
                     "estimated_jev_credits": 96, "batch_count": 7})

    def _study_guide(self, source, options=None, review=True, progress=None, **kw):
        self.calls.append("study_guide")
        if self.raise_on_guide:
            raise self.raise_on_guide
        if progress:
            progress("stage 1 of 16")
        return _Obj({"quality": dict(self.quality), "artifacts": dict(self.artifacts),
                     "output_dir": "/out/meditations",
                     "usage": {"input_tokens": 400_000, "output_tokens": 90_000}})


def install_stub(room: _FakeRoom) -> None:
    errors_mod = types.ModuleType("bookroom_sdk.errors")
    for cls in (ConfigError, UnsupportedSourceError, ExtractionError, BudgetExceededError,
                QuotaError, ValidationError):
        setattr(errors_mod, cls.__name__, cls)
    client_mod = types.ModuleType("bookroom_sdk.client")
    client_mod.Bookroom = types.SimpleNamespace(from_env=lambda **kw: room)
    pkg = types.ModuleType("bookroom_sdk")
    pkg.errors = errors_mod
    pkg.client = client_mod
    sys.modules.update({"bookroom_sdk": pkg, "bookroom_sdk.errors": errors_mod,
                        "bookroom_sdk.client": client_mod})


def remove_stub() -> None:
    for name in [n for n in sys.modules if n == "bookroom_sdk" or n.startswith("bookroom_sdk.")]:
        del sys.modules[name]


def main() -> int:
    from afon.brain.proactive import CONFIRM_TIER, confirm_required
    from afon.brain.tools import bookroom as B

    run = lambda a: asyncio.run(B.book(a))  # noqa: E731

    print("[1] with no SDK installed, it says so and never raises")
    remove_stub()
    for action, args in (("check", {}), ("outline", {"source": "x.epub"}),
                         ("preflight", {"source": "x.epub"}), ("guide", {"source": "x.epub"})):
        out = run(dict(args, action=action))
        check(f"{action} degrades to a spoken note", "isn't configured" in out, out[:90])
        check(f"...naming what is missing ({action})", "bookroom-sdk" in out, out[:90])

    print("\n[2] bad arguments are refused before anything is imported")
    # `base.missing_arg` answers with a QUESTION when the right keys arrived and an ERROR when the
    # model invented key names. Both are asserted on behaviour rather than on a keyword: the first
    # draft of these checks looked for the words "action"/"source" in the reply, which would have
    # passed on any sentence containing them and failed on a correct one that did not.
    out = run({"action": "incinerate"})
    check("an unknown action does not reach the SDK",
          "isn't configured" not in out and bool(out.strip()), out[:90])
    check("...and the reply offers the real actions",
          all(w in out.lower() for w in ("outline", "price", "guide")), out[:120])
    out = run({})
    check("a bare call asks which action rather than guessing",
          "?" in out and "guide" in out.lower(), out[:120])
    out = run({"action": "guide"})
    check("guide with no source asks which book", "which book" in out.lower(), out[:120])
    check("...and names the two formats it reads",
          "epub" in out.lower() and "pdf" in out.lower(), out[:120])
    out = run({"chapter": 3, "booknames": "x"})
    # `base.tool_error` turns the ValueError into spoken prose rather than echoing it, so the thing
    # to assert is that this path is an ERROR and not the fluent question above — a question would
    # be read out by the model as the answer, with the tool never having run.
    check("invented key names produce an error, not a fluent question",
          "couldn't complete" in out.lower() and "outline" not in out.lower(), out[:140])

    print("\n[3] credentials are checked, and a bad key stops the run")
    room = _FakeRoom()
    install_stub(room)
    B.forget_preflights()
    out = run({"action": "check"})
    check("a healthy check is reported", "ready" in out.lower(), out)
    room.health = {"ok": False, "status": "invalid api key"}
    out = run({"action": "check"})
    check("an unhealthy check says so", "not ready" in out.lower(), out)
    check("...and states that nothing was started", "not started" in out.lower(), out)
    room.health = {"ok": True, "status": "ready"}

    print("\n[4] the free actions spend nothing")
    room.calls.clear()
    out = run({"action": "outline", "source": "x.epub"})
    check("an outline names the book and its sections", "Meditations" in out and "12" in out, out)
    check("...and says nothing was spent", "spent" in out.lower(), out)
    check("...and did not call the paid path", "study_guide" not in room.calls, str(room.calls))

    print("\n[5] THE FENCE — an unpriced book is not summarised")
    room.calls.clear()
    B.forget_preflights()
    out = run({"action": "guide", "source": "x.epub"})
    check("a guide without a preflight is refused", "priced" in out.lower(), out)
    check("...and the paid call never happened", "study_guide" not in room.calls, str(room.calls))
    check("...and it offers the estimate instead of just saying no",
          "estimate" in out.lower(), out)

    print("\n[6] priced, then run")
    room.calls.clear()
    out = run({"action": "preflight", "source": "x.epub"})
    check("the estimate carries tokens, credits and batches",
          "412,000" in out and "96" in out and "7" in out, out)
    check("the preflight is remembered for this book", B.preflight_is_fresh("x.epub"))
    check("...and not for a different one", not B.preflight_is_fresh("other.epub"))
    out = run({"action": "guide", "source": "x.epub"})
    check("the guide now runs", "study_guide" in room.calls, str(room.calls))
    check("...and reports where the files are", "/out/meditations" in out, out)

    print("\n[7] a stale estimate cannot authorise a run")
    import time as _t
    key = str(Path("x.epub").expanduser().resolve())
    B._preflights[key] = (_t.monotonic() - B.PREFLIGHT_TTL_S - 1, "old")
    room.calls.clear()
    out = run({"action": "guide", "source": "x.epub"})
    check("an expired preflight is refused like none at all", "priced" in out.lower(), out)
    check("...and nothing was spent", "study_guide" not in room.calls, str(room.calls))

    print("\n[8] quality is reported honestly — the SDK's own rule")
    def priced_guide() -> str:
        B._preflights[key] = (_t.monotonic(), "fresh")
        return run({"action": "guide", "source": "x.epub"})

    room.quality = {"met": 16, "total": 16}
    out = priced_guide()
    check("a full pass says all 16 met the threshold", "All 16" in out, out)
    room.quality = {"met": 11, "total": 16}
    out = priced_guide()
    check("a partial run says 11 of 16", "11 of 16" in out, out)
    check("...and is NOT described as a pass", "all 16" not in out.lower(), out)
    check("...and names the shortfall as a real outcome", "not a crash" in out.lower(), out)
    room.quality = {}
    out = priced_guide()
    check("a missing quality figure does not imply a pass",
          "do not assume a pass" in out.lower(), out)

    print("\n[9] the claim audit is never called verification")
    room.quality = {"met": 16, "total": 16}
    out = priced_guide()
    check("the claim audit is described as lexical overlap",
          "lexical overlap" in out.lower(), out)
    check("...and explicitly not as fact-checking",
          "not fact-checking" in out.lower() or "not a verification" in out.lower(), out)
    for word in ("verified", "confirmed the facts", "fact-checked"):
        check(f"the word {word!r} is not used about it", word not in out.lower(), out)

    print("\n[10] every SDK failure mode speaks, and none of them crashes the turn")
    cases = [
        (UnsupportedSourceError("nope"), "epub", "an unsupported file names the two it reads"),
        (ExtractionError("empty"), "ocr", "an empty extraction suggests OCR"),
        (BudgetExceededError("cap 300k"), "budget", "an over-budget book says the cap"),
        (QuotaError("429", 120), "resumes", "a quota error says the run resumes"),
        (ValidationError("bad md"), "bug", "a malformed report is called a bug, not papered over"),
    ]
    for exc, needle, label in cases:
        room.raise_on_guide = exc
        out = priced_guide()
        check(label, needle in out.lower(), out[:120])
    room.raise_on_guide = BudgetExceededError("cap")
    out = priced_guide()
    check("an over-budget run states that nothing was spent",
          "before spending anything" in out.lower(), out)
    room.raise_on_guide = None

    print("\n[11] only the paid action is confirm-gated")
    check("book is in CONFIRM_TIER", "book" in CONFIRM_TIER)
    check("guide confirms", confirm_required("book", {"action": "guide"}))
    for free in ("check", "outline", "preflight"):
        check(f"{free} does not confirm", not confirm_required("book", {"action": free}),
              "a gate in front of a cost estimate teaches him to skip the estimate")

    print("\n[12] the tool is wired into the registry and reachable")
    from afon.brain.tools import LAZY_GROUP_TRIGGERS, group_tool_schemas, tool_handlers
    check("the handler is registered", "book" in tool_handlers())
    check("it has a lazy group of its own", "reading" in LAZY_GROUP_TRIGGERS)
    names = [s["function"]["name"] for s in group_tool_schemas("reading")]
    check("the group advertises the tool", names == ["book"], str(names))
    from afon.brain.tools import groups_for_text
    check("'summarise this book' arms the group",
          "reading" in groups_for_text("can you summarise this book for me"))
    check("'book me a table' does NOT arm it",
          "reading" not in groups_for_text("book me a table at eight"),
          "the triggers name the artefact, not the word 'book'")

    print("\n[13] the integration does not assume the engine lives outside the package")
    # The owner is bundling the engine so the package installs and runs offline with no home
    # directory access. This asserts the module is not standing in the way of that: it never reads
    # BOOKROOM_APP_ROOT itself and never builds the engine path, so when the engine ships inside
    # the package the missing-engine branch stops firing on its own.
    mod_src = Path(B.__file__).read_text(encoding="utf-8")
    body = mod_src.split('"""', 2)[-1]          # past the module docstring
    check("the module never READS the engine path variable",
          'environ.get("BOOKROOM_APP_ROOT")' not in body
          and "environ['BOOKROOM_APP_ROOT']" not in body,
          "that is the SDK's job; a second copy is what would need editing later")
    check("the missing-engine message says the variable will stop being needed",
          "once the engine ships inside the package" in mod_src)
    # Checked by INDENTATION, not by position in the file: `_room()` is defined above `book()`,
    # so "before the handler" is the wrong test — the first draft of this check used it and failed
    # on correct code. What matters is that no import of the SDK sits at module level.
    top_level = [ln for ln in mod_src.splitlines()
                 if ln[:1] not in (" ", "\t") and "bookroom_sdk" in ln
                 and (ln.startswith("import ") or ln.startswith("from "))]
    check("the SDK is imported inside a function, never at module level",
          not top_level,
          f"a module-level import would break the brain on a version mismatch: {top_level}")
    check("...and it is imported somewhere", "bookroom_sdk" in body)

    print("\n[14] the executor roster still declines this domain, and now says why")
    import afon.brain.executors as X
    from afon.brain.executors import Domain
    check("no executor serves reading",
          not any(Domain.READING in s.domains for s in X.SPECS),
          "the SDK is a library, not an agent: a subprocess would marshal a key into a child "
          "and lose preflight")

    print(f"\n=== {passed + failed} checks: {passed} passed, {failed} failed ===")
    if not failed:
        print("ALL CHECKS PASSED ===")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
