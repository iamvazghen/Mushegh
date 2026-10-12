"""The 50 subsystems, as a setup catalogue.

`docs/systems-plan.json` is the project's own registry: 50 systems, each with a
wave, a status and a task list. The wizard did not know about it, which is why
"is my install complete?" could only ever be answered as "are these 8 values
set?" — a much weaker question than the owner actually asks, which is "which of
my fifty subsystems are dark, and why?"

Dark is the important word. Most subsystems here are built and simply have no
credential, so the failure is silent: the code is there, the tool is advertised,
and it declines to do anything. Counting settings is not the same as counting
what works, and this module exists to make the difference visible.

The mapping below is **curated, not derived**. `systems-plan.json` carries no
configuration keys, so there is nothing to derive one from, and guessing a system
to key association would produce a confident and wrong answer — the exact failure
mode this file is meant to prevent. A system with no entry here is reported as
unmapped rather than assumed fine.

Every key named here is checked against the live `settings`, so this reflects the
running install, not what the docs claim.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

PLAN = "docs/systems-plan.json"

#: system id -> the settings fields that decide whether it is actually usable.
#: Ids and titles are taken from docs/systems-plan.json itself, not recalled, because
#: a mapping built from memory produces exactly the confident wrong answer this module
#: exists to avoid — an early draft mapped S05 to speech-to-text and S33 to Google
#: Maps, and both were simply wrong: S05 is Browser Control and S33 is Goal & Project
#: Management. Only systems with a real, nameable configuration dependency appear here.
SYSTEM_SETTINGS: dict[str, tuple[str, ...]] = {
    "S01": ("llm_backend",),                                   # Brain / core intelligence
    "S02": ("freellmapi_api_key", "llm_chain"),                # LLM integration
    "S05": ("browser_tools_enabled",),                         # Browser Control
    "S08": ("speaker_profile_path",),                          # Voice Enrollment
    "S09": ("face_embed_threshold",),                          # Face Enrollment
    "S10": ("speaker_id_enabled", "speaker_threshold"),        # speaker identification
    "S12": ("telegram_phone",),                                # Multi-Device Coordination
    "S13": ("ntfy_topic",),                                    # Notification Management
    "S19": ("mcp_servers",),                                   # Composio / MCP Integration
    "S20": ("composio_api_key", "tavily_api_key", "brave_api_key", "jina_api_key"),
    "S24": ("memory_enabled",),                                # Knowledge & World Model
    "S26": ("vision_chain", "vision_models"),                 # Multi-Modal Perception
    "S28": ("composio_user_id",),                              # IoT orchestration
    "S30": ("memory_enabled", "memory_semantic_enabled"),      # Persistent Memory
    "S33": ("objectives_enabled",),                            # Goal & Project Management
    "S34": ("speaker_id_enabled",),                            # Health & Wellness
    "S37": ("memory_enabled",),                                # Privacy & Data Governance
    "S38": ("telegram_bot_token",),                            # Communication Hub
    "S39": ("openclaw_gateway_url", "openclaw_token"),         # Multi-Agent Delegation
    "S40": ("vault_path",),                                    # Financial & Asset Management
    "S41": ("bookroom_llm_api_key",),                          # Research & Synthesis
    "S42": ("music_source",),                                  # Media & Entertainment
    "S47": ("memory_enabled",),                                # Inventory & Resource
    # Systems whose gate is a genuinely REQUIRED value. Optional hints are deliberately
    # not mapped: `device_hint` defaults to None and means "work it out yourself", so
    # mapping it would report Device Control as dark on a perfectly working install.
    "S11": ("face_match_threshold", "face_second_factor"),      # Face Recognition
    "S14": ("proactive_enabled",),                              # Proactivity Engine
    "S17": ("task_briefing_time",),                            # Morning Brief
    "S18": ("audio_output_device",),                           # Mic & Speaker Management
    "S25": ("persona_file",),                                  # Personality & Interaction
    "S35": ("emergency_contacts_path",),                       # Crisis & Emergency
    "S36": ("protocols_enabled", "protocol_goodnight_password", "protocol_backup_password"),
    "S43": ("presence_engaged_idle_seconds",),                 # Presence & Continuity
    "S23": ("brain_host", "brain_port"),                        # 24/7 Reachability
}

#: Finished code with nothing to configure — reported plainly rather than as a gap.
BUILTIN_SYSTEMS: frozenset[str] = frozenset({
    "S03",   # Tool Utilization — the belt is always registered
    "S04",   # Device Control — devices are detected; `device_hint` is only a hint
    "S06",   # Document Creation — works against the vault
    "S07",   # Session & Context Management
    "S16",   # Task Queue — the DB path is derived from the state dir when unset
    "S21",   # Personal Time Management
    "S22",   # System Recoverability — backups run from the task scheduler
    "S27",   # Contextual Awareness
    "S29",   # Automation & Workflow Engine — macros
    "S31",   # Self-Monitoring, Diagnostics & Self-Healing
    "S32",   # Redundancy & Failover
    "S44",   # Ethical Reasoning, Safety & Alignment
    "S45",   # Explainability & Transparency
    "S48",   # Collaborative Multi-Agent Coordination — one-way; the fleet is S39
    "S50",   # Legacy Continuity & Knowledge Preservation
})

#: Status text that means the owner decided this one is gone. The registry already
#: says so; re-deriving it keeps `doctor` honest instead of listing a retired system
#: as a gap to fix.
_RETIRED = re.compile(r"removed|dropped|cancelled|no open tasks", re.I)


@dataclass
class SystemView:
    """One system as the installer should describe it."""

    id: str
    title: str
    wave: str
    status: str
    configured: bool
    detail: str = ""
    missing: tuple[str, ...] = field(default_factory=tuple)

    @property
    def state(self) -> str:
        if self.detail:
            return "dark"
        if not self.configured:
            return "builtin" if self.id in BUILTIN_SYSTEMS else "unmapped"
        return "ready"


def _plan_path() -> Path:
    return Path(__file__).resolve().parents[2] / PLAN


@lru_cache(maxsize=1)
def load_plan() -> list[dict]:
    """The 50 systems. An unreadable plan yields an empty list, not a crash —
    `doctor` must still be able to report on the live settings."""
    try:
        data = json.loads(_plan_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    systems = data.get("systems")
    return systems if isinstance(systems, list) else []


def _settings():
    from mushegh.config import settings
    return settings


def _is_set(value) -> bool:
    if isinstance(value, bool):
        return True          # a deliberate False is a configured choice, not a gap
    if value is None:
        return False
    return bool(str(value).strip())


def system_views() -> list[SystemView]:
    """Every system, with whether its own dependencies are actually satisfied."""
    s = _settings()
    views: list[SystemView] = []
    for entry in load_plan():
        sid = str(entry.get("id") or "").strip()
        if not sid:
            continue
        status = str(entry.get("status") or "").strip()
        title = str(entry.get("title") or sid)
        # Retired by the owner's own decision. Not a gap, and not something the wizard
        # should keep offering to configure.
        if _RETIRED.search(status):
            views.append(SystemView(sid, title, str(entry.get("wave") or "?"),
                                    status[:80], configured=True))
            continue
        keys = SYSTEM_SETTINGS.get(sid)
        if not keys:
            views.append(SystemView(sid, title, str(entry.get("wave") or "?"),
                                    status[:80], configured=False, detail=""))
            continue
        missing = tuple(k for k in keys if not _is_set(getattr(s, k, None)))
        views.append(SystemView(
            sid, title, str(entry.get("wave") or "?"), status[:80],
            configured=not missing,
            detail="needs: " + ", ".join(missing) if missing else "",
            missing=missing,
        ))
    return views


def summary() -> dict[str, int]:
    """Counts by state — the one line `doctor` leads with."""
    counts: dict[str, int] = {}
    for view in system_views():
        counts[view.state] = counts.get(view.state, 0) + 1
    return counts


def dark_systems() -> list[SystemView]:
    """Subsystems that are built but cannot run because a value is missing."""
    return [v for v in system_views() if v.state == "dark"]


# --------------------------------------------------------------------------
# Turning "dark" into something the wizard can actually fix.
#
# A readiness report that only says "S20 is dark" leaves the owner to open an
# editor and guess the variable name. This turns each dark subsystem into an
# ordered, named prompt set so `mushegh wizard` can close the gap rather than
# describe it.

#: setting -> what to call it and where the owner gets it. Only settings that
#: appear in SYSTEM_SETTINGS need an entry; a missing one falls back to the raw
#: name rather than inventing a description.
SETTING_PROMPTS: dict[str, tuple[str, str]] = {
    "speaker_profile_path": ("Voice profile", "Run `bench/enroll_voice.py` to create it."),
    "telegram_phone": ("Phone number", "Your Telegram phone number, for placing calls."),
    "brave_api_key": ("Brave Search key", "brave.com/search/api — free tier, used for web search."),
    "composio_user_id": ("Composio user id", "app.composio.dev — required alongside the API key."),
    "bookroom_llm_api_key": ("Bookroom LLM key", "Any OpenAI-compatible key; summarises your own books."),
    "telegram_bot_token": ("Telegram bot token", "From @BotFather."),
    "ntfy_topic": ("ntfy topic", "Pick an unguessable string — it is your push endpoint."),
    "notion_token": ("Notion token", "Notion integrations → your internal integration secret."),
    "jina_api_key": ("Jina key", "jina.ai — renders JS pages to Markdown when reading a URL."),
    "tavily_api_key": ("Tavily key", "tavily.com — search with citations."),
    "composio_api_key": ("Composio API key", "app.composio.dev/settings/api-keys."),
    "vault_path": ("Vault folder", "Your Obsidian/Markdown folder — long-term memory."),
    "freellmapi_api_key": ("LLM API key", "Key for your own reasoning model."),
    "llm_chain": ("Model chain", "Comma-separated, most-preferred first."),
    "browser_tools_enabled": ("Browser control", "Leave on unless you want it fully off."),
    "speaker_id_enabled": ("Speaker ID", "Only your voice is answered."),
    "speaker_threshold": ("Speaker threshold", "0.0-1.0; lower accepts more, higher is stricter."),
    "face_embed_threshold": ("Face threshold", "0.0-1.0 for owner recognition."),
    "memory_enabled": ("Persistent memory", "Learning and recall across sessions."),
    "memory_semantic_enabled": ("Semantic recall", "Embedding-based recall rather than keyword only."),
    "objectives_enabled": ("Objectives", "Multi-day goals Mushegh drives toward."),
    "music_source": ("Music source", "ytmusic, telegram, or youtube."),
    "vision_chain": ("Vision chain", "Ordered list of models for looking at things."),
    "vision_models": ("Vision models", "Which model answers a visual question."),
    "mcp_servers": ("MCP servers", "JSON list of external tool servers."),
    "llm_backend": ("LLM backend", "The engine that does the thinking."),
}


@dataclass
class WizardStep:
    """One dark subsystem, reduced to the keys it is actually waiting on."""

    key: str            # stable id, used for resume
    system_id: str
    title: str
    settings: tuple[str, ...]

    def prompt_for(self, name: str) -> tuple[str, str]:
        return SETTING_PROMPTS.get(name, (name.replace("_", " ").capitalize(), ""))


def wizard_steps() -> list[WizardStep]:
    """Ordered steps for every dark subsystem, soonest-gap first.

    Sorted by how many keys a system is missing so the cheapest wins come first:
    a subsystem blocked on one value is a two-minute fix, and finishing those
    first means an interrupted wizard still leaves the owner better off.
    """
    steps = [
        WizardStep(key=v.id, system_id=v.id, title=v.title, settings=v.missing)
        for v in dark_systems()
    ]
    steps.sort(key=lambda s: (len(s.settings), s.system_id))
    return steps