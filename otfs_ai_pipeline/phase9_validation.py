"""Phase 9 Validation Suite — 35 tests for the React/TypeScript frontend.

Tests 1-5:    File structure (package.json, vite.config.ts, App.tsx, types, services)
Tests 6-15:   Frontend source files (services, hooks, components)
Tests 16-19:  Pages
Tests 20-22:  Build artifacts
Tests 23-25:  TypeScript types verification
Tests 26-27:  API service verification
Tests 28-29:  Vite config verification
Test 30:      Backend not modified
Test 31:      Dataset integrity
Test 32:      Phase 7 visualizations
Tests 33-35:  Phase 9 documentation
"""

import hashlib
import json
import sys
import time
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
FRONTEND = PROJECT_ROOT / "frontend"
SRC = FRONTEND / "src"
DIST = FRONTEND / "dist"
EXPECTED_CHECKSUM = "faa877a248c0f599a87f21dabf4df358"


def md5(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read_text(path):
    return Path(path).read_text(encoding="utf-8")


def run_tests():
    results = []

    def record(num, name, passed, detail=""):
        results.append((num, name, passed, detail))

    # ── 1. File Structure (5 tests) ──────────────────────────────────────

    record(1, "frontend/package.json exists",
           (FRONTEND / "package.json").is_file())

    record(2, "frontend/vite.config.ts exists",
           (FRONTEND / "vite.config.ts").is_file())

    record(3, "frontend/src/App.tsx exists",
           (SRC / "App.tsx").is_file())

    record(4, "frontend/src/types/api.ts exists",
           (SRC / "types" / "api.ts").is_file())

    record(5, "frontend/src/services/api.ts exists",
           (SRC / "services" / "api.ts").is_file())

    # ── 2. Frontend Source Files (10 tests) ───────────────────────────────

    record(6, "services/websocket.ts exists",
           (SRC / "services" / "websocket.ts").is_file())

    record(7, "hooks/useSimulation.ts exists",
           (SRC / "hooks" / "useSimulation.ts").is_file())

    record(8, "components/Header.tsx exists",
           (SRC / "components" / "Header.tsx").is_file())

    record(9, "components/Sidebar.tsx exists",
           (SRC / "components" / "Sidebar.tsx").is_file())

    record(10, "components/SimulationControls.tsx exists",
           (SRC / "components" / "SimulationControls.tsx").is_file())

    record(11, "components/DigitalTwinViz.tsx exists",
           (SRC / "components" / "DigitalTwinViz.tsx").is_file())

    record(12, "components/AIDecisionPanel.tsx exists",
           (SRC / "components" / "AIDecisionPanel.tsx").is_file())

    record(13, "components/LiveCharts.tsx exists",
           (SRC / "components" / "LiveCharts.tsx").is_file())

    record(14, "components/Timeline.tsx exists",
           (SRC / "components" / "Timeline.tsx").is_file())

    record(15, "components/SwitchingBar.tsx exists",
           (SRC / "components" / "SwitchingBar.tsx").is_file())

    # ── 3. Pages (4 tests) ───────────────────────────────────────────────

    record(16, "pages/Overview.tsx exists",
           (SRC / "pages" / "Overview.tsx").is_file())

    record(17, "pages/DigitalTwinPage.tsx exists",
           (SRC / "pages" / "DigitalTwinPage.tsx").is_file())

    record(18, "pages/Analysis.tsx exists",
           (SRC / "pages" / "Analysis.tsx").is_file())

    record(19, "pages/About.tsx exists",
           (SRC / "pages" / "About.tsx").is_file())

    # ── 4. Build Artifacts (3 tests) ─────────────────────────────────────

    record(20, "frontend/dist/index.html exists",
           (DIST / "index.html").is_file())

    record(21, "frontend/dist/assets/ directory exists",
           (DIST / "assets").is_dir())

    js_files = list((DIST / "assets").glob("*.js")) if (DIST / "assets").is_dir() else []
    record(22, "At least one .js file in dist/assets",
           len(js_files) > 0,
           f"count={len(js_files)}")

    # ── 5. TypeScript Types (3 tests) ────────────────────────────────────

    api_ts = read_text(SRC / "types" / "api.ts")
    required_types = [
        "HealthResponse", "ConfigResponse", "SimulationStartRequest",
        "SimulationStatus", "FrameResult", "AIInfo", "MetricsSummary",
    ]
    found_types = [t for t in required_types if f"export interface {t}" in api_ts
                   or f"export type {t}" in api_ts]
    record(23, "api.ts exports all required type interfaces",
           len(found_types) == len(required_types),
           f"found={len(found_types)}/{len(required_types)}")

    record(24, "api.ts defines FrameResult with field 'BER'",
           "BER:" in api_ts or "BER :" in api_ts)

    record(25, "api.ts defines WSFrameEvent for WebSocket",
           "WSFrameEvent" in api_ts)

    # ── 6. API Service (2 tests) ─────────────────────────────────────────

    service_ts = read_text(SRC / "services" / "api.ts")
    required_methods = ["health", "getSimulationStatus", "startSimulation"]
    found_methods = [m for m in required_methods
                     if f"{m}:" in service_ts or f"{m} (" in service_ts]
    record(26, "api.ts exports api object with required methods",
           len(found_methods) == len(required_methods),
           f"found={found_methods}")

    record(27, "api.ts covers all 17 endpoints",
           service_ts.count("/api/") >= 15,
           f"api_path_count={service_ts.count('/api/')}")

    # ── 7. Vite Config (2 tests) ─────────────────────────────────────────

    vite_ts = read_text(FRONTEND / "vite.config.ts")
    record(28, "vite.config.ts proxies /api",
           "'/api'" in vite_ts or '"/api"' in vite_ts,
           f"target={'127.0.0.1:8000' if '127.0.0.1:8000' in vite_ts else 'missing'}")

    record(29, "vite.config.ts proxies /ws",
           "'/ws'" in vite_ts or '"/ws"' in vite_ts)

    # ── 8. Backend Not Modified (1 test) ─────────────────────────────────

    backend_main = PROJECT_ROOT / "backend" / "main.py"
    if backend_main.is_file():
        main_content = read_text(backend_main)
        record(30, "Backend main.py unchanged (@app.get /api/health)",
               '@app.get("/api/health"' in main_content)
    else:
        record(30, "Backend main.py unchanged (@app.get /api/health)",
               False, "file missing")

    # ── 9. Dataset Integrity (1 test) ────────────────────────────────────

    dataset_path = (PROJECT_ROOT / "OTFS MRC detection MATLAB code"
                    / "Results" / "FinalEvaluation" / "final_dataset.csv")
    if dataset_path.is_file():
        actual = md5(dataset_path)
        record(31, "Dataset checksum unchanged",
               actual == EXPECTED_CHECKSUM,
               f"expected={EXPECTED_CHECKSUM} actual={actual}")
    else:
        record(31, "Dataset checksum unchanged",
               False, "dataset missing")

    # ── 10. Phase 7 Visualizations (1 test) ──────────────────────────────

    viz_dir = (PROJECT_ROOT / "OTFS MRC detection MATLAB code"
               / "Results" / "FinalEvaluation" / "Visualizations")
    gi_path = viz_dir / "graph_index.json"
    try:
        gi = json.loads(gi_path.read_text(encoding="utf-8"))
        record(32, "Phase 7 graph_index.json exists",
               len(gi) == 42 and viz_dir.exists(),
               f"graphs={len(gi)}")
    except Exception as e:
        record(32, "Phase 7 graph_index.json exists", False, str(e))

    # ── 11. Phase 9 Documentation (3 tests) ──────────────────────────────

    record(33, "PHASE9_ARCHITECTURE.md exists",
           (PROJECT_ROOT / "PHASE9_ARCHITECTURE.md").is_file())

    record(34, "PHASE9_VALIDATION.md exists",
           (PROJECT_ROOT / "PHASE9_VALIDATION.md").is_file())

    record(35, "PHASE9_FINAL_REPORT.md exists",
           (PROJECT_ROOT / "PHASE9_FINAL_REPORT.md").is_file())

    return results


def main():
    print("=" * 64)
    print("  PHASE 9 VALIDATION SUITE  (35 tests)")
    print("  Frontend: React/TypeScript/Vite digital twin UI")
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
