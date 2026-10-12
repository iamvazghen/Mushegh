import Link from "next/link";

export default function Networking() {
  return (
    <>
      <h1>Networking — the Tailnet requirement</h1>
      <p className="lead">
        Mushegh is multi-device. The secure way to connect your phone, laptop, and glasses to the
        same 24/7 brain on a VPS is a private mesh VPN — a <strong>Tailnet</strong>.
      </p>

      <div className="callout warn">
        <span className="k">Rule of thumb.</span> If a device should talk to Mushegh, it must be{" "}
        <strong>on your Tailnet and logged in</strong>. Off the tailnet, only the public fallbacks
        work (Telegram bot messages, ntfy push).
      </div>

      <h2>Why a Tailnet</h2>
      <p>
        The brain binds <code>0.0.0.0</code> so devices can reach it — but you must never expose
        that on the public internet. A Tailnet (
        <a href="https://tailscale.com" target="_blank" rel="noreferrer">Tailscale</a>, WireGuard under
        the hood) gives every one of <em>your</em> devices a stable private <code>100.x.y.z</code>{" "}
        address that is unroutable to anyone else. The brain is still additionally guarded by the{" "}
        <code>MUSHEGH_API_AUTH_TOKEN</code> bearer the wizard generates — defence in depth.
      </p>

      <h2>Install Tailscale on every device</h2>
      <p>Sign in to the same Tailscale account everywhere:</p>
      <table>
        <thead>
          <tr><th>Device</th><th>How</th></tr>
        </thead>
        <tbody>
          <tr><td>VPS / brain host (Linux)</td><td><code>curl -fsSL https://tailscale.com/install.sh | sh</code> then <code>sudo tailscale up</code></td></tr>
          <tr><td>Laptop (Windows/Linux)</td><td>install the Tailscale app, sign in</td></tr>
          <tr><td>Mac (macOS)</td><td>Tailscale from the Mac App Store (or <code>brew install --cask tailscale</code>), sign in</td></tr>
          <tr><td>iPhone</td><td>Tailscale from the App Store, sign in (keep it connected — use the App Store settings)</td></tr>
          <tr><td>Android</td><td>Tailscale from Google Play, sign in (keep it connected — disable battery optimisation for Tailscale)</td></tr>
          <tr><td>Any client you write</td><td>speak the <code>/voice</code> protocol from a device on the tailnet</td></tr>
          <tr><td>Home Assistant</td><td>the brain reaches HA over the tailnet (or your LAN)</td></tr>
        </tbody>
      </table>
      <p>
        Find your brain host's tailnet IP with <code>tailscale ip -4</code> on the VPS.
      </p>

      <h2>How each connection uses it</h2>
      <table>
        <thead>
          <tr><th>Path</th><th>Endpoint</th><th>What it carries</th></tr>
        </thead>
        <tbody>
          <tr><td>Laptop / glasses edge &rarr; brain</td><td><code>ws://&lt;brain-tailnet-ip&gt;:8765/voice</code></td><td>transcripts &rarr; streamed reply deltas</td></tr>
          <tr><td>PC-control executor &rarr; brain</td><td><code>ws://&lt;brain-tailnet-ip&gt;:8765/control</code></td><td>system-tool commands run on the laptop</td></tr>
          <tr><td>iPhone Siri Shortcut &rarr; brain</td><td><code>http://&lt;brain-tailnet-ip&gt;:8766/talk?token=…</code></td><td>dictated text in, MP3 voice out</td></tr>
          <tr><td>Phone web client</td><td><code>http://&lt;brain-tailnet-ip&gt;:8766/iphone/</code></td><td>served as a static page with the token injected</td></tr>
          <tr><td>Recurring-reminder ticker</td><td><code>http://&lt;brain-tailnet-ip&gt;:8770</code></td><td>VPS-side recurring ntfy push service</td></tr>
          <tr><td>Live-check weekly timer</td><td>(local to VPS)</td><td>cron + bot alert on failure</td></tr>
        </tbody>
      </table>
      <p>
        No port-forwarding, no public exposure, no dynamic-DNS. Set these in <code>.env</code> (the
        wizard's <em>vps</em> deployment shape fills <code>MUSHEGH_BRAIN_HOST=0.0.0.0</code>,
        generates the token, and builds the edge URL from the host you give it). See{" "}
        <Link href="/configuration">Configuration</Link>.
      </p>

      <h2>Firewall</h2>
      <p>
        On a multi-device LAN test (no tailnet) you'd open ports 8765/8766 in the OS firewall;
        over a tailnet you generally don't need to, since traffic arrives on the Tailscale
        interface. Keep the public internet closed to these ports regardless.
      </p>
    </>
  );
}