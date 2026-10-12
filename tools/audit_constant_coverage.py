"""Can a gate fail? The registry-wide version: does any gate read this shipped number?

`tools/audit_gate_sensitivity.py` (§01.J9) answered one question per hand-written case — four
systems, all in S01 — by breaking the thing a gate guards and watching the gate. It found exactly
one real miss, and the miss had a shape worth generalising:

    widen `jev_arbitration_timeout_seconds` 0.4 -> 5.0, and test_jev_tool_arbitration.py stays GREEN.
    The behavioural tests were GOOD. They inject stub transports and assert behaviour. What they
    never did was reference the shipped cap -- zero times -- and nothing in bench/ mentioned 0.4 in
    a Jev context.

So the signature is mechanical: **a shipped contract number that no gate in the tree references.**
That is what this sweeps for, across every constant `src/mushegh/config.py` declares, and then
confirms by actually breaking a bounded set of them.

Two tiers, and the boundary between them is the whole point of the instrument.

## Tier A — reference sweep (triage, cheap, every constant, no verdict)

    for each of the 268 shipped defaults in src/mushegh/config.py:
        does any bench/test_*.py mention the FIELD NAME?
        does any bench/test_*.py mention the shipped LITERAL VALUE, in a form rare enough to be
        evidence rather than coincidence?

Emits the full ranked table. **Tier A is a TRIAGE, not a verdict, and a row it flags must never be
read as "unguarded".** A constant unreferenced by name can still be covered *behaviourally*: a test
can inject a value through a fixture or monkeypatch and assert on what happens, never naming the
default. Nothing short of Tier B distinguishes "no gate names this number" from "no gate notices
this number", and only Tier B is allowed to call something theatre. This limit is stated here, and
printed next to the number it qualifies, for the same reason §01.J10's runner refuses to launder a
loaded measurement: a number without its instrument's limit attached is a claim the instrument did
not earn.

The value half of the test has a second limit, found while building it. A bare literal is not a
signal on its own: `2.0` occurs **665 times** across the 271 gate files and `8.0` **747 times**, all
of it unrelated. Matching on value alone would have marked nearly every numeric constant "covered"
for no reason at all, which is a false all-clear -- the same failure mode as §01.J11's two bad
audits, pointed at the tree instead of at the instrument. So a value match only counts when the
literal is rare in the corpus (`COLLISION_MAX`). Collisions are reported, not silently swallowed.
Bools go further: `True`/`False` are near-universal Python tokens, so their literal match is
recorded but **excluded from the covered test**, because for a bool the name is the only handle.

## Tier B — mutation confirmation (the only tier allowed to say "theatre")

    backup bytes -> run the gate -> break the default -> run the SAME gate -> restore from bytes.

`before_pass and after_pass` is THEATRE. `before_pass and not after_pass` is caught. A candidate
whose gate is already RED cannot be audited this way and is recorded `baseline-not-green` rather
than counted either way. Mutations are 10x for numbers (the §01.J9 move) and a flip for bools,
chosen to break behaviour rather than to be noticed: two of §01.J9's first-pass mutations were too
weak to prove anything, and that lesson is why these are not comments or renames.

Two guards that stop this reporting false theatre:
  * `.env` shadows a default. If `MUSHEGH_<NAME>` is set there, mutating the config.py default is a
    runtime no-op and the gate stays green for a reason that has nothing to do with the gate. Tier A
    reports these as their own bucket rather than folding them into "unreferenced", because an
    always-overridden default is a different risk class from an untested one: no gate can fail on a
    number no code ever executes, and that is not curable by writing a gate. Tier B skips them.
  * a constant nothing in `src/` reads cannot be broken, only renamed. Those are not candidates.

Every mutation runs inside `try/finally` so a crashing gate still restores, and the restore is
verified against the saved BYTES -- never against `original.encode()`, because `read_text()` applies
universal newlines and re-encoding a CRLF file yields LF, which made four clean restores look
broken in §01.J9.

One gate per candidate, not the suite: this host runs ~50% CPU with another agent on it, and the
question asked here is per-gate ("does the gate that should notice, notice?"), not per-tree. That
choice bounds coverage honestly -- a gate not chosen is a gate not audited, and the report says so.

    .venv\\Scripts\\python.exe tools/audit_constant_coverage.py            # both tiers
    .venv\\Scripts\\python.exe tools/audit_constant_coverage.py --tier-a   # sweep only, seconds
"""
from __future__ import annotations

