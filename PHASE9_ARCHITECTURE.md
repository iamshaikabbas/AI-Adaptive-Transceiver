# Phase 9 Architecture — React/TypeScript Frontend

## System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│  Browser (React/TypeScript/Vite)                                │
│  http://localhost:5173                                          │
│                                                                 │
│  App.tsx                                                        │
│  ├── Header.tsx          (title, connection status, about)      │
│  ├── Sidebar.tsx         (nav: Overview, DigitalTwin, Analysis) │
│  └── Pages                                                    │
│       ├── Overview.tsx       (system status, info cards)        │
│       ├── DigitalTwinPage.tsx (main dashboard, 3-column)        │
│       ├── Analysis.tsx       (charts, metrics table)            │
│       └── About.tsx          (project info, phase history)      │
│                                                                 │
│  useSimulation hook  ─── state + polling + WebSocket            │
│  api.ts              ─── typed REST client (17 endpoints)       │
│  websocket.ts        ─── auto-reconnect WS client               │
└──────────────┬──────────────────────────┬───────────────────────┘
               │ HTTP (via Vite proxy)    │ WS (via Vite proxy)
               ▼                          ▼
┌─────────────────────────────────────────────────────────────────┐
│  Vite Dev Server (port 5173)                                    │
│  proxy: /api → http://127.0.0.1:8000                            │
│  proxy: /ws  → ws://127.0.0.1:8000                              │
└──────────────┬──────────────────────────┬───────────────────────┘
               │                          │
               ▼                          ▼
┌─────────────────────────────────────────────────────────────────┐
│  FastAPI Backend (port 8000)                                    │
│  backend/main.py                                                │
│  ├── /api/health, /api/config, /api/scenarios, ...              │
│  ├── /api/simulation/start|stop|pause|resume|reset|step         │
│  ├── /api/metrics/summary, /api/metrics/current                 │
│  └── /ws/simulation  (WebSocket frame events)                   │
│                                                                 │
│  simulation_manager.py  ── state machine, orchestrates run      │
│  matlab_bridge.py       ── subprocess calls to MATLAB            │
│  ai_bridge.py           ── Python RandomForest AI engine         │
│  scenario_service.py    ── 18 scenario definitions (A-R)         │
│  result_service.py      ── frame result storage                  │
│  websocket_manager.py   ── WS broadcast to connected clients     │
└──────────────┬──────────────────────────────────────────────────┘
               │ subprocess (30-60s per batch)
               ▼
┌─────────────────────────────────────────────────────────────────┐
│  MATLAB Digital Twin                                            │
│  dt_run_scenario.m   ── batch execution (12 or all frames)      │
│  dt_step_frame.m     ── single-frame execution                  │
│  otfs_detector.m     ── OTFS MRC detection                      │
│  oddm_detector.m     ── ODDM detection                          │
│  channel_model.m     ── 3GPP channel generation                 │
└─────────────────────────────────────────────────────────────────┘
```

## File Structure

```
frontend/
├── package.json                    # React 18, Recharts, Tailwind CSS
├── vite.config.ts                  # Vite config with /api and /ws proxy
├── tsconfig.json                   # TypeScript strict config
├── index.html                      # SPA entry point
├── src/
│   ├── main.tsx                    # ReactDOM.createRoot
│   ├── App.tsx                     # Router-less SPA with state-based nav
│   │
│   ├── types/
│   │   └── api.ts                  # 14 TypeScript interfaces (149 lines)
│   │
│   ├── services/
│   │   ├── api.ts                  # Typed REST client, 17 endpoints (57 lines)
│   │   └── websocket.ts            # Auto-reconnect WS, exponential backoff (90 lines)
│   │
│   ├── hooks/
│   │   └── useSimulation.ts        # Central state hook: polling + WS (239 lines)
│   │
│   ├── components/
│   │   ├── Header.tsx              # App header with connection indicator
│   │   ├── Sidebar.tsx             # Navigation sidebar
│   │   ├── SimulationControls.tsx  # Start/Stop/Pause/Resume/Reset buttons
│   │   ├── DigitalTwinViz.tsx      # SVG visualization: TX → Channel → RX
│   │   ├── AIDecisionPanel.tsx     # Waveform badge, ACS bars, AI reason
│   │   ├── LiveCharts.tsx          # Recharts mini line charts (BER, TP, CQI)
│   │   ├── Timeline.tsx            # Frame progress bar
│   │   ├── SwitchingBar.tsx        # OTFS/ODDM segment visualization
│   │   ├── OracleComparison.tsx    # Oracle vs AI comparison table
│   │   ├── WaveformComparison.tsx  # OTFS vs ODDM side-by-side metrics
│   │   ├── MetricCard.tsx          # Reusable metric display card
│   │   └── ConnectionStatus.tsx    # WebSocket connection indicator
│   │
│   └── pages/
│       ├── Overview.tsx            # System status, phase info cards
│       ├── DigitalTwinPage.tsx     # Main dashboard (3-column layout)
│       ├── Analysis.tsx            # Post-simulation analysis charts
│       └── About.tsx               # Project description, phase history
│
└── dist/                           # Vite build output
    ├── index.html
    └── assets/
        ├── index-[hash].js         # Bundled JS (~350 KB)
        └── index-[hash].css        # Bundled CSS (~25 KB)
