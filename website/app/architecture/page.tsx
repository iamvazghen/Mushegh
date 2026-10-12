import Link from "next/link";
import groups from "./groups.generated.json";

export default function Architecture() {
  return (
    <>
      <h1>Architecture</h1>
      <p className="lead">
        Two cooperating processes over one streaming WebSocket protocol: a local <strong>edge</strong>{" "}
        and an always-on <strong>brain</strong>.
      </p>

      <pre>
        <code>{`EDGE — laptop / phone / glasses (where you are)
  Mic -> mic-gain -> VAD (Silero) -> wake word (openWakeWord) -> DuplexGate (half/full)
      -> STT (Deepgram / Whisper / Moonshine) -> [speaker-id gate]
      -> [BrainBridge or RemoteBrain] --WebSocket--+
  Speaker <- TTS (ElevenLabs / Piper / Kokoro) <-+   (barge-in, smart turn-taking)
                                |
              streaming events  |  (Tailnet + Bearer-token auth)
                                v
BRAIN — always-on host / VPS (24/7)
  Agent loop: own LLM (+failover chain) - tool-calling - session + memory
  Confirmation tier ENFORCED in code - smart idle session reset
  Tools: vault(r/w) - web - telegram - gmail - calendar - notion - smart-home
         - utilities - system/PC-control - browser - reminders - coding/git
         - skills - tasks - documents - contacts - composio (MCP)
  Memory L0-L5 - proactive tick (durably logged) - scheduler - audit - health
  HTTP sidecar: /talk (iPhone Siri voice) - /control (remote PC executor)`}</code>
      </pre>

      <h2>Why the split</h2>
      <ul>
        <li>
          <strong>Edge</strong> (<code>src/mushegh/edge/</code>) keeps audio + STT/TTS local for privacy
          and low mic latency. Pure Python + PyAudio — the same code runs natively on Windows,
          macOS, and Linux.
        </li>
        <li>
          <strong>Brain</strong> (<code>src/mushegh/brain/</code>) holds the 24/7 obligations —
          reasoning, memory, scheduler, channels — so they survive the laptop being off.
        </li>
        <li>
          The Pipecat “LLM stage” is replaced by a thin <code>BrainBridge</code> processor, so
          swapping reasoning backends or transports never touches the audio pipeline.
        </li>
        <li>
          The brain can run in-process (single machine) or as a shared WebSocket server so every
          device shares <em>one</em> brain and <em>one</em> memory. The laptop edge can run the
          in-process brain (<code>brain_mode=local</code>) or thinly dial the VPS brain (<code>remote</code>/
          <code>auto</code> — auto falls back to local if the VPS is unreachable).
        </li>
      </ul>

      <h2>Two WebSocket paths on the brain</h2>
      <table>
        <thead><tr><th>Path</th><th>Used by</th></tr></thead>
        <tbody>
          <tr><td><code>/voice</code></td><td>the laptop edge, the iPhone Telegram voice-bridge bot, glasses clients</td></tr>
          <tr><td><code>/control</code></td><td>the laptop PC-control executor (<code>mushegh.edge.pc_agent</code>) so the VPS brain can run file/process/PowerShell/open-app commands on the laptop</td></tr>
        </tbody>
      </table>
      <p>
        Both paths share the same bearer token (<code>MUSHEGH_API_AUTH_TOKEN</code>); <code>/control</code>{" "}
        requires the laptop executor's <code>pc_hello</code> handshake first. See{" "}
        <Link href="/pc-control">PC control</Link> for the protocol.
      </p>

      <h2 id="memory">Memory — six layers</h2>
      <table>
        <thead>
          <tr><th>Layer</th><th>What</th><th>Where</th><th>Enabled by</th></tr>
        </thead>
        <tbody>
          <tr><td>L0 Working</td><td>live conversation; smart-reset on long idle; restart-durable</td><td>RAM + JSON snapshot</td><td>always</td></tr>
          <tr><td>L1 Learned</td><td>durable facts (remember/recall/forget) + auto-extracted by <code>background_review</code></td><td><code>memory/learned/</code></td><td>always</td></tr>
          <tr><td>L2 Journal</td><td>daily summaries + a durable log of proactive nudges</td><td><code>memory/journal/</code></td><td>always</td></tr>
          <tr><td>L3 Vault</td><td>your Obsidian KB — read always, <strong>write</strong> on the authoritative host</td><td><code>MUSHEGH_VAULT_PATH</code></td><td><code>MUSHEGH_VAULT_WRITABLE=true</code> only on the host that owns it</td></tr>
          <tr><td>L4 Hot-cache</td><td>fronts slow paths (search, utilities)</td><td>in-process TTL</td><td>always on, no setting</td></tr>
          <tr><td>L5 Semantic</td><td>recall by meaning, not just keywords</td><td>optional Jina API or local embedder</td><td><code>MUSHEGH_MEMORY_SEMANTIC_ENABLED=true</code>; embedder available</td></tr>
        </tbody>
      </table>
      <div className="callout good">
        <span className="k">Smart session reset.</span> After a long idle gap
        (<code>MUSHEGH_SESSION_IDLE_RESET_MINUTES</code>, default 180) the brain journals the prior
        conversation and clears working memory, so a fresh conversation hours later doesn't drag
        stale context or anaphora (“set it back” pointing at a “it” from this
        morning). Durable memory is untouched — Mushegh forgets the <em>thread</em>, not the{" "}
        <em>person</em>. See <Link href="/memory-care">Memory care</Link> for the daily hygiene that
        keeps L1/L2 bounded.
      </div>

      <h2 id="catalogue">Tools — a budget, not just a lean surface</h2>
      <p>
        Every tool is registered in <code>brain/tools/</code> from day one, so tests, the proactive
        engine and direct handler calls can always reach it. What varies per turn is what gets{" "}
        <em>advertised</em> to the model: a core surface every turn, plus any lazy group the turn
        needs, with a one-turn warm decay so “reply to it” still has the tools it just used.
      </p>
      <p>
        The reason is not only speed. Sending all 171 schemas costs roughly 21,900 tokens a turn, and
        a model choosing between 171 tools mis-selects more often than one choosing between sixty —
        so a fat catalogue buys latency <em>and</em> a worse router.
      </p>
      <div className="callout good">
        <span className="k">The ceiling is enforced, not observed.</span> Core alone is ~7,300
        tokens; one armed group ~9,400; four ~12,200; all twenty-five ~19,000. There used to be
        nothing stopping the last number. Now a group is measured <em>before</em> it joins the turn,
        against a hard budget of 11,000 tokens, which fits core plus the two heaviest groups — the
        honest reading of “one clause, one group”.
      </div>
      <p>
        A third group means the trigger matcher matched broadly and could not tell which capability
        you wanted. The answer to that is not another 1,500 tokens of catalogue; it is a question. So
        the deferred group becomes <strong>one short clarifying question</strong> naming the
        candidates — asked once, never twice in the same session for the same request. Groups arm
        strongest-match-first, and what this turn asked for outranks what the last turn left warm,
        because a warm group is a guess about the follow-up and a guess loses to a request.
      </p>

      <h3>The {groups.count} lazy groups</h3>
      <p>
        Generated from the registry (<code>LAZY_GROUP_TRIGGERS</code>), so this table is the one the
        router actually uses. Core is always on and is made of{" "}
        {groups.core_modules.length} modules:{" "}
        {groups.core_modules.map((m, i) => (
          <span key={m}>{i ? ", " : ""}<code>{m}</code></span>
        ))}.
      </p>
      <table>
        <thead><tr><th>Group</th><th>Modules</th><th>Arms on (a sample of its triggers)</th></tr></thead>
        <tbody>
          {groups.groups.map((g) => (
            <tr key={g.group}>
              <td><code>{g.group}</code></td>
              <td>{g.modules.map((m, i) => (<span key={m}>{i ? ", " : ""}<code>{m}</code></span>))}</td>
              <td style={{ fontSize: "0.92em" }}>
                {g.triggers.slice(0, 6).join(" · ")}
                {g.triggers.length > 6 ? ` … (${g.triggers.length} in total)` : ""}
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      <h2 id="intent">What kind of turn is this</h2>
      <p>
        Before any of that, one function decides what the turn <em>is</em>:{" "}
        <strong>chat</strong>, <strong>lookup</strong>, <strong>act</strong>,{" "}
        <strong>multi</strong> (more than one thing in one sentence) or{" "}
        <strong>ambiguous</strong>. The classes were always in the system — one piece of code decided
        act-versus-lookup, another decided compound, a third decided chatter — but no single place
        held the question, so “why did he treat that as small talk?” had nowhere to look and no
        number to move.
      </p>
      <ul>
        <li><strong>chat</strong> carries <em>no tools at all</em>, which is what makes a greeting answer immediately instead of paying a ~1.7s tool prefill.</li>
        <li><strong>ambiguous</strong> is a pointer with nothing to point at — “send it”, “the usual”. Perfectly good sentences one turn after “here's the draft”, and unanswerable as an opener, so the reference resolver's verdict decides which one it is.</li>
        <li><strong>multi</strong> gets the full surface and a per-clause plan, so the second half of “look it up and remember it” cannot be quietly dropped.</li>
        <li><strong>act</strong> and <strong>lookup</strong> split on whether the routed tool changes something.</li>
      </ul>
      <p>
        The classifier is measured on a labelled set, and — because a set written alongside a
        classifier only measures agreement with itself — also on a holdout it cannot tune: prompts
        written months earlier for the behavioural benchmark, labelled mechanically by the tools they
        expect. Every class is also what the cost accounting groups by, so{" "}
        <Link href="/production">the HUD</Link> can say which <em>kind</em> of turn spends the money.
      </p>

      <h2>Proactivity that remembers</h2>
      <p>
        A background tick weighs signals (routine, calendar, unread, open threads, self-health, MyNews)
        and decides whether to say something <em>unprompted</em> — but inside a strict{" "}
        <strong>interruption budget</strong> and <strong>quiet hours</strong>, so it's a companion, not
        a nag. Every proactive line is recorded into both working memory (so you can answer “yes,
        do it” at once) and the L2 journal (so you can refer back days later). See{" "}
        <Link href="/security">Security</Link> for the enforced confirmation tier that gates anything it
        tries to act on.
      </p>

      <h2>LLM — chain & failover</h2>
      <p>
        Any OpenAI-compatible endpoint works. The chain (<code>MUSHEGH_LLM_PRIMARY_MODEL</code> +
        <code>MUSHEGH_LLM_FALLBACK_MODELS</code>) handles rate-limits, errors, and slow first tokens; a
        first-token timeout abandons a stalled model so a turn never blocks a full minute on one
        provider. <code>groq:</code> and <code>cerebras:</code> prefixes hit direct endpoints with
        their own keys; <code>ollama:</code> hits a local Ollama server for fully-offline tail
        coverage. Warmup pings every distinct provider at startup. See{" "}
        <Link href="/llm-providers">LLM providers</Link>.
      </p>

      <h2>Shared always-on services on the VPS</h2>
      <ul>
        <li><strong>mushegh-brain</strong> — the agent + WebSocket voice endpoint + reminder scheduler + Telegram bridge. Systemd unit, Restart=always, MemoryMax.</li>
        <li><strong>mushegh-ticker</strong> — a tiny standalone daemon for recurring ntfy pushes (the one reminder case ntfy can't hold server-side).</li>
        <li><strong>Weekly live-check timer</strong> — Mon 07:30 UTC; runs <code>bench/test_live_integrations.py</code>; voice-alerts the owner via the Mushegh bot on failure (text as the last-resort fallback).</li>
      </ul>
      <p>
        See <Link href="/deployment">Deployment</Link> for the unit files, the install scripts, and
        the safe-deploy wrapper (<code>scripts/deploy_vps.sh</code>) that ships source + skills and
        restarts the brain atomically.
      </p>

      <h2>What lives where</h2>
      <ul>
        <li><strong>Character</strong> — <code>personality/mushegh.md</code> (edit to make Mushegh yours).</li>
        <li><strong>Knowledge</strong> — Markdown under <code>memory/</code> + your vault.</li>
        <li><strong>Skills</strong> — on-demand playbooks in <code>skills/*.md</code>. See <Link href="/skills">Skills</Link> for the curated 20.</li>
        <li><strong>Site</strong> — <code>website/</code> (Next.js on Vercel; the tool reference regenerates from the registry at every build).</li>
      </ul>
      <p>
        Nothing is hard-coded: the same codebase runs CPU-local-only or cloud-quality by flipping
        provider flags, and an unconfigured integration simply says “that isn't configured
        yet”.
      </p>
    </>
  );
}