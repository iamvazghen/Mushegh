import Link from "next/link";

export const metadata = { title: "Skills — Mushegh" };

const SKILLS = [
  // Companion / daily ops
  { group: "Companion", name: "daily-briefing", blurb: "Morning voice briefing of overdue, due-today, this-week deadlines, recurring tasks." },
  { group: "Companion", name: "email-triage", blurb: "Triage unread email: urgent / reply-needed / FYI / archive." },
  { group: "Companion", name: "calendar-and-reminders", blurb: "Read today / create events / schedule reminders." },
  { group: "Companion", name: "task-capture", blurb: "Capture a task from anywhere: inbox, Notion, voice." },
  { group: "Companion", name: "research-method", blurb: "Multi-source research, cross-check, cite." },
  { group: "Companion", name: "proactive-etiquette", blurb: "When to speak, when to stay quiet, quiet hours + budget." },
  { group: "Companion", name: "voice-style", blurb: "Mushegh's own voice: pacing, filler phrases, no markdown on the wire." },
  { group: "Companion", name: "memory-discipline", blurb: "L1/L2/L3/L5: what goes where, when to forget, when to skip." },
  { group: "Companion", name: "task-cleanup", blurb: "Turn a messy backlog into a short, honest, actionable list — never silently deleting anything he might still want." },
  // Self-improvement / coding
  { group: "Coding", name: "self-improvement", blurb: "Read your own source, run the suite, make a reversible commit." },
  { group: "Coding", name: "adding-a-tool", blurb: "Drop a SCHEMAS+HANDLERS module into brain/tools/, list it in tools/__init__.py." },
  { group: "Coding", name: "debugging", blurb: "Where to look, what to tail, how to repro a voice turn." },
  { group: "Coding", name: "git-workflow", blurb: "Branches, reversible commits, no force-push, deploy_vps.sh gate." },
  { group: "Coding", name: "python", blurb: "Style: type hints, fail-quiet, 100 cols, the surrounding idiom." },
  { group: "Coding", name: "web-and-typescript", blurb: "TypeScript / Next.js patterns for the docs site + clients/." },
  // System
  { group: "System", name: "mushegh-architecture", blurb: "The edge/brain split, the protocol, the six memory layers." },
  { group: "System", name: "pc-control", blurb: "Drive the laptop from the brain; PC_LINK + the executor." },
  { group: "System", name: "google-workspace", blurb: "Gmail + Calendar OAuth, refresh token, one-time consent." },
  { group: "System", name: "media-and-voice-rooms", blurb: "Telegram voice-chat streaming, music room, voice-note outbound." },
  { group: "System", name: "governance-and-compliance", blurb: "What actually controls him, named mechanism by mechanism — and the absences, which matter as much. Written after he invented a vendor for his own architecture." },
  { group: "System", name: "governance-regulatory-mapping", blurb: "GDPR Art. 5 / 32 / 9 and the secrets row: control AND gap, never the gap skipped. Split out so neither file overflows what read_skill returns." },
  { group: "System", name: "secrets-and-access", blurb: "The paths and commands the code actually refuses, read from the enforcers. Why 'I don't have that key' is a correct answer." },
  { group: "System", name: "sessions-and-context", blurb: "The real trim numbers, what survives it, and when a reset is right — plus when it is just a way of dodging a hard problem." },
  { group: "System", name: "owner-model", blurb: "Tiered context: a small injected core, the rich model on demand. LifeOS's taxonomy mapped onto this repo's storage, and the rule that keeps it true." },
  { group: "Coding", name: "prompting", blurb: "Two audiences: prose for him, compressed exactness for a machine. Plus the make-the-task-checkable habit." },
  { group: "Coding", name: "integration-utilization", blurb: "Reach for Graphify, REA, Ponytail and Caveman — and what not to reach them for. The order: understand, check, build smallest, say it small." },
  { group: "Coding", name: "coding-pipeline", blurb: "Which tool gets the work, and why the routing is not yours to choose. Read before writing a coding brief — the first decision is where it goes, not how to phrase it." },
  { group: "Coding", name: "architecture-modelling", blurb: "Decide where a change belongs before writing it. A brief that names the wrong seam produces a diff that works and lives in the wrong file." },
  { group: "Coding", name: "graphify", blurb: "Read the structure before the source: a scoped query is ~1.6k tokens where a full-repo read is ~120k. Cheapest layer first, stop at the first that answers." },
  { group: "Coding", name: "ponytail-and-caveman", blurb: "Ponytail spends less code; Caveman spends fewer tokens. Two currencies, easily confused, and which one is actually installed here." },
  { group: "Coding", name: "prompting-claude-code", blurb: "The main coding tool. It is an agent, not a code generator — brief it like a competent engineer who has never seen the repo." },
  { group: "Coding", name: "prompting-mcode", blurb: "The first fallback, reached when Claude Code failed on evidence rather than a hunch. Richest non-interactive interface of the three, which changes the brief." },
  { group: "Coding", name: "prompting-mistral-vibe", blurb: "The second fallback. Two agents have already tried, so the brief is no longer the original — it is the original plus what the other two learned." },
  { group: "Coding", name: "prompting-open-design", blurb: "Owns frontend exclusively — sites, UI, UX, visual direction. An MCP server, so its tools arrive namespaced." },
  { group: "System", name: "the-fleet", blurb: "Eighteen specialists, eighty-three domains, and no router. What to unlearn first: the team lead that used to choose a specialist no longer exists." },
];

