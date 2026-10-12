import Link from "next/link";

export default function Bots() {
  return (
    <>
      <h1>Bots & send-paths — who sends what, from where</h1>
      <p className="lead">
        Mushegh uses Telegram in two distinct roles, plus several other outbound paths. Each role has its
        own token (so two pollers on the same token don't steal each other's messages), and each
        outbound channel has its own medium (voice / voice-note / text).
      </p>

      <h2>1 · Telegram bridge bot (DM Mushegh 24/7)</h2>
      <p>
        <strong>Purpose:</strong> A dedicated bot you DM from your phone or desktop — the 24/7 brain
        polls <code>getUpdates</code>, runs the same shared agent (so Telegram and voice share one
        memory + one conversation context), and replies.
      </p>
      <ul>
        <li>Token: <code>MUSHEGH_TELEGRAM_BRIDGE_BOT_TOKEN</code>. <strong>Must be separate</strong> from <code>MUSHEGH_TELEGRAM_BOT_TOKEN</code>; two pollers on one token steal each other's messages.</li>
        <li>Auth: only your <code>MUSHEGH_TELEGRAM_DEFAULT_CHAT</code> is answered; anything else is logged and ignored.</li>
        <li>Reply: voice note by default for the assistant's outbound (ElevenLabs &rarr; ffmpeg libopus OGG &rarr; <code>sendVoice</code>); text as the last-resort fallback if synthesis fails.</li>
        <li>Disable by leaving the token unset.</li>
      </ul>

      <h2>2 · Telegram send bot (default recipient)</h2>
      <p>
        <strong>Purpose:</strong> Mushegh uses this token for <code>send_telegram</code> — sending a
        message/GIF/file to a recipient by name or chat id. Same physical bot can serve both roles ONLY
        when sends and polls don't fight (separate tokens are still recommended).
      </p>
      <ul>
        <li>Token: <code>MUSHEGH_TELEGRAM_BOT_TOKEN</code>.</li>
        <li>Default recipient: <code>MUSHEGH_TELEGRAM_DEFAULT_CHAT</code> (your chat id).</li>
        <li>Sends a <strong>text</strong> reply to other people (the owner is texting on Mushegh's behalf).</li>
        <li>Sends a <strong>voice note</strong> to the owner (the Mushegh assistant is talking).</li>
      </ul>

      <h2>3 · Mushegh vs ispir bot — the rule</h2>
      <p>
        The Mushegh assistant uses ONLY the Mushegh bot (<code>@afon_iamvazghen_bot</code>) for both sends
        and the bridge poll. The ispir / OpenClaw bot (<code>@ispir</code>) is the fleet's
        dedicated bot, used by the OpenClaw agents directly — Mushegh must never post or poll on the
        ispir bot. The previous setup leaked Mushegh's weekly-check alerts into the ispir bot; the
        split fixes that permanently.
      </p>
      <div className="callout warn">
        <span className="k">One bot, one role.</span> Never share tokens between Mushegh's assistant
        and OpenClaw's agents. If you don't run a fleet, leave the ispir bot unset and Mushegh
        simply won't reach it.
      </div>

      <h2>4 · ntfy phone push (always on)</h2>
      <p>
        Cross-platform phone push via <a href="https://ntfy.sh" target="_blank" rel="noreferrer">ntfy.sh</a>{" "}
        (or your own server). Topic in <code>MUSHEGH_NTFY_TOPIC</code> — pick an unguessable string;
        subscribe to it in the ntfy app on your phone.
      </p>
      <table>
        <thead>
          <tr><th>Used for</th><th>Notes</th></tr>
        </thead>
        <tbody>
          <tr><td>One-shot / <code>at</code> reminders</td><td>Server-side scheduled by the brain (or ntfy itself holds them for 10s&ndash;3 days); fires with the PC off</td></tr>
          <tr><td>Proactive nudges when nothing's listening</td><td>Voice to a connected device first; push as the fall-back</td></tr>
          <tr><td>Weekly live-check failure alerts</td><td>Voice (ElevenLabs &rarr; OGG &rarr; <code>sendVoice</code>) by default; text if synthesis itself fails</td></tr>
          <tr><td>Memory-backup / diagnostics confirmations</td><td>Optional; via <code>push()</code> helper</td></tr>
        </tbody>
      </table>

      <h2>5 · Outbound medium — voice-only by default</h2>
      <p>
        The owner's standing rule: <strong>all</strong> Mushegh&rarr;owner messages are voice notes
        — no text allowed. The send path:
      </p>
      <pre><code>{`# CLI one-shot
uv run python -m mushegh.brain.voice_io "Sir, the weekly integration check passed."

# In code
from mushegh.brain.voice_io import send_voice_note
await send_voice_note("Sir, the briefing is ready.")
# → ElevenLabs mp3 → ffmpeg libopus OGG → Telegram sendVoice (Mushegh bot)
# → falls back to text via the same bot ONLY if synthesis itself failed.`}</code></pre>
      <p>
        Text remains the medium for Mushegh&rarr;OTHER people (the owner is texting on Mushegh's
        behalf; the recipient expects a text).
      </p>

      <h2>6 · ElevenLabs + ffmpeg dependency</h2>
      <p>
        Voice notes need <code>ffmpeg</code> with <code>libopus</code> on the brain host (the standard
        package on Ubuntu/Debian, present on the shipped VPS image). Without it the transcode fails and
        the helper falls back to the synthesised MP3 (raw audio attachment) and then to text. Check on
        the VPS with <code>ffmpeg -codecs | grep opus</code>.
      </p>

      <p style={{ marginTop: 22 }}>
        See <Link href="/integrations">Integrations</Link> for the full Telegram setup walk-through and
        the Music Room details.
      </p>
    </>
  );
}