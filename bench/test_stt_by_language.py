"""18.R7 — the ear is chosen per turn, and the choice is explainable (D-78).

The owner speaks six languages; the configured ear hears five. Deepgram's nova-3 `multi` covers
en/es/fr/de/ru and NOT Ukrainian, so Ukrainian speech does not fail — it comes back as plausible
Russian, the language detector agrees with it, and Afon answers confidently in the wrong language.

A **predictive** router (identify the language from the audio first) was designed, MEASURED, and
REJECTED: faster-whisper `detect_language()` on this machine costs 1089ms on `tiny` and 2425ms on
`base` (2026-10-04, int8, CPU). Paying ~1.1s on every turn to avoid at most ~1.1s of transcription
is a net loss, and on Ukrainian it is slower than simply using Whisper, which auto-detects for
free inside the transcription. [1] asserts that number is recorded where the design was killed, so
it is not re-derived.

So this is **sticky, feedback-driven** routing: the primary ear stays, a transcript teaches the
router where the NEXT turn goes, and turns in a language the primary cannot hear are transcribed
locally — slowly and correctly. What is asserted here:

  * **the routing decision itself** — a language the primary covers keeps the primary; one it does
    not moves to the local ear; an unknown language and a missing local ear are both handled
    explicitly rather than by accident.
  * **no thrash.** The ear changes only when the tracked language crosses the coverage boundary.
    A one-word "так" in the middle of an English exchange must not swap engines, because that reads
    as a malfunction rather than a setting — the same reason `LanguageTracker` needs
    MIN_SWITCH_WORDS.
  * **the limitation is exposed, not commented.** The first Ukrainian turn of a conversation is
    still misheard, because it is the turn that reveals the language and it was transcribed by the
    ear that cannot hear it. `missed_first_turn` counts those, so the cost is measurable.
  * **the exit is reliable.** Leaving the local ear is confirmed by TEXT, unlike the entry, which
    is inferred — so an English exchange routes back to the fast ear and stays there.
  * **no claim of a predictive fix, and no new dependency.**

Hermetic: pure decision logic plus one string scan. No audio, no model, no network, no key.

    uv run python bench/test_stt_by_language.py
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(ROOT / "src"))

passed = failed = 0

SIX = ["en", "ru", "de", "fr", "es", "uk"]
DEEPGRAM = "deepgram"
WHISPER = "whisper"

#: A real Ukrainian sentence (>= MIN_SWITCH_WORDS, with decisive Ukrainian-only letters).
UK_SENTENCE = "дякую, це дуже гарна ідея для нашого проекту"
#: A real English sentence of comparable length.
EN_SENTENCE = "thank you, that is a very good idea for our project"
#: One word. Valid in several of the six, which is exactly why it must not steer the ear.
SHORT_ACK = "так"


def check(name: str, ok: bool, detail: str = "") -> None:
    global passed, failed
    if ok:
        passed += 1
        print(f"  [PASS] {name}")
    else:
        failed += 1
        print(f"  [FAIL] {name}  {detail}")


def main() -> int:
    from afon.edge.stt_routing import (
        CANNOT_HEAR, HEARD, NO_LOCAL, UNKNOWN_LANGUAGE, StickyEarRouter, choose_ear, ear_covers,
    )
    from afon.shared.language import STT_COVERAGE

    print("\n[1] the cost that killed the predictive design is on the record")
    src = (ROOT / "src" / "afon" / "edge" / "stt_routing.py").read_text(encoding="utf-8")
    check("the module states the measured detect_language() cost",
          "1089ms" in src and "2425ms" in src, "the refutation number is missing")
    check("...and says the design was rejected rather than deferred",
          "rejected" in src.lower() and "net loss" in src.lower())
    check("...and explains why routing on the transcript would be circular",
          "circular" in src.lower() or "downstream of the error" in src.lower())

    print("\n[2] the coverage table is read, not copied")
    check("Deepgram's only gap is Ukrainian — the fact this whole task exists for",
          STT_COVERAGE[DEEPGRAM] == frozenset({"en", "es", "fr", "de", "ru"}),
          str(sorted(STT_COVERAGE[DEEPGRAM])))
    check("...and Whisper covers all six", STT_COVERAGE[WHISPER] == frozenset(SIX))
    check("ear_covers agrees with that table for every one of the six languages",
          [ear_covers(DEEPGRAM, c) for c in SIX]
          == [True, True, True, True, True, False],
          str([(c, ear_covers(DEEPGRAM, c)) for c in SIX]))
    tree = ast.parse(src)
    reads_table = "STT_COVERAGE" in src and "STT_COVERAGE[" not in src
    check("the module references STT_COVERAGE rather than restating its contents", reads_table,
          "a second copy of the coverage list is how the two drift apart")

    print("\n[3] the decision, one language at a time")
    for lang in ("en", "ru", "de", "fr", "es"):
        d = choose_ear(lang, DEEPGRAM, WHISPER)
        check(f"{lang}: the fast ear stays", d.engine == DEEPGRAM and d.reason == HEARD,
              f"{d.engine}/{d.reason}")
    uk = choose_ear("uk", DEEPGRAM, WHISPER)
    check("uk: moves to the local ear, and says why", uk.engine == WHISPER
          and uk.reason == CANNOT_HEAR, f"{uk.engine}/{uk.reason}")
    check("a language nobody has claimed yet is not treated as a gap",
          choose_ear("", DEEPGRAM, WHISPER).reason == UNKNOWN_LANGUAGE)
    check("no local ear available keeps the primary rather than refusing to listen",
          choose_ear("uk", DEEPGRAM, None).reason == NO_LOCAL
          and choose_ear("uk", DEEPGRAM, None).engine == DEEPGRAM)
    check("an unknown provider gets the benefit of the doubt — no routing, no cost",
          choose_ear("uk", "some-future-engine", WHISPER).engine == "some-future-engine")
    check("the decision is pure: the same inputs give the same answer",
          choose_ear("uk", DEEPGRAM, WHISPER) == choose_ear("uk", DEEPGRAM, WHISPER))
    check("...and it carries no audio and no provider object",
          not hasattr(uk, "audio") and not hasattr(uk, "service"))

    print("\n[4] the router learns from a transcript and moves the NEXT turn")
    r = StickyEarRouter(primary=DEEPGRAM, local=WHISPER)
    check("an English conversation stays on the fast ear", r.decide().engine == DEEPGRAM)
    r.observe(EN_SENTENCE)
    check("...through several English turns without ever switching",
          r.decide().engine == DEEPGRAM and r.missed_first_turn == 0,
          f"engine={r.decide().engine} missed={r.missed_first_turn}")
    r.observe(UK_SENTENCE)
    check("a Ukrainian transcript moves the conversation into Ukrainian", r.language == "uk",
          r.language)
    check("...and the NEXT turn is transcribed by the local ear", r.decide().engine == WHISPER,
          r.decide().reason)
    check("...and by then it is right, not missed", r.missed_first_turn == 1,
          str(r.missed_first_turn))
    before = r.missed_first_turn
    for _ in range(3):
        r.observe(UK_SENTENCE)
        r.decide()
    check("further Ukrainian turns cost nothing and miss nothing",
          r.missed_first_turn == before and r.decide().engine == WHISPER,
          f"missed={r.missed_first_turn} engine={r.decide().engine}")

    print("\n[5] the honest cost is a counter, not a comment")
    r2 = StickyEarRouter(primary=DEEPGRAM, local=WHISPER)
    r2.observe(EN_SENTENCE)
    r2.observe(UK_SENTENCE)
    check("entering Ukrainian is counted as one missed turn", r2.missed_first_turn == 1,
          str(r2.missed_first_turn))
    r2.reset()
    check("reset clears the counter and the language", r2.missed_first_turn == 0
          and r2.language == "en")
    r3 = StickyEarRouter(primary=DEEPGRAM, local=WHISPER)
    r3.observe(EN_SENTENCE)
    check("a conversation that never goes near Ukrainian misses nothing",
          r3.missed_first_turn == 0)

    print("\n[6] no thrash: a short turn cannot swap the ear")
    r4 = StickyEarRouter(primary=DEEPGRAM, local=WHISPER)
    r4.observe(EN_SENTENCE)
    for ack in (SHORT_ACK, "ok", "да", "oui", "si", "ja"):
        r4.observe(ack)
    check("six one-word acknowledgements in six languages leave the ear where it was",
          r4.language == "en" and r4.decide().engine == DEEPGRAM,
          f"language={r4.language} engine={r4.decide().engine}")
    r4.observe(UK_SENTENCE)
    for ack in (SHORT_ACK, "ok", "так", "так"):
        engine = r4.decide().engine
        r4.observe(ack)
        if r4.decide().engine != engine:
            check("a one-word turn inside a Ukrainian exchange stays on the local ear", False,
                  f"{engine} -> {r4.decide().engine} after {ack!r}")
            break
    else:
        check("a one-word turn inside a Ukrainian exchange stays on the local ear", True)

    print("\n[7] the exit is reliable, because it is confirmed by text")
    r5 = StickyEarRouter(primary=DEEPGRAM, local=WHISPER)
    r5.observe(UK_SENTENCE)
    check("in Ukrainian", r5.decide().engine == WHISPER)
    r5.observe(EN_SENTENCE)
    check("an English sentence takes it back to the fast ear", r5.decide().engine == DEEPGRAM,
          r5.decide().reason)
    r5.observe(EN_SENTENCE)
    r5.observe(EN_SENTENCE)
    check("...and it stays there", r5.decide().engine == DEEPGRAM)
    check("the language detector really does separate the two scripts",
          r5.language == "en" and r5.tracker.last_confidence > 0.5,
          f"{r5.language} @ {r5.tracker.last_confidence}")

    print("\n[8] the switch is visible in the decision")
    r6 = StickyEarRouter(primary=DEEPGRAM, local=WHISPER)
    r6.decide()
    r6.observe(EN_SENTENCE)
    first = r6.decide()
    check("an unchanged ear is not reported as switched", first.switched is False)
    r6.observe(UK_SENTENCE)
    check("the turn that moves the ear says so", r6.decide().switched is True)
    check("and the one after it does not", r6.decide().switched is False)
    st = r6.status()
    check("status is reportable in one log line",
          set(st) == {"primary", "local", "language", "engine", "reason", "missed_first_turns"},
          str(sorted(st)))

    print("\n[9] no new dependency, and no pipeline wiring claimed")
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            imports.add(node.module.split(".")[0])
    check("the module imports only stdlib and afon",
          imports <= {"__future__", "dataclasses", "afon"}, str(sorted(imports)))
    check("it imports no pipecat frame machinery, because the wiring is not in here",
          "pipecat" not in imports, str(sorted(imports)))
    check("the docstring says the wiring is a separate task, not done",
          "18.R8" in src, "the module claims more than it does")

    print("\n[10] the shipped default is unchanged, and that is asserted")
    import afon.config as cfg
    fresh = cfg.Settings(_env_file=None)
    check("the code default is still Deepgram — this task adds logic, not a behaviour change",
          fresh.stt_provider == cfg.STTProvider.deepgram, fresh.stt_provider.value)
    check("...and no setting was added to turn routing on, so nothing is active by accident",
          not hasattr(fresh, "stt_language_routing"),
              "a default-on router would be a behaviour change disguised as a helper")

    print(f"\n{'=' * 60}")
    print(f"  {passed} passed, {failed} failed")
    print("=" * 60)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
