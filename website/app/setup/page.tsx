import Link from "next/link";

export default function Setup() {
  return (
    <>
      <h1>Setup & keys — from <code>git clone</code> to talking</h1>
      <p className="lead">
        Everything a developer needs to stand up their own Mushegh: install, get every key, integrate
        each component, and run the tests.
      </p>

      <h2>0 · Prerequisites</h2>
      <ul>
        <li><strong>Python 3.11+</strong> and <a href="https://github.com/astral-sh/uv" target="_blank" rel="noreferrer">uv</a>.</li>
        <li><strong>Node 18+</strong> only if you also build this docs site.</li>
        <li><strong>Tailscale</strong> on every device for a multi-device deploy (see <Link href="/networking">Networking</Link>).</li>
        <li>An always-on host (a small Linux VPS) if you want the 24/7 brain.</li>
      </ul>

      <h2>1 · Clone & install</h2>
      <pre><code>{`git clone https://github.com/iamvazghen/OpenWatari mushegh
cd mushegh
uv sync --extra edge --extra cloud-voice --extra brain --extra channels --extra identity --extra dev
uv run mushegh-setup        # interactive .env generator`}</code></pre>

      <h2>2 · Get the keys</h2>
      <p>
        All keys live in <code>.env</code> (prefix <code>MUSHEGH_</code>). Everything degrades
        gracefully — set only what you want. <strong>Required</strong> to function: a voice (TTS),
        an ear (STT), a brain (LLM), and the vault path.
      </p>
      <table>
        <thead><tr><th>Component</th><th>Key(s)</th><th>Where to get it</th><th>Tier</th></tr></thead>
        <tbody>
          <tr><td>TTS voice</td><td><code>MUSHEGH_ELEVENLABS_API_KEY</code>, <code>_VOICE_ID</code></td><td>elevenlabs.io → Profile → API key; pick a voice, copy its ID (or use local Piper/Kokoro, no key)</td><td>Required</td></tr>
          <tr><td>STT</td><td><code>MUSHEGH_DEEPGRAM_API_KEY</code></td><td>deepgram.com (free tier). For Armenian/Ukrainian use local Whisper instead (no key)</td><td>Required</td></tr>
          <tr><td>Brain LLM</td><td><code>MUSHEGH_FREELLMAPI_BASE_URL</code> + <code>_API_KEY</code></td><td>any OpenAI-compatible endpoint: a free proxy, OpenAI (<code>api.openai.com/v1</code>), or local Ollama</td><td>Required</td></tr>
          <tr><td>LLM primary (direct, fastest)</td><td><code>MUSHEGH_GROQ_API_KEY</code></td><td>console.groq.com — free tier. Prefix primary as <code>groq:&lt;model&gt;</code> for ~0.3s TTFT</td><td>Recommended</td></tr>
          <tr><td>LLM alternate (different pool)</td><td><code>MUSHEGH_CEREBRAS_API_KEY</code></td><td>cloud.cerebras.ai — free tier. ~2000 tok/s, separate rate-limit pool</td><td>Recommended</td></tr>
          <tr><td>Vault (L3 memory)</td><td><code>MUSHEGH_VAULT_PATH</code></td><td>path to your Obsidian/Markdown folder; <code>MUSHEGH_VAULT_WRITABLE=true</code> only on the host that owns it</td><td>Required</td></tr>
          <tr><td>Web search</td><td><code>MUSHEGH_TAVILY_API_KEY</code></td><td>tavily.com (scraping uses keyless Jina Reader; Jina key raises limits)</td><td>Recommended</td></tr>
          <tr><td>Telegram</td><td><code>MUSHEGH_TELEGRAM_API_ID</code>, <code>_API_HASH</code>, <code>_BOT_TOKEN</code>, <code>_BRIDGE_BOT_TOKEN</code>, <code>_PHONE</code></td><td>my.telegram.org (api id/hash) + @BotFather (bot tokens — send and bridge are separate) + then <code>uv run python bench/telegram_login.py</code> once</td><td>Recommended</td></tr>
          <tr><td>Gmail + Calendar</td><td><code>MUSHEGH_GOOGLE_CLIENT_ID</code>, <code>_SECRET</code>, <code>_REFRESH_TOKEN</code></td><td>console.cloud.google.com: enable Gmail + Calendar APIs, make a Web OAuth client, add the redirect, then <code>uv run python bench/google_login.py</code></td><td>Recommended</td></tr>
          <tr><td>Notion</td><td><code>MUSHEGH_NOTION_TOKEN</code></td><td>notion.so/my-integrations → internal integration; share the pages you want it to touch</td><td>Optional</td></tr>
          <tr><td>Home Assistant</td><td><code>MUSHEGH_HA_URL</code>, <code>MUSHEGH_HA_TOKEN</code></td><td>HA → Profile → Security → long-lived access token</td><td>Optional</td></tr>
          <tr><td>Phone push</td><td><code>MUSHEGH_NTFY_TOPIC</code></td><td>pick an unguessable string; subscribe to it in the ntfy app</td><td>Recommended</td></tr>
          <tr><td>Self-improvement push</td><td><code>MUSHEGH_GITHUB_TOKEN</code>, <code>MUSHEGH_GITHUB_REPO</code></td><td>github.com/settings/tokens → fine-grained PAT, Contents: read/write on your repo</td><td>Optional</td></tr>
          <tr><td>Cloud browser</td><td><code>MUSHEGH_BROWSERBASE_API_KEY</code>, <code>_PROJECT_ID</code></td><td>browserbase.com (the local visible browser needs no key)</td><td>Optional</td></tr>
          <tr><td>Custom wake phrase</td><td>—</td><td>No key of any kind. The pre-trained phrases ship with openWakeWord; a custom phrase is your own <code>.onnx</code> model, trained free.</td><td>Optional</td></tr>
          <tr><td>External fleet (optional)</td><td><code>MUSHEGH_OPENCLAW_GATEWAY_URL</code>, <code>MUSHEGH_OPENCLAW_TOKEN</code>, <code>MUSHEGH_FLEET_AUTHORIZED=true</code></td><td>only if you run a gateway; stays off otherwise</td><td>Optional</td></tr>
          <tr><td>MCP servers</td><td><code>MUSHEGH_MCP_SERVERS</code> (inline JSON or path)</td><td>e.g. Composio's MCP server URL — see <Link href="/apps">External apps</Link></td><td>Optional</td></tr>
        </tbody>
      </table>
      <div className="callout">
        The wizard auto-generates the multi-device <code>MUSHEGH_API_AUTH_TOKEN</code> and all eight{" "}
        <code>MUSHEGH_PROTOCOL_*_PASSWORD</code> values for you — you don't fetch those anywhere.
      </div>

      <h2>3 · Integrate the components</h2>
      <ul>
        <li><strong>Vault</strong> — point <code>MUSHEGH_VAULT_PATH</code> at your notes; it's validated at startup (3 retries w/ short grace to ride out a 15-min sync).</li>
        <li><strong>Telegram / Google</strong> — run the one-time login helpers in <code>bench/</code> (they print a token or create a session file).</li>
        <li><strong>Semantic recall (optional L5)</strong> — default uses Jina embeddings API if <code>MUSHEGH_JINA_API_KEY</code> is set; OR fully local: <code>uv pip install sentence-transformers</code> (~1GB model).</li>
        <li><strong>Multi-device</strong> — Tailscale on every device, then set <code>MUSHEGH_BRAIN_HOST=0.0.0.0</code> and the brain WS URL to the tailnet IP (the wizard's <em>vps</em> mode does this).</li>
        <li><strong>Voice enrollment</strong> — <code>uv run python bench/enroll_voice.py --script &quot;to-read-script.md&quot;</code>, then <code>MUSHEGH_SPEAKER_ID_ENABLED=true</code>.</li>
        <li><strong>Custom wake word</strong> — train an <code>.onnx</code> model (free; no API key) or use Porcupine with a Picovoice key. List the path or phrase in <code>MUSHEGH_WAKE_WORDS</code>.</li>
      </ul>

      <h2>4 · Run the tests</h2>
      <pre><code>{`uv run python bench/run_all_tests.py        # the single gate (offline; SKIP != FAIL)
uv run python bench/check_config.py         # which keys are set
uv run python bench/efficiency_report.py    # hot-path latency vs targets
uv run python bench/test_live_integrations.py  # exercises the keys you actually set`}</code></pre>

      <h2>5 · Run it</h2>
      <pre><code>{`uv run python -m mushegh.edge.assistant      # local voice loop
uv run python -m mushegh.brain.server        # the shared 24/7 brain (phone/glasses)`}</code></pre>
      <p>
        Then see <Link href="/production">Production readiness</Link> for the go-live checklist, edit{" "}
        <code>personality/mushegh.md</code> to make it yours, and skim{" "}
        <Link href="/voice">Voice pipeline</Link> if anything in the voice loop doesn't feel right.
      </p>
    </>
  );
}