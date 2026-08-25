# PHASE 10 — Integration Documentation

## Frontend–Backend Connections

All connections verified via `phase10_validation.py` (25/25 PASS).

### REST API (17 endpoints)

| Frontend Call | Backend Endpoint | Status |
|---|---|---|
| `api.health()` | `GET /api/health` | Verified |
| `api.getConfig()` | `GET /api/config` | Verified |
| `api.getScenarios()` | `GET /api/scenarios` | Verified |
| `api.getScenarioDetail(id)` | `GET /api/scenarios/{id}` | Verified |
| `api.startSimulation(req)` | `POST /api/simulation/start` | Verified |
| `api.stopSimulation()` | `POST /api/simulation/stop` | Verified |
| `api.pauseSimulation()` | `POST /api/simulation/pause` | Verified |
| `api.resumeSimulation()` | `POST /api/simulation/resume` | Verified |
| `api.resetSimulation()` | `POST /api/simulation/reset` | Verified |
| `api.stepSimulation()` | `POST /api/simulation/step` | Available |
| `api.getSimulationStatus()` | `GET /api/simulation/status` | Verified |
| `api.getSimulationState()` | `GET /api/simulation/state` | Verified |
| `api.getSimulationResult()` | `GET /api/simulation/result` | Verified |
| `api.getHistory(limit)` | `GET /api/simulation/history` | Verified |
| `api.getMetricsSummary()` | `GET /api/metrics/summary` | Verified |
| `api.getCurrentMetrics()` | `GET /api/metrics/current` | Verified |
| `api.getStrategies()` | `GET /api/strategies` | Verified |
| `api.getPolicies()` | `GET /api/policies` | Verified |

### New in Phase 10

| Endpoint | Purpose |
|---|---|
| `GET /api/graphs/index` | Returns `graph_index.json` (42 graph entries) |
| `GET /api/graphs/{filename}` | Serves PNG images from category subdirectories |

### WebSocket

| Endpoint | Purpose |
|---|---|
| `ws://127.0.0.1:8000/ws/simulation` | Real-time frame updates, simulation events |

WebSocket events handled by frontend:
- `frame_update` — Appends to frame history
- `simulation_started` — Starts polling
- `simulation_completed` / `simulation_stopped` / `simulation_error` — Stops polling, refreshes status
- `simulation_paused` / `simulation_resumed` — Refreshes status

### Polling

When simulation is RUNNING or PAUSED, frontend polls every 2 seconds:
- `GET /api/simulation/status`
- `GET /api/simulation/state`
- `GET /api/metrics/current`
- `GET /api/simulation/history?limit=200`

## MATLAB Lifecycle

Preserved from Phase 9.1:
- Frame-by-frame execution via `dt_step_frame.m`
- `Popen`-based subprocess with `_current_process` tracking
- Background daemon thread for simulation loop
- `threading.Event` for pause/stop signals
- `asyncio.run_coroutine_threadsafe` for thread-safe WebSocket broadcasts

## AI Integration

- Phase 3 policy remains canonical
- `ai_engine_v2.py` and `adaptive_config_v2.json` unchanged
- AI decisions appear in the AI Waveform Decision panel
- Predicted ACS for OTFS and ODDM displayed in comparison table

## Data Integrity

- Phase 6 dataset checksum: `faa877a248c0f599a87f21dabf4df358` — unchanged
- Phase 7 visualizations: 42 graphs — intact
- `graph_index.json` — intact, served via new API endpoint

## Known Limitations

1. Polling at 2s interval means up to 2s delay in status updates
2. WebSocket provides real-time frame updates but status polling supplements it
3. Graph images served from filesystem — no caching headers
4. No authentication or rate limiting on API endpoints