const GROUPS = ["Companion", "Coding", "System"] as const;

export default function SkillsPage() {
  return (
    <>
      <h1>Skills — the 35 on-demand playbooks</h1>
      <p className="lead">
        Skills are plain-Markdown playbooks Mushegh reads with <code>read_skill</code> when a turn calls
        for one. They live in <code>skills/</code>, ship with every deploy, and are listed by{" "}
        <code>list_skills</code>. None auto-load — each is loaded on demand, so the per-turn prompt
        stays lean.
      </p>

      <h2>How skills are used</h2>
      <pre><code>{`"read your self-improvement skill, then make recall faster"
  → list_skills → finds self-improvement → read_skill → branches, edits, tests, confirms, commits.

"give me my morning briefing"
  → reads daily-briefing, uses it as the rubric. Returns the spoken text.

"research X"
  → reads research-method, follows it. Falls back to whatever tools are available.`}</code></pre>

      <p>
        The skill catalog is a deliberate, framework-curated set — vetted, written against the
        actual tools, and small enough to keep coherent. Mushegh does <em>not</em> install third-party
        skill packs at runtime; the catalog ships with the brain and is regenerated on every{" "}
        <code>scripts/deploy_vps.sh</code>.
      </p>

      {GROUPS.map((g) => (
        <section key={g}>
          <h2 id={g.toLowerCase()}>{g}</h2>
          <table>
            <thead>
              <tr><th>Skill</th><th>What it teaches Mushegh</th></tr>
            </thead>
            <tbody>
              {SKILLS.filter((s) => s.group === g).map((s) => (
                <tr key={s.name}>
                  <td><code>{s.name}</code></td>
                  <td>{s.blurb}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      ))}

      <h2>Adding your own</h2>
      <p>
        Drop a <code>skills/&lt;name&gt;.md</code> in the repo, ship via <code>scripts/deploy_vps.sh</code>,
        and it appears in <code>list_skills</code> on next brain start. Treat skills the way you'd
        treat a runbook: short, example-rich, and tied to the actual tools. See{" "}
        <code>skills/adding-a-tool.md</code> for the pattern.
      </p>

      <div className="callout">
        <span className="k">One skill = one focused playbook.</span> Resist the urge to merge things
        (“research-and-coding-and-writing”) — a skill that tries to teach three jobs
        rarely teaches any of them well.
      </div>
    </>
  );
}