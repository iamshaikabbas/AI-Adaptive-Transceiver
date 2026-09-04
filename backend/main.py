"""Phase 8 Backend — FastAPI application for the AI-Adaptive-Transceiver."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from .ai_bridge import AIBridge
from .config import (
    DEFAULT_POLICY,
    VALID_CHANNELS,
    VALID_MODULATIONS,
    VALID_POLICIES,
    VALID_STRATEGIES,
)
from .matlab_bridge import MATLABBridge
from .models import (
    ConfigResponse,
    CustomEvaluationRequest,
    CustomEvaluationResponse,
    CustomSchemaResponse,
    ErrorResponse,
    FrameResponse,
    HealthResponse,
    MetricsSummary,
    SimulationStartRequest,
    SimulationStatus,
    Strategy,
    WSFrameEvent,
)
from .result_service import ResultService
from .scenario_service import list_scenarios
from .simulation_manager import SimulationManager
from .websocket_manager import WebSocketManager
from .deployment_data_service import get_service as get_deployment_service

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

matlab_bridge = MATLABBridge()
ai_bridge = AIBridge()
result_service = ResultService()
ws_manager = WebSocketManager()
sim_manager = SimulationManager(matlab_bridge, ai_bridge, result_service, ws_manager)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Phase 8 backend starting...")
    matlab_bridge.check_available_async()
    ai_ok = ai_bridge.is_available()
    logger.info("AI engine available: %s", ai_ok)
    yield
    logger.info("Phase 8 backend shutting down.")
    matlab_bridge.cleanup()


app = FastAPI(
    title="AI-Adaptive-Transceiver API",
    description="Phase 8 Backend API for the AI-Adaptive-Transceiver Digital Twin",
    version="8.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
        "https://ai-adaptive-transceiver-73zjb4fhm-iamshaikabbas-projects.vercel.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health", response_model=HealthResponse, tags=["System"])
async def health():
    matlab_ok = matlab_bridge.is_available()
    ai_ok = ai_bridge.is_available()
    return HealthResponse(
        status="ok",
        service="AI-Adaptive-Transceiver",
        phase=8,
        policy=DEFAULT_POLICY,
        digital_twin="available" if matlab_ok else "unavailable",
        matlab="available" if matlab_ok else "unavailable",
        ai_engine="available" if ai_ok else "unavailable",
    )


@app.get("/api/config", response_model=ConfigResponse, tags=["System"])
async def config():
    from .config import ENVIRONMENTS
    return ConfigResponse(
        default_policy=DEFAULT_POLICY,
        available_policies=VALID_POLICIES,
        available_strategies=VALID_STRATEGIES,
        supported_environments=list(ENVIRONMENTS.keys()),
        supported_channels=VALID_CHANNELS,
        supported_modulations=VALID_MODULATIONS,
        simulation_modes=["FAST", "FULL"],
    )


@app.get("/api/scenarios", tags=["Scenarios"])
async def scenarios():
    return list_scenarios()


@app.get("/api/scenarios/{scenario_id}", tags=["Scenarios"])
async def scenario_detail(scenario_id: str):
    from .scenario_service import get_scenario
    s = get_scenario(scenario_id)
    if s is None:
        raise HTTPException(status_code=404, detail=f"Scenario {scenario_id} not found")
    if "points" in s:
        s["points"] = s["points"][:5]
        s["note"] = f"Showing first 5 of {len(s.get('points', []))} points"
    return s


@app.post("/api/simulation/start", response_model=SimulationStatus, tags=["Simulation"])
async def simulation_start(req: SimulationStartRequest):
    try:
        return await sim_manager.start(req)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@app.post("/api/simulation/stop", tags=["Simulation"])
async def simulation_stop():
    try:
        await sim_manager.stop()
        return {"status": "stopped", "run_id": sim_manager.run_id}
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@app.post("/api/simulation/pause", tags=["Simulation"])
async def simulation_pause():
    try:
        await sim_manager.pause()
        return {"status": "paused", "run_id": sim_manager.run_id}
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@app.post("/api/simulation/resume", tags=["Simulation"])
async def simulation_resume():
    try:
        await sim_manager.resume()
        return {"status": "resumed", "run_id": sim_manager.run_id}
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@app.post("/api/simulation/reset", tags=["Simulation"])
async def simulation_reset():
    await sim_manager.reset()
    return {"status": "reset"}


@app.get("/api/simulation/status", response_model=SimulationStatus, tags=["Simulation"])
async def simulation_status():
    return sim_manager.get_status()


@app.get("/api/simulation/state", tags=["Simulation"])
async def simulation_state():
    state = sim_manager.get_state()
    if state is None:
        return {"status": "simulation_not_running"}
    return state


@app.get("/api/simulation/result", tags=["Simulation"])
async def simulation_result():
    if not sim_manager.frame_results:
        return {"status": "no_results"}
    last = sim_manager.frame_results[-1]
    return last


@app.get("/api/simulation/history", tags=["Simulation"])
async def simulation_history(limit: int = 100):
    return sim_manager.get_history(limit=limit)


@app.post("/api/simulation/step", tags=["Simulation"])
async def simulation_step():
    if sim_manager.status.value == "CREATED":
        sim_manager.current_frame += 1
        frame_result = sim_manager._execute_frame(sim_manager.current_frame)
        sim_manager.frame_results.append(frame_result)
        sim_manager.history.append(frame_result)
        return frame_result
    raise HTTPException(
        status_code=409,
        detail="step only available in CREATED state (use start for full run)",
    )


@app.get("/api/metrics/summary", response_model=MetricsSummary, tags=["Metrics"])
async def metrics_summary():
    return sim_manager.get_metrics_summary()


@app.get("/api/metrics/current", tags=["Metrics"])
async def metrics_current():
    m = sim_manager.get_current_metrics()
    if m is None:
        return {"status": "no_metrics"}
    ai = sim_manager.get_current_ai()
    return {"metrics": m, "ai": ai}


@app.get("/api/strategies", tags=["Config"])
async def strategies():
    return [{"id": s, "name": s.replace("_", " ").title()} for s in VALID_STRATEGIES]


@app.get("/api/policies", tags=["Config"])
async def policies():
    return [
        {"id": "phase3", "name": "Phase 3", "description": "Canonical AI adaptive policy", "default": True},
        {"id": "phase4", "name": "Phase 4", "description": "Experimental banded confidence policy", "default": False},
    ]


@app.get("/api/graphs/index", tags=["Graphs"])
async def graphs_index():
    index_path = Path(__file__).resolve().parent.parent / "OTFS MRC detection MATLAB code" / "Results" / "FinalEvaluation" / "Visualizations" / "graph_index.json"
    if not index_path.exists():
        raise HTTPException(status_code=404, detail="graph_index.json not found")
    import json
    return json.loads(index_path.read_text(encoding="utf-8"))


@app.get("/api/graphs/{filename}", tags=["Graphs"])
async def graph_file(filename: str):
    viz_dir = Path(__file__).resolve().parent.parent / "OTFS MRC detection MATLAB code" / "Results" / "FinalEvaluation" / "Visualizations"
    # PNGs are in category subdirectories
    for subdir in viz_dir.iterdir():
        if subdir.is_dir():
            file_path = subdir / filename
            if file_path.exists() and file_path.suffix == ".png":
                return FileResponse(file_path, media_type="image/png")
    raise HTTPException(status_code=404, detail="Graph not found")


@app.websocket("/ws/simulation")
async def websocket_simulation(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        await ws_manager.disconnect(websocket)
    except Exception:
        await ws_manager.disconnect(websocket)


# ── Evals Platform ──────────────────────────────────────────────────────────

_eval_runner = None


def _get_eval_runner():
    global _eval_runner
    if _eval_runner is None:
        from .evals.runner import EvalRunner
        _eval_runner = EvalRunner()
    return _eval_runner


@app.get("/api/evals/golden-dataset", tags=["Evals Platform"])
async def evals_golden_dataset():
    """Return the Golden Dataset manifest with integrity verification."""
    from .evals.golden_dataset import get_golden_dataset
    ds = get_golden_dataset()
    return ds.build_manifest().model_dump()


@app.get("/api/evals/suites", tags=["Evals Platform"])
async def evals_suites():
    """List available evaluation suites."""
    return [
        {"id": "FULL_REGRESSION", "name": "Full Regression", "description": "EXACT + INTERIOR + BOUNDARY + OOD cases"},
        {"id": "PREDICTION_ACCURACY", "name": "Prediction Accuracy", "description": "EXACT cases only — compare AI prediction vs golden ground truth"},
        {"id": "OOD_SAFETY", "name": "OOD Safety", "description": "Out-of-domain cases — verify AI correctly rejects invalid inputs"},
        {"id": "ROBUSTNESS", "name": "Robustness", "description": "BOUNDARY + OOD cases — test near-boundary and invalid behavior"},
    ]


@app.post("/api/evals/run", tags=["Evals Platform"])
async def evals_start_run(suite: str = "FULL_REGRESSION"):
    """Start a new evaluation run."""
    from .evals.schemas import EvalSuite, EvalRunConfig

    suite_map = {
        "FULL_REGRESSION": EvalSuite.FULL_REGRESSION,
        "PREDICTION_ACCURACY": EvalSuite.PREDICTION_ACCURACY,
        "OOD_SAFETY": EvalSuite.OOD_SAFETY,
        "ROBUSTNESS": EvalSuite.ROBUSTNESS,
    }

    if suite not in suite_map:
        raise HTTPException(status_code=400, detail=f"Invalid suite: {suite}. Valid: {list(suite_map.keys())}")

    runner = _get_eval_runner()
    if runner.is_running():
        raise HTTPException(status_code=409, detail="An evaluation run is already active")

    config = EvalRunConfig(suite=suite_map[suite])

    # Capture the current asyncio event loop so the background eval thread can
    # schedule async WebSocket broadcasts onto it (the established
    # sync->async bridge pattern used by SimulationManager._broadcast_sync).
    import asyncio
    main_loop = asyncio.get_running_loop()

    def on_progress(summary, case_result, graph_data):
        # Synchronous callback invoked from EvalRunner's background thread.
        # Bridge to the async WebSocket broadcast on the main event loop.
        import asyncio as aio
        event = {
            "type": "eval_progress",
            "run_id": summary.run_id,
            "timestamp": _eval_now_iso(),
            "progress_pct": summary.progress_pct,
            "completed_cases": summary.completed_cases,
            "total_cases": summary.total_cases,
            "elapsed_seconds": round(summary.elapsed_seconds, 3),
            "current_case_id": summary.current_case_id,
            "current_case_type": summary.current_case_type.value if summary.current_case_type else None,
            "status": summary.status.value,
            "passed": summary.passed,
            "failed": summary.failed,
            "rejected": summary.rejected,
            "unavailable": summary.unavailable,
        }
        if case_result is not None:
            event["case_result"] = case_result.model_dump() if hasattr(case_result, 'model_dump') else case_result
        if graph_data:
            event["graph_data"] = {k: v[-1] if v else None for k, v in graph_data.items()}
            event["graph_data_full"] = graph_data

        if main_loop and not main_loop.is_closed():
            try:
                aio.run_coroutine_threadsafe(ws_manager.broadcast(event), main_loop)
            except Exception:
                pass

    try:
        summary = runner.start_run(config, on_progress=on_progress)
        return summary.model_dump()
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@app.post("/api/evals/stop", tags=["Evals Platform"])
async def evals_stop_run():
    """Stop the active evaluation run."""
    runner = _get_eval_runner()
    if not runner.is_running():
        raise HTTPException(status_code=409, detail="No active evaluation run")
    runner.stop_run()
    return {"status": "stopping"}


@app.get("/api/evals/runs", tags=["Evals Platform"])
async def evals_list_runs():
    """List all completed evaluation runs."""
    runner = _get_eval_runner()
    return runner.list_runs()


@app.get("/api/evals/runs/{run_id}", tags=["Evals Platform"])
async def evals_get_run(run_id: str):
    """Get full evaluation run data."""
    runner = _get_eval_runner()
    run_data = runner.get_run(run_id)
    if run_data is None:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    return run_data


@app.get("/api/evals/runs/{run_id}/cases", tags=["Evals Platform"])
async def evals_get_cases(run_id: str):
    """Get case results for a run."""
    runner = _get_eval_runner()
    run_data = runner.get_run(run_id)
    if run_data is None:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    return run_data.get("cases", [])


@app.get("/api/evals/runs/{run_id}/report", tags=["Evals Platform"])
async def evals_get_report(run_id: str):
    """Get evaluation report for a run."""
    runner = _get_eval_runner()
    run_data = runner.get_run(run_id)
    if run_data is None:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    return run_data.get("report", {})


@app.get("/api/evals/runs/{run_id}/graphs", tags=["Evals Platform"])
async def evals_get_graphs(run_id: str):
    """Get graph data for a run."""
    runner = _get_eval_runner()
    run_data = runner.get_run(run_id)
    if run_data is None:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    return run_data.get("graph_data", {})


@app.get("/api/evals/compare/{run_a}/{run_b}", tags=["Evals Platform"])
async def evals_compare_runs(run_a: str, run_b: str):
    """Compare two completed evaluation runs."""
    runner = _get_eval_runner()
    data_a = runner.get_run(run_a)
    data_b = runner.get_run(run_b)
    if data_a is None:
        raise HTTPException(status_code=404, detail=f"Run {run_a} not found")
    if data_b is None:
        raise HTTPException(status_code=404, detail=f"Run {run_b} not found")

    from .evals.report import compare_runs
    from .evals.schemas import EvalRunSummary

    summary_a = EvalRunSummary(**data_a.get("summary", {}))
    summary_b = EvalRunSummary(**data_b.get("summary", {}))
    report_a = data_a.get("report", {})
    report_b = data_b.get("report", {})

    comparison = compare_runs(summary_a, summary_b, report_a, report_b)
    return comparison.model_dump()


@app.get("/api/evals/status", tags=["Evals Platform"])
async def evals_status():
    """Get current evaluation status."""
    runner = _get_eval_runner()
    return {
        "running": runner.is_running(),
        "active_run_id": runner.get_active_run_id(),
    }


def _eval_now_iso():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


@app.websocket("/ws/evals")
async def websocket_evals(websocket: WebSocket):
    """WebSocket for live evaluation progress updates."""
    await ws_manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        await ws_manager.disconnect(websocket)
    except Exception:
        await ws_manager.disconnect(websocket)


# ── Phase 11: Custom Evaluation (Deployment Mode) ───────────────────────────

@app.get("/api/custom/schema", response_model=CustomSchemaResponse, tags=["Custom Evaluation"])
async def custom_schema():
    """Return supported input schema for dynamic form generation."""
    svc = get_deployment_service()
    return svc.get_schema()


@app.post("/api/custom/evaluate", response_model=CustomEvaluationResponse, tags=["Custom Evaluation"])
async def custom_evaluate(req: CustomEvaluationRequest):
    """Evaluate a custom operating point using hybrid model-based deployment.

    Pipeline: exact lookup → nearest neighbors → RF regression →
    neighborhood consistency → coverage → confidence → Phase-3 decision.
    No MATLAB required.
    """
    svc = get_deployment_service()
    query = {
        "environment": req.environment,
        "speed_kmph": req.speed_kmph,
        "snr_db": req.snr_db,
        "channel_profile": req.channel_profile,
        "modulation": req.modulation,
        "detector": req.detector,
    }
    result = svc.evaluate(query)
    return svc.result_to_dict(result)
