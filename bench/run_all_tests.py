"""One command to verify Mushegh works end-to-end.

    uv run python bench/run_all_tests.py

Runs every check in order and prints a single PASS/FAIL summary. Tests are tagged:

  [offline]  — deterministic, no network (config, VAD, barge-in, wake-word perf)
  [network]  — needs the freellmapi proxy reachable (Mushegh's brain LLM); reported as
               SKIP (not FAIL) if the proxy is unreachable, so an offline run still passes
  [gated]    — the OpenClaw fleet connect, intentionally blocked until a sanctioned path
               is enabled; reported as SKIP

Exit code is non-zero only if a runnable test actually fails.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable

# (label, script, tag, success_substrings) — a test passes if exit==0 AND every
# required substring appears in its output (empty list = exit code only).
TESTS = [
    ("config loads + secrets present", "check_config.py", "offline", ["elevenlabs_api_key  : set"]),
    ("Aggregate runner: network skip classification", "test_run_all_tests_classifier.py", "offline",
     ["checks passed ==="]),
    ("Phase 1: VAD + barge-in", "test_phase1_vad_bargein.py", "offline", ["checks passed ==="]),
    ("Turn assembly: text+quiet beats a fixed silence timer for local STT", "test_turn_assembly.py",
     "offline", ["checks passed ==="]),
    ("Outbound URL guard: refuse internal + metadata targets; tools consult it", "test_netguard.py",
     "offline", ["checks passed ==="]),
    ("Unattended worker: report a raised tool as failed, never as used", "test_worker_progress.py",
     "offline", ["checks passed ==="]),
    ("Live transit (DB + KVB, keyless): delay wording, platforms, journey shape, cancellations",
     "test_transit.py", "offline", ["checks passed ==="]),
    ("Named places + JSON contacts: 'home'/'the gym' resolve; ambiguity is refused, not guessed",
     "test_places_and_contacts.py", "offline", ["checks passed ==="]),
    ("Subsystem ledger: all 50 mapped honestly — no phantom settings, no orphan ids, unmapped != ready",
     "test_subsystems.py", "offline", ["checks passed ==="]),
    ("Phase 3: knowledge & channel tools + per-agent delegation", "test_phase3_tools.py", "offline",
     ["checks passed ==="]),
    ("Phase 4 + system/browser/protocols", "test_phase4_system_protocols.py", "offline",
     ["checks passed ==="]),
    ("wake word: faster than realtime", "test_wakeword.py", "offline", ["wake word ready"]),
    ("audio watchdog: recover a dead mic/speaker after a device change", "test_audio_watchdog.py",
     "offline", ["checks passed ==="]),
    ("Phase 5: speaker biometrics + TTFW/VAQI", "test_phase5_identity_bench.py", "offline",
     ["checks passed ==="]),
    ("Speaker gate: identify the UTTERANCE, not the 6s window around it (score quality + turn cost)",
     "test_speaker_gate_scoping.py", "offline", ["checks passed ==="]),
    ("Speaker verifier lifecycle: warm off the boot path without failing OPEN; voiceprint out of the repo",
     "test_speaker_warmup.py", "offline", ["checks passed ==="]),
    ("Phase 6: multi-device (edge-lite + device routing)", "test_phase6_multidevice.py", "offline",
     ["checks passed ==="]),
    ("Android Termux edge-lite: push-to-talk loop (mic->STT->brain->TTS), off-device", "test_edge_lite.py",
     "offline", ["checks passed ==="]),
    ("iPhone mic-over-HTTPS client: self-contained, token-gated, /talk wiring", "test_iphone_client.py",
     "offline", ["checks passed ==="]),
    # Needs a reachable LLM (the shared brain answers a real turn) — tagged network so a dev box
    # with no LLM SKIPs it cleanly instead of a false red; on the VPS it runs and must pass.
    ("Phase 6: brain WS server (phone/glasses -> shared brain)", "test_phase6_brain_server.py",
     "network", ["checks passed ==="]),
    ("Phase 9: persistent memory (learned facts + journal)", "test_phase9_memory.py", "offline",
     ["checks passed ==="]),
    ("Phase 9b: L4 hot-cache (in-process TTL)", "test_phase9b_cache.py", "offline",
     ["checks passed ==="]),
    ("Phase 9c: L5 semantic recall (graceful embedder)", "test_phase9c_semantic.py", "offline",
     ["checks passed ==="]),
    ("D-13: physical door locks refuse outright, with no confirmation path that opens one (28.R4)",
     "test_blast_radius_refusal.py", "offline", ["ALL CHECKS PASSED ==="]),
    ("D-07: a browser op that could commit a form confirms; reading a page does not (05.R1)",
     "test_browser_submit_confirm.py", "offline", ["ALL CHECKS PASSED ==="]),
    ("D-79/D-80: one contract for every external executor — no credentials to the child, no "
     "non-zero exit reading as success, no arbitration outside the candidates (M41)",
     "test_executor_contract.py", "offline", ["ALL CHECKS PASSED ==="]),
    ("D-79: a brief is assembled by code from a task record, and an acceptance check that "
     "restates the task is refused (M46)",
     "test_brief_assembly.py", "offline", ["ALL CHECKS PASSED ==="]),
    ("D-05/D-84: the OpenClaw transport is the official CLI with the task in a file, never a "
     "shell, and never passes --deliver (M42)",
     "test_fleet_transport.py", "offline", ["ALL CHECKS PASSED ==="]),
    ("D-73/D-76/D-81: Jev picks the executor from the ballot code built, and an outage keeps the "
     "deterministic choice silently (M45)",
     "test_executor_arbitration.py", "offline", ["ALL CHECKS PASSED ==="]),
    ("D-08/D-80: a delegated coding change cannot become a commit without all four conditions, "
     "and a refused approval leaves the owner's checkout untouched (M43)",
     "test_coding_delegation.py", "offline", ["ALL CHECKS PASSED ==="]),
    ("D-86: the Bookroom summarizer is reachable, an unpriced book is never summarised, and "
     "quality is reported honestly",
     "test_bookroom_tool.py", "offline", ["ALL CHECKS PASSED ==="]),
    ("D-88/D-89: the toolchain updates itself, proves each update with a ping, rolls a bad "
     "release back, and the weekly Jev review installs nothing",
     "test_toolchain.py", "offline", ["ALL CHECKS PASSED ==="]),
    ("Persistent vector store: L5 embeddings survive restart (sqlite)", "test_vector_store.py",
     "offline", ["checks passed ==="]),
    ("S30 staged migration is gone (M02): no scaffolding, no DSN, no psycopg — and the backup "
     "path that replaced the snapshot helper still round-trips",
     "test_s30_migration_removed.py", "offline", ["ALL CHECKS PASSED ==="]),
    ("Local voice is the default (18.R4): TTS builds with no key, cloud is an explicit opt-in, "
     "and a local primary that cannot build degrades instead of dying",
     "test_tts_local_default.py", "offline", ["ALL CHECKS PASSED ==="]),
    ("No unprompted content feed (41.R4): the news source is not collected, the seam carries no "
     "import of it, and the engine ticks a stubbed registry rather than the live one",
     "test_no_unprompted_feed.py", "offline", ["ALL CHECKS PASSED ==="]),
    ("Wake word is on-device (18.R5): the two dead settings are gone, the module cannot reach the "
     "network, and every configured phrase is reported loadable-or-pending",
     "test_wakeword_offline.py", "offline", ["ALL CHECKS PASSED ==="]),
    ("The never-store set is enforced (37.R5): all four D-24 classes are refused at the write "
     "boundary, the audit trail withholds the payload instead of recording it, and there is no "
     "override to reach past any of it",
     "test_never_store.py", "offline", ["passed, 0 failed"]),
    ("No video frame leaves the house (26.R5): the detector channel carries metadata or nothing, "
     "events still arrive with egress blocked, see() is not on the path, and neither a log nor a "
     "crash report can hold frame bytes",
     "test_no_frame_egress.py", "offline", ["passed, 0 failed"]),
    ("The ear is chosen per turn (18.R7): the language the fast ear cannot hear moves the next "
     "turn to the local one, a short turn cannot swap it, and the refuted predictive design's "
     "measured cost stays on the record",
     "test_stt_by_language.py", "offline", ["passed, 0 failed"]),
    ("The elite scorecard measures the brain (01.E1/E2, D-44): an unconfigured scenario is skipped "
     "rather than scored, the overall states its basis, underpowered categories are excluded, and "
     "the per-turn scoring bands are unchanged so nothing was loosened",
     "test_scorecard_integrity.py", "offline", ["passed, 0 failed"]),
    ("The audit trail is verifiable (45.R10): every line chains to the one before it, an edited, "
     "removed, reordered or spliced line is found by a reader that needs no framework, and the "
     "limits that are NOT detected are asserted rather than implied",
     "test_audit_integrity.py", "offline", ["passed, 0 failed"]),
    ("A past turn can be reconstructed (45.R3): the decision is replayed in full and joined to its "
     "tool calls on turn_id, the three things a replay CANNOT show are named rather than left blank, "
     "and a tampered turn is explained and flagged in the same breath",
     "test_decision_replay.py", "offline", ["passed, 0 failed"]),
    ("A stalled delegation comes back (39.R2): a timeout is NOT an outage, so the task is never "
     "re-sent over the CLI, the breaker is not tripped, and the outage path still recovers",
     "test_fleet_takeback.py", "offline", ["passed, 0 failed"]),
    ("A failure is described accurately (02.E1): an exhausted chain, a single model going quiet and "
     "a bug in Mushegh are three different sentences, and a bug is never blamed on the models",
     "test_outage_audible.py", "offline", ["passed, 0 failed"]),
    ("The catalogue router is MEASURED (03.R1 + 03.R7): 60 hand-written prompts reach the right "
     "group, narrowing measurably beats the 19k full surface, and the triggers that mis-fired are "
     "gone",
     "test_catalogue_narrowing.py", "offline", ["passed, 0 failed"]),
    ("The acceptance rate is a number with a definition (14.R1): strict and lenient are both "
     "reported because silence is not a refusal, a cold start is 0.0 and not 1.0, and quoting a "
     "rate moves no threshold",
     "test_acceptance_rate.py", "offline", ["passed, 0 failed"]),
    ("One fact is one hit (30.R1): the same fact from two memory layers collapses to one and names "
     "the layers, while two DISAGREEING facts are deliberately not merged",
     "test_memory_dedup.py", "offline", ["passed, 0 failed"]),
    ("The weekly self-report answers all three questions (31.R3): what broke, what self-repaired "
     "and what needs the owner — and a section it cannot measure is SPOKEN as unknown, never "
     "rendered as all-clear",
     "test_self_report.py", "offline", ["passed, 0 failed"]),
    ("weather: 'tomorrow'/'this week' answer the day asked for, not today (H2.11)",
     "test_weather_when.py", "offline", ["checks passed ==="]),
    ("if_then: the parsed comparison operator is actually applied (H2.12)",
     "test_if_then_operator.py", "offline", ["checks passed ==="]),
    ("Vault search (L3): cache never serves stale text, never holds the loop, warms to reachable",
     "test_vault_search.py", "offline", ["checks passed ==="]),
    ("Phase 10: proactive engine (budget/quiet-hours/clarify-confirm)", "test_phase10_proactive.py",
     "offline", ["checks passed ==="]),
    ("Phase 0 companion: activity/presence tracking + persistent proactive state (no re-fire)",
     "test_presence.py", "offline", ["checks passed ==="]),
    ("Phase 1 companion: context-gated proactivity + dismissal-learning feedback loop",
     "test_proactive_learning.py", "offline", ["checks passed ==="]),
    ("Tool usage: per-tool call counts survive a restart (input to catalogue tiering)",
     "test_tool_usage.py", "offline", ["passed, 0 failed"]),
    ("Proactive suppression counters: 'restrained' is distinguishable from 'never generated'",
     "test_proactive_suppression.py", "offline", ["passed, 0 failed"]),
    ("Screenshot transport: capture on laptop, read on brain (VPS-split fix)",
     "test_screenshot_transport.py", "offline", ["checks passed ==="]),
    ("Phase 2 companion: field coaching (skill reviews/level/streak) + evening offer",
     "test_coaching.py", "offline", ["checks passed ==="]),
    ("Phase 3 companion: task co-pilot (clarify/plan/confirm/execute via worker or fleet)",
     "test_copilot.py", "offline", ["checks passed ==="]),
    ("Phase 4 companion: conflict-only interventions (pause media on a real imminent commitment)",
     "test_interventions.py", "offline", ["checks passed ==="]),
    ("Memory RAG: auto-recall per turn + un-frozen learned digest", "test_memory_autorecall.py",
     "offline", ["checks passed ==="]),
    ("Memory review learning: one call yields facts and relations, L5 semantic default on",
     "test_memory_review_learn.py", "offline", ["checks passed ==="]),
    ("Memory behavioral trace: each layer engages at the right moment through the agent",
     "test_memory_behavioral.py", "offline", ["checks passed ==="]),
    ("Phase 11: Gmail/Calendar/Home-Assistant (graceful degradation)",
     "test_phase11_integrations.py", "offline", ["checks passed ==="]),
    ("Phase 11: Notion (read/write/comment, graceful)", "test_phase11_notion.py", "offline",
     ["checks passed ==="]),
    ("Phase 12: utilities belt (weather/crypto/fx/convert/…)", "test_phase12_utility.py",
     "offline", ["checks passed ==="]),
    ("Phase X: audit log + self-health + modes/routines", "test_phasex_audit_health_modes.py",
     "offline", ["checks passed ==="]),
    ("Phase 13: coding tools + git safety + skills", "test_phase13_coding.py",
     "offline", ["checks passed ==="]),
    ("Local audio plays on the LAPTOP (the VPS has ffplay too — it just has no speakers)",
     "test_localplay_routing.py", "offline", ["checks passed ==="]),
    ("'Read this file' means the OWNER's disk: laptop reads the bytes, brain parses them",
     "test_documents_routing.py", "offline", ["checks passed ==="]),
    ("'Switch to my headphones' exists AND re-routes the live stream (not just a saved setting)",
     "test_audio_output_switch.py", "offline", ["checks passed ==="]),
    ("Tool failures speak in his voice and stay detectable as failures (not raw exception names)",
     "test_tool_error_handling.py", "offline", ["checks passed ==="]),
    ("Errors logged while the brain link is DOWN still reach it (spool + replay on reconnect)",
     "test_error_spool.py", "offline", ["checks passed ==="]),
    ("A brain-side protocol's report reaches the OWNER, not just the brain's disk",
     "test_protocol_reports.py", "offline", ["checks passed ==="]),
    ("Face as a second factor on privileged actions — adds refusals, never locks the owner out",
     "test_face_second_factor.py", "offline", ["checks passed ==="]),
    ("Fine-tuning: lean prompt + per-turn tool surface + fast primary", "test_finetune.py",
     "offline", ["checks passed ==="]),
    ("Latency regression guard: config invariants + TTFW/VAQI floor", "test_latency_guard.py",
     "offline", ["checks passed ==="]),
    ("M13 latency METHOD: the 30-utterance corpus per device exists, is diverse, and its budgets "
     "match D-35. Explicitly NOT a measurement — no end-to-end number has been taken",
     "test_latency_method.py", "offline", ["checks passed ==="]),
    ("Uptime watcher: edge-triggered outage alert (no repeat spam)", "test_uptime_watch.py",
     "offline", ["checks passed ==="]),
    ("Phase 0.1: active self-repair + escalate-on-sustained-red (reliability probe acts, not just logs)",
     "test_self_repair.py", "offline", ["checks passed ==="]),
    ("Phase 0.2: RemoteBrain warm local standby (VPS SPOF — local agent answers during an outage)",
     "test_warm_standby.py", "offline", ["checks passed ==="]),
    ("Phase 0.3: dead-man's switch (one remote restart per outage + edge-triggered alert)",
     "test_deadmans_switch.py", "offline", ["checks passed ==="]),
    ("Phase 2.1: owner world-model (durable goals/projects/deadlines the anticipation engine reasons from)",
     "test_world_model.py", "offline", ["checks passed ==="]),
    ("Phase 2.3: reasoned anticipation (world-model -> LLM -> one timely Signal; throttled, fail-quiet)",
     "test_anticipation.py", "offline", ["checks passed ==="]),
    ("Phase 1.5: proper-noun STT biasing (hotwords from identity+contacts+config -> Whisper/Deepgram)",
     "test_proper_nouns.py", "offline", ["checks passed ==="]),
    ("Phase 3.1: vision — see() image-message + failover + describe_screen w/ OCR degradation",
     "test_vision.py", "offline", ["checks passed ==="]),
    ("Phase 3.2/3.3: camera — look_around (VLM) + visual_presence (local face detection), graceful",
     "test_camera.py", "offline", ["checks passed ==="]),
    ("Phase 3.3+: owner face recognition (local LBP histograms) — enroll/recognise/reject, hermetic",
     "test_face_recognition.py", "offline", ["checks passed ==="]),
    ("Face identity: the signature must respond to LAYOUT, and a burst must VOTE (not accept on one)",
     "test_face_identity_separation.py", "offline", ["checks passed ==="]),
    ("Face ArcFace backend: real embeddings when available, LBP fallback when not — never mixed",
     "test_face_arcface_backend.py", "offline", ["checks passed ==="]),
    ("Face liveness (11.F3): a photograph propped at the camera withdraws the second factor",
     "test_face_liveness.py", "offline", ["checks passed ==="]),
    ("Ops scripts (J4.4): the deploy parses, its gates stay in order, the restart stays LAST",
     "test_ops_scripts.py", "offline", ["checks passed ==="]),
    ("Deploy prune (H2.13): --prune removes stale code on the brain, and refuses everything else",
     "test_deploy_prune.py", "offline", ["checks passed ==="]),
    ("Skill docs (J4.6/J4.7): no doc may name a tool Mushegh cannot call — it fails silently mid-turn",
     "test_skill_docs_resolve.py", "offline", ["checks passed ==="]),
    ("Roadmap docs (J5.1): one canonical roadmap, and no doc cites a path that isn't in the tree",
     "test_doc_paths.py", "offline", ["checks passed ==="]),
    ("Docs site: no page claims a setting nothing reads, a file that is not there, or a tool count "
     "the registry disagrees with (SKIPs when website/ is absent)",
     "test_website_claims.py", "offline", ["checks passed ==="]),
    ("Layering (J8.4): base layers import nothing upward, edge<->brain crossings are declared, no cycles",
     "test_layering.py", "offline", ["checks passed ==="]),
    ("Source compiles: every file under src/ is valid UTF-8 and parses, so a broken module "
     "cannot hide behind a gate that skips it",
     "test_source_compiles.py", "offline", ["passed, 0 failed"]),
    ("Routing manifest (J8.2): the dispatch tables reach the graph, and a rebuild can't drop them",
     "test_routing_manifest.py", "offline", ["checks passed ==="]),
    ("Graph prune (J0.2): inferred edges are grounded, and none resolves to a file nobody imports",
     "test_graph_prune.py", "offline", ["checks passed ==="]),
    ("Cohesion baseline (J8.1): the gate measures graphify's own metric, and a re-cluster isn't a regression",
     "test_cohesion_baseline.py", "offline", ["checks passed ==="]),
    ("Systems plan: 50 sections, a gate on every task, and a scoreboard that matches the checkboxes",
     "test_systems_plan.py", "offline", ["checks passed ==="]),
    ("Composio context (J3.8): memoise the lookup on success, retry it on failure",
     "test_composio_context_cache.py", "offline", ["checks passed ==="]),
    ("Camera routing (J3.9): one frontal detector, and the burst/single choice is not accidental",
     "test_camera_routing.py", "offline", ["checks passed ==="]),
    ("Health coverage (J3.7): the healthy sentence names what it checked, and never overclaims",
     "test_health_coverage.py", "offline", ["checks passed ==="]),
    ("README claims (J5.2): the feature tour cannot advertise a capability Mushegh does not have",
     "test_readme_claims.py", "offline", ["checks passed ==="]),
    ("Chain exhaustion (J7.2): a domain type for 'every model refused', and the harness agrees on it",
     "test_llm_chain_exhausted.py", "offline", ["checks passed ==="]),
    ("Client endpoints (J4.5): the browser clients and the brain agree on route, verb and auth",
     "test_client_endpoints.py", "offline", ["checks passed ==="]),
    ("Tool-result ceiling (J1.4): one tool that forgets to bound its output cannot cost the turn",
     "test_tool_result_ceiling.py", "offline", ["checks passed ==="]),
    ("Park switch: a parked deployment stays parked — every entry point honours the lock",
     "test_maintenance_lock.py", "offline", ["checks passed ==="]),
    ("Context object (27.F1/27.F2): one situation per turn, and he says which one he assumed",
     "test_context_object.py", "offline", ["checks passed ==="]),
    ("Perception snapshot (26.F2/26.F3): one sensing view, and no fact can pretend to be newer",
     "test_perception_snapshot.py", "offline", ["checks passed ==="]),
    ("Session identity (07.F1/07.F2): a conversation has a name, and the trim summarises what it drops",
     "test_session_identity.py", "offline", ["checks passed ==="]),
    ("Reference resolution (07.F3): twenty cases for 'it', 'that' and 'the second one'",
     "test_reference_resolution.py", "offline", ["checks passed ==="]),
    ("Delivery ledger (13.F3): delivered is not seen, and an urgent miss is re-raised once",
     "test_delivery_ledger.py", "offline", ["checks passed ==="]),
    ("Smart-home read-back (28.F2/28.F3): the observed state, and shared spaces confirm first",
     "test_smarthome_verify.py", "offline", ["checks passed ==="]),
    ("API policy (20.F3): one declared table of timeouts and retries, and nothing bypasses it",
     "test_api_policy.py", "offline", ["checks passed ==="]),
    ("Unified inbox (38.F2/38.F3): one 'what's waiting' across channels, and drafts read back",
     "test_unified_inbox.py", "offline", ["checks passed ==="]),
    ("Citations (41.F2/41.F3): a source he names is one he opened, and a spent budget says so",
     "test_citations.py", "offline", ["checks passed ==="]),
    ("Refusal grades (44.F4): refuse / confirm / proceed-with-note, strongest first",
     "test_refusal_grades.py", "offline", ["checks passed ==="]),
    ("Why (45.F3): the last answer explains itself from the record, not from the model",
     "test_why_last_turn.py", "offline", ["checks passed ==="]),
    ("Data inventory (37.F1): every store declared, and an undeclared one fails the build",
     "test_data_inventory.py", "offline", ["checks passed ==="]),
    ("Right to forget (37.F3): forget sweeps four stores, then re-queries to prove it",
     "test_right_to_forget.py", "offline", ["checks passed ==="]),
    ("Delegation tracking (39.F2/39.F3): nothing handed off untracked, nothing back unchecked",
     "test_delegation_tracking.py", "offline", ["checks passed ==="]),
    ("Coordination (48.F1-F3): one owner per unit, and disagreement surfaced not averaged",
     "test_coordination.py", "offline", ["checks passed ==="]),
    ("Document creation (06.F1/06.F2): one creation path, read back before it says done",
     "test_document_create.py", "offline", ["checks passed ==="]),
    ("Emergency path (35.F1/35.F2): deterministic, ahead of the model, contacts off disk",
     "test_emergency_path.py", "offline", ["checks passed ==="]),
    ("Portable export (50.F1): plain markdown and JSON, read back with no codebase at all",
     "test_portable_export.py", "offline", ["checks passed ==="]),
    ("Inventory (47.F1-F3): one table, dated consumption, and unknown stays unknown",
     "test_inventory.py", "offline", ["checks passed ==="]),
    ("Forecast (46.F1-F3): one predictor, scored against the naive baseline, silent below the floor",
     "test_forecast.py", "offline", ["checks passed ==="]),
    ("Recommendations (15.F1-F3): a reason that cites its data, and a refusal to invent taste",
     "test_recommend.py", "offline", ["checks passed ==="]),
    ("Portfolio (40.F1-F3): a plain-text ledger, valued with as-of times, and no way to move money",
     "test_portfolio.py", "offline", ["checks passed ==="]),
    ("Degraded modes (32.F3): three declared modes, one table, announced once in and once out",
     "test_degraded_modes.py", "offline", ["checks passed ==="]),
    ("Goal attribution (33.F3): every task names the objective it serves, or is ad-hoc",
     "test_goal_attribution.py", "offline", ["checks passed ==="]),
    ("Day shape (21.F1/21.F2): routines drafted from evidence, and a broken day named",
     "test_day_shape.py", "offline", ["checks passed ==="]),
    # 21.F3 — replays the clock-sensitive tests across 6 awkward dates and 4 timezones. It was
    # manual-only until 2026-09-12, and a gate nobody runs is not a gate: registering it caught a
    # real bug the same day. ~60s, parallel; the cost is process startup, not the tests.
    ("Clock robustness (21.F3): the date-sensitive tests replayed across 6 days, 4 timezones and "
     "2 times of day",
     "check_date_robustness.py", "offline", ["no clock-dependent failures"]),
    ("Health agreement (J3.6): when a component is broken, no surface reports it healthy",
     "test_health_agreement.py", "offline", ["checks passed ==="]),
    ("Error taxonomy (J7.3): WHY a tool failed is a value, not a sentence to grep",
     "test_error_taxonomy.py", "offline", ["checks passed ==="]),
    ("Fire paths (J2.8): every autonomous job REPORTS what it did — none may go silent",
     "test_fire_paths_report.py", "offline", ["checks passed ==="]),
    ("Loop registry (31.F4): no background loop runs unseen — period, budget, kill switch, HUD",
     "test_loop_registry.py", "offline", ["checks passed ==="]),
    ("RSS ceiling (31.F6): the brain's memory budget is a MEASURED figure with stated headroom, "
     "not the 250 MB guess it replaces",
     "test_rss_ceiling.py", "offline", ["checks passed ==="]),
    ("Unpark gate (23.F4): leaving the park refuses while any Wave-0 floor is unmet",
     "test_unpark_gate.py", "offline", ["checks passed ==="]),
    ("Jev call budget (01.J1): a turn the router already resolves to one argument-less tool "
     "spends no decision call — and everything else still asks",
     "test_jev_call_budget.py", "offline", ["checks passed ==="]),
    ("Jev arbitration cap: the 400 ms budget is a configured number, and no other gate read it "
     "until this one did",
     "test_jev_arbitration_cap.py", "offline", ["checks passed ==="]),
    ("Constant contracts (01.J14): six shipped numbers — the governor's call ceiling among them — "
     "that stayed green through every mutation, now read directly",
     "test_constant_contracts.py", "offline", ["checks passed ==="]),
    ("Provider cooldown (02.F3): provider health is learned from failures, and the HUD says so",
     "test_provider_cooldown.py", "offline", ["checks passed ==="]),
    ("Languages: six understood, the spoken one identified, and the reply matched to it",
     "test_languages.py", "offline", ["checks passed ==="]),
    ("Protocol utility: all 8 protocols do the thing they claim, not just pass the password gate",
     "test_protocol_utility.py", "offline", ["checks passed ==="]),
    ("Static correctness: undefined names / redefinitions fail at lint time, not at 03:00 Sunday",
     "test_static_correctness.py", "offline", ["checks passed ==="]),
    ("Phase 3: presence-aware proactivity — greet-on-arrival (idle transition, privacy gate)",
     "test_presence_arrival.py", "offline", ["checks passed ==="]),
    ("LLM: MiniMax <think> stripping — reasoning primary never speaks chain-of-thought (streamed)",
     "test_think_strip.py", "offline", ["checks passed ==="]),
    ("Phase 4.1: multi-day objectives — assign/drive/advance one safe step/report, deferred approvals",
     "test_objectives.py", "offline", ["checks passed ==="]),
    ("Phase 4.2: approval queue — deferred outward steps become approvable; worker can't self-approve",
     "test_approvals.py", "offline", ["checks passed ==="]),
    ("Fleet routing: the agent is named and checked against the 18-agent roster, or refused",
     "test_fleet_fastpath.py", "offline", ["checks passed ==="]),
    ("Fleet transport: A2A to the 9 OpenClaw agents, hermes -z to the 9 profiles",
     "test_a2a_transport.py", "offline", ["offline ok:"]),
    ("Coding pipeline: Claude Code -> mcode -> vibe on failure; frontend goes to Open Design",
     "test_coding_chain.py", "offline", ["ALL CHECKS PASSED ==="]),
    ("Phase 5.3: ambient HUD snapshot — objectives/working-on/awaiting-approval, fail-quiet per section",
     "test_hud.py", "offline", ["checks passed ==="]),
    ("Phase 5.2: device handoff — unprompted speech follows the owner to his active device",
     "test_device_handoff.py", "offline", ["checks passed ==="]),
    ("Phase 1.2: AEC seam — echo-canceller flips open speakers to full-duplex; degrades without the SDK",
     "test_aec.py", "offline", ["checks passed ==="]),
    ("Phase 6: relational — affect sensing + manner, relationship memory, calibrated wellbeing pushback",
     "test_relational.py", "offline", ["checks passed ==="]),
    ("Tools-util: tool-reliability learning — flaky tools surfaced from the audit trail, gated + cached",
     "test_tool_reliability.py", "offline", ["checks passed ==="]),
    ("Memory-util: salience surfacing — durable commitments proactively resurfaced, rotated not nagged",
     "test_memory_salience.py", "offline", ["checks passed ==="]),
    ("30.F1: one memory origin — every store follows one state root, and a merge unions two hosts",
     "test_memory_single_origin.py", "offline", ["checks passed ==="]),
    ("01.F2: calibrated uncertainty — an unknowable is not answered flat, an answerable is not refused",
     "test_uncertainty.py", "offline", ["checks passed ==="]),
    ("S36: secrets never leak — redaction masks, the report carries no value, and a dead backend "
     "cannot stop the boot",
     "test_secrets_redaction.py", "offline", ["checks passed ==="]),
    ("Calibration: a reported confidence can be scored — ECE/Brier against hand-computed values, "
     "and None (never 0.0) when there is nothing to measure",
     "test_calibration_metrics.py", "offline", ["checks passed ==="]),
    ("S01-S50: the skill suite is reachable — every playbook reads, and the integration triggers "
     "name tools that exist",
     "test_skill_suite.py", "offline", ["checks passed ==="]),
    ("B1: intent router — high-precision intents narrow to the one right tool; multi-intent/chat untouched",
     "test_intent_router.py", "offline", ["checks passed ==="]),
    ("02.R2: the stable half of the system prompt is byte-identical between turns, so a prompt "
     "cache can actually hit it",
     "test_prompt_prefix_stable.py", "offline", ["checks passed ==="]),
    ("01.R1/01.R2: the five intent classes are explicit and measured, and an ambiguous turn asks "
     "ONE question instead of guessing \u2014 and never the same one twice",
     "test_intent_classes.py", "offline", ["checks passed ==="]),
    ("03.R3: chaining — a bare recipient name resolves to the right target for THAT channel in the "
     "same turn, before the confirm gate, and asks rather than guessing",
     "test_tool_chaining.py", "offline", ["checks passed ==="]),
    ("B6: clause routing — each clause of a multi-intent turn asks for its own tool, not just the first",
     "test_clause_routing.py", "offline", ["checks passed ==="]),
    ("B6: clause completion — a compound request fires every tool its plan names, on BOTH response paths",
     "test_clause_completion.py", "offline", ["checks passed ==="]),
    ("J4.2/J4.3: PC-op routing — no tool module silently unrouted, no two modules claiming one op name",
     "test_pc_agent_routing.py", "offline", ["checks passed ==="]),
    # J6.2 — five files that were on disk and in NO registry, so they had silently stopped
    # running. Verified passing before registration; three print nothing at all, so they are
    # gated on exit code only until they grow a summary line.
    ("Restore drill: a backup that has never been restored is not a backup (hermetic)",
     "test_backup_restore.py", "offline", ["checks passed ==="]),
    ("Composio tool router: two-step router, hermetic, no network",
     "test_composio_router.py", "offline", ["checks passed ==="]),
    ("Fleet routing memory: repeated delegated domains surface as a system-prompt bias line",
     "test_fleet_routing.py", "offline", ["checks passed ==="]),
    ("PC-agent refuse-list: catastrophic ops die at the elevated executor",
     "test_pc_agent_refuse.py", "offline", ["checks passed ==="]),
    ("Proactive reporting: the autonomous backlog pass reports what it did, never acts silently",
     "test_proactive_report.py", "offline", ["proactive report wiring OK"]),
    ("C7 Skills: skill runtime — invoke_skill runs built-in composable manifests step-by-step",
     "test_skill_runtime.py", "offline", ["checks passed ==="]),
    ("C6 Protocols: recovery drills — every protocol rehearses (gated) without launching the real script",
     "test_protocol_drills.py", "offline", ["checks passed ==="]),
    ("C2 Integrations-util: HMAC-verified inbound webhooks feed the world-model; bad signatures rejected",
     "test_webhooks.py", "offline", ["checks passed ==="]),
    ("G1 Acknowledgements: instant acks are varied + don't double up with the per-tool ack on fast reads",
     "test_acknowledgements.py", "offline", ["checks passed ==="]),
    ("G5 Connectivity: fresh integration events (webhooks/world-model) reach the reactive per-turn context",
     "test_connectivity.py", "offline", ["checks passed ==="]),
    ("Edge audio auto-route: the built-in Realtek headphone jack never masquerades as connected headphones",
     "test_audio_route.py", "offline", ["checks passed ==="]),
    ("Streaming latency: pure-chatter turns carry zero tools (skip the ~10k-token prefill); tool turns keep them",
     "test_pure_chat_tools.py", "offline", ["checks passed ==="]),
    ("C3 TTS affect: owner mood -> ElevenLabs voice_settings (steadier when stressed, livelier when upbeat)",
     "test_affect_voice.py", "offline", ["checks passed ==="]),
    ("C5 PC-agent: see->act->VERIFY loop confirms file/process effects landed; flags a mismatch",
     "test_pc_verify.py", "offline", ["checks passed ==="]),
    ("PC-agent pause/continue: process_op suspend+resume freezes/unfreezes an app (proactive can pause activity)",
     "test_pc_suspend.py", "offline", ["checks passed ==="]),
    ("Reminder robustness: set_reminder tolerates alt arg keys + a relative phrase in at/when (no fromisoformat crash)",
     "test_reminder_args.py", "offline", ["checks passed ==="]),
    ("Proactive thresholds: every companion source (anticipation/wellbeing/presence/pattern/resurface) can clear the bar",
     "test_proactive_thresholds.py", "offline", ["checks passed ==="]),
    ("Reliability guards: permanent-error bench + owner paging + shell-chain refusal",
     "test_reliability_guards.py", "offline", ["reliability guards self-check OK"]),
    ("Tool-failure guard: proactive/digest never voice a tool error as data",
     "test_tool_failure_guard.py", "offline", ["passed, 0 failed"]),
    ("Brain mode selection: slow handshake keeps the supervised REMOTE link (no session demotion)",
     "test_brain_mode_selection.py", "offline", ["passed, 0 failed"]),
    ("Real-world integrations: Twilio/Maps/Wolfram/Fit registration + degradation + confirm-gating + plan_today",
     "test_new_integrations.py", "offline", ["checks passed ==="]),
    ("C4 Speed: streaming TTFW — first spoken word reaches the owner before the slow tail finishes",
     "test_speed.py", "offline", ["checks passed ==="]),
    ("Catalogue budget (03.R5): the per-turn tool surface has an ENFORCED ceiling, and an unsure "
     "router asks one question instead of guessing",
     "test_catalogue_budget.py", "offline", ["checks passed ==="]),
    ("C3 edge: AffectTTS pushes a live voice-settings update per owner mood (change-filtered, downstream)",
     "test_affect_tts_edge.py", "offline", ["checks passed ==="]),
    ("No-result sentinels: every read tool speaks a complete negative when empty", "test_no_result_sentinels.py",
     "offline", ["checks passed ==="]),
    ("Hardware acceptance baseline: per-device TTFW/VAQI envelope + config consistency",
     "test_hardware_baseline.py", "offline", ["checks passed ==="]),
    ("Failover latency: dead/cooling primary costs <500ms P50 (cold + warm)",
     "test_failover_latency.py", "offline", ["checks passed ==="]),
    ("Protocol smoke + overlap audit: recovery scripts drilled, archives distinct",
     "test_protocol_smoke.py", "offline", ["checks passed ==="]),
    ("Structured observability: metrics registry + agent/LLM feed + /metrics route",
     "test_metrics.py", "offline", ["checks passed ==="]),
    ("P0 #1: brain owns the reminder scheduler (fires 24/7)", "test_scheduler_brain.py",
     "offline", ["checks passed ==="]),
    ("P0 #3: edge auto-reconnects to the brain after a restart", "test_edge_reconnect.py",
     "offline", ["checks passed ==="]),
    ("Streaming voice path (respond_stream yields sentences live)", "test_streaming.py",
     "offline", ["checks passed ==="]),
    ("Self-improvement loop (background_review learns facts into L1)", "test_self_improve.py",
     "offline", ["checks passed ==="]),
    ("Code self-improvement (4.12): bounded, opt-in, branch-only, never pushes", "test_code_self_improve.py",
     "offline", ["checks passed ==="]),
    ("Companion safety: confirm-gate + durable proactive + smart reset + vault write",
     "test_companion_safety.py", "offline", ["checks passed ==="]),
    ("LLM routing: provider prefix + fast tier + first-token failover + warm-up",
     "test_llm_routing.py", "offline", ["checks passed ==="]),
    ("Background task queue: fire long work, live status, voice completion",
     "test_background_tasks.py", "offline", ["checks passed ==="]),
    ("Task to-do list: add/manage/priority/deadline/progress + spoken deadline reminders",
     "test_task_todos.py", "offline", ["checks passed ==="]),
    ("Task restart expiry: a dead work job never reloads as 'running' (the HUD orphan pile-up)",
     "test_task_restart_expiry.py", "offline", ["checks passed ==="]),
    ("Mis-keyed tool calls error instead of returning a fluent question the model then speaks",
     "test_missing_arg.py", "offline", ["checks passed ==="]),
    ("Proactive timing: no signal kind escapes quiet hours (every kind x every hour)",
     "test_proactive_windows.py", "offline", ["checks passed ==="]),
    ("Reminder cancel contract: all three entry points clear the ticker, not just the local job",
     "test_reminder_cancel_contract.py", "offline", ["checks passed ==="]),
    ("Voice-enrolment script parses: to-read-script.md is DATA, and its durations are read",
     "test_enroll_script_parse.py", "offline", ["checks passed ==="]),
    ("SECURITY.md's confirmation tier matches CONFIRM_TIER in code (both directions)",
     "test_confirm_tier_documented.py", "offline", ["checks passed ==="]),
    ("Browser/SpeechBrain guard: the k2 LazyModule cannot mask a real Playwright error",
     "test_browser_speechbrain_guard.py", "offline", ["checks passed ==="]),
    ("LLM failover speed: both streaming paths bail fast; a slow model is not benched like a broken one",
     "test_llm_failover_speed.py", "offline", ["checks passed ==="]),
    ("Daily digest: one catch-up/day (6am + first edge turn), no duplicate Telegram nudges",
     "test_daily_digest.py", "offline", ["checks passed ==="]),
    ("Voice-grade brain: single-tool short-circuit + read-intent forcing + parallel tools",
     "test_brain_voice_grade.py", "offline", ["checks passed ==="]),
    ("Autonomous work_on_task: bounded worker, defers outward actions, backgrounds",
     "test_work_on_task.py", "offline", ["checks passed ==="]),
    ("Safety+Autonomy levers: catastrophic refusal + work_on_task intent routing",
     "test_safety_autonomy.py", "offline", ["checks passed ==="]),
    ("Autonomy governor (36.F6): calls/spend/runtime ceilings refuse, audited, survive restart",
     "test_action_governor.py", "offline", ["checks passed ==="]),
    ("Correlation id (31.F5): one id joins edge, brain, tool and audit with no gaps",
     "test_correlation_id.py", "offline", ["checks passed ==="]),
    ("Unattended review (45.F4): every unattended action with its actor, id and outcome",
     "test_unattended_review.py", "offline", ["checks passed ==="]),
    ("HUD render seam (P1.2): the page draws every section the brain sends, and parses it",
     "test_hud_render.py", "offline", ["checks passed ==="]),
    ("Jev typed decisions: option authority, outage behavior, minimized audit and path parity",
     "test_jev_judgment.py", "offline", ["checks passed ==="]),
    ("Jev tool arbitration (01.R6): the deterministic group match is the only candidate source, "
     "a 400ms cap, silent deterministic fallback, and the owner-visible two-option path unchanged",
     "test_jev_tool_arbitration.py", "offline", ["ALL CHECKS PASSED ==="]),
    ("Supersession (30.R10): a declared subject makes a correction replace its predecessor, the "
     "loser is tombstoned not deleted, and a weaker source can never overwrite a stronger one",
     "test_supersession.py", "offline", ["ALL CHECKS PASSED ==="]),
    ("Coherence journeys (01.E3): cross-system policy seams, with blocked legs named rather "
     "than faked", "test_journeys.py", "offline", ["Journey verdicts: CLEAN"]),
    ("Jev turn assessment (01.R7): route, clarity, urgency and tone in ONE bounded call; ambiguity "
     "asks one question; a failed assessment stays silent; urgency never touches the budget",
     "test_jev_turn_assessment.py", "offline", ["ALL CHECKS PASSED ==="]),
    # Added 2026-10-08 after TWO hand-found defects of the same class: `routine` and the
    # day-planning tools shipped, were advertised every turn, and no route reached them, so
    # 'drop focus mode' was answered 'I have deactivated focus mode' while it stayed active.
    # This makes that class impossible to reintroduce silently.
    ("Tool reachability: every core-advertised tool is routed, or exempt with a stated "
     "reason — so a capability cannot rest on the model happening to volunteer it",
     "test_tool_reachability.py", "offline", ["ALL CHECKS PASSED"]),
    # Added 2026-10-08. All five were written during the S01 pass and then left unregistered,
    # which `test_registry_complete.py` caught: a test that is never run in CI is
    # indistinguishable from a passing test, and worse than no test because its presence
    # implies coverage. Their absence was my omission, not a deliberate exemption.
    ("Calibration recorded (01.F2): the verdict is on the row, so the score is derivable",
     "test_calibration_recorded.py", "offline", ["PASSED", "FAILED"]),
    ("Verbalizer tier (D-92): off by default, narrows one call when on, never silently substitutes",
     "test_verbalizer_tier.py", "offline", ["PASSED", "FAILED"]),
    ("Verbalizer renderer (D-92): with the tier off the reply is byte-identical to before",
     "test_verbalizer_renderer.py", "offline", ["PASSED", "FAILED"]),
    ("Doc integrity: no control characters, no phantom paths, no dead surface claims, no "
     "duplicate or gapped decision numbers",
     "test_doc_integrity.py", "offline", ["PASSED", "FAILED"]),
    ("Interruption budget (D-29): the charter's own number, read from DECISIONS.md, plus a "
     "focus block that zeroes the engine at maximum urgency",
     "test_interruption_budget.py", "offline", ["PASSED", "FAILED"]),
    ("Spatial HUD (45.R6): bounded Mushegh control, search-only shell, real sources and loaders",
     "test_hud_modes.py", "offline", ["checks passed ==="]),
    ("Confirm seam (O2.5): all six exits from tool dispatch audit a decision, rule and turn id",
     "test_confirm_seam.py", "offline", ["checks passed ==="]),
    ("Low-confidence escalation (44.R4): an unsure non-destructive write asks instead of running",
     "test_confirm_low_confidence.py", "offline", ["checks passed ==="]),
    ("Shell bound (04.R4): the shell runs in one directory; escapes and network reach are refused",
     "test_shell_sandbox.py", "offline", ["checks passed ==="]),
    ("Data classes (37.R4): every store declares a class; an undeclared store fails the gate",
     "test_data_classification.py", "offline", ["checks passed ==="]),
    ("Goal deviation (14.R4): a stated goal can interrupt; an aligned session of equal length cannot",
     "test_goal_deviation.py", "offline", ["checks passed ==="]),
    ("Offline promises (23.R4): speech during an outage is held on disk and answered, in order",
     "test_offline_queue.py", "offline", ["checks passed ==="]),
    ("Actor field (36.F7): every audit line has a truthful actor; unattended work is not the owner",
     "test_actor_field.py", "offline", ["checks passed ==="]),
    ("Contacts: resolve name -> target, clarify ambiguous/unknown, degrade",
     "test_contacts.py", "offline", ["checks passed ==="]),
    ("Calendar dates: named day != today, seconds-bearing writes, speakable times",
     "test_calendar_dates.py", "offline", ["checks passed ==="]),
    ("Error tracking: auto-capture, secret scrubbing, cross-process turn correlation, hooks",
     "test_error_tracking.py", "offline", ["checks passed ==="]),
    ("Production guards: one live process per role (newest wins) + no unconfirmed macro actions",
     "test_singleton_and_macro_guard.py", "offline", ["checks passed ==="]),
    ("Coding tools act on the owner's repo (PC_LINK-routed), never the VPS deploy copy",
     "test_coding_routing.py", "offline", ["checks passed ==="]),
    ("Document RAG: ingest/query/close a temp local-doc index, graceful edges",
     "test_documents.py", "offline", ["checks passed ==="]),
    ("Search/scrape fallback: Tavily->Brave->Jina (keyless), Jina->Firecrawl",
     "test_web_fallback.py", "offline", ["checks passed ==="]),
    ("MCP client: local stdio server exposes a callable tool, degrades cleanly",
     "test_mcp_client.py", "offline", ["checks passed ==="]),
    ("Public-surface clean: no secrets/private hosts/personal email in tracked files",
     "check_public_clean.py", "offline", ["clean:"]),
    ("Local voice: build_tts honours provider (ElevenLabs/Piper/Kokoro)",
     "test_local_voice.py", "offline", ["checks passed ==="]),
    ("Identity layer: one persona template personalises from config (framework)",
     "test_identity.py", "offline", ["checks passed ==="]),
    ("Setup wizard: identity render + profile/persona seeding (no clobber)",
     "test_setup_wizard.py", "offline", ["checks passed ==="]),
    ("P1 #4: resilience under fault injection (LLM/cache/scheduler/tool)", "test_resilience.py",
     "offline", ["checks passed ==="]),
    ("P1 #6: memory hygiene (dedup + cap + journal rotation)", "test_memory_hygiene.py",
     "offline", ["checks passed ==="]),
    ("P1 #7: security hardening (system-delete guard + audit value scrub)",
     "test_security_hardening.py", "offline", ["checks passed ==="]),
    ("Phase 2: brain agent (LLM + tools + memory)", "test_brain_agent.py", "network",
     ["fleet sentinel not leaked"]),
    # Fleet live test (MASTER 3.10): self-skips (exit 0 + sentinel) unless FLEET_AUTHORIZED=true and
    # the gateway is reachable; when armed it verifies brain -> ispir. Either sentinel counts as pass
    # here — an armed-and-verified run OR an intentional disarmed skip. A hard failure (armed but the
    # router is missing) exits non-zero and shows as FAIL.
    ("Fleet live: brain -> ispir reachable (gated on FLEET_AUTHORIZED)", "test_fleet_connect.py",
     "offline", ["fleet"]),
]

# Markers that mean "the proxy/brain wasn't reachable" -> SKIP a [network] test, not FAIL.
# Keep these narrow: provider rejections and model/tool behavior errors must stay red.
NETWORK_DOWN = (
    "ConnectError",
    "Connection refused",
    "Failed to establish",
    "Max retries",
    "NameResolutionError",
    "No connection could be made",
    "Temporary failure in name resolution",
    "Timeout",
    "Connection error",  # openai APIConnectionError renders as "Connection error." (no host reachable)
    "WinError 10061",
    "WinError 11001",
    "actively refused",
    "getaddrinfo",
    "nodename nor servname provided",
    # The LLM endpoint answered with a web page, not an API response — something OTHER than the
    # freellmapi proxy is on that port (a squatting dev server), or the tunnel is down. An LLM API
    # never returns an HTML doctype, so this is unambiguously a network/env condition, not a bug.
    "<!DOCTYPE html>",
    "<!doctype html>",
)

# These indicate the dependency was reachable enough to reject the request, or the model/tool
# behavior was wrong. They are real runnable failures even if earlier failover logs mention
# connection errors from other providers.
RUNNABLE_FAILURE = (
    "400 -",
    "401 -",
    "403 -",
    "429 -",
    "BadRequestError",
    "RateLimitError",
    "invalid_request_error",
    "rate_limit_exceeded",
    "tool call validation failed",
    "tool_use_failed",
)


#: Per-test wall clock. Was 180s, which turned out to be *just* under what the heaviest offline test
#: legitimately needs: building the pipeline warms the ECAPA speaker embedder, and importing
#: torch+speechbrain and loading the checkpoint measured 183s on this box while Docker, three VS Code
#: instances and Chrome were holding ~72% CPU. The tests weren't hanging — they were finishing a few
#: seconds late, and whichever one crossed the line got reported as a hang and blocked the deploy.
#: Five consecutive deploys died on that, each on a different test, each passing in isolation.
#: The suite must not spend the real autonomy window (36.F6). Several tests drive a real
#: TaskWorker, and a measured run consumed 64 of 200 calls - so the ledger is pointed at a
#: throwaway file for the duration. Set before any test imports mushegh.brain.governor.
os.environ.setdefault(
    "MUSHEGH_GOVERNOR_LEDGER",
    # The PID is load-bearing. A FIXED path was documented as "a throwaway file for the
    # duration" while actually persisting every run, and `autonomy_max_calls` is 200 over a
    # 24 h window - so the ledger kept accumulating (measured 162 calls, window opened the
    # previous evening) until the governor started refusing calls and failing gates for
    # reasons that had nothing to do with the code under test. That is the "deploy died on a
    # different test each time, each passing in isolation" failure this line exists to
    # prevent, rebuilt one level down. Each run now starts on a fresh budget.
    str(Path(tempfile.gettempdir()) / f"mushegh-test-governor-{os.getpid()}.json"),
)

#: Override with MUSHEGH_TEST_TIMEOUT_S on a slower machine.
TEST_TIMEOUT_S = int(os.environ.get("MUSHEGH_TEST_TIMEOUT_S", "420"))


#: How long to wait between deadline checks. Also the suspend detector's resolution: ask for a slice
#: this long, and any wall time beyond it that we can't account for is time the machine wasn't running.
_SLICE_S = 15.0


def run(script: str, timeout: int) -> tuple[int, str]:
    """Run one test, charging it only the time the machine was actually awake.

    subprocess.run(timeout=...) measures WALL CLOCK, and on Windows time.monotonic() keeps ticking
    through Modern Standby — so closing the lid mid-gate charges the child every frozen second and
    kills it for a hang it never had. That is not hypothetical: the 2026-08-01 gate suspended twice
    (13:56->16:56 and 16:56->18:27) and murdered test_llm_routing and test_task_todos, which need 91s
    and 3s against a 420s cap. Both passed in isolation minutes later.

    So the deadline is enforced in slices: whenever a slice takes far longer than we asked for, the
    excess is time nobody was executing, and it's credited back rather than charged to the test. Real
    hangs are unaffected — a wedged child burns the budget in awake time and still dies at 124.
    """
    t0 = time.monotonic()
    suspended = 0.0
    p = subprocess.Popen(
        [PY, str(ROOT / "bench" / script)],
        cwd=str(ROOT),
        # No test may inherit this process's stdin. One that reads it waits forever for input that
        # is never coming, and the budget below does not save the run: on 2026-08-15 a `ruff … -`
        # inside test_static_correctness blocked on an inherited stdin, and after the kill its
        # orphaned grandchild still held the pipes — the run sat there for half an hour. A test
        # that wants input must supply it; one that reads by accident now gets EOF and fails fast.
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    deadline = t0 + timeout
    while True:
        mark = time.monotonic()
        want = min(_SLICE_S, max(0.1, deadline - mark))
        try:
            out, err = p.communicate(timeout=want)
            break
        except subprocess.TimeoutExpired:
            # communicate() leaves the child alive and its reader threads draining, so it is safe to
            # call again — no output is lost across these slices.
            drift = (time.monotonic() - mark) - want
            if drift > _SLICE_S:      # >2x what we asked for: the box was asleep, not merely busy
                suspended += drift
                deadline += drift
                print(f"    (system suspended ~{drift:.0f}s during this test — not counted "
                      f"against its {timeout}s budget)")
            if time.monotonic() >= deadline:
                p.kill()
                out, err = p.communicate()
                awake = (time.monotonic() - t0) - suspended
                return 124, f"TIMEOUT after {awake:.0f}s awake ({timeout}s budget)"
    dt = ((time.monotonic() - t0) - suspended) * 1000
    return p.returncode, (out or "") + "\n" + (err or "") + f"\n[{dt:.0f}ms]"


_EMPTY_RUN_RE = re.compile(r"===\s*0/0\s+checks passed\s*===")


def classify_result(tag: str, code: int, out: str, needles: list[str]) -> str:
    """Classify a child test result as PASS, FAIL, or SKIP."""
    # A test that asserted NOTHING is not a passing test. Three entries here were gated on the exit
    # code alone (J6.5), so a body that stopped asserting would still have read green — and adding
    # the "checks passed ===" needle does not fix that on its own, because "0/0 checks passed"
    # contains it. Nothing legitimately runs zero checks, so treat it as a failure everywhere rather
    # than per-entry, which closes the class instead of the three instances.
    if _EMPTY_RUN_RE.search(out):
        return "FAIL"
    if code == 0 and all(n in out for n in needles):
        return "PASS"
    if tag == "network" and code == 124:
        # A [network] test that hit the timeout wall = the LLM dependency didn't respond in time in THIS
        # env (a dev box on a slow/rate-limited key; the VPS carries the working chain). Same
        # 'unavailable dependency' signal as a refused connection -> SKIP, not a false red. (An
        # OFFLINE test that times out is a genuine hang and still FAILs — it never reaches here.)
        return "SKIP"
    if tag == "network" and code != 0:
        net_down = any(n in out for n in NETWORK_DOWN)
        # The whole LLM failover chain exhausted to a connectivity failure -> no reachable model in
        # THIS environment (a dev box; the VPS carries the working chain). That's the 'unavailable
        # dependency' case the SKIP path exists for, so skip it even if one provider logged a 4xx
        # along the way. A specific model/tool REJECTION (tool_use_failed, tool-call validation) does
        # NOT print this terminal marker, so it still falls through to FAIL below.
        if "all LLM models failed" in out and net_down:
            return "SKIP"
        if any(n in out for n in RUNNABLE_FAILURE):
            return "FAIL"
        if net_down:
            return "SKIP"
    return "FAIL"


_NO_BASH = -99

#: Wall-clock ceiling for the preflight subprocess. Preflight itself is a dozen local checks and
#: finishes in about two seconds; anything past this is wedged, not slow.
_PREFLIGHT_TIMEOUT_S = 120


def _run_preflight():
    """Run scripts/preflight.sh under GIT Bash specifically.

    Not plain `bash`: on this machine that resolves to WSL, which mounts the drive at /mnt/c and
    reports HOME=/home/<user>. Every path in the script then pointed at a filesystem the brain
    does not use, so the checker confidently reported "state dir is missing" for a directory
    sitting right there. A preflight that inspects the wrong machine is worse than no preflight —
    it is the same failure it exists to catch, one level up.

    Bounded, because this was the one subprocess in the gate without a timeout and an unbounded
    one has no failure mode of its own: it hangs, the operator waits, and the only escape is
    Ctrl+C, which raises KeyboardInterrupt out of `main()` and takes the other 250 results with
    it. A wedged preflight is a broken invariant and belongs in the tally like any other.
    """
    candidates = [Path(r"C:\Program Files\Git\bin\bash.exe"),
                  Path(r"C:\Program Files (x86)\Git\bin\bash.exe")]
    git_bash = next((c for c in candidates if c.is_file()), None)
    if git_bash is None:
        return subprocess.CompletedProcess([], _NO_BASH, "", "")
    try:
        return subprocess.run([str(git_bash), "scripts/preflight.sh"], cwd=str(ROOT),
                              capture_output=True, text=True,
                              timeout=_PREFLIGHT_TIMEOUT_S)
    except subprocess.TimeoutExpired:
        # Reported, not raised. The point of the gate is the full set of results;
        # one wedged script must not be able to destroy the other 250.
        return subprocess.CompletedProcess(
            [], 124,
            stdout=f"preflight did not finish within {_PREFLIGHT_TIMEOUT_S}s and was terminated.\n"
                   "        -> it is hung, not slow: rerun 'bash scripts/preflight.sh' directly to see where it stops",
            stderr="")


def _tree_fingerprint() -> str:
    """A digest of every .py the suite can execute, so the run can name the tree it verified.

    Recorded before the first test and re-checked after the last. A 33-minute run whose inputs
    moved underneath it does not describe one moment, it describes two trees, and nothing in the
    output would say so. That is not hypothetical: on 2026-10-11 a concurrent agent landed a merge
    across the whole working tree 15 minutes into a baseline run. Every file took a fresh mtime,
    `.git/AUTO_MERGE` appeared, and the giveaway was a traceback citing line 115 of a gate whose
    line 115 had moved to 121 in the version that replaced it. `255 passed, 10 failed` was a
    comparison across two different checkouts and looked exactly as authoritative as a real one.

    Content, not mtime: a merge or checkout rewrites mtimes wholesale, and a touched-but-identical
    file is still the same tree. SHA-256 over (relative path, bytes) in sorted order.
    """
    import hashlib

    h = hashlib.sha256()
    for base in (ROOT / "src", ROOT / "bench"):
        for p in sorted(base.rglob("*.py")):
            try:
                h.update(str(p.relative_to(ROOT)).encode("utf-8", "replace"))
                h.update(p.read_bytes())
            except OSError:
                h.update(str(p).encode("utf-8", "replace"))
    return h.hexdigest()[:16]


def main() -> int:
    print("=" * 60)
    print(" MUSHEGH — full verification")
    print("=" * 60)
    results: list[tuple[str, str]] = []  # (status, label)

    tree_before = _tree_fingerprint()
    print(f"\ntree fingerprint (the exact code this run verifies): {tree_before}")

    # K7b — the environment invariants run FIRST, before any test.
    #
    # The rename produced three silent failures in one day (stranded face refs, wrong deploy path,
    # wrong env prefix) and **118 passing tests caught none of them**, because none is a code
    # defect: they are statements about the machine the code runs on. Waiting for a deploy to
    # discover them means discovering them at the worst moment.
    #
    # Local checks only here (no --remote): the gate must stay runnable offline, and the remote
    # assertions belong to the deploy, which is the thing they gate.
    print("\n--- [ops] Preflight: environment invariants (K7b)\n    (scripts/preflight.sh)")
    pre = _run_preflight()
    print("    " + (pre.stdout or "").strip().replace("\n", "\n    "))
    if pre.returncode == 0:
        results.append(("PASS", "Preflight: environment invariants (K7b)"))
    elif pre.returncode == _NO_BASH:
        print("    -> SKIP (no Git Bash found; preflight still runs on deploy)")
        results.append(("SKIP", "Preflight: environment invariants (K7b)"))
    else:
        # NOT fatal to the run. A broken invariant is real, but stopping here would hide every
        # code result behind an environment problem — and a gate people cannot get past is a gate
        # people learn to bypass. It fails the run at the end, where it is impossible to miss.
        print("    -> FAIL (an environment invariant is broken; see the lines above)")
        results.append(("FAIL", "Preflight: environment invariants (K7b)"))

    for label, script, tag, needles in TESTS:
        print(f"\n--- [{tag}] {label}\n    ({script})")
        code, out = run(script, timeout=TEST_TIMEOUT_S)
        tail = "\n".join(line for line in out.splitlines() if line.strip())[-1500:]
        print("    " + tail.replace("\n", "\n    "))

        status = classify_result(tag, code, out, needles)
        if status == "FAIL":
            # Say WHY. A child can print "15/15 checks passed" and still fail here — a non-zero exit
            # after the summary (a crash during interpreter shutdown, say) is invisible otherwise, and
            # the log then shows a passing test marked FAIL with no explanation. Costs one line.
            absent = [n for n in needles if n not in out]
            # The child's own failing lines, wherever they are in its output. The tail printed above
            # is only the last 1500 chars, so a check that failed early scrolls off — which is how a
            # test reporting "24/25 checks passed" got summarised as "output looked fine": the needle
            # "checks passed ===" matches a PARTIAL pass just as happily as a total one.
            bad = [ln.strip() for ln in out.splitlines()
                   if "[FAIL]" in ln or ln.lstrip().startswith("x ") or "FAILED" in ln]
            why = f", missing output: {absent}" if absent else ""
            print(f"    -> FAIL (exit={code}{why})")
            for ln in bad[:10]:
                print(f"       {ln[:200]}")
            if len(bad) > 10:
                print(f"       … and {len(bad) - 10} more failing checks")
            if not bad and not absent:
                print("       (no failing check printed — the child exited non-zero after its "
                      "summary, e.g. a crash during interpreter shutdown)")
        if status == "SKIP":
            print("    -> SKIP (freellmapi proxy unreachable — start the VPS tunnel to run this)")
        results.append((status, label))

    failed = [lbl for s, lbl in results if s == "FAIL"]
    npass = sum(1 for s, _ in results if s == "PASS")
    nskip = sum(1 for s, _ in results if s == "SKIP")

    # The run's own integrity, checked before its own verdict is printed. A moved tree makes every
    # line above a composite of two checkouts, so this says so rather than letting the tally stand.
    tree_after = _tree_fingerprint()
    print("\n" + "=" * 60)
    print(" RUN INTEGRITY")
    print("=" * 60)
    if tree_after != tree_before:
        print("  *** THE TREE CHANGED WHILE THIS RUN WAS IN FLIGHT ***")
        print(f"      began as {tree_before}, ended as {tree_after}")
        print("      Every result above is a composite of TWO different checkouts — some tests ran")
        print("      against the first tree and some against the second. Do not read this tally as")
        print("      a verdict on either. A concurrent agent, merge or checkout is the usual cause.")
        results.append(("FAIL", "RUN INTEGRITY: the tree changed during the run"))
    else:
        print(f"  tree unchanged for the whole run ({tree_before})")

    print("\n" + "=" * 60)
    print(" SUMMARY")
    print("=" * 60)
    icon = {"PASS": "✓", "FAIL": "✗", "SKIP": "·"}
    for status, label in results:
        print(f"  {icon[status]} {status:4} {label}")

    failed = [lbl for s, lbl in results if s == "FAIL"]
    print(f"\n  {npass} passed, {len(failed)} failed, {nskip} skipped")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

