import Link from "next/link";

export default function Vault() {
  return (
    <>
      <h1>Obsidian vault & memory</h1>
      <p className="lead">
        Mushegh has six layers of memory. Your Obsidian vault is the big one — its long-term,
        read (and optionally write) knowledge base. Here's how to connect it, switch on every
        memory capability, and how it stays healthy (see <Link href="/memory-care">Memory care</Link>
        for the daily hygiene).
      </p>

      <h2>The six layers</h2>
      <table>
        <thead><tr><th>Layer</th><th>What it is</th><th>Enable</th></tr></thead>
        <tbody>
          <tr><td><strong>L0 Working</strong></td><td>the live conversation; restart-durable, smart-reset on long idle</td><td>always on</td></tr>
          <tr><td><strong>L1 Learned facts</strong></td><td>durable one-line facts it saves about you (<code>remember</code>); auto-extracted by <code>background_review</code> every N turns</td><td>on by default (<code>MUSHEGH_MEMORY_ENABLED=true</code>)</td></tr>
          <tr><td><strong>L2 Journal</strong></td><td>a daily journal written at session end + a durable log of proactive nudges</td><td>on by default</td></tr>
          <tr><td><strong>L3 Obsidian vault</strong></td><td>your notes — searched & read every turn</td><td><code>MUSHEGH_VAULT_PATH</code> (below)</td></tr>
          <tr><td><strong>L4 Hot cache</strong></td><td>in-process TTL, per process</td><td>always on, no setting</td></tr>
          <tr><td><strong>L5 Semantic recall</strong></td><td>recall by meaning, not just keywords</td><td>Jina API or <code>uv pip install sentence-transformers</code></td></tr>
        </tbody>
      </table>

      <h2>1 · Connect your Obsidian vault (L3)</h2>
      <p>Point Mushegh at the folder of Markdown notes you want it to read. In <code>.env</code>:</p>
      <pre><code>{`MUSHEGH_VAULT_PATH=C:\\Users\\you\\Documents\\Obsidian Vault   # Windows
# MUSHEGH_VAULT_PATH=/home/you/obsidian-vault                  # Linux/Mac`}</code></pre>
      <p>
        It's validated at startup (3 retries with a short grace to ride out a 15-min sync
        delete&rarr;move window). Any folder of <code>.md</code> files works — it doesn't have
        to be Obsidian. Tuning knobs: <code>MUSHEGH_VAULT_SEARCH_MAX_RESULTS</code> (default 6) and{" "}
        <code>MUSHEGH_VAULT_READ_MAX_CHARS</code> (default 4000).
      </p>
      <p><strong>Reading is on as soon as the path is set.</strong> Try it by voice: <em>“search my
      vault for the rabbit-farm note and read me the summary.”</em> Tools:{" "}
      <code>search_vault(query)</code>, <code>read_vault_note(path)</code>.</p>

      <h2>2 · Enable WRITING to the vault</h2>
      <p>
        Writing is <strong>off by default</strong> on purpose: if your vault is a one-way sync target
        (e.g. a local mirror of a server-authoritative vault), local edits get clobbered. Turn it on
        only on the host that <em>owns</em> the vault:
      </p>
      <pre><code>{`MUSHEGH_VAULT_WRITABLE=true`}</code></pre>
      <p>
        Then <code>write_vault(path, text)</code> can save notes (path-scoped, no traversal). On the
        host that owns the vault this is safe; on a mirror, leave it false and let the authoritative
        host write.
      </p>

      <h2>3 · Learned facts & journal (L1 / L2)</h2>
      <p>
        These are Mushegh's own memory, stored as Markdown under{" "}
        <code>memory/learned/</code> and <code>memory/journal/</code> (gitignored). They're on by
        default. Tools you can use by voice:
      </p>
      <ul>
        <li><code>remember(text, tags)</code> — “remember that I keep rabbits at the farm.” Mushegh also extracts durable facts on its own (<code>MUSHEGH_SELF_IMPROVE_EVERY_TURNS</code>, default 6).</li>
        <li><code>recall(query)</code> — “what do you know about my farm?”</li>
        <li><code>forget(query)</code> — drop a stored fact.</li>
        <li><code>read_journal()</code> — “what did we do yesterday?”</li>
      </ul>
      <p>
        The most recent learned facts are injected into the system prompt at startup (capped by{" "}
        <code>MUSHEGH_MEMORY_DIGEST_MAX</code>, default 12); <code>recall</code> reaches older ones. See{" "}
        <Link href="/memory-care">Memory care</Link> for the daily dedup / cap / rotate hygiene that
        keeps L1 lean.
      </p>

      <h2>4 · Recall by meaning (L5, optional)</h2>
      <pre><code>{`# Default: Jina embeddings API if MUSHEGH_JINA_API_KEY is set (no torch).
# Or fully local: uv pip install sentence-transformers  (~1 GB model, first use)`}</code></pre>
      <p>
        With either installed, <code>recall</code> matches on meaning (“my bunnies”
        &rarr; your rabbit-farm note), not just keywords. It's a graceful no-op until one of them is
        available.
      </p>

      <h2>5 · Working memory (L0) — restart durable</h2>
      <p>
        A snapshot of the rolling conversation thread is written to disk each turn (<code>MUSHEGH_SESSION_PERSIST_PATH</code>;
        default <code>&lt;repo&gt;/mushegh_session.json</code>). After a brain restart or crash, Mushegh
        resumes mid-thread — a snapshot older than the idle-reset window is treated as
        expired (journalled + dropped).
      </p>

      <div className="callout warn">
        <span className="k">Sync direction matters.</span> If your vault is mirrored from a server
        (the common 24/7 setup), treat the server as authoritative: write there, keep the local
        mirror read-only (<code>MUSHEGH_VAULT_WRITABLE=false</code>) so a sync never clobbers an edit.
      </div>

      <p style={{ marginTop: 22 }}>
        See also <Link href="/architecture#memory">Architecture → Memory</Link> for how the layers
        compose and <Link href="/integrations">Integrations</Link> for every other tool.
      </p>
    </>
  );
}