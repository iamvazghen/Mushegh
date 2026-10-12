import Link from "next/link";

export default function Devices() {
  return (
    <>
      <h1>Devices</h1>
      <p className="lead">
        One brain, reached many ways — all sharing memory, all over your{" "}
        <Link href="/networking">Tailnet</Link>. All eight setups are wired and tested.
      </p>

      <table>
        <thead>
          <tr><th>Setup</th><th>Connects via</th><th>Barge-in</th><th>Notes</th></tr>
        </thead>
        <tbody>
          <tr><td>Laptop (Windows/Linux)</td><td><code>mushegh.edge.assistant</code> &rarr; brain WS (remote) or in-process brain (local)</td><td>off (open speakers)</td><td>baseline; open speakers run half-duplex</td></tr>
          <tr><td>Mac (macOS)</td><td>same Python/PyAudio edge, runs natively</td><td>off</td><td>grant mic permission to your terminal the first time</td></tr>
          <tr><td>Laptop/Mac + headphones</td><td>same, auto-routes to headphones</td><td><strong>on</strong></td><td>private endpoint; interrupt mid-sentence</td></tr>
          <tr><td>Laptop speakers</td><td>same</td><td>wake-word only (no AEC)</td><td>the wake word interrupts Mushegh mid-sentence at threshold + 0.15</td></tr>
          <tr><td>iPhone (no app)</td><td>“Hey Siri, Mushegh” &rarr; <code>/talk</code></td><td>n/a</td><td>Siri dictation &rarr; spoken reply</td></tr>
          <tr><td>Android (no app)</td><td>Assistant/Tasker &rarr; <code>/talk</code>, or Termux edge-lite</td><td>n/a</td><td>dictation &rarr; spoken reply; or full mic stream</td></tr>
          <tr><td>Phone + headphones</td><td>same shortcut, <code>android-headphones</code>/<code>phone-headphones</code> hint</td><td><strong>on</strong></td><td>reply plays in the earbuds</td></tr>
          <tr><td>Mentra OS glasses</td><td>TS bridge &rarr; brain WS</td><td>scaffold</td><td>needs MentraOS SDK wiring (see below)</td></tr>
          <tr><td>Home Assistant</td><td>brain &rarr; HA REST (local)</td><td>n/a</td><td>states + control; locks confirm-gated</td></tr>
          <tr><td>Remote PC control</td><td>host executor &rarr; brain <code>/control</code></td><td>n/a</td><td>brain drives a laptop from anywhere</td></tr>
        </tbody>
      </table>
      <p>
        Every setup is modelled in <code>src/mushegh/edge/device_profile.py</code>{" "}
        (<code>SUPPORTED_DEVICES</code>: laptop, mac, iphone, android, airpods, mentra). The
        auto-route rule: when AirPods/headphones are connected to <em>any</em> base device, route
        everything to the headphones (private &rarr; barge-in on) regardless of the base.
      </p>

      <h2>Laptop / Mac</h2>
      <pre>
        <code>{`uv run python -m mushegh.edge.assistant`}</code>
      </pre>
      <p>
        The voice edge is pure Python + PyAudio, so it runs <strong>natively on Windows, macOS, and
        Linux</strong> — the same command on a MacBook gives you a local Mushegh. With
        headphones/AirPods connected to the host, output auto-routes to them and barge-in turns on (a
        private endpoint), so you can talk over Mushegh mid-sentence. On open speakers it runs
        half-duplex so it never transcribes its own voice. Each turn logs a TTFW latency number; aim
        for ~10 turns to get a stable mean.
      </p>
      <p>
        Run the brain on the same laptop (in-process, <code>MUSHEGH_BRAIN_MODE=local</code>) or on the
        VPS (<code>remote</code> for the unified brain, <code>auto</code> for VPS-with-local-fallback).
        See <Link href="/voice">Voice pipeline</Link> for the full edge &harr; brain handshake.
      </p>

      <h2>Phone (iPhone, no app, no page)</h2>
      <p>
        Run the brain reachable over the tailnet, then build a one-time Siri Shortcut:
      </p>
      <pre>
        <code>{`# on the brain host:
MUSHEGH_BRAIN_HOST=0.0.0.0  uv run python -m mushegh.brain.server`}</code>
      </pre>
      <ol>
        <li><strong>Dictate Text</strong></li>
        <li>
          <strong>Get Contents of URL</strong> &rarr; <code>http://&lt;brain-tailnet-ip&gt;:8766/talk?token=&lt;MUSHEGH_API_AUTH_TOKEN&gt;</code>,
          method <span className="kbd">POST</span>, body <span className="kbd">JSON</span>, field{" "}
          <code>text</code> = the Dictated Text variable
        </li>
        <li><strong>Play</strong> the response (Mushegh's voice, <code>audio/mpeg</code>)</li>
        <li>Name the shortcut <strong>“Mushegh”</strong> &rarr; say “Hey Siri, Mushegh”.</li>
      </ol>
      <p>
        With AirPods connected to the phone, the same shortcut plays the reply in the AirPods —
        nothing extra to configure. iOS bans background mic for web pages, so a Siri Shortcut is the
        no-app, no-page path; Telegram voice notes are the backup.
      </p>

      <h2>Android (no app, no page)</h2>
      <p>
        Two ways, both over the tailnet:
      </p>
      <ul>
        <li>
          <strong>No-app voice (simplest):</strong> use Google Assistant routines or
          <a href="https://tasker.joaoapps.com/" target="_blank" rel="noreferrer"> Tasker</a> /
          HTTP Shortcuts to POST your dictated text to
          <code>http://&lt;brain-tailnet-ip&gt;:8766/talk?token=…</code> and play the audio reply
          — the exact mirror of the iPhone Siri Shortcut. Declare the listening endpoint with the
          <code>android</code> or <code>android-headphones</code> device hint.
        </li>
        <li>
          <strong>Full mic stream (Termux edge-lite):</strong> install Termux + Termux:Boot, run the
          Python edge there, and it streams mic &rarr; brain and plays TTS like the laptop — wake
          word and barge-in included. Disable battery optimisation so it stays alive.
        </li>
      </ul>
      <p>
        With earbuds on the phone, the <code>android-headphones</code> hint makes the session private
        (barge-in on) and the reply plays in the earbuds.
      </p>

      <h2 id="mentra">Smart glasses — not shipped</h2>
      <p>
        There is <strong>no glasses client in this repository</strong>. A TypeScript bridge scaffold
        existed briefly and was deleted along with the other unused client stubs, because a scaffold
        that cannot run is a capability claim the reader has to disprove by cloning.
      </p>
      <p>
        What <em>is</em> real is the half that would carry one: the brain speaks a versioned
        edge↔brain protocol over <code>/voice</code>, routes replies per device, and classifies an
        output endpoint as private or shared (which is what decides whether barge-in is safe). Any
        client that speaks that protocol over your tailnet gets the same brain and the same memory.
        Writing one is a real project, not a fill-in-the-blanks exercise, and nothing here pretends
        otherwise.
      </p>

      <h2>Home Assistant</h2>
      <p>
        Create a long-lived access token in HA (Profile &rarr; Security) and set{" "}
        <code>MUSHEGH_HA_URL</code> + <code>MUSHEGH_HA_TOKEN</code>. Mushegh reads device states
        (“is the door locked?”) and calls services (lights/scenes/climate/locks) —
        locks, alarms, and covers are <Link href="/security">confirm-gated</Link>. Local-first: the
        brain talks straight to your HA box over the tailnet/LAN, nothing via the cloud.
      </p>

      <h2>Remote PC control</h2>
      <p>
        An edge executor (<code>mushegh.edge.pc_agent</code>) connects out to the brain's{" "}
        <code>/control</code> socket, so the 24/7 brain can drive your laptop end-to-end from your
        phone — open apps, manage processes, run scripts. On Windows it installs as an elevated
        scheduled task. Every action still passes the enforced confirmation tier, the path/secret
        guards, and the catastrophic-op refuse list. See <Link href="/pc-control">PC control</Link>.
      </p>

      <div className="callout">
        <span className="k">Acceptance tests.</span> Each setup has a step-by-step test (TTFW, auto-route,
        barge-in, Siri voice, music room, proactive voice, shared memory) in{" "}
        <Link href="/production">Production readiness</Link>.
      </div>
    </>
  );
}