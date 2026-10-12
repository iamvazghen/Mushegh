import Link from "next/link";

export default function QuickStart() {
  return (
    <>
      <h1>Quick start</h1>
      <p className="lead">Install, configure with the wizard, and talk to Mushegh in about 5 minutes.</p>

      <p>
        Requires <strong>Python 3.11+</strong> and{" "}
        <a href="https://github.com/astral-sh/uv" target="_blank" rel="noreferrer">
          uv
        </a>
        . For a multi-device deployment you also need <Link href="/networking">Tailscale</Link> on
        every device.
      </p>

      <h2>1 · Clone & install</h2>
      <pre>
        <code>{`git clone https://github.com/iamvazghen/Mushegh Mushegh
cd Mushegh

# Install the base + the stack you want (also installs the \`mushegh-setup\` CLI).
# Cloud quality voice + 24/7 brain + channels + speaker-id + dev tools:
uv sync --extra edge --extra cloud-voice --extra brain --extra channels --extra identity --extra dev
#   for a 100% local/offline voice stack: drop cloud-voice, add local-voice
#   for VPS brain + the cloud browser: add browse`}</code>
      </pre>
      <div className="callout warn">
        <span className="k">Note.</span> <code>uv sync</code> prunes extras you don't list —
        install the full set you intend to use in one command.
      </div>

      <h2 id="wizard">2 · Run the setup wizard</h2>
      <pre>
        <code>uv run mushegh-setup</code>
      </pre>
      <p>
        A terminal UI (Rich with a <strong>MUSHEGH</strong> banner; falls back to plain text) walks
        you through eight steps and writes a ready <code>.env</code>. It never prints a secret back,
        backs up an existing <code>.env</code>, validates every key live against its provider as you
        type it, and auto-generates the brain auth token and all eight protocol passwords.
      </p>
      <table>
        <thead>
          <tr>
            <th>Step</th>
            <th>What it sets</th>
          </tr>
        </thead>
        <tbody>
          <tr><td>1 · Identity</td><td>display name, owner name, honorific, wake phrase(s), understood + reply languages</td></tr>
          <tr><td>2 · Voice</td><td>cloud (ElevenLabs + Deepgram) or local (Piper/Kokoro + Whisper/Moonshine)</td></tr>
          <tr><td>3 · Brain</td><td>LLM backend: freellmapi / openai-compatible / local Ollama + optional Groq / Cerebras keys</td></tr>
          <tr><td>4 · Knowledge</td><td>path to your Obsidian/Markdown notes (L3 memory)</td></tr>
          <tr><td>5 · Deployment</td><td><code>single</code> (loopback) or <code>vps</code> (binds 0.0.0.0 + token)</td></tr>
          <tr><td>6 · Security</td><td>generates strong, unique passwords for all 8 privileged protocols</td></tr>
          <tr><td>7 · Integrations</td><td>optional: Telegram, Tavily, Google, Notion, ntfy</td></tr>
          <tr><td>8 · Behaviour</td><td>proactivity on/off; fleet stays off by default</td></tr>
        </tbody>
      </table>
      <p>
        Re-running the wizard is idempotent: your current values become the defaults, Enter keeps them,
        and the password-bearing keys are rotated <strong>only when blank</strong>. Existing device
        tokens survive.
      </p>

      <h2>3 · Verify</h2>
      <pre>
        <code>{`uv run python bench/run_all_tests.py     # the single gate — should be all green
uv run python bench/efficiency_report.py # hot-path latency vs targets
uv run python bench/check_config.py      # which keys are set
uv run python bench/test_live_integrations.py  # exercises the keys you actually set`}</code>
      </pre>
      <div className="callout">
        <span className="k">Publish gate.</span> Keep your repo <strong>private</strong> until the
        suite is green and the efficiency report meets its targets.
      </div>

      <h2>4 · Talk to it</h2>
      <pre>
        <code>{`# Local voice loop on this machine:
uv run python -m mushegh.edge.assistant

# …or the shared 24/7 brain (for phone/glasses, over your tailnet):
uv run python -m mushegh.brain.server`}</code>
      </pre>
      <p>
        Say your wake phrase, then a command. Mushegh acks the moment he hears the wake word
        (<em>“Yes, sir?”</em>) so you know the edge is hot. See <Link href="/voice">Voice pipeline</Link>{" "}
        for the full path and every knob.
      </p>

      <h2>5 · Make it 24/7</h2>
      <pre>
        <code>{`# Edge autostarts on every login / boot (Windows Task Scheduler / launchd / systemd):
uv run python -m mushegh.edge.autostart install

# On the always-on host, deploy the brain + ticker + weekly voice-alert:
# (see the Deployment page for the full runbook)
ssh openclaw@<vps>
cd ~/mushegh/deploy/vps && bash install-brain.sh
bash install.sh            # the ticker
bash install-live-check.sh # weekly voice-alert timer`}</code>
      </pre>

      <h2>6 · Finish setup</h2>
      <p>
        <Link href="/features">Features</Link> is the full capability tour, <Link href="/tools">Tool
        reference</Link> is the 80-tool inventory, <Link href="/personalize">Personalize</Link> shapes
        the voice + persona from config, and <Link href="/security">Security</Link> is the model to
        read before you deploy. Edit <code>personality/mushegh.md</code> to make the assistant yours.
      </p>
    </>
  );
}