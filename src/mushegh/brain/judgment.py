"""Typed contextual decisions through TypeSafe Jev (14.R5).

Jev is the decision layer for explicit owner-supplied options. Generative LLMs may verbalize a
successful verdict, but they never choose the option and are not a fallback decision-maker.

This module deliberately does *not* authorize actions. Emergency handling, privacy, confirmation,
governor budgets and tool argument checks remain deterministic code. The first runtime seam is also
intentionally narrow: no model invents candidate options. A request reaches Jev only when the owner
plainly supplies two alternatives in a decision-shaped utterance.

Outbound minimisation: the current question and its explicit options only; no conversation history,
memory, tool output, secret or biometric material. Durable provenance is smaller still: IDs,
selection, confidence, model, timing and outcome, never raw question/option prose.
"""

from __future__ import annotations

import asyncio
import json
import math
import re
import threading
import time
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Awaitable, Callable, Literal

from loguru import logger

from mushegh.config import settings
from mushegh.shared.paths import state_dir

Outcome = Literal["decided", "disabled", "unavailable", "invalid"]
Transport = Callable[[dict[str, Any], str, str, float], Awaitable[tuple[int, dict[str, Any]]]]

_MAX_QUESTION = 800
_MAX_OPTION = 280
_CLEAN_EDGE = " \t\r\n.,;:!?\"'"
#: Arbitration budget, and it is much smaller than the service timeout on purpose. This call
#: sits on the voice hot path, where a laptop turn is budgeted under 300ms (D-35): an
#: arbitration that arrives after the owner has finished speaking is worse than no arbitration
#: at all, because the owner has already moved on. The explicit two-option path keeps the full
#: service timeout, because there the fallback is *ask the owner* — a real answer. Here the
#: fallback is the deterministic trigger match, which is also a real answer, and a fast one.
ARBITRATION_TIMEOUT_S = 0.4
#: The labels the turn assessment may choose from. Code declares them, Jev picks one — a model
#: that answers with anything else is ignored rather than trusted, because "unclear" that means
#: something else is the whole failure this is meant to catch.
URGENCY_BANDS = ("now", "soon", "whenever")
TONE_BANDS = ("direct", "steady", "gentle", "curt")
CLARITY_BANDS = ("clear", "unclear")
#: 01.J13 — Jev's `answerable` verdict (its own request, p=0.77). Additive: a fifth question inside
#: the call 01.R7 already makes, so it costs no extra round trip and no extra budget.
ANSWERABLE_BANDS = ("answerable", "not_answerable")
#: The wording is load-bearing and was measured, not chosen. `tools/probe_jev_answerable_v2.py`,
#: ten topic-matched pairs so topic and answerability cannot be confused:
#:
#:     "judge only from what can be recalled or computed without fetching anything"   T=0.00
#:     "answerable at all, including by one of the ordinary tools"                  T=0.95
#:
#: The first wording is a true statement about the CALL — no tool has run, so nothing can read a
#: clock — and a false one about the TURN, which does have tools. Shipped as written it marks
#: "what time is it" unanswerable and would suppress the tool call on precisely the turns that
#: need one, at 100% accuracy, which is how it would have looked like a win in a summary line.
#: Keep "ordinary tools"; dropping them reintroduces the bug.
ANSWERABLE_INSTRUCTIONS = (
    "Is this request answerable? Select 'answerable' when a correct answer is obtainable at all: "
    "from general knowledge, from arithmetic, or by running one of the ordinary tools an "
    "assistant would normally use to look something up (the clock or calendar for the time or "
    "date, the mail or file tools for what is in the inbox, a search for a fact that changes). "
    "Select 'not_answerable' only when no source could ever settle it: the future, the owner's "
    "private history or records, and subjective value judgements. Returning only the typed choice "
    "judgment; authorization and execution are out of scope."
)
#: Below this, a route pick is treated as a coin flip and the turn asks instead of guessing.
#: Deliberately conservative: a wrong tool call costs an action the owner did not ask for, and
#: a clarifying question costs one round trip.
MIN_ROUTE_PROBABILITY = 0.6
#: Route options are positional (`group_1`, `group_2`); everything else is label-shaped.
#: The route question's wording, per thing being chosen between. Declared here rather than passed
#: in by callers: the instructions are part of what the model is allowed to decide, and a caller
#: that could write its own would be able to widen the question without touching this file. M45
#: added the second entry; a third is an edit here, which is the point.
ROUTE_INSTRUCTIONS = {
    "tools": (
        "Select the tool group that best answers the owner's request. Return only "
        "the typed choice judgment; authorization and execution are out of scope."
    ),
    "executor": (
        "Each option is a command-line coding or task agent already installed and already "
        "permitted to receive this work. Select the one best suited to the task described. "
        "Return only the typed choice judgment; authorization, permissions and execution are "
        "out of scope, and the work is bounded elsewhere regardless of which you pick."
    ),
}

