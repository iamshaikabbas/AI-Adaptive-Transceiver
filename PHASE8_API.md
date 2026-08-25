# PHASE 8 API REFERENCE

## Backend

- **Location**: `backend/`
- **URL**: `http://127.0.0.1:8000`
- **Swagger**: `http://127.0.0.1:8000/docs`
- **ReDoc**: `http://127.0.0.1:8000/redoc`

## Setup

```bash
pip install -r backend/requirements.txt
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `MATLAB_EXECUTABLE` | `matlab` | Path to MATLAB executable |
| `MATLAB_PATH` | (fallback) | Alternative MATLAB path env var |

## Endpoints

### System

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/health` | Health check with MATLAB/AI status |
| GET | `/api/config` | Available policies, strategies, environments, channels, modulations |

### Scenarios

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/scenarios` | List all 18 scenarios (A-R) with frame counts |
| GET | `/api/scenarios/{id}` | Scenario detail (first 5 points) |

### Simulation Lifecycle

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/simulation/start` | Start simulation (async, returns immediately) |
| POST | `/api/simulation/stop` | Stop running simulation |
| POST | `/api/simulation/pause` | Pause (blocks frame advancement) |
| POST | `/api/simulation/resume` | Resume paused simulation |
| POST | `/api/simulation/reset` | Clear current run state |
| GET | `/api/simulation/status` | Current status (run_id, frame, total, elapsed) |
| GET | `/api/simulation/state` | Current frame state (environment, speed, SNR, etc.) |
| GET | `/api/simulation/result` | Latest frame result with metrics |
| GET | `/api/simulation/history?limit=100` | Frame history |
| POST | `/api/simulation/step` | Advance one frame (CREATED state only) |

### Metrics

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/metrics/summary` | Aggregated metrics (BER, throughput, ACS, etc.) |
| GET | `/api/metrics/current` | Current frame metrics + AI decision |

### Configuration

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/strategies` | Available strategies |
| GET | `/api/policies` | Available policies (phase3=canonical, phase4=experimental) |

### WebSocket

| Protocol | Path | Description |
|----------|------|-------------|
| WS | `/ws/simulation` | Real-time frame update streaming |

## Request Examples

### Start FAST simulation

```json
POST /api/simulation/start
{
  "mode": "FAST",
  "scenario": "A",
  "strategy": "ai_adaptive",
  "policy": "phase3",
  "seed0": 20260823
}
```

### Start custom scenario

```json
POST /api/simulation/start
{
  "mode": "FAST",
  "scenario": "custom",
  "environment": "Urban",
  "speed_kmph": 100,
  "snr_db": 12,
  "channel_profile": "EVA",
  "modulation": 4,
  "strategy": "ai_adaptive",
  "policy": "phase3",
  "duration_frames": 30
}
```

## Response Examples

### Health

```json
{
  "status": "ok",
  "service": "AI-Adaptive-Transceiver",
  "phase": 8,
  "policy": "phase3",
  "digital_twin": "available",
  "matlab": "available",
  "ai_engine": "available"
}
```

### Simulation Status

```json
{
  "run_id": "20260825_201530_abc123",
  "status": "COMPLETED",
  "scenario": "A",
  "strategy": "ai_adaptive",
  "policy": "phase3",
  "mode": "FAST",
  "current_frame": 12,
  "total_frames": 12,
  "elapsed_seconds": 45.2
}
```

### Frame Result

```json
{
  "run_id": "20260825_201530_abc123",
  "frame": 5,
  "environment": "Urban",
  "speed_kmph": 42.3,
  "snr_db": 13.5,
  "waveform": "OTFS",
  "BER": 0.0012,
  "throughput_bps": 285000,
  "ACS": 0.72,
  "oracle_waveform": "OTFS",
  "decision_correct": 1
}
```

## WebSocket Protocol

### Events

| Type | Description |
|------|-------------|
| `simulation_started` | Simulation initiated |
| `frame_update` | New frame completed |
| `simulation_completed` | All frames done |
| `simulation_paused` | Paused |
| `simulation_resumed` | Resumed |
| `simulation_stopped` | Stopped |
| `simulation_error` | Error occurred |

### Frame Update Event

```json
{
  "type": "frame_update",
  "run_id": "20260825_201530_abc123",
  "frame": 5,
  "total_frames": 12,
  "result": { ... }
}
```

## State Machine

```
CREATED -> RUNNING -> PAUSED -> RUNNING -> COMPLETED
                  \-> STOPPED
         -> STOPPED (direct)
```

Valid transitions:
- `CREATED` -> `RUNNING`
- `RUNNING` -> `PAUSED`, `STOPPED`, `COMPLETED`
- `PAUSED` -> `RUNNING`, `STOPPED`
- `STOPPED` -> (terminal)
- `COMPLETED` -> (terminal)

## Error Codes

| Code | Meaning |
|------|---------|
| 200 | Success |
| 409 | Conflict (simulation already running, invalid state transition) |
| 422 | Validation error (invalid strategy/policy/mode) |
| 500 | Internal server error |

## Limitations

- One active simulation per backend instance
- MATLAB subprocess execution takes ~30-60s per batch run
- `latency_ms_modeled` is always null (not modeled)
- No authentication (local research application only)
