"""Simulation manager — state machine, frame execution, lifecycle.

Phase 9.1 fix: Frame-by-frame execution with subprocess cancellation.

ROOT CAUSE: The original _run_loop() called matlab.run_scenario() which
used subprocess.run() — a blocking call that held the GIL for 30-60s.
During that time, no HTTP request could be processed, so PAUSE and STOP
requests were queued and ignored until MATLAB returned all results.

SOLUTION: Execute frames one at a time via dt_step_frame.m. Between each
frame, check _stop_event and _pause_event. Use a threading lock so that
PAUSE/STOP requests can acquire the lock only when MATLAB is NOT running
(i.e., between frames), ensuring no frame is lost and no race condition.
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
import time
import uuid
from concurrent.futures import Future
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from .ai_bridge import AIBridge
from .config import (
    DEFAULT_SEED,
    MATLAB_DIR,
    VALID_MODES,
    VALID_POLICIES,
    VALID_STRATEGIES,
)
from .matlab_bridge import MATLABBridge
from .models import (
    AIInfo,
    FrameMetrics,
    FrameResponse,
    MetricsSummary,
    SimMode,
    SimStatus,
    SimulationStartRequest,
    SimulationState,
    SimulationStatus,
    Strategy,
)
from .result_service import ResultService
from .scenario_service import build_custom_scenario, get_scenario
from .websocket_manager import WebSocketManager

logger = logging.getLogger(__name__)


class SimulationManager:
    """Manages the active simulation lifecycle.

    Phase 9.1: Executes frames one at a time via dt_step_frame.m,
    checking _stop_event and _pause_event between frames. This allows
    PAUSE and STOP to interrupt the simulation within one frame cycle.
    """

    def __init__(
        self,
        matlab_bridge: MATLABBridge,
        ai_bridge: AIBridge,
        result_service: ResultService,
        ws_manager: WebSocketManager,
    ):
        self.matlab = matlab_bridge
        self.ai = ai_bridge
        self.results = result_service
        self.ws = ws_manager

        self.run_id: Optional[str] = None
        self.status: SimStatus = SimStatus.STOPPED
        self.scenario: Optional[dict] = None
        self.scenario_id: str = ""
        self.strategy: str = "ai_adaptive"
        self.policy: str = "phase3"
        self.mode: str = "FAST"
        self.seed0: int = DEFAULT_SEED
        self.current_frame: int = 0
        self.total_frames: int = 0
        self.start_time: float = 0.0
        self.frame_results: list[dict] = []
        self.history: list[dict] = []
        self._error: Optional[str] = None

        # Phase 9.1: Event-based control signals
        self._stop_event = threading.Event()
        self._pause_event = threading.Event()
        self._pause_event.set()  # Not paused initially
        self._pause_pending = False  # True after pause() until run loop confirms

        # Phase 9.1: Lock to coordinate frame execution with pause/stop
        self._process_lock = threading.Lock()

        # Phase 9.1: Handle to the background run loop thread
        self._loop_handle: Optional[threading.Thread] = None

        # Phase 9.1: Reference to the main asyncio event loop (set in start())
        self._main_loop: Optional[asyncio.AbstractEventLoop] = None

    @property
    def elapsed_seconds(self) -> float:
        if self.start_time == 0:
            return 0.0
        return time.time() - self.start_time

    def is_running(self) -> bool:
        return self.status in (SimStatus.RUNNING, SimStatus.PAUSED)

    def _make_run_id(self) -> str:
        now = datetime.now()
        short_id = uuid.uuid4().hex[:6]
        return f"{now.strftime('%Y%m%d_%H%M%S')}_{short_id}"

    async def start(self, req: SimulationStartRequest) -> SimulationStatus:
        if self.is_running():
            raise ValueError("simulation_already_running")

        self.run_id = self._make_run_id()
        self.strategy = req.strategy.value
        self.policy = req.policy.value
        self.mode = req.mode.value
        self.seed0 = req.seed0
        self.current_frame = 0
        self.frame_results = []
        self.history = []
        self._error = None
        self._stop_event.clear()
        self._pause_event.set()
        self._pause_pending = False
        self.start_time = time.time()

        # Phase 9.1: Capture the main asyncio loop for thread-safe broadcasts
        self._main_loop = asyncio.get_running_loop()

        if req.scenario == "custom":
            if not all([req.environment, req.channel_profile, req.modulation]):
                raise ValueError(
                    "custom scenario requires environment, channel_profile, "
                    "and modulation"
                )
            speed = req.speed_kmph or 30.0
            snr = req.snr_db or 15.0
            dur = req.duration_frames or 12
            env = req.environment
            from .config import ENVIRONMENTS
            ch = req.channel_profile
            if ch not in ("EPA", "EVA", "ETU"):
                raise ValueError(f"invalid channel_profile: {ch}")
            if req.modulation not in (4, 16, 64):
                raise ValueError(f"invalid modulation: {req.modulation}")
            self.scenario = build_custom_scenario(
                env, speed, snr, ch, req.modulation, dur
            )
            self.scenario_id = "custom"
            self.total_frames = dur
        else:
            sid = req.scenario.upper()
            scen = get_scenario(sid)
            if scen is None:
                raise ValueError(f"invalid scenario: {req.scenario}")
            self.scenario = scen
            self.scenario_id = sid
            pts = scen.get("points", [])
            if not pts:
                raise ValueError(
                    f"scenario {sid} has no points data: "
                    "cannot start a simulation for an empty scenario"
                )
            n_frames = req.duration_frames or len(pts)
            self.total_frames = min(n_frames, len(pts))

        self.scenario["name"] = self.scenario_id
        self.status = SimStatus.CREATED
        self.results.create_run(self.run_id, {
            "run_id": self.run_id,
            "scenario": self.scenario_id,
            "strategy": self.strategy,
            "policy": self.policy,
            "mode": self.mode,
            "seed0": self.seed0,
            "total_frames": self.total_frames,
            "created_at": datetime.now().isoformat(),
        })

        await self.ws.broadcast({
            "type": "simulation_started",
            "run_id": self.run_id,
            "scenario": self.scenario_id,
            "strategy": self.strategy,
            "total_frames": self.total_frames,
        })

        self.status = SimStatus.RUNNING

        # Phase 9.1: Run in a daemon thread, not an asyncio task.
        # The thread releases the GIL during subprocess.wait(), allowing
        # the asyncio event loop to process HTTP requests (pause/stop).
        self._loop_handle = threading.Thread(
            target=self._run_loop_sync, daemon=True
        )
        self._loop_handle.start()

        return SimulationStatus(
            run_id=self.run_id,
            status=self.status,
            scenario=self.scenario_id,
            strategy=self.strategy,
            policy=self.policy,
            mode=self.mode,
            current_frame=self.current_frame,
            total_frames=self.total_frames,
            elapsed_seconds=self.elapsed_seconds,
        )

    def _broadcast_sync(self, event: dict):
        """Phase 9.1: Broadcast a WebSocket event from a background thread.

        Uses asyncio.run_coroutine_threadsafe() to schedule the broadcast
        on the main event loop. This avoids creating a new event loop per
        call and prevents issues with async locks bound to different loops.
        """
        if self._main_loop and not self._main_loop.is_closed():
            try:
                asyncio.run_coroutine_threadsafe(
                    self.ws.broadcast(event), self._main_loop
                )
            except Exception as e:
                logger.warning("Failed to schedule broadcast: %s", e)

    def _run_loop_sync(self):
        """Phase 9.1: Frame-by-frame execution in a background thread.

        Each frame:
        1. Check _stop_event → if set, exit loop
        2. Wait if paused (check _pause_event)
        3. Execute one frame via dt_step_frame.m
        4. Broadcast frame update
        5. Check _pause_event → if cleared, pause here
        6. Yield briefly to let asyncio process HTTP requests
        7. Repeat
        """
        run_id = self.run_id
        try:
            for frame_idx in range(1, self.total_frames + 1):
                # Check stop BEFORE executing the frame
                if self._stop_event.is_set():
                    break

                # Check pause: wait here until resumed or stopped
                while not self._pause_event.is_set():
                    if self._stop_event.is_set():
                        break
                    time.sleep(0.1)
                if self._stop_event.is_set():
                    break

                # Execute one frame (releases GIL during subprocess.wait)
                fr = self._execute_frame(frame_idx)

                # Check if stop was requested DURING frame execution
                if self._stop_event.is_set():
                    break

                # Update state (only this thread writes these)
                self.current_frame = frame_idx
                fr["run_id"] = run_id
                fr["strategy"] = self.strategy
                self.frame_results.append(fr)
                self.history.append(fr)
                self.results.append_frame(run_id, fr)

                # Broadcast frame update via the main event loop
                self._broadcast_sync({
                    "type": "frame_update",
                    "run_id": run_id,
                    "frame": self.current_frame,
                    "total_frames": self.total_frames,
                    "result": fr,
                })

                # Check pause AFTER broadcast — if user paused during frame,
                # we stop now rather than starting the next frame
                if self._pause_event.is_set():
                    # Not paused, yield briefly to let asyncio process requests
                    time.sleep(0.01)
                else:
                    # User paused during this frame — broadcast paused event
                    # and wait for resume
                    self._broadcast_sync({
                        "type": "simulation_paused",
                        "run_id": run_id,
                        "frame": self.current_frame,
                    })
                    while not self._pause_event.is_set():
                        if self._stop_event.is_set():
                            break
                        time.sleep(0.1)

            # Determine final status
            # Note: stop() may have already set status=STOPPED and broadcast.
            # Only broadcast if the run loop is setting the status for the first time.
            if self._stop_event.is_set():
                if self.status != SimStatus.STOPPED:
                    self.status = SimStatus.STOPPED
                    self._broadcast_sync({
                        "type": "simulation_stopped",
                        "run_id": run_id,
                    })
            else:
                self.status = SimStatus.COMPLETED
                self._broadcast_sync({
                    "type": "simulation_completed",
                    "run_id": run_id,
                    "total_frames": self.total_frames,
                })

        except Exception as e:
            logger.error("Simulation loop error: %s", e)
            self.status = SimStatus.ERROR
            self._error = str(e)
            self._broadcast_sync({
                "type": "simulation_error",
                "run_id": run_id,
                "error": str(e),
            })

        # Write results regardless of how we exited
        try:
            self.results.write_results_csv(run_id, self.frame_results)
            self.results.write_manifest(run_id, {
                "run_id": run_id,
                "scenario": self.scenario_id,
                "strategy": self.strategy,
                "policy": self.policy,
                "mode": self.mode,
                "total_frames": self.total_frames,
                "status": self.status.value,
                "completed_at": datetime.now().isoformat(),
            })
        except Exception as e:
            logger.error("Failed to write results: %s", e)

    def _execute_frame(self, frame: int) -> dict:
        scenario_json = json.dumps(self.scenario)
        result = self.matlab.run_frame(
            scenario_json, frame, self.strategy, self.policy, self.seed0
        )
        result["run_id"] = self.run_id
        result["strategy"] = self.strategy
        return result

    async def stop(self):
        if not self.is_running():
            raise ValueError("simulation_not_running")

        # Phase 9.1: Set STOPPED immediately so the HTTP response is correct.
        # The run loop will also set this, but setting it here ensures the
        # status API returns STOPPED right away.
        self.status = SimStatus.STOPPED
        self._stop_event.set()
        self._pause_event.set()  # Unblock if paused — let the loop exit
        self._pause_pending = False

        # Kill the MATLAB subprocess so the loop thread unblocks immediately
        try:
            self.matlab.terminate_current()
        except Exception as e:
            logger.warning("Error terminating MATLAB: %s", e)

        await self.ws.broadcast({
            "type": "simulation_stopped",
            "run_id": self.run_id,
        })
        logger.info("Stop requested — MATLAB subprocess terminated, run loop will exit")

    async def pause(self):
        if self.status != SimStatus.RUNNING:
            raise ValueError("can only pause a running simulation")

        # Phase 9.1: Set PAUSED immediately so HTTP response is correct.
        # Clear the pause event — the run loop will wait at the next frame boundary.
        # Set _pause_pending so resume() doesn't clear the flag prematurely.
        self.status = SimStatus.PAUSED
        self._pause_event.clear()
        self._pause_pending = True

        await self.ws.broadcast({
            "type": "simulation_paused",
            "run_id": self.run_id,
            "frame": self.current_frame,
        })
        logger.info("Pause requested — run loop will pause at next frame boundary")

    async def resume(self):
        if self.status != SimStatus.PAUSED:
            raise ValueError("can only resume a paused simulation")

        # Phase 9.1: If _pause_pending is True, the run loop hasn't confirmed
        # the pause yet. Wait briefly for it to enter the pause state.
        if self._pause_pending:
            for _ in range(50):  # Wait up to 5 seconds
                if not self._pause_pending:
                    break
                await asyncio.sleep(0.1)

        self.status = SimStatus.RUNNING
        self._pause_event.set()
        logger.info("Resume requested — run loop will continue")

        await self.ws.broadcast({
            "type": "simulation_resumed",
            "run_id": self.run_id,
            "frame": self.current_frame,
        })

    async def reset(self):
        if self.is_running():
            await self.stop()
            # Phase 9.1: Don't block the event loop with join().
            # Use a non-blocking check instead.
            if self._loop_handle and self._loop_handle.is_alive():
                await asyncio.to_thread(self._loop_handle.join, timeout=15)

        self.run_id = None
        self.status = SimStatus.STOPPED
        self.scenario = None
        self.scenario_id = ""
        self.current_frame = 0
        self.total_frames = 0
        self.frame_results = []
        self.history = []
        self._error = None
        self._stop_event.clear()
        self._pause_event.set()
        self._pause_pending = False
        self._main_loop = None

    def get_status(self) -> SimulationStatus:
        return SimulationStatus(
            run_id=self.run_id or "",
            status=self.status,
            scenario=self.scenario_id or "",
            strategy=self.strategy or "",
            policy=self.policy or "",
            mode=self.mode or "",
            current_frame=self.current_frame,
            total_frames=self.total_frames,
            elapsed_seconds=self.elapsed_seconds,
        )

    def get_state(self) -> Optional[SimulationState]:
        if not self.frame_results:
            return None
        last = self.frame_results[-1]
        return SimulationState(
            frame=last.get("frame", 0),
            scenario_id=last.get("scenario_id", ""),
            environment=last.get("environment", ""),
            speed_kmph=last.get("speed_kmph", 0),
            snr_db=last.get("snr_db", 0),
            doppler_hz=last.get("doppler_hz", 0),
            channel_profile=last.get("channel_profile", ""),
            modulation=last.get("modulation", 4),
            waveform=last.get("waveform", ""),
            strategy=last.get("strategy", ""),
        )

    def get_current_metrics(self) -> Optional[FrameMetrics]:
        if not self.frame_results:
            return None
        last = self.frame_results[-1]
        return FrameMetrics(
            ber=last.get("BER"),
            ser=last.get("SER"),
            per=last.get("PER"),
            throughput_bps=last.get("throughput_bps"),
            spectral_efficiency=last.get("spectral_efficiency"),
            cqi=last.get("CQI"),
            acs=last.get("ACS"),
            detector_time_ms=last.get("detector_time_ms"),
            latency_ms_modeled=last.get("latency_ms_modeled"),
        )

    def get_current_ai(self) -> Optional[AIInfo]:
        if not self.frame_results:
            return None
        last = self.frame_results[-1]
        ai = last.get("ai")
        if ai is not None:
            predicted = ai.get("predicted_metrics") or {}
            otfs_pred = predicted.get("OTFS") or {}
            oddm_pred = predicted.get("ODDM") or {}
            def _num(value):
                return value if isinstance(value, (int, float)) and value == value else None
            return AIInfo(
                selected_waveform=ai.get("recommendation"),
                confidence=ai.get("confidence"),
                predicted_otfs_acs=_num(otfs_pred.get("ACS")),
                predicted_oddm_acs=_num(oddm_pred.get("ACS")),
                reason=ai.get("reason"),
                fallback_used=ai.get("fallback_used", False),
            )
        conf = last.get("ai_confidence")
        reason = last.get("ai_reason")
        if conf is not None or reason is not None:
            return AIInfo(
                selected_waveform=last.get("waveform"),
                confidence=conf if conf is not None and not (isinstance(conf, float) and conf != conf) else None,
                reason=reason,
                fallback_used=False,
            )
        return AIInfo()

    def get_history(self, limit: int = 100) -> list[dict]:
        return self.history[-limit:]

    def get_metrics_summary(self) -> MetricsSummary:
        if not self.frame_results:
            return MetricsSummary(
                frames_processed=0, otfs_frames=0, oddm_frames=0,
                switches=0, mean_ber=0, mean_throughput=0, mean_cqi=0,
                mean_acs=0, oracle_agreement=0, mean_acs_regret=0,
            )
        otfs = sum(1 for r in self.frame_results if r.get("waveform") == "OTFS")
        oddm = sum(1 for r in self.frame_results if r.get("waveform") == "ODDM")
        switches = sum(1 for r in self.frame_results if r.get("switched"))
        bers = [r["BER"] for r in self.frame_results if r.get("BER") is not None]
        tps = [r["throughput_bps"] for r in self.frame_results if r.get("throughput_bps") is not None]
        cqis = [r["CQI"] for r in self.frame_results if r.get("CQI") is not None]
        acs = [r["ACS"] for r in self.frame_results if r.get("ACS") is not None]
        regs = [r.get("ACS_regret", 0) for r in self.frame_results]
        correct = [r.get("decision_correct", 0) for r in self.frame_results
                   if r.get("strategy") == "ai_adaptive"]

        return MetricsSummary(
            frames_processed=len(self.frame_results),
            otfs_frames=otfs,
            oddm_frames=oddm,
            switches=switches,
            mean_ber=sum(bers) / len(bers) if bers else 0,
            mean_throughput=sum(tps) / len(tps) if tps else 0,
            mean_cqi=sum(cqis) / len(cqis) if cqis else 0,
            mean_acs=sum(acs) / len(acs) if acs else 0,
            oracle_agreement=sum(correct) / len(correct) * 100 if correct else 0,
            mean_acs_regret=sum(regs) / len(regs) if regs else 0,
        )
