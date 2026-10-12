import Link from "next/link";

export default function Personalize() {
  return (
    <>
      <h1>Personalize — make it yours</h1>
      <p className="lead">
        Mushegh ships one generic persona <em>template</em>. Your assistant's name, what it
        calls you, and the languages it speaks all come from config — so the same code becomes{" "}
        <em>your</em> assistant without editing a single prompt or source file.
      </p>

      <h2>The five identity settings</h2>
      <table>
        <thead>
          <tr><th>Setting</th><th>What it does</th><th>Example</th></tr>
        </thead>
        <tbody>
          <tr><td><code>MUSHEGH_ASSISTANT_NAME</code></td><td>what it calls itself</td><td><code>Mushegh</code>, <code>Aria</code>, <code>Jeeves</code></td></tr>
          <tr><td><code>MUSHEGH_USER_NAME</code></td><td>your name (blank = none)</td><td><code>Dana</code></td></tr>
          <tr><td><code>MUSHEGH_USER_ADDRESS</code></td><td>how it addresses you</td><td><code>sir</code>, <code>ma'am</code>, <code>boss</code>, or blank</td></tr>
          <tr><td><code>MUSHEGH_UNDERSTOOD_LANGUAGES</code></td><td>languages it can understand</td><td><code>English, Spanish</code></td></tr>
          <tr><td><code>MUSHEGH_REPLY_LANGUAGE</code></td><td>the single language it replies in</td><td><code>English</code></td></tr>
          <tr><td><code>MUSHEGH_USER_TZ</code></td><td>IANA timezone (drives time, scheduling, calendar)</td><td><code>America/New_York</code></td></tr>
        </tbody>
      </table>

      <p>Drop them in <code>.env</code> (or answer the <Link href="/quickstart">setup wizard</Link>):</p>
      <pre><code>{`MUSHEGH_ASSISTANT_NAME=Aria
MUSHEGH_USER_NAME=Dana
MUSHEGH_USER_ADDRESS=ma'am
MUSHEGH_UNDERSTOOD_LANGUAGES=English, Spanish
MUSHEGH_REPLY_LANGUAGE=English`}</code></pre>

      <p>
        That alone yields: <em>“You are Aria, Dana's personal voice assistant. Address Dana
        as ma'am. They may speak English, Spanish — understand any of them, but always reply
        in English.”</em> Leave a field blank and the prose adapts gracefully (no name &rarr;
        “your personal assistant”; no honorific &rarr; “address them naturally”).
      </p>

      <h2>How it works</h2>
      <p>
        The persona file (<code>personality/mushegh.md</code>, or whatever{" "}
        <code>MUSHEGH_PERSONA_FILE</code> points at) is a template with{" "}
        <code>{`{assistant_name}`}</code>, <code>{`{owner_possessive}`}</code>,{" "}
        <code>{`{address_line}`}</code> and <code>{`{language_line}`}</code> tokens.{" "}
        <code>build_system_prompt()</code> fills them from config at every turn — verified in the
        test suite (which also asserts no unfilled token ever leaks into the prompt). A generic
        starting point lives at <code>personality/persona.example.md</code>.
      </p>

      <h2>Going deeper: persona & profile</h2>
      <ul>
        <li>
          <strong>Rewrite the voice.</strong> Edit the prose in your persona file (tone, manner,
          boundaries) — keep the <code>{`{tokens}`}</code> and they'll still be filled. Point{" "}
          <code>MUSHEGH_PERSONA_FILE</code> at a different file to keep several personas.
        </li>
        <li>
          <strong>Give it knowledge about you (your profile).</strong> The Markdown files under{" "}
          <code>memory/</code> (who you are, your projects, your environment) are injected as
          long-term context. These are <em>yours</em> — fill them with your life, and keep them out
          of any public fork (they're your private profile, not framework code). A generic starter
          ships at <code>personality/persona.example.md</code> and at{" "}
          <code>memory/*.example.md</code>.
        </li>
        <li>
          <strong>Runtime home location.</strong> <code>MUSHEGH_HOME_LOCATION</code> sets a default;{" "}
          <em>“set home to Yerevan”</em> updates it at runtime and persists to{" "}
          <code>runtime_prefs.json</code>, so a multi-month move doesn't need <code>.env</code>
          edits.
        </li>
        <li>
          <strong>Wake word.</strong> Independent of the name — see{" "}
          <Link href="/configuration">Configuration</Link> (<code>MUSHEGH_WAKE_WORDS</code>). The
          spoken name and the wake word can differ (e.g. wake on “hey afon”, identify as
          “Aria”).
        </li>
        <li>
          <strong>Reply length.</strong> Set <code>MUSHEGH_USER_ADDRESS=short</code> (or use commute mode — see{" "}
          <Link href="/modes">Modes</Link>) for terser replies.
        </li>
      </ul>

      <div className="callout">
        <span className="k">Local-first.</span> Identity is pure config — nothing is sent anywhere
        to personalize. Pair it with local STT/TTS (whisper + piper — see{" "}
        <Link href="/configuration">Configuration</Link>) for a fully offline, fully personal
        assistant.
      </div>
    </>
  );
}