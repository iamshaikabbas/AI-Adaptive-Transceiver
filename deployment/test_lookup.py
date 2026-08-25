#!/usr/bin/env python3
"""Phase 11A — Lookup test: verify 5 real operating points against source CSV."""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

JSON_PATH = Path(__file__).resolve().parent / "data" / "digital_twin_results.json"
CSV_PATH = (
    Path(__file__).resolve().parent.parent
    / "OTFS MRC detection MATLAB code"
    / "Results"
    / "FinalEvaluation"
    / "final_dataset.csv"
)

TOLERANCE = 1e-8


def load_json() -> dict:
    return json.loads(JSON_PATH.read_text(encoding="utf-8"))


def load_csv_groups() -> dict[tuple[str, str], dict[str, dict]]:
    with open(CSV_PATH, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    groups: dict[tuple[str, str], dict[str, dict]] = {}
    for r in rows:
        key = (r["scenario_id"], r["frame"])
        groups.setdefault(key, {})[r["strategy"]] = r
    return groups


def main():
    data = load_json()
    csv_groups = load_csv_groups()
    ops = data["operating_points"]

    # Pick 5 diverse operating points
    test_cases = [
        ("A", 1),
        ("E", 10),
        ("J", 5),
        ("O", 15),
        ("R", 24),
    ]

    print("=" * 70)
    print("  PHASE 11A LOOKUP TEST  (5 operating points)")
    print("=" * 70)

    all_pass = True

    for scenario, frame in test_cases:
        # Find in JSON
        json_op = None
        for op in ops:
            if op["source_scenario"] == scenario and op["source_frame"] == frame:
                json_op = op
                break

        # Find in CSV
        csv_strats = csv_groups.get((scenario, str(frame)))

        if json_op is None:
            print(f"\n  [{scenario}, frame {frame}] FAIL: not found in JSON")
            all_pass = False
            continue
        if csv_strats is None:
            print(f"\n  [{scenario}, frame {frame}] FAIL: not found in CSV")
            all_pass = False
            continue

        # Compare OTFS metrics
        otfs_csv = csv_strats.get("fixed_otfs")
        otfs_json = json_op.get("waveforms", {}).get("OTFS")

        # Compare ODDM metrics
        oddm_csv = csv_strats.get("fixed_oddm")
        oddm_json = json_op.get("waveforms", {}).get("ODDM")

        # Compare AI predictions
        ai_csv = csv_strats.get("ai_adaptive")
        ai_json = json_op.get("ai_prediction")

        errors = []

        if otfs_csv and otfs_json:
            for field in ["BER", "throughput_bps", "CQI", "ACS"]:
                csv_val = float(otfs_csv[field])
                json_val = otfs_json[field]
                if json_val is not None and abs(csv_val - json_val) > TOLERANCE:
                    errors.append(f"OTFS.{field}: csv={csv_val} json={json_val}")

        if oddm_csv and oddm_json:
            for field in ["BER", "throughput_bps", "CQI", "ACS"]:
                csv_val = float(oddm_csv[field])
                json_val = oddm_json[field]
                if json_val is not None and abs(csv_val - json_val) > TOLERANCE:
                    errors.append(f"ODDM.{field}: csv={csv_val} json={json_val}")

        if ai_csv and ai_json:
            for field in ["predicted_OTFS_ACS", "predicted_ODDM_ACS"]:
                csv_val = float(ai_csv[field])
                json_val = ai_json[field]
                if json_val is not None and abs(csv_val - json_val) > TOLERANCE:
                    errors.append(f"AI.{field}: csv={csv_val} json={json_val}")

        if errors:
            print(f"\n  [{scenario}, frame {frame}] FAIL:")
            for e in errors:
                print(f"    {e}")
            all_pass = False
        else:
            otfs_ber = otfs_json["BER"] if otfs_json else "N/A"
            oddm_ber = oddm_json["BER"] if oddm_json else "N/A"
            print(f"\n  [{scenario}, frame {frame}] PASS")
            print(f"    Conditions: {json_op['conditions']}")
            print(f"    OTFS BER={otfs_ber}, ODDM BER={oddm_ber}")

    print("\n" + "=" * 70)
    if all_pass:
        print("  ALL LOOKUP TESTS PASSED")
    else:
        print("  SOME LOOKUP TESTS FAILED")
    print("=" * 70)
    return all_pass


if __name__ == "__main__":
    ok = main()
    sys.exit(0 if ok else 1)
