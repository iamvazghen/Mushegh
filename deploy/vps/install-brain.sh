#!/usr/bin/env bash
# Deploy mushegh-brain as an always-on systemd service ON THE VPS.
#
#   bash install-brain.sh
#
# Idempotent: re-run to update code + restart. Expects:
#   * the mushegh repo present at $MUSHEGH_DIR (default ~/mushegh) — git clone or rsync it first;
#   * a real .env at $MUSHEGH_DIR/.env (copy your edge .env, see notes below);
#   * uv installed (https://docs.astral.sh/uv/); falls back to python -m venv if absent.
set -euo pipefail

MUSHEGH_DIR="${MUSHEGH_DIR:-$HOME/mushegh}"
HOST="${MUSHEGH_BRAIN_HOST:-127.0.0.1}"
HEALTH_PORT="${MUSHEGH_CLIENT_HTTP_PORT:-8766}"

if [ ! -d "$MUSHEGH_DIR/src/mushegh" ]; then
  echo "No mushegh repo at $MUSHEGH_DIR. Clone/rsync it there first, then re-run."
  echo "  e.g.  git clone <repo> $MUSHEGH_DIR    (or rsync from your machine)"
  exit 1
fi
if [ ! -f "$MUSHEGH_DIR/.env" ]; then
  echo "No $MUSHEGH_DIR/.env. Copy your edge .env there (it holds the brain's keys), then re-run."
  echo "NOTE for a VPS-reachable brain: set MUSHEGH_BRAIN_HOST=0.0.0.0 AND a non-empty"
  echo "MUSHEGH_API_AUTH_TOKEN in that .env — the server enforces the bearer token when it's set."
  exit 1
fi

cd "$MUSHEGH_DIR"

# Sync the brain runtime (brain = LLM/FastAPI/scheduler/cache; channels = Telethon DM reading).
if command -v uv >/dev/null 2>&1; then
  UV_BIN="$(command -v uv)"
  echo "Syncing deps with uv ($UV_BIN)…"
  "$UV_BIN" sync --extra brain --extra channels --extra browse
  EXEC="$UV_BIN run --no-sync python -m mushegh.brain.server"
else
  echo "uv not found; using python venv…"
  python3 -m venv .venv
  ./.venv/bin/pip install --quiet --upgrade pip
  ./.venv/bin/pip install --quiet -e ".[brain,channels]"
  EXEC="$MUSHEGH_DIR/.venv/bin/python -m mushegh.brain.server"
  UV_BIN=""
fi

# Install the unit, rewriting user/paths/ExecStart for this account + chosen runtime.
SVC=/etc/systemd/system/mushegh-brain.service
sed -e "s#/home/openclaw/mushegh#$MUSHEGH_DIR#g" \
    -e "s#^User=.*#User=$(whoami)#" \
    -e "s#^ExecStart=.*#ExecStart=$EXEC#" \
    mushegh-brain.service | sudo tee "$SVC" >/dev/null

sudo systemctl daemon-reload
sudo systemctl enable --now mushegh-brain.service
sleep 2
echo "--- health ---"
curl -fsS "http://$HOST:$HEALTH_PORT/healthz" \
  && echo " (brain alive)" \
  || echo "(health check failed; inspect: journalctl -u mushegh-brain -n 60 --no-pager)"
echo
echo "Deployed. Logs: journalctl -u mushegh-brain -f"
echo "Restart proof: sudo systemctl kill mushegh-brain  ->  it should come back within ~5s."
