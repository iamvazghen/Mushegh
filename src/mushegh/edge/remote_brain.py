"""RemoteBrain — the unified-brain twin of the in-process MusheghBrain.

When ``MUSHEGH_BRAIN_MODE=remote`` (or ``auto`` and the brain is reachable), the laptop edge stops
running its own agent and becomes a thin client to the 24/7 VPS brain: there is then ONE Mushegh and
ONE memory across the laptop, phone, and glasses. Audio (STT/TTS, wake word, VAD) still runs locally
for privacy + mic latency; only the finished transcript goes to the brain, which streams the reply
back sentence-by-sentence for incremental TTS — same low-latency feel as local.

Pipeline placement is identical to MusheghBrain: STT -> RemoteBrain -> TTS.
"""

from __future__ import annotations

import asyncio

from loguru import logger
from pipecat.frames.frames import Frame, InterruptionFrame, TranscriptionFrame, TTSSpeakFrame
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor

from mushegh.edge.brain_client import BrainClient
from mushegh.shared.protocol import StreamEvent, StreamKind
from mushegh.shared.session import device_session_id


class RemoteBrain(FrameProcessor):
    """Thin client to the VPS brain, with a WARM LOCAL STANDBY (Phase 0.2).

    The VPS brain is a single point of failure: over a week it *will* be briefly unreachable (deploy,
    OOM, network). ``BrainClient`` already reconnects, but during the gap a naive client just drops the
    utterance and Mushegh goes mute. Instead, when a send can't reach the VPS we answer the turn with a
    LOCAL in-process ``MusheghAgent`` — its own independent LLM chain — and speak that. Routing is
    decided per turn on the live link state, so the moment the VPS is back the next turn returns to it
    automatically (promote → serve-local → demote, with no explicit state machine). The local agent is
    built lazily, so the common case (VPS up) never pays for it.
    """

    def __init__(
        self,
        session_id: str | None = None,
        device_id: str = "laptop",
        headphones_connected: bool = False,
    ) -> None:
        super().__init__()
        # 07.F1 — resolved at construction, not at import: the id must be the one on disk when
        # this edge actually connects, so a reconnect rejoins the conversation it left.
        self._client = BrainClient(
            session_id=session_id or device_session_id(device_id),
            device_id=device_id,
            headphones_connected=headphones_connected,
            on_event=self._on_event,
        )
        # 23.R4 — deliver what was held the moment the link returns, not the next time he speaks.
        # "Answer when the brain returns" is the promise; waiting for another utterance is not it.
        self._client.on_connected = self._drain_held
        self._task: asyncio.Task | None = None
        self._fallback_agent = None          # lazily-built local MusheghAgent (warm standby)
        self._local_task: asyncio.Task | None = None
        # Send this laptop's errors up to the brain, so the VPS journal is the union of all three
        # processes and "what did he actually experience?" is answerable from one place.
        try:
            from mushegh.shared import errors as _err

            _err.set_shipper(self._client.ship_error)
        except Exception:  # noqa: BLE001 — shipping is a bonus; the local journal is the source
            pass

    async def start(self, connect_timeout_s: float = 3.0) -> bool:
        """Begin the supervised link. Returns True once connected within the timeout (so the
        caller can fall back to the local brain if the VPS is unreachable)."""
        self._task = asyncio.create_task(self._client.run())
        deadline = asyncio.get_running_loop().time() + connect_timeout_s
        while asyncio.get_running_loop().time() < deadline:
            if self._client.connected:
                logger.info("RemoteBrain: linked to the VPS brain")
                return True
            await asyncio.sleep(0.1)
        logger.warning("RemoteBrain: VPS brain not reachable within timeout")
        return self._client.connected

    async def _on_event(self, ev: StreamEvent) -> None:
        # Assistant text and spoken tool-progress both go to TTS; lifecycle events are control-only.
        if ev.kind in (StreamKind.assistant, StreamKind.tool) and ev.delta.strip():
            await self.push_frame(TTSSpeakFrame(ev.delta.strip()))

    async def process_frame(self, frame: Frame, direction: FrameDirection) -> None:
        await super().process_frame(frame, direction)

        if isinstance(frame, InterruptionFrame):
            await self._client.barge()          # tell the brain to cancel the in-flight turn
            if self._local_task and not self._local_task.done():
                self._local_task.cancel()       # also cancel any in-flight LOCAL standby turn
            await self.push_frame(frame, direction)
            return

        if isinstance(frame, TranscriptionFrame):
            text = (getattr(frame, "text", "") or "").strip()
            if text:
                await self._route_utterance(text)
            return  # consume; the remote reply arrives async via _on_event

        await self.push_frame(frame, direction)

    async def _route_utterance(self, text: str) -> str:
        """Send to the VPS brain if the link is live; otherwise fall back to the local standby.

        Returns "remote" or "local" (for logging/testing). The remote reply streams back async via
        ``_on_event``; the local reply is streamed inline here.
        """
        if self._client.connected and await self._client.send_utterance(text):
            logger.info(f"heard: {text!r} -> VPS brain")
            return "remote"
        # 23.R2 — before spending an LLM on it, check whether the answer needs one at all. Status
        # comes from the declared degraded matrix and reminders from the digest the brain handed over
        # while it still could; both are free and instant. Only tried while degraded, because with the
        # brain up these belong to the brain, which has the live scheduler rather than a copy.
        local = self._degraded_answer(text)
        if local is not None:
            logger.info(f"heard: {text!r} -> answered locally while degraded (no model)")
            await self.push_frame(TTSSpeakFrame(local))
            return "degraded"
        logger.warning(f"VPS brain unreachable — answering {text!r} on the LOCAL standby brain")
        await self._answer_local(text)
        return "local"

    def _degraded_answer(self, text: str) -> str | None:
        """23.R2 — the answer if this host can give one without a model, else None. Fail-quiet."""
        try:
            from mushegh.edge import degraded_answers
            from mushegh.shared import degraded

            mode = degraded.current(brain_up=self._client.connected)
            return degraded_answers.answer(text, mode_name=mode.name)
        except Exception as e:  # noqa: BLE001 — never let this path cost him the standby
            logger.debug(f"degraded answer skipped ({type(e).__name__})")
            return None

    async def _promise(self, text: str) -> None:
        """23.R4 — hold a turn we could not answer, and say so truthfully.

        Reached only when BOTH the VPS brain and the local standby are unavailable. Before this, both
        of those paths spoke an apology and dropped the transcript: it had been heard and transcribed,
        and was then thrown away, which is what made real offline capability score 0.70/4.

        The wording follows what actually happened. A promise that was not taken on must not be
        announced as though it were, so a full or unwritable queue says something different.
        """
        from mushegh.edge import offline_queue

        if offline_queue.enqueue(text):
            owed = offline_queue.depth()
            more = "" if owed == 1 else f" That's {owed} I'm holding."
            await self.push_frame(TTSSpeakFrame(
                "I can't reach the brain or answer that locally, sir — I've held it and I'll come "
                f"back to you the moment the link returns.{more}"))
        else:
            await self.push_frame(TTSSpeakFrame(
                "I can't reach the brain or answer that locally, sir, and I can't hold any more "
                "either — you'll have to ask me again later."))

    async def _drain_held(self) -> None:
        """Send everything held during the outage, oldest first. Called on every reconnect."""
        from mushegh.edge import offline_queue

        if not offline_queue.depth():
            return
        n = await offline_queue.drain(self._client.send_utterance)
        if n:
            await self.push_frame(TTSSpeakFrame(
                f"The link's back, sir — catching up on {n} thing{'' if n == 1 else 's'} "
                "you said while it was down."))

    async def _ensure_fallback(self):
        """Build (once) + warm the local standby agent. A preset agent (tests) is left untouched."""
        if self._fallback_agent is None:
            from mushegh.brain.agent import MusheghAgent

            agent = MusheghAgent()
            warm = getattr(agent, "warmup", None)
            if callable(warm):
                try:
                    await warm()
                except Exception:  # noqa: BLE001 — warmup is best-effort
                    pass
            self._fallback_agent = agent
        return self._fallback_agent

    async def _answer_local(self, text: str) -> None:
        """Run one turn on the local standby agent and speak it (streamed sentence-by-sentence)."""
        async def _turn() -> None:
            try:
                agent = await self._ensure_fallback()
                spoke = False
                async for sentence in agent.respond_stream(text):
                    if sentence:
                        spoke = True
                        await self.push_frame(TTSSpeakFrame(sentence))
                if not spoke:
                    await self._promise(text)
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001 — a standby failure must not crash the edge
                logger.exception("local standby turn failed")
                await self._promise(text)

        self._local_task = asyncio.create_task(_turn())
        await self._local_task

    async def stop(self) -> None:
        if self._local_task and not self._local_task.done():
            self._local_task.cancel()
        await self._client.stop()
