# PHASE 9.1 — PAUSE / STOP Fix

## Root Cause

The original `matlab_bridge.py` used `subprocess.run()` (synchronous) to invoke MATLAB for
each frame. This blocked the GIL for 30–60 seconds per frame. While blocked:

- The FastAPI event loop could not accept HTTP requests
- PAUSE and STOP commands timed out
- The simulation appeared "frozen" to the frontend

## Solution

### 1. Frame-by-frame MATLAB execution (`matlab_bridge.py`)

Replaced `subprocess.run()` with `subprocess.Popen()` for each frame invocation of
`dt_step_frame.m`. Added a `_current_process` handle per-run so that `terminate_current()`
can kill only the active MATLAB subprocess — never `taskkill /IM matlab.exe`.

Key methods:
- `run_frame(scenario_json, frame, strategy, policy, seed)` — spawns MATLAB, captures
  stdout, returns parsed JSON
- `terminate_current()` — kills only the tracked `_current_process`
- `close()` — full cleanup

### 2. Non-blocking run loop (`simulation_manager.py`)

Moved the frame-by-frame loop into a **background daemon thread** so it no longer blocks
the asyncio event loop. Inter-frame pause/stop is controlled by `threading.Event` objects:

| Signal | Mechanism |
|---|---|
| STOP | `threading.Event` `_stop_event` + `terminate_current()` |
| PAUSE | `threading.Event` `_pause_event` (cleared = paused) |
| RESUME | `threading.Event` `_pause_event` (set) |
| Pause race guard | `bool` `_pause_pending` prevents resume before loop confirms pause |

Thread-safe broadcast uses `asyncio.run_coroutine_threadsafe()` with a reference to the
main event loop (`_main_loop`) captured during `start()`.

### 3. Status API (`simulation_manager.py`)

`stop()` now sets `self.status = SimStatus.STOPPED` immediately so the HTTP response and
subsequent status checks reflect the stop right away, without waiting for the thread to
finish cleanup (write results CSV/manifest).

## Files Changed

| File | Change |
|---|---|
| `backend/matlab_bridge.py` | Rewritten — `Popen`-based execution, `_current_process` tracking |
| `backend/simulation_manager.py` | Rewritten — frame-by-frame loop, threading.Event signals, `run_coroutine_threadsafe` broadcast, immediate status on stop |
| `otfs_ai_pipeline/test_pause_stop.py` | Rewritten — 5 live integration tests with improved timing |

## Test Results

```
================================================================
  ALL TESTS PASSED
================================================================

  TEST 1: START → verify frames execute          PASS
  TEST 2: PAUSE → verify frames stop             PASS
  TEST 3: RESUME → verify frames continue         PASS
  TEST 4: STOP → verify subprocess killed         PASS
  TEST 5: START→STOP→START (no orphan MATLAB)     PASS
```

### Regression checks

- **Dataset checksum**: `faa877a248c0f599a87f21dabf4df358` — unchanged
- **Phase 9 validation**: 35/35 PASS
- **Backend health**: OK on `http://127.0.0.1:8000`
- **Frontend build**: 0 TypeScript errors, `npm run build` succeeds
