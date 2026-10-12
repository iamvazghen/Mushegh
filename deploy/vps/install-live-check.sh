#!/usr/bin/env bash
# Install the weekly live-integration check (systemd user timer). Run ON the VPS, once.
set -euo pipefail
mkdir -p ~/.config/systemd/user
cp "$(dirname "$0")/live-check.sh" "$HOME/mushegh/live-check.sh"
chmod +x "$HOME/mushegh/live-check.sh"

cat > ~/.config/systemd/user/mushegh-live-check.service <<'EOF'
[Unit]
Description=Mushegh weekly live-integration check (credential rot)

[Service]
Type=oneshot
ExecStart=%h/mushegh/live-check.sh
EOF

cat > ~/.config/systemd/user/mushegh-live-check.timer <<'EOF'
[Unit]
Description=Run the Mushegh live-integration check weekly

[Timer]
OnCalendar=Mon 07:30
Persistent=true

[Install]
WantedBy=timers.target
EOF

systemctl --user daemon-reload
systemctl --user enable --now mushegh-live-check.timer
systemctl --user list-timers mushegh-live-check.timer --no-pager