_ROUTE_CHOICE = re.compile(r"^group_(\d+)$")

#: Entropy bands over the normalised Shannon entropy H_n = H(P)/log2(K) of the route
#: distribution. Scale-free, which a fixed probability floor is not: 0.60 means "quite sure"
#: across four options and near-total uncertainty across two, so one threshold silently judges
#: two different situations by the same number.
#:
#:   FAST      the distribution has an opinion. Narrow to it and act.
#:   MARGINAL  the distribution has an opinion it will not stand behind. Ask the owner.
#:   AMBIGUOUS the distribution has no opinion. Give the model the full surface and let
#:              deliberation — not a coin flip — decide.
ENTROPY_FAST_MAX = 0.25
ENTROPY_MARGINAL_MAX = 0.60
#: Routing gets a looser bar, and the difference is not arbitrary. Narrowing the tool surface
#: is a LOW-stakes decision: the groups Jev did not pick are not lost, they are re-armed by
#: their own triggers next turn, and the model keeps the core belt either way. A safety
#: decision — is this the owner, may this lock open — has no such floor, and gets the tight
#: band above. Using one threshold for both would either make routing never fire or make
#: safety permissive, and the two failure modes are not symmetric.
ENTROPY_ROUTE_FAST_MAX = 0.60


def normalized_entropy(probabilities: dict[str, float]) -> float:
    """H_n of a distribution over K options: 0.0 is certain, 1.0 is uniform.

    Local arithmetic, no service, and it is the reason a two-way near-tie and a four-way
    near-tie can be told apart. Returns 1.0 for an empty or single-option distribution that
    carries no information, which routes it to deliberation rather than to a guess.
    """
    usable = [p for p in probabilities.values() if p > 0.0]
    if len(usable) < 2:
        return 1.0
    total = sum(usable)
    if total <= 0:
        return 1.0
    entropy = -sum((p / total) * math.log2(p / total) for p in usable)
    return entropy / math.log2(len(usable))


def entropy_zone(h_norm: float, *, fast_max: float = ENTROPY_FAST_MAX) -> str:
    """Which of the three bands a distribution falls in. `fast_max` is the caller's risk bar."""
    if h_norm < fast_max:
        return "fast"
    return "marginal" if h_norm <= ENTROPY_MARGINAL_MAX else "ambiguous"


@dataclass(frozen=True)
class DecisionOption:
    id: str
    text: str


@dataclass(frozen=True)
class DecisionRequest:
    question: str
    options: tuple[DecisionOption, ...]
    kind: str = "explicit_options"


@dataclass(frozen=True)
class DecisionVerdict:
    request_id: str
    correlation_id: str
    kind: str
    option_ids: tuple[str, ...]
    selected_id: str | None
    selected_text: str | None
    probability: float | None
    confidence: float | None
    model: str
    latency_ms: float
    outcome: Outcome
    fallback: str
    error: str = ""

    @property
    def decided(self) -> bool:
        return self.outcome == "decided" and self.selected_id is not None


