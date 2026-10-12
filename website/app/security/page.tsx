import Link from "next/link";

export default function Security() {
  return (
    <>
      <h1>Security</h1>
      <p className="lead">
        Mushegh runs shell commands, drives a browser, sends messages, and edits its own code. The
        safety model makes that trustworthy: least surprise, full reversibility, deny-by-default.
      </p>
      <div className="callout">
        Full detail is in <code>SECURITY.md</code> in the repo. This page is the summary; read the file
        before you deploy.
      </div>

      <h2>1 · Confirmation tier — enforced in code</h2>
      <p>
        Outward-facing or destructive tools (send a message/email, delete a file, kill a process, run
        PowerShell, write to Notion/calendar, smart-home locks, self-edits/commits, run a protocol) are
        in a confirmation tier that is <strong>enforced in the agent's execution path</strong>
        — not merely requested in the prompt. The agent <em>blocks</em> the first attempt, reads the
        action back, and runs it only after your next turn affirms it. One “yes” authorises
        exactly one action. So even a weak model that ignores the prompt cannot fire a consequential
        tool unprompted. Reads and lookups are never gated.
      </p>
      <p>The tier (<code>proactive.CONFIRM_TIER</code>) covers:</p>
      <ul>
        <li>Messaging/outbound: <code>send_telegram</code>, <code>send_email</code>, <code>send_push</code>.</li>
        <li>Machine: <code>file_op</code> (deletes), <code>process_op</code> (kill/start), <code>run_powershell</code>, <code>browser</code>.</li>
        <li>Calendar/home/Notion: <code>create_event</code>, <code>ha_call</code> (locks/alarms/covers especially), <code>notion_append</code>, <code>notion_comment</code>, <code>notion_create_page</code>.</li>
        <li>Self-improvement: <code>write_source</code>, <code>git_commit</code>, <code>git_push</code>, <code>git_revert</code>.</li>
        <li>Protocols: <code>run_protocol</code>.</li>
      </ul>

      <h2>2 · Tools that can't be fired even if the model wants to</h2>
      <ul>
        <li><strong>Catastrophic-command refusal</strong> (<code>agent._CATASTROPHIC_RE</code>): “wipe C:\Windows” / “rm -rf /” / “format c:” are refused BEFORE the model can emit the destructive call. Tested hermetically.</li>
        <li><strong>Catastrophic-op refuse list</strong> on the elevated <Link href="/pc-control">PC executor</Link>: format, whole-drive delete, registry hklm, diskpart, etc.</li>
        <li><strong>Forced <code>tool_choice=required</code></strong> on unambiguous imperative commands (set home, set reminder, play X, send telegram, …): a weak model can't speak a hollow confirmation without calling the tool. Scoped tightly so normal chat still flows on <code>auto</code>.</li>
        <li><strong>Multi-intent nudge</strong>: a compound request (“look it up AND remember it”) gets a completion nudge so the loop doesn't stop after only one part.</li>
      </ul>

      <h2>3 · Secrets</h2>
      <ul>
        <li>All secrets live in a git-ignored <code>.env</code>; only <code>.env.example</code> (no values) is committed.</li>
        <li>The following are explicitly git-ignored: <code>.env</code> and any <code>.env.*</code> (except the example), <code>*.session</code> / <code>*.session-journal</code> (Telegram / Telethon), <code>voiceprint.json</code>, <code>mushegh_jobs.sqlite</code>, <code>mushegh_tasks.sqlite</code>, <code>audit/</code>, <code>backups/</code>, <code>.mushegh-browser/</code> (persistent browser profile — holds login cookies), and the personal memory (<code>memory/learned/</code>, <code>memory/journal/</code>).</li>
        <li>The audit log redacts secrets two ways: by argument KEY (<code>password | token | secret | api_key | apikey | auth | credential</code>), and a value-scrub that removes any real <code>.env</code> value from the whole line. So a secret that leaks via a tool result (e.g. PowerShell echoing an env var) never reaches disk.</li>
        <li>Use the narrowest scopes (fine-grained GitHub PAT, Notion deny-by-default sharing, your own Google OAuth app with yourself as the only test user).</li>
      </ul>

      <h2>4 · Guardrails — filesystem & system</h2>
      <ul>
        <li><strong>File delete</strong> refuses anything under <code>MUSHEGH_SYSTEM_PROTECTED_PATHS</code> (default <code>C:\Windows, C:\Program Files, C:\Program Files (x86)</code>) and drive roots.</li>
        <li><strong>System tools also refuse Mushegh's own secrets/state</strong>: <code>.env</code>, <code>*.session</code>, <code>voiceprint.json</code>, <code>.git/</code>, <code>audit/</code>, <code>backups/</code>, <code>.mushegh-browser/</code>. “Delete the .env” can never land through the system tools.</li>
        <li><strong>Elevation is explicit</strong>: <code>run_powershell(as_admin=true)</code> raises a Windows UAC prompt you must accept; nothing silently elevates.</li>
        <li><strong>The browser is visible by default</strong> (<code>MUSHEGH_BROWSER_HEADLESS=false</code>) so you can watch what it does and complete logins yourself.</li>
      </ul>

      <h2>5 · Protocols (password-gated)</h2>
      <p>
        The <Link href="/protocols">eight privileged routines</Link> (goodnight / phoenix / ragnarok /
        backup / ping / diagnostics / auditpack / checkpoint) are password-gated. Mushegh asks for the
        password first; it's compared in constant time (<code>hmac.compare_digest</code>); a wrong or
        missing password runs nothing. The <code>mushegh-setup</code> wizard generates a strong unique
        password for all eight on first run, so a fork is never shipped on placeholders. Passwords are
        never spoken or logged.
      </p>

      <h2>6 · Self-improvement guardrails</h2>
      <ul>
        <li><strong>Repo-scoped</strong>: <code>read_source / write_source / list_source</code> resolve paths and refuse anything outside the repository (no traversal) and refuse secrets.</li>
        <li><strong>Reversible-only git</strong>: <code>status | diff | log | new_branch | commit | push | revert</code>. <strong>No</strong> <code>reset</code>, <code>force-push</code>, <code>rebase</code>, <code>amend</code>, <code>clean</code>, or branch-delete tool — by design. History is added to, never rewritten; a revert is a new commit.</li>
        <li><strong>Verify-then-commit</strong>: <code>run_tests</code> / <code>lint</code>; the self-improvement playbook commits only green code, on a branch, after your confirmation.</li>
        <li><strong>Confirm-gated</strong>: writes, commits, and pushes are in the confirmation tier.</li>
      </ul>

      <h2>7 · Speaker biometrics</h2>
      <p>
        With <code>MUSHEGH_SPEAKER_ID_ENABLED=true</code> and an enrolled voiceprint, Mushegh obeys{" "}
        <strong>only your voice</strong>. It's off until you enroll — and deliberately fails{" "}
        <em>open</em> (accepts all) so a fresh install can never lock you out.
      </p>

      <h2>8 · The OpenClaw fleet is gated</h2>
      <p>
        Mushegh can <em>consult</em> an external multi-agent fleet, but it touches shared infrastructure
        and ships <strong>off by default</strong>. Arm it deliberately per session, or for a deployment
        via <code>MUSHEGH_FLEET_AUTHORIZED=true</code>. Until armed, <code>delegate_to_fleet</code> returns
        a safe sentinel and performs no network action. See <Link href="/fleet">Fleet</Link>.
      </p>

      <h2>9 · Bot split — Mushegh vs ispir</h2>
      <p>
        The assistant uses ONLY the Mushegh bot (<code>@afon_iamvazghen_bot</code>) for both sends and
        the bridge poll. The ispir / OpenClaw bot (<code>@ispir</code>) is the fleet's dedicated bot.
        Never share tokens between them. See <Link href="/bots">Bots & send-paths</Link>.
      </p>

      <h2>10 · Audit trail</h2>
      <p>
        Every tool call is appended (best-effort, fail-quiet) to <code>audit/&lt;date&gt;.jsonl</code> with a
        timestamp, the tool name, <strong>redacted</strong> arguments, success flag, and a clipped
        result. The trust-and-debug record: you can see exactly what Mushegh did. The audit directory
        is git-ignored (it can contain personal context).
      </p>

      <h2>11 · Network & privacy posture</h2>
      <ul>
        <li><strong>Local-first.</strong> Audio capture, wake word, VAD, and (optionally) STT/TTS run on your machine. Cloud STT/TTS (Deepgram/ElevenLabs) are opt-in quality choices behind provider flags.</li>
        <li><strong>Loopback by default.</strong> The brain WebSocket (<code>/voice</code>, <code>/control</code>) and the HTTP sidecar (<code>/talk</code>) bind <code>127.0.0.1</code>. To reach them from a phone/glasses, bind <code>0.0.0.0</code> <strong>and set <code>MUSHEGH_API_AUTH_TOKEN</code></strong> — remote clients must then present the token as <code>Authorization: Bearer &lt;token&gt;</code> (native) or <code>?token=&lt;token&gt;</code> (browser / Siri Shortcut). Requests without it are refused.</li>
        <li><strong>Prefer a private overlay.</strong> Put the brain host on Tailscale/WireGuard rather than the public internet; the bearer token guards the port, the overlay keeps it unroutable.</li>
        <li><strong>Graceful degradation</strong> means an unconfigured integration makes no network calls at all.</li>
      </ul>

      <h2>12 · Reporting a vulnerability</h2>
      <p>
        This is a personal project, not a service. If you find a way to bypass the path/secret guards,
        the confirmation tier, or a protocol password — open a <strong>private</strong> report (a
        private issue or direct contact with the repository owner), not a public issue. Include
        reproduction steps and the affected file/function.
      </p>

      <h2>13 · Operator responsibilities (you, if you fork & deploy)</h2>
      <ul>
        <li><strong>Run <code>mushegh-setup</code></strong> — it generates the brain auth token and the eight protocol passwords.</li>
        <li><strong>Keep your repo private</strong> if it carries personal data (<code>memory/</code>, <code>personality/</code>).</li>
        <li><strong>Rotate any key ever shared in plaintext</strong> (chat, screenshare, a committed mistake) and use the narrowest scope that works.</li>
        <li><strong>Don't expose the brain without the bearer token</strong>, and prefer a private overlay network.</li>
        <li>Review <Link href="/production">Production readiness</Link> before enabling outward-facing integrations, and enroll a voiceprint if others share your space.</li>
        <li>Treat the host running the brain as trusted — anyone with shell on it can read <code>.env</code>.</li>
        <li>Arm the fleet deliberately (<code>MUSHEGH_FLEET_AUTHORIZED</code>).</li>
      </ul>
    </>
  );
}