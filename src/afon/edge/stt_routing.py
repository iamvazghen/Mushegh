"""18.R7 / D-78 — which ear should this turn use?

The problem this solves: the owner speaks six languages and the configured ear hears five of them.
Deepgram's nova-3 `multi` model covers en/es/fr/de/ru and **not Ukrainian**, so a Ukrainian
sentence does not fail — it comes back as plausible *Russian*, the language detector agrees with
it, and Afon answers confidently in the wrong language. Nothing crashes and nothing logs an error,
which is what makes it the worst kind of bug.

**A predictive router was designed, measured, and rejected.** The obvious design is to identify
the language from the AUDIO before trusting any transcript — a transcript is the thing that is
wrong, so routing on it is circular, and `afon.shared.language.detect()` runs on text and is
therefore downstream of the error. Measuring the only available audio-level LID on this machine
(2026-10-04, faster-whisper `detect_language()`, int8, CPU) gave **1089ms on `tiny` and 2425ms on
`base`**. Every turn would pay ~1.1s to avoid at most ~1.1s of transcription, and the 300ms
endpointing that is the whole reason for choosing Deepgram would be consumed by the router. On the
five languages that already work it is a 4.7x regression; on Ukrainian it is *slower* than just
using Whisper, which auto-detects for free as part of transcription. Net loss. Refuted, and the
number is recorded here so nobody re-derives it.

**What this module is instead: sticky, feedback-driven routing.** The primary ear stays. A turn
transcribed by the primary is fed to the language tracker that already exists; once the
conversation is in a language the primary cannot hear, subsequent turns are transcribed locally,
slowly and correctly. The language leaving that state is confirmed *by text*, so the exit is
reliable. Marginal cost on a normal turn: one string scan. No new model, no new dependency, and
no per-turn model call.

**The honest limitation, stated here rather than discovered later:** the FIRST Ukrainian turn in
a conversation is still misheard, because that turn is the one that reveals the language and it
was transcribed by the ear that cannot hear it. Every turn after it is right. `missed_first_turn`
is exposed as a counter so the cost is measurable rather than folklore, and closing it needs a
predictive LID this hardware cannot afford.

This is deliberately **only the decision**. It is pure — no pipecat frames, no audio, no
provider calls — because a per-turn router inside the live frame pipeline cannot be verified
without a microphone and a reachable brain, and shipping unverified pipeline wiring is the
inversion this project refuses. The wiring is `18.R8`; the logic is here and gated.
"""

from __future__ import annotations

from dataclasses import dataclass

from afon.shared.language import STT_COVERAGE, LanguageTracker

#: Why a turn was routed the way it was. Machine-readable on purpose: "it worked" is not a reason
#: anyone can act on, and the whole point of this module is that the routing is explainable.
HEARD = "ear-can-hear-this-language"
CANNOT_HEAR = "ear-cannot-hear-this-language"
NO_LOCAL = "no-local-ear-available"
UNKNOWN_LANGUAGE = "language-not-yet-known"


@dataclass(frozen=True)
class RoutingDecision:
    """Which engine transcribes this turn, and why. Carries no audio and no provider object."""

    engine: str
    reason: str
    language: str
    switched: bool = False

    @property
    def is_local(self) -> bool:
        return self.reason in (CANNOT_HEAR, NO_LOCAL)


def ear_covers(provider: str, language: str) -> bool:
    """Can this provider actually transcribe this language?

    Reads `STT_COVERAGE` rather than repeating a list, because that table is the single place this
    fact is written down — a second copy is how the two drift apart and the bug comes back. An
    unknown provider gets the benefit of the doubt (no routing, no cost), and an unknown or empty
    language is not a gap: nothing has claimed to be a language yet.
    """
    covered = STT_COVERAGE.get((provider or "").strip().lower())
    lang = (language or "").strip().lower()
    if covered is None or not lang:
        return True
    return lang in covered


def choose_ear(language: str, primary: str, local: str | None = None) -> RoutingDecision:
    """Pure: given the conversation's language, pick the engine for the NEXT turn.

    `local` is the engine to use when the primary cannot hear the language, and `None` means no
    local ear is available — which is a real configuration, not an error: the turn still has to be
    transcribed, and refusing to listen is worse than listening imperfectly. That case says so
    explicitly instead of pretending.
    """
    lang = (language or "").strip().lower()
    if not lang:
        return RoutingDecision(primary, UNKNOWN_LANGUAGE, lang)
    if ear_covers(primary, lang):
        return RoutingDecision(primary, HEARD, lang)
    if not local:
        return RoutingDecision(primary, NO_LOCAL, lang)
    return RoutingDecision(local, CANNOT_HEAR, lang)


class StickyEarRouter:
    """Keeps the conversation's language and answers 'which ear for this turn?'.

    Sticky in the same sense `LanguageTracker` is: the router only changes ears when the tracked
    language crosses the primary's coverage boundary, never on a marginal turn. That is what stops
    a short "так" in the middle of an English exchange from swapping engines mid-conversation,
    which would look like a malfunction rather than a setting.
    """

    def __init__(self, primary: str, local: str | None = "whisper",
                 default_language: str = "en") -> None:
        self.primary = primary
        self.local = local
        self.tracker = LanguageTracker(default=default_language)
        self.missed_first_turn = 0
        self._last_engine = ""

    @property
    def language(self) -> str:
        return self.tracker.current

    def decide(self) -> RoutingDecision:
        """The engine for the turn about to be recorded. Pure with respect to the router state."""
        decision = choose_ear(self.language, self.primary, self.local)
        switched = bool(self._last_engine) and decision.engine != self._last_engine
        self._last_engine = decision.engine
        return RoutingDecision(decision.engine, decision.reason, decision.language, switched)

    def observe(self, transcript: str) -> str:
        """Feed one transcript back so the NEXT turn can be routed correctly.

        The ordering matters and is the whole design: the transcript of turn N is what teaches the
        router where turn N+1 goes. A turn can only teach what it got right, which is why the first
        Ukrainian turn of a conversation is lost — and why `missed_first_turn` counts it.
        """
        before = self.language
        after = self.tracker.observe(transcript or "")
        if after != before and not ear_covers(self.primary, after):
            self.missed_first_turn += 1
        return after

    def reset(self) -> None:
        self.tracker.reset()
        self._last_engine = ""
        self.missed_first_turn = 0

    def status(self) -> dict:
        """What the router is doing and what it has cost so far. For a log line, not for a test."""
        d = self.decide()
        return {
            "primary": self.primary,
            "local": self.local,
            "language": d.language,
            "engine": d.engine,
            "reason": d.reason,
            "missed_first_turns": self.missed_first_turn,
        }
