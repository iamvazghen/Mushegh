import Link from "next/link";

export default function Apps() {
  return (
    <>
      <h1>External apps — MCP and Composio</h1>
      <p className="lead">
        The 24 native tools cover Mushegh's hot paths (vault, Telegram, Gmail, Calendar, Notion, Home
        Assistant, web, files, browser). For everything else — Slack, GitHub, Linear, Drive,
        Stripe, Airtable, HubSpot, etc. — Mushegh exposes two <strong>meta-tools</strong> that
        reach any Model Context Protocol server, including Composio's pre-built OAuth-managed
        250+ app integrations.
      </p>

      <h2>1 · The MCP client (stdlib only)</h2>
      <p>
        A tiny client in <code>brain/mcp_client.py</code> covers the Model Context Protocol's
        stdio transport with <strong>no new dependency</strong>: spawn the configured server,
        <code>initialize</code>, <code>tools/list</code>, <code>tools/call</code>. Each MCP tool is
        converted into the same OpenAI function schema + async handler the rest of the registry uses,
        namespaced <code>mcp__&lt;server&gt;__&lt;tool&gt;</code> so names never collide.
      </p>
      <p>
        Security boundary: <strong>only</strong> servers explicitly listed in{" "}
        <code>MUSHEGH_MCP_SERVERS</code> are ever launched. No default server. A server that fails to
        start (bad command, missing binary) is logged and skipped — it never blocks startup or
        crashes a turn.
      </p>

      <h3>Configure</h3>
      <pre><code>{`# .env — inline JSON
MUSHEGH_MCP_SERVERS={"filesystem": {"command": "npx", "args": ["-y", "@modelcontextprotocol/server-filesystem", "/safe/dir"]}}

# or a path to a .json file
MUSHEGH_MCP_SERVERS=/path/to/mcp_servers.json`}</code></pre>

      <h2>2 · Composio (250+ apps, OAuth handled)</h2>
      <p>
        Composio is a managed tool/auth provider that ships pre-built, OAuth-handled app integrations
        (Slack, GitHub, Linear, Google Drive, Stripe, HubSpot, Calendly, Airtable, Reddit, YouTube,
        LinkedIn, …) and exposes them through a hosted MCP server. With Composio, Mushegh gains breadth
        without writing a new tool per app.
      </p>

      <h3>Setup</h3>
      <ol>
        <li>Create a Composio account and copy the API key.</li>
        <li>
          Set <code>MUSHEGH_COMPOSIO_API_KEY</code> (and optionally{" "}
          <code>MUSHEGH_COMPOSIO_USER_ID</code> for the connected-accounts entity).
        </li>
        <li>
          In the Composio dashboard, create the MCP server (Tool Router), pick the app toolkits you want
          (GitHub / Slack / Drive / …), connect the OAuth accounts, and copy the MCP server URL.
        </li>
        <li>
          Add the entry to <code>MUSHEGH_MCP_SERVERS</code> bridged via <code>npx mcp-remote</code>:
        </li>
      </ol>
      <pre><code>{`MUSHEGH_MCP_SERVERS={
  "composio": {
    "command": "npx",
    "args": ["-y", "mcp-remote", "<your-composio-mcp-url>"]
  }
}`}</code></pre>
      <p>
        Restart the brain. The log shows <code>MCP server 'composio': exposed N tool(s)</code>.
        Composio tools now join the registry as <code>mcp__composio__&lt;tool&gt;</code> and the
        confirm-tier still gates outward actions.
      </p>

      <h3>Why not just call every tool every turn?</h3>
      <p>
        GitHub alone ships ~846 tools, Slack ~158. Exposing them raw would blow the per-turn tool budget
        (the registry is capped lean by lazy groups). Composio's Tool Router exposes a small set of
        <strong>semantic search/execute meta-tools</strong> that resolve the right tool on demand and
        keep the per-turn surface manageable.
      </p>

      <h3>Two meta-tools you'll see</h3>
      <table>
        <thead>
          <tr><th>Meta-tool</th><th>What it does</th></tr>
        </thead>
        <tbody>
          <tr><td><code>composio_search_tools</code></td><td>Find the right tool by toolkit + free-text query.</td></tr>
          <tr><td><code>composio_run_tool</code></td><td>Execute the resolved tool (confirm-gated for outward actions).</td></tr>
        </tbody>
      </table>

      <h2>3 · Native vs MCP — when to use which</h2>
      <ul>
        <li><strong>Native</strong> tools stay primary for the hot paths already live and tuned: Gmail, Calendar, Notion, the visible browser, the utility belt, the file/process tools, Telegram.</li>
        <li><strong>Composio via MCP</strong> is the additive breadth layer for apps Mushegh doesn't have first-class — and for offloading OAuth refresh.</li>
        <li><strong>Local git</strong> stays the only path for self-improvement commits (no Composio for source control).</li>
      </ul>

      <h2>4 · Verifying the wiring</h2>
      <pre><code>{`# Check the connected apps + live status
uv run python bench/test_composio_accounts.py

# Brain boot log (the line you're looking for)
MCP server 'composio': exposed N tool(s)`}</code></pre>
      <p>
        The bench script enumerates every connected account + live status with the API key in your
        gitignored <code>.env</code>; it never logs a token value.
      </p>

      <div className="callout">
        <span className="k">Not replacing native tools.</span> Composio is breadth, not a swap. A native
        Gmail tool wins on latency, observability, and the confirm-tier wiring; Composio's Gmail is
        there if you want it as a fallback.
      </div>
    </>
  );
}