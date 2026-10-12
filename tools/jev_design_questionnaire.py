"""Twenty questions for Jev about how it should be wired into a real-life assistant.

Asked on 2026-07-11 at the owner's request, with the explicit instruction that **nothing which
already exists carries weight**: no sunk cost, no deference to D-92/D-72, no "keep it because it
is there". Every option is a design position, and the incumbent is one of the options rather than
the default.

The context handed to Jev is what was MEASURED from the running system, not what the charter
believes:

  * turn path: prepare -> decide -> route -> LLM+tools -> completion pass -> trace row
  * 164 tools registered, 59 advertised per turn; 27 lazy groups loaded on demand
  * Jev is called from exactly two sites: an explicit two-option decision gate (zero tools), and
    one per-turn assessment (route / clarity / urgency / tone, plus optional group arbitration)
  * 8,729 recorded calls: 37% decided, p50 706 ms, p95 1,635 ms, against a 400 ms cap;
    5,437 failures are literally `timeout_0.4s`
  * on timeout / outage / missing key every deterministic candidate is kept, and the turn proceeds
  * calibration is measured at 78.2 and is the weakest category: unknowable questions get flat
    answers, and prompting has been measured exhausted (0/12 as shipped, 0/12 restated)

Run:  TYPESAFE_API_KEY=... python tools/jev_design_questionnaire.py
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from mushegh.brain.judgment import DecisionOption, DecisionRequest, JudgmentService  # noqa: E402

CONTEXT = """\
You are advising the design of a voice-first personal assistant brain. It runs as two processes: a
laptop "edge" holding the audio path (wake word, STT, TTS, barge-in) and a 24/7 "brain" on a VPS
holding memory, tools and reasoning. Current construction, measured:

TURN PATH: user speech -> wake/STT -> brain prepares the turn -> intent is classified into one of
chat/lookup/act/multi/ambiguous -> the tool surface is narrowed (59 of 164 tools by default, 27 lazy
groups on demand) -> an LLM runs a tool-calling loop -> a completion pass finishes compound turns ->
a trace row is written. Every turn produces a trace row.

YOUR CURRENT USE: you are called from two places only. (1) An explicit decision gate, used when the
owner states two clear alternatives; on that turn the assistant gets ZERO tools and merely speaks
your choice. (2) One call per turn returning route, clarity, urgency and tone, plus optional
arbitration between competing tool groups. That is the whole integration.

YOUR MEASURED BEHAVIOUR: 8,729 calls logged. 37% decided, 63% unavailable. Median latency 706 ms,
p95 1,635 ms, against a 400 ms budget; 5,437 failures are timeouts at that budget. When you time
out, are unavailable, or the key is missing, every deterministic candidate is kept and the turn
proceeds without you. Historically you failed 99% of the time.

THE WEAKEST SUBSYSTEM: calibration, scored 78.2. Given a question with no knowable answer
(a price next year, whether a job application will succeed, an opinion), the assistant answers
flatly and confidently. Prompt engineering has been measured exhausted - restating the rule changes
nothing (0/12 either way).

CONSTRAINTS THAT ARE REAL: one request must stay cheap and fast enough to sit inside a voice turn;
no owner data may leave the host; a wrong decision is worse than no decision, because the owner acts
on what he is told.

