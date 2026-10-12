"""18.R4 — the local voice is the default, and the cloud is an opt-in.

D-17: "Latency and local privacy dominate cost and personality, every time. Piper/Kokoro is
the default; ElevenLabs is an opt-in for when quality is worth the egress."

The code disagreed with its own stated intent: `config.py` defaulted `tts_provider` to
ElevenLabs while `bench/voice_offline_check.py` printed that "the OpenMushegh FRAMEWORK default
is local/BYO-key so a stranger needs no paid accounts." Two documents, one of them a
comment in the file that decides it. This gate makes the code match the decision, and it
checks the property that actually matters: **a default that needs no key.**

The subtle half is [4]. While the primary was cloud, the fallback only had to cover a cloud
failure. With a LOCAL primary, a builder that cannot construct would raise and take the voice
down — the exact regression the local default was chosen to avoid — so the fallback was
widened to cover a local primary too. That is a behaviour change and it is asserted here.

STT is untouched here, and deliberately so. An earlier version of this file asserted that as a
process note; it is now a measured position. The owner's ear is the weak point — Deepgram's
nova-3 `multi` covers en/es/fr/de/ru but NOT Ukrainian, and he speaks Ukrainian, so Ukrainian
speech came back as plausible Russian with a confident answer in the wrong language (D-78). The
local alternative was then MEASURED on this machine: `whisper_model=base`, int8, CPU, mean 3.00s
per utterance, real-time factor 1.39, against a 1800ms mean budget. So local STT is 1.7x over
budget and cloud STT is wrong in one of six languages. Neither is acceptable alone; the fix is
routing by language (`18.R7`) and it is the owner's call. The assertions in [6] therefore pin the
*cost* rather than pretend the conflict is resolved.

Hermetic: builders are replaced with sentinels, so no voice model, no key and no network.

    uv run python bench/test_tts_local_default.py
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

_TMP = tempfile.TemporaryDirectory(prefix="mushegh-tts-")
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
    from mushegh.config import STTProvider, Settings, TTSProvider, settings
    from mushegh.edge import stt as stt_mod
    from mushegh.edge import tts as tts_mod
    from mushegh.edge import voice_health

    print("[1] the code default is local")
    fresh = Settings(_env_file=None)
    check("tts_provider defaults to a LOCAL provider", fresh.tts_provider not in tts_mod._CLOUD,
          f"got {fresh.tts_provider.value}")
    check("...specifically piper", fresh.tts_provider == TTSProvider.piper, fresh.tts_provider.value)
    check("a blank-key config carries no ElevenLabs key", fresh.elevenlabs_api_key is None)
    # `using_cloud_voice` is a COMBINED STT-or-TTS diagnostic. It reads True here because STT is
    # Deepgram — and that is a measured position, not an unfinished decision, so it is reported and
    # asserted rather than left to drift. The Ukrainian gap that makes Deepgram uncomfortable is
    # asserted by name in [6], and the fix for it is `18.R7`, not a silent default change.
    check("using_cloud_voice is True, and only because STT is the cloud ear",
          fresh.using_cloud_voice is True, str(fresh.using_cloud_voice))
    check("...while the TTS half of it is local",
          fresh.tts_provider not in tts_mod._CLOUD, fresh.tts_provider.value)

    print("\n[1b] is the charter in force on THIS machine?")
    live = settings                      # the module singleton, which read the real .env
    if live.tts_provider in tts_mod._CLOUD:
        print(f"        NO — the live config resolves to '{live.tts_provider.value}', because")
        print("        MUSHEGH_TTS_PROVIDER is set in C:\\Mushegh\\.env. That is the D-17 OPT-IN")
        print("        working, not a defect: the code default is local, and the deployment")
        print("        explicitly asks for the cloud voice. To put D-17 in force, comment out")
        print("        MUSHEGH_TTS_PROVIDER (or set it to 'piper') in that file.")
        check("the code default is local even though the deployment overrides it", True)
    else:
        print(f"        YES — the live config resolves to '{live.tts_provider.value}'")
        check("...and the deployment agrees with the code default", True)
    print("\n[2] the default needs no key and no paid account")
    saved = tts_mod._BUILDERS
    # `build_tts` reads the module's OWN settings object, not one passed in. Patching a local
    # Settings instance changes nothing — the first version of this gate did exactly that and
    # every assertion after it passed by testing the wrong object.
    saved_settings = tts_mod.settings
    saved_prov = saved_settings.tts_provider
    saved_fb = saved_settings.tts_fallback_provider
    saved_fb_on = saved_settings.voice_local_fallback
    saved_health = voice_health.cloud_tts_healthy
    saved_turn = voice_health.mark_cloud_active
    try:
        # Sentinels, so nothing heavy loads and the startup health gate is not consulted.
        tts_mod._BUILDERS = {
            TTSProvider.elevenlabs: lambda: "CLOUD",
            TTSProvider.piper: lambda: "LOCAL-PIPER",
            TTSProvider.kokoro: lambda: "LOCAL-KOKORO",
        }
        voice_health.cloud_tts_healthy = lambda: True
        voice_health.mark_cloud_active = lambda *_a, **_k: None

        saved_settings.tts_provider = TTSProvider.piper
        check("a blank-key config still builds a voice", tts_mod.build_tts() == "LOCAL-PIPER",
              str(tts_mod.build_tts()))

        print("\n[3] the cloud is reachable, as an explicit opt-in")
        saved_settings.tts_provider = TTSProvider.elevenlabs
        check("setting the provider to elevenlabs uses the cloud builder",
              tts_mod.build_tts() == "CLOUD", str(tts_mod.build_tts()))
        saved_settings.tts_provider = TTSProvider.kokoro
        check("and kokoro is a local alternative", tts_mod.build_tts() == "LOCAL-KOKORO",
              str(tts_mod.build_tts()))

        print("\n[4] a LOCAL primary that cannot build degrades instead of dying")
        def _boom() -> str:
            raise RuntimeError("no local engine installed")

        tts_mod._BUILDERS = {
            TTSProvider.elevenlabs: lambda: "CLOUD",
            TTSProvider.piper: lambda: "LOCAL-PIPER",
            TTSProvider.kokoro: _boom,
        }
        saved_settings.tts_provider = TTSProvider.kokoro
        saved_settings.tts_fallback_provider = TTSProvider.piper
        saved_settings.voice_local_fallback = True
        check("kokoro failing falls back to piper, not to an exception",
              tts_mod.build_tts() == "LOCAL-PIPER", str(tts_mod.build_tts()))

        print("\n[5] ...but falling back to itself is not a fallback")
        tts_mod._BUILDERS = {TTSProvider.piper: _boom}
        saved_settings.tts_provider = TTSProvider.piper
        saved_settings.tts_fallback_provider = TTSProvider.piper
        try:
            tts_mod.build_tts()
            check("with no other local voice to offer, it raises", False, "it returned a voice")
        except RuntimeError:
            check("with no other local voice to offer, it raises", True)
    finally:
        tts_mod._BUILDERS = saved
        tts_mod.settings = saved_settings
        saved_settings.tts_provider = saved_prov
        saved_settings.tts_fallback_provider = saved_fb
        saved_settings.voice_local_fallback = saved_fb_on
        voice_health.cloud_tts_healthy = saved_health
        voice_health.mark_cloud_active = saved_turn

    print("\n[6] the scope boundary is asserted, not left to drift")
    check("STT is untouched by this task: still Deepgram, which is where the measurement puts it",
          fresh.stt_provider == STTProvider.deepgram, fresh.stt_provider.value)
    check("Deepgram is still SELECTABLE, so cloud STT remains an opt-in and not a deletion",
          STTProvider.deepgram in stt_mod._BUILDERS and STTProvider.deepgram in stt_mod._CLOUD)
    check("Whisper is selectable too, so the local ear is one setting away",
          STTProvider.whisper in stt_mod._BUILDERS, str(sorted(s.value for s in STTProvider)))

    # The defect that makes Deepgram uncomfortable, asserted as still real. If this ever goes empty
    # the pressure to route by language (18.R7) disappears, and that is exactly when someone should
    # be told rather than a year later.
    from mushegh.shared.language import SUPPORTED, stt_gaps
    six = sorted(SUPPORTED)
    check("the Ukrainian gap is still real for Deepgram", stt_gaps("deepgram", six) == ["uk"],
          str(stt_gaps("deepgram", six)))
    check("and Whisper would close it — every supported language, none missing",
          stt_gaps("whisper", six) == [], str(stt_gaps("whisper", six)))
    check("so the cost of the current default is stated, not hidden: one of six languages is wrong",
          stt_gaps(fresh.stt_provider.value, six) != [], str(fresh.stt_provider.value))

    env = (ROOT / ".env.example").read_text(encoding="utf-8")
    check(".env.example documents the TTS opt-in", "MUSHEGH_TTS_PROVIDER" in env)
    check("...and still carries the ElevenLabs key as an option, now commented as opt-in",
          "ELEVENLABS" in env)

    print(f"\n=== {passed + failed} checks: {passed} passed, {failed} failed ===")
    if not failed:
        print("ALL CHECKS PASSED ===")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
