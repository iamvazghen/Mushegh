"""PROBE (read-only, changes nothing): does the `answerable` lever work **on the real path**?

`probe_jev_answerable.py` asked this question once and returned `gap +0.06` — no separation. §01.J1
recorded that result but did not trust it, and named the two ways it could be wrong. This probe is
the second attempt, built to remove both defects rather than to argue with the first one.

## What was wrong with the first probe

**1. It asked on the wrong path.** §01.J1's lever is an `answerable` verdict *"in the call it ALREADY
makes"* — one bounded call, because D-92/D-72 protect exactly that. The first probe instead called
`judge()`, which is a **separate** method that ships its own hard-coded instruction:

    "Select the option that best answers the owner's stated **decision**. Return only the typed
     choice judgment; authorization and execution are out of scope."

and passed the real question as the *criteria text* of two option labels. The model was told to pick
the option that best answers a **decision**, then handed options called `answerable` /
`not_answerable`. The framing fights the instruction. That is the suspicion §01.J1 recorded, and it
was correct: a probe that cannot ask its own question cleanly is measuring the harness.

**This probe sends the answerability question the way `assess_turn` sends clarity, urgency and
tone** — same `choice` type, same own `instructions`, same own `criteria`, inside the same single
payload. The production lever is then exactly this call, so the probe measures the lever and not a
neighbour of it.

**2. Its corpus was mislabelled in both directions.** "Will it rain here next Tuesday?" and "How many
rabbits are there in Armenia right now?" were filed ANSWERABLE — neither is answerable from
knowledge; both need a live source. "Is nuclear power the right choice for Germany?" and "Was the
euro a good idea for southern Europe?" were filed UNKNOWABLE — both are discussable with nuance.
Errors in opposite directions do not average out, they cancel.

**3. Topic and answerability were confounded.** The UNKNOWABLE set was almost entirely future /
counterfactual / private-history, the ANSWERABLE set almost entirely general fact / arithmetic /
definition. A model could separate those two populations **by topic** and score a full gap while
having no answerability signal at all. Every pair here is **topic-matched**: both members of a pair
name the same subject and differ only in whether a source exists.

## Three classes, because "answerable" has two meanings

| class | meaning | expected |
|---|---|---|
| `K` | answerable from knowledge / recall / computation | answerable |
| `T` | answerable only through a TOOL (clock, mail, files) | **contested — see below** |
| `U` | no source exists | not answerable |

`T` is not padding, it is the deployment hazard. The payload carries `state: {question: <utterance>}`
and nothing else — no tool results, no catalogue. So Jev is judging answerability **without tools**,
while the thing it gates (a turn) has them. A verdict used naively would mark "what time is it"
unanswerable and suppress exactly the turns that need a tool. Whether Jev does that is an empirical
question, and this probe is the only place it gets asked.

## Method

One call per utterance, the real payload shape, the production arbitration cap. Reads
p(answerable) for the two criteria. Reports K-vs-U separation (**the signal §01.J1 needs**) and the
`T` behaviour (**the risk of shipping it**) separately, and says which of the two a verdict would
actually depend on.

    uv run python tools/probe_jev_answerable_v2.py
    uv run python tools/probe_jev_answerable_v2.py --model jev-latest
"""
from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from mushegh.brain.judgment import (  # noqa: E402
    ROUTE_INSTRUCTIONS,
    TONE_BANDS,
    URGENCY_BANDS,
    JudgmentService,
)

#: (prompt, class). Paired on topic; `topic` is only used to report the control, never to decide.
PAIRS: list[tuple[str, str, str, str]] = [
    # --- geography ---------------------------------------------------------------
    ("geo-capital", "What is the capital of Armenia?", "K",
     "What will the capital of Armenia be in the year 2200?"),
    ("geo-population", "How many people live in Yerevan?", "K",
     "How many people will be living in Yerevan in the year 2200?"),
    # --- arithmetic --------------------------------------------------------------
    ("arith-product", "What is 17 times 23?", "K",
     "How many minutes will I have worked in total by the end of next month?"),
    ("arith-count", "How many days are there in a leap year?", "K",
     "How many hours did I sleep in total last night?"),
    # --- linguistics -------------------------------------------------------------
    ("lang-spoken", "What language is spoken in Brazil?", "K",
     "What language will be spoken in Brazil in the year 2200?"),
    ("lang-translate", "How do you say 'good morning' in German?", "K",
     "How would you translate 'good morning' into every language by 2200?"),
    # --- tool-answerable, NOT knowledge-answerable --------------------------------
    ("tool-clock", "What time is it right now?", "T",
     "What time will it be at exactly this moment in ten years?"),
    ("tool-mail", "How many unread emails do I have?", "T",
     "How many unread emails will I have received by the end of next month?"),
    # --- opinion / personal prediction (the genuinely unknowable tail) ------------
    ("value-choice", "Is 91 a prime number?", "K",
     "Is nuclear power the right choice for Germany?"),
    ("value-history", "Who wrote 'Le Petit Prince'?", "K",
     "Am I going to get the job I applied for?"),
]

