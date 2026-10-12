"""37.R4 â€” what class of data each store holds, declared before any retention rule is written.

Jev p = 0.95, conf 0.93 â€” the highest-confidence directive in the whole evaluation:
*classify data first â€” biometric, financial, medical, ordinary â€” before writing any retention rule;
every other rule, retention included, depends on knowing which class a thing is.*

Two design decisions worth stating, because both were the alternative to writing something false:

**A store declares the set of classes it MAY contain, not the one it usually does.** A single label
would have forced a lie about half of these. ``memory/`` is the owner's life in prose: it holds what
he earns, what his doctor said, and what he wants from the week, in the same file. ``traces/`` holds
prompts, so it holds whatever was in them. ``screenshots/`` holds whatever was on the screen. The
honest declaration for a container is **the strictest class it can hold**, and a frozenset costs the
same as a string while letting the handling rule pick the strictest itself (``strictest()``).

**The gate is discovery-based, not list-based.** ``unclassified()`` walks the live state root and
reports anything with no declaration. A test that only checked the declarations against each other
would pass forever while a new store appeared beside them â€” which is the failure this whole
directive exists to prevent, and the same shape as the HUD section that was emitted and never drawn
(P1.2).

``leaves_host`` is carried here rather than in prose because it is the one property that has a
standing, absolute rule behind it: **owner biometrics never leave the laptop.** Written as data, it
is checkable; written in a document, it is a promise.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

#: The four classes Jev named. Strictest first â€” `strictest()` depends on this order, and the order
#: is a judgement worth stating: biometrics identify the body and cannot be reissued; a medical fact
#: is the most damaging thing here to disclose; a financial fact is recoverable but exploitable.
BIOMETRIC = "biometric"
MEDICAL = "medical"
FINANCIAL = "financial"
ORDINARY = "ordinary"
STRICTEST_FIRST: tuple[str, ...] = (BIOMETRIC, MEDICAL, FINANCIAL, ORDINARY)
CLASSES = frozenset(STRICTEST_FIRST)


@dataclass(frozen=True)
class Store:
    """One place data lives, and what may be in it."""

    name: str                    #: path relative to the state root, or a logical name for an external store
    classes: frozenset[str]      #: every class this store MAY hold
    leaves_host: bool            #: may these bytes ever cross the network?
    why: str                     #: why that set, in one line

    @property
    def strictest(self) -> str:
        return strictest(self.classes)


def _s(name: str, classes: tuple[str, ...], leaves_host: bool, why: str) -> Store:
    assert set(classes) <= CLASSES, f"{name}: unknown class in {classes}"
    return Store(name, frozenset(classes), leaves_host, why)


#: Every store, declared. An entry whose `name` contains no "/" and no "." is a directory under the
#: state root; anything else is matched literally. External stores are named with a `!` prefix so
#: they can never collide with a filename.
STORES: tuple[Store, ...] = (
    # ---- biometric: the three files that must never leave this laptop --------------------------
    _s("voiceprint.json", (BIOMETRIC,), False,
       "the owner's speaker embedding â€” the thing the speaker gate compares against"),
    _s("faces", (BIOMETRIC,), False,
       "owner.npy, the face embedding used as the confirm tier's second factor"),

    # ---- containers that hold whatever the owner said -----------------------------------------
    _s("memory", (MEDICAL, FINANCIAL, ORDINARY), True,
       "L1 learned facts and L2 journal: his health, his money and his week in the same prose"),
    _s("mushegh_graph.sqlite", (MEDICAL, FINANCIAL, ORDINARY), True,
       "the memory graph indexes the same prose, so it inherits the same classes"),
    _s("mushegh_vectors.sqlite", (MEDICAL, FINANCIAL, ORDINARY), True,
       "embeddings of that prose; an embedding is not anonymisation"),
    _s("traces", (MEDICAL, FINANCIAL, ORDINARY), True,
       "turn traces carry prompts, and a prompt carries whatever was being discussed"),
    _s("screenshots", (MEDICAL, FINANCIAL, ORDINARY), True,
       "whatever was on the screen; a container cannot be cleaner than its contents"),

    # ---- specific classes ----------------------------------------------------------------------
    _s("mushegh_coaching.sqlite", (MEDICAL, ORDINARY), True,
       "wellbeing nudges and habit history, which is health data however gently phrased"),
    _s("vitals.json", (MEDICAL,), False,
       "heart rate, sleep, steps, weight read from an export the owner already has. MEDICAL because "
       "it is the body, and never leaves this machine because nothing here sends it anywhere -- "
       "34.F3 states observations only, no condition named and no treatment advised"),
    _s("mushegh_stock.sqlite", (FINANCIAL,), True, "holdings and prices"),
    _s("forecasts.jsonl", (FINANCIAL, ORDINARY), True, "predictions, including financial ones"),

    # ---- ordinary operational state ------------------------------------------------------------
    _s("mushegh_tasks.sqlite", (ORDINARY,), True, "task rows"),
    _s("mushegh_jobs.sqlite", (ORDINARY,), True, "the APScheduler jobstore"),
    _s("mushegh_presence.sqlite", (ORDINARY,), True, "which device he is at"),
    _s("mushegh_work.sqlite", (ORDINARY,), True, "background work rows"),
    _s("mushegh_session.json", (ORDINARY,), True, "the resumable session pointer"),
    _s("approvals.json", (ORDINARY,), True, "pending approvals â€” summaries, not payloads"),
    _s("governor.json", (ORDINARY,), True, "the autonomy ledger: counts, money, seconds"),
    _s("relationship.json", (ORDINARY,), True, "interaction style state"),
    _s("room_context.json", (ORDINARY,), True, "who else is in the room"),
    _s("runtime_prefs.json", (ORDINARY,), True, "spoken preference overrides"),
    _s("tool_usage.json", (ORDINARY,), True, "per-tool counts, for reliability"),
    _s("patterns.jsonl", (ORDINARY,), True, "learned routine patterns"),
    _s("delivery_ledger.json", (ORDINARY,), True, "what was already said, so it is not said twice"),
    _s("daily_digest_state.json", (ORDINARY,), True, "the last digest's watermark"),
    # Found by the gate on 2026-10-08, not by reading: `day_plan.json` is written by
    # `routines.plan_today` and read by the reminder scheduler, but nothing had ever
    # CALLED plan_today, so the file never existed in a live state root and no one had to
    # classify it. Adding a route for day planning made that tool fire for the first time,
    # the file appeared, and the table that exists precisely to catch unclassified owner
    # data did its job on the first day it was given something real to find. Same shape as
    # the daily digest's watermark beside it: ordinary operational state that leaves the host.
    _s("day_plan.json", (ORDINARY,), True, "today's plan as Mushegh understands it"),
    # Two files that were on disk in the live state root with no declaration here, which is
    # the exact failure this table exists to prevent: unclassified owner data. `audio_pref.json`
    # is written by the edge audio device picker; `restore_drill.json` is written by the backup
    # restore drill. Both are ordinary operational state and both may leave the host, the same
    # as the other preference and ledger files above them.
    _s("audio_pref.json", (ORDINARY,), True,
       "which speaker he wants Mushegh to talk through â€” a device preference, not a biometric"),
    _s("restore_drill.json", (ORDINARY,), True,
       "the last restore drill's verdict; operational history, and the reason a drill is run "
       "at all is to be able to say afterwards whether it would have worked"),
    _s("proactive_state.json", (ORDINARY,), True, "proactivity budget and quiet-hours state"),
    # Added 2026-10-09 with brain/calibration.py. Declared on the day it was written rather than
    # when a gate caught it, which is the point of having the table. It is ORDINARY because a
    # calibration record is a confidence and an outcome â€” but `detail` carries a short label for
    # what was decided ("office vs cafe"), and a decision label is about the owner's life, so it
    # inherits the strictest class it can hold rather than being called operational.
    _s("calibration.jsonl", (MEDICAL, FINANCIAL, ORDINARY), True,
       "reported confidence paired with the outcome, for ECE/Brier; the detail string names the "
       "decision being judged, so this is owner data wearing a metrics hat"),
    # Found by the gate on 2026-10-11, hours after it was written. `composio_catalog.json` is the
    # on-disk cache of Composio's public tool catalogue, refreshed daily and on startup. It was
    # undeclared for as long as Composio had no API key, because `refresh()` skips the fetch when
    # one is not configured — the same reason `day_plan.json` above stayed invisible until a tool
    # route first made it appear. Configuring Composio made a 160 KB file exist that no gate could
    # account for.
    #
    # ORDINARY, and leaves the host. The contents are third-party API metadata — tool names,
    # descriptions and parameter schemas — so no owner data is in it. What it does carry is the
    # LIST of active toolkits, which is a small fingerprint of which apps this account has wired
    # up; that is configuration state, like the device preference and the approval summaries above
    # it, and it is why this is declared explicitly rather than waved through `_NOT_A_STORE`.
    _s("composio_catalog.json", (ORDINARY,), True,
       "the cached Composio tool catalogue: third-party API metadata plus which toolkits this "
       "account has active, which is configuration state about the owner even though the bulk of "
       "the file is not about him at all"),
    _s("errors.jsonl", (ORDINARY,), True,
       "scrubbed error records; the scrubber is what keeps this class honest"),
    _s("conversation_id", (ORDINARY,), True, "one opaque id"),
    _s("run", (ORDINARY,), True, "pid and lock files"),
    _s("shell", (ORDINARY,), True, "the 04.R4 shell working directory"),
    _s("MAINTENANCE", (ORDINARY,), True, "the park marker â€” its presence is the whole content"),
    _s("MIGRATED.txt", (ORDINARY,), True, "the 30.F1 migration receipt"),

    # ---- stores outside the state root ---------------------------------------------------------
    _s("!audit", (MEDICAL, FINANCIAL, ORDINARY), True,
       "audit lines carry tool arguments, so they inherit the classes of what was being done"),
    _s("!postgres", (MEDICAL, FINANCIAL, ORDINARY), True,
       "a legacy Postgres directory. The runtime store is SQLite and always was (D-02), but the "
       "classification is kept: a host that ran the staged adapters may still have one on "
       "disk, and unclassified owner data is the failure this table exists to prevent"),
    _s("!vault", (MEDICAL, FINANCIAL, ORDINARY), True,
       "the Obsidian vault on the VPS â€” decisions, and the life they were about"),
    _s("!env", (ORDINARY,), False,
       "credentials. Not one of the four classes and never in git: secrets are not owner data, "
       "they are access to it"),
    _s("!contacts", (ORDINARY,), False,
       "other people's handles and addresses â€” his to hold, not his to leak"),
    _s("goal_deviation_log.jsonl", (MEDICAL, FINANCIAL, ORDINARY), False,
       "14.R4's would-have-said log: goal text plus the window title he was looking at. Goals carry "
       "health and money targets and a title carries anything, so it declares what it may hold"),
    _s("jev_judgments.jsonl", (MEDICAL, FINANCIAL, ORDINARY), False,
       "14.R5's compact local judgment provenance: correlation/request and stable option IDs, result, "
       "confidence, model, timing and outcome. It deliberately excludes question and option prose"),
    _s("degraded_digest.json", (MEDICAL, FINANCIAL, ORDINARY), False,
       "23.R2's cached reminder digest: reminder names, which are whatever he set them about - a doctor, a payment, a call"),
    _s("offline_queue.jsonl", (MEDICAL, FINANCIAL, ORDINARY), False,
       "23.R4's held turns: whatever he said while the brain was unreachable, so it holds "
       "whatever he talks about. Never leaves the host - it is waiting to be answered BY the "
       "host"),
    # ---- Q1.3: the one outbound flow that is not storage -----------------------------------------
    # Declared before 14.R5's first runtime call. Its gate now asserts the live payload stays narrow;
    # widening it later is a classification decision, not an incidental client refactor.
    _s("!typesafe", (MEDICAL, FINANCIAL, ORDINARY), True,
       "the judgment payload: today the current explicit decision question and owner-supplied "
       "options; 14.R6 may later add bounded goal-deviation context. Either can contain medical or "
       "financial material, so strictest=medical and minimisation is obligatory. Never biometric: "
       "speaker and face embeddings are not judgment inputs"),
    # Added 2026-10-10: the setup wizard's own progress file was being written into the state root
    # with no declaration, so the live-root gate flagged it as undeclared. It holds which onboarding
    # steps are done and the answers he gave to them — ordinary, and it never leaves the host.
    _s("wizard-state.json", (ORDINARY,), False,
       "setup-wizard progress: which onboarding steps are done, and the answers given to them"),
)


def strictest(classes: frozenset[str] | set[str] | tuple[str, ...]) -> str:
    """The strictest class in the set â€” what a handling rule must apply."""
    for c in STRICTEST_FIRST:
        if c in classes:
            return c
    return ORDINARY


def classify(name: str) -> Store | None:
    """The declaration for a store name, or None if it is undeclared.

    A ``.bak`` sibling inherits its base declaration. That is a rule and not an exemption: a backup
    of a biometric file is a biometric file, and treating it as undeclared would be wrong in the
    other direction.
    """
    key = (name or "").strip().strip("/\\")
    for store in STORES:
        if store.name == key:
            return store
    if key.endswith(".bak"):
        return classify(key[: -len(".bak")])
    # A TIMESTAMPED backup â€” `mushegh_tasks.sqlite.bak-20261010-111312` â€” is the same thing wearing a
    # date, and it was undeclared until 2026-10-10 when taking one for a residue wipe tripped
    # this gate. A backup is a rule, not an exemption, so the date must not change the class.
    m = re.search(r"\.bak(?:[-_.].*)?$", key)
    if m:
        return classify(key[: m.start()])
    return None


#: Things that appear in the state root but are not stores. Kept short on purpose â€” every addition
#: here is a hole in the gate, so each one has to be something that provably holds no owner data.
_NOT_A_STORE = {"__pycache__", ".ds_store", "thumbs.db", ".gitignore", ".gitkeep"}


def unclassified(root: Path | None = None) -> list[str]:
    """THE GATE â€” every top-level entry in the live state root that has no declaration.

    Discovery-based on purpose: checking the declarations against each other would pass forever
    while a new store appeared beside them.
    """
    if root is None:
        from mushegh.shared.paths import state_dir

        root = state_dir()
    if not root.is_dir():
        return []
    out = []
    for p in sorted(root.iterdir()):
        if p.name.lower() in _NOT_A_STORE:
            continue
        if classify(p.name) is None:
            out.append(p.name)
    return out


def must_not_leave() -> tuple[Store, ...]:
    """Stores that may never cross the network, whatever else changes."""
    return tuple(s for s in STORES if not s.leaves_host)


def summary() -> dict:
    """For the HUD and for `diagnose`: how many stores, by strictest class, and any undeclared."""
    by_class: dict[str, int] = {}
    for s in STORES:
        by_class[s.strictest] = by_class.get(s.strictest, 0) + 1
    undeclared = unclassified()
    return {
        "stores": len(STORES),
        "by_strictest_class": by_class,
        "never_leaves_host": [s.name for s in must_not_leave()],
        "undeclared": undeclared,
        "ok": not undeclared,
    }


if __name__ == "__main__":  # a quick look at the live host
    import json

    print(json.dumps(summary(), indent=2))
    for s in STORES:
        flag = "" if s.leaves_host else "  [NEVER LEAVES]"
        print(f"  {s.strictest:9} {s.name:28} {sorted(s.classes)}{flag}")
