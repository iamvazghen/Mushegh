import Image from "next/image";
import Link from "next/link";

export default function Home() {
  return (
    <>
      <div className="hero">
        <Image src="/banner.png" alt="Mushegh" width={999} height={249} priority />
      </div>
      <h1>Mushegh</h1>
      <p className="lead">
        An open-source, ready-to-install, voice-first AI assistant —{" "}
        <strong>Modular Universal Synthetic Hyper Engine General Hub</strong>.
      </p>
      <p>
        <span className="badge v">MIT licensed</span>
        <span className="badge">Python 3.11+</span>
        <span className="badge">Local-first</span>
        <span className="badge">Self-hosted</span>
        <span className="badge">No GPU required</span>
      </p>

      <p>
        Clone it, run the <Link href="/quickstart#wizard">setup wizard</Link>, point it at the voice
        and LLM providers you like, and you have a personal assistant you <em>talk to</em>: it listens
        for a wake word, answers in a natural streaming voice, remembers across sessions, acts on your
        machine and your accounts, reaches you proactively when it matters, and can even improve its
        own code — safely and reversibly.
      </p>

      <div className="callout">
        <span className="k">Naming.</span> <strong>M.U.S.H.E.G.H.</strong> —{" "}
        <em>M</em>odular <em>U</em>niversal <em>S</em>ynthetic <em>H</em>yper <em>E</em>ngine{" "}
        <em>G</em>eneral <em>H</em>ub. The project and the assistant you talk to are both{" "}
        <strong>Mushegh</strong>. The Python package, the <code>MUSHEGH_</code> environment prefix
        and the <code>mushegh</code> CLI are the internal names; everything you read is Mushegh.
      </div>

      <h2>What you get</h2>
      <ul>
        <li>
          <strong>Natural voice</strong> — wake word, multilingual understanding (EN / FR / DE / RU /
          Armenian / Ukrainian), streaming TTS with barge-in on private endpoints (auto-detected), and
          barge-in via the wake word on speakers (no AEC needed). Eight
          named <Link href="/protocols">protocols</Link> behind strong passwords.
        </li>
        <li>
          <strong>Its own mind</strong> — a reasoning LLM (any OpenAI-compatible endpoint) with a
          <Link href="/llm-providers">failover chain</Link>, a tool-calling loop, and an editable Markdown
          personality.
        </li>
        <li>
          <strong>Six-layer memory</strong> — working context, durable learned facts, a daily journal,
          your Obsidian vault (read & write), a hot-cache, and optional semantic recall. Plus
          daily <Link href="/memory-care">memory hygiene</Link> + a backup scheduler + a self-health check.
        </li>
        <li>
          <strong>Acts</strong> — files, processes, PowerShell (incl. elevated), a real visible browser,
          music, reminders & push, Telegram (read and send), Gmail, Calendar, Notion, Home Assistant. <Link href="/pc-control">Remote PC control</Link> from your phone over the tailnet.
        </li>
        <li>
          <strong>Proactive</strong> — speaks up within a budget and quiet hours, and remembers what it
          said so you can answer “yes, do that” a minute or ten days later. <Link href="/modes">Modes</Link> (focus / lockdown / guest / commute) flip behaviour on voice.
        </li>
        <li>
          <strong>Self-improving</strong> — reads/edits its own source, runs its tests, makes reversible
          git commits, all confirm-gated, repo-scoped, secret-blocked.
        </li>
        <li>
          <strong>Delegates when warranted</strong> — an optional <Link href="/fleet">fleet</Link> team
          lead (ispir) handles deep multi-domain work. Off by default; arm deliberately.
        </li>
        <li>
          <strong>Honest about its limits</strong> — it knows which of its integrations are
          unconfigured and says so in one sentence instead of calling a tool and apologising; it asks
          one clarifying question when a request is genuinely ambiguous, and never the same one
          twice; and it reports the state it <em>verified</em>, not the one it requested.
        </li>
        <li>
          <strong>Broadens freely</strong> — <Link href="/apps">250+ apps via MCP / Composio</Link>,
          with the confirm-tier still gating outward actions.
        </li>
      </ul>

      <h2>Built against a plan, and gated</h2>
      <p>
        A voice assistant fails quietly — a wrong answer sounds exactly like a right one, and a dead
        integration still says something pleasant. So the work is organised as{" "}
        <strong>50 subsystems × three tiers</strong>, every task carrying the named test that decides
        whether it is done, and <strong>262 offline checks</strong> that run before anything is pushed.
        The plan itself is checked by the build, because a plan that can drift from the code is worse
        than none. See <Link href="/engineering">How it is built &amp; verified</Link>.
      </p>

      <h2>One brain, every device</h2>
      <p>
        The brain runs 24/7 on an always-on host (a cheap VPS); the voice front-end runs wherever you
        are. A Windows/Linux laptop, a Mac, and an iPhone or Android phone (no app installed) all reach
        the same brain and the same memory — connected privately over your{" "}
        <Link href="/networking">Tailnet</Link>. See <Link href="/devices">Devices</Link> for every
        supported setup and <Link href="/phones">Phones</Link> for the no-app Siri/Assistant path.
      </p>

      <h2>Voice-first, by design</h2>
      <p>
        Every assistant reply is voice by default — ElevenLabs mp3 to ffmpeg libopus OGG to a
        Telegram <code>sendVoice</code>, all through the <Link href="/bots">dedicated Mushegh bot</Link>.
        Text is the last-resort fallback when synthesis itself fails. Run the one-shot CLI{" "}
        <code>uv run python -m mushegh.brain.voice_io &quot;…&quot;</code> for ad-hoc voice notes
        from your laptop too.
      </p>

      <h2>Start here</h2>
      <div className="cards">
        <div className="card">
          <h3><Link href="/quickstart">Quick start →</Link></h3>
          <p>Install, run the wizard, and talk to it in 5 minutes.</p>
        </div>
        <div className="card">
          <h3><Link href="/voice">Voice pipeline →</Link></h3>
          <p>Wake word, VAD, barge-in, STT/TTS, speaker biometrics, TTFW. The deep page.</p>
        </div>
        <div className="card">
          <h3><Link href="/integrations">Integrations & tools →</Link></h3>
          <p>Enable every capability — Telegram, Music Room, Notion, Gmail, vault, and more.</p>
        </div>
        <div className="card">
          <h3><Link href="/tools">Tool reference (171) →</Link></h3>
          <p>Generated from the live registry. 54 are advertised per turn, under an enforced token budget.</p>
        </div>
        <div className="card">
          <h3><Link href="/background-work">Background work →</Link></h3>
          <p>work_on_task, the TaskQueue, the daily backlog pass, the morning briefing.</p>
        </div>
        <div className="card">
          <h3><Link href="/skills">Skills (35 playbooks) →</Link></h3>
          <p>The on-demand playbooks Mushegh reads when a turn calls for one.</p>
        </div>
        <div className="card">
          <h3><Link href="/vault">Obsidian vault & memory →</Link></h3>
          <p>Connect your notes and switch on read/write long-term memory.</p>
        </div>
        <div className="card">
          <h3><Link href="/deployment">Deployment (VPS brain + ticker) →</Link></h3>
          <p>The systemd units, the recurring-reminder ticker, the weekly voice alert, the safe-deploy script.</p>
        </div>
        <div className="card">
          <h3><Link href="/architecture">Architecture →</Link></h3>
          <p>The edge/brain split, the WebSocket protocol, the six memory layers.</p>
        </div>
        <div className="card">
          <h3><Link href="/protocols">The 8 protocols →</Link></h3>
          <p>goodnight, phoenix, ragnarok, backup, ping, diagnostics, auditpack, checkpoint.</p>
        </div>
        <div className="card">
          <h3><Link href="/objectives">Objectives &amp; agency →</Link></h3>
          <p>Multi-day goals he drives himself — preparing anything, sending nothing without you.</p>
        </div>
        <div className="card">
          <h3><Link href="/engineering">How it is built &amp; verified →</Link></h3>
          <p>The 427-row plan, the gates, and the defects they caught.</p>
        </div>
        <div className="card">
          <h3><Link href="/privacy">Privacy &amp; what it stores →</Link></h3>
          <p>Ask it out loud. The inventory is declared, and retention is executed, not documented.</p>
        </div>
        <div className="card">
          <h3><Link href="/security">Security →</Link></h3>
          <p>The enforced safety model to understand before you deploy.</p>
        </div>
        <div className="card">
          <h3><Link href="/personalize">Personalize →</Link></h3>
          <p>Name it, set how it addresses you, and pick its languages — from config.</p>
        </div>
      </div>

      <div className="footer">
        Mushegh — a from-scratch, local-first assistant you install and talk to.</div>
    </>
  );
}