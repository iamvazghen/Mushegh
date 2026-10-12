#!/data/data/com.termux/files/usr/bin/bash
# Launch Mushegh edge-lite (push-to-talk) on Android/Termux.
set -euo pipefail

REPO="${MUSHEGH_REPO:-$HOME/OpenMushegh}"
cd "$REPO"

# Load local secrets if present (MUSHEGH_BRAIN_WS_URL, MUSHEGH_API_AUTH_TOKEN, MUSHEGH_GROQ_API_KEY).
[ -f "$HOME/.mushegh.env" ] && set -a && . "$HOME/.mushegh.env" && set +a

# Keep the CPU awake while the loop runs so the mic/link don't sleep (needs termux-api).
termux-wake-lock 2>/dev/null || true
trap 'termux-wake-unlock 2>/dev/null || true' EXIT

exec uv run python -m mushegh.edge.edge_lite