#: The question under test, worded to name the ABSENCE of tools — because that is the context it
#: will actually be asked in, and a probe that silently assumes tools it does not send is the same
#: class of defect that sank the first one.
ANSWERABLE_INSTRUCTIONS = (
    "Is this request answerable? Judge only from what can be recalled or computed without "
    "fetching anything: no tool has run and no document, file or clock has been consulted. "
    "Select 'answerable' when a correct answer exists in general knowledge or arithmetic. "
    "Select 'not_answerable' for anything about the future, the owner's private history or "
    "records, subjective value judgements, or a current reading of the clock, calendar, mail or "
    "files. Returning only the typed choice judgment; authorization and execution are out of scope."
)

#: Variant B, written after variant A's result came back. Variant A scored the T class at p=0.00 —
#: every tool-answerable request called not-answerable — because it told Jev to judge without
#: tools. That is a true statement about the CALL and a false one about the TURN, which does have
#: tools. Variant B asks the question the turn actually needs answered: not "can you answer this
#: from memory" but "is a correct answer obtainable at all, from whatever the assistant can reach".
ANSWERABLE_INSTRUCTIONS_TOOLS = (
    "Is this request answerable? Select 'answerable' when a correct answer is obtainable at all: "
    "from general knowledge, from arithmetic, or by running one of the ordinary tools an "
    "assistant would normally use to look something up (the clock or calendar for the time or "
    "date, the mail or file tools for what is in the inbox, a search for a fact that changes). "
    "Select 'not_answerable' only when no source could ever settle it: the future, the owner's "
    "private history or records, and subjective value judgements. Returning only the typed choice "
    "judgment; authorization and execution are out of scope."
)

VARIANTS = {
    "no-tools": ANSWERABLE_INSTRUCTIONS,
    "with-tools": ANSWERABLE_INSTRUCTIONS_TOOLS,
}


def build_payload(text: str, model: str, variant: str = "no-tools") -> dict:
    """The production turn-assessment payload, plus the answerability question.

    Deliberately assembled from the same constants `assess_turn` uses so that the four shipped
    questions are byte-identical to the real call and only the fifth is new.
    """
    asked: dict[str, dict] = {
        "clarity": {
            "type": "choice",
            "instructions": (
                "Is the owner's request specific enough to act on without guessing? Select "
                "'clear' if the object, target or intent is stated. Select 'unclear' if a "
                "reasonable person would have to ask which one is meant."
            ),
            "criteria": {"clarity_clear": "clear", "clarity_unclear": "unclear"},
        },
        "urgency": {
            "type": "choice",
            "instructions": (
                "How soon does the owner need an answer? 'now' only when waiting would "
                "cost him something; 'soon' when it matters this turn; 'whenever' when it "
                "can be batched. This shapes framing and delivery priority only."
            ),
            "criteria": {f"urgency_{b}": b for b in URGENCY_BANDS},
        },
        "tone": {
            "type": "choice",
            "instructions": (
                "Choose the register for the reply. 'direct' for a clipped instruction, "
                "'steady' as the default, 'gentle' when he sounds worn down, 'curt' when he is "
                "plainly clipped. Never choose a register that invents feelings he did not "
                "express."
            ),
            "criteria": {f"tone_{t}": t for t in TONE_BANDS},
        },
        # THE QUESTION UNDER TEST. Its own instructions, its own criteria — the same treatment
        # the four shipped questions get, and the thing the first probe did not give it.
        "answerable": {
            "type": "choice",
            "instructions": VARIANTS[variant],
            "criteria": {
                "answerability_answerable": "answerable",
                "answerability_not_answerable": "not_answerable",
            },
        },
    }
    # The route question needs >= 2 candidates; with none, `assess_turn` omits it. Mirror that.
    return {"model": model, "state": {"question": " ".join((text or "").strip().split())[:800]},
            "questions": asked}


async def ask(service: JudgmentService, text: str, model: str, variant: str) -> dict:
    payload = build_payload(text, model, variant)
    t0 = time.perf_counter()
    status, body = await asyncio.wait_for(
        service._transport(payload, service._key, service._endpoint, service._timeout),
        timeout=max(0.1, service._timeout),
    )
    ms = (time.perf_counter() - t0) * 1000
    row: dict = {"text": text, "ms": round(ms), "http": status, "p_answerable": None,
                 "choice": None, "error": None}
    if status < 200 or status >= 300:
        row["error"] = f"http_{status}"
        return row
    try:
        answer = (body.get("answers") or {})["answerable"]
        choice = str(answer["choice"])
        probs = answer.get("probabilities") or {}
        row["choice"] = choice
        if choice in ("answerability_answerable", "answerability_not_answerable") and choice in probs:
            p = float(probs[choice])
            # Read the mass on the POSITIVE option: for a not_answerable pick that is 1 - p.
            row["p_answerable"] = p if choice == "answerability_answerable" else 1.0 - p
        # The raw shape matters: a model that returns only the winner with no distribution is a
        # different instrument from one that returns calibrated masses, and the report says which.
        row["probs_raw"] = {str(k): round(float(v), 3) for k, v in probs.items()} if isinstance(
            probs, dict) else None
    except (KeyError, TypeError, ValueError) as exc:
        row["error"] = type(exc).__name__
    return row


