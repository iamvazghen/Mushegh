"""37.R4 — what class of data each store holds, declared before any retention rule is written.

Jev p = 0.95, conf 0.93 — the highest-confidence directive in the whole evaluation:
*classify data first — biometric, financial, medical, ordinary — before writing any retention rule;
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
would pass forever while a new store appeared beside them — which is the failure this whole
directive exists to prevent, and the same shape as the HUD section that was emitted and never drawn
(P1.2).

``leaves_host`` is carried here rather than in prose because it is the one property that has a
standing, absolute rule behind it: **owner biometrics never leave the laptop.** Written as data, it
is checkable; written in a document, it is a promise.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

#: The four classes Jev named. Strictest first — `strictest()` depends on this order, and the order
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
       "the owner's speaker embedding — the thing the speaker gate compares against"),
    _s("faces", (BIOMETRIC,), False,
       "owner.npy, the face embedding used as the confirm tier's second factor"),

    # ---- containers that hold whatever the owner said -----------------------------------------
    _s("memory", (MEDICAL, FINANCIAL, ORDINARY), True,
       "L1 learned facts and L2 journal: his health, his money and his week in the same prose"),
    _s("afon_graph.sqlite", (MEDICAL, FINANCIAL, ORDINARY), True,
       "the memory graph indexes the same prose, so it inherits the same classes"),
    _s("afon_vectors.sqlite", (MEDICAL, FINANCIAL, ORDINARY), True,
       "embeddings of that prose; an embedding is not anonymisation"),
    _s("traces", (MEDICAL, FINANCIAL, ORDINARY), True,
       "turn traces carry prompts, and a prompt carries whatever was being discussed"),
    _s("screenshots", (MEDICAL, FINANCIAL, ORDINARY), True,
       "whatever was on the screen; a container cannot be cleaner than its contents"),

    # ---- specific classes ----------------------------------------------------------------------
    _s("afon_coaching.sqlite", (MEDICAL, ORDINARY), True,
       "wellbeing nudges and habit history, which is health data however gently phrased"),
    _s("afon_stock.sqlite", (FINANCIAL,), True, "holdings and prices"),
    _s("forecasts.jsonl", (FINANCIAL, ORDINARY), True, "predictions, including financial ones"),

    # ---- ordinary operational state ------------------------------------------------------------
    _s("afon_tasks.sqlite", (ORDINARY,), True, "task rows"),
    _s("afon_jobs.sqlite", (ORDINARY,), True, "the APScheduler jobstore"),
    _s("afon_presence.sqlite", (ORDINARY,), True, "which device he is at"),
    _s("afon_work.sqlite", (ORDINARY,), True, "background work rows"),
    _s("afon_session.json", (ORDINARY,), True, "the resumable session pointer"),
    _s("approvals.json", (ORDINARY,), True, "pending approvals — summaries, not payloads"),
    _s("governor.json", (ORDINARY,), True, "the autonomy ledger: counts, money, seconds"),
    _s("relationship.json", (ORDINARY,), True, "interaction style state"),
    _s("room_context.json", (ORDINARY,), True, "who else is in the room"),
    _s("runtime_prefs.json", (ORDINARY,), True, "spoken preference overrides"),
    _s("tool_usage.json", (ORDINARY,), True, "per-tool counts, for reliability"),
    _s("patterns.jsonl", (ORDINARY,), True, "learned routine patterns"),
    _s("delivery_ledger.json", (ORDINARY,), True, "what was already said, so it is not said twice"),
    _s("daily_digest_state.json", (ORDINARY,), True, "the last digest's watermark"),
    # Two files that were on disk in the live state root with no declaration here, which is
    # the exact failure this table exists to prevent: unclassified owner data. `audio_pref.json`
    # is written by the edge audio device picker; `restore_drill.json` is written by the backup
    # restore drill. Both are ordinary operational state and both may leave the host, the same
    # as the other preference and ledger files above them.
    _s("audio_pref.json", (ORDINARY,), True,
       "which speaker he wants Afon to talk through — a device preference, not a biometric"),
    _s("restore_drill.json", (ORDINARY,), True,
       "the last restore drill's verdict; operational history, and the reason a drill is run "
       "at all is to be able to say afterwards whether it would have worked"),
    _s("proactive_state.json", (ORDINARY,), True, "proactivity budget and quiet-hours state"),
    _s("errors.jsonl", (ORDINARY,), True,
       "scrubbed error records; the scrubber is what keeps this class honest"),
    _s("conversation_id", (ORDINARY,), True, "one opaque id"),
    _s("run", (ORDINARY,), True, "pid and lock files"),
    _s("shell", (ORDINARY,), True, "the 04.R4 shell working directory"),
    _s("MAINTENANCE", (ORDINARY,), True, "the park marker — its presence is the whole content"),
    _s("MIGRATED.txt", (ORDINARY,), True, "the 30.F1 migration receipt"),

    # ---- stores outside the state root ---------------------------------------------------------
    _s("!audit", (MEDICAL, FINANCIAL, ORDINARY), True,
       "audit lines carry tool arguments, so they inherit the classes of what was being done"),
    _s("!postgres", (MEDICAL, FINANCIAL, ORDINARY), True,
       "a legacy Postgres directory. The runtime store is SQLite and always was (D-02), but the "
       "classification is kept: a host that ran the staged adapters may still have one on "
       "disk, and unclassified owner data is the failure this table exists to prevent"),
    _s("!vault", (MEDICAL, FINANCIAL, ORDINARY), True,
       "the Obsidian vault on the VPS — decisions, and the life they were about"),
    _s("!env", (ORDINARY,), False,
       "credentials. Not one of the four classes and never in git: secrets are not owner data, "
       "they are access to it"),
    _s("!contacts", (ORDINARY,), False,
       "other people's handles and addresses — his to hold, not his to leak"),
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
)


def strictest(classes: frozenset[str] | set[str] | tuple[str, ...]) -> str:
    """The strictest class in the set — what a handling rule must apply."""
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
    return None


#: Things that appear in the state root but are not stores. Kept short on purpose — every addition
#: here is a hole in the gate, so each one has to be something that provably holds no owner data.
_NOT_A_STORE = {"__pycache__", ".ds_store", "thumbs.db", ".gitignore", ".gitkeep"}


def unclassified(root: Path | None = None) -> list[str]:
    """THE GATE — every top-level entry in the live state root that has no declaration.

    Discovery-based on purpose: checking the declarations against each other would pass forever
    while a new store appeared beside them.
    """
    if root is None:
        from afon.shared.paths import state_dir

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
