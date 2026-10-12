import Link from "next/link";

export default function Configuration() {
  return (
    <>
      <h1>Configuration</h1>
      <p className="lead">
        Everything is driven by <code>MUSHEGH_</code>-prefixed environment variables in a local{" "}
        <code>.env</code>. Run <code>mushegh-setup</code> to generate it (the wizard validates every key
        live as you type it). <code>.env.example</code> documents every knob inline.
      </p>

      <div className="callout warn">
        <span className="k">Never commit <code>.env</code></span> — it's git-ignored. Keep your
        configured fork private if it carries personal data. See <Link href="/security">Security</Link>{" "}
        &sect;1 for the full list of files kept out of version control.
      </div>

      <h2>Core knobs (the deployment shape)</h2>
      <table>
        <thead>
          <tr><th>Variable</th><th>Purpose</th></tr>
        </thead>
        <tbody>
          <tr><td><code>MUSHEGH_STT_PROVIDER</code></td><td><code>deepgram</code> (cloud, fastest, multilingual EN/FR/DE/RU) / <code>whisper</code> (local, auto-detects 6 incl. Armenian + Ukrainian) / <code>moonshine</code> (local English, ~3&times; faster)</td></tr>
          <tr><td><code>MUSHEGH_TTS_PROVIDER</code></td><td><code>elevenlabs</code> (cloud, streaming) / <code>piper</code> (local, fast) / <code>kokoro</code> (local, higher quality)</td></tr>
          <tr><td><code>MUSHEGH_VOICE_LOCAL_FALLBACK</code></td><td>When the cloud provider can't be built, fall back to local. Never fail the pipeline.</td></tr>
          <tr><td><code>MUSHEGH_LLM_BACKEND</code></td><td>the reasoning LLM: <code>freellmapi</code> / <code>openai</code> / <code>ollama</code></td></tr>
          <tr><td><code>MUSHEGH_LLM_PRIMARY_MODEL</code> + <code>MUSHEGH_LLM_FALLBACK_MODELS</code></td><td>ordered failover chain; <code>groq:</code>/<code>cerebras:</code>/<code>ollama:</code> prefixes route by provider</td></tr>
          <tr><td><code>MUSHEGH_LLM_FAST_MODEL</code></td><td>tiny fast model prepended for snappier first words (optional)</td></tr>
          <tr><td><code>MUSHEGH_WAKE_WORDS</code></td><td>comma-list of phrases and/or trained <code>.onnx</code> paths</td></tr>
          <tr><td><code>MUSHEGH_VAULT_PATH</code></td><td>your Obsidian/Markdown notes folder (L3 memory)</td></tr>
          <tr><td><code>MUSHEGH_BRAIN_MODE</code></td><td><code>local</code> (in-process agent) / <code>remote</code> / <code>auto</code> (try VPS, fall back to local)</td></tr>
          <tr><td><code>MUSHEGH_BRAIN_HOST</code></td><td><code>127.0.0.1</code> single-machine, <code>0.0.0.0</code> for multi-device (requires the bearer token)</td></tr>
          <tr><td><code>MUSHEGH_API_AUTH_TOKEN</code></td><td>bearer token required off-loopback (wizard generates it)</td></tr>
          <tr><td><code>MUSHEGH_BRAIN_WS_URL</code></td><td>edge &rarr; brain, e.g. <code>ws://&lt;tailnet-ip&gt;:8765/voice</code></td></tr>
        </tbody>
      </table>

      <h2>Voice-loop knobs (the deep page)</h2>
      <table>
        <thead>
          <tr><th>Variable</th><th>Purpose</th><th>Default</th></tr>
        </thead>
        <tbody>
          <tr><td><code>MUSHEGH_WAKE_WORD_THRESHOLD</code></td><td>openWakeWord detection confidence 0…1</td><td><code>0.5</code></td></tr>
          <tr><td><code>MUSHEGH_WAKE_LISTEN_WINDOW_S</code></td><td>mic stays open this long after a wake</td><td><code>8.0</code></td></tr>
          <tr><td><code>MUSHEGH_WAKE_BARGE_IN_ENABLED</code></td><td>wake word interrupts Mushegh mid-sentence on speakers (no AEC)</td><td><code>true</code></td></tr>
          <tr><td><code>MUSHEGH_WAKE_ACK_PHRASE</code></td><td>pipe-separated spoken acks (e.g. <code>Yes, sir?|I'm listening, sir.</code>)</td><td>varied defaults</td></tr>
          <tr><td><code>MUSHEGH_LISTENING_PULSE</code></td><td>one soft ping at edge startup, then silent</td><td><code>true</code></td></tr>
          <tr><td><code>MUSHEGH_DEEPGRAM_ENDPOINTING_MS</code></td><td>trailing-silence before Deepgram finalises an utterance</td><td><code>300</code></td></tr>
          <tr><td><code>MUSHEGH_VAD_ENABLED</code></td><td>Silero VAD in the pipeline</td><td><code>true</code></td></tr>
          <tr><td><code>MUSHEGH_BARGE_IN_MODE</code></td><td><code>auto</code> (private endpoint &rarr; on, speakers &rarr; off) / <code>on</code> / <code>off</code></td><td><code>auto</code></td></tr>
          <tr><td><code>MUSHEGH_AUDIO_OUTPUT_DEVICE</code> + <code>_INDEX</code></td><td>pin output by name fragment or PyAudio index (HFP headsets need the index)</td><td>OS default; auto-route to AirPods on by default</td></tr>
          <tr><td><code>MUSHEGH_AUDIO_INPUT_DEVICE_NAME</code></td><td>pin INPUT by name (survives BT reconnects — indices go stale)</td><td>OS default</td></tr>
          <tr><td><code>MUSHEGH_AUDIO_OUT_SAMPLE_RATE</code></td><td>match the output device (HFP = 16000)</td><td><code>22050</code></td></tr>
          <tr><td><code>MUSHEGH_DEVICE_HINT</code></td><td>declare how the OWNER hears you: <code>headphones</code>, <code>airpods</code>, <code>glasses</code>, <code>phone-headphones</code>, <code>phone-speaker</code>, …</td><td>(blank = classify the local output)</td></tr>
          <tr><td><code>MUSHEGH_MIC_GAIN</code></td><td>software boost for quiet laptop arrays; pair with raising the OS mic level</td><td><code>1.0</code></td></tr>
          <tr><td><code>MUSHEGH_SPEAKER_ID_ENABLED</code></td><td>respond only to your enrolled voice (off until enrolled)</td><td><code>false</code></td></tr>
          <tr><td><code>MUSHEGH_SPEAKER_THRESHOLD</code></td><td>ECAPA cosine accept threshold</td><td><code>0.25</code></td></tr>
          <tr><td><code>MUSHEGH_TTFW_TARGET_MS</code></td><td>Goal surfaced in <code>bench/efficiency_report.py</code></td><td><code>1200</code></td></tr>
        </tbody>
      </table>

      <h2>Safety, memory, behaviour</h2>
      <table>
        <thead>
          <tr><th>Variable</th><th>Purpose</th></tr>
        </thead>
        <tbody>
          <tr><td><code>MUSHEGH_VAULT_WRITABLE</code></td><td><code>true</code> only on the host that <em>owns</em> the vault; enables <code>write_vault</code>. Off on the laptop (its mirror is clobbered by the one-way sync).</td></tr>
          <tr><td><code>MUSHEGH_SESSION_IDLE_RESET_MINUTES</code></td><td>after this idle gap the brain journals the prior conversation and clears working memory (durable memory kept). <code>0</code> disables.</td></tr>
          <tr><td><code>MUSHEGH_PROACTIVE_ENABLED</code></td><td>allow unprompted speech (within budget + quiet hours)</td></tr>
          <tr><td><code>MUSHEGH_PROACTIVE_QUIET_HOURS</code></td><td>no unprompted voice in this window (local time, <code>HH:MM-HH:MM</code>)</td></tr>
          <tr><td><code>MUSHEGH_PROACTIVE_DAILY_BUDGET</code></td><td>max unprompted interjections per day</td></tr>
          <tr><td><code>MUSHEGH_PROACTIVE_RELEVANCE_THRESHOLD</code></td><td>only signals with urgency &ge; this fire</td></tr>
          <tr><td><code>MUSHEGH_PROACTIVE_QUIET_OVERRIDE_URGENCY</code></td><td>only <em>this</em> urgent reaches you in quiet hours — as a silent push, never spoken</td></tr>
          <tr><td><code>MUSHEGH_BACKLOG_ENABLED</code></td><td>opt-in to the daily autonomous Notion tasks backlog pass</td></tr>
          <tr><td><code>MUSHEGH_FLEET_AUTHORIZED</code></td><td>allow consulting the optional external fleet (off by default)</td></tr>
          <tr><td><code>MUSHEGH_SYSTEM_PROTECTED_PATHS</code></td><td>paths refused for <code>file_op</code> delete (defence against catastrophic rm)</td></tr>
          <tr><td><code>MUSHEGH_PROTOCOL_*_PASSWORD</code></td><td>passwords for the <Link href="/protocols">eight privileged routines</Link> (wizard generates them)</td></tr>
          <tr><td><code>MUSHEGH_COMPOSIO_API_KEY</code> + <code>MUSHEGH_COMPOSIO_USER_ID</code></td><td><Link href="/apps">Composio</Link> via MCP for the 250+ app breadth layer</td></tr>
          <tr><td><code>MUSHEGH_MCP_SERVERS</code></td><td>inline JSON (or path to JSON) for the MCP servers to launch — nothing launched unless listed</td></tr>
          <tr><td><code>MUSHEGH_MYNEWS_URL</code></td><td>enable the owner's RSS morning-brief proactive signal</td></tr>
          <tr><td><code>MUSHEGH_HOME_LOCATION</code></td><td>the place “what's the weather” defaults to (overridable at runtime via <code>runtime_prefs.json</code>)</td></tr>
          <tr><td><code>MUSHEGH_USER_TZ</code></td><td>IANA timezone (e.g. <code>America/New_York</code>); drives time, scheduling, calendar</td></tr>
          <tr><td><code>MUSHEGH_UNDERSTOOD_LANGUAGES</code> + <code>MUSHEGH_REPLY_LANGUAGE</code></td><td>what he can understand vs. what he always replies in</td></tr>
          <tr><td><code>MUSHEGH_ASSISTANT_NAME</code> + <code>MUSHEGH_USER_NAME</code> + <code>MUSHEGH_USER_ADDRESS</code></td><td>make the codebase yours — fill the persona tokens from <Link href="/personalize">Personalize</Link></td></tr>
        </tbody>
      </table>

      <h2>Telegram model + the bot split</h2>
      <table>
        <thead><tr><th>Variable</th><th>Purpose</th></tr></thead>
        <tbody>
          <tr><td><code>MUSHEGH_TELEGRAM_BRIDGE_BOT_TOKEN</code></td><td>DEDICATED bridge bot for DM-ing Mushegh from any device (separate from <code>_BOT_TOKEN</code>) — see <Link href="/bots">Bots</Link></td></tr>
          <tr><td><code>MUSHEGH_TELEGRAM_BOT_TOKEN</code></td><td>send-token for <code>send_telegram</code> and the Mushegh outbound bot</td></tr>
          <tr><td><code>MUSHEGH_TELEGRAM_DEFAULT_CHAT</code></td><td>your chat id, the default recipient</td></tr>
          <tr><td><code>MUSHEGH_TELEGRAM_PLAYLIST_CHAT</code> + <code>MUSHEGH_TELEGRAM_MUSIC_ROOM_CHAT</code></td><td>personal playlist chat + the group for live music-room streaming</td></tr>
          <tr><td><code>MUSHEGH_TELEGRAM_MUSIC_TARGET</code></td><td>where the chosen track is sent (<code>me</code> = Saved Messages &rarr; phone)</td></tr>
        </tbody>
      </table>

      <p>
        See the <Link href="/setup">Setup & keys</Link> page for the full table per integration, the{" "}
        <Link href="/voice">Voice pipeline</Link> page for the voice-specific knobs, and{" "}
        <Link href="/security">Security</Link> for what is kept out of git.
      </p>
    </>
  );
}