def _stats(rows: list[dict]) -> tuple[float, float]:
    ps = [r["p_answerable"] for r in rows if r["p_answerable"] is not None]
    return (statistics.mean(ps) if ps else float("nan"),
            statistics.median(ps) if ps else float("nan"))


async def run(model: str, service: JudgmentService, variant: str) -> dict:
    items: list[dict] = []
    for topic, k_text, k_cls, u_text in PAIRS:
        for text, cls in ((k_text, k_cls), (u_text, "U")):
            row = await ask(service, text, model, variant)
            row.update({"topic": topic, "cls": cls})
            items.append(row)
            p = row["p_answerable"]
            mark = "?" if p is None else f"p={p:.2f}"
            print(f"  {cls} {mark:>10} {row['ms']:>6}ms  {text[:50]}")
    return {"model": model, "variant": variant, "items": items}


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=None,
                    help="model to probe; defaults to the configured one")
    ap.add_argument("--variant", default="no-tools", choices=sorted(VARIANTS),
                    help="how the answerability question is worded")
    args = ap.parse_args()

    service = JudgmentService()
    if not service._enabled or not service._key:
        print("Jev is disabled or has no key — nothing to probe.")
        return 2
    model = args.model or service._model
    print(f"answerable probe v2 — real turn-assessment payload, model={model}, "
          f"variant={args.variant}\n")
    print(f"route instruction reference: {ROUTE_INSTRUCTIONS['tools'][:48]}...\n")

    result = await run(model, service, args.variant)
    items = result["items"]
    by = {c: [r for r in items if r["cls"] == c] for c in ("K", "T", "U")}

    print("\n=== p(answerable) by class ===")
    for cls in ("K", "T", "U"):
        mean, median = _stats(by[cls])
        n = len([r for r in by[cls] if r["p_answerable"] is not None])
        print(f"  {cls}  n={n:2}  mean={mean:.2f}  median={median:.2f}")

    k_mean, _ = _stats(by["K"])
    u_mean, _ = _stats(by["U"])
    t_mean, _ = _stats(by["T"])
    gap = k_mean - u_mean

    scored = [r for r in items if r["p_answerable"] is not None and r["cls"] in ("K", "U")]
    errors = sum(1 for r in scored if r["p_answerable"] >= 0.5 and r["cls"] == "U") + \
        sum(1 for r in scored if r["p_answerable"] < 0.5 and r["cls"] == "K")
    acc = 1 - errors / len(scored) if scored else float("nan")

    print("\n=== the control: does each TOPIC separate? ===")
    print("  (the first probe could not answer this — its two sets were different topics)")
    for topic, k_text, _kc, u_text in PAIRS:
        kp = next((r["p_answerable"] for r in items
                   if r["topic"] == topic and r["cls"] in ("K", "T")), None)
        up = next((r["p_answerable"] for r in items if r["topic"] == topic and r["cls"] == "U"), None)
        if kp is None or up is None:
            print(f"  {topic:16} incomplete")
        else:
            print(f"  {topic:16} K={kp:.2f}  U={up:.2f}  gap={kp - up:+.2f}")

    print("\n=== verdict ===")
    print(f"  K-vs-U gap      : {gap:+.2f}   (the signal §01.J1 asked about)")
    print(f"  K-vs-U accuracy : {acc:.0%} at p=0.5   ({errors}/{len(scored)} misclassified)")
    print(f"  T class mean    : {t_mean:.2f}  — tool-answerable, judged with NO tools in context")

    separates = gap > 0.4 and acc > 0.75
    if not separates:
        verdict = ("WEAK — no clean K/U separation. An `answerable` verdict would be a number that "
                   "does not track the thing it names.")
    elif t_mean < 0.5:
        verdict = (f"SEPARATES on K/U (gap {gap:+.2f}, {acc:.0%}) BUT MISDEPLOYS — the T class is "
                   f"called not-answerable at p={t_mean:.2f}. A verdict used as-is would suppress "
                   f"tool use on exactly the turns that need it.")
    else:
        verdict = (f"SEPARATES (gap {gap:+.2f}, {acc:.0%}) and does not misdeploy (T mean "
                   f"{t_mean:.2f}). The lever is real; the first probe's +0.06 was the harness.")
    print(f"\n  VERDICT: {verdict}")

    out = Path(f"logs/jev-answerable-probe-v2-{args.variant}-{model}.json")
    out.write_text(json.dumps({
        "model": model, "variant": args.variant, "items": items, "gap_ku": gap,
        "accuracy_ku": acc, "t_mean": t_mean, "verdict": verdict,
        "note": "topic-matched pairs; read logs/jev-answerable-probe.json for the first, "
                "untrusted attempt and why it was not believed",
    }, indent=2), encoding="utf-8")
    print(f"\n  wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))