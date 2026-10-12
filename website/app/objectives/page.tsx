import Link from "next/link";

export const metadata = { title: "Objectives & agency — Mushegh" };

export default function Objectives() {
  return (
    <>
      <h1>Objectives &amp; agency</h1>
      <p className="lead">
        Reminders react to a time. Tasks react to a list. An <strong>objective</strong> is something
        Mushegh owns across days: he advances the safe parts himself, keeps a dated log of what actually
        moved, and tells you when something has stalled — without being asked.
      </p>

      <h2>Hand him a goal</h2>
      <table>
        <thead><tr><th>Say</th><th>Tool</th></tr></thead>
        <tbody>
          <tr><td>“Take this on: get the beta launch-ready.”</td><td><code>assign_objective</code></td></tr>
          <tr><td>“What are you working on?”</td><td><code>list_objectives</code> — the active set, each with its latest progress</td></tr>
          <tr><td>“How's the launch going?”</td><td><code>objective_status</code></td></tr>
          <tr><td>“Milestone: beta by the 30th.”</td><td><code>set_milestone</code> — how a stalled objective is told from a slow one</td></tr>
          <tr><td>“What's actually moving?”</td><td><code>objective_review</code> — moving, stalled with the reason, and what your open work is really serving</td></tr>
          <tr><td>“That's done.” / “Drop it.”</td><td><code>complete_objective</code> / <code>drop_objective</code> (both confirm-gated — an objective that stops being driven stops silently)</td></tr>
        </tbody>
      </table>

      <h2>A daily pass that does the safe half</h2>
      <p>
        Once a day Mushegh takes each active objective and makes concrete progress on the{" "}
        <em>next safe step only</em> — research, drafting, code — through the bounded background
        worker. Anything outward or destructive is not done. It is{" "}
        <strong>deferred for your approval</strong> and waits in a queue you can read:
      </p>
      <ul>
        <li><code>list_approvals</code> — what autonomous work is holding, and why</li>
        <li>approve or reject each one; nothing outward happens on his own judgement</li>
      </ul>
      <p>
        This is the line the whole design turns on. Autonomy is allowed to <em>prepare</em> anything
        and permitted to <em>send</em> nothing. See <Link href="/security">Security</Link> for the
        confirmation tier that enforces it in code, and{" "}
        <Link href="/background-work">Background work</Link> for the worker itself.
      </p>

      <h2>What a turn is in aid of</h2>
      <p>
        Mushegh can name the objective a given request serves, or say plainly that it serves none. The
        inference is deliberately dull — two or more distinctive words shared with the objective's own
        text — and “nothing standing” is a real answer rather than a blank. Most of what anyone does
        in a day serves no standing goal, and an assistant that finds one for every turn is telling
        you what you want to hear.
      </p>
      <p>
        The same restraint applies to <em>tasks</em>: a task's objective is the one it was filed
        under, never one guessed from its title. A task is written once and read for months, so a
        guess there hardens into a fact.
      </p>

      <h2>The shape of a day</h2>
      <p>
        Three more tools sit next to this, and they are about the day rather than the goal:
      </p>
      <ul>
        <li>
          <code>propose_routines</code> — drafts your routines <strong>from what you actually did</strong>,
          with the evidence attached, instead of asking you to describe habits you have never
          articulated.
        </li>
        <li><code>adopt_routines</code> — installs a draft you have agreed to (confirm-gated).</li>
        <li>
          <code>day_clashes</code> — says what will not work about a day <em>before</em> it starts:
          the two things booked at once, the travel that does not fit between them.
        </li>
      </ul>
      <p>
        They live in their own lazy group rather than in the always-on routine tools, because they are
        asked for a few times a month and every schema on the per-turn surface is prefill tokens on
        every turn of every day. When they were added to the core module, the efficiency gate caught
        it — which is exactly what that gate is for.
      </p>

      <div className="callout">
        <span className="k">Honest stalling.</span> “Stalled” is arithmetic here, not a mood: an
        objective with a milestone whose date has passed, or no logged progress in a defined window.
        The failure this prevents is the quiet one — an objective nobody is driving looks identical
        to an objective going fine, right up until you ask.
      </div>
    </>
  );
}
