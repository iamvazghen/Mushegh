"""TTS builder — pick + configure the text-to-speech voice for the edge pipeline.

Like ``build_stt``, this honours ``settings.tts_provider`` so the SAME pipeline runs cloud-quality
or **100% local** just by flipping one flag — no code change:

  * ``piper``      — the code default (D-17). Local, CPU-fast. Fully offline: the voice model
                     auto-downloads ONCE, then no network at all.
  * ``elevenlabs`` — cloud, streaming, the chosen "Mushegh voice". Needs an API key + voice id.
  * ``kokoro``     — local, higher quality than Piper, still CPU-runnable. Model auto-downloads once.

With ``stt_provider`` also local (Whisper is the default — D-78), the default stack is now
**fully offline on both sides**: no audio ever leaves the machine and no cloud key is required.

**But "fully offline" currently means "fully offline in English," and that is the whole of D-78.**
The local engines are monolingual as wired — one ``piper_voice`` model, one English voice on disk,
Kokoro pinned to ``Language.EN``, and no per-language voice selection anywhere. This owner speaks
French, English, German, Ukrainian and Russian, so on his machine ``MUSHEGH_TTS_PROVIDER`` is set to
``elevenlabs`` and the D-17 opt-in is exercised. That is the charter working, not failing; the
alternative was a local voice that answers a German sentence in English. The exit from that
exception is per-language local voices (`18.R6`), not a weaker claim about this one.

The local voices need the ``local-voice`` extra installed (``uv sync --extra local-voice``).
"""

from __future__ import annotations

from pathlib import Path

from loguru import logger

from mushegh.config import TTSProvider, settings

_REPO_ROOT = Path(__file__).resolve().parents[3]


def _build_elevenlabs():
    if not (settings.elevenlabs_api_key and settings.elevenlabs_voice_id):
        raise RuntimeError(
            "TTS provider is 'elevenlabs' but MUSHEGH_ELEVENLABS_API_KEY / MUSHEGH_ELEVENLABS_VOICE_ID "
            "are not set. Add them to .env, or switch to a fully-local voice with "
            "MUSHEGH_TTS_PROVIDER=piper (offline, no key)."
        )
    from pipecat.services.elevenlabs.tts import ElevenLabsTTSService
    from pipecat.frames.frames import ErrorFrame
    from mushegh.edge import voice_health

    from mushegh.shared.language import MATCH, SUPPORTED, name_of, parse_languages

    # Which language to hand ElevenLabs. When the reply language is PINNED, say so — it is free
    # determinism. When it is "match", deliberately leave it unset: the reply text is already
    # wholly in the target language and eleven_flash_v2_5 detects it per utterance, whereas a
    # build-time pin would lock the voice to one language for the life of the process, which is
    # the opposite of what mirror mode is for.
    reply = (settings.reply_language or "").strip().lower()
    pinned = "" if reply == MATCH else next(iter(parse_languages(settings.reply_language)), "")
    wanted = parse_languages(settings.understood_languages) or ["en"]
    if len(wanted) > 1 and not any(m in settings.elevenlabs_model
                                   for m in ("multilingual", "flash", "turbo", "v3")):
        logger.warning(
            f"MUSHEGH_ELEVENLABS_MODEL='{settings.elevenlabs_model}' is an English-only voice model, "
            f"but {len(wanted)} languages are configured "
            f"({', '.join(name_of(c) for c in wanted)}). Non-English replies will be spoken with "
            f"an English phoneme set. Use eleven_flash_v2_5 or eleven_multilingual_v2."
        )
    logger.info(
        f"TTS: ElevenLabs {settings.elevenlabs_model} (cloud, streaming"
        + (f", language={pinned}" if pinned else
           f", per-utterance language across {len(wanted)}: "
           f"{'/'.join(SUPPORTED[c][0] for c in wanted)}") + ")"
    )

    class _MonitoredElevenLabs(ElevenLabsTTSService):
        """Records escalated errors so the watchdog can fail over to local Piper when the cloud
        WebSocket keeps timing out (handshake/keepalive deaths a REST probe can't detect)."""

        async def push_error_frame(self, error: ErrorFrame) -> None:
            voice_health.record_cloud_error(str(getattr(error, "error", "")))
            await super().push_error_frame(error)

    opts: dict = {"voice": settings.elevenlabs_voice_id, "model": settings.elevenlabs_model}
    if pinned:
        opts["language"] = pinned
    return _MonitoredElevenLabs(
        api_key=settings.elevenlabs_api_key,
        settings=ElevenLabsTTSService.Settings(**opts),
    )


