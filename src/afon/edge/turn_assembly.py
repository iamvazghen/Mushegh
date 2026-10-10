"""Turn assembly — deciding that the owner has finished speaking.

The problem this solves is specific to the LOCAL STT paths. Deepgram does its own
endpointing: it decides where the utterance ended and finalises a turn, so the
brain fires as soon as the speech sounds complete. Whisper and Moonshine have no
such model. Pipecat's ``SegmentedSTTService`` cuts them on a Silero silence
timer, so the turn ends when the room has been quiet for ``vad_stop_secs`` — a
fixed number chosen for *silence*, not for *thought*.

That number cannot be right for both. Set it low and Afon interrupts the owner
every time he pauses to think ("remind me about the thing I mentioned to Anna
last — no, the one about—" arrives as two turns, and he answers the first).
Set it high and every exchange pays the full wait even after a clean, finished
sentence, which is the latency budget this pipeline is explicitly built around.

So the silence timer stops being the decision. Text and quiet are two different
signals and this reads both: a turn fires when the accumulated text *looks
finished* AND the room has been quiet long enough. A fragment ending in a
conjunction or a preposition is not finished, and gets a longer hold; a clean
final sentence gets the short one and does not pay for the cautious case.

Three bounds make this safe rather than merely clever:

* **A hard ceiling.** ``max_wait_ms`` is honoured even when the text still looks
  incomplete. Otherwise a fragment that happens to end in "and" hangs the
  assistant indefinitely on a mis-transcription.
* **Silence, not duration, gates the hold.** A long pause *before* any speech
  must not count toward it, or the first fragment after a long room-silence
  fires instantly.
* **Empty is not a turn.** Silence with no text produces nothing at all.

Ported from adewaskar/jarvis ``src/lib/voice.ts`` (``makeAssembler`` /
``holdFor``, MIT © 2026 Aditya Dewaskar), where the same problem exists in the
browser for the same reason: there is no endpointing model behind a Web Speech
or local-STT path.

Not wired into the live pipeline. Per D-08 a handler existing does not enable it;
this is the decision logic, tested, and available to the local STT path when its
acceptance gate has actually run.
"""

from __future__ import annotations

import re

# A closed class, not a general part-of-speech guess.
#
# These are the function words that cannot end an English utterance — "because"
# and "and" and "to" all promise a continuation the STT has not heard yet. Kept
# deliberately small: a word that merely *sounds* open-ended ("right"? "well"?) is
# excluded, because treating a finished sentence as unfinished costs the owner a
# wait on the common case to save him on the rare one.
CONTINUES: frozenset[str] = frozenset({
    "and", "or", "but", "so", "because", "if", "when", "while", "unless", "until",
    "than", "that", "which", "who", "whom", "whose", "where", "whether",
    "to", "of", "in", "on", "at", "for", "with", "from", "by", "about", "into",
    "also", "then", "plus", "plus,",
})

# Bare auxiliaries and copulas. Not function words in the grammatical sense, but
# they cannot end an utterance either: "...the one because it was" is the owner
# mid-sentence, and reading it as finished is precisely the cut-off this module
# exists to prevent. A *complete* sentence ending in one of these is vanishingly
# rare, so the false-hold cost is much smaller than the false-fire cost.
AUXILIARIES: frozenset[str] = frozenset({
    "is", "are", "was", "were", "be", "been", "being", "am",
    "has", "have", "had", "do", "does", "did",
    "can", "could", "will", "would", "shall", "should", "may", "might", "must",
})

# Terminal punctuation is the strongest completion signal there is; it is checked
# before the word list so a sentence ending "...because of the delay." is not
# held back by its own penultimate word.
_TERMINAL = re.compile(r"[.!?…]['\")\]]*\s*$")

# Contractions and clitics that make a trailing-word test wrong in both
# directions: "don't" is not "do not", and "let's" does not continue.
_LEADING_CLITIC = re.compile(r"^['’]|[’']s$|[’']re$|[’']ve$|[’']ll$|[’']d$")

_WORD = re.compile(r"[\w’'-]+", re.UNICODE)


def normalise(text: str) -> str:
    """Collapse whitespace and strip, without touching case or punctuation."""
    return re.sub(r"\s+", " ", (text or "")).strip()


