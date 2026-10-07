"""Module-level job targets so apscheduler can serialise them."""

from loguru import logger

from afon.brain.loops import ticks


@ticks("reliability-health-probe")
async def _fire_reliability_probe() -> None:
    """Probe critical organs, self-repair what's fixable, and page the owner on a SUSTAINED
    outage (Phase 0.1). Never raises into the loop."""
    try:
        from afon.brain.reliability import health_probe, attempt_repair_and_escalate
        probes = await health_probe()
        summary = await attempt_repair_and_escalate(probes)
        still_bad = [n for n, s in summary.items() if not s["ok"]]
        repaired = [n for n, s in summary.items() if s.get("repaired")]
        if repaired:
            logger.info(f"reliability probe: self-repaired {repaired}")
        if still_bad:
            logger.warning(f"reliability probe: still degraded after repair: {still_bad}")
    except Exception as e:  # noqa: BLE001
        logger.warning(f"reliability probe failed: {type(e).__name__}: {e}")


@ticks("composio-catalog-refresh")
async def _fire_composio_catalog_refresh() -> None:
    """T12 — refresh the cached Composio catalog so the system prompt picks up new tools
    overnight (before the morning briefing, so the next session sees the full list)."""
    try:
        from afon.brain.composio_catalog import refresh, invalidate
        n = await refresh()
        invalidate()
        total = sum(len(v) for v in (n.get("toolkits") or {}).values())
        logger.info(f"composio catalog nightly refresh: {total} tools cached")
    except Exception as e:  # noqa: BLE001
        logger.warning(f"composio catalog refresh failed: {type(e).__name__}: {e}")


@ticks("toolchain-daily-update")
async def _fire_toolchain_update() -> None:
    """Every 24h — new versions for the four managed CLIs, installed and proved (D-88).

    Reports only when something changed or broke. A daily "nothing happened" is an interruption
    bought with no information (D-29, D-34), so a quiet run is silent by design.
    """
    try:
        from afon.brain.toolchain import daily_update_check, report

        states = await daily_update_check()
        line = report(states)
        if not line:
            logger.info("toolchain: nothing to update")
            return
        broke = any(s.broke for s in states)
        logger.info(f"toolchain: {line}")
        from afon.brain.scheduler import _emit_proactive

        # A break is worth hearing about; a clean update is worth a note, not a spoken interruption.
        await _emit_proactive(line, 0.80 if broke else 0.40, "Afon — toolchain")
    except Exception as e:  # noqa: BLE001
        logger.warning(f"toolchain daily update failed: {type(e).__name__}: {e}")


@ticks("toolchain-weekly-review")
async def _fire_toolchain_review() -> None:
    """Every 168h — Jev ranks what each CLI is missing, and each CLI is asked too (D-89).

    Advisory only. Nothing is installed, enabled or permitted by this job; it produces a report the
    owner answers.
    """
    try:
        from afon.brain.toolchain import review_report, weekly_improvement_review

        proposals = await weekly_improvement_review()
        line = review_report(proposals)
        if not line:
            return
        logger.info("toolchain: weekly improvement review written")
        from afon.brain.scheduler import _emit_proactive

        await _emit_proactive(line, 0.42, "Afon — weekly toolchain review")
    except Exception as e:  # noqa: BLE001
        logger.warning(f"toolchain weekly review failed: {type(e).__name__}: {e}")
