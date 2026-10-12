import Link from "next/link";

export default function InstallRun() {
  return (
    <>
      <h1>Install & run Mushegh</h1>
      <p className="lead">
        The complete command reference: install the stack you want, walk the setup wizard, switch on
        every capability, then run Mushegh once — or 24/7 on every device.
      </p>
      <p>
        This page is the “what do I actually type” companion to{" "}
        <Link href="/quickstart">Quick start</Link> (the 5-minute path) and{" "}
        <Link href="/setup">Setup & keys</Link> (where each key comes from). All commands run from
        the repo root.
      </p>

      <h2 id="install">1 · Install the stack</h2>
      <p>
        <code>uv sync</code> installs only the extras you name and <strong>prunes the rest</strong>, so
        list the full set you intend to use in one command. The <code>mushegh-setup</code> wizard is
        installed with any set.
      </p>
      <pre><code>{`git clone https://github.com/iamvazghen/OpenWatari mushegh
cd mushegh

# Everything (cloud voice + 24/7 brain + channels + speaker-ID + dev tools + cloud browser):
uv sync --extra edge --extra cloud-voice --extra brain --extra channels --extra identity --extra browse --extra dev

# 100% local / offline voice instead of cloud: drop cloud-voice, add local-voice
uv sync --extra edge --extra local-voice --extra brain --extra channels --extra identity`}</code></pre>
      <table>
        <thead><tr><th>Extra</th><th>Turns on</th></tr></thead>
        <tbody>
          <tr><td><code>edge</code></td><td>the device loop: mic, wake word, VAD, audio I/O</td></tr>
          <tr><td><code>cloud-voice</code></td><td>Deepgram STT + ElevenLabs TTS (fast, cloud)</td></tr>
          <tr><td><code>local-voice</code></td><td>Whisper / Moonshine STT + Piper / Kokoro TTS (no keys, offline)</td></tr>
          <tr><td><code>brain</code></td><td>the LLM agent loop, tools, memory L1–L5, scheduler</td></tr>
          <tr><td><code>channels</code></td><td>Telegram, Gmail, Calendar, Notion, ntfy push</td></tr>
          <tr><td><code>browse</code></td><td>the agentic web browser (local + Browserbase)</td></tr>
          <tr><td><code>identity</code></td><td>speaker-ID — obey only your enrolled voice</td></tr>
          <tr><td><code>dev</code></td><td>the test suite + benchmarks</td></tr>
        </tbody>
      </table>

      <h2 id="wizard">2 · Run the setup wizard</h2>
      <pre><code>uv run mushegh-setup</code></pre>
      <p>
        A terminal UI walks every decision and writes a ready <code>.env</code>. It{" "}
        <strong>never prints a secret back</strong>, backs up an existing <code>.env</code>, validates
        every key live against its provider as you type it, and auto-generates your{" "}
        <code>MUSHEGH_API_AUTH_TOKEN</code> and all eight{" "}
        <code>MUSHEGH_PROTOCOL_*_PASSWORD</code> values — you don't fetch those anywhere.
      </p>
      <table>
        <thead><tr><th>Step</th><th>It asks</th><th>Typical answer</th></tr></thead>
        <tbody>
          <tr><td>1 · Identity</td><td>display name, owner name, honorific, understood + reply languages, wake phrase</td><td>your name + wake word like <code>hey afon</code></td></tr>
          <tr><td>2 · Voice</td><td>cloud or local</td><td><code>cloud</code> = Deepgram + ElevenLabs keys; <code>local</code> = no keys</td></tr>
          <tr><td>3 · Brain</td><td>LLM backend + optional Groq/Cerebras</td><td>freellmapi by default; OpenAI or local Ollama; <code>groq:</code>-prefixed for snappy voice</td></tr>
          <tr><td>4 · Knowledge</td><td>notes folder for L3 memory</td><td>your Obsidian/Markdown path</td></tr>
          <tr><td>5 · Deployment</td><td><code>single</code> or <code>vps</code></td><td><code>single</code> = loopback; <code>vps</code> = binds 0.0.0.0 + token for phones/glasses</td></tr>
          <tr><td>6 · Security</td><td>(generated)</td><td>the 8 protocol passwords — kept across re-runs</td></tr>
          <tr><td>7 · Integrations</td><td>Telegram, Tavily, Google, Notion, ntfy</td><td>fill the ones you want; all optional</td></tr>
          <tr><td>8 · Behaviour</td><td>proactivity on/off</td><td>your call; fleet stays off by default</td></tr>
        </tbody>
      </table>
      <div className="callout">
        <span className="k">Re-run any time.</span> <code>mushegh-setup</code> is idempotent — run it
        again to change an answer; it backs up the old <code>.env</code> first. Or edit{" "}
        <code>.env</code> by hand (every key is prefixed <code>MUSHEGH_</code>; see{" "}
        <Link href="/setup">Setup & keys</Link>).
      </div>

      <h2 id="enable">3 · Switch on each capability</h2>
      <p>Everything degrades gracefully — do only the ones you want. Each is a one-time step.</p>
      <pre><code>{`# Speaker-ID — record your voiceprint, then only you are obeyed
uv sync --extra identity
uv run python bench/enroll_voice.py --script "to-read-script.md"
#   then set MUSHEGH_SPEAKER_ID_ENABLED=true in .env

# Telegram — one-time login, writes a reusable session file
uv run python bench/telegram_login.py

# Gmail + Calendar — one-time OAuth, writes the refresh token
uv run python bench/google_login.py

# Custom wake word — train a free openWakeWord model (no API key)
# See skills/.../wake-word training notes; output goes in MUSHEGH_WAKE_WORDS as a .onnx path.

# Semantic recall (L5, optional) — keyword fallback if not installed
# Default now uses Jina embeddings API when MUSHEGH_JINA_API_KEY is set, no torch needed.
# Or fully local: uv pip install sentence-transformers  (~1GB model, first use)
`}</code></pre>
      <div className="callout">
        <span className="k">Check what's live.</span> <code>uv run python bench/check_config.py</code>{" "}
        prints which keys are set; <code>uv run python bench/test_live_integrations.py</code> actually
        exercises the ones you configured.
      </div>

      <h2 id="run">4 · Run Mushegh</h2>
      <p>The core processes. On one machine run both; across devices the brain lives on the always-on host.</p>
      <pre><code>{`# The voice edge (mic + wake word + STT/TTS) on this device:
uv run python -m mushegh.edge.assistant

# The shared 24/7 brain (LLM, tools, memory, scheduler) — for phones/glasses over your tailnet:
uv run python -m mushegh.brain.server

# Optional — let Mushegh control this PC (open apps, type, click):
uv run python -m mushegh.edge.pc_agent

# Fire a one-shot voice note from the CLI (ElevenLabs → ffmpeg OGG → Telegram sendVoice):
uv run python -m mushegh.brain.voice_io "Sir, the briefing is ready."`}</code></pre>
      <div className="callout warn">
        <span className="k">Brain first.</span> If the edge is configured for a remote brain
        (<code>vps</code> mode), start <code>brain.server</code> before <code>edge.assistant</code> so
        the edge links on boot. The edge auto-reconnects if the brain restarts (75s ping timeout,
        exponential backoff).
      </div>

      <h2 id="247">5 · Run it 24/7 (autostart)</h2>
      <p>
        One cross-platform installer registers Mushegh to start at boot/login and stay alive —
        Scheduled Tasks on Windows, a launchd LaunchAgent on macOS, a systemd <code>--user</code> unit
        on Linux. Auto-restart on crash, no console window. <code>pc_agent</code> runs elevated so the
        brain gets true full control.
      </p>
      <pre><code>{`uv run python -m mushegh.edge.autostart install      # edge + pc_agent, start at login
uv run python -m mushegh.edge.autostart install edge  # just the voice edge
uv run python -m mushegh.edge.autostart install pc_agent  # just the PC executor
uv run python -m mushegh.edge.autostart status
uv run python -m mushegh.edge.autostart uninstall`}</code></pre>
      <p>
        Each edge process is supervised by <code>edge/_supervisor.py</code>: it relaunches on any
        exit (crash or clean pipeline end) and tees stdout/stderr to{" "}
        <code>logs/&lt;name&gt;.log</code>.
      </p>

      <p>
        On the always-on host, deploy the brain + ticker + weekly voice-alert with the VPS scripts in{" "}
        <Link href="/deployment">Deployment</Link>.
      </p>

      <h2 id="verify">6 · Verify</h2>
      <pre><code>{`uv run python bench/run_all_tests.py        # the single gate — all green (offline; SKIP != FAIL)
uv run python bench/efficiency_report.py    # hot-path latency vs targets`}</code></pre>
      <div className="callout">
        <span className="k">Publish gate.</span> Keep your repo <strong>private</strong> until the suite
        is green and the efficiency report meets its targets.
      </div>

      <h2 id="check">7 · Is it actually listening?</h2>
      <p>
        Say your wake phrase, then a command (“hey afon, what time is it?”). The
        listening ping is <strong>one soft tone at startup</strong>, then silent — it isn't a
        constant sound. If nothing reacts, tail the edge log: every detection prints{" "}
        <code>wake: 'hey_jarvis' detected</code>.
      </p>
      <pre><code>{`# Windows
Get-Content logs/edge.log -Tail 20 -Wait
# macOS / Linux
tail -f logs/edge.log`}</code></pre>
      <table>
        <thead><tr><th>Symptom in the log</th><th>Cause & fix</th></tr></thead>
        <tbody>
          <tr><td><code>no audio received</code> / no <code>wake … detected</code></td><td>two edges are fighting for the mic, or the wrong default input device. Stop every Mushegh process, confirm one edge, restart it. Pin by name with <code>MUSHEGH_AUDIO_INPUT_DEVICE_NAME</code> (survives Bluetooth reconnects).</td></tr>
          <tr><td><code>timed out during opening handshake</code> (Deepgram/ElevenLabs)</td><td>a network blip reaching the cloud voice services — it auto-retries. Persistent? Check connectivity or switch to the local voice stack.</td></tr>
          <tr><td><code>brain link: connected</code> never appears</td><td>the brain isn't running or the host/token is wrong — start <code>brain.server</code>, check the tailnet IP.</td></tr>
        </tbody>
      </table>
      <p>
        Next: <Link href="/personalize">personalize</Link> the voice and persona, wire{" "}
        <Link href="/integrations">integrations</Link>, and walk the{" "}
        <Link href="/production">production checklist</Link> before go-live.
      </p>
    </>
  );
}