import Link from "next/link";

export default function BackgroundWork() {
  return (
    <>
      <h1>Background work — tasks that run while you keep talking</h1>
      <p className="lead">
        Long work (a deep-research brief, a fleet delegation, a big build) shouldn't block a voice
        turn or leave you in the dark. Two complementary mechanisms cover it: a <strong>bounded
        background worker</strong> for safe multi-step work that Mushegh does himself, and a{" "}
        <strong>task queue</strong> that persists across 24/7 restarts so you can ask “how's
        that going?” hours later.
      </p>

      <h2>1 · <code>work_on_task</code> — bounded autonomous work</h2>
      <p>
        The agent's own background loop. A small, bounded tool-calling loop (default 6 steps) for
        research, drafting, summarising, light coding, and verification — using the tools Mushegh
        already has (web/scrape/vault/Notion/coding/utilities).
      </p>
      <p>
        It is <strong>safe by construction</strong>:
      </p>
      <ul>
        <li>Confirm-tier tools (send, delete, push, run shell) are <strong>deferred</strong>, not run — the worker records them as “Needs your approval” in the final reply.</li>
        <li>It runs to a step budget and must produce a written result; it cannot loop forever.</li>
        <li>It holds no conversation history and no shared agent state, so it is safe to run alongside live turns.</li>
        <li>Hermetically testable with a fake LLM (no live network required).</li>
      </ul>
      <p>Triggered for research-and-produce requests automatically:</p>
      <pre><code>{`"look into X and write me a summary"   → work_on_task
"research Y and prepare a briefing"    → work_on_task
"compile a comparison report on Z"     → work_on_task
"what's the capital of France"         → answered live (no work_on_task)`}</code></pre>

      <h2>2 · Task queue — “how's that going?”</h2>
      <p>
        SQLite-backed (<code>MUSHEGH_TASKS_DB_PATH</code>, default <code>&lt;repo&gt;/mushegh_tasks.sqlite</code>)
        so the queue survives a 24/7 brain restart. Each task carries <code>title</code>, <code>kind</code>,
        <code>started_at</code>, <code>last_progress</code>, <code>result</code>, and a metadata bag
        (complexity grade, duration, etc.). Live status from <code>TASKS.summary_line()</code>:
      </p>
      <pre><code>{`'research the IS24 OAuth history' is still in progress (4m 12s so far) — the specialist is using web_search, sir.
'research the IS24 OAuth history' is done (4m 38s), sir.`}</code></pre>
      <p>
        When a task finishes, <code>on_complete</code> fires and the brain announces it through the
        proactive delivery channel: voice to a listening device, else Telegram voice note, else ntfy push.
        The voice note says how long it took, the complexity grade, and the first 600 chars of the result.
      </p>
      <h3>From the CLI</h3>
      <pre><code>{`# What did you mean by "background" — a status dump of active tasks
TASKS.summary_line(task)`}</code></pre>
      <h3>Spoken use</h3>
      <pre><code>{`"how's that going?"                   → active tasks by topic
"how's the website rebuild going?"     → narrow to one by title word
"any background work running?"         → full list`}</code></pre>

      <h2>3 · Daily autonomous backlog pass</h2>
      <p>
        Optional, opt-in via <code>MUSHEGH_BACKLOG_ENABLED=true</code>. Once a day (default 09:30, your
        timezone) the scheduler pulls overdue + undated-inbox tasks from the configured Notion tasks DB
        (<code>MUSHEGH_NOTION_TASKS_DB_ID</code>) and has the bounded worker attempt the{" "}
        <strong>safe</strong> work on each. The result is posted as a Notion comment on the task. Outward
        actions (send, delete, run shell) remain deferred. Capped per run (<code>MUSHEGH_BACKLOG_MAX_TASKS</code>,
        default 2). No Notion / no tasks DB / nothing overdue = a quiet no-op.
      </p>

      <h2>4 · Daily morning voice briefing</h2>
      <p>
        With a tasks DB configured and <code>MUSHEGH_TASK_BRIEFING_TIME</code> set (default 08:30), the
        scheduler fires the briefing daily. The body covers <strong>overdue + due today + this-week
        deadlines + standing recurring</strong>; delivery goes through the proactive channel so it speaks
        to a listening device, else a Telegram voice note, else an ntfy push. Trigger ad-hoc with{" "}
        <em>“give me my briefing.”</em>
      </p>

      <h2>5 · What does this look like in practice</h2>
      <ol>
        <li>You: <em>“Look into IS24's OAuth change history and write me a memo.”</em></li>
        <li>Mushegh: <em>“Right away, sir — putting that to the team.”</em> (or, with the fleet off, hands off to <code>work_on_task</code>.)</li>
        <li>Two minutes later, Mushegh speaks a progress note: <em>“Still working on the research — 12s elapsed.”</em></li>
        <li>When it's done, your phone (or the speaker, if you're there) plays a voice note: <em>“Done, sir — 'research the IS24 OAuth history' finished in 4m 38s (heavy). Memo attached …”</em></li>
        <li>You can read the memo in <code>audit/</code>, in the Notion comment on the source task, or ask “what did you find?” in the next voice turn.</li>
      </ol>

      <div className="callout">
        <span className="k">Mushegh or the team?</span> Background work Mushegh does himself
        (<code>work_on_task</code>) is one of his tools. Deep multi-domain research can also be{" "}
        <em>delegated</em> to the optional OpenClaw fleet via <code>delegate_to_fleet(task, background=true)</code>{" "}
        — the task id is the same shape, and Mushegh still announces completion. See{" "}
        <Link href="/fleet">Fleet</Link>.
      </div>
    </>
  );
}