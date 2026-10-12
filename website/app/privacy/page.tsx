import Link from "next/link";

export const metadata = { title: "Privacy & what it stores — Mushegh" };

export default function Privacy() {
  return (
    <>
      <h1>Privacy &amp; what it stores</h1>
      <p className="lead">
        An assistant that lives with you accumulates a record of your life. The question is not
        whether it stores things — it must, or it cannot remember you — but whether you can{" "}
        <em>ask it</em> what it has, and whether the answer is generated from the real stores rather
        than written down once and left to rot.
      </p>

      <h2>Ask it out loud</h2>
      <table>
        <thead><tr><th>Say</th><th>What happens</th></tr></thead>
        <tbody>
          <tr>
            <td>“What do you know about me?”</td>
            <td>
              <code>what_you_know</code> — every store, how many there are, how large they are, which
              expire and which are kept indefinitely, and which never leave the laptop.
            </td>
          </tr>
          <tr>
            <td>“How long do you keep that?”</td>
            <td><code>data_retention</code> — the long form, one line per store, for reading rather than hearing.</td>
          </tr>
          <tr>
            <td>“Forget what I said about X.”</td>
            <td>
              <code>forget</code> — and it is a real deletion across every layer that holds it, not a
              tombstone. The test for it deletes, then goes back and checks the fact cannot be
              recalled by any path.
            </td>
          </tr>
          <tr>
            <td>“Stop tracking my activity.”</td>
            <td>The activity group carries its own off switch; presence data is on a rolling window regardless.</td>
          </tr>
        </tbody>
      </table>

      <h2>The inventory is the source, not a description of it</h2>
      <p>
        <code>brain/inventory.py</code> declares every store: what it holds, in plain words, and how
        long it is kept. Two rules keep it honest, and both are enforced by the build rather than by
        discipline:
      </p>
      <ul>
        <li>
          <strong>Nothing undeclared may exist.</strong> A file that appears in the state directory
          and is not declared fails the build. You cannot add a quiet little cache of someone's
          messages and forget to mention it.
        </li>
        <li>
          <strong>Retention is executed, not documented.</strong> A daily job deletes what is past its
          declared window. Before that, every store's retention lived in somebody's head and one
          lived in a setting nothing read — which is the same as having none.
        </li>
      </ul>

      <h2>Roughly what that looks like</h2>
      <table>
        <thead><tr><th>Store</th><th>Kept</th><th>Holds</th></tr></thead>
        <tbody>
          <tr><td><code>audit/</code></td><td>90 days</td><td>every tool call, with values scrubbed of secrets</td></tr>
          <tr><td><code>mushegh_presence.sqlite</code></td><td>30 days</td><td>which app was in the foreground, and how idle the machine was</td></tr>
          <tr><td><code>mushegh_jobs.sqlite</code></td><td>30 days</td><td>background work queued and finished</td></tr>
          <tr><td><code>traces/</code></td><td>14 days</td><td>what each turn cost and how it classified</td></tr>
          <tr><td><code>memory/learned/</code></td><td>indefinite</td><td>the facts you asked it to remember</td></tr>
          <tr><td><code>mushegh_graph.sqlite</code></td><td>indefinite</td><td>who and what relate to whom — people, projects, places</td></tr>
          <tr><td><code>voiceprint.json</code>, <code>owner.npy</code></td><td>indefinite, <strong>never leaves the laptop</strong></td><td>your voice and face embeddings</td></tr>
        </tbody>
      </table>
      <p>
        Ask the running system rather than trusting this table — it prints the live one, with real
        sizes. Biometrics are the one category with a hard rule: they are not synced, not deployed,
        and not in version control, because a face embedding is not a password you can change.
      </p>

      <div className="callout good">
        <span className="k">What leaves the machine.</span> Your voice goes to whichever STT you
        configured, your text to whichever LLM — both are your choice, and both have fully local
        options (Whisper or Moonshine, Piper or Kokoro, Ollama) that keep the whole loop on your own
        hardware. Nothing else is uploaded anywhere. See <Link href="/security">Security</Link> for
        the enforced action model and <Link href="/vault">Vault &amp; memory</Link> for the layers.
      </div>
    </>
  );
}
