"""Afon — a 24/7 self-hosted voice assistant.

Edge (Pipecat voice pipeline, local PC) + Brain (orchestrator + OpenClaw fleet, VPS).

Deliberately NOT described as "local-first" (O1.5, p=0.77): every byte of state is self-hosted —
yours, on your machine and your VPS, no vendor account holding it — but the reasoning models are
remote by default, and the VPS has no GPU. The audio path IS local (capture, wake word, VAD,
optional STT/TTS). Saying "local-first" overpromises on the half that is not.
"""

__version__ = "0.0.1"