@dataclass(frozen=True)
class TurnSignals:
    """What one bounded Jev call produced for one turn. Every field may be None.

    All of them are advisory. None of them can widen the tool surface, raise the
    interruption budget, or pierce quiet hours — the safety rules stay in code, and the
    owner's own judgement stays the owner's.
    """

    candidates: tuple[str, ...]
    group: str | None
    urgency: str | None
    tone: str | None
    clarity: str | None
    outcome: Outcome
    latency_ms: float
    probability: float | None = None
    model: str = ""
    #: The full distribution Jev returned for the route question, not just the winner. Kept
    #: because a probability without its competitors says nothing: 0.94 is decisive beside one
    #: rival and meaningless beside three.
    distribution: tuple[tuple[str, float], ...] = ()
    #: 01.J13 — `answerable` / `not_answerable` / None (not asked, or no usable answer). Advisory
    #: in exactly the way the other four are: it may shape how the answer is GENERATED and may
    #: never touch the tool surface, the interruption budget or quiet hours.
    answerable: str | None = None

    @property
    def entropy(self) -> float:
        """Normalised Shannon entropy of the route distribution, or 1.0 when there is none."""
        return normalized_entropy(dict(self.distribution)) if self.distribution else 1.0

    @property
    def zone(self) -> str:
        """`fast`, `marginal` or `ambiguous` — see `entropy_zone`, at the routing risk bar."""
        return entropy_zone(self.entropy, fast_max=ENTROPY_ROUTE_FAST_MAX)

    @property
    def routed(self) -> bool:
        """True only when the distribution has an opinion worth acting on.

        This is a claim about the *distribution*, not about the top label: 0.94 of four options
        is fast, 0.94 of two is still a near-tie, and a fixed threshold cannot tell those apart.
        """
        return (self.outcome == "decided" and self.group is not None
                and self.zone == "fast")

    @property
    def too_low_confidence(self) -> bool:
        """Jev named a group but would not stand behind it — the marginal band."""
        return (self.outcome == "decided" and self.group is not None
                and self.zone == "marginal")

    @property
    def needs_clarification(self) -> bool:
        return self.clarity == "unclear"

    @property
    def needs_hedge(self) -> bool:
        """True only on a DECIDED `not_answerable`.

        The distinction is the whole safety of this signal. An assessment that failed, timed out
        or was never asked leaves `answerable` as None and this property False — a hedge note on
        a turn whose assessment failed would be hedging for no reason, on a clear turn, which is
        the one thing §01.R7 forbids. Fail-closed toward saying nothing.
        """
        return self.outcome == "decided" and self.answerable == "not_answerable"


@dataclass(frozen=True)
class Arbitration:
    """Which candidate the Jev layer picked, or None to keep every candidate.

    Distinct from :class:`DecisionVerdict` on purpose. A verdict is the owner being asked a
    question; an arbitration is the system resolving its own ambiguity, where the correct
    failure mode is silence — keep the deterministic candidates and carry on. The two have
    opposite fallbacks, and conflating them is how "the model was unsure" turns into "the
    model decided".
    """

    candidates: tuple[str, ...]
    winner: str | None
    outcome: Outcome
    latency_ms: float
    probability: float | None = None
    model: str = ""

    @property
    def arbitrated(self) -> bool:
        return self.outcome == "decided" and self.winner is not None


def _option(text: str) -> str:
    return " ".join(text.strip(_CLEAN_EDGE).split())[:_MAX_OPTION]


def explicit_decision(text: str) -> DecisionRequest | None:
    """Extract exactly two explicit alternatives from a plainly decision-shaped utterance.

    The conservative syntax is a feature: "open Chrome or Firefox" is an ambiguous command, not
    permission for an external service to choose. Broader option generation belongs to a later,
    separately gated RAISE batch.
    """
    raw = " ".join((text or "").strip().split())
    if not raw or len(raw) > _MAX_QUESTION:
        return None

    patterns = (
        r"\bchoose\s+(?:between|from)\s+(.+?)\s+(?:or|versus|vs\.?)\s+(.+?)[?!.]*$",
        r"\bshould\s+(?:i|we)\s+(.+?)\s+or\s+(.+?)[?!.]*$",
        r"\bwhich\s+(?:one|option)\s*[:,\-]?\s*(.+?)\s+(?:or|versus|vs\.?)\s+(.+?)[?!.]*$",
    )
    match = next((m for p in patterns if (m := re.search(p, raw, re.IGNORECASE))), None)
    if match is None:
        return None
    options = tuple(_option(part) for part in match.groups())
    if len(options) != 2 or any(not item or len(item) < 2 for item in options):
        return None
    if options[0].casefold() == options[1].casefold():
        return None
    return DecisionRequest(
        question=raw[:_MAX_QUESTION],
        options=tuple(DecisionOption(f"option_{i + 1}", item) for i, item in enumerate(options)),
    )