import argparse
import collections
import re
import shutil
import subprocess
import sys
import tempfile
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = ROOT / ".venv" / "Scripts" / "python.exe"
CONFIG = ROOT / "src" / "mushegh" / "config.py"
BENCH = ROOT / "bench"
ENVFILE = ROOT / ".env"

# A literal seen more often than this across the gate corpus is coincidence, not evidence. Calibrated
# on the real corpus: 2.0 -> 665 hits, 8.0 -> 747, 30 -> 126. Above the line, the value half of the
# reference test is switched OFF rather than allowed to manufacture coverage.
COLLISION_MAX = 25

# Names that make a default a CONTRACT number rather than an incidental setting.
CONTRACT_WORDS = re.compile(
    r"timeout|budget|cap$|cap_|ceiling|threshold|limit|max|min|seconds|_s$|token|retry|"
    r"ttl|deadline|quota|window|depth|width|steps|chars|results|calls|usd",
    re.I,
)

#: `[ \t]` and `[^\n=]`, never `\s` and never a bare `[^=]`: both of those match a newline, so a
#: field whose declaration did not parse on its own physical line would swallow the blank line and
#: the following comment block. That is not theoretical — it produced a Tier-B anchor of
#: "copilot_max_steps: int = 6\n\n    # --- The autonomy governor (36.F6) ..." in which the value `6` occurs twice
#: (once as the default, once inside "36.F6"), and the audit refused to mutate its own target.
FIELD_RE = re.compile(
    r"^    (?P<name>[a-z_][a-z0-9_]*)[ \t]*:[ \t]*(?P<type>[^\n=]+?)[ \t]*=[ \t]*"
    r"(?P<value>[^\n]+?)[ \t]*(?:#.*)?$",
    re.M,
)


# --------------------------------------------------------------------------------------- tier A


@dataclass
class Constant:
    name: str
    type: str
    value: str          # source text of the shipped default
    line: str           # the full source line, used as the Tier-B anchor
    src_uses: int = 0   # times src/ reads it -- a constant nothing reads cannot be broken
    name_refs: int = 0  # gate occurrences of the field name
    value_refs: int = 0 # gate occurrences of the literal (numeric only)
    collided: bool = False
    env_shadowed: bool = False

    @property
    def is_num(self) -> bool:
        try:
            float(self.value)
            return True
        except ValueError:
            return False

    @property
    def is_bool(self) -> bool:
        return self.value in ("True", "False")

    @property
    def by_name(self) -> bool:
        return self.name_refs > 0

    @property
    def by_value(self) -> bool:
        """A value match counts only if it is rare enough to be evidence rather than coincidence."""
        return self.is_num and self.value_refs > 0 and not self.collided

    @property
    def referenced(self) -> bool:
        return self.by_name or self.by_value

    @property
    def contract(self) -> bool:
        return bool(CONTRACT_WORDS.search(self.name))

    def numeric_forms(self) -> set[str]:
        v = float(self.value)
        forms = {repr(v), str(v)}
        if v == int(v):
            forms.add(str(int(v)))
        return forms


def load_constants() -> list[Constant]:
    src = CONFIG.read_text(encoding="utf-8")
    return [
        Constant(name=m["name"], type=m["type"].strip(), value=m["value"].strip(), line=m.group(0))
        for m in FIELD_RE.finditer(src)
    ]


def gate_corpus() -> tuple[Counter, Counter, list[str]]:
    """One pass over every bench/test_*.py, indexed as identifier and numeric-literal counters.

    Done as a single pass on purpose: the obvious implementation -- a regex scan of the whole
    2.3 MB corpus once per constant -- is 268 full scans and took 90 s in the prototype. This
    returns in about a second, which is what makes "every constant" affordable rather than a sample.
    """
    names: Counter = collections.Counter()
    nums: Counter = collections.Counter()
    files: list[str] = []
    id_re = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
    num_re = re.compile(r"(?<![\w.])(\d+(?:\.\d+)?)(?![\w.])")
    for gate in sorted(BENCH.glob("test_*.py")):
        text = gate.read_text(encoding="utf-8", errors="replace")
        files.append(gate.name)
        names.update(id_re.findall(text))
        nums.update(num_re.findall(text))
    return names, nums, files


