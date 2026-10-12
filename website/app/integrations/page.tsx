import Link from "next/link";

export default function Integrations() {
  return (
    <>
      <h1>Integrations & enabling tools</h1>
      <p className="lead">
        Every capability is wired and tested; you switch each one on by adding its key/credential.
        Anything you skip <strong>degrades gracefully</strong> — Mushegh just says “that
        isn't configured yet”. Set values in <code>.env</code> (or answer the{" "}
        <Link href="/quickstart">setup wizard</Link>).
      </p>

      <div className="callout">
        <span className="k">How enabling works.</span> Tools register at startup regardless; a tool
        becomes <em>usable</em> when its credential is present. So you can enable integrations one at a
        time, restart the brain, and they light up. Reads are frictionless; outward/destructive
        actions (send, delete, spend, lock, write to external apps) are always confirm-gated — see{" "}
        <Link href="/security">Security</Link>.
      </div>

      <p>
        <strong>240+ other apps</strong> (Slack, GitHub, Linear, Drive, Stripe, Airtable, HubSpot, …)
        reach Mushegh through <Link href="/apps">MCP / Composio</Link> with no new code.
      </p>

      <h2 id="telegram">Telegram — read DMs, send, voice notes</h2>
      <p>
        Telegram has up to <strong>three roles</strong> in Mushegh; add only what you want. See{" "}
        <Link href="/bots">Bots & send-paths</Link> for the full token model + the Mushegh-vs-ispir
        bot split.
      </p>

      <h3>a) Read your DMs (Telethon user client)</h3>
      <p>The Bot API can't read your DMs, so reading needs a one-time user login.</p>
      <ol>
        <li>Get an <strong>api_id</strong> + <strong>api_hash</strong> at <a href="https://my.telegram.org" target="_blank" rel="noreferrer">my.telegram.org</a> → API development tools.</li>
        <li>In <code>.env</code>:
          <pre><code>{`MUSHEGH_TELEGRAM_API_ID=...
MUSHEGH_TELEGRAM_API_HASH=...
MUSHEGH_TELEGRAM_PHONE=+15551234567   # your number, for the one-time sign-in`}</code></pre>
        </li>
        <li>One-time interactive login (writes the Telethon session named by <code>MUSHEGH_TELEGRAM_SESSION</code>, default <code>mushegh</code>):
          <pre><code>{`uv run python bench/telegram_login.py   # enter the code Telegram texts you`}</code></pre>
        </li>
      </ol>
      <p>Verify: <em>“read me my last messages with Anna”</em> (reads without marking them seen),
        <em> “any unread Telegram?”</em>. Tools: <code>check_telegram</code>, <code>read_chat</code>, <code>mark_telegram</code>.</p>

      <h3>b) DM Mushegh 24/7 (a dedicated bridge bot)</h3>
      <p>
        So you can text Mushegh from any device, give it its <strong>own</strong> bot — separate
        from any other bot you run (two pollers on one token steal each other's messages). Used
        ONLY for the assistant; the ispir / OpenClaw fleet bot is fleet-only.
      </p>
      <ol>
        <li>In Telegram, message <a href="https://t.me/BotFather" target="_blank" rel="noreferrer">@BotFather</a> → <code>/newbot</code> → copy the token.</li>
        <li><pre><code>{`MUSHEGH_TELEGRAM_BRIDGE_BOT_TOKEN=123456:ABC...`}</code></pre></li>
      </ol>
      <p>
        Now DM that bot — the same shared brain answers, so Telegram and voice share one memory.
        Outbound is <strong>a voice note by default</strong> (ElevenLabs &rarr; ffmpeg libopus OGG
        &rarr; <code>sendVoice</code>); text only when synthesis itself fails.
      </p>

      <h3>c) Send messages / GIFs / files (bot)</h3>
      <pre><code>{`MUSHEGH_TELEGRAM_BOT_TOKEN=...        # can be the same as the bridge bot; the Mushegh one in any case
MUSHEGH_TELEGRAM_DEFAULT_CHAT=...     # your chat id, the default recipient`}</code></pre>
      <p>Verify: <em>“tell Anna I'll be five minutes late”</em> (it confirms first). GIFs: <em>“@gif panda”</em>.</p>

      <h2 id="music-room">Music Room — stream music live into a group call</h2>
      <p>
        The Music Room plays a track <strong>live inside a Telegram group voice chat</strong> (via
        pytgcalls) — so you hear it on your phone when you join that call, not as a file. Needs
        the Telethon <em>user</em> login (a) above and the <code>channels</code> extra.
      </p>
      <ol>
        <li>Install the streaming deps: <pre><code>{`uv sync --extra channels`}</code></pre></li>
        <li>Create a Telegram <strong>group</strong> (or use one you own) and <strong>start a voice chat</strong> in it.</li>
        <li>Get the group's id (a <code>-100…</code> number). Easiest: add <a href="https://t.me/myidbot" target="_blank" rel="noreferrer">@myidbot</a> to the group, or read it from <code>read_chat</code>.</li>
        <li>In <code>.env</code>:
          <pre><code>{`MUSHEGH_TELEGRAM_MUSIC_ROOM_CHAT=-1001234567890`}</code></pre>
        </li>
      </ol>
      <p>
        Then: <em>“play lo-fi in the music room.”</em> Mushegh joins that group's voice
        chat and streams the track into the call. <strong>Open the group's voice chat on your phone
        and join</strong> to hear it live. <em>“stop the music”</em> leaves the call.
        (Only the user account can stream into a call — a bot can't join voice chats.)
      </p>
      <p>
        Prefer files on your phone instead? Set a <strong>personal playlist</strong> chat and use{" "}
        <code>telegram_music</code>: <code>MUSHEGH_TELEGRAM_PLAYLIST_CHAT</code> (a chat/group of audio
        tracks). <code>local=true</code> plays out loud on the desktop; default delivers to your phone
        Telegram to tap-and-play. Or just <em>“play X”</em> — default source is free
        YouTube Music (no account).
      </p>

      <h2 id="web">Web search & page reading</h2>
      <pre><code>{`MUSHEGH_TAVILY_API_KEY=...     # web_search (answer + sources); free tier at tavily.com
# scrape_url uses Jina Reader — FREE + KEYLESS; MUSHEGH_JINA_API_KEY only raises rate limits
# L5 semantic recall also uses Jina embeddings API if JINA_API_KEY is set (no torch needed)
MUSHEGH_BRAVE_API_KEY=...     # web_search fallback; optional
MUSHEGH_FIRECRAWL_API_KEY=... # scrape_url fallback; optional`}</code></pre>
      <p>Verify: <em>“what's the latest on X”</em> (search), <em>“open this URL and read the headline”</em> (scrape). The visible local <code>browser</code> tool needs no key.</p>

      <h2 id="notion">Notion — pages & the tasks dashboard</h2>
      <ol>
        <li>Create an <strong>internal integration</strong> at <a href="https://www.notion.so/my-integrations" target="_blank" rel="noreferrer">notion.so/my-integrations</a> → copy the secret (<code>ntn_…</code>). <code>MUSHEGH_NOTION_TOKEN=ntn_…</code></li>
        <li><strong>Share</strong> each page/database with the integration: open it → ••• → Connections → add your integration. (Notion is deny-by-default.)</li>
        <li>For the <strong>tasks dashboard</strong>, share your Tasks database and set its id (the 32-hex chunk in its URL):
          <pre><code>{`MUSHEGH_NOTION_TASKS_DB_ID=9c5a572c...bd68`}</code></pre>
        </li>
      </ol>
      <p>Verify: <em>“what's on my plate today?”</em>, <em>“add a task to call the bank Friday”</em>, <em>“mark groceries done”</em>. The morning voice briefing covers overdue + today + this-week deadlines + recurring. Opt-in to the daily autonomous backlog pass with <code>MUSHEGH_BACKLOG_ENABLED=true</code>. Tools: <code>notion_tasks</code>, <code>notion_create_task / update / complete / delete</code>, plus <code>notion_search / read_page / append / comment / create_page</code>.</p>

      <h2 id="google">Gmail + Google Calendar (one OAuth app)</h2>
      <ol>
        <li>In <a href="https://console.cloud.google.com/" target="_blank" rel="noreferrer">Google Cloud Console</a>: new project → enable <strong>Gmail API</strong> + <strong>Calendar API</strong> → OAuth consent screen (External, add yourself as a test user) → create an <strong>OAuth client (Web)</strong> with redirect <code>http://127.0.0.1:8585/oauth2callback</code>.</li>
        <li><pre><code>{`MUSHEGH_GOOGLE_CLIENT_ID=...apps.googleusercontent.com
MUSHEGH_GOOGLE_CLIENT_SECRET=...`}</code></pre></li>
        <li>One-time login → paste the refresh token it prints:
          <pre><code>{`uv run python bench/google_login.py
# -> MUSHEGH_GOOGLE_REFRESH_TOKEN=1//0g...`}</code></pre>
        </li>
      </ol>
      <p>Verify: <em>“read my unread email”</em>, <em>“what's on my calendar today?”</em>. Sending mail + creating events are confirm-gated.</p>

      <h2 id="ha">Home Assistant (smart home)</h2>
      <pre><code>{`MUSHEGH_HA_URL=http://homeassistant.local:8123   # or the IP
MUSHEGH_HA_TOKEN=...   # Profile -> Security -> Long-lived access token`}</code></pre>
      <p>Verify: <em>“is the front door locked?”</em> (<code>ha_state</code>), <em>“turn on the living-room lights”</em> (<code>ha_call</code>). Locks, alarms, covers confirm first. Local-first — the brain talks straight to your HA box, nothing via the cloud.</p>

      <h2 id="push">Phone push (ntfy) & recurring reminders</h2>
      <pre><code>{`MUSHEGH_NTFY_TOPIC=afon-<your-unguessable-string>
MUSHEGH_NTFY_SERVER=https://ntfy.sh`}</code></pre>
      <p>Install the <strong>ntfy</strong> app and subscribe to that topic. Reminders fire as a phone push when you're away from the mic. One-shot/at reminders even fire with the PC off (ntfy holds them). For <strong>recurring</strong> reminders with the PC off, deploy the always-on VPS ticker — see <Link href="/deployment">Deployment</Link>.</p>

      <h2 id="biometrics">Respond only to your voice (speaker biometrics)</h2>
      <pre><code>{`uv sync --extra identity
uv run python bench/enroll_voice.py --script "to-read-script.md"   # ~3 min
# then in .env:
MUSHEGH_SPEAKER_ID_ENABLED=true`}</code></pre>
      <p>After enrolling, Mushegh obeys only your enrolled voice and ignores the TV or a guest. Until you enroll it answers anyone (so it never locks you out). Tune strictness with <code>MUSHEGH_SPEAKER_THRESHOLD</code>. See <Link href="/voice">Voice pipeline</Link>.</p>

      <h2 id="browser">Cloud browser (optional)</h2>
      <pre><code>{`MUSHEGH_BROWSERBASE_API_KEY=...
MUSHEGH_BROWSERBASE_PROJECT_ID=...
uv sync --extra browse
# The local visible browser needs nothing extra:
uv sync --extra browse && playwright install chromium`}</code></pre>
      <p>For headless <code>browse_web</code>. The local <em>visible</em> <code>browser</code> tool (Playwright) already works without Browserbase — a persistent profile keeps you logged in.</p>

      <h2 id="mynews">MyNews (the owner's RSS aggregator)</h2>
      <pre><code>{`MUSHEGH_MYNEWS_URL=http://127.0.0.1:3000    # VPS-local; untruncated titles, no Vercel hop
# HTTP endpoint serving the day's RSS-aggregated brief`}</code></pre>
      <p>One of the proactive signal sources — a morning-brief push within the daily budget + quiet hours.</p>

      <h2 id="fleet-link">Optional: an external specialist fleet</h2>
      <p>
        For deep multi-step work Mushegh can delegate to an external OpenClaw gateway via a single
        team-lead agent. It ships <strong>fully disabled with no host baked in</strong>. Enable only if
        you run your own gateway:
      </p>
      <pre><code>{`MUSHEGH_OPENCLAW_GATEWAY_URL=http://<your-gateway>:3200
MUSHEGH_OPENCLAW_TOKEN=...
MUSHEGH_OPENCLAW_CLI_PATH=openclaw          # usually already on PATH
MUSHEGH_OPENCLAW_CLI_SSH_TARGET=user@vps     # only needed for the CLI fallback
MUSHEGH_FLEET_AUTHORIZED=true   # opt-in; it reaches shared infra`}</code></pre>
      <p>Most users never need it — see <Link href="/fleet">Fleet delegation</Link> and <Link href="/security">Security</Link>.</p>

      <h2 id="mcp">External apps via MCP</h2>
      <p>
        The framework's <Link href="/apps">MCP client</Link> exposes any Model Context Protocol
        server's tools through the same registry — namespaced{" "}
        <code>mcp__&lt;server&gt;__&lt;tool&gt;</code>. Composio's pre-built 250+ OAuth-managed apps are
        the quickest breadth path.
      </p>
      <pre><code>{`MUSHEGH_MCP_SERVERS={"filesystem": {"command": "npx", "args": ["-y", "@modelcontextprotocol/server-filesystem", "/safe/dir"]}}`}</code></pre>

      <div className="callout good">
        <span className="k">No keys needed for the utility belt.</span> Weather, crypto, stocks, FX,
        news, Wikipedia, dictionary, unit/currency convert, local music (YouTube Music), page scraping
        (Jina), reminders, the task queue, system control, and coding tools all work out of the box.
      </div>
    </>
  );
}