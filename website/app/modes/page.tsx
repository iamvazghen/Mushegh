import Link from "next/link";

export default function Modes() {
  return (
    <>
      <h1>Modes — the light “personality switches”</h1>
      <p className="lead">
        Unlike the password-gated <Link href="/protocols">protocols</Link> (which run privileged system
        scripts), modes are <em>behavioural</em>: Mushegh flips a flag and other parts of the brain read
        it. Process-local, reset on restart, scoped to the live session.
      </p>

      <table>
        <thead>
          <tr><th>Mode</th><th>What it changes</th><th>Spoken</th></tr>
        </thead>
        <tbody>
          <tr><td><code>focus</code> / <code>deepwork</code></td><td>Holds non-urgent proactive interjections for N minutes (default via voice: “focus mode for an hour”)</td><td><em>“Focus mode for 60 minutes, sir.”</em></td></tr>
          <tr><td><code>lockdown</code> / <code>privacy</code></td><td>Go quiet: no unprompted speech, a cue to stop listening to the room</td><td><em>“Lockdown on, sir. I'll go quiet.”</em></td></tr>
          <tr><td><code>guest</code></td><td>Relaxes speaker biometrics so other people can interact too</td><td><em>“Guest mode on — anyone can talk to me.”</em></td></tr>
          <tr><td><code>commute</code></td><td>Keep replies extra brief (a hint the persona and edge honour)</td><td><em>“Commute mode — short replies.”</em></td></tr>
          <tr><td><code>normal</code></td><td>Clears all modes back to default</td><td><em>“Back to normal, sir.”</em></td></tr>
        </tbody>
      </table>

      <p>
        The brain exposes these through the <code>routine</code> tool (“<em>set routine focus 60</em>”,
        “<em>clear routine</em>”). The proactive engine respects <code>focus</code> and{" "}
        <code>lockdown</code> automatically — no interjection can fire while either is active.
      </p>

      <div className="callout">
        <span className="k">Process-local.</span> Modes reset on brain restart — they are a
        “for now” thing, not a configuration. To persist a preference across restarts, set
        the relevant <code>MUSHEGH_</code> env var in <code>.env</code>.
      </div>
    </>
  );
}