def env_shadowed_names() -> set[str]:
    """Constants whose shipped default is overridden by .env, so mutating it is a runtime no-op."""
    shadowed: set[str] = set()
    if not ENVFILE.is_file():
        return shadowed
    for line in ENVFILE.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key = line.split("=", 1)[0].strip().removeprefix("MUSHEGH_").lower()
        if key:
            shadowed.add(key)
    return shadowed


def index(constants: list[Constant], names: Counter, nums: Counter, src_names: Counter) -> None:
    """src_uses comes from a prebuilt identifier Counter rather than a per-constant regex scan.
    Scanning src/ once per constant is 268 passes over the tree and cost ~55 of the ~60 s this tier
    originally took; the Counter makes it a dictionary lookup and the whole sweep a couple of seconds.
    """
    shadowed = env_shadowed_names()
    for c in constants:
        c.name_refs = names.get(c.name, 0)
        c.src_uses = src_names.get(c.name, 0)
        if c.is_num:
            c.value_refs = max((nums.get(f, 0) for f in c.numeric_forms()), default=0)
            c.collided = c.value_refs > COLLISION_MAX
        c.env_shadowed = c.name in shadowed


def source_corpus() -> Counter:
    """Identifier frequency across src/, excluding config.py itself so a field is never counted as
    a use of itself."""
    names: Counter = collections.Counter()
    id_re = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
    for path in (ROOT / "src").rglob("*.py"):
        if path.name == "config.py":
            continue
        names.update(id_re.findall(path.read_text(encoding="utf-8", errors="replace")))
    return names


# --------------------------------------------------------------------------------------- tier B


@dataclass
class Candidate:
    name: str
    gate: str          # the single most-relevant gate; see the coverage note in the docstring
    why: str           # what the constant governs, and why this gate is the one that should notice
    new_value: str     # the mutated default -- 10x for numbers, flipped for bools


