#!/usr/bin/env python3
"""Phase 11A Deployment Validation — 20 tests."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent / "data"
JSON_PATH = DATA_DIR / "digital_twin_results.json"
META_PATH = DATA_DIR / "metadata.json"
PROJECT_DIR = Path(__file__).resolve().parent.parent
CSV_PATH = (
    PROJECT_DIR
    / "OTFS MRC detection MATLAB code"
    / "Results"
    / "FinalEvaluation"
    / "final_dataset.csv"
)

EXPECTED_CHECKSUM = "faa877a248c0f599a87f21dabf4df358"

passed = 0
failed = 0
data = None
meta = None


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
    global passed, failed, data, meta

    print("=" * 70)
    print("  PHASE 11A DEPLOYMENT VALIDATION  (20 tests)")
    print("=" * 70)

    # --- 1. JSON parses ---
    try:
        raw = JSON_PATH.read_text(encoding="utf-8")
        data = json.loads(raw)
        test("1. JSON parses", True, f"size={len(raw):,} bytes")
    except Exception as e:
        test("1. JSON parses", False, str(e))
        print("\n  Cannot continue without valid JSON.")
        return

    # --- 2. schema_version exists ---
    sv = data.get("schema_version")
    test("2. schema_version exists", sv is not None, f"version={sv}")

    # --- 3. policy_version = phase3 ---
    pv = data.get("policy_version")
    test("3. policy_version = phase3", pv == "phase3", f"got={pv}")

    # --- 4. master_seed = 20260823 ---
    ms = data.get("master_seed")
    test("4. master_seed = 20260823", ms == 20260823, f"got={ms}")

    # --- 5. operating_points is non-empty ---
    ops = data.get("operating_points", [])
    test("5. operating_points is non-empty", len(ops) > 0, f"count={len(ops)}")

    # --- 6. every operating point has conditions ---
    all_have_conditions = all("conditions" in op for op in ops)
    missing = sum(1 for op in ops if "conditions" not in op)
    test("6. every operating point has conditions", all_have_conditions,
         f"missing={missing}" if missing else "")

    # --- 7. every operating point has waveform data ---
    all_have_wf = all("waveforms" in op and len(op.get("waveforms", {})) > 0 for op in ops)
    test("7. every operating point has waveform data", all_have_wf)

    # --- 8. waveform names valid ---
    valid_names = {"OTFS", "ODDM"}
    wf_names_ok = True
    bad_names = 0
    for op in ops:
        for wf_name in op.get("waveforms", {}):
            if wf_name not in valid_names:
                wf_names_ok = False
                bad_names += 1
    test("8. waveform names valid (OTFS/ODDM)", wf_names_ok,
         f"bad={bad_names}" if bad_names else "")

    # --- 9. BER within [0,1] ---
    ber_ok = True
    bad_ber = 0
    for op in ops:
        for wf_name, wf_data in op.get("waveforms", {}).items():
            ber = wf_data.get("BER")
            if ber is not None and (ber < 0 or ber > 1):
                ber_ok = False
                bad_ber += 1
    test("9. BER within [0,1]", ber_ok, f"violations={bad_ber}" if bad_ber else "")

    # --- 10. SER within [0,1] ---
    ser_ok = True
    bad_ser = 0
    for op in ops:
        for wf_name, wf_data in op.get("waveforms", {}).items():
            ser = wf_data.get("SER")
            if ser is not None and (ser < 0 or ser > 1):
                ser_ok = False
                bad_ser += 1
    test("10. SER within [0,1]", ser_ok, f"violations={bad_ser}" if bad_ser else "")

    # --- 11. PER within [0,1] ---
    per_ok = True
    bad_per = 0
    for op in ops:
        for wf_name, wf_data in op.get("waveforms", {}).items():
            per = wf_data.get("PER")
            if per is not None and (per < 0 or per > 1):
                per_ok = False
                bad_per += 1
    test("11. PER within [0,1]", per_ok, f"violations={bad_per}" if bad_per else "")

    # --- 12. throughput >= 0 ---
    tp_ok = True
    bad_tp = 0
    for op in ops:
        for wf_name, wf_data in op.get("waveforms", {}).items():
            tp = wf_data.get("throughput_bps")
            if tp is not None and tp < 0:
                tp_ok = False
                bad_tp += 1
    test("12. throughput >= 0", tp_ok, f"violations={bad_tp}" if bad_tp else "")

    # --- 13. CQI within [0,15] ---
    cqi_ok = True
    bad_cqi = 0
    for op in ops:
        for wf_name, wf_data in op.get("waveforms", {}).items():
            cqi = wf_data.get("CQI")
            if cqi is not None and (cqi < 0 or cqi > 15):
                cqi_ok = False
                bad_cqi += 1
    test("13. CQI within [0,15]", cqi_ok, f"violations={bad_cqi}" if bad_cqi else "")

    # --- 14. ACS within [0,1] ---
    acs_ok = True
    bad_acs = 0
    for op in ops:
        for wf_name, wf_data in op.get("waveforms", {}).items():
            acs = wf_data.get("ACS")
            if acs is not None and (acs < 0 or acs > 1):
                acs_ok = False
                bad_acs += 1
    test("14. ACS within [0,1]", acs_ok, f"violations={bad_acs}" if bad_acs else "")

    # --- 15. no fabricated missing values (0 or -1 where null expected) ---
    # Check that no waveform metric is exactly 0.0 for BER/SER/PER/ACS/CQI
    # (0.0 for BER is technically possible but suspicious for real data)
    # We check that metrics are not all-zero across waveforms
    fabricated = 0
    for op in ops:
        for wf_name, wf_data in op.get("waveforms", {}).items():
            # throughput_bps = 0 is valid (no throughput)
            # But BER = 0 AND throughput = 0 AND ACS = 0 is suspicious
            ber = wf_data.get("BER")
            tp = wf_data.get("throughput_bps")
            acs = wf_data.get("ACS")
            if ber == 0.0 and tp == 0.0 and acs == 0.0:
                fabricated += 1
    test("15. no fabricated missing values", fabricated == 0,
         f"suspicious={fabricated}" if fabricated else "")

    # --- 16. no duplicate operating-point IDs ---
    ids = [op.get("id", "") for op in ops]
    test("16. no duplicate operating-point IDs", len(ids) == len(set(ids)),
         f"duplicates={len(ids) - len(set(ids))}")

    # --- 17. all operating-point IDs deterministic (sorted) ---
    id_sorted = sorted(ids)
    test("17. all operating-point IDs deterministic", ids == id_sorted,
         "sorted order matches" if ids == id_sorted else "MISMATCH")

    # --- 18. provenance exists ---
    has_source = all(
        "source_scenario" in op and "source_frame" in op
        for op in ops
    )
    test("18. provenance exists (source_scenario, source_frame)", has_source)

    # --- 19. source checksum matches frozen Phase 6 dataset ---
    actual_chk = hashlib.md5(CSV_PATH.read_bytes()).hexdigest()
    source_info = data.get("source", {})
    exported_chk = source_info.get("source_checksum")
    test("19. source checksum matches Phase 6 dataset",
         exported_chk == EXPECTED_CHECKSUM and actual_chk == EXPECTED_CHECKSUM,
         f"exported={exported_chk} actual={actual_chk}")

    # --- 20. JSON values agree with source data (spot check) ---
    # Load first 5 operating points and verify against CSV
    import csv as _csv
    with open(CSV_PATH, "r", encoding="utf-8") as f:
        csv_rows = list(_csv.DictReader(f))

    # Group by (scenario, frame) and pick first group
    csv_groups: dict[tuple, list] = {}
    for r in csv_rows:
        key = (r["scenario_id"], r["frame"])
        csv_groups.setdefault(key, []).append(r)

    first_key = sorted(csv_groups.keys())[0]
    csv_group = csv_groups[first_key]
    csv_by_strat = {r["strategy"]: r for r in csv_group}

    # Find matching operating point
    matching_op = None
    for op in ops:
        if op["source_scenario"] == first_key[0] and op["source_frame"] == int(first_key[1]):
            matching_op = op
            break

    if matching_op is None:
        test("20. JSON values agree with source (spot check)", False, "no matching op found")
    else:
        # Compare OTFS BER
        csv_ber = float(csv_by_strat["fixed_otfs"]["BER"])
        json_ber = matching_op["waveforms"]["OTFS"]["BER"]
        match = abs(csv_ber - json_ber) < 1e-10
        # Compare ODDM throughput
        csv_tp = float(csv_by_strat["fixed_oddm"]["throughput_bps"])
        json_tp = matching_op["waveforms"]["ODDM"]["throughput_bps"]
        match = match and abs(csv_tp - json_tp) < 1.0
        test("20. JSON values agree with source (spot check)", match,
             f"OTFS_BER: csv={csv_ber} json={json_ber}")

    # Summary
    print("-" * 70)
    total = passed + failed
    print(f"  {passed}/{total} passed  |  {failed} failed")
    print("=" * 70)
    return failed == 0


if __name__ == "__main__":
    ok = main()
    sys.exit(0 if ok else 1)
