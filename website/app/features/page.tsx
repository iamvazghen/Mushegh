import Link from "next/link";

export default function Features() {
  return (
    <>
      <h1>Features — everything Mushegh can do</h1>
      <p className="lead">
        A complete tour of the capability surface. Every integration{" "}
        <strong>degrades gracefully</strong> — anything you haven't configured simply says
        “that isn't set up yet” instead of breaking. Tool schemas in{" "}
        <code>src/mushegh/brain/tools/</code> are the source of truth — <Link href="/tools">the
        171-tool reference</Link> is generated from the live registry.
      </p>

      <h2>Voice (the whole point)</h2>
      <ul>
        <li><strong>Always-listening wake word</strong> — openWakeWord (CPU). Custom <code>.onnx</code> models trained free (no key). Spoken ack (“Yes, sir?”) the moment it fires so you know it heard you. <Link href="/voice">Full pipeline →</Link></li>
        <li><strong>Speech-to-text</strong> — Deepgram (cloud, nova-3, streaming, EN/FR/DE/RU multilingual) or Whisper (local, auto-detects 6 langs incl. Armenian/Ukrainian) or Moonshine (local, English, ~3&times; faster than whisper base).</li>
        <li><strong>Text-to-speech</strong> — ElevenLabs (cloud, streaming) or Piper / Kokoro (fully local, offline). Auto-falls-back to local if the cloud voice can't be built.</li>
        <li><strong>Barge-in</strong> — VAD-driven on <strong>private</strong> endpoints (headphones / AirPods / earbuds / smart-glasses) — auto-detected. Wake-word barge-in works on <strong>speakers</strong> too (threshold + 0.15; no AEC needed).</li>
        <li><strong>Streaming & latency</strong> — speaks sentence-by-sentence as the model generates; pre-LLM acknowledgements mask first-token latency; per-turn TTFW logged; <code>MUSHEGH_TTFW_TARGET_MS=1200</code>.</li>
        <li><strong>Speaker biometrics</strong> — optional ECAPA voiceprint; obeys only your voice. Fail-open until you enroll, so it never locks you out.</li>
      </ul>

      <h2>His own mind</h2>
      <ul>
        <li><strong>Multi-provider LLM</strong> with an ordered <Link href="/llm-providers">failover chain</Link> (Groq direct and/or an OpenAI-compatible proxy; Ollama for fully offline); warmup probe primes every provider at startup so neither the first turn NOR a failover pays a cold TLS / connection.</li>
        <li>
          <strong>Layered memory</strong> (<Link href="/architecture#memory">details</Link>): L1 learned
          facts, L2 daily journal, L3 your Obsidian vault, L4 hot cache (Redis optional), L5 semantic recall
          by meaning (Jina API or local sentence-transformers). <Link href="/memory-care">Daily hygiene</Link>{" "}
          dedups, caps, and rotates so the prompt stays lean. A background self-improvement pass
          distils durable facts every few turns.
        </li>
        <li><strong>Conversation memory</strong> shared across every device (one brain), with a smart idle-reset so a new chat hours later doesn't drag stale context — and restart-durable so a reboot resumes mid-thread.</li>
        <li><strong>Streaming & tool-calling discipline</strong> — native tool calls only (textual tool-calls fail over); groq's mixed-format recovery keeps the fast path; mid-stream break never double-speaks.</li>
      </ul>

      <h2>Knowing what he cannot do</h2>
      <ul>
        <li>
          <strong>Honest gaps.</strong> Every integration knows whether it is configured and what it
          needs, and the unconfigured ones are named in his prompt. Ask him to text someone with no
          Twilio account and you get one plain sentence instead of a tool call, a failure string and
          an apology. It is generated from the live config, so an integration appears the day it is
          added and disappears the day it is retired.
        </li>
        <li>
          <strong>One question, not a guess.</strong> When a request is genuinely ambiguous — “send
          it”, “the usual”, with nothing to point at — he asks one short question and stops. He does
          not ask the same one twice in a session: the second time he takes the likeliest reading and
          says out loud which one he took, so a wrong guess costs you one word to correct.
        </li>
        <li>
          <strong>No fabricated certainty.</strong> Unknowables are named as unknowable, estimates are
          labelled as estimates, and answers carry what they rested on.
        </li>
      </ul>

      <h2>Proactive companion</h2>
      <ul>
        <li><strong>Initiates on its own</strong> — routine, calendar, unread, open threads, self-health, MyNews, Notion tasks — within a daily budget + quiet hours so it's a companion, not a nag.</li>
        <li><strong>Morning voice briefing</strong> — overdue, due today, this-week deadlines, and recurring tasks, spoken (or a phone voice-note if you're away).</li>
        <li><Link href="/modes"><strong>Modes by voice</strong></Link> — focus (hold nudges for N minutes), lockdown (go quiet), guest (relax biometrics), commute (short replies), normal.</li>
        <li><strong>Repeat-suppression</strong> per signal key so a stuck signal never nags.</li>
        <li>
          <strong>Objectives he drives</strong> — hand him a multi-day goal and he advances the safe
          part of it daily, logs what moved, defers every outward step for your approval, and reports
          a stall as arithmetic rather than a feeling. See <Link href="/objectives">Objectives</Link>.
        </li>
        <li>
          <strong>Routines drafted from evidence</strong> — he proposes your routines from what you
          actually do, and says what will not work about a day before it starts.
        </li>
      </ul>

      <h2>Reminders & true 24/7</h2>
      <ul>
        <li><strong>Reminders</strong> — one-shot, absolute time, or daily; spoken if you're there, pushed to your phone (ntfy) if not.</li>
        <li><strong>PC-off recurring</strong> — an always-on <Link href="/deployment">VPS ticker</Link> owns recurring reminders so they fire even with every personal device asleep.</li>
        <li><strong>Background task queue</strong> — hand off long work (deep research, a big build), keep chatting, ask “how's that going?”, get a voice note when it finishes. See <Link href="/background-work">Background work</Link>.</li>
      </ul>

      <h2>Channels & knowledge</h2>
      <ul>
        <li><strong>Telegram</strong> — read your DMs (without marking them seen), send messages/files, proactive <em>voice notes</em> by default, and <em>stream music live</em> into a group voice chat. See <Link href="/bots">Bots & send-paths</Link>.</li>
        <li><strong>Web</strong> — answer-with-sources search (Tavily + Brave + keyless Jina tail) and keyless page scraping (Jina Reader); a real, visible browser (Playwright) that can log in with your credentials when you ask.</li>
        <li><strong>Notion</strong> — search/read/append/comment, full <strong>tasks dashboard</strong> by voice, and an opt-in daily autonomous <strong>backlog pass</strong> that has the bounded worker attempt the safe work and comments back.</li>
        <li><strong>Gmail & Calendar</strong> — read/draft/send mail and read/create events (sending + writes are confirm-gated).</li>
        <li><strong>Smart home</strong> — Home Assistant device states + control (lights, scenes, climate, locks); locks/alarms confirm first. Local-first, no cloud.</li>
        <li><strong>Music</strong> — “play X” via YouTube Music (free), your Telegram playlist, or live into the music room.</li>
        <li><strong>Utilities belt (no keys)</strong> — weather, crypto, stocks, FX, unit/currency convert, news, Wikipedia, dictionary.</li>
        <li><strong>“Read this doc”</strong> — ephemeral document RAG over a local file; ingests text/Markdown/code/CSV/JSON or a PDF (needs <code>pypdf</code>), chunks, and answers grounded in it.</li>
        <li><strong>External apps</strong> — 250+ via <Link href="/apps">MCP / Composio</Link> (Slack, GitHub, Linear, Drive, Stripe, Airtable, HubSpot, …) behind two meta-tools.</li>
      </ul>

      <h2>Control & self-improvement</h2>
      <ul>
        <li><strong>This machine</strong> — create/delete files, list/kill/start processes, run shell (elevated raises a prompt), open apps — all behind the confirmation tier + path/secret guards.</li>
        <li><strong>Remote PC control</strong> — <Link href="/pc-control">drive your laptop from your phone</Link> via an edge executor that connects out to the brain (no inbound ports). Catastrophic-op refuse list as the last-line defense.</li>
        <li><strong>Coding on its own source</strong> — read/write code, run the test suite, lint, and make <em>reversible-only</em> git commits (never force-push/reset); commits and pushes are confirm-first.</li>
        <li>
          <strong>Verify, then report.</strong> An action that can be checked is checked, and the
          answer is the verified state rather than the requested one — the volume he reads back, not
          the number he sent. Where the evidence is one-sided he says so instead of inventing
          certainty: finding a launched app proves it started, not finding it proves very little.
        </li>
        <li>
          <strong>Chains in one turn.</strong> “Text Anna I'm late” resolves who Anna is on
          <em>that</em> channel and sends, in the same turn — with the resolution happening before
          the confirmation, so what you approve names the address it will actually go to.
        </li>
        <li><strong>Eight protocols</strong> — password-gated routines: <Link href="/protocols">goodnight, phoenix, ragnarok, backup, ping, diagnostics, auditpack, checkpoint</Link>.</li>
      </ul>

      <h2>Identity & safety</h2>
      <ul>
        <li><strong>Speaker biometrics</strong> — optional ECAPA voiceprint so it responds only to <em>your</em> voice and ignores the TV or a guest.</li>
        <li><strong>Enforced confirm-tier</strong> on every outward/destructive action, hard guards on secrets and protected paths, and a redacted audit log with value-scrubbing.</li>
        <li>
          <strong>Malformed calls never half-run.</strong> A tool call whose arguments do not match
          its schema is rejected before dispatch, and the model is told exactly what to fix — once.
          A second failure on the same tool stops and tells you, rather than spending your turn on
          retries.
        </li>
        <li><strong><Link href="/personalize">Configurable identity</Link></strong> — name, address, languages, persona — all from config (no code edits).</li>
      </ul>

      <h2>Optional: an agent fleet</h2>
      <p>
        For deep multi-step domain work Mushegh can delegate to an external{" "}
        <strong>OpenClaw</strong> fleet via a single team-lead agent — but it ships{" "}
        <strong>fully disabled with no host baked in</strong>. Most users never need it; enable it only
        if you run your own gateway. See <Link href="/fleet">Fleet delegation</Link> and{" "}
        <Link href="/security">Security</Link>.
      </p>

      <div className="callout good">
        <span className="k">All of it is gated.</span> 262 offline checks, every task in the plan
        carrying the named test that decides whether it is done, and the suite runs before any push.
        See <Link href="/engineering">How it is built &amp; verified</Link>.
      </div>

      <div className="callout">
        <span className="k">Devices.</span> All of the above reaches you on laptop, Mac, iPhone,
        Android, Home Assistant, and a remotely-controlled PC — see{" "}
        <Link href="/devices">Devices</Link> and <Link href="/phones">Phones</Link>.
      </div>
    </>
  );
}