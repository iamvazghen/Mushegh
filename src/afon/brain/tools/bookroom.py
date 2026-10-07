"""D-86 — the owner's own Bookroom summarisation SDK, as one tool with four actions.

Bookroom turns an EPUB or PDF into a 16-section study guide, has JEv score each section, and
exports Markdown, PDF, a concept map and a claim audit. The SDK is the owner's; this module is the
seam Afon reaches it through.

**Why this is a tool and not an executor, which D-86 originally assumed.** The executor contract in
``src/afon/brain/executors/__init__.py`` exists to bound an external *agent* that acts on its own
judgement — it refuses interpreters, withholds credentials from the child, and derives success from
an exit code. Bookroom is a library, not an agent, and three things make the subprocess route
strictly worse here:

1. **The SDK's own rule is that Python holds the keys in the process.** Its skill file says so
   first and in bold. A subprocess would marshal ``GEMINI_API_KEY`` into a child for no gain;
   Afon's brain is already the server-side Python process the SDK is designed to live in.
2. **The CLI has no ``preflight`` subcommand.** ``bookroom`` exposes serve/check/describe/guide/
   extract, and `guide` does not preflight on its way in. Preflight is the one call the SDK says to
   always make before spending, so routing through the CLI would lose exactly the safety step.
3. **A study guide is a long checkpointed job**, not a request. The contract's deadline-and-result
   shape fits an errand; it does not fit a run that resumes from its last finished stage.

So the executor roster still reports no `reading` executor, and that is now a recorded decline
rather than a gap. What is kept from the contract is its reasoning: the paid action is gated, the
cost is charged to the governor, and nothing is reported as more certain than it is.

**Three honesty rules from the SDK's own skill file, enforced here rather than hoped for:**

- ``report.quality`` says how many of the 16 categories met the threshold. A run with some below it
  is a legitimate outcome, **not** a failure and **not** a full pass. The number is always spoken.
- ``claim_audit`` is **lexical overlap, not fact-checking.** It is never described as verification.
- OCR confidence is a recognition signal. A low-confidence name is a prompt to look at the page,
  not a claim that the text is right.

**What is not configured on this machine, and what is about to change.** The SDK wraps a separate
application — a flat tree containing ``book_pipeline.py`` — which it imports from
``BOOKROOM_APP_ROOT``. That engine does not ship with the SDK repository today, and **every** call
goes through it, including `extract`. Without the variable set, this tool says so and names it (the
``base.not_configured`` contract) rather than raising into the turn loop.

The owner is bundling the engine into the package so it installs and runs offline with no home
directory access. Nothing in this module assumes the current arrangement: it never reads
``BOOKROOM_APP_ROOT`` itself, never constructs the engine path, and recognises the missing-engine
case from the SDK's own error text. When the engine ships inside the package that branch stops
firing on its own, and the rest of this file is unaffected — which is the only reason it is worth
writing an integration against a thing that is still moving.
"""

from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import Any

from loguru import logger

from afon.brain.tools.base import clip, missing_arg, not_configured, tool_error
from afon.config import settings

#: How long a preflight stays good for. Long enough to hear the estimate, answer a question and say
#: yes; short enough that a figure from this morning cannot authorise an afternoon run.
PREFLIGHT_TTL_S = 1800

#: path -> (monotonic timestamp, the spoken estimate). Module state, like the browser's commit flag:
#: the guard is "has he heard what this costs", which is a property of the conversation and not of
#: the file.
_preflights: dict[str, tuple[float, str]] = {}


def _resolved(source: str) -> str:
    try:
        return str(Path(source).expanduser().resolve())
    except Exception:  # noqa: BLE001 — an unresolvable path is handled by the SDK's own error
        return str(source)


def preflight_is_fresh(source: str) -> bool:
    """Has this exact book been priced recently enough to spend against? Test seam, and the gate."""
    entry = _preflights.get(_resolved(source))
    return bool(entry) and (time.monotonic() - entry[0]) < PREFLIGHT_TTL_S


def forget_preflights() -> None:
    """Test seam."""
    _preflights.clear()


def _room() -> Any:
    """Build the SDK client, or raise the plainest possible explanation of what is missing."""
    from bookroom_sdk.client import Bookroom

    return Bookroom.from_env()


def _unconfigured_note(exc: Exception) -> str | None:
    """Turn the SDK's own setup errors into the one sentence the owner can act on.

    Matched on the SDK's error TEXT rather than on a variable this module checks itself, and that
    is deliberate forward-compatibility: the owner is bundling the engine into the package so it
    installs and runs offline without reaching into a home directory. When that lands,
    ``BOOKROOM_APP_ROOT`` stops being required and this branch simply stops firing — nothing here
    needs editing, and nothing here will keep asking for a variable that no longer exists. A
    module that tested for the variable itself would have had to be found and changed.
    """
    text = str(exc)
    if "BOOKROOM_APP_ROOT" in text or "book_pipeline.py" in text or "Could not locate" in text:
        return not_configured(
            "the book summarizer",
            "BOOKROOM_APP_ROOT pointing at the directory that holds book_pipeline.py "
            "(not needed once the engine ships inside the package)",
        )
    if "llm_api_key" in text or "GEMINI_API_KEY" in text:
        return not_configured("the book summarizer", "a GEMINI_API_KEY")
    return None


