# PHASE 8 ARCHITECTURE

## Overview

Phase 8 adds a Python FastAPI backend that exposes the existing MATLAB/Python Digital Twin through a clean local REST API + WebSocket interface for the future Phase 9 frontend.

## Architecture Diagram

```
                    PHASE 9 FRONTEND
                         |
                         | HTTP / WebSocket
                         v
                +-----------------+
                |   PHASE 8 API   |  FastAPI + uvicorn
                |  backend/main.py|
                +--------+--------+
                         |
             +-----------+-----------+
             v                       v
    backend/ai_bridge.py     backend/matlab_bridge.py
    AIEngineV2 (Python)      subprocess (MATLAB)
             |                       |
             v                       v
    models/metric_models_v2/   dt_run_scenario.m
    6 RandomForest regs             |
             |                 run_otfs.m / run_oddm.m
             +-----------+-----------+
                         v
                  Communication Metrics
                         |
                         v
                     ACS Score
```

## Components

### `backend/main.py`
- FastAPI application with all REST endpoints
- CORS configured for localhost:5173/5174
- OpenAPI/Swagger at `/docs`
- WebSocket endpoint at `/ws/simulation`

### `backend/models.py`
- Pydantic v2 request/response schemas
- Strategy, Policy, SimMode, SimStatus enums
- Consistent error handling models

### `backend/config.py`
- Environment variables (MATLAB_EXECUTABLE)
- Path constants (MATLAB_DIR, OTFS_PIPELINE, etc.)
- Valid strategy/policy/channel/modulation lists
- Environment profile definitions from environment_profiles_v2.csv

### `backend/matlab_bridge.py`
- Subprocess communication with MATLAB
- `run_scenario()` — batch execution via dt_run_scenario.m
- `run_frame()` — single frame via dt_step_frame.m
- Lazy async availability check (non-blocking startup)
- Configurable timeout (120s FAST, 600s FULL)

### `backend/ai_bridge.py`
- Loads AIEngineV2 from existing ai_engine_v2.py
- `decide(state)` — AI waveform decision
- `predict_metrics(waveform, state)` — metric prediction
- Graceful fallback on failure (keeps current waveform)

### `backend/simulation_manager.py`
- State machine: CREATED -> RUNNING -> PAUSED -> STOPPED -> COMPLETED
- Frame execution loop (calls MATLAB bridge)
- History tracking and metrics aggregation
- WebSocket broadcasting for real-time updates
- One active simulation per backend instance

### `backend/scenario_service.py`
- Maps API scenario IDs to Phase 5 scenario JSONs
- Custom scenario builder (environment, speed, SNR, channel, modulation)
- Reads from Results/DigitalTwin/scenario_*.json

### `backend/result_service.py`
- Persistence to Results/LiveSimulation/<run_id>/
- config.json, frames.csv, results.csv, events.jsonl, manifest.json
- Does NOT modify Phase 6 final_dataset.csv

### `backend/websocket_manager.py`
- WebSocket connection management
- Broadcast to all connected clients
- Dead connection cleanup

## MATLAB Integration

### New MATLAB Scripts

| File | Purpose |
|------|---------|
| `dt_run_scenario.m` | Batch frame execution for one scenario+strategy |
| `dt_step_frame.m` | Single-frame execution |

Both scripts use existing Phase 5 primitives (dt_state, dt_channel_for_frame, dt_exec_waveform, dt_ai_decide).

### Communication Method

Subprocess (`matlab -batch "..."`) — no MATLAB Engine API dependency.

## Data Flow

1. Frontend sends POST /api/simulation/start
2. SimulationManager creates run, starts async loop
3. MATLAB bridge calls dt_run_scenario.m via subprocess
4. MATLAB runs OTFS+ODDM for each frame, AI decides, computes metrics
5. Results returned as JSON array
6. Each frame result broadcast via WebSocket
7. Results persisted to Results/LiveSimulation/<run_id>/
8. Frontend polls GET /api/simulation/status for progress

## Security

- Local research application only
- CORS restricted to localhost
- No arbitrary MATLAB code execution from HTTP input
- No file system exposure
- Input validation via Pydantic models
