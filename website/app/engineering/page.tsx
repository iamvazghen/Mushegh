import Link from "next/link";

export const metadata = { title: "How it is built & verified — Mushegh" };

export default function Engineering() {
  return (
    <>
      <h1>How it is built &amp; verified</h1>
      <p className="lead">
        A voice assistant fails quietly. A wrong answer sounds exactly like a right one, a tool that
        stopped working still says something pleasant, and an integration can be dead for weeks
        before anyone thinks to check. Almost everything on this page exists because of that one
        problem.
      </p>

      <h2>The plan is a document with 370 rows in it</h2>
      <p>
        <code>docs/SYSTEMS.md</code> breaks the assistant into <strong>50 subsystems</strong> — voice,
        memory, tools, identity, proactivity, safety — and gives each three tiers:
      </p>
      <table>
        <thead><tr><th>Tier</th><th>Means</th></tr></thead>
        <tbody>
          <tr><td><strong>Floor</strong></td><td>the subsystem is not embarrassing. It does the obvious thing and says so when it cannot.</td></tr>
          <tr><td><strong>Raise</strong></td><td>it is good. The failure modes that only show up in daily use are handled.</td></tr>
          <tr><td><strong>Elite</strong></td><td>it is better than what you could buy, and there is a measurement proving it.</td></tr>
        </tbody>
      </table>
      <p>
        Every row carries a <strong>named gate</strong>: the specific test that decides whether that
        row is done. Not "add tests" — the test is chosen with the task, before the code, because a
        task whose gate you cannot name is a task you have not finished thinking about.
      </p>
      <div className="callout good">
        <span className="k">The plan cannot lie about itself.</span>{" "}
        <code>bench/test_systems_plan.py</code> fails the build if a task has no gate, or if the
        scoreboard's counts disagree with the actual checkboxes. A plan that can drift from the code
        is worse than no plan, because it gets believed.
      </div>

      <h2>One suite, and it runs before anything leaves the machine</h2>
      <p>
        <code>uv run python bench/run_all_tests.py</code> runs <strong>201 tests</strong>, offline and
        hermetic — no network, no keys, no real accounts. Tests that need a live backend report SKIP
        rather than FAIL, so a run on a plane still means something.
      </p>
      <p>
        The same suite runs on <code>git push</code> via a pre-push hook. It has blocked pushes in
        this project more than once, which is the only evidence that a gate is real.
      </p>

      <h2>What gets found this way</h2>
      <p>
        A sample from recent work — every one of these was invisible in normal use, and every one was
        found by a test written for a different task:
      </p>
      <table>
        <thead><tr><th>Defect</th><th>How it presented</th></tr></thead>
        <tbody>
          <tr>
            <td>A tool that had never worked once</td>
            <td>
              Written as a synchronous function in a registry the agent awaits, so "show me what I
              can undo" answered with a type error from the day it shipped. Nothing noticed because
              no test called it.
            </td>
          </tr>
          <tr>
            <td>The startup warm-up warmed nothing</td>
            <td>
              It called a function with the wrong number of arguments, raised on its first line, and
              swallowed the error at debug level. The first sentence of every morning paid a cost the
              method existed to remove.
            </td>
          </tr>
          <tr>
            <td>The prompt carried notes to its own editor</td>
            <td>
              ~470 characters of HTML comments — including "keep this short, it eats the budget" —
              were being sent to the model on every single turn.
            </td>
          </tr>
          <tr>
            <td>A capability advertised after it was retired</td>
            <td>
              A module still told the owner to enable a Google API that had been replaced, and
              reported itself configured because it borrowed an unrelated login as its readiness
              check.
            </td>
          </tr>
          <tr>
            <td>Two streaming paths, opposite bugs</td>
            <td>
              One refused to fail over after speaking and cut off mid-sentence; the other had no such
              guard and let the next model start again, so you heard the first sentence twice.
            </td>
          </tr>
        </tbody>
      </table>

      <h2>Rules the code enforces on itself</h2>
      <ul>
        <li>
          <strong>Layering.</strong> Shared code may not import the brain or the edge; there are no
          import cycles; every edge↔brain crossing is declared.
        </li>
        <li>
          <strong>One way in.</strong> A single function opens the database — nothing else may.
        </li>
        <li>
          <strong>Declare your loops.</strong> Every recurring background job has a row in a registry,
          with its period and its budget, or the build fails. A loop that runs and never appears on
          the HUD is work happening where you cannot see it.
        </li>
        <li>
          <strong>Declare your stores.</strong> Anything that persists is declared; a file nothing
          declares fails the build.
        </li>
        <li>
          <strong>No ghost tools in prose.</strong> Any tool named in the personality files must exist
          in the registry — a promise in a document rots silently when a tool is renamed.
        </li>
        <li>
          <strong>Every tool is exercised.</strong> A tool nothing uses and nothing tests is catalogue
          tokens spent on code no one is looking at.
        </li>
        <li>
          <strong>Awaitable handlers.</strong> Every registered handler must be a coroutine, because
          the agent awaits all of them.
        </li>
        <li>
          <strong>No phantom paths.</strong> A file path cited in any planning document must exist.
        </li>
      </ul>

      <h2>Measure before you build</h2>
      <p>
        Three tasks in a row changed shape once they were measured, and the measurements are worth
        more than the code that followed:
      </p>
      <ul>
        <li>
          <strong>"Shrink the tool schemas."</strong> Parameters no caller reads: <em>zero</em>.
          Descriptions that merely restate their key: twelve, worth 42 tokens. The long descriptions
          turned out to be dense with routing hints and safety rules, so cutting them buys tokens and
          pays for them in wrong-tool rate. The real unbounded cost was the <em>number of groups one
          turn could arm</em> — which nothing capped. That became the budget on{" "}
          <Link href="/architecture#catalogue">Architecture</Link>.
        </li>
        <li>
          <strong>"Reject calls missing a required argument."</strong> Measured against the registry
          first: eleven working tools accept a spelling their own schema marks required, because
          handlers take synonyms while the schema advertises one to keep the catalogue small. The
          obvious version of that task would have broken all eleven.
        </li>
        <li>
          <strong>"Answer what you can and cannot do from the registry."</strong> The "can" half
          needed no prompt text at all — the model already holds the catalogue — and adding a
          generated capability list would have spent exactly what the budget work had just saved. The
          half that was missing was the negative one.
        </li>
      </ul>

      <h2>Where the work is planned</h2>
      <table>
        <thead><tr><th>Document</th><th>What it is</th></tr></thead>
        <tbody>
          <tr>
            <td><code>docs/SYSTEMS.md</code></td>
            <td>The canonical plan: 50 subsystems × three tiers, every task with its gate, plus a scoreboard the build checks.</td>
          </tr>
          <tr>
            <td><code>docs/MASTER-PLAN.md</code></td>
            <td>The long-range shape — what this is meant to become.</td>
          </tr>
          <tr>
            <td><code>TODO.md</code></td>
            <td>The running engineering log: what was built, what it broke, and what it measured.</td>
          </tr>
        </tbody>
      </table>
      <p>
        All three are tracked in the repository rather than kept in someone's head. They are the
        reason this page can be specific.
      </p>

      <div className="callout">
        <span className="k">Current position.</span> 163 of 370 tasks green — the floor tier
        essentially complete across all 50 subsystems, the raise tier under way. Six floor tasks
        remain open on purpose: three need the owner physically present (a voice re-enrolment sitting,
        a face capture, a token from a device), and three are parked by a decision recorded in the
        plan — the hardware they would serve does not exist yet, and building for it would be
        speculation.
      </div>
    </>
  );
}
