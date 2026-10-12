import Link from "next/link";

export default function PCControl() {
  return (
    <>
      <h1>Remote PC control — brain drives your laptop</h1>
      <p className="lead">
        The brain's system tools (files, processes, PowerShell, opening apps/URLs, the browser) run
        on whatever host the brain runs on. On the VPS that's the wrong machine. So the laptop
        runs a small executor that connects <strong>out</strong> to the brain over the tailnet and
        registers itself — the system tools then <em>forward</em> each command to it and await the
        result. No inbound ports needed on the laptop.
      </p>

      <h2>1 · The link</h2>
      <p>
        The brain exposes a second WebSocket path, <code>/control</code> (port 8765), guarded by the
        same bearer token. The laptop runs <code>edge/pc_agent.py</code> in the background (autostart
        installer), dials the brain's <code>/control</code> URL on the tailnet, sends a{" "}
        <code>pc_hello</code> with its hostname + code version, and is ready.
      </p>
      <ul>
        <li>One executor at a time (the latest registered wins).</li>
        <li>If none is connected, the tools fall back to running locally (correct when the brain itself runs on the laptop) or report the laptop offline (on the VPS).</li>
        <li>The existing system-tool guards (protected paths, Mushegh's own secrets) still apply — they run inside the forwarded handler on the laptop.</li>
        <li>Ping timeout 75s, supervised reconnect with exponential backoff + jitter.</li>
      </ul>

      <h2>2 · What runs where</h2>
      <table>
        <thead>
          <tr><th>Operation</th><th>Where it runs</th></tr>
        </thead>
        <tbody>
          <tr><td><code>file_op</code> create / read / write / list</td><td>Wherever the executor is — brain forwards to laptop when the laptop is the executor</td></tr>
          <tr><td><code>file_op</code> delete</td><td>Forwarded, AND refuses protected paths and Mushegh's own secrets (<code>.env</code>, sessions, voiceprint, <code>audit/</code>, <code>backups/</code>, <code>.git</code>, <code>.mushegh-browser</code>)</td></tr>
          <tr><td><code>process_op</code> list / kill / start</td><td>Forwarded</td></tr>
          <tr><td><code>run_powershell</code></td><td>Forwarded; optional elevation raises a UAC prompt</td></tr>
          <tr><td><code>browser</code> (visible Chromium)</td><td>Forwarded; profile and cookies live on the laptop</td></tr>
          <tr><td><code>open_app</code> / <code>open_url</code></td><td>Forwarded</td></tr>
        </tbody>
      </table>

      <h2>3 · The catastrophic-op refuse list</h2>
      <p>
        The laptop executor carries a last-line refuse list — substring match on the flattened
        command — for commands that have no legitimate use from the assistant:
      </p>
      <pre><code>{`_REFUSED_SUBSTRINGS = (
    "format-volume", "format c:", "format d:", "clear-disk", "initialize-disk",
    "remove-item c:\\ ", "remove-item -path c:\\ ", "rd /s /q c:\\",
    "del /f /s /q c:\\", "cipher /w", "bcdedit", "vssadmin delete",
    "reg delete hklm", "diskpart",
)`}</code></pre>
      <p>
        Last-line defense after the brain's own guards and the confirm tier: a compromised or
        confused brain still cannot wipe the system through the executor.
      </p>

      <h2>4 · Installation</h2>
      <pre><code>{`# Cross-platform helper
uv run python -m mushegh.edge.autostart install pc_agent

# Or, on Windows, the elevated standalone installer:
powershell -ExecutionPolicy Bypass -File deploy/windows/install_pc_agent_task.ps1`}</code></pre>
      <p>
        The Windows installer self-elevates via UAC, registers <code>MusheghPcAgent</code> as a Scheduled
        Task with <code>RunLevel=Highest</code>, <code>RestartCount=999</code>, launches pythonw.exe
        directly (no VBS shim), and removes the old non-elevated Startup launcher so two executors
        don't fight.
      </p>

      <h2>5 · Spoken use</h2>
      <pre><code>{`"open YouTube on my laptop"        → open_url  → forwarded to pc_agent
"kill Chrome"                      → process_op kill chrome → forwarded
"list the running processes"       → process_op list       → forwarded
"clean up my downloads folder"     → file_op remove → confirm → forwarded
"launch VS Code"                   → open_app vscode       → forwarded`}</code></pre>

      <div className="callout warn">
        <span className="k">Brain-first when the brain is local.</span> If you run the brain on the SAME
        laptop (single-machine mode), system tools don't need to forward — they run locally
        with the same guards. The executor is the VPS-brain case.
      </div>
    </>
  );
}