"""Phase 8 Validation Suite — 20 tests for the backend API.

Tests 1-16: API structure and Python AI (no MATLAB required).
Tests 17-20: Dataset integrity and file verification.

MATLAB integration is tested separately via PHASE8_MATLAB_TEST.md.
"""

import hashlib
import json
import sys
import time
import urllib.request
import urllib.error
import subprocess
import os
from pathlib import Path

BASE_URL = "http://127.0.0.1:8000"
EXPECTED_CHECKSUM = "faa877a248c0f599a87f21dabf4df358"
DATASET_PATH = (
    Path(__file__).resolve().parent.parent
    / "OTFS MRC detection MATLAB code"
    / "Results" / "FinalEvaluation" / "final_dataset.csv"
)
PROJECT_ROOT = Path(__file__).resolve().parent.parent


def md5(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def api_get(path):
    r = urllib.request.urlopen(f"{BASE_URL}{path}", timeout=10)
    return json.loads(r.read())


def api_post(path, data=None):
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(
        f"{BASE_URL}{path}", data=body,
        headers={"Content-Type": "application/json"} if body else {},
        method="POST",
    )
    r = urllib.request.urlopen(req, timeout=10)
    return json.loads(r.read())


def api_post_expect(path, data=None, expected_codes=(409, 422)):
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(
        f"{BASE_URL}{path}", data=body,
        headers={"Content-Type": "application/json"} if body else {},
        method="POST",
    )
    try:
        r = urllib.request.urlopen(req, timeout=10)
        return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def start_server():
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "backend.main:app",
         "--host", "127.0.0.1", "--port", "8000"],
        cwd=str(PROJECT_ROOT),
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    time.sleep(4)
    return proc


def stop_server(proc):
    if proc and proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


