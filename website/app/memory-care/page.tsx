import Link from "next/link";

export default function MemoryCare() {
  return (
    <>
      <h1>Memory care — how a 24/7 companion stays sharp</h1>
      <p className="lead">
        A 24/7 companion accumulates state every day. Three small jobs keep the learned/journal stores
        healthy: deduping near-identical facts, capping the active set, rotating old journals. Plus a
        self-health check that notices when the assistant's own organs fail.
      </p>

      <h2>1 · Learned-fact extraction (background_review)</h2>
      <p>
        After every N turns (default 6, <code>MUSHEGH_SELF_IMPROVE_EVERY_TURNS</code>), a background
        pass replays the recent conversation, asks the LLM what <em>durable</em> facts about the owner
        are worth remembering for months (preferences, decisions, people, projects), and writes them into
        L1 learned memory (<code>STORE.remember</code>). Adapted from
        <a href="https://github.com/NousResearch/hermes-agent" target="_blank" rel="noreferrer">NousResearch/hermes-agent's <code>background_review</code></a>.
      </p>
      <ul>
        <li>Off the hot path — never slows a reply.</li>
        <li>Only add/dedup; never delete.</li>
        <li>Never touches the live conversation or the main model's prompt.</li>
        <li>Degrades silently on any error.</li>
      </ul>
      <p>Disable with <code>MUSHEGH_SELF_IMPROVE_ENABLED=false</code>.</p>

      <h2>2 · Daily memory hygiene</h2>
      <p>
        Registered on the brain scheduler daily at 04:00 (your timezone). Three idempotent jobs:
      </p>
      <table>
        <thead>
          <tr><th>Job</th><th>What</th><th>Where</th></tr>
        </thead>
        <tbody>
          <tr><td><code>compact_learned</code></td><td>Drop near-duplicate learned facts (token-set Jaccard &ge; 0.82), keep newest</td><td><code>memory/learned/</code></td></tr>
          <tr><td><code>cap_learned</code></td><td>Archive the oldest beyond <code>max_facts=500</code> into <code>memory/learned/archive/</code></td><td><code>memory/learned/archive/</code></td></tr>
          <tr><td><code>rotate_journals</code></td><td>Move journal day-files older than 35 days into <code>memory/journal/archive/</code></td><td><code>memory/journal/archive/</code></td></tr>
        </tbody>
      </table>
      <p>
        Archived notes stay on disk forever — <code>recall()</code> and <code>recent_digest()</code>{" "}
        glob the active directory only, so the prompt budget stays bounded without losing history.
      </p>

      <h2>3 · Daily memory backup</h2>
      <p>
        At 03:30 (your timezone) the scheduler zips the entire <code>memory/</code> directory into{" "}
        <code>backups/mushegh-memory-&lt;stamp&gt;.zip</code> and prunes the oldest beyond the most recent 14.
        Restore manually with <code>uv run python -m mushegh.protocols.backup restore &lt;zip&gt;</code>{" "}
        (refuses a non-empty <code>memory/</code> unless <code>--force</code>).
      </p>

      <h2>4 · Self-health</h2>
      <p>
        The <code>self_health</code> tool answers “are you all right?” with a snapshot of the
        components Mushegh depends on:
      </p>
      <table>
        <thead>
          <tr><th>Component</th><th>Check</th><th>Failure consequence</th></tr>
        </thead>
        <tbody>
          <tr><td>L3 Obsidian vault</td><td>Readable, lists files (3 retries w/ short grace to ride out the 15-min sync window)</td><td>Proactive Signal “I've lost read access to your vault”</td></tr>
          <tr><td>Always-on VPS ticker</td><td><code>GET &lt;ticker_url&gt;/health</code> reachable</td><td>Signal “recurring reminders may not fire”</td></tr>
          <tr><td>L4 hot-cache</td><td>Backend label (redis vs in-process)</td><td>No proactive signal (cache is a speed win, not a hard dep)</td></tr>
        </tbody>
      </table>
      <p>
        Each check is fail-quiet: a check that itself errors is reported as degraded, never as a
        crash. The snapshot is also exposed as a proactive signal source so the tick can surface failures
        on its own, then repeat-suppression keeps it from nagging.
      </p>

      <h2>5 · Vault validation at boot</h2>
      <p>
        The brain refuses to start quietly with a broken L3. <code>brain/context.validate_vault()</code>{" "}
        runs at startup, logs the note count it sees, and the proactive engine picks up the failure as a
        signal if it later turns bad. The retry-with-short-grace guards against the 15-min sync's
        delete&rarr;move window firing a false alarm.
      </p>

      <h2>6 · What the live picture looks like</h2>
      <ul>
        <li>You talk. Every 6 turns, a background pass writes durable facts to <code>memory/learned/</code>.</li>
        <li>At 03:30 the scheduler zips <code>memory/</code> to <code>backups/</code>.</li>
        <li>At 04:00 the hygiene pass dedups, caps, and rotates. The prompt stays lean.</li>
        <li>All day, the vault check + ticker check surface failures via the proactive engine, gated by repeat-suppression so it never nags.</li>
      </ul>

      <div className="callout">
        <span className="k">Files kept out of git.</span> <code>memory/learned/</code>,{" "}
        <code>memory/journal/</code>, <code>audit/</code>, <code>backups/</code>, and{" "}
        <code>voiceprint.json</code> are gitignored — they are personal context, not framework code.
        See <Link href="/security">Security</Link> for the full list.
      </div>
    </>
  );
}