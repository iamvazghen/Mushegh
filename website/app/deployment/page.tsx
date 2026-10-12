import Link from "next/link";

export default function Deployment() {
  return (
    <>
      <h1>Deployment — the brain, the ticker, and the live-check</h1>
      <p className="lead">
        Three pieces can live on the always-on host (your cheap Linux VPS). They're independent
        — deploy any one, any combination, or all three.
      </p>

      <table>
        <thead>
          <tr><th>Service</th><th>Port</th><th>What it does</th></tr>
        </thead>
        <tbody>
          <tr><td><code>mushegh-brain</code></td><td>8765 (WS) · 8766 (HTTP)</td><td>The full agent + WebSocket voice endpoint + reminder scheduler + proactive engine + Telegram bridge. The 24/7 brain.</td></tr>
          <tr><td><code>mushegh-ticker</code></td><td>8770 (HTTP)</td><td>Tiny standalone daemon for <em>recurring</em> ntfy pushes (the only reminder case ntfy can't hold server-side).</td></tr>
          <tr><td><code>live-check timer</code></td><td>(cron)</td><td>Weekly live-integration test; voice alert to the owner on failure.</td></tr>
        </tbody>
      </table>

      <h2>1 · Brain service</h2>
      <p>
        <code>deploy/vps/mushegh-brain.service</code> is the systemd unit (Restart=always, MemoryMax,
        EnvironmentFile=.env). <code>deploy/vps/install-brain.sh</code> does the one-command deploy:
        <code>uv sync --extra brain --extra channels --extra browse</code>, install + enable, health check.
      </p>
      <h3>Deploy</h3>
      <pre><code>{`# ON the VPS
git clone <your-fork> ~/mushegh       # or rsync -a ./ vps:~/mushegh
cp /path/to/your/.env ~/mushegh/.env
cd ~/mushegh/deploy/vps && bash install-brain.sh`}</code></pre>

      <h3>One scheduler owner</h3>
      <div className="callout warn">
        <span className="k">Run the brain OR the fully-local edge, not both against the same DB.</span>{" "}
        Each starts the reminder scheduler against the SQLite jobstore. Two owners = a daily reminder
        firing twice. In the standard split (brain on VPS, thin edge on the laptop) the brain owns the
        jobstore; the laptop edge connects as a client and doesn't.
      </div>

      <h3>Reachability & auth</h3>
      <ul>
        <li><strong>Loopback</strong> (default): <code>MUSHEGH_BRAIN_HOST=127.0.0.1</code>. No auth needed.</li>
        <li><strong>Exposed</strong>: set <code>MUSHEGH_BRAIN_HOST=0.0.0.0</code> AND a non-empty <code>MUSHEGH_API_AUTH_TOKEN</code>. Remote clients must present <code>Authorization: Bearer &lt;token&gt;</code> (native) or <code>?token=&lt;token&gt;</code> (browser / Siri Shortcut). Requests without it are refused.</li>
        <li><strong>Prefer a Tailnet</strong> (see <Link href="/networking">Networking</Link>): the bearer token guards the port, the overlay keeps it unroutable to the world.</li>
      </ul>

      <h3>Verify</h3>
      <pre><code>{`curl -fsS http://127.0.0.1:8766/healthz      # -> ok
sudo systemctl kill mushegh-brain             # restart proof: it returns within ~5s
journalctl -u mushegh-brain -f                # watch turns / reminders / proactive ticks`}</code></pre>

      <h2>2 · VPS ticker (Phase 4b)</h2>
      <p>
        <code>deploy/vps/mushegh_ticker.py</code> is a tiny APScheduler daemon. It owns{" "}
        <strong>recurring</strong> (daily) reminders so they fire even with the laptop off. Pushes via the
        same ntfy topic. Fully decoupled from the fleet — only knows ntfy + a local JSON file.
      </p>
      <pre><code>{`# ON the VPS
MUSHEGH_NTFY_TOPIC=afon-<your-unguessable-string> bash deploy/vps/install.sh
# Optional: MUSHEGH_TICKER_PORT=8770, MUSHEGH_TICKER_HOST=127.0.0.1,
#           MUSHEGH_TICKER_TOKEN=<shared bearer>, MUSHEGH_TICKER_TZ=Europe/Berlin`}</code></pre>
      <p>
        Point the edge at it:
      </p>
      <pre><code>{`MUSHEGH_TICKER_URL=http://127.0.0.1:8770
MUSHEGH_TICKER_TOKEN=        # match the ticker if you set one`}</code></pre>
      <p>
        After that, <code>set_reminder(daily=&quot;08:00&quot;, ...)</code> on the PC <strong>also</strong>{" "}
        registers the reminder on the ticker. <code>cancel_reminder</code> removes it from both.
        Unreachable ticker = graceful no-op.
      </p>

      <h2>3 · Live-integration check (weekly)</h2>
      <p>
        <code>deploy/vps/install-live-check.sh</code> registers a systemd user timer (Mon 07:30 UTC).
        It runs <code>bench/test_live_integrations.py</code> against every configured integration. On
        failure it speaks the failure to the owner via{" "}
        <code>python -m mushegh.brain.voice_io &quot;…&quot;</code> (ElevenLabs &rarr; ffmpeg
        libopus OGG &rarr; sendVoice via the <strong>Mushegh</strong> Telegram bot). If synthesis itself
        fails, falls back to a text push via the Telegram bot. First run on the live VPS caught
        Browserbase unconfigured (missing <code>browse</code> extra + playwright).
      </p>

      <h2>4 · Safe deploy from your laptop</h2>
      <p>
        <code>scripts/deploy_vps.sh</code> codifies the safe VPS deploy: runs the test suite FIRST, then
        syncs <code>src/mushegh</code> + <code>skills/</code> over SSH, then restarts the brain and
        health-checks. Push is blocked on any test failure.
      </p>
      <pre><code>{`# from the repo root
scripts/deploy_vps.sh
# Overrides:
#   MUSHEGH_VPS=other-user@host       MUSHEGH_VPS_DIR=/path/to/mushegh scripts/deploy_vps.sh`}</code></pre>
      <p>
        <code>.env</code>, sessions, voiceprint, audit, and backups live ONLY on the target — they
        are gitignored and never transferred.
      </p>

      <h2>5 · Pre-push gate</h2>
      <p>
        <code>scripts/githooks/pre-push</code> runs the suite before <code>git push</code> so a broken
        push is blocked locally. Register it once:
      </p>
      <pre><code>{`git config core.hooksPath scripts/githooks`}</code></pre>

      <h2>6 · Edge autostart (per-device)</h2>
      <p>
        One cross-platform installer registers the edge (and optional PC-control executor) to start at
        boot/login and stay alive (auto-restart on crash, no console window):
      </p>
      <pre><code>{`uv run python -m mushegh.edge.autostart install            # both services
uv run python -m mushegh.edge.autostart install edge        # just the voice edge
uv run python -m mushegh.edge.autostart install pc_agent    # brain-driven PC control
uv run python -m mushegh.edge.autostart status
uv run python -m mushegh.edge.autostart uninstall`}</code></pre>
      <table>
        <thead>
          <tr><th>OS</th><th>Mechanism</th></tr>
        </thead>
        <tbody>
          <tr><td>Windows</td><td>Scheduled Tasks (AtLogOn, pythonw.exe, RestartCount=999). <code>pc_agent</code> runs elevated (RunLevel=Highest) for true full control.</td></tr>
          <tr><td>macOS</td><td>LaunchAgents in <code>~/Library/LaunchAgents</code> with <code>RunAtLoad</code> + <code>KeepAlive</code></td></tr>
          <tr><td>Linux</td><td>systemd <code>--user</code> units + <code>loginctl enable-linger</code> so they start at boot, not at login</td></tr>
        </tbody>
      </table>
      <p>
        Each edge process is supervised by <code>edge/_supervisor.py</code>: it relaunches on any exit
        (crash or clean pipeline end) with backoff, and tees stdout/stderr to <code>logs/&lt;name&gt;.log</code>{" "}
        — so a <code>pythonw.exe</code> windowless run doesn't lose its log on crash.
      </p>

      <h2>7 · Single-snapshot deploy runbook</h2>
      <pre><code>{`# 1. First time (fresh VPS)
ssh openclaw@<vps>
git clone <your-fork> ~/mushegh
# copy .env from your laptop: scp .env openclaw@<vps>:~/mushegh/.env
cd ~/mushegh/deploy/vps && bash install-brain.sh
bash install.sh            # the ticker
bash install-live-check.sh # weekly voice-alert timer
exit

# 2. Every later deploy (from the laptop)
scripts/deploy_vps.sh

# 3. One-off VPS commands
ssh openclaw@<vps> 'journalctl --user -u mushegh-brain -n 100 --no-pager'`}</code></pre>

      <p style={{ marginTop: 22 }}>
        See <Link href="/security">Security</Link> &sect;11 for the operator-responsibility checklist
        you walk before going public.
      </p>
    </>
  );
}