# Bounded, hand-picked from the Tier-A pool, and every entry is VALIDATED against Tier-A output at
# run time (must be unreferenced, must be load-bearing, must not be .env-shadowed), so this list
# cannot silently drift away from the data it claims to come from. Gate choice is the one part that
# needs judgement rather than a regex: it is the gate that owns the subsystem, not merely a gate whose
# name shares a word with the constant.
CANDIDATES: list[Candidate] = [
    Candidate(
        "memory_autorecall_limit", "test_memory_autorecall.py",
        "max facts auto-injected per turn. This gate already reads THREE neighbouring settings "
        "(memory_autorecall_enabled, _min_words, memory_digest_refresh_every_turns) and this one "
        "nowhere -- the §01.J9 signature exactly.",
        "40"),
    Candidate(
        "autonomy_max_calls", "test_safety_autonomy.py",
        "the tool+model call ceiling per autonomy window, across all autonomous runs. The autonomy "
        "governor exists to enforce a bound; 200 -> 2000 removes it.",
        "2000"),
    Candidate(
        "code_self_improve_max_steps", "test_code_self_improve.py",
        "the step budget a self-improving run may burn. This gate reads code_self_improve_enabled "
        "and never the budget that bounds the loop it turns on.",
        "80"),
    Candidate(
        "wake_listen_window_s", "test_phase1_vad_bargein.py",
        "how long the mic stays open after a wake or reply -- the barge-in window. 8s -> 80s is the "
        "difference between an interruptible assistant and one that cannot be interrupted.",
        "80.0"),
    Candidate(
        "objectives_max_steps", "test_objectives.py",
        "the bounded worker step budget per objective. Unbounded work is what turns an objective "
        "into a runaway; 6 -> 60 is not a rounding change.",
        "60"),
    Candidate(
        "vad_enabled", "test_wakeword_offline.py",
        "the voice-activity gate itself. Bool, so the mutation is a flip rather than a scale.",
        "False"),

    # ---- tranche 2 (2026-10-11) ------------------------------------------------------------------
    # Picked from the 75 mutatable Tier-A candidates Tier B was not reaching, because `CANDIDATES`
    # was a fixed list of six and could not advance past them once test_constant_contracts.py closed
    # those (see §01.J17). Ordered by consequence: bounds that decide when work STOPS come before
    # bounds that shape what it sees.
    Candidate(
        "autonomy_max_usd", "test_safety_autonomy.py",
        "the governor's SPEND ceiling, and the direct sibling of autonomy_max_calls (already pinned "
        "by test_constant_contracts.py). Read at governor.py as getattr(settings, 'autonomy_max_usd', "
        "2.0) -- the same duplicated-default shape, so this one carries the rename hazard too. A "
        "governor with a calls ceiling but an unmonitored spend ceiling is one runaway away from the "
        "~565M-token failure the governor exists to prevent.",
        "20.0"),
    Candidate(
        "memory_vault_search_budget_s", "test_vault_search.py",
        "the wall-clock budget on a vault search. Search is the slowest thing the owner can ask for, "
        "so this number IS the latency of the feature; 6s -> 60s turns a bounded search into a turn "
        "that appears to hang.",
        "60.0"),
    Candidate(
        "copilot_max_steps", "test_copilot.py",
        "the step budget for the co-pilot's background worker. The bounded work loop's reason for "
        "being; 6 -> 60 is not a rounding change.",
        "60"),
    Candidate(
        "intervention_lead_minutes", "test_interventions.py",
        "how far ahead of a deadline the owner gets warned. A lead that is too long is noise he "
        "learns to ignore -- the intervention system failing by over-warning, which no gate catches.",
        "100"),
    Candidate(
        "goal_deviation_deadline_days", "test_goal_deviation.py",
        "how long a goal may drift before it counts as deviated. Widen it and drift stops being "
        "detected for weeks; the goal system reports itself healthy precisely because nothing is "
        "comparing.",
        "70"),
    Candidate(
        "vault_search_max_results", "test_vault_search.py",
        "how many hits a vault search returns before the results are truncated. Too few and a real "
        "answer is cut off and never seen, which reads as the answer not existing.",
        "60"),
    Candidate(
        "objectives_max", "test_objectives.py",
        "how many objectives the turn may carry at once. The sibling of objectives_max_steps (already "
        "pinned): together they are the whole bound on background work per turn.",
        "20"),
    Candidate(
        "memory_recall_limit", "test_memory_salience.py",
        "the cap on hits the recall TOOL returns, the sibling of memory_autorecall_limit (already "
        "pinned). Both are injection caps; the tool one is the one a caller can reach directly.",
        "50"),

    # ---- tranche 3 (2026-10-11) ------------------------------------------------------------------
    # Gate ownership was PROPOSED automatically from the module that reads each setting, but only
    # 20 of 47 proposals were unambiguous — the other 27 put the reader inside 2-8 different gate
    # names and picking one would have been a guess. Guesses do not go in: an audit run on a
    # wrongly-attributed gate reports "the gate is silent" when the truth is "nobody looked".
    # These ten are the ones where the owner is decidable, and two of them are picked precisely
    # BECAUSE they are safety-relevant rather than merely unguarded.
    Candidate(
        "system_tools_enabled", "test_phase4_system_protocols.py",
        "whether the privileged system tools exist at all. Flipping it to False removes the "
        "capability rather than tuning it, so a gate that misses this is not being strict about "
        "the privileged surface - it does not know the surface is gone. Safety-relevant, which is "
        "why it is here ahead of anything else in the tranche.",
        "False"),
    Candidate(
        "system_protected_paths", "test_phase4_system_protocols.py",
        "the paths the privileged tools refuse to touch: C:\\Windows and both Program Files trees. "
        "Narrowing this to a path that does not exist turns a protection into a no-op while every "
        "test still passes, because nothing has yet tried to write to the real directory. First "
        "attempt at this was declared INERT: the candidate carried its own surrounding quotes, and "
        "Settings() resolves the bare string. The inert check caught it and counted it neither way "
        "— which is the whole reason that check exists.",
        'C:\\\\Mushegh-Nonexistent\\\\Nothing'),
    Candidate(
        "coding_tools_enabled", "test_coding_chain.py",
        "the switch for the whole coding capability. False removes the tools from the belt rather "
        "than degrading them, so this measures whether the chain gate knows the chain is gone.",
        "False"),
    Candidate(
        "memory_semantic_weight", "test_phase9c_semantic.py",
        "how much a semantic match outranks a lexical one in recall ranking. At 40.0 the embedding "
        "channel dominates outright; at 0 lexical wins. Either way the ORDER of results changes, "
        "and a recall gate that does not notice is only testing that recall returns something.",
        "40.0"),
    Candidate(
        "intervention_urgency", "test_interventions.py",
        "the urgency threshold that separates 'interrupt him' from 'queue it', sitting between "
        "context_override and quiet_override. Move it out of that band and the intervention system "
        "silently changes class: either never fires or always does.",
        "9.0"),
    Candidate(
        "vad_confidence", "test_phase1_vad_bargein.py",
        "the Silero speech-probability threshold. 6.0 is outside the 0..1 domain entirely, so a "
        "gate that passes on it is not testing the threshold - it is testing that the code loads.",
        "6.0"),
    Candidate(
        "jev_timeout_seconds", "test_jev_judgment.py",
        "the Jev service timeout: how long a turn will wait before giving up on its advisor. 80.0 "
        "means a dead advisor holds the turn for a minute and a half, which is the failure "
        "01.J1's one-bounded-call rule exists to prevent.",
        "80.0"),
    Candidate(
        "browser_nav_timeout_ms", "test_browser_submit_confirm.py",
        "the Playwright default timeout for every navigation. No gate is named for it - the "
        "browser gates are about submit-confirm and the speechbrain guard - so this asks whether "
        "anything at all watches a browser that will hang for 30 s per navigation by default.",
        "300000"),
    Candidate(
        "backlog_max_tasks", "test_brain_agent.py",
        "how many tasks the daily pass may attempt. The sibling of copilot_max_steps, already "
        "pinned: together they are what stops the daily loop from becoming an unbounded run.",
        "20"),
    Candidate(
        "a2a_poll_seconds", "test_a2a_transport.py",
        "how often a delegated task is polled. It is the floor on the latency of every "
        "agent-to-agent answer, so a poll interval nobody watches is a latency nobody watches.",
        "20.0"),
]


