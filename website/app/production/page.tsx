import Link from "next/link";

export default function Production() {
  return (
    <>
      <h1>Production readiness</h1>
      <p className="lead">
        How to know your Mushegh is ready for 24/7 use — and the gate that decides when to make a
        fork public.
      </p>

      <div className="callout warn">
        <span className="k">The gate.</span> Keep your repo <strong>private</strong> until: the test
        suite is green, the efficiency report meets its targets, and you've made the decisions
        below. Mushegh's own status is captured in <code>TODO.md</code> and{" "}
        <code>docs/MASTER-PLAN.md</code>.
      </div>

      <h2>Readiness checklist</h2>
      <table>
        <thead><tr><th>Check</th><th>How</th></tr></thead>
        <tbody>
          <tr><td>Tests green</td><td><code>uv run python bench/run_all_tests.py</code> &rarr; all passed (SKIP is fine)</td></tr>
          <tr><td>Efficiency targets met</td><td><code>uv run python bench/efficiency_report.py</code> &rarr; every row OK/GOOD (watch streaming TTFT)</td></tr>
          <tr><td>Required keys set</td><td><code>uv run python bench/check_config.py</code> &rarr; TTS, STT, brain LLM, vault present</td></tr>
          <tr><td>Live integrations work</td><td><code>uv run python bench/test_live_integrations.py</code> &rarr; the keys you set respond</td></tr>
          <tr><td>Voice enrollment (if shared space)</td><td><code>uv run python bench/enroll_voice.py</code> + <code>MUSHEGH_SPEAKER_ID_ENABLED=true</code></td></tr>
          <tr><td>Custom wake word (optional)</td><td>train an <code>.onnx</code> model (free; openWakeWord's own pipeline, out of repo)</td></tr>
          <tr><td>Protocol passwords changed (auto by wizard)</td><td>re-run <code>mushegh-setup</code> — you should NOT see the placeholders in <code>.env</code></td></tr>
          <tr><td>Confirmation tier verified</td><td>ask it to send/delete something &rarr; it asks first, runs only after &quot;yes&quot;</td></tr>
          <tr><td>Vault writable only on the owner host</td><td><code>MUSHEGH_VAULT_WRITABLE=true</code> on the VPS, false on the laptop</td></tr>
          <tr><td>Tailnet on every device</td><td>brain reachable from laptop + phone over <code>100.x</code>; nothing public</td></tr>
          <tr><td>Edge autostart registered</td><td><code>uv run python -m mushegh.edge.autostart status</code></td></tr>
          <tr><td>VPS brain deployed (24/7)</td><td><code>curl http://&lt;vps&gt;:8766/healthz</code> &rarr; <code>ok</code></td></tr>
          <tr><td>VPS ticker for PC-off recurring reminders</td><td>see <Link href="/deployment">Deployment</Link>; tested with laptop off</td></tr>
          <tr><td>Weekly live-check timer armed</td><td><code>systemctl --user list-timers</code> shows the Mon 07:30 UTC entry</td></tr>
          <tr><td>Bot split honoured</td><td>Mushegh bot (<code>@afon_iamvazghen_bot</code>) for the assistant; ispir bot for the fleet only</td></tr>
          <tr><td>Proactivity decision</td><td><code>MUSHEGH_PROACTIVE_ENABLED</code> + quiet hours + budget tuned</td></tr>
          <tr><td>Fleet decision</td><td><code>MUSHEGH_FLEET_AUTHORIZED</code> stays false unless you mean it</td></tr>
          <tr><td>Device acceptance tests</td><td>walk the per-device tests below on each device</td></tr>
        </tbody>
      </table>

      <h2>Run it as a service</h2>
      <ul>
        <li><strong>Brain (VPS, 24/7):</strong> run <code>python -m mushegh.brain.server</code> under systemd (it owns the reminder scheduler, proactive tick, daily briefing, daily backup, and the Telegram bridge). Pattern in <code>deploy/vps/mushegh-brain.service</code>.</li>
        <li><strong>Ticker (VPS, optional):</strong> run <code>deploy/vps/mushegh_ticker.py</code> under <code>mushegh-ticker.service</code> so recurring reminders fire with the PC off.</li>
        <li><strong>Live-check timer (VPS):</strong> Mon 07:30 UTC; speaks failures to the owner via the Mushegh bot.</li>
        <li><strong>Edge (laptop):</strong> the cross-platform <code>autostart</code> installer so it auto-starts and reconnects. See <Link href="/deployment">Deployment</Link>.</li>
      </ul>

      <h2>What “done” looks like</h2>
      <p>
        Cold-boot the laptop &rarr; the edge auto-starts and reconnects to the brain. The wake word
        fires only on your voice and ignores the TV. A direct question answers in ~1&ndash;3 s; a
        hard one is delegated (if armed) with spoken progress. Vault search, Telegram, calendar, and
        Notion tasks all work. A reminder fires proactively — spoken if you're listening,
        pushed if not — and you can answer it a minute or days later. Every consequential action
        is read back and confirmed. The daily memory backup runs at 03:30, the daily hygiene pass at
        04:00. The suite is green and TTFW is within your tolerance.
      </p>

      <p>
        See the full audit in <code>TODO.md</code> and the <Link href="/llm-providers">LLM providers</Link>{" "}
        page for how the failover chain + warmup keep that first-turn latency short.
      </p>
    </>
  );
}