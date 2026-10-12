import Link from "next/link";
import data from "./tools.generated.json";

export const metadata = { title: "Tool reference — Mushegh" };

const GROUP_META: Record<string, { title: string; blurb: string }> = {
  core: {
    title: "Core — advertised on every turn",
    blurb:
      "Always in the model's tool surface: memory, vault, web, Telegram, music, PC control, reminders, routines, utilities. These are the tools a turn can need without warning, so they are never lazy.",
  },
  coding: { title: "Coding", blurb: "Repo-scoped self-improvement: read and write source, run tests, lint, reversible git." },
  office: { title: "Office", blurb: "Gmail, Google Calendar and Notion — including the task list, which is canonically Notion." },
  home: { title: "Home", blurb: "Home Assistant control and the Telegram music-room voice chat." },
  docs: { title: "Documents", blurb: "Open a local document and answer questions grounded in it." },
  apps: { title: "External apps (Composio)", blurb: "250+ apps — GitHub, Slack, Drive and the rest — behind two meta-tools, so the catalogue stays two entries instead of hundreds." },
  channels: { title: "YouTube channels", blurb: "List a channel, play its latest, or pick something at random from it." },
  macros: { title: "Macros", blurb: "Saved sequences of tool calls, and if-then rules that fire them." },
  screen: { title: "Screen", blurb: "Screenshot and read what is on the display — armed only when you ask him to look." },
  camera: { title: "Camera", blurb: "Webcam vision and visual presence: whether you are at the desk, and who." },
  undo: { title: "Undo", blurb: "Roll back the last reversible action, or list what can still be undone." },
  graph: { title: "Graph memory", blurb: "Structured relations between people, projects and events, and multi-hop recall across them." },
  activity: { title: "Activity", blurb: "Screen time, what you are working on now, and the switch that turns the tracking off." },
  coaching: { title: "Coaching", blurb: "Skill reviews and progress in a field you are learning." },
  objectives: { title: "Objectives", blurb: "Multi-day goals Mushegh actively drives, with a dated progress log and honest stall reporting." },
  approvals: { title: "Approvals", blurb: "Approve or reject the outward steps that autonomous work deferred to you." },
  relationship: { title: "Relationship", blurb: "Sensitivities, running jokes and how things stand between you — read before he chooses a tone." },
  phone: { title: "Phone", blurb: "Real phone calls through Twilio. Unconfigured by default, and he says so rather than pretending." },
  places: { title: "Places", blurb: "Live travel time and place search through Google Maps." },
  compute: { title: "Compute", blurb: "Exact maths and hard facts through Wolfram Alpha, instead of a plausible-sounding guess." },
  vitals: { title: "Vitals", blurb: "Sleep, steps and heart rate from an Apple Health export — no API, no key, no cloud project." },
  audioout: { title: "Audio output", blurb: "Which speaker or headphones Mushegh talks through, and how loud." },
  dayshape: { title: "Day shape", blurb: "Draft routines from what you actually do, and say when a day does not hold together." },
  privacy: { title: "Privacy", blurb: "What Mushegh stores about you, for how long, and how to make him forget it." },
  stock: { title: "Stock", blurb: "What you have in the house and when it runs out." },
  money: { title: "Money", blurb: "Reads your ledger and values it. It never moves anything — there is no write path." },
};

export default function Tools() {
  const groups = [...new Set(data.tools.map((t) => t.group))];
  const lazyCount = groups.filter((g) => g !== "core").length;
  const coreCount = data.tools.filter((t) => t.group === "core").length;
  return (
    <>
      <h1>Tool reference ({data.count} tools)</h1>
      <p className="lead">
        Generated from the live registry (<code>bench/dump_tools.py --json</code>), so the list on
        this page is the list the model is handed.
      </p>

      <div className="callout">
        <span className="k">Only {coreCount} of them are advertised at once.</span> Sending the whole
        catalogue costs roughly 17,500 tokens on every turn, and it is not only slow — a model
        choosing between {data.count} tools picks the wrong one more often than a model choosing
        between sixty. So {coreCount} core tools are always present and the other {lazyCount} groups
        arm only when what you said matches them, strongest match first.
      </div>

      <p>
        There is a <strong>hard ceiling on the result</strong>: 11,000 tokens of catalogue per turn,
        checked before each group joins rather than reported the morning after. A turn that would
        exceed it does not quietly drop a capability — Mushegh asks one short question naming the two
        things he might have meant, because a request ambiguous enough to arm four groups deserved a
        question anyway. See <Link href="/architecture">Architecture</Link>.
      </p>

      {groups.map((g) => (
        <section key={g}>
          <h2 id={g}>
            {GROUP_META[g]?.title ?? g}{" "}
            <span style={{ fontWeight: 400, opacity: 0.6 }}>
              ({data.tools.filter((t) => t.group === g).length})
            </span>
          </h2>
          <p>{GROUP_META[g]?.blurb}</p>
          <table>
            <thead>
              <tr><th>Tool</th><th>Module</th><th>What it does</th></tr>
            </thead>
            <tbody>
              {data.tools.filter((t) => t.group === g).map((t) => (
                <tr key={t.name}>
                  <td><code>{t.name}</code></td>
                  <td><code>{t.module}</code></td>
                  <td>{t.description}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      ))}

      <div className="callout">
        <span className="k">Safety.</span> Reads run freely; outward or destructive actions (send,
        delete, spend, lock, write to an external app) are confirm-gated in code, not in the prompt —
        see <Link href="/security">Security</Link>. A bare recipient name is resolved to a real
        address <em>before</em> that gate, so what you are asked to approve names the address it will
        actually go to.
      </div>

      <div className="callout">
        <span className="k">Every tool here is exercised by a test.</span> A tool nothing uses and
        nothing checks is catalogue tokens spent on code no one is looking at. The sweep that
        enforces it found one that had never worked: written as a synchronous function in a registry
        the agent awaits, it had answered with a type error since the day it shipped, and nothing
        noticed because nothing called it.
      </div>
    </>
  );
}