def runtime_value(field_name: str) -> str:
    """The value `Settings()` actually resolves at runtime, read by a real interpreter.

    This exists because a mutation that does not take effect produces a gate that stays green for a
    reason that has nothing to do with the gate — an inert mutation would be indistinguishable from
    theatre in the output. Six of the six candidates were confirmed to change the resolved value
    before any verdict below was allowed to be reported; without that check all six would have been
    unfalsifiable. Verified on a clean tree by mutating, probing, and restoring.
    """
    probe = (
        "import sys;sys.path.insert(0,'src');"
        "from mushegh.config import Settings;"
        f"print(repr(getattr(Settings(),{field_name!r})))"
    )
    proc = subprocess.run(
        [str(PY), "-c", probe], cwd=str(ROOT), capture_output=True, text=True, timeout=180,
    )
    return proc.stdout.strip() if proc.returncode == 0 else f"<probe failed: {proc.stderr.strip()[-120:]}>"


def run_gate(gate: str) -> bool:
    """True when the gate PASSES. Raises on a broken environment."""
    proc = subprocess.run(
        [str(PY), str(BENCH / gate)],
        cwd=str(ROOT), capture_output=True, text=True, timeout=600,
    )
    return proc.returncode == 0


def mutate_line(line: str, old: str, new: str) -> str:
    """Replace the shipped default on the field's own line, once. The line is the anchor, so a
    default that also occurs in a comment or on another line cannot be hit by accident."""
    if line.count(old) != 1:
        raise ValueError(f"anchor {old!r} is not unique on the line: {line!r}")
    return line.replace(old, new, 1)


#: Written BEFORE the first mutation and removed only on a clean exit. The per-case `finally`
#: restores on an exception, but it cannot run when the process is KILLED — a runner timeout, a
#: closed console, Task Manager. That is not hypothetical: on 2026-10-12 an attribution run was
#: killed mid-mutation and left `copilot_autopilot_enabled` flipped in config.py. A `finally` is
#: not a restore guarantee against a kill, so the restore has to live somewhere the kill cannot
#: reach: on disk, repaired by the NEXT run before it touches anything.
_RESCUE = ROOT / "logs" / "_audit_rescue_config.py"


def rescue_interrupted_run() -> str | None:
    """Repair config.py if a previous run died holding a mutation. Returns what it did, or None.

    Deliberately unconditional on the backup's existence: the tool is the only thing that writes
    that path, its presence means a run started mutating and never finished, and the content is a
    pre-mutation snapshot. It says so loudly rather than doing it quietly, because silently
    reverting someone's file is its own kind of surprise.
    """
    if not _RESCUE.is_file():
        return None
    saved = _RESCUE.read_bytes()
    _RESCUE.unlink()
    if CONFIG.read_bytes() == saved:
        return None
    CONFIG.write_bytes(saved)
    return ("config.py was left MUTATED by an interrupted run and has been restored from that "
            "run's pre-mutation snapshot — compare it against git before trusting the tree")