async def book(args: dict) -> str:
    """Read, price, or summarise a book. One tool, four actions, only one of which spends."""
    action = str(args.get("action") or "").strip().lower()
    source = str(args.get("source") or "").strip()

    if action not in {"check", "outline", "preflight", "guide"}:
        return missing_arg(
            "book", args, "action", "source", "language", "length", "no_review",
            ask=("Which would you like, sir — check the summarizer, outline a book, price one, "
                 "or run the full guide?"))
    if action != "check" and not source:
        return missing_arg(
            "book", args, "source", "action", "language", "length", "no_review",
            ask="Which book, sir? I need the path to the EPUB or the PDF.")

    try:
        from bookroom_sdk import errors as bk_errors
    except ImportError:
        return not_configured("the book summarizer", "the bookroom-sdk package")

    try:
        room = await asyncio.to_thread(_room)
    except ImportError:
        return not_configured("the book summarizer", "the bookroom-sdk package")
    except Exception as e:  # noqa: BLE001
        note = _unconfigured_note(e)
        return note if note else tool_error("the book summarizer", e)

    try:
        if action == "check":
            return await asyncio.to_thread(_check, room)
        if action == "outline":
            return await asyncio.to_thread(_outline, room, source)
        if action == "preflight":
            return await asyncio.to_thread(_preflight, room, source, args)
        return await asyncio.to_thread(_guide, room, source, args)
    except Exception as e:  # noqa: BLE001
        note = _unconfigured_note(e)
        if note:
            return note
        return _speak_sdk_error(bk_errors, e)


def _speak_sdk_error(bk_errors: Any, e: Exception) -> str:
    """The SDK's failure modes, in the owner's terms, with the action he can take."""
    name = type(e).__name__
    if name == "UnsupportedSourceError":
        return "That is not an EPUB or a PDF, sir — those are the two it reads."
    if name == "ExtractionError":
        return ("I could not find any text in that file, sir. If it is a scanned PDF it needs OCR "
                "turned on, which needs Tesseract installed.")
    if name == "BudgetExceededError":
        return (f"That book is over the per-batch budget cap, sir, so I stopped before spending "
                f"anything. Either the cap goes up or the book gets split. ({clip(str(e), 200)})")
    if name == "QuotaError":
        retry = getattr(e, "retry_after_seconds", None) or getattr(e, "retryAfterSeconds", None)
        when = f" It suggests waiting about {int(retry)} seconds." if retry else ""
        return ("The provider quota is exhausted, sir — nothing was lost, the run resumes from its "
                "last finished stage when we try again." + when)
    if name == "ValidationError":
        return ("The report came out malformed, sir, and I am not going to paper over that — it is "
                f"a bug in the summarizer worth reporting. ({clip(str(e), 200)})")
    return tool_error("the book summarizer", e)


def _check(room: Any) -> str:
    report = room.check()
    data = report.as_dict() if hasattr(report, "as_dict") else dict(report)
    ok = bool(data.get("ok"))
    # Asked of config, not of the environment: 36.F5 gives a credential exactly one home, and
    # `check_public_clean` caught the version that read os.environ here. The aliases are declared
    # in `afon/config.py`, which is also where a reviewer looks for what Afon can be given.
    have_llm = settings.bookroom_llm_api_key is not None
    have_jev = (settings.bookroom_jev_api_key is not None
                or settings.typesafe_api_key is not None)
    jev = "JEv review is on" if have_jev else "JEv review will be skipped (no TYPESAFE_API_KEY)"
    if ok:
        return f"The summarizer is ready, sir. {jev}."
    why = clip(str(data.get("status") or data.get("message") or data), 240)
    missing = [n for n, present in (("GEMINI_API_KEY", have_llm),) if not present]
    tail = f" {missing[0]} is not set." if missing else ""
    return f"The summarizer is not ready, sir — {why}.{tail} I have not started anything."


def _outline(room: Any, source: str) -> str:
    document = room.extract.extract(source, include_text=False)
    data = document.as_dict(include_text=False) if hasattr(document, "as_dict") else dict(document)
    sections = data.get("sections") or []
    title = (data.get("metadata") or {}).get("title") or Path(source).name
    heads = "; ".join(str(s.get("title") or "untitled") for s in sections[:6])
    more = f", and {len(sections) - 6} more" if len(sections) > 6 else ""
    return (f"{title}, sir — {len(sections)} section(s): {heads}{more}. Nothing has been spent; "
            f"ask me to price it before a full guide.")