async def _http_transport(
    payload: dict[str, Any], key: str, endpoint: str, timeout: float,
) -> tuple[int, dict[str, Any]]:
    # Import lazily to preserve the small base/edge import surface and avoid a tools-package cycle.
    # The shared transport owns User-Agent, status handling, and the declared per-host policy.
    from mushegh.brain.tools.base import http_post

    response = await http_post(
        endpoint,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json=payload,
        timeout=timeout,
    )
    try:
        body = response.json()
    except ValueError:
        body = {}
    return response.status_code, body if isinstance(body, dict) else {}


class JudgmentService:
    """One typed, fail-closed Jev client with compact local provenance."""

    def __init__(
        self,
        *,
        transport: Transport | None = None,
        key: str | None = None,
        enabled: bool | None = None,
        model: str | None = None,
        endpoint: str | None = None,
        timeout: float | None = None,
        log_path: str | Path | None = None,
    ) -> None:
        configured = settings.typesafe_api_key.get_secret_value() if settings.typesafe_api_key else ""
        self._key = configured if key is None else key
        self._enabled = settings.jev_enabled if enabled is None else enabled
        self._model = model or settings.jev_model
        self._endpoint = endpoint or settings.jev_endpoint
        self._timeout = max(0.1, timeout or settings.jev_timeout_seconds)
        configured_path = settings.jev_judgment_log_path
        self._path = Path(log_path or configured_path or (state_dir() / "jev_judgments.jsonl"))
        self._transport = transport or _http_transport
        self._lock = threading.Lock()
        self._calls = 0
        self._errors = 0
        self._latest: dict[str, Any] = {}

    async def consider(self, text: str, *, correlation_id: str = "") -> DecisionVerdict | None:
        request = explicit_decision(text)
        if request is None:
            return None
        return await self.judge(request, correlation_id=correlation_id)

    async def arbitrate(
        self,
        text: str,
        groups: Sequence[str],
        *,
        correlation_id: str = "",
        timeout_s: float | None = None,
        route_purpose: str = "tools",
    ) -> Arbitration | None:
        """Pick one of several deterministic candidates, or return None to keep them all.

        The candidates are supplied by the caller and must have come from code — today, the
        lazy-group trigger match. This method never *invents* a candidate, never receives one
        from a model, and never returns a candidate that was not offered. That is the whole
        reason this is safe to put on the hot path: Jev chooses within a boundary the
        deterministic router drew, so a model cannot widen what the system is willing to do by
        deciding that a wider thing should have been on offer.

        Fewer than two candidates is not a decision, so it costs no call at all — which is why
        the overwhelming majority of turns pay nothing for this.

        Thin wrapper over :meth:`assess_turn` for callers that only want the route answer.
        """
        signals = await self.assess_turn(
            text, groups=groups, arbitrate=True, correlation_id=correlation_id,
            timeout_s=timeout_s, ask_clarity=False, route_purpose=route_purpose,
        )
        if signals is None:
            # Fewer than two candidates: there was no decision to make, so there is nothing to
            # report. This is the only case that returns None — a FAILED attempt returns an
            # Arbitration with no winner, because "we tried and could not" and "there was
            # nothing to try" are different facts and the caller may want to record the first.
            return None
        return Arbitration(signals.candidates, signals.group if signals.routed else None,
                           signals.outcome, signals.latency_ms, probability=signals.probability,
                           model=signals.model)

    async def assess_turn(
        self,
        text: str,
        *,
        groups: Sequence[str] = (),
        arbitrate: bool = True,
        ask_clarity: bool = True,
        ask_answerable: bool = False,
        correlation_id: str = "",
        timeout_s: float | None = None,
        route_purpose: str = "tools",
    ) -> "TurnSignals | None":
        """One bounded call carrying every question the turn needs.

        Route, urgency, tone and clarity are asked **together in a single request**. That is
        the efficiency claim, and it is also the correctness one: a turn that made three
        sequential cloud calls would spend three times the budget and could disagree with
        itself, because the third call would see a different moment from the first.

        Every question here is advisory in the same way, and with the same limit as the route
        question: Jev picks from labels the code declared, and nothing it returns may widen
        what the system is willing to do. In particular **urgency never touches the
        interruption budget or quiet hours** (D-29, D-32) — it shapes how an answer is framed
        and how a delivery is prioritised inside the budget that already exists. Only
        life-safety pierces it, and that stays deterministic code (D-18).

        Returns None only when there is nothing worth asking: no candidates to route between
        and no clarity question requested. A failure returns a `TurnSignals` with everything
        unset, which the caller reads as "carry on exactly as before".
        """
        candidates = tuple(dict.fromkeys(g for g in groups if g))
        route = tuple(candidates) if (arbitrate and len(candidates) >= 2) else ()
        if not route and not ask_clarity and not ask_answerable:
            return None

        started = time.perf_counter()
        cap = max(0.05, timeout_s or settings.jev_arbitration_timeout_seconds
                  or ARBITRATION_TIMEOUT_S)
        if not self._enabled or not self._key:
            return TurnSignals(candidates, None, None, None, None,
                               "disabled" if not self._enabled else "unavailable", 0.0,
                               model=self._model)

        question = " ".join((text or "").strip().split())[:_MAX_QUESTION]
        asked: dict[str, dict[str, Any]] = {}
        if route:
            asked["route"] = {
                "type": "choice",
                # An unknown purpose falls back to the tool wording rather than raising: a typo in
                # a caller must not take the turn down, and the tool wording is the conservative
                # one. The gate asserts the key set, so a typo is caught there instead.
                "instructions": ROUTE_INSTRUCTIONS.get(route_purpose,
                                                       ROUTE_INSTRUCTIONS["tools"]),
                "criteria": {f"group_{i + 1}": name for i, name in enumerate(route)},
            }
        if ask_clarity:
            asked["clarity"] = {
                "type": "choice",
                "instructions": (
                    "Is the owner's request specific enough to act on without guessing? Select "
                    "'clear' if the object, target or intent is stated. Select 'unclear' if a "
                    "reasonable person would have to ask which one is meant."
                ),
                "criteria": {"clarity_clear": "clear", "clarity_unclear": "unclear"},
            }
            asked["urgency"] = {
                "type": "choice",
                "instructions": (
                    "How soon does the owner need an answer? 'now' only when waiting would "
                    "cost him something; 'soon' when it matters this turn; 'whenever' when it "
                    "can be batched. This shapes framing and delivery priority only."
                ),
                "criteria": {f"urgency_{b}": b for b in URGENCY_BANDS},
            }
            asked["tone"] = {
                "type": "choice",
                "instructions": (
                    "Choose the register for the reply. 'direct' for a clipped instruction, "
                    "'steady' as the default, 'gentle' when he sounds worn down, 'curt' when he "
                    "is plainly clipped. Never choose a register that invents feelings he did "
                    "not express."
                ),
                "criteria": {f"tone_{t}": t for t in TONE_BANDS},
            }

        if ask_answerable:
            # 01.J13. Asked last and opt-in, so the four-question production payload is byte-for-
            # byte what it was before this existed — `test_jev_turn_assessment.py` pins that set.
            # It rides in the SAME round trip as the others; it is not a fifth call.
            asked["answerable"] = {
                "type": "choice",
                "instructions": ANSWERABLE_INSTRUCTIONS,
                "criteria": {f"answerability_{b}": b for b in ANSWERABLE_BANDS},
            }

        payload = {
            "model": self._model,
            "state": {"question": question},
            "questions": asked,
        }
        try:
            # The arbitration cap has to reach the HTTP client, not just wrap the await.
            # With only the service timeout passed down, `wait_for` cancelled an in-flight
            # request that did not stop promptly: the deadline was honoured logically while
            # the turn still paid the full wall clock (measured 2026-10-08: 957 ms median
            # against a 400 ms cap, 0 of 25 inside it). Passing `cap` makes the client give
            # up on its own at the same moment the deadline fires, so the documented budget
            # and the real cost finally agree.
            transport_timeout = min(self._timeout, cap)
            status, body = await asyncio.wait_for(
                self._transport(payload, self._key, self._endpoint, transport_timeout),
                timeout=cap,
            )
            if status < 200 or status >= 300:
                raise ValueError(f"http_{status}")
            answers = body.get("answers") or {}
            elapsed = round((time.perf_counter() - started) * 1000, 1)
            model = str(body.get("model") or self._model)
            return self._read_turn_signals(candidates, route, answers, elapsed, model,
                                           correlation_id, asked)
        except (asyncio.TimeoutError, TimeoutError):
            elapsed = round((time.perf_counter() - started) * 1000, 1)
            self._record_turn(candidates, route, asked, correlation_id, elapsed,
                              self._model, "unavailable", f"timeout_{cap:g}s")
            return TurnSignals(candidates, None, None, None, None, "unavailable", elapsed,
                               model=self._model)
        except Exception as exc:  # noqa: BLE001 — an outage is a normal outcome, not an error
            elapsed = round((time.perf_counter() - started) * 1000, 1)
            self._record_turn(candidates, route, asked, correlation_id, elapsed,
                              self._model, "unavailable", type(exc).__name__)
            return TurnSignals(candidates, None, None, None, None, "unavailable", elapsed,
                               model=self._model)

    def _read_turn_signals(
        self,
        candidates: tuple[str, ...],
        route: tuple[str, ...],
        answers: dict[str, Any],
        elapsed: float,
        model: str,
        correlation_id: str,
        asked: dict[str, Any] | None = None,
    ) -> "TurnSignals":
        """Parse each answer independently, so one bad question cannot void the others."""
        picked: dict[str, str] = {}
        probability: float | None = None
        distribution: list[tuple[str, float]] = []
        for name, answer in answers.items():
            if not isinstance(answer, dict):
                continue
            choice = str(answer.get("choice") or "")
            if name == "route":
                # Route options are indexed (`group_2`), not labelled, so the answer has to be
                # resolved back through the tuple we offered. A choice outside that range is not
                # a near miss — it is something the model invented, and it is dropped.
                match = _ROUTE_CHOICE.match(choice)
                if not match:
                    continue
                index = int(match.group(1)) - 1
                if not 0 <= index < len(route):
                    continue
                picked["group"] = route[index]
                probs = answer.get("probabilities") or {}
                if isinstance(probs, dict):
                    # Keep the WHOLE distribution, not just the winner. Entropy is a claim about
                    # the shape of the beliefs, so throwing away the losers would leave the gate
                    # judging a one-option distribution — which is maximum certainty, every time.
                    for position in range(1, len(route) + 1):
                        key = f"group_{position}"
                        try:
                            value = float(probs.get(key, 0.0))
                        except (TypeError, ValueError):
                            value = 0.0
                        distribution.append((route[position - 1], value))
                    if choice in probs:
                        try:
                            probability = float(probs[choice])
                        except (TypeError, ValueError):
                            probability = None
                continue
            label = choice.split("_", 1)[1] if "_" in choice else ""
            if name == "urgency" and label in URGENCY_BANDS:
                picked["urgency"] = label
            elif name == "tone" and label in TONE_BANDS:
                picked["tone"] = label
            elif name == "clarity" and label in CLARITY_BANDS:
                picked["clarity"] = label
            elif name == "answerable" and label in ANSWERABLE_BANDS:
                picked["answerable"] = label
        self._record_turn(candidates, route, asked, correlation_id, elapsed, model,
                          "decided" if picked else "invalid",
                          "" if picked else "no_usable_answer", picked=picked)
        return TurnSignals(
            candidates,
            picked.get("group"),
            picked.get("urgency"),
            picked.get("tone"),
            picked.get("clarity"),
            "decided" if picked else "invalid",
            elapsed,
            probability=probability,
            model=model,
            distribution=tuple(distribution),
            answerable=picked.get("answerable"),
        )

    def _record_turn(
        self,
        candidates: tuple[str, ...],
        route: tuple[str, ...],
        asked: dict[str, Any] | None,
        correlation_id: str,
        elapsed: float,
        model: str,
        outcome: str,
        error: str,
        picked: dict[str, str] | None = None,
    ) -> None:
        """One provenance row per turn assessment, whatever the outcome.

        The fields are IDs and labels only — never the utterance, the options as prose, or
        anything from the owner's side of the conversation. `asked` records which questions
        went out, because "nothing was asked" and "it was asked and failed" are different
        facts and only one of them is a problem.
        """
        self._record({
            "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "correlation_id": correlation_id,
            "request_id": uuid.uuid4().hex,
            "kind": "turn_assessment",
            "candidates": list(candidates),
            "routed_over": list(route),
            "asked": sorted(asked) if asked else [],
            "picked": picked or {},
            "probability": None,
            "confidence": None,
            "model": model,
            "latency_ms": elapsed,
            "outcome": outcome,
            "fallback": "deterministic" if outcome != "decided" else "none",
            "error": error[:80],
        })

    async def judge(
        self, request: DecisionRequest, *, correlation_id: str = "",
    ) -> DecisionVerdict:
        request_id = uuid.uuid4().hex
        started = time.perf_counter()
        option_ids = tuple(option.id for option in request.options)

        if not self._enabled or not self._key:
            outcome: Outcome = "disabled" if not self._enabled else "unavailable"
            return self._finish(
                request, request_id, correlation_id, option_ids, None, None, None, "",
                started, outcome, "ask_owner", "disabled" if not self._enabled else "missing_key",
            )

        # The complete outbound contract. Do not add history, memories, tool output, actor identity,
        # biometrics or credentials here. The stable IDs are also the only keys Jev can return.
        payload = {
            "model": self._model,
            "state": {"question": request.question},
            "questions": {
                "decision": {
                    "type": "choice",
                    "instructions": (
                        "Select the option that best answers the owner's stated decision. Return "
                        "only the typed choice judgment; authorization and execution are out of scope."
                    ),
                    "criteria": {option.id: option.text for option in request.options},
                }
            },
        }
        try:
            status, body = await self._transport(
                payload, self._key, self._endpoint, self._timeout,
            )
        except Exception as exc:  # noqa: BLE001 - outage must become a typed unavailable verdict
            logger.warning(f"Jev judgment unavailable: {type(exc).__name__}")
            return self._finish(
                request, request_id, correlation_id, option_ids, None, None, None, "",
                started, "unavailable", "ask_owner", type(exc).__name__,
            )

        if status < 200 or status >= 300:
            return self._finish(
                request, request_id, correlation_id, option_ids, None, None, None, "",
                started, "unavailable", "ask_owner", f"http_{status}",
            )

        try:
            answer = body["answers"]["decision"]
            selected = str(answer["choice"])
            if selected not in option_ids:
                raise ValueError("unknown_choice")
            probabilities = answer.get("probabilities") or {}
            probability = float(probabilities[selected]) if selected in probabilities else None
            confidence = float(answer["confidence"]) if answer.get("confidence") is not None else None
            if probability is not None and not 0 <= probability <= 1:
                raise ValueError("probability_range")
            if confidence is not None and not 0 <= confidence <= 1:
                raise ValueError("confidence_range")
            selected_text = next(option.text for option in request.options if option.id == selected)
            model = str(body.get("model") or self._model)
        except (KeyError, TypeError, ValueError, StopIteration) as exc:
            return self._finish(
                request, request_id, correlation_id, option_ids, None, None, None,
                str(body.get("model") or ""), started, "invalid", "ask_owner", str(exc),
            )
        return self._finish(
            request, request_id, correlation_id, option_ids, selected, selected_text,
            probability, model, started, "decided", "none", "", confidence=confidence,
        )

    def _finish(
        self,
        request: DecisionRequest,
        request_id: str,
        correlation_id: str,
        option_ids: tuple[str, ...],
        selected_id: str | None,
        selected_text: str | None,
        probability: float | None,
        model: str,
        started: float,
        outcome: Outcome,
        fallback: str,
        error: str,
        *,
        confidence: float | None = None,
    ) -> DecisionVerdict:
        elapsed = round((time.perf_counter() - started) * 1000, 1)
        verdict = DecisionVerdict(
            request_id=request_id,
            correlation_id=correlation_id,
            kind=request.kind,
            option_ids=option_ids,
            selected_id=selected_id,
            selected_text=selected_text,
            probability=probability,
            confidence=confidence,
            model=model,
            latency_ms=elapsed,
            outcome=outcome,
            fallback=fallback,
            error=error[:80],
        )
        row = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "correlation_id": correlation_id,
            "request_id": request_id,
            "kind": request.kind,
            "option_ids": list(option_ids),
            "selected_id": selected_id,
            "probability": probability,
            "confidence": confidence,
            "model": model,
            "latency_ms": elapsed,
            "outcome": outcome,
            "fallback": fallback,
            "error": error[:80],
        }
        self._record(row)
        return verdict

    def _record(self, row: dict[str, Any]) -> None:
        with self._lock:
            self._calls += 1
            if row["outcome"] != "decided":
                self._errors += 1
            self._latest = dict(row)
            try:
                self._path.parent.mkdir(parents=True, exist_ok=True)
                with self._path.open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps(row, separators=(",", ":"), ensure_ascii=False) + "\n")
            except OSError as exc:  # provenance loss is visible, but never breaks the owner turn
                logger.warning(f"Jev judgment audit unavailable: {type(exc).__name__}")

    def snapshot(self) -> dict[str, Any]:
        latest = self._latest
        return {
            "provider": "typesafe",
            "enabled": self._enabled,
            "configured": bool(self._key),
            # Reachability is unknown until a successful call; configured is reported separately so
            # the HUD never turns an unprobed credential into a green provider-health claim.
            "available": latest.get("outcome") == "decided",
            "model": latest.get("model") or self._model,
            "calls": self._calls,
            "errors": self._errors,
            "latest": {
                "request_id": latest.get("request_id", ""),
                "kind": latest.get("kind", ""),
                "selected_id": latest.get("selected_id"),
                "outcome": latest.get("outcome", "never_called"),
                "latency_ms": latest.get("latency_ms", 0.0),
                "correlation_id": latest.get("correlation_id", ""),
            },
        }


