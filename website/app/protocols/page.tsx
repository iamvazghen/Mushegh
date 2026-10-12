import Link from "next/link";

export default function Protocols() {
  return (
    <>
      <h1>Protocols — the eight privileged routines</h1>
      <p className="lead">
        Protocols are password-gated executable scripts Mushegh runs ONLY when given the right password.
        They are the identity gate: Mushegh asks first, the runner verifies in constant time, the script
        is launched detached so it survives Mushegh being killed (needed for stop/restart).
      </p>

      <div className="callout">
        <span className="k">The wizard generates all eight passwords for you.</span>{" "}
        <code>mushegh-setup</code> writes a strong unique password to each <code>MUSHEGH_PROTOCOL_*_PASSWORD</code>
        on first run, so a fresh fork is never shipped on the placeholders. Re-runs preserve them.
        Constant-time compare (<code>hmac.compare_digest</code>) so a wrong guess leaks no timing.
      </div>

      <table>
        <thead>
          <tr><th>Protocol</th><th>What it does</th><th>Env key</th><th>When to use</th></tr>
        </thead>
        <tbody>
          <tr><td><code>goodnight</code></td><td>Stops Mushegh (terminates the edge process)</td><td><code>MUSHEGH_PROTOCOL_GOODNIGHT_PASSWORD</code></td><td>“Going to bed, stop yourself.”</td></tr>
          <tr><td><code>phoenix</code></td><td>Restarts Mushegh (kills the old process, starts a fresh one)</td><td><code>MUSHEGH_PROTOCOL_PHOENIX_PASSWORD</code></td><td>After a config change, when something looks wedged</td></tr>
          <tr><td><code>ragnarok</code></td><td>Restarts the laptop</td><td><code>MUSHEGH_PROTOCOL_RAGNAROK_PASSWORD</code></td><td>The nuclear option when only a reboot saves the day</td></tr>
          <tr><td><code>backup</code></td><td>Archives L1/L2 memory to a zip</td><td><code>MUSHEGH_PROTOCOL_BACKUP_PASSWORD</code></td><td>Before risky changes or for off-site copies</td></tr>
          <tr><td><code>ping</code></td><td>Sends a phone push test via ntfy</td><td><code>MUSHEGH_PROTOCOL_PING_PASSWORD</code></td><td>“Did the push channel wake up?”</td></tr>
          <tr><td><code>diagnostics</code></td><td>Writes a local config health report</td><td><code>MUSHEGH_PROTOCOL_DIAGNOSTICS_PASSWORD</code></td><td>When something looks off and you want a snapshot</td></tr>
          <tr><td><code>auditpack</code></td><td>Archives the audit logs</td><td><code>MUSHEGH_PROTOCOL_AUDITPACK_PASSWORD</code></td><td>For retention / offline review</td></tr>
          <tr><td><code>checkpoint</code></td><td>Archives non-secret context (memory/persona/docs)</td><td><code>MUSHEGH_PROTOCOL_CHECKPOINT_PASSWORD</code></td><td>A safe “snapshot of who I am” you can hand to someone</td></tr>
        </tbody>
      </table>

      <h2>How a protocol runs</h2>
      <ol>
        <li>You say: <em>“run protocol phoenix, password X.”</em> (or pass it via tool args).</li>
        <li>The agent checks the tool is in the confirm tier and asks you to affirm.</li>
        <li>You say yes. <code>brain/protocols.py</code> verifies the password with <code>hmac.compare_digest</code>.</li>
        <li>The script in <code>src/mushegh/protocols/&lt;name&gt;.py</code> is launched <strong>detached</strong> with the parent PID + repo root + python exe. The detached script then waits, kills the parent, and starts a fresh process where applicable.</li>
        <li>Mushegh speaks the protocol's signature line (<em>“Rebooting myself, sir. Back in a moment.”</em>) before the kill so you don't think it hung.</li>
      </ol>
      <p>
        Passwords are never spoken, never logged, and the audit log redacts them by key shape. If a
        password is missing or wrong, the protocol refuses and Mushegh tells you; the runner never executes
        anything. Disable the whole class with <code>MUSHEGH_PROTOCOLS_ENABLED=false</code> in <code>.env</code>.
      </p>

      <h2>Restore a memory backup</h2>
      <p>
        Disaster recovery for the <code>backup</code> protocol. Run by a human from the command line:
      </p>
      <pre><code>{`# Preview (default: refuses if memory/ is non-empty)
uv run python -m mushegh.protocols.backup restore backups/mushegh-memory-20260702-030000.zip

# Overwrite a live memory dir (destructive)
uv run python -m mushegh.protocols.backup restore backups/mushegh-memory-20260702-030000.zip --force`}</code></pre>
      <p>
        The daily scheduler also writes a fresh <code>backups/mushegh-memory-&lt;stamp&gt;.zip</code> every
        night at 03:30 (<code>schedule_daily_backup</code>) and prunes the oldest beyond the most recent
        14.
      </p>

      <h2>Non-privileged routines</h2>
      <p>
        A separate, lighter class of <em>behaviour</em> routines need no password — they flip a
        runtime mode. See <Link href="/modes">Modes</Link> for <code>focus</code>, <code>lockdown</code>,
        <code>guest</code>, <code>commute</code>, and <code>normal</code>.
      </p>

      <div className="callout warn">
        <span className="k">Rotate the placeholders.</span> Even though the wizard generates them, if you
        later edited <code>.env</code> by hand and shipped placeholders to a public fork, rotate every
        <code>MUSHEGH_PROTOCOL_*_PASSWORD</code> + the <code>MUSHEGH_API_AUTH_TOKEN</code> before exposing
        anything to the network. See <Link href="/security">Security</Link> &sect;5.
      </div>
    </>
  );
}