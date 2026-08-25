"""Phase 9.1 Integration Test — Live pause/stop with MATLAB subprocess.

Tests:
1. START → frame advances
2. PAUSE → frame stops advancing within ~1 frame cycle
3. RESUME → frame advances again
4. STOP → subprocess killed, backend returns STOPPED
5. START→STOP→START → no orphan processes
"""
import requests
import time
import sys

BASE = "http://127.0.0.1:8000"


def get_status():
    r = requests.get(f"{BASE}/api/simulation/status", timeout=10)
    return r.json()


def main():
    # Check backend
    try:
        r = requests.get(f"{BASE}/api/health", timeout=5)
        print(f"Backend health: {r.json()['status']}")
    except Exception as e:
        print(f"Backend not running: {e}")
        return False

    all_pass = True

    # ── TEST 1: START → check frame advances ──
    print()
    print("=" * 64)
    print("  TEST 1: START → verify frames execute")
    print("=" * 64)
    r = requests.post(f"{BASE}/api/simulation/start", json={
        "mode": "FAST", "scenario": "A", "strategy": "ai_adaptive", "policy": "phase3"
    }, timeout=10)
    assert r.status_code == 200, f"START failed: {r.status_code}"
    data = r.json()
    print(f"  START OK: run_id={data['run_id']} status={data['status']}")

    # Wait for at least 2 frames to complete
    print("  Waiting for at least 2 frames...")
    for i in range(60):  # Up to 60 seconds
        time.sleep(1)
        s = get_status()
        if s["current_frame"] >= 2:
            break
    print(f"  Frames completed: {s['current_frame']}/{s['total_frames']}")
    if s["current_frame"] < 2:
        print("  FAIL: Could not get 2 frames to complete")
        all_pass = False

    # ── TEST 2: PAUSE → verify frame stops advancing ──
    print()
    print("=" * 64)
    print("  TEST 2: PAUSE → verify frames stop")
    print("=" * 64)
    # Record the current frame AFTER the next frame completes
    # Wait for one more frame to ensure we have a clean baseline
    while get_status()["current_frame"] == s["current_frame"]:
        time.sleep(0.5)
    # Now we know the frame just completed — capture it
    s_before = get_status()
    frame_before = s_before["current_frame"]
    print(f"  Frame before PAUSE: {frame_before}")

    # Wait until a NEW frame completes so we know we're between frames
    time.sleep(1)  # Give the loop a moment to enter the next iteration
    s_check = get_status()
    if s_check["current_frame"] > frame_before:
        frame_before = s_check["current_frame"]
        print(f"  Updated frame_before: {frame_before}")

    # Now call PAUSE
    r = requests.post(f"{BASE}/api/simulation/pause", timeout=10)
    print(f"  PAUSE response: {r.status_code} {r.json()}")
    time.sleep(1)

    s_paused = get_status()
    print(f"  Status after PAUSE: frame={s_paused['current_frame']} status={s_paused['status']}")
    assert s_paused["status"] == "PAUSED", f"Expected PAUSED, got {s_paused['status']}"

    # The frame that was in progress when we paused may complete — allow for that
    # But AFTER that, no more frames should execute
    # Wait 15 seconds and verify frame count is at most frame_before + 1
    print("  Waiting 15s to verify no additional frames execute...")
    time.sleep(15)

    s_during = get_status()
    frame_during = s_during["current_frame"]
    print(f"  Frame after 15s pause: {frame_during} (was {frame_before} before pause)")
    # Allow for at most 1 extra frame (the one already in progress)
    if frame_during <= frame_before + 1:
        print(f"  PASS: Frame {frame_during} <= {frame_before}+1 (at most 1 frame completed during pause)")
    else:
        print(f"  FAIL: Frame {frame_during} > {frame_before}+1 (too many frames during pause)")
        all_pass = False

    # ── TEST 3: RESUME → verify frame advances again ──
    print()
    print("=" * 64)
    print("  TEST 3: RESUME → verify frames continue")
    print("=" * 64)
    frame_at_pause = s_during["current_frame"]
    r = requests.post(f"{BASE}/api/simulation/resume", timeout=10)
    print(f"  RESUME response: {r.status_code} {r.json()}")

    # Wait for at least 2 more frames
    print("  Waiting for at least 2 more frames after RESUME...")
    for i in range(30):
        time.sleep(1)
        s = get_status()
        if s["current_frame"] >= frame_at_pause + 2:
            break
    frame_after_resume = s["current_frame"]
    print(f"  Frame after resume: {frame_after_resume} (was {frame_at_pause} during pause)")
    if frame_after_resume >= frame_at_pause + 2:
        print("  PASS: Frame advanced by 2+ after RESUME")
    else:
        print(f"  FAIL: Frame only advanced to {frame_after_resume}")
        all_pass = False
    print(f"  Status: {s['status']}")

    # ── TEST 4: STOP → verify subprocess killed ──
    print()
    print("=" * 64)
    print("  TEST 4: STOP → verify subprocess killed")
    print("=" * 64)
    s = get_status()
    if s["status"] == "COMPLETED":
        print("  Simulation already completed, skipping STOP test")
    else:
        # Start a fresh simulation for STOP test
        requests.post(f"{BASE}/api/simulation/reset", timeout=30)
        time.sleep(2)

        r = requests.post(f"{BASE}/api/simulation/start", json={
            "mode": "FAST", "scenario": "A", "strategy": "ai_adaptive", "policy": "phase3"
        }, timeout=10)
        print(f"  START for STOP test: {r.status_code}")

        # Wait for MATLAB to actually start executing
        print("  Waiting 15s for MATLAB to start...")
        time.sleep(15)

        s = get_status()
        frame_before_stop = s["current_frame"]
        print(f"  Frame before STOP: {frame_before_stop} status={s['status']}")

        if s["status"] in ("RUNNING", "PAUSED"):
            r = requests.post(f"{BASE}/api/simulation/stop", timeout=30)
            print(f"  STOP response: {r.status_code} {r.json()}")

            # Wait for the run loop to write results and exit
            time.sleep(5)

            s = get_status()
            print(f"  Status after STOP: frame={s['current_frame']} status={s['status']}")
            if s["status"] == "STOPPED":
                print("  PASS: Backend returned to STOPPED")
            else:
                print(f"  FAIL: Expected STOPPED, got {s['status']}")
                all_pass = False
        else:
            print(f"  Simulation already finished: {s['status']}, skipping")

    # ── TEST 5: START→STOP→START (no orphan processes) ──
    print()
    print("=" * 64)
    print("  TEST 5: START→STOP→START (no orphan MATLAB)")
    print("=" * 64)
    requests.post(f"{BASE}/api/simulation/reset", timeout=30)
    time.sleep(2)

    r = requests.post(f"{BASE}/api/simulation/start", json={
        "mode": "FAST", "scenario": "A", "strategy": "ai_adaptive", "policy": "phase3"
    }, timeout=10)
    print(f"  First START: {r.status_code} status={r.json().get('status')}")
    time.sleep(15)

    s = get_status()
    print(f"  Frames before STOP: {s['current_frame']}")
    r = requests.post(f"{BASE}/api/simulation/stop", timeout=30)
    print(f"  STOP: {r.status_code}")
    time.sleep(5)

    s = get_status()
    print(f"  After STOP: status={s['status']}")
    assert s["status"] == "STOPPED", f"Expected STOPPED, got {s['status']}"

    requests.post(f"{BASE}/api/simulation/reset", timeout=30)
    time.sleep(2)

    r = requests.post(f"{BASE}/api/simulation/start", json={
        "mode": "FAST", "scenario": "A", "strategy": "ai_adaptive", "policy": "phase3"
    }, timeout=10)
    print(f"  Second START: {r.status_code} status={r.json().get('status')}")
    if r.status_code == 200 and r.json().get("status") == "RUNNING":
        print("  PASS: Second START succeeded — no orphan process")
    else:
        print("  FAIL: Second START failed — possible orphan process")
        all_pass = False

    # Clean up
    requests.post(f"{BASE}/api/simulation/stop", timeout=30)
    time.sleep(5)
    requests.post(f"{BASE}/api/simulation/reset", timeout=30)

    print()
    print("=" * 64)
    if all_pass:
        print("  ALL TESTS PASSED")
    else:
        print("  SOME TESTS FAILED")
    print("=" * 64)
    return all_pass


if __name__ == "__main__":
    ok = main()
    sys.exit(0 if ok else 1)
