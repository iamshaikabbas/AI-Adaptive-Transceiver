"""Phase 7 Validation Suite - 20 tests on final dataset and visualization outputs."""

import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path

import pandas as pd

EXPECTED_CHECKSUM = "faa877a248c0f599a87f21dabf4df358"
EXPECTED_ROWS = 2336
EXPECTED_COLS = 82
EXPECTED_SCENARIOS = list("ABCDEFGHIJKLMNOPQR")
EXPECTED_STRATEGIES = ["ai_adaptive", "fixed_oddm", "fixed_otfs", "oracle"]
ROWS_PER_STRATEGY = 584
GRAPH_COUNT_MIN = 30
GRAPH_COUNT_MAX = 42
REQUIRED_GRAPH_FIELDS = ["graph_id", "title", "filename", "category", "data_source"]
EXPECTED_CATEGORIES = [
    "01_system_overview", "02_waveform_comparison", "03_snr_analysis",
    "04_mobility_analysis", "05_channel_analysis", "06_modulation_analysis",
    "07_ai_analysis", "08_oracle_analysis", "09_digital_twin", "10_summary",
]
EXPECTED_AI_SWITCHES = 22
EXPECTED_ORACLE_AGREEMENT = 82.7
AGREEMENT_TOLERANCE = 1.0
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent


