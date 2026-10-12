#!/usr/bin/env bash
# Deploy the Mushegh VPS ticker (Phase 4b true-24/7 recurring reminders).
# Run ON the VPS, from this directory:  bash install.sh
# Idempotent: re-running updates the code + restarts the service.
set -euo pipefail

DEST="${MUSHEGH_TICKER_DIR:-$HOME/mushegh-ticker}"
NTFY_TOPIC="${MUSHEGH_NTFY_TOPIC:-}"
NTFY_SERVER="${MUSHEGH_NTFY_SERVER:-https://ntfy.sh}"
PORT="${MUSHEGH_TICKER_PORT:-8770}"
HOST="${MUSHEGH_TICKER_HOST:-127.0.0.1}"
TOKEN="${MUSHEGH_TICKER_TOKEN:-}"

if [ -z "$NTFY_TOPIC" ]; then
  echo "Set MUSHEGH_NTFY_TOPIC to the SAME topic as your edge .env, e.g.:"
  echo "  MUSHEGH_NTFY_TOPIC=mushegh-vaz-619-7f3k9q2 bash install.sh"
  exit 1
fi

mkdir -p "$DEST"
cp -f mushegh_ticker.py "$DEST/mushegh_ticker.py"

# Isolated venv with just the two deps the ticker needs.
python3 -m venv "$DEST/.venv"
"$DEST/.venv/bin/pip" install --quiet --upgrade pip
"$DEST/.venv/bin/pip" install --quiet "apscheduler>=3.10" "httpx>=0.27"

# Environment file the systemd unit reads.
cat > "$DEST/ticker.env" <<EOF
MUSHEGH_NTFY_SERVER=$NTFY_SERVER
MUSHEGH_NTFY_TOPIC=$NTFY_TOPIC
MUSHEGH_TICKER_HOST=$HOST
MUSHEGH_TICKER_PORT=$PORT
MUSHEGH_TICKER_TOKEN=$TOKEN
MUSHEGH_TICKER_TZ=${MUSHEGH_TICKER_TZ:-Europe/Berlin}
MUSHEGH_TICKER_DB=$DEST/ticker_reminders.json
EOF

# Install + start the systemd service (rewrites paths/user for this account).
SVC=/etc/systemd/system/mushegh-ticker.service
sed -e "s#/home/openclaw/mushegh-ticker#$DEST#g" \
    -e "s#^User=.*#User=$(whoami)#" \
    mushegh-ticker.service | sudo tee "$SVC" >/dev/null

sudo systemctl daemon-reload
sudo systemctl enable --now mushegh-ticker.service
sleep 1
echo "--- health ---"
curl -fsS "http://$HOST:$PORT/health" || echo "(health check failed; check: journalctl -u mushegh-ticker -n 50)"
echo
echo "Deployed to $DEST. Point the edge at it with MUSHEGH_TICKER_URL=http://$HOST:$PORT in .env"
echo "(if HOST is 127.0.0.1, the edge must reach it over the same tunnel/host as the gateway)."