```

## State Management

### `useSimulation` Hook (central state)

Uses React `useState` + `useEffect` + `useRef` for:

- **Connection status**: `connected | disconnected | connecting`
- **Simulation status**: polled every 2s when running (`simStatus`)
- **Simulation state**: environment, waveform, speed, SNR per frame (`simState`)
- **Current metrics**: BER, throughput, CQI, ACS, AI decision (`currentMetrics`)
- **Frame history**: array of `FrameResult` objects, max 200 frames
- **Reference data**: scenarios, strategies, policies, config

**Polling lifecycle**:
1. On mount: fetch config data + initial status
2. If simulation RUNNING or PAUSED: start 2-second polling interval
3. On `simulation_completed` / `simulation_error` via WS: stop polling, fetch final status
4. On unmount: cleanup polling interval + WS subscription

### WebSocket Integration

```
wsService.connect()      → opens ws://host/ws/simulation
wsService.subscribe(cb)  → registers frame event callback
wsService.disconnect()   → clean close
```

## API Layer

### REST Client (`api.ts`)

| Method | Endpoint | Returns |
|--------|----------|---------|
| `health()` | GET /api/health | `HealthResponse` |
| `getConfig()` | GET /api/config | `ConfigResponse` |
| `getScenarios()` | GET /api/scenarios | `ScenarioInfo[]` |
| `getScenarioDetail(id)` | GET /api/scenarios/:id | `ScenarioInfo` |
| `startSimulation(req)` | POST /api/simulation/start | `SimulationStatus` |
| `stopSimulation()` | POST /api/simulation/stop | `{ status, run_id }` |
| `pauseSimulation()` | POST /api/simulation/pause | `{ status, run_id }` |
| `resumeSimulation()` | POST /api/simulation/resume | `{ status, run_id }` |
| `resetSimulation()` | POST /api/simulation/reset | `{ status }` |
| `stepSimulation()` | POST /api/simulation/step | `SimulationStatus` |
| `getSimulationStatus()` | GET /api/simulation/status | `SimulationStatus` |
| `getSimulationState()` | GET /api/simulation/state | `SimulationState` |
| `getSimulationResult()` | GET /api/simulation/result | `FrameResult` |
| `getHistory(limit)` | GET /api/simulation/history | `FrameResult[]` |
| `getMetricsSummary()` | GET /api/metrics/summary | `MetricsSummary` |
| `getCurrentMetrics()` | GET /api/metrics/current | `CurrentMetricsResponse` |
| `getStrategies()` | GET /api/strategies | `StrategyInfo[]` |
| `getPolicies()` | GET /api/policies | `PolicyInfo[]` |

### WebSocket Client (`websocket.ts`)

- Auto-reconnect with exponential backoff: 1s → 2s → 4s → 8s → 16s → 30s (max)
- Intentional close flag prevents reconnect loop
- Subscribable via `wsService.subscribe(callback)`

**Protocol — Server → Client messages**:

| Event Type | Payload | Triggered When |
|------------|---------|----------------|
| `simulation_started` | `{ type, run_id, scenario, strategy }` | MATLAB subprocess begins |
| `frame_update` | `{ type, run_id, frame, result: FrameResult }` | Single frame completes |
| `simulation_completed` | `{ type, run_id }` | All frames done |
| `simulation_error` | `{ type, run_id, error }` | MATLAB or AI failure |

## Component Hierarchy

```
App
├── Header
│   ├── Title: "AI Adaptive Transceiver — Digital Twin"
│   └── ConnectionStatus (green/red dot)
├── Sidebar
│   ├── Overview (nav link)
│   ├── Digital Twin (nav link, main)
│   ├── Analysis (nav link)
│   └── About (nav link)
└── Page Content
    ├── Overview: status cards, phase timeline, quick stats
    ├── DigitalTwinPage (3-column layout):
    │   ├── Column 1 (Controls):
    │   │   ├── SimulationControls
    │   │   ├── Environment panel (SNR, speed, doppler)
    │   │   └── AIDecisionPanel
    │   ├── Column 2 (Visualization):
    │   │   ├── DigitalTwinViz (SVG TX→Channel→RX)
    │   │   ├── Timeline (frame progress)
    │   │   ├── SwitchingBar (OTFS/ODDM segments)
    │   │   └── WaveformComparison (OTFS vs ODDM)
    │   └── Column 3 (Metrics):
    │       ├── LiveCharts (BER, throughput, CQI mini charts)
    │       └── OracleComparison table
    ├── Analysis: full charts, metrics table, history
    └── About: project description, phase references
```

## Color Palette

| Element | Color | Hex |
|---------|-------|-----|
| Fixed OTFS | Blue | `#2196F3` |
| Fixed OTFS (green accent) | Green | `#4CAF50` |
| Fixed ODDM | Orange | `#FF9800` |
| Fixed ODDM (blue accent) | Blue | `#2196F3` |
| AI Adaptive | Green | `#4CAF50` |
| Oracle | Purple | `#9C27B0` |
| Background | Dark gray | `gray-950` |
| Cards | Dark gray | `gray-900` |
| Text | White/gray | `white` / `gray-400` |

## Vite Proxy Configuration

```typescript
// vite.config.ts
server: {
  port: 5173,
  proxy: {
    '/api': {
      target: 'http://127.0.0.1:8000',
      changeOrigin: true,
    },
    '/ws': {
      target: 'ws://127.0.0.1:8000',
      ws: true,
    },
  },
},
```

This eliminates CORS issues during development and means the frontend code uses empty-base-url fetch (`const BASE = ""`).

## Design Principles

1. **No fabricated data** — all values come from real API responses
2. **Real-time updates** — WebSocket `frame_update` events for live data
3. **Graceful degradation** — polling fallback if WS disconnects
4. **Dark theme** — consistent `bg-gray-950` background
5. **State-aware UI** — buttons disabled/enabled based on simulation status
6. **No router** — simple state-based navigation via `useState`
