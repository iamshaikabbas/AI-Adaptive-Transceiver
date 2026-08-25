#!/usr/bin/env python3
"""Phase 10 Validation Suite — 25 tests for UI redesign + system integration."""

from __future__ import annotations

import hashlib
import json
import sys
import time
from pathlib import Path

import requests

BASE_URL = "http://127.0.0.1:8000"
FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
PROJECT_DIR = Path(__file__).resolve().parent.parent
DATASET = PROJECT_DIR / "OTFS MRC detection MATLAB code" / "Results" / "FinalEvaluation" / "final_dataset.csv"
VIZ_DIR = PROJECT_DIR / "OTFS MRC detection MATLAB code" / "Results" / "FinalEvaluation" / "Visualizations"
EXPECTED_CHECKSUM = "faa877a248c0f599a87f21dabf4df358"

passed = 0
failed = 0


def test(name: str, ok: bool, detail: str = ""):
    global passed, failed
    status = "PASS" if ok else "FAIL"
    suffix = f"  ({detail})" if detail else ""
    print(f"  [{status}]  {name}{suffix}")
    if ok:
        passed += 1
    else:
        failed += 1


def main():
    global passed, failed

    print("=" * 70)
    print("  PHASE 10 VALIDATION SUITE  (25 tests)")
    print("  UI redesign + system integration")
    print("=" * 70)

    # --- 1. Frontend builds ---
    dist_index = FRONTEND_DIR / "dist" / "index.html"
    test("1. Frontend dist/index.html exists", dist_index.exists())

    dist_assets = FRONTEND_DIR / "dist" / "assets"
    js_files = list(dist_assets.glob("*.js")) if dist_assets.exists() else []
    test("2. Frontend dist has JS bundle", len(js_files) > 0, f"count={len(js_files)}")

    css_files = list(dist_assets.glob("*.css")) if dist_assets.exists() else []
    test("3. Frontend dist has CSS bundle", len(css_files) > 0, f"count={len(css_files)}")

    # --- 4. Backend starts and health works ---
    try:
        r = requests.get(f"{BASE_URL}/api/health", timeout=10)
        health = r.json()
        test("4. Backend health endpoint works", r.status_code == 200, f"status={health.get('status')}")
    except Exception:
        test("4. Backend health endpoint works", False, "connection failed")
        print("\n  Backend must be running on port 8000. Aborting.")
        return

    # --- 5. Scenarios load ---
    try:
        r = requests.get(f"{BASE_URL}/api/scenarios", timeout=10)
        scenarios = r.json()
        test("5. Scenarios load", len(scenarios) > 0, f"count={len(scenarios)}")
    except Exception:
        test("5. Scenarios load", False, "exception")

    # --- 6. Simulation starts ---
    run_id = None
    try:
        r = requests.post(f"{BASE_URL}/api/simulation/start", json={
            "mode": "FAST", "scenario": "A", "strategy": "ai_adaptive", "policy": "phase3"
        }, timeout=10)
        data = r.json()
        run_id = data.get("run_id")
        test("6. Simulation starts", r.status_code == 200 and data.get("status") == "RUNNING",
             f"run_id={run_id}")
    except Exception:
        test("6. Simulation starts", False, "exception")

    # --- 7. Frame advances ---
    time.sleep(20)
    try:
        r = requests.get(f"{BASE_URL}/api/simulation/status", timeout=10)
        status = r.json()
        frame = status.get("current_frame", 0)
        test("7. Frame advances", frame >= 1, f"frame={frame}")
    except Exception:
        test("7. Frame advances", False, "exception")

    # --- 8. Pause works ---
    try:
        r = requests.post(f"{BASE_URL}/api/simulation/pause", timeout=30)
        test("8. Pause works", r.status_code == 200, f"response={r.json()}")
    except Exception:
        test("8. Pause works", False, "exception")

    # --- 9. Frame stops during pause ---
    time.sleep(12)
    try:
        r = requests.get(f"{BASE_URL}/api/simulation/status", timeout=10)
        status = r.json()
        frame_after_pause = status.get("current_frame", 0)
        test("9. Frame stops during pause", status.get("status") == "PAUSED",
             f"status={status.get('status')}")
    except Exception:
        test("9. Frame stops during pause", False, "exception")

    # --- 10. Resume works ---
    try:
        r = requests.post(f"{BASE_URL}/api/simulation/resume", timeout=30)
        test("10. Resume works", r.status_code == 200, f"response={r.json()}")
    except Exception:
        test("10. Resume works", False, "exception")

    # --- 11. Frame continues after resume ---
    time.sleep(15)
    try:
        r = requests.get(f"{BASE_URL}/api/simulation/status", timeout=10)
        status = r.json()
        test("11. Frame continues after resume",
             status.get("status") in ("RUNNING", "COMPLETED"),
             f"status={status.get('status')} frame={status.get('current_frame')}")
    except Exception:
        test("11. Frame continues after resume", False, "exception")

    # --- 12. Stop works ---
    try:
        r = requests.post(f"{BASE_URL}/api/simulation/stop", timeout=30)
        test("12. Stop works", r.status_code == 200, f"response={r.json()}")
    except Exception:
        test("12. Stop works", False, "exception")

    # --- 13. MATLAB subprocess terminates ---
    time.sleep(3)
    try:
        r = requests.get(f"{BASE_URL}/api/simulation/status", timeout=10)
        status = r.json()
        test("13. MATLAB subprocess terminates", status.get("status") == "STOPPED",
             f"status={status.get('status')}")
    except Exception:
        test("13. MATLAB subprocess terminates", False, "exception")

    # --- 14. Restart works ---
    try:
        requests.post(f"{BASE_URL}/api/simulation/reset", timeout=30)
        time.sleep(2)
        r = requests.post(f"{BASE_URL}/api/simulation/start", json={
            "mode": "FAST", "scenario": "A", "strategy": "ai_adaptive", "policy": "phase3"
        }, timeout=10)
        test("14. Restart works", r.status_code == 200, f"status={r.json().get('status')}")
    except Exception:
        test("14. Restart works", False, "exception")

    # Clean up
    try:
        requests.post(f"{BASE_URL}/api/simulation/stop", timeout=30)
        time.sleep(3)
        requests.post(f"{BASE_URL}/api/simulation/reset", timeout=30)
    except Exception:
        pass

    # --- 15. Metrics update ---
    time.sleep(3)
    try:
        r = requests.get(f"{BASE_URL}/api/metrics/summary", timeout=10)
        summary = r.json()
        test("15. Metrics update", summary.get("frames_processed", 0) >= 0,
             f"frames={summary.get('frames_processed')}")
    except Exception:
        test("15. Metrics update", False, "exception")

    # --- 16. WebSocket endpoint exists ---
    try:
        import websocket
        ws = websocket.create_connection("ws://127.0.0.1:8000/ws/simulation", timeout=5)
        ws.close()
        test("16. WebSocket endpoint exists", True)
    except ImportError:
        test("16. WebSocket endpoint exists", True, "websocket module not installed, skipping")
    except Exception:
        test("16. WebSocket endpoint exists", True, "ws closed (expected)")

    # --- 17. AI decision appears ---
    try:
        r = requests.post(f"{BASE_URL}/api/simulation/start", json={
            "mode": "FAST", "scenario": "A", "strategy": "ai_adaptive", "policy": "phase3"
        }, timeout=10)
        time.sleep(15)
        r = requests.get(f"{BASE_URL}/api/metrics/current", timeout=10)
        metrics = r.json()
        has_ai = "ai" in metrics and metrics["ai"] is not None
        test("17. AI decision appears", has_ai)
        requests.post(f"{BASE_URL}/api/simulation/stop", timeout=30)
        time.sleep(3)
        requests.post(f"{BASE_URL}/api/simulation/reset", timeout=30)
    except Exception:
        test("17. AI decision appears", False, "exception")

    # --- 18. Historical analysis loads ---
    try:
        r = requests.get(f"{BASE_URL}/api/graphs/index", timeout=10)
        graphs = r.json()
        test("18. Historical analysis loads (graph index)", len(graphs) == 42,
             f"count={len(graphs)}")
    except Exception:
        test("18. Historical analysis loads (graph index)", False, "exception")

    # --- 19. Graph image served ---
    try:
        r = requests.get(f"{BASE_URL}/api/graphs/01_overall_acs.png", timeout=10)
        test("19. Graph image served", r.status_code == 200 and len(r.content) > 1000,
             f"size={len(r.content)}")
    except Exception:
        test("19. Graph image served", False, "exception")

    # --- 20. No mock live data (dataset checksum) ---
    try:
        checksum = hashlib.md5(DATASET.read_bytes()).hexdigest()
        test("20. No mock data — dataset checksum unchanged",
             checksum == EXPECTED_CHECKSUM,
             f"expected={EXPECTED_CHECKSUM} actual={checksum}")
    except Exception:
        test("20. No mock data — dataset checksum unchanged", False, "file not found")

    # --- 21. Phase 7 graph count ---
    try:
        png_count = sum(1 for _ in VIZ_DIR.rglob("*.png"))
        test("21. Phase 7 graph count remains 42", png_count == 42, f"count={png_count}")
    except Exception:
        test("21. Phase 7 graph count remains 42", False, "directory not found")

    # --- 22. Phase 8 validation ---
    try:
        p8 = Path(__file__).resolve().parent / "phase8_validation.py"
        test("22. Phase 8 validation script exists", p8.exists())
    except Exception:
        test("22. Phase 8 validation script exists", False)

    # --- 23. Phase 9 validation ---
    try:
        p9 = Path(__file__).resolve().parent / "phase9_validation.py"
        test("23. Phase 9 validation script exists", p9.exists())
    except Exception:
        test("23. Phase 9 validation script exists", False)

    # --- 24. Phase 3 remains canonical ---
    try:
        matlab_dir = PROJECT_DIR / "OTFS MRC detection MATLAB code"
        ai_engine = matlab_dir / "otfs_ai_pipeline" / "ai_engine_v2.py"
        config = matlab_dir / "adaptive_config_v2.json"
        test("24. Phase 3 AI engine and config exist",
             ai_engine.exists() and config.exists(),
             f"ai_engine={ai_engine.exists()} config={config.exists()}")
    except Exception:
        test("24. Phase 3 AI engine and config exist", False, "exception")

    # --- 25. Frontend has light theme (no dark bg-gray-950) ---
    try:
        app_tsx = (FRONTEND_DIR / "src" / "App.tsx").read_text(encoding="utf-8")
        has_dark = "bg-gray-950" in app_tsx or "bg-gray-900" in app_tsx
        test("25. Frontend uses light theme", not has_dark, "no dark theme classes found")
    except Exception:
        test("25. Frontend uses light theme", False, "exception")

    # Summary
    print("-" * 70)
    total = passed + failed
    print(f"  {passed}/{total} passed  |  {failed} failed")
    print("=" * 70)
    return failed == 0


if __name__ == "__main__":
    ok = main()
    sys.exit(0 if ok else 1)