def looks_complete(text: str) -> bool:
    """Does this transcript read as a finished thought?

    Two independent signals, either sufficient:

    * it ends in terminal punctuation, or
    * its last word is not in the closed class of continuations.

    Empty text is never complete — there is nothing to have finished.
    """
    t = normalise(text)
    if not t:
        return False
    if _TERMINAL.search(t):
        return True
    words = _WORD.findall(t)
    if not words:
        return False
    last = words[-1].lower()
    if _LEADING_CLITIC.search(last):
        # "let's" / "we'll" / "don't" — the clitic is the verb, not a dangling
        # continuation, so strip it and re-test the stem.
        stem = _LEADING_CLITIC.sub("", last)
        if stem and (stem in CONTINUES or stem in AUXILIARIES):
            return False
        return True
    return last not in CONTINUES and last not in AUXILIARIES


def hold_ms_for(text: str, *, base_ms: int, long_ms: int) -> int:
    """How long to wait after the room goes quiet before firing this turn.

    A complete sentence waits the short hold and nothing more — this is the
    common case and it is the one paying the latency. An unfinished-looking one
    waits longer, to give the owner time to carry on.

    The caller supplies both values rather than this module hard-coding them,
    because "how long" is a deployment judgement (room acoustics, mic) while
    "finished or not" is not.
    """
    return base_ms if looks_complete(text) else long_ms


class TurnAssembler:
    """Accumulates transcript fragments and says when the turn is ready.

    Not thread-safe, and does not need to be: it is driven from the single
    pipeline task that also observes the VAD frames.
    """

    def __init__(
        self,
        *,
        base_hold_ms: int = 350,
        long_hold_ms: int = 900,
        max_wait_ms: int = 2_500,
    ) -> None:
        if base_hold_ms < 0 or long_hold_ms < base_hold_ms or max_wait_ms < long_hold_ms:
            raise ValueError(
                "holds must satisfy 0 <= base <= long <= max; got "
                f"base={base_hold_ms} long={long_hold_ms} max={max_wait_ms}"
            )
        self._base_hold_ms = base_hold_ms
        self._long_hold_ms = long_hold_ms
        self._max_wait_ms = max_wait_ms
        self._parts: list[str] = []
        # When the VAD last reported speech as having stopped. None means the
        # owner is still talking, or has never talked — both are "not ready".
        self._silence_at: float | None = None
        # When the first fragment of the current turn arrived. The ceiling is
        # measured from here, not from the silence, so a turn cannot be held
        # open indefinitely by speech that never quite stops being speech.
        self._started_at: float | None = None

    # ---------------------------------------------------------------- input

    def push_fragment(self, text: str, *, now_ms: float) -> None:
        """Add a transcript fragment and mark speech as (re)started."""
        clean = normalise(text)
        if not clean:
            return
        if self._started_at is None:
            self._started_at = now_ms
        self._parts.append(clean)
        self._silence_at = None

    def note_silence(self, *, now_ms: float) -> None:
        """The VAD reports speech has stopped; start counting the hold."""
        if self._parts:
            self._silence_at = now_ms

    def reset(self) -> None:
        """Drop the turn in progress. The next fragment starts a fresh one."""
        self._parts.clear()
        self._silence_at = None
        self._started_at = None

    # --------------------------------------------------------------- output

    @property
    def pending(self) -> str:
        """Everything accumulated so far, normalised."""
        return normalise(" ".join(self._parts))

    def due(self, *, now_ms: float) -> bool:
        """Is this turn ready to be handed to the brain?"""
        if not self._parts:
            return False
        if self._silence_at is None or self._started_at is None:
            return False

        # The ceiling first: a mis-transcribed fragment ending in "and" must not
        # be able to hold the assistant open forever.
        if now_ms - self._started_at >= self._max_wait_ms:
            return True

        hold = hold_ms_for(self.pending, base_ms=self._base_hold_ms, long_ms=self._long_hold_ms)
        return now_ms - self._silence_at >= hold

    def take(self) -> str:
        """Return the finished utterance and clear the turn.

        Returns an empty string when nothing was pending, so a caller that polls
        on a timer cannot accidentally fire a blank turn.
        """
        text = self.pending
        self.reset()
        return text