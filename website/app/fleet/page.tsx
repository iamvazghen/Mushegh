import Link from "next/link";

export default function Fleet() {
  return (
    <>
      <h1>Fleet delegation — optional, gated, by design</h1>
      <p className="lead">
        For deep multi-step work Mushegh can consult an external OpenClaw fleet — a single
        team-lead agent (ispir) that decides which specialist handles a brief and returns the result.
        Mushegh remains himself: the result is re-voiced in his own words, and the fleet is{" "}
        <strong>off by default</strong> because it touches shared infrastructure.
      </p>

      <div className="callout warn">
        <span className="k">Off by default.</span> <code>MUSHEGH_FLEET_AUTHORIZED=false</code> on a fresh
        fork. Arm deliberately per session (<em>“authorize the fleet”</em>) or for a
        deployment (<code>MUSHEGH_FLEET_AUTHORIZED=true</code>). Until armed, <code>delegate_to_fleet</code>{" "}
        returns a safe sentinel and performs no network action.
      </div>

      <h2>1 · The contract</h2>
      <p>
        One tool, one rule: <strong>always ispir, never a specialist directly</strong>. The team lead
        re-reads the brief, decides which specialist(s) to involve, briefs them in depth, and returns a
        synthesized answer. So the target agent is fixed to the router (<code>MUSHEGH_OPENCLAW_ROUTER_AGENT=ispir</code>);
        there is no per-call override by design.
      </p>
      <p>
        The tool schema is wired so the description makes the separation AND the ispir-only rule
        explicit; the model can't accidentally address a specialist by name.
      </p>

      <h2>2 · Two transports</h2>
      <table>
        <thead>
          <tr><th>Transport</th><th>When</th><th>Setup</th></tr>
        </thead>
        <tbody>
          <tr><td><strong>WebSocket</strong> (<code>/ws</code> on the gateway)</td><td>You have a gateway host + token; you've allowlisted a client id</td><td><code>MUSHEGH_OPENCLAW_GATEWAY_URL</code>, <code>MUSHEGH_OPENCLAW_TOKEN</code></td></tr>
          <tr><td><strong>CLI over SSH</strong> (the sanctioned path)</td><td>No token / no client allowlist; you have SSH access to the VPS</td><td><code>MUSHEGH_OPENCLAW_CLI_PATH</code>, <code>MUSHEGH_OPENCLAW_CLI_SSH_TARGET</code></td></tr>
        </tbody>
      </table>
      <p>
        The CLI path self-heals: <code>_delegate_via_cli()</code> resolves <code>openclaw</code> on PATH,
        else falls back to <code>~/.npm-global/bin/openclaw</code> (the standard npm-global location)
        so a service with a minimal PATH still finds it.
      </p>

      <h2>3 · Scopes — the least-privilege set</h2>
      <p>
        Mushegh requests only <code>operator.read</code> and <code>operator.write</code> (message + read),
        <strong>not</strong> the full admin scope set the human control UI uses. The token-only connect
        carries no device-identity signature; the gateway still authenticates the session.
      </p>

      <h2>4 · Routing memory</h2>
      <p>
        After every successful delegation, the task's domain bumps a prefs counter (finance/markets,
        real estate, crypto, deep research, coding). Once a domain has two or more successes, a one-line{" "}
        <em>routing memory</em> hint is injected into the system prompt for that domain — Mushegh
        pre-biases toward delegating those without re-deliberating per turn. The hint is plain keyword
        tagging; the policy is overridable per turn.
      </p>

      <h2>5 · Background delegation</h2>
      <p>
        Long-running briefs (<em>“research X and write me a memo”</em>) can be delegated with{" "}
        <code>background=true</code>. The tool returns a task id immediately, and the same TaskQueue
        voice-announcement path that <code>work_on_task</code> uses kicks in when the fleet returns.
      </p>

      <h2>6 · The WS auth reality</h2>
      <p>
        OpenClaw's <code>openclaw-control-ui</code> client id is origin-allowlisted AND ECDSA
        device-identity gated (HTTPS / secure-context), which a Python backend cannot satisfy. The
        <code>openclaw-tui</code> client id avoids device identity and works without HTTPS. Until you
        allowlist a dedicated Mushegh client id / origin on your gateway, the WS path falls through to
        the CLI path automatically. The intent is documented; the fallback is automatic.
      </p>

      <h2>7 · Failure modes & how they surface</h2>
      <table>
        <thead><tr><th>Symptom</th><th>What it means</th></tr></thead>
        <tbody>
          <tr><td>“The bridge isn't configured.”</td><td>Fleet is off, or no host/token. Nothing to fix — Mushegh handled it gracefully.</td></tr>
          <tr><td>CLI exits non-zero</td><td>The CLI failed; stderr is summarised back so you can see why.</td></tr>
          <tr><td>WS path raises <code>FleetUnavailable</code></td><td>Gateway rejected the connect; the runner falls back to the CLI path. If both fail, you get a one-line spoken reason.</td></tr>
          <tr><td>Slow delegation</td><td>Normal for deep work; you'll hear a progress note and a “Done, sir — 'X' finished in N m” voice note when it lands.</td></tr>
        </tbody>
      </table>

      <p style={{ marginTop: 22 }}>
        See <Link href="/security">Security</Link> &sect;7 for the fleet gating and{" "}
        <Link href="/integrations">Integrations</Link> for the env-var reference.
      </p>
    </>
  );
}