def _build_piper():
    try:
        from pipecat.services.piper.tts import PiperTTSService
    except ImportError as e:  # pragma: no cover - depends on optional extra
        raise RuntimeError(
            "Piper (local TTS) isn't installed. Run: uv sync --extra local-voice"
        ) from e

    download_dir = _REPO_ROOT / ".piper-voices"
    download_dir.mkdir(exist_ok=True)
    logger.info(f"TTS: Piper LOCAL (voice={settings.piper_voice}) — offline, no key, no cloud")
    return PiperTTSService(
        download_dir=download_dir,
        settings=PiperTTSService.Settings(model=None, voice=settings.piper_voice, language=None),
    )


def _build_kokoro():
    try:
        from pipecat.services.kokoro.tts import KokoroTTSService
        from pipecat.transcriptions.language import Language
    except ImportError as e:  # pragma: no cover - depends on optional extra
        raise RuntimeError(
            "Kokoro (local TTS) isn't installed. Run: uv sync --extra local-voice"
        ) from e

    logger.info(f"TTS: Kokoro LOCAL (voice={settings.kokoro_voice}) — offline, no key, no cloud")
    return KokoroTTSService(
        settings=KokoroTTSService.Settings(
            model=None, voice=settings.kokoro_voice, language=Language.EN
        ),
    )


# provider -> builder. Kept as a dispatch table so the selection is unit-testable without
# instantiating (and downloading) any heavy model.
_BUILDERS = {
    TTSProvider.elevenlabs: _build_elevenlabs,
    TTSProvider.piper: _build_piper,
    TTSProvider.kokoro: _build_kokoro,
}
# Cloud providers: if one of these can't be built, we fall back to the local engine.
_CLOUD = {TTSProvider.elevenlabs}


def build_tts():
    """Construct the configured TTS service (honours ``MUSHEGH_TTS_PROVIDER``).

    Cloud is the default for quality; if it can't be built (missing key, etc.) and
    ``voice_local_fallback`` is on, fall back to the configured LOCAL voice so the pipeline always
    comes up instead of dying. Non-cloud providers raise their own clear, actionable error.
    """
    prov = settings.tts_provider
    fb = settings.tts_fallback_provider
    # Startup health gate (mirrors build_stt): only build cloud TTS if it actually answers now (or
    # isn't in post-failure cooldown); else come up on local Piper so the edge can always speak.
    if prov in _CLOUD and settings.voice_local_fallback and fb not in _CLOUD:
        from mushegh.edge import voice_health

        if not voice_health.cloud_tts_healthy():
            logger.warning(f"cloud TTS '{prov.value}' unhealthy at startup — using local '{fb.value}'")
            return _BUILDERS[fb]()
        voice_health.mark_cloud_active(True)
    try:
        return _BUILDERS.get(prov, _build_elevenlabs)()
    except Exception as e:  # noqa: BLE001
        # The fallback applies to a LOCAL primary too, not only a cloud one. That was not needed
        # while the default was cloud — but it is needed now, because with Piper primary a
        # builder that cannot construct would otherwise raise and take the voice down with it,
        # which is the exact regression the local default was chosen to avoid. A fallback to
        # ITSELF is not a fallback, so `fb is not prov` is the condition.
        if settings.voice_local_fallback and fb is not prov:
            logger.warning(f"{prov.value} unavailable ({e}); falling back to '{fb.value}'")
            return _BUILDERS[fb]()
        raise