def tier_b(by_name: dict[str, Constant], limit: int) -> int:
    backup = Path(tempfile.mkdtemp(prefix="const-audit-"))
    print("\n" + "=" * 78)
    print("TIER B — mutation confirmation. The only tier allowed to say 'theatre'.")
    print("=" * 78)
    print("One gate per candidate, not the suite: the host is loaded and the question is per-gate.")
    print("A gate not chosen here is a gate NOT audited — that is a limit of this run, not a result.\n")

    header = f"{'constant':32}{'gate':32}{'before':>8}{'after':>8}{'verdict':>18}"
    print(header)
    print("-" * len(header))

    theatre: list[str] = []
    caught: list[str] = []
    skipped: list[str] = []
    inert: list[str] = []
    problems: list[str] = []
    touched: list[tuple[Path, bytes]] = []
    ran = 0

    # Armed before anything is touched, so a kill at any point leaves a recoverable snapshot on
    # disk rather than a mutated config.py with nothing pointing back to the original.
    _RESCUE.parent.mkdir(parents=True, exist_ok=True)
    _RESCUE.write_bytes(CONFIG.read_bytes())
    try:
        return _tier_b_cases(by_name, limit, backup, header, theatre, caught, skipped, inert,
                             problems, touched, ran)
    finally:
        # Cleared only once the tree is byte-identical to the snapshot. A kill skips this entirely,
        # which is the whole point — `rescue_interrupted_run()` repairs it on the next invocation.
        if _RESCUE.is_file() and CONFIG.read_bytes() == _RESCUE.read_bytes():
            _RESCUE.unlink()


