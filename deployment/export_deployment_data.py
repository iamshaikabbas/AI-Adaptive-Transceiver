#!/usr/bin/env python3
"""Phase 11A — Export validated MATLAB Digital Twin results to deployment JSON.

Reads final_dataset.csv (Phase 6) and produces deployment/data/digital_twin_results.json.
Each operating point groups results for both OTFS and ODDM under shared physical conditions.

Source: final_dataset.csv (Phase 6, 2336 rows x 82 columns)
Output: deployment/data/digital_twin_results.json
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import csv

PROJECT_DIR = Path(__file__).resolve().parent.parent
CSV_PATH = (
    PROJECT_DIR
    / "OTFS MRC detection MATLAB code"
    / "Results"
    / "FinalEvaluation"
    / "final_dataset.csv"
)
OUTPUT_DIR = Path(__file__).resolve().parent / "data"
OUTPUT_JSON = OUTPUT_DIR / "digital_twin_results.json"
OUTPUT_META = OUTPUT_DIR / "metadata.json"

# Fields to extract from each waveform's row
WAVEFORM_FIELDS = [
    "BER", "SER", "PER", "throughput_bps", "spectral_efficiency",
    "CQI", "ACS", "detector_time_ms", "wall_clock_ms",
]

# AI prediction fields (only present in ai_adaptive rows)
AI_PREDICTION_FIELDS = [
    "predicted_OTFS_BER", "predicted_ODDM_BER",
    "predicted_OTFS_ACS", "predicted_ODDM_ACS",
    "predicted_OTFS_throughput", "predicted_ODDM_throughput",
    "predicted_OTFS_CQI", "predicted_ODDM_CQI",
]

# Oracle fields
ORACLE_FIELDS = [
    "oracle_waveform", "oracle_BER", "oracle_ACS",
    "ACS_regret", "BER_regret", "decision_correct",
]


def read_csv(path: Path) -> list[dict]:
    """Read CSV into list of dicts."""
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader)


def safe_float(val: str | None) -> float | None:
    """Convert string to float, returning None for empty/invalid values."""
    if val is None or val == "" or val == "nan":
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def make_op_id(conditions: dict) -> str:
    """Create deterministic operating-point ID from conditions."""
    env = conditions["environment"]
    spd = conditions["speed_kmph"]
    snr = conditions["snr_db"]
    dop = conditions["doppler_hz"]
    ch = conditions["channel_profile"]
    mod = conditions["modulation"]
    return f"{env}_{spd}_{snr}_{dop}_{ch}_{mod}"


def extract_waveform_metrics(row: dict) -> dict:
    """Extract waveform-specific metrics from a row."""
    metrics = {}
    for field in WAVEFORM_FIELDS:
        metrics[field] = safe_float(row.get(field))
    # Include detector used
    metrics["detector"] = row.get("detector", None)
    return metrics


def extract_ai_predictions(row: dict) -> dict | None:
    """Extract AI prediction fields from an ai_adaptive row."""
    if row.get("strategy") != "ai_adaptive":
        return None

    preds = {}
    for field in AI_PREDICTION_FIELDS:
        preds[field] = safe_float(row.get(field))

    preds["selected_waveform"] = row.get("selected_waveform") or None
    preds["oracle_waveform"] = row.get("oracle_waveform") or None
    preds["confidence"] = safe_float(row.get("confidence"))
    preds["switched"] = row.get("switched", "") == "1" or row.get("switched", "").lower() == "true"
    preds["switch_reason"] = row.get("switch_reason") or None
    preds["fallback_used"] = row.get("fallback_used", "") == "1" or row.get("fallback_used", "").lower() == "true"

    return preds


def extract_oracle(row: dict) -> dict | None:
    """Extract oracle fields from the oracle row."""
    if row.get("strategy") != "oracle":
        return None

    oracle = {}
    for field in ORACLE_FIELDS:
        val = row.get(field)
        if field in ("oracle_waveform",):
            oracle[field] = val or None
        else:
            oracle[field] = safe_float(val)
    return oracle


def export():
    """Main export function."""
    print(f"Reading {CSV_PATH}...")
    rows = read_csv(CSV_PATH)
    print(f"  Total rows: {len(rows)}")

    # Group by (scenario_id, frame)
    groups: dict[tuple[str, str], list[dict]] = {}
    for row in rows:
        key = (row["scenario_id"], row["frame"])
        groups.setdefault(key, []).append(row)

    print(f"  Unique (scenario, frame) groups: {len(groups)}")

    # Build operating points
    operating_points = []
    seen_ids: set[str] = set()

    for (scenario_id, frame), group_rows in sorted(groups.items()):
        # All rows in this group share the same conditions
        ref = group_rows[0]

        conditions = {
            "environment": ref["environment"],
            "speed_kmph": safe_float(ref["speed_kmph"]),
            "snr_db": safe_float(ref["snr_db"]),
            "doppler_hz": safe_float(ref["doppler_hz"]),
            "channel_profile": ref["channel_profile"],
            "modulation": int(ref["modulation"]) if ref.get("modulation") else None,
        }

        # Index rows by strategy
        by_strategy: dict[str, dict] = {}
        for r in group_rows:
            by_strategy[r["strategy"]] = r

        # Extract OTFS metrics (from fixed_otfs)
        otfs_row = by_strategy.get("fixed_otfs")
        otfs_metrics = extract_waveform_metrics(otfs_row) if otfs_row else None

        # Extract ODDM metrics (from fixed_oddm)
        oddm_row = by_strategy.get("fixed_oddm")
        oddm_metrics = extract_waveform_metrics(oddm_row) if oddm_row else None

        # Extract AI predictions (from ai_adaptive)
        ai_row = by_strategy.get("ai_adaptive")
        ai_preds = extract_ai_predictions(ai_row) if ai_row else None

        # Extract oracle (from oracle strategy)
        oracle_row = by_strategy.get("oracle")
        oracle_data = extract_oracle(oracle_row) if oracle_row else None

        # Build operating point
        op_id = make_op_id(conditions)

        # Handle duplicate IDs (shouldn't happen but be safe)
        if op_id in seen_ids:
            n = 2
            while f"{op_id}_{n}" in seen_ids:
                n += 1
            op_id = f"{op_id}_{n}"
        seen_ids.add(op_id)

        op = {
            "id": op_id,
            "source_scenario": scenario_id,
            "source_frame": int(frame) if frame else None,
            "conditions": conditions,
            "waveforms": {},
        }

        if otfs_metrics:
            op["waveforms"]["OTFS"] = otfs_metrics
        if oddm_metrics:
            op["waveforms"]["ODDM"] = oddm_metrics
        if ai_preds:
            op["ai_prediction"] = ai_preds
        if oracle_data:
            op["oracle"] = oracle_data

        operating_points.append(op)

    # Sort deterministically by ID
    operating_points.sort(key=lambda op: op["id"])

    # Compute source checksum
    source_checksum = hashlib.md5(CSV_PATH.read_bytes()).hexdigest()

    # Collect unique values for metadata
    environments = sorted(set(op["conditions"]["environment"] for op in operating_points))
    channels = sorted(set(op["conditions"]["channel_profile"] for op in operating_points))
    modulations = sorted(set(op["conditions"]["modulation"] for op in operating_points if op["conditions"]["modulation"]))
    speeds = [op["conditions"]["speed_kmph"] for op in operating_points if op["conditions"]["speed_kmph"] is not None]
    snrs = [op["conditions"]["snr_db"] for op in operating_points if op["conditions"]["snr_db"] is not None]
    dopplers = [op["conditions"]["doppler_hz"] for op in operating_points if op["conditions"]["doppler_hz"] is not None]

    # Build output
    output = {
        "schema_version": "1.0",
        "project": "AI-Adaptive-Transceiver",
        "policy_version": "phase3",
        "master_seed": 20260823,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": {
            "dataset": "final_dataset.csv",
            "simulation_engine": "MATLAB Digital Twin (dt_step_frame.m)",
            "model_version": "metric_models_v2",
            "source_checksum": source_checksum,
            "total_csv_rows": len(rows),
            "total_unique_scenarios": len(set(r["scenario_id"] for r in rows)),
            "total_unique_frames_groups": len(groups),
        },
        "operating_points": operating_points,
    }

    # Write JSON
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")

    # Write metadata
    import sys as _sys
    _sys.path.insert(0, str(PROJECT_DIR))
    # Avoid importing deployment module
    metadata = {
        "project": "AI-Adaptive-Transceiver",
        "schema_version": "1.0",
        "generation_timestamp": datetime.now(timezone.utc).isoformat(),
        "source_dataset": "final_dataset.csv",
        "source_checksum": source_checksum,
        "policy_version": "phase3",
        "model_version": "metric_models_v2",
        "master_seed": 20260823,
        "total_operating_points": len(operating_points),
        "total_csv_rows": len(rows),
        "total_unique_scenarios": len(set(r["scenario_id"] for r in rows)),
        "environments": environments,
        "channel_profiles": channels,
        "modulations": modulations,
        "detectors": ["MRC", "LMMSE"],
        "waveforms": ["OTFS", "ODDM"],
        "snr_range": [min(snrs), max(snrs)] if snrs else None,
        "speed_range": [min(speeds), max(speeds)] if speeds else None,
        "doppler_range": [min(dopplers), max(dopplers)] if dopplers else None,
        "deployment_mode": "precomputed",
        "matlab_required": False,
        "known_limitations": [
            "Continuous speed/snr/doppler values — each frame is a unique operating point",
            "Detector is waveform-dependent: OTFS uses MRC, ODDM uses LMMSE",
            "AI predictions only available for ai_adaptive strategy rows",
            "No latency_ms_modeled data (column fully null in source)",
            "No uncertainty estimates (columns fully null in source)",
        ],
    }
    OUTPUT_META.write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")

    # Report
    json_size = OUTPUT_JSON.stat().st_size
    avg_record = json_size / max(len(operating_points), 1)
    ai_count = sum(1 for op in operating_points if "ai_prediction" in op)
    oracle_count = sum(1 for op in operating_points if "oracle" in op)

    print(f"\nExport complete:")
    print(f"  Operating points: {len(operating_points)}")
    print(f"  With AI predictions: {ai_count}")
    print(f"  With oracle data: {oracle_count}")
    print(f"  JSON size: {json_size:,} bytes ({json_size / 1024:.1f} KB)")
    print(f"  Avg record size: {avg_record:,.0f} bytes")
    print(f"  Source checksum: {source_checksum}")
    print(f"  Output: {OUTPUT_JSON}")
    print(f"  Metadata: {OUTPUT_META}")


if __name__ == "__main__":
    export()
