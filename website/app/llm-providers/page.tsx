import Link from "next/link";

export default function LLMProviders() {
  return (
    <>
      <h1>LLM providers -- the failover chain</h1>
      <p className="lead">
        Mushegh thinks on a single OpenAI-compatible endpoint with an ordered failover chain. A
        rate-limit or a hiccup on the primary must never mute him -- the chain fails over within
        a tight first-token window, and a cooldown skips a sick model on later turns while a healthy
        alternative exists.
      </p>

      <h2>1 · Endpoints you can use</h2>
      <table>
        <thead>
          <tr><th>Endpoint</th><th>Code</th><th>Notes</th></tr>
        </thead>
        <tbody>
          <tr><td><code>freellmapi</code></td><td>default</td><td>An OpenAI-compatible proxy on the VPS. URL <code>MUSHEGH_FREELLMAPI_BASE_URL</code>, key <code>MUSHEGH_FREELLMAPI_API_KEY</code>.</td></tr>
          <tr><td><code>openai</code></td><td><code>openai</code></td><td>Any OpenAI-compatible endpoint (api.openai.com, Groq, Cerebras, an internal gateway). Same key/URL slots.</td></tr>
          <tr><td><code>ollama</code></td><td><code>ollama</code></td><td>Local Ollama server (<code>http://localhost:11434/v1</code>, no key). True offline fallback.</td></tr>
          <tr><td>Groq direct</td><td>prefix <code>groq:</code></td><td>Free tier; ~0.3s TTFT, very consistent. Best <em>primary</em> for the voice path.</td></tr>
          <tr><td>Cerebras direct</td><td>prefix <code>cerebras:</code></td><td>Free tier; ~2000 tok/s, separate rate-limit pool from Groq -- rare to see both rate-limited at once.</td></tr>
        </tbody>
      </table>

      <h2>2 · The chain</h2>
      <pre><code>{`MUSHEGH_LLM_PRIMARY_MODEL=groq:llama-3.3-70b-versatile
MUSHEGH_LLM_FALLBACK_MODELS=cerebras:llama-3.3-70b,groq:llama-3.1-8b-instant,llama-3.3-70b-versatile,openai/gpt-oss-20b:free
# Optional fast tier (prepended for first words):
MUSHEGH_LLM_FAST_MODEL=groq:llama-3.1-8b-instant`}</code></pre>
      <p>
        A chain entry is a model name; prefix it with a provider (<code>groq:</code>, <code>cerebras:</code>,
        <code>ollama:</code>) to hit that endpoint directly. Unprefixed names go to the freellmapi
        proxy. The primary sits first; the fallback chain is walked in order on any
        rate-limit / API error / timeout / empty 200 / textual tool-call (which silently degrades to no
        call).
      </p>

      <h2>3 · Failover timing</h2>
      <ul>
        <li><strong>First-token timeout</strong> (<code>MUSHEGH_LLM_FIRST_TOKEN_TIMEOUT_SECONDS=4.0</code>): if no FIRST token arrives within the window, the model is cancelled and the chain fails over. Keeps a hung primary from blocking a turn.</li>
        <li><strong>Per-model attempt cap</strong> (<code>MUSHEGH_LLM_REQUEST_TIMEOUT_SECONDS=20</code>): the absolute ceiling per attempt. Raise only for heavy non-voice batch calls.</li>
        <li><strong>Unhealthy cooldown</strong> (<code>MUSHEGH_LLM_UNHEALTHY_COOLDOWN_SECONDS=45</code>): after a timeout/error/empty, skip that model on later turns while a healthy alternative exists. No silent loss of capability.</li>
      </ul>

      <h2>4 · Streaming -- first-token failover only</h2>
      <p>
        Once a model starts streaming, the chain does NOT silently switch mid-utterance (that would
        double-speak). If a streaming model breaks mid-utterance with committed prose, we flush what we
        have and end the turn. The first-token deadline is the snappy-recovery lever; mid-stream
        recovery is the “don't be weird” lever.
      </p>

      <h2>5 · Reasoning models -- the <code>gpt-oss</code> quirk</h2>
      <p>
        Reasoning models (e.g. Cerebras <code>gpt-oss-120b</code>) spend the first ~2s “thinking”
        with empty content -- fatal for a voice turn. <code>brain/llm.py::_model_extra()</code>{" "}
        auto-injects <code>reasoning_effort=low</code> for any model whose name contains <code>gpt-oss</code>,
        so the spoken answer comes back in ~0.26s instead of two seconds of silence.
      </p>

      <h2>6 · Native tool-calling -- the quality floor</h2>
      <p>
        A weaker model sometimes <em>speaks</em> a tool call as text (&quot;<code>&lt;function name=&quot;x&quot;&gt;</code>&quot;)
        instead of using the native JSON <code>tool_calls</code>. The chain detects this in two places
        and fails over to a model that calls tools properly:
      </p>
      <ul>
        <li>Before-the-fact: the LLM layer rejects a textual tool-call as <code>_EmptyResponse</code> and fails over.</li>
        <li>After-the-fact (Groq): the <code>tool_use_failed</code> error body carries a <code>failed_generation</code>; we parse the textual tool-call back into a native one and keep the fast path with no failover.</li>
      </ul>

      <h2>7 · Connection warmup</h2>
      <p>
        <code>LLMClient.warmup()</code> fires a one-token ping to every distinct provider in the chain at
        brain start, concurrently, best-effort. Pre-opens the TLS / connection so neither the first turn
        NOR the first failover pays a cold start -- a measurable slice of TTFT.
      </p>

      <h2>8 · Choosing a primary</h2>
      <ol>
        <li><strong>For voice</strong>: <code>groq:</code>-prefixed as the primary (best TTFT consistency), Cerebras as the second slot (different rate-limit pool), then a freellmapi / openai model for fallback.</li>
        <li><strong>For the openai / ollama backend</strong>: name the model id (e.g. <code>gpt-4o-mini</code>) and a curated fallback chain -- the wizard clears the freellmapi-default chain when you pick openai or ollama.</li>
        <li><strong>For local-only</strong>: ollama:<code>llama3.1</code> as the primary, ollama:<code>llama3.2</code> as the second slot. Same chain, fully offline.</li>
      </ol>

      <div className="callout">
        <span className="k">The fast tier is optional.</span> Set <code>MUSHEGH_LLM_FAST_MODEL</code> to a tiny
        fast model that answers before the primary -- quality is the primary's job, snappiness
        is the fast tier's. Useful on a slower primary that needs first-words sooner.
      </div>
    </>
  );
}