JUDGMENTS = JudgmentService()


def judgment_snapshot() -> dict[str, Any]:
    return JUDGMENTS.snapshot()


def clarity_question() -> str:
    """The one clarifying question, in the house's voice. Never two questions, never a menu.

    01.R2 established that a genuinely ambiguous instruction gets ONE question rather than a
    guess. This is the wording for the case Jev detects rather than a regex.

    It deliberately does **not** name the candidate groups. "The office one or the docs one?"
    asks the owner to choose between words he has never used, and he cannot answer it — which
    turns one clarifying turn straight back into a second guess. Uncertainty about *which
    internal bucket* an utterance fell into is the system's problem and is solved by giving the
    model the full surface, not by asking him. This question is only ever about the thing he
    actually asked for.
    """
    return "I want to get that right, sir — what exactly should I do with it?"


def manner_note(signals: "TurnSignals | None") -> str | None:
    """A system-note line steering manner from the turn assessment, or None.

    Kept deliberately thin. The cue-word affect inference in `mushegh.brain.affect` is local,
    always available and cheap, and stays the floor; this refines it when Jev answered, and
    adds urgency as *framing* only. It cannot raise the interruption budget or pierce quiet
    hours — that is life-safety's job alone, and it is deterministic code (D-18, D-29, D-32).
    """
    if signals is None or signals.outcome != "decided":
        return None
    bits: list[str] = []
    if signals.urgency == "now":
        bits.append("he needs this now — answer first, no preamble, no restating the question")
    elif signals.urgency == "soon":
        bits.append("he needs this shortly — lead with the answer, keep it tight")
    if signals.tone == "gentle":
        bits.append("he sounds worn down — warm and steady, no forced positivity")
    elif signals.tone == "curt":
        bits.append("he is being clipped — match the pace, do not pad")
    elif signals.tone == "direct":
        bits.append("he gave a clipped instruction — take it at face value, no hedging")
    return " ".join(bits) or None