def run_tests():
    results = []

    def record(num, name, passed, detail=""):
        results.append((num, name, passed, detail))

    server = start_server()
    try:
        # Test 1: Backend starts
        record(1, "Backend starts locally", server.poll() is None)

        # Test 2: /api/health
        try:
            h = api_get("/api/health")
            record(2, "/api/health works", h.get("status") == "ok",
                   f"digital_twin={h.get('digital_twin')}")
        except Exception as e:
            record(2, "/api/health works", False, str(e))

        # Test 3: /api/config
        try:
            c = api_get("/api/config")
            ok = ("available_policies" in c and "phase3" in c["available_policies"]
                  and "available_strategies" in c)
            record(3, "/api/config works", ok)
        except Exception as e:
            record(3, "/api/config works", False, str(e))

        # Test 4: /api/scenarios
        try:
            sc = api_get("/api/scenarios")
            letters = [s["id"] for s in sc]
            record(4, "/api/scenarios works",
                   len(sc) >= 18 and "A" in letters and "R" in letters,
                   f"count={len(sc)}")
        except Exception as e:
            record(4, "/api/scenarios works", False, str(e))

        # Test 5: /api/strategies
        try:
            st = api_get("/api/strategies")
            ids = [s["id"] for s in st]
            record(5, "/api/strategies works",
                   "ai_adaptive" in ids and "fixed_otfs" in ids
                   and "fixed_oddm" in ids and "oracle" in ids,
                   f"count={len(ids)}")
        except Exception as e:
            record(5, "/api/strategies works", False, str(e))

        # Test 6: /api/policies
        try:
            po = api_get("/api/policies")
            ids = [p["id"] for p in po]
            record(6, "/api/policies works",
                   "phase3" in ids and "phase4" in ids)
        except Exception as e:
            record(6, "/api/policies works", False, str(e))

        # Test 7: Initial simulation status
        try:
            ss = api_get("/api/simulation/status")
            record(7, "Initial simulation status STOPPED",
                   ss.get("status") == "STOPPED",
                   f"status={ss.get('status')}")
        except Exception as e:
            record(7, "Initial simulation status STOPPED", False, str(e))

        # Test 8: State when no simulation
        try:
            st = api_get("/api/simulation/state")
            record(8, "State when no simulation",
                   st.get("status") == "simulation_not_running")
        except Exception as e:
            record(8, "State when no simulation", False, str(e))

        # Test 9: Metrics summary empty
        try:
            ms = api_get("/api/metrics/summary")
            record(9, "Metrics summary (empty)",
                   ms.get("frames_processed") == 0)
        except Exception as e:
            record(9, "Metrics summary (empty)", False, str(e))

        # Test 10: Current metrics empty
        try:
            cm = api_get("/api/metrics/current")
            record(10, "Current metrics (empty)",
                   cm.get("status") == "no_metrics")
        except Exception as e:
            record(10, "Current metrics (empty)", False, str(e))

        # Test 11: Simulation history empty
        try:
            h = api_get("/api/simulation/history")
            record(11, "Simulation history (empty)",
                   isinstance(h, list) and len(h) == 0)
        except Exception as e:
            record(11, "Simulation history (empty)", False, str(e))

        # Test 12: Simulation result empty
        try:
            r = api_get("/api/simulation/result")
            record(12, "Simulation result (empty)",
                   r.get("status") == "no_results")
        except Exception as e:
            record(12, "Simulation result (empty)", False, str(e))

        # Test 13: Invalid scenario rejected
        try:
            code, body = api_post_expect(
                "/api/simulation/start",
                {"mode": "FAST", "scenario": "Z", "strategy": "ai_adaptive"},
            )
            record(13, "Invalid scenario rejected", code in (404, 409),
                   f"code={code}")
        except Exception as e:
            record(13, "Invalid scenario rejected", False, str(e))

        # Test 14: Invalid strategy rejected
        try:
            code, body = api_post_expect(
                "/api/simulation/start",
                {"mode": "FAST", "scenario": "A", "strategy": "bad_strat"},
            )
            record(14, "Invalid strategy rejected", code == 422,
                   f"code={code}")
        except Exception as e:
            record(14, "Invalid strategy rejected", False, str(e))

        # Test 15: Reset works
        try:
            api_post("/api/simulation/reset")
            ss = api_get("/api/simulation/status")
            record(15, "Reset works",
                   ss.get("current_frame") == 0)
        except Exception as e:
            record(15, "Reset works", False, str(e))

        # Test 16: AI bridge loads correctly
        try:
            sys.path.insert(0, str(PROJECT_ROOT / "OTFS MRC detection MATLAB code" / "otfs_ai_pipeline"))
            from ai_engine_v2 import AIEngineV2
            engine = AIEngineV2()
            decision = engine.decide({
                "environment": "Urban", "speed_kmph": 30, "snr_db": 15,
                "doppler_hz": 111.1, "carrier_frequency_hz": 4e9,
                "bandwidth_hz": 480e3, "channel_profile": "EVA",
                "delay_spread_taps": 5, "num_paths": 6,
                "doppler_spread_hz": 200, "modulation": 4,
                "current_waveform": "OTFS", "frames_since_switch": 99,
            })
            record(16, "AI engine produces decision",
                   decision.get("recommendation") in ("OTFS", "ODDM"),
                   f"rec={decision.get('recommendation')} conf={decision.get('confidence'):.2f}")
        except Exception as e:
            record(16, "AI engine produces decision", False, str(e))

        # Test 17: Dataset exists
        record(17, "Dataset exists", DATASET_PATH.exists(), str(DATASET_PATH))

        # Test 18: Dataset checksum
        try:
            actual = md5(DATASET_PATH)
            record(18, "Dataset checksum unchanged",
                   actual == EXPECTED_CHECKSUM,
                   f"expected={EXPECTED_CHECKSUM} actual={actual}")
        except Exception as e:
            record(18, "Dataset checksum unchanged", False, str(e))

        # Test 19: Phase 7 visualizations exist
        viz_dir = (PROJECT_ROOT / "OTFS MRC detection MATLAB code"
                   / "Results" / "FinalEvaluation" / "Visualizations")
        try:
            gi_path = viz_dir / "graph_index.json"
            gi = json.loads(gi_path.read_text(encoding="utf-8"))
            record(19, "Phase 7 visualizations intact",
                   len(gi) == 42 and viz_dir.exists(),
                   f"graphs={len(gi)}")
        except Exception as e:
            record(19, "Phase 7 visualizations intact", False, str(e))

        # Test 20: Backend directory structure
        try:
            backend_dir = PROJECT_ROOT / "backend"
            required = ["main.py", "models.py", "config.py", "matlab_bridge.py",
                        "ai_bridge.py", "simulation_manager.py", "scenario_service.py",
                        "result_service.py", "websocket_manager.py", "requirements.txt"]
            found = [f.name for f in backend_dir.iterdir() if f.is_file()]
            missing = [r for r in required if r not in found]
            record(20, "Backend directory structure complete",
                   len(missing) == 0,
                   f"missing={missing}" if missing else f"files={len(found)}")
        except Exception as e:
            record(20, "Backend directory structure complete", False, str(e))

    finally:
        stop_server(server)

    return results


def main():
    print("=" * 64)
    print("  PHASE 8 VALIDATION SUITE  (20 tests)")
    print("=" * 64)

    t0 = time.perf_counter()
    results = run_tests()
    elapsed = time.perf_counter() - t0

    pass_count = sum(1 for _, _, ok, _ in results if ok)
    fail_count = len(results) - pass_count

    for num, name, ok, detail in results:
        tag = "PASS" if ok else "FAIL"
        suffix = f"  ({detail})" if detail else ""
        print(f"  [{tag}] {num:>2}. {name}{suffix}")

    print("-" * 64)
    print(f"  {pass_count}/{len(results)} passed  |  {fail_count} failed  |  {elapsed:.1f}s")
    print("=" * 64)
    sys.exit(0 if fail_count == 0 else 1)


if __name__ == "__main__":
    main()