def _preflight(room: Any, source: str, args: dict) -> str:
    plan = room.summarize.preflight(source, options=_options(args))
    data = plan.as_dict() if hasattr(plan, "as_dict") else dict(plan)
    tokens = data.get("estimated_llm_input_tokens") or getattr(plan, "estimated_llm_input_tokens", 0)
    credits = data.get("estimated_jev_credits") or getattr(plan, "estimated_jev_credits", 0)
    batches = data.get("batch_count") or getattr(plan, "batch_count", 0)
    spoken = (f"About {int(tokens):,} input tokens, {int(credits):,} JEv credits, across "
              f"{int(batches)} batch(es)")
    _preflights[_resolved(source)] = (time.monotonic(), spoken)
    return (f"{spoken}, sir. That is within the budget caps — the estimate fails loudly if it is "
            f"not. Say the word and I will run the full guide.")


def _guide(room: Any, source: str, args: dict) -> str:
    # The SDK's skill file says to always preflight before spending, and the CLI route cannot. So
    # the requirement lives here: an unpriced book is not summarised, it is priced first. This is a
    # refusal rather than an automatic preflight on purpose — the point of the estimate is that the
    # owner hears it, and a figure nobody heard is not a budget check.
    if not preflight_is_fresh(source):
        return ("I have not priced that one yet, sir. Let me run the estimate first — a full guide "
                "is the only thing here that spends, and I would rather you heard the number.")

    report = room.summarize.study_guide(
        source,
        options=_options(args),
        review=not bool(args.get("no_review")),
        progress=lambda message, **kw: logger.info(f"bookroom: {message}"),
    )
    data = report.as_dict() if hasattr(report, "as_dict") else dict(report)
    _charge(data)

    quality = data.get("quality") or {}
    met = quality.get("met") if isinstance(quality, dict) else None
    total = quality.get("total") if isinstance(quality, dict) else None
    if met is None or total is None:
        # Better to say the quality figure is missing than to imply a full pass.
        grade = "The run finished; I could not read the quality summary, so do not assume a pass"
    elif int(met) == int(total):
        grade = f"All {int(total)} categories met the threshold"
    else:
        grade = (f"{int(met)} of {int(total)} categories met the threshold — the rest came out "
                 f"below it, which is a real outcome and not a crash")

    artifacts = data.get("artifacts") or data.get("exports") or {}
    where = ", ".join(sorted(str(k) for k in artifacts)) if isinstance(artifacts, dict) else ""
    out = data.get("output_dir") or data.get("outputDir") or ""
    tail = f" Files: {where}." if where else ""
    place = f" In {out}." if out else ""
    audit = ("" if "claim_audit" not in str(artifacts) else
             " The claim audit is lexical overlap, not fact-checking — a flagged line needs your "
             "eye, it is not a verification.")
    return f"Done, sir. {grade}.{place}{tail}{audit}"


def _options(args: dict) -> dict:
    opts: dict[str, Any] = {}
    if args.get("language"):
        opts["language"] = str(args["language"])
    if args.get("length"):
        opts["digest_length"] = str(args["length"])
    return opts


def _charge(data: dict) -> None:
    """Charge the run to the shared ledger. Best effort — accounting never fails a finished run."""
    try:
        from afon.brain.governor import Governor

        usage = data.get("usage") or {}
        Governor().charge(calls=1,
                          in_tokens=int(usage.get("input_tokens") or 0),
                          out_tokens=int(usage.get("output_tokens") or 0))
    except Exception as e:  # noqa: BLE001
        logger.warning(f"bookroom: could not charge the governor: {e}")


SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "book",
            "description": (
                "Read, price or summarise a BOOK (EPUB or PDF) with the owner's own Bookroom "
                "summarizer. actions: check (are the credentials and engine ready), outline (what "
                "sections the book has — free), preflight (what a full guide would cost — free, "
                "and required first), guide (the full 16-section study guide with JEv review and "
                "Markdown/PDF/concept-map/claim-audit exports — THIS SPENDS MONEY and is "
                "confirmed). Use for 'summarise this book', 'what's in this PDF', 'make me a study "
                "guide'. Always preflight before a guide; the tool refuses an unpriced book."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string",
                               "enum": ["check", "outline", "preflight", "guide"]},
                    "source": {"type": "string",
                               "description": "Path to the .epub or .pdf. Not needed for check."},
                    "language": {"type": "string",
                                 "description": "Output language, e.g. 'English'. Optional."},
                    "length": {"type": "string", "enum": ["brief", "standard", "deep"],
                               "description": "Digest length. Optional, default standard."},
                    "no_review": {"type": "boolean",
                                  "description": "Skip the JEv review pass. Optional."},
                },
                "required": ["action"],
            },
        },
    },
]

HANDLERS = {"book": book}