def md5(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def run_tests(dataset_path, viz_dir):
    results = []

    def record(num, name, passed, detail=""):
        results.append((num, name, passed, detail))

    # Test 1
    t1 = dataset_path.exists()
    record(1, "Source dataset exists", t1, str(dataset_path))
    if not t1:
        for i in range(2, 21):
            record(i, "Skipped (dependency)", False, "source dataset missing")
        return results

    # Test 2
    actual_checksum = md5(dataset_path)
    record(2, "Checksum matches", actual_checksum == EXPECTED_CHECKSUM,
           f"expected={EXPECTED_CHECKSUM} actual={actual_checksum}")

    # Load dataset
    df = pd.read_csv(dataset_path)

    # Test 3
    record(3, f"Row count = {EXPECTED_ROWS}", len(df) == EXPECTED_ROWS,
           f"actual={len(df)}")

    # Test 4
    record(4, f"Column count = {EXPECTED_COLS}", len(df.columns) == EXPECTED_COLS,
           f"actual={len(df.columns)}")

    # Test 5
    found_scenarios = sorted(df.scenario_id.unique())
    record(5, "All 18 scenarios (A-R) present",
           found_scenarios == EXPECTED_SCENARIOS,
           f"found={found_scenarios}")

    # Test 6
    found_strategies = sorted(df.strategy.unique())
    record(6, "All 4 strategies present",
           found_strategies == EXPECTED_STRATEGIES,
           f"found={found_strategies}")

    # Test 7
    graph_index_path = viz_dir / "graph_index.json"
    gi_exists = graph_index_path.exists()
    record(7, "graph_index.json exists", gi_exists)

    graph_index = None
    if gi_exists:
        try:
            with open(graph_index_path, encoding="utf-8") as f:
                graph_index = json.load(f)
            record(8, "graph_index.json is valid JSON", True)
        except (json.JSONDecodeError, ValueError) as exc:
            record(8, "graph_index.json is valid JSON", False, str(exc))

    if graph_index is None:
        graph_index = []
        for i in range(9, 13):
            record(i, "Skipped (dependency)", False, "graph_index invalid")

    # Test 8
    if graph_index:
        gc = len(graph_index)
        record(8, f"Graph count between {GRAPH_COUNT_MIN}-{GRAPH_COUNT_MAX}",
               GRAPH_COUNT_MIN <= gc <= GRAPH_COUNT_MAX, f"actual={gc}")

        # Test 9
        missing_fields = []
        for idx, g in enumerate(graph_index):
            for field in REQUIRED_GRAPH_FIELDS:
                if field not in g or not g[field]:
                    missing_fields.append(f"graph[{idx}].{field}")
        record(9, "Every graph has required fields",
               len(missing_fields) == 0,
               f"missing={missing_fields}" if missing_fields else "all present")

        # Test 10 - files are in category subdirectories
        missing_files = []
        for g in graph_index:
            fn = g.get("filename", "")
            cat = g.get("category", "")
            p = viz_dir / cat / fn
            if not p.exists():
                missing_files.append(f"{cat}/{fn}")
        record(10, "All graph PNG files exist on disk",
               len(missing_files) == 0,
               f"missing={missing_files}" if missing_files else "all found")

        # Test 11
        zero_files = []
        for g in graph_index:
            fn = g.get("filename", "")
            cat = g.get("category", "")
            p = viz_dir / cat / fn
            if p.exists() and p.stat().st_size == 0:
                zero_files.append(fn)
        record(11, "All graph files have non-zero size",
               len(zero_files) == 0,
               f"zero_size={zero_files}" if zero_files else "all non-zero")

        # Test 12
        from collections import Counter
        filenames = [g.get("filename", "") for g in graph_index]
        dupes = [fn for fn, cnt in Counter(filenames).items() if cnt > 1]
        record(12, "No duplicate filenames in graph_index",
               len(dupes) == 0,
               f"duplicates={dupes}" if dupes else "no duplicates")
    else:
        for i in range(9, 13):
            record(i, "Skipped (dependency)", False, "graph_index invalid")

    # Test 13
    missing_dirs = [c for c in EXPECTED_CATEGORIES if not (viz_dir / c).is_dir()]
    record(13, "All 10 category directories exist",
           len(missing_dirs) == 0,
           f"missing={missing_dirs}" if missing_dirs else "all present")

    # Tests 14-16 - reports at project root
    for num, name in [
        (14, "PHASE7_VISUAL_ANALYSIS.md"),
        (15, "PHASE7_EXECUTIVE_SUMMARY.md"),
        (16, "PHASE7_FINAL_REPORT.md"),
    ]:
        p = SCRIPT_DIR.parent.parent / name
        record(num, f"{name} exists", p.exists(), str(p))

    # Test 17
    if "policy_version" in df.columns:
        bad = df[df.policy_version != "phase3"]
        record(17, "No Phase 4 results in dataset (policy_version=phase3)",
               len(bad) == 0, f"bad_count={len(bad)}")
    else:
        record(17, "No Phase 4 results (policy_version column missing)",
               False, "column 'policy_version' not in header")

    # Test 18
    if "switched" in df.columns:
        ai = df[df.strategy == "ai_adaptive"]
        switch_count = int(ai.switched.sum())
        record(18, "22 AI switches in dataset",
               switch_count == EXPECTED_AI_SWITCHES,
               f"actual={switch_count}")
    else:
        record(18, "22 AI switches in dataset",
               False, "column 'switched' not in header")

    # Test 19
    if "decision_correct" in df.columns:
        ai = df[df.strategy == "ai_adaptive"]
        agree_pct = ai.decision_correct.mean() * 100
        within = abs(agree_pct - EXPECTED_ORACLE_AGREEMENT) <= AGREEMENT_TOLERANCE
        record(19, f"~82.7% oracle agreement (tol={AGREEMENT_TOLERANCE}%)",
               within,
               f"actual={agree_pct:.1f}% expected~{EXPECTED_ORACLE_AGREEMENT}%")
    else:
        record(19, "~82.7% oracle agreement",
               False, "column 'decision_correct' not in header")

    # Test 20
    final_checksum = md5(dataset_path)
    record(20, "Dataset unchanged (checksum still matches)",
           final_checksum == EXPECTED_CHECKSUM,
           f"current={final_checksum} expected={EXPECTED_CHECKSUM}")

    return results


def main():
    parser = argparse.ArgumentParser(
        description="Phase 7 validation suite - 20 checks on dataset and visuals."
    )
    parser.add_argument("--dataset", type=Path,
        default=SCRIPT_DIR.parent /
                "Results" / "FinalEvaluation" / "final_dataset.csv")
    parser.add_argument("--visualizations-dir", type=Path,
        default=SCRIPT_DIR.parent /
                "Results" / "FinalEvaluation" / "Visualizations")
    args = parser.parse_args()

    print("=" * 64)
    print("  PHASE 7 VALIDATION SUITE  (20 tests)")
    print("=" * 64)
    print(f"  Dataset : {args.dataset}")
    print(f"  Visuals : {args.visualizations_dir}")
    print("-" * 64)

    t0 = time.perf_counter()
    results = run_tests(args.dataset, args.visualizations_dir)
    elapsed = time.perf_counter() - t0

    pass_count = sum(1 for _, _, ok, _ in results if ok)
    fail_count = len(results) - pass_count

    for num, name, ok, detail in results:
        tag = "PASS" if ok else "FAIL"
        suffix = f"  ({detail})" if detail else ""
        print(f"  [{tag}] {num:>2}. {name}{suffix}")

    print("-" * 64)
    print(f"  {pass_count}/{len(results)} passed  |  {fail_count} failed  |  {elapsed:.3f}s")
    print("=" * 64)
    sys.exit(0 if fail_count == 0 else 1)


if __name__ == "__main__":
    main()