There are no existing commitments. Recommend the best design, not the cheapest migration.
"""

Q: list[tuple[str, str, tuple[tuple[str, str], ...]]] = [
    ("position",
     "Where should you sit in the turn?",
     (("early", "At the very start of every turn, before any routing - you are the primary "
                "decision layer and the router only executes your plan"),
      ("selective", "On the turns that are genuinely ambiguous or high-stakes; elsewhere the "
                    "deterministic router decides alone"),
      ("late", "Only after tools have run, to choose what to say and whether to trust the result"),
      ("both", "Early for routing and late for the final answer check, accepting two calls"))),
    ("frequency",
     "How many times per turn should you be consulted?",
     (("one", "Exactly one call per turn, whatever the turn looks like"),
      ("zero_or_one", "Only when the deterministic layer cannot decide, so most turns cost nothing"),
      ("budgeted", "Up to two calls, the second only when the first produced a low-confidence pick"),
      ("continuous", "Re-consulted after each tool result, so the loop stays steered by you"))),
    ("surface",
     "What should you see when choosing tools?",
     (("names", "Only tool names - the cheapest payload and the smallest privacy surface"),
      ("names_and_one_liners", "Names plus one-line descriptions, so you can pick on meaning"),
      ("signatures", "Names plus full argument schemas, so you judge what is actually callable"),
      ("signatures_and_results", "Everything including what past turns' tools returned"))),
    ("arbitration",
     "Should you arbitrate between competing tool groups on every turn?",
     (("always", "Every turn, so the surface is always your pick"),
      ("only_ties", "Only when the deterministic router ranks two groups equally"),
      ("never", "Never - you advise, the router arbitrates"),
      ("compound_only", "Only on multi-intent turns, where the current design skips you entirely"))),
    ("budget",
     "What latency budget should you be given?",
     (("tight", "Stay under 400 ms - a voice turn cannot wait longer"),
      ("moderate", "Up to 900 ms, which is where your median already sits"),
      ("asynchronous", "No hard cap; run concurrently with the LLM's first token and join the result"),
      ("two_tier", "A fast tier under 300 ms, escalating to a slower tier past 700 ms"))),
    ("failure",
     "What should happen when you are unavailable?",
     (("fail_open", "The deterministic layer decides alone and the turn proceeds"),
      ("fail_clarify", "The deterministic layer decides, but the owner is told you were unavailable"),
      ("fail_ask", "Ask the owner rather than guessing, accepting the friction"),
      ("fail_queue", "Queue the turn and answer once you are back"))),
    ("fields",
     "Which signals should you return?",
     (("current", "Route, clarity, urgency and tone, as today"),
      ("minimal", "One pick plus a confidence - less to go wrong, less to gain"),
      ("plus_answerable", "The current four, plus a verdict on whether the question is answerable "
                          "at all"),
      ("plus_plan", "A full multi-step plan the router then executes"))),
    ("context",
     "What owner context may be injected into your question?",
     (("none", "Nothing - the utterance alone, which is what is sent today"),
      ("session", "The current session summary and the active modes"),
      ("memory", "Retrieved memories relevant to the turn"),
      ("full", "Session, memories, preferences and recent tool results"))),
    ("privacy",
     "Given that owner data must not leave the host, how should context be handled?",
     (("none", "Send no context, so nothing can leak"),
      ("hash", "Send the utterance plus non-reversible hashes of preferences"),
      ("abstract", "Send only an abstract profile - traits and tendencies, no specifics"),
      ("local", "Run the decision locally and only use you for the hard cases"))),
    ("answerable",
     "Should you decide whether a question is answerable before the model answers it?",
     (("yes", "Yes - return a verdict so the turn can hedge before generating rather than after"),
      ("no", "No - leave honesty to the existing post-hoc degrade"),
      ("only_tools", "Only when the question looks like a lookup, to decide which tool to use"),
      ("only_unsafe", "Only for questions where a wrong answer could be acted on"))),
    ("multi_intent",
     "Should you decompose a compound request into its parts?",
     (("yes", "Yes - plan the clauses yourself and hand the router an ordered list"),
      ("no", "No - the clause router already does this deterministically"),
      ("verify", "Let the router propose and you verify or reorder"),
      ("only_long", "Only when there are more than two clauses"))),
    ("clarify",
     "When should the owner be asked a clarifying question?",
     (("you_decide", "You decide, on any turn you judge ambiguous"),
      ("router_decides", "The router decides; you are not consulted"),
      ("confidence", "Only when your own confidence is below a threshold"),
      ("never_guess", "Never - proceed on the most likely reading and state the assumption"))),
    ("refusals",
     "Should you own the decision to refuse or escalate an action?",
     (("yes", "Yes - refusals and confirmations are decisions like any other"),
      ("no", "No - the deterministic confirm tiers already own that"),
      ("advisory", "Advisory only - you may recommend a refusal, code decides"),
      ("only_irreversible", "Only for irreversible or outward-facing actions"))),
    ("memory",
     "Should you decide what is worth remembering?",
     (("no", "No - memory has its own salience system"),
      ("yes", "Yes - you judge whether a turn contains a durable fact"),
      ("importance_only", "Only whether something is important enough to keep, not what"),
      ("deletion", "Also whether something previously stored should be deleted"))),
    ("proactive",
     "Should you decide when the assistant speaks unprompted?",
     (("no", "No - a daily budget and quiet hours already govern this"),
      ("yes", "Yes - you judge whether an unprompted interruption is worth it"),
      ("rate_only", "Only the rate, leaving the content to the scheduler"),
      ("never", "Never - unprompted speech should stay off entirely"))),
    ("authority",
     "Should your output be binding or advisory?",
     (("binding", "Binding - the router executes your pick"),
      ("advisory", "Advisory - the router may override you when it is confident"),
      ("abstain", "You may abstain, and abstaining keeps every candidate"),
      ("tiered", "Binding on some surfaces, advisory on others"))),
    ("trivial",
     "Should cheap deterministic turns skip you entirely?",
     (("yes", "Yes - greetings, acknowledgements and reflex reads should never cost a call"),
      ("no", "No - every turn goes through you so behaviour stays uniform"),
      ("cache", "Cache your answer per utterance shape instead of skipping"),
      ("only_after_n", "Only after the deterministic layer has been uncertain N times running"))),
    ("degrade",
     "How should your absence be made visible?",
     (("silent", "Silently - the owner should not care which layer answered"),
      ("log", "Log it and surface it in diagnostics only"),
      ("tell_owner", "Tell the owner when a turn was decided without you"),
      ("periodic", "Tell the owner in a weekly summary rather than per turn"))),
    ("evaluation",
     "How should your contribution be judged?",
     (("latency", "By latency - how often you return inside budget"),
      ("tool_choice", "By tool-choice accuracy against a labelled set"),
      ("outcome", "By outcome - did turns the owner acted on correctly"),
      ("abstention", "By calibration of your own confidence against outcomes"))),
    ("model",
     "Which model should serve the decision call?",
     (("same", "The same model that writes the answer"),
      ("small", "A small, fast dedicated model for routing and arbitration"),
      ("strongest", "The strongest available model, accepting the latency"),
      ("two_models", "A fast model for routine turns, the strongest only for hard ones"))),
    ("shape",
     "Looking across all of this, what should the integration look like?",
     (("advisory_layer", "A narrow advisory layer over a strong deterministic router"),
      ("primary_layer", "The primary layer - you decide routing, ambiguity and honesty, the "
                        "router executes"),
      ("full_planner", "A planner that produces the whole turn plan, which the runtime executes"),
      ("ensemble", "You plus the router, each arbitrating where the other is weak"))),
]


async def ask(service: JudgmentService, key: str, prompt: str, options: tuple[tuple[str, str], ...]) -> dict:
    request = DecisionRequest(
        question=f"{CONTEXT}\n\nQUESTION: {prompt}",
        options=tuple(DecisionOption(oid, text) for oid, text in options),
        kind="brain_architecture_advice",
    )
    t0 = time.perf_counter()
    verdict = await service.judge(request, correlation_id="design-q")
    ms = (time.perf_counter() - t0) * 1000
    return {
        "key": key,
        "question": prompt,
        "picked": getattr(verdict, "selected_id", None),
        "selected_text": getattr(verdict, "selected_text", None),
        "probability": getattr(verdict, "probability", None),
        "confidence": getattr(verdict, "confidence", None),
        "outcome": verdict.outcome,
        "ms": round(ms),
        "options": {oid: text for oid, text in options},
    }


async def main() -> int:
    key = os.environ.get("TYPESAFE_API_KEY", "").strip()
    if not key:
        print("TYPESAFE_API_KEY is not set.")
        return 2
    service = JudgmentService(key=key, timeout=30.0)
    if not service._enabled:
        print("Jev is disabled in settings; set MUSHEGH_JEV_ENABLED=true.")
        return 2

    results = []
    for key_, prompt, options in Q:
        row = await ask(service, key_, prompt, options)
        results.append(row)
        prob = row["probability"]
        print(f"  {row['outcome']:11} {row['ms']:>6}ms  {key_:16} -> {row['picked']} "
              f"(p={prob:.2f})" if prob is not None else
              f"  {row['outcome']:11} {row['ms']:>6}ms  {key_:16} -> {row['picked']}")

    out = Path("logs/jev-design-questionnaire.json")
    out.write_text(json.dumps(results, indent=2), encoding="utf-8")
    decided = [r for r in results if r["outcome"] == "decided"]
    print(f"\n=== {len(decided)}/{len(results)} answered ===")
    for r in results:
        if r["outcome"] == "decided":
            print(f"  {r['key']:16} {r['picked']:16} p={r['probability']:.2f}")
    print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))