def _tier_b_cases(by_name, limit, backup, header, theatre, caught, skipped, inert, problems,
                  touched, ran) -> int:

    for cand in CANDIDATES:
        if ran >= limit:
            skipped.append(f"{cand.name}: beyond --top {limit}")
            print(f"{cand.name:32}{'--':32}{'--':>8}{'--':>8}{'NOT RUN (limit)':>18}")
            continue

        const = by_name.get(cand.name)
        if const is None:
            skipped.append(f"{cand.name}: no longer declared in config.py")
            print(f"{cand.name:32}{cand.gate:32}{'--':>8}{'--':>8}{'NOT IN CONFIG':>18}")
            continue
        # Validate the hand-picked list against the Tier-A sweep, so it cannot drift from the data.
        if const.referenced:
            skipped.append(f"{cand.name}: now referenced by a gate — Tier A says no longer a candidate")
            print(f"{cand.name:32}{cand.gate:32}{'--':>8}{'--':>8}{'NOW COVERED':>18}")
            continue
        if const.env_shadowed:
            skipped.append(f"{cand.name}: .env shadows this default; mutating it is a runtime no-op")
            print(f"{cand.name:32}{cand.gate:32}{'--':>8}{'--':>8}{'ENV-SHADOWED':>18}")
            continue
        if const.src_uses == 0:
            skipped.append(f"{cand.name}: nothing in src/ reads it — cannot be broken, only renamed")
            print(f"{cand.name:32}{cand.gate:32}{'--':>8}{'--':>8}{'NOT LOAD-BEARING':>18}")
            continue
        if not (BENCH / cand.gate).is_file():
            skipped.append(f"{cand.name}: gate {cand.gate} does not exist")
            print(f"{cand.name:32}{cand.gate:32}{'--':>8}{'--':>8}{'NO SUCH GATE':>18}")
            continue
        if cand.new_value == const.value:
            skipped.append(f"{cand.name}: mutation equals the shipped default — too weak to prove anything")
            print(f"{cand.name:32}{cand.gate:32}{'--':>8}{'--':>8}{'WEAK MUTATION':>18}")
            continue

        ran += 1
        target = CONFIG
        copy = backup / f"{cand.name}.config.py"
        shutil.copy2(target, copy)
        before_bytes = copy.read_bytes()
        touched.append((target, before_bytes))
        try:
            before = run_gate(cand.gate)
            if not before:
                # A gate that is already RED cannot answer "does it notice?" — reporting it as caught
                # or as theatre would both be inventions.
                skipped.append(f"{cand.name}: {cand.gate} is already RED on a clean tree")
                print(f"{cand.name:32}{cand.gate:32}{'FAIL':>8}{'--':>8}{'BASELINE NOT GREEN':>18}")
                continue

            text = target.read_text(encoding="utf-8")
            if text.count(const.line) != 1:
                problems.append(f"{cand.name}: anchor line is not unique in config.py")
                print(f"{cand.name:32}{cand.gate:32}{'pass':>8}{'--':>8}{'ANCHOR AMBIGUOUS':>18}")
                continue

            try:
                new_line = mutate_line(const.line, const.value, cand.new_value)
            except ValueError as exc:
                # One unusable anchor must cost one candidate, never the rest of the run. This
                # raised and killed tranche 2 after two findings, so five candidates went
                # unaudited and the report looked like a clean finish.
                skipped.append(f"{cand.name}: {exc}")
                print(f"{cand.name:32}{cand.gate:32}{'pass':>8}{'--':>8}{'UNUSABLE ANCHOR':>18}")
                continue
            target.write_text(text.replace(const.line, new_line, 1), encoding="utf-8")

            # Confirm the mutation reached the running code before believing any result from it.
            effective = runtime_value(cand.name).strip("'\"")
            if effective != cand.new_value:
                inert.append(f"{cand.name}: Settings() still resolves {effective!r}, "
                             f"not {cand.new_value!r} — mutation did not take effect")
                print(f"{cand.name:32}{cand.gate:32}{'pass':>8}{'--':>8}{'MUTATION INERT':>18}")
                continue

            after = run_gate(cand.gate)

            if after:
                verdict = "THEATRE"
                theatre.append(f"{cand.name} -> {cand.gate}")
            else:
                verdict = "caught"
                caught.append(f"{cand.name} -> {cand.gate}")
            print(f"{cand.name:32}{cand.gate:32}{'pass':>8}{'pass' if after else 'RED':>8}{verdict:>18}")
        finally:
            # Restore from the BYTES we copied, and verify against those same bytes. Comparing to
            # `original.encode()` is wrong: read_text() applies universal newlines, so re-encoding
            # a CRLF file yields LF and every clean restore reports as a failure. That bug made four
            # clean restores look broken in §01.J9.
            shutil.copy2(copy, target)
            if target.read_bytes() == before_bytes:
                print(f"{'':32}{'':32}{'':8}{'restored':>8}{'ok':>18}")
            else:
                problems.append(f"RESTORE FAILED for {target} ({cand.name})")

    print(f"\nTier B: {len(theatre)} THEATRE · {len(caught)} caught · {len(skipped)} not audited "
          f"· {len(inert)} inert · {ran} actually mutated "
          f"(of {len(CANDIDATES)} declared candidates)")
    print("  Every THEATRE here was first confirmed to change the value Settings() resolves at")
    print("  runtime, so the gate went green with the contract number genuinely broken.")
    # The false all-clear, caught before it shipped one. `CANDIDATES` is a hand-picked list, so a
    # run can legitimately mutate NOTHING and still print "0 THEATRE" — which reads as a clean
    # tree. It is not a clean tree. This happens for real: once test_constant_contracts.py covered
    # the original six, every declared candidate became "NOW COVERED", Tier B audited nothing, and
    # the headline still read `0 THEATRE`. Say so instead of letting the number stand alone.
    if ran == 0:
        pool = [c for c in by_name.values()
                if not c.referenced and not c.env_shadowed and c.src_uses > 0]
        print("\n  *** TIER B AUDITED NOTHING. ***")
        print("      The headline above reads 0 THEATRE because no candidate was broken, NOT because")
        print("      the tree is clean. CANDIDATES is a hand-picked list; Tier A is what knows the")
        print("      real pool. Add candidates before reading anything into this run.")
        print(f"      MUTABLE CANDIDATES STILL UNEXAMINED: {len(pool)}")
    if inert:
        print("\nINERT MUTATIONS — these prove nothing and are not counted either way:")
        for i in inert:
            print(f"  - {i}")
    if theatre:
        print("\nTHEATRE — the gate stayed GREEN with its contract number broken:")
        for t in theatre:
            print(f"  - {t}")
    if skipped:
        print("\nnot audited (recorded, NOT counted as caught and NOT counted as theatre):")
        for s in skipped:
            print(f"  - {s}")

    # Whole-run check, after every try/finally has unwound: nothing mutated may still be mutated.
    print("\nfinal restore verification across every file this run mutated:")
    for path, expected in touched:
        ok = path.read_bytes() == expected
        print(f"  {path.relative_to(ROOT).as_posix():40} {'byte-exact' if ok else 'DIFFERS'}")
        if not ok:
            problems.append(f"FINAL RESTORE FAILED for {path}")

    shutil.rmtree(backup, ignore_errors=True)
    return len(theatre)