def answerable_note(signals: "TurnSignals | None") -> str | None:
    """A system-note line for an unanswerable turn, or None. 01.J13.

    Deliberately silent unless Jev returned a **decided** `not_answerable`. A failed, timed-out or
    never-asked assessment leaves the field None and this returns None, because hedging a clear
    turn because the advice never arrived is worse than the overconfidence it prevents — and §01.R7
    already forbids questioning a clear turn on an outage.

    **The wording is constrained on purpose, and this is the whole risk of the feature.** It tells
    the model to say so when it cannot establish a correct answer, and it explicitly tells it to
    KEEP USING ITS TOOLS. The probe's `no-tools` wording scored the tool-answerable class at p=0.00
    ("what time is it" -> unanswerable), which would have suppressed the tool call on exactly the
    turns that need one. A note that said "this is unanswerable, say so" without that second
    sentence would reproduce that bug in the prompt instead of the payload, and would be harder to
    see, because the payload now measures correct.

    It shapes the GENERATED answer only. It cannot touch the tool surface, the interruption budget
    or quiet hours — same limit as every other advisory signal here (D-18, D-29, D-32).
    """
    if signals is None or not signals.needs_hedge:
        return None
    return (
        "no source may settle this one — so do not invent a specific answer to it. Still use the "
        "tools normally and say plainly what you could and could not establish. A tool may be "
        "exactly what settles it; being unanswerable from memory is not a reason to skip one."
    )
