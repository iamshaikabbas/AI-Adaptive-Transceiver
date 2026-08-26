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