# ---------------------------------------------------------------------------------------- main


def tier_a() -> tuple[list[Constant], list[Constant]]:
    constants = load_constants()
    names, nums, files = gate_corpus()
    index(constants, names, nums, source_corpus())
    unreferenced = [c for c in constants if not c.referenced]

    print("=" * 78)
    print("TIER A — constant-reference sweep. TRIAGE, NOT A VERDICT.")
    print("=" * 78)
    print(f"shipped constants in src/mushegh/config.py   {len(constants)}")
    print(f"gate files swept (bench/test_*.py)           {len(files)}")
    print(f"referenced by name or by a rare literal      {len(constants) - len(unreferenced)}")
    print(f"ZERO gate references (triage candidates)    {len(unreferenced)}")
    print(f"  ...of which numeric                        {sum(1 for c in unreferenced if c.is_num)}")
    print(f"  ...of which bool                            {sum(1 for c in unreferenced if c.is_bool)}")
    print(f"  ...load-bearing (src/ reads them)           {sum(1 for c in unreferenced if c.src_uses)}")
    print(f"  ...contract-named                           {sum(1 for c in unreferenced if c.contract)}")

    # An always-overridden default is a DIFFERENT risk from an untested one, so it gets its own line
    # rather than being folded into the unreferenced count. If .env sets MUSHEGH_<NAME>, the shipped
    # default never reaches runtime: no gate can fail on it because no code executes it. That is a
    # dead default, not a merely unverified one, and it is not curable by writing a gate.
    shadowed = [c for c in unreferenced if c.env_shadowed]
    shadowed_all = [c for c in constants if c.env_shadowed]
    print(f"\n.env-shadowed defaults (shipped default never reaches runtime)  {len(shadowed_all)}")
    print(f"  ...of those, ALSO carrying zero gate references                {len(shadowed)}")
    if shadowed:
        for c in shadowed:
            print(f"      {c.name:44} default={c.value:<12} contract={c.contract}")
    print("  These are excluded from Tier B on purpose: mutating a shadowed default is a runtime")
    print("  no-op, so the gate would stay green for a reason that has nothing to do with the gate.")

    print("\nWHAT THIS TIER CANNOT TELL YOU")
    print("  A constant unreferenced by name may still be covered BEHAVIOURALLY — a test can inject a")
    print("  value through a fixture or monkeypatch and assert on the outcome without ever naming the")
    print("  default. Nothing below says 'unguarded'. Only Tier B, which breaks the number and watches")
    print("  a gate, may promote a row here to a finding.")
    print(f"\n  A literal is treated as evidence only at <= {COLLISION_MAX} corpus hits. Calibrated on the")
    print("  real corpus: 2.0 occurs 665 times and 8.0 747 times, all of it unrelated text. Counting")
    print("  those as coverage would be a false all-clear — the §01.J11 failure mode, pointed at the")
    print("  tree instead of at the instrument. Bools are excluded from the value test entirely:")
    print("  True/False are near-universal Python tokens, so for a bool the name is the only handle.")
    return constants, unreferenced


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--tier-a", action="store_true", help="reference sweep only; no mutation")
    ap.add_argument("--top", type=int, default=len(CANDIDATES),
                    help=f"max Tier-B candidates to mutate (default {len(CANDIDATES)})")
    args = ap.parse_args()

    if not PY.is_file():
        print("venv python not found; run through uv.")
        return 2

    # Before anything is read, let alone mutated: a previous run may have died holding a
    # mutation, and Tier A's numbers would otherwise describe a config.py that is not real.
    rescued = rescue_interrupted_run()
    if rescued:
        print("*** RECOVERED ***")
        print(f"    {rescued}")

    constants, unreferenced = tier_a()

    if args.tier_a:
        return 0

    by_name = {c.name: c for c in constants}
    theatre = tier_b(by_name, args.top)
    return 0 if theatre == 0 else 1


if __name__ == "__main__":
    sys.exit(main())