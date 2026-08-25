"""
phase6_final_dataset.py
========================
Phase 6 post-processing: consolidate MATLAB Digital Twin traces into a final
dataset and comprehensive evaluation summaries.

Reads all trace CSVs from Results/DigitalTwin/<scenario>/<strategy>_trace.csv
for scenarios A-R (lowercase a-r), merges with run_manifest.json metadata,
computes derived columns, writes final_dataset.csv plus multiple summary files,
predicted-vs-actual, oracle-comparison, switching analysis, fixed-vs-adaptive,
and a full data-quality report.

Usage:
    python phase6_final_dataset.py
    python phase6_final_dataset.py --dt-root <path>
"""

import argparse
import json
import math
import os
import sys
import time
from collections import defaultdict

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

DEFAULT_DT_ROOT = os.path.normpath(
    os.path.join(
        SCRIPT_DIR,
        os.pardir,
        "Results",
        "DigitalTwin",
    )
)

OUTPUT_DIR = os.path.normpath(
    os.path.join(
        SCRIPT_DIR,
        os.pardir,
        "Results",
        "FinalEvaluation",
    )
)

SCENARIO_LETTERS = [chr(ord("a") + i) for i in range(18)]  # a-r

STRATEGIES = ["fixed_otfs", "fixed_oddm", "ai_adaptive", "oracle"]

VALID_WAVEFORMS = {"OTFS", "ODDM"}

VALID_CHANNELS = {"EPA", "EVA", "ETU"}

VALID_MODULATIONS = {4, 16, 64}

VALID_STRATEGIES = set(STRATEGIES)

MODULATION_MAP = {4: "QPSK", 16: "16QAM", 64: "64QAM"}

ENVIRONMENT_TIER = {
    "commute": "A",
    "high_speed_rail": "B",
    "pedestrian_day": "C",
    "stress": "D",
    "tune": "E-H",
    "heldout": "I-L",
    "difficult": "M-R",
}

REQUIRED_TRACE_COLUMNS = [
    "frame", "scenario_id", "environment", "strategy", "waveform",
    "BER", "SER", "throughput_bps", "CQI", "ACS",
    "snr_db", "speed_kmph", "doppler_hz", "modulation", "channel_profile",
    "actual_BER_OTFS", "actual_ACS_OTFS", "actual_BER_ODDM", "actual_ACS_ODDM",
    "oracle_waveform", "oracle_BER", "oracle_ACS",
    "decision_correct",
    "predicted_OTFS_BER", "predicted_ODDM_BER",
    "predicted_OTFS_ACS", "predicted_ODDM_ACS",
]

SUMMARY_STATS = ["mean", "std", "min", "median", "max", "p10", "p90", "count"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _mod_label(val):
    """Map numeric constellation order to human label."""
    v = int(val)
    return MODULATION_MAP.get(v, f"MOD{v}")


def _round_snr(val):
    """Round SNR to nearest integer dB."""
    return round(float(val))


def _round_speed(val):
    """Round speed to nearest 10 km/h."""
    return round(float(val) / 10.0) * 10.0


def _percentile_safe(series, q):
    """Compute percentile, returning NaN if empty."""
    s = series.dropna()
    if s.empty:
        return np.nan
    return float(np.percentile(s, q))


def _agg_dict(metrics):
    """Build aggregation dict for a list of metric column names."""
    d = {}
    for m in metrics:
        d[m] = ["mean", "std", "min", "median", "max",
                 lambda x: _percentile_safe(x, 10),
                 lambda x: _percentile_safe(x, 90),
                 "count"]
    return d


def _safe_div(num, den):
    """Safe division returning NaN when denominator is zero."""
    if den == 0 or np.isnan(den):
        return np.nan
    return num / den


def _flatten_agg(df_agg, group_cols):
    """Flatten a multi-level aggregation result into a clean DataFrame."""
    new_cols = []
    for col in df_agg.columns:
        if isinstance(col, tuple):
            if col[1] in ("mean", "std", "min", "median", "max", "count"):
                new_cols.append(f"{col[0]}_{col[1]}")
            elif col[1] == "<lambda_0>":
                new_cols.append(f"{col[0]}_p10")
            elif col[1] == "<lambda_1>":
                new_cols.append(f"{col[0]}_p90")
            else:
                new_cols.append(f"{col[0]}_{col[1]}")
        else:
            new_cols.append(col)
    df_agg.columns = new_cols
    return df_agg.reset_index()


def _append_percentile_aliases(df):
    """After flattening, rename <lambda_0/1> columns to p10/p90."""
    renames = {}
    for c in df.columns:
        if "<lambda_0>" in c:
            renames[c] = c.replace("<lambda_0>", "p10")
        elif "<lambda_1>" in c:
            renames[c] = c.replace("<lambda_1>", "p90")
    if renames:
        df.rename(columns=renames, inplace=True)
    return df


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------
def load_all_traces(dt_root):
    """Load all trace CSVs and manifests from DigitalTwin directory.

    Returns:
        all_traces: list of DataFrames (one per loaded trace)
        manifest_info: dict mapping scenario_id -> manifest metadata
        load_report: list of (scenario, strategy, status) tuples
    """
    all_traces = []
    manifest_info = {}
    load_report = []

    for sc in SCENARIO_LETTERS:
        sc_dir = os.path.join(dt_root, sc)
        if not os.path.isdir(sc_dir):
            load_report.append((sc, "*", "dir_not_found"))
            continue

        # Load manifest
        manifest_path = os.path.join(sc_dir, "run_manifest.json")
        if os.path.isfile(manifest_path):
            try:
                with open(manifest_path, "r", encoding="utf-8") as fh:
                    mft = json.load(fh)
                master_seed = mft.get("seed0", np.nan)
                policy_version = mft.get("policy", "unknown")
                manifest_info[sc] = {
                    "master_seed": master_seed,
                    "policy_version": policy_version,
                    "manifest_raw": mft,
                }
            except (OSError, ValueError, json.JSONDecodeError) as exc:
                manifest_info[sc] = {
                    "master_seed": np.nan,
                    "policy_version": "unknown",
                    "manifest_raw": {},
                    "error": str(exc),
                }
                load_report.append((sc, "manifest", f"parse_error: {exc}"))
        else:
            manifest_info[sc] = {
                "master_seed": np.nan,
                "policy_version": "unknown",
                "manifest_raw": {},
            }

        # Load each strategy trace
        for strat in STRATEGIES:
            csv_path = os.path.join(sc_dir, f"{strat}_trace.csv")
            if not os.path.isfile(csv_path):
                load_report.append((sc, strat, "file_not_found"))
                continue
            try:
                df = pd.read_csv(csv_path, encoding="utf-8")
                if df.empty:
                    load_report.append((sc, strat, "empty_csv"))
                    continue
                all_traces.append(df)
                load_report.append((sc, strat, f"ok ({len(df)} rows)"))
            except Exception as exc:
                load_report.append((sc, strat, f"read_error: {exc}"))

    return all_traces, manifest_info, load_report


# ---------------------------------------------------------------------------
# Derive columns and rename
# ---------------------------------------------------------------------------
def derive_and_rename(df_all, manifest_info):
    """Add derived columns, rename TP columns, fix types."""
    # Rename predicted throughput columns for spec compliance
    rename_map = {}
    if "predicted_OTFS_TP" in df_all.columns:
        rename_map["predicted_OTFS_TP"] = "predicted_OTFS_throughput"
    if "predicted_ODDM_TP" in df_all.columns:
        rename_map["predicted_ODDM_TP"] = "predicted_ODDM_throughput"
    if rename_map:
        df_all.rename(columns=rename_map, inplace=True)

    # master_seed and policy_version from manifest
    # manifest_info is keyed lowercase ('a'..'r'), scenario_id in traces is uppercase ('A'..'R')
    df_all["master_seed"] = df_all["scenario_id"].map(
        lambda s: manifest_info.get(str(s).lower(), {}).get("master_seed", np.nan)
    )
    df_all["policy_version"] = df_all["scenario_id"].map(
        lambda s: manifest_info.get(str(s).lower(), {}).get("policy_version", "unknown")
    )

    # experiment_id
    df_all["experiment_id"] = df_all.apply(
        lambda r: f"{r['scenario_id']}_{r['strategy']}_{r['master_seed']}"
        if pd.notna(r["master_seed"]) else f"{r['scenario_id']}_{r['strategy']}_nan",
        axis=1,
    )

    # modulation_label
    if "modulation" in df_all.columns:
        df_all["modulation_label"] = df_all["modulation"].apply(
            lambda v: _mod_label(v) if pd.notna(v) else "unknown"
        )
    else:
        df_all["modulation_label"] = "unknown"

    # Ensure numeric types for key columns
    numeric_cols = [
        "BER", "SER", "throughput_bps", "CQI", "ACS",
        "snr_db", "speed_kmph", "doppler_hz", "modulation",
        "actual_BER_OTFS", "actual_ACS_OTFS", "actual_BER_ODDM", "actual_ACS_ODDM",
        "oracle_BER", "oracle_ACS", "ACS_regret", "BER_regret", "relative_BER_regret",
        "predicted_OTFS_BER", "predicted_ODDM_BER",
        "predicted_OTFS_ACS", "predicted_ODDM_ACS",
        "predicted_OTFS_throughput", "predicted_ODDM_throughput",
        "predicted_OTFS_CQI", "predicted_ODDM_CQI",
        "spectral_efficiency", "tp_cap_bps", "se_cap",
        "actual_TP_OTFS", "actual_TP_ODDM",
    ]
    for col in numeric_cols:
        if col in df_all.columns:
            df_all[col] = pd.to_numeric(df_all[col], errors="coerce")

    return df_all


# ---------------------------------------------------------------------------
# Summary builders
# ---------------------------------------------------------------------------
def build_environment_summary(df):
    """Group by (environment, strategy): mean BER, throughput, CQI, ACS, switch_count, oracle_agreement."""
    metrics = ["BER", "throughput_bps", "CQI", "ACS"]
    agg = {}
    for m in metrics:
        agg[m] = "mean"

    g = df.groupby(["environment", "strategy"], as_index=False).agg(agg)
    # switch_count
    if "switched" in df.columns:
        switch_counts = (
            df[df["switched"] == 1]
            .groupby(["environment", "strategy"], as_index=False)
            .size()
            .rename(columns={"size": "switch_count"})
        )
        g = g.merge(switch_counts, on=["environment", "strategy"], how="left")
    else:
        g["switch_count"] = 0
    g["switch_count"] = g["switch_count"].fillna(0).astype(int)

    # oracle_agreement for ai_adaptive
    ai = df[df["strategy"] == "ai_adaptive"]
    if not ai.empty and "decision_correct" in ai.columns:
        agree = (
            ai.groupby(["environment", "strategy"], as_index=False)["decision_correct"]
            .mean()
            .rename(columns={"decision_correct": "oracle_agreement"})
        )
        g = g.merge(agree, on=["environment", "strategy"], how="left")
    else:
        g["oracle_agreement"] = np.nan

    # Also add switch_count for non-ai strategies (always 0)
    g["switch_count"] = g["switch_count"].fillna(0).astype(int)
    g["oracle_agreement"] = g["oracle_agreement"].fillna(np.nan)
    return g


def build_scenario_summary(df):
    """Group by (scenario_id, strategy)."""
    metrics = ["BER", "throughput_bps", "CQI", "ACS"]
    agg = {}
    for m in metrics:
        agg[m] = "mean"

    g = df.groupby(["scenario_id", "strategy"], as_index=False).agg(agg)
    if "switched" in df.columns:
        switch_counts = (
            df[df["switched"] == 1]
            .groupby(["scenario_id", "strategy"], as_index=False)
            .size()
            .rename(columns={"size": "switch_count"})
        )
        g = g.merge(switch_counts, on=["scenario_id", "strategy"], how="left")
    else:
        g["switch_count"] = 0
    g["switch_count"] = g["switch_count"].fillna(0).astype(int)

    ai = df[df["strategy"] == "ai_adaptive"]
    if not ai.empty and "decision_correct" in ai.columns:
        agree = (
            ai.groupby(["scenario_id", "strategy"], as_index=False)["decision_correct"]
            .mean()
            .rename(columns={"decision_correct": "oracle_agreement"})
        )
        g = g.merge(agree, on=["scenario_id", "strategy"], how="left")
    else:
        g["oracle_agreement"] = np.nan

    return g


def build_snr_summary(df):
    """Group by (snr_db_rounded, waveform, strategy)."""
    df = df.copy()
    df["snr_db_rounded"] = df["snr_db"].apply(
        lambda v: _round_snr(v) if pd.notna(v) else np.nan
    )
    metrics = ["BER", "throughput_bps", "CQI", "ACS"]
    agg = {m: "mean" for m in metrics}
    g = df.groupby(["snr_db_rounded", "waveform", "strategy"], as_index=False).agg(agg)
    return g


def build_mobility_summary(df):
    """Group by (speed_kmph_rounded, doppler_hz, strategy, waveform)."""
    df = df.copy()
    df["speed_kmph_rounded"] = df["speed_kmph"].apply(
        lambda v: _round_speed(v) if pd.notna(v) else np.nan
    )
    metrics = ["BER", "throughput_bps", "CQI", "ACS"]
    agg = {m: "mean" for m in metrics}
    g = df.groupby(
        ["speed_kmph_rounded", "doppler_hz", "strategy", "waveform"],
        as_index=False,
    ).agg(agg)
    return g


def build_channel_summary(df):
    """Group by (channel_profile, waveform, strategy)."""
    metrics = ["BER", "throughput_bps", "CQI", "ACS"]
    agg = {m: "mean" for m in metrics}
    g = df.groupby(["channel_profile", "waveform", "strategy"], as_index=False).agg(agg)
    return g


def build_modulation_summary(df):
    """Group by (modulation_label, waveform, strategy)."""
    metrics = ["BER", "throughput_bps", "CQI", "ACS"]
    agg = {m: "mean" for m in metrics}
    g = df.groupby(["modulation_label", "waveform", "strategy"], as_index=False).agg(agg)
    return g


# ---------------------------------------------------------------------------
# Derived tables
# ---------------------------------------------------------------------------
def build_predicted_vs_actual(df):
    """AI-adaptive rows: predicted vs actual metrics."""
    ai = df[df["strategy"] == "ai_adaptive"].copy()
    if ai.empty:
        return pd.DataFrame()

    out = pd.DataFrame()
    out["frame"] = ai["frame"]
    out["scenario_id"] = ai["scenario_id"]
    out["environment"] = ai["environment"]
    out["snr_db"] = ai["snr_db"]
    out["speed_kmph"] = ai["speed_kmph"]
    out["predicted_OTFS_BER"] = ai["predicted_OTFS_BER"]
    out["actual_BER_OTFS"] = ai["actual_BER_OTFS"]
    out["predicted_ODDM_BER"] = ai["predicted_ODDM_BER"]
    out["actual_BER_ODDM"] = ai["actual_BER_ODDM"]
    out["predicted_OTFS_throughput"] = ai["predicted_OTFS_throughput"]
    out["actual_TP_OTFS"] = ai["actual_TP_OTFS"]
    out["predicted_ODDM_throughput"] = ai["predicted_ODDM_throughput"]
    out["actual_TP_ODDM"] = ai["actual_TP_ODDM"]
    out["predicted_OTFS_CQI"] = ai["predicted_OTFS_CQI"]
    # CQI from trace for the selected waveform (the executed waveform's CQI)
    out["CQI_OTFS_from_trace"] = ai["CQI"]
    out["predicted_OTFS_ACS"] = ai["predicted_OTFS_ACS"]
    out["actual_ACS_OTFS"] = ai["actual_ACS_OTFS"]
    out["predicted_ODDM_ACS"] = ai["predicted_ODDM_ACS"]
    out["actual_ACS_ODDM"] = ai["actual_ACS_ODDM"]

    out.reset_index(drop=True, inplace=True)
    return out


def build_oracle_comparison(df):
    """AI-adaptive rows: compare to oracle."""
    ai = df[df["strategy"] == "ai_adaptive"].copy()
    if ai.empty:
        return pd.DataFrame()

    out = pd.DataFrame()
    out["frame"] = ai["frame"]
    out["scenario_id"] = ai["scenario_id"]
    out["environment"] = ai["environment"]
    out["snr_db"] = ai["snr_db"]
    out["speed_kmph"] = ai["speed_kmph"]
    out["ai_waveform"] = ai["waveform"]
    out["oracle_waveform"] = ai["oracle_waveform"]
    out["decision_correct"] = ai["decision_correct"]
    out["ACS"] = ai["ACS"]
    out["oracle_ACS"] = ai["oracle_ACS"]
    out["ACS_regret"] = ai["ACS_regret"]
    out["BER"] = ai["BER"]
    out["oracle_BER"] = ai["oracle_BER"]
    out["BER_regret"] = ai["BER_regret"]
    out["relative_BER_regret"] = ai["relative_BER_regret"]

    out.reset_index(drop=True, inplace=True)
    return out


def build_fixed_vs_adaptive(df):
    """One row per strategy with aggregate stats."""
    rows = []
    for strat in STRATEGIES:
        sdf = df[df["strategy"] == strat]
        if sdf.empty:
            continue
        row = {"strategy": strat}
        # BER stats
        row["mean_BER"] = sdf["BER"].mean() if "BER" in sdf.columns else np.nan
        row["median_BER"] = sdf["BER"].median() if "BER" in sdf.columns else np.nan
        row["p90_BER"] = _percentile_safe(sdf["BER"], 90) if "BER" in sdf.columns else np.nan
        # Throughput stats
        if "throughput_bps" in sdf.columns:
            row["mean_throughput"] = sdf["throughput_bps"].mean()
            row["median_throughput"] = sdf["throughput_bps"].median()
            row["p90_throughput"] = _percentile_safe(sdf["throughput_bps"], 90)
        else:
            row["mean_throughput"] = np.nan
            row["median_throughput"] = np.nan
            row["p90_throughput"] = np.nan
        # CQI
        row["mean_CQI"] = sdf["CQI"].mean() if "CQI" in sdf.columns else np.nan
        # SE
        row["mean_spectral_efficiency"] = (
            sdf["spectral_efficiency"].mean()
            if "spectral_efficiency" in sdf.columns
            else np.nan
        )
        # ACS
        if "ACS" in sdf.columns:
            row["mean_ACS"] = sdf["ACS"].mean()
            row["p90_ACS"] = _percentile_safe(sdf["ACS"], 90)
        else:
            row["mean_ACS"] = np.nan
            row["p90_ACS"] = np.nan
        # Detector time
        if "detector_time_ms" in sdf.columns:
            row["mean_detector_time_ms"] = sdf["detector_time_ms"].mean()
        else:
            row["mean_detector_time_ms"] = np.nan
        # Switch count
        if "switched" in sdf.columns:
            row["switch_count"] = int(sdf["switched"].sum())
        else:
            row["switch_count"] = 0
        # Oracle agreement (only for ai_adaptive)
        if strat == "ai_adaptive" and "decision_correct" in sdf.columns:
            row["oracle_agreement"] = sdf["decision_correct"].mean()
        else:
            row["oracle_agreement"] = np.nan
        # ACS regret
        if strat == "ai_adaptive" and "ACS_regret" in sdf.columns:
            row["mean_ACS_regret"] = sdf["ACS_regret"].mean()
            row["p90_ACS_regret"] = _percentile_safe(sdf["ACS_regret"], 90)
        else:
            row["mean_ACS_regret"] = np.nan
            row["p90_ACS_regret"] = np.nan

        rows.append(row)

    return pd.DataFrame(rows)


def build_switching_analysis(df):
    """Switching analysis: total-level and per-environment stats."""
    ai = df[df["strategy"] == "ai_adaptive"].copy()
    if ai.empty:
        return pd.DataFrame()

    rows = []
    # Total level
    total_row = _compute_switch_stats(ai, "ALL")
    rows.append(total_row)

    # Per environment
    for env, eg in ai.groupby("environment"):
        row = _compute_switch_stats(eg, env)
        rows.append(row)

    return pd.DataFrame(rows)


def _compute_switch_stats(sub_df, label):
    """Compute switching statistics for a subset of ai_adaptive rows."""
    row = {"level": label}
    row["total_frames"] = len(sub_df)

    if "switched" in sub_df.columns:
        n_switches = int(sub_df["switched"].sum())
    else:
        n_switches = 0
    row["total_switches"] = n_switches
    row["switch_rate"] = _safe_div(n_switches, len(sub_df))

    if "waveform" in sub_df.columns:
        row["OTFS_frames"] = int((sub_df["waveform"] == "OTFS").sum())
        row["ODDM_frames"] = int((sub_df["waveform"] == "ODDM").sum())
    else:
        row["OTFS_frames"] = 0
        row["ODDM_frames"] = 0

    # Dwell times (consecutive frames with same waveform)
    if "waveform" in sub_df.columns:
        dwells = []
        current_wf = None
        current_len = 0
        for wf in sub_df["waveform"].values:
            if pd.isna(wf):
                continue
            if wf == current_wf:
                current_len += 1
            else:
                if current_wf is not None and current_len > 0:
                    dwells.append(current_len)
                current_wf = wf
                current_len = 1
        if current_wf is not None and current_len > 0:
            dwells.append(current_len)

        if dwells:
            row["avg_dwell"] = float(np.mean(dwells))
            row["min_dwell"] = float(np.min(dwells))
            row["max_dwell"] = float(np.max(dwells))
        else:
            row["avg_dwell"] = np.nan
            row["min_dwell"] = np.nan
            row["max_dwell"] = np.nan
    else:
        row["avg_dwell"] = np.nan
        row["min_dwell"] = np.nan
        row["max_dwell"] = np.nan

    # Oracle agreement
    if "decision_correct" in sub_df.columns:
        dc = sub_df["decision_correct"].dropna()
        row["oracle_agreement"] = dc.mean() if len(dc) > 0 else np.nan
    else:
        row["oracle_agreement"] = np.nan

    return row


# ---------------------------------------------------------------------------
# Data quality checks
# ---------------------------------------------------------------------------
def run_data_quality_checks(df):
    """Run comprehensive data quality checks. Returns dict for JSON report."""
    report = {
        "total_rows": int(len(df)),
        "total_columns": int(len(df.columns)),
        "scenarios_found": sorted(df["scenario_id"].unique().tolist())
        if "scenario_id" in df.columns else [],
        "strategies_found": sorted(df["strategy"].unique().tolist())
        if "strategy" in df.columns else [],
        "checks": {},
    }

    # 1. No duplicate rows (scenario_id + frame + strategy unique)
    if all(c in df.columns for c in ["scenario_id", "frame", "strategy"]):
        dup_mask = df.duplicated(subset=["scenario_id", "frame", "strategy"], keep=False)
        n_dups = int(dup_mask.sum())
        report["checks"]["no_duplicates"] = {
            "pass": n_dups == 0,
            "duplicate_count": n_dups,
        }
    else:
        report["checks"]["no_duplicates"] = {"pass": False, "error": "missing columns"}

    # 2. No missing required fields
    # AI-specific columns only checked on ai_adaptive rows; other columns
    # checked globally.
    AI_ONLY_COLS = {
        "predicted_OTFS_BER", "predicted_ODDM_BER",
        "predicted_OTFS_ACS", "predicted_ODDM_ACS",
        "decision_correct",
    }
    missing_fields = {}
    ai_df_q = df[df["strategy"] == "ai_adaptive"] if "strategy" in df.columns else df
    for col in REQUIRED_TRACE_COLUMNS:
        if col in df.columns:
            if col in AI_ONLY_COLS:
                n_miss = int(ai_df_q[col].isna().sum())
                missing_fields[col] = {"null_in_ai_rows": n_miss, "scope": "ai_adaptive_only"}
            else:
                n_miss = int(df[col].isna().sum())
                missing_fields[col] = n_miss
        else:
            missing_fields[col] = "column_absent"
    any_missing_issues = False
    for col, val in missing_fields.items():
        if isinstance(val, dict):
            if val["null_in_ai_rows"] > 0:
                any_missing_issues = True
        elif val != 0 and val != "column_absent":
            any_missing_issues = True
    report["checks"]["no_missing_required"] = {
        "pass": not any_missing_issues,
        "details": missing_fields,
    }

    # 3. BER >= 0 and finite
    if "BER" in df.columns:
        ber = df["BER"].dropna()
        n_neg = int((ber < 0).sum())
        n_inf = int(np.isinf(ber).sum())
        report["checks"]["ber_nonnegative_finite"] = {
            "pass": n_neg == 0 and n_inf == 0,
            "negative_count": n_neg,
            "infinite_count": n_inf,
        }
    else:
        report["checks"]["ber_nonnegative_finite"] = {"pass": False, "error": "BER column missing"}

    # 4. BER <= 1
    if "BER" in df.columns:
        ber = df["BER"].dropna()
        n_over = int((ber > 1).sum())
        report["checks"]["ber_le_1"] = {
            "pass": n_over == 0,
            "over_one_count": n_over,
        }
    else:
        report["checks"]["ber_le_1"] = {"pass": False, "error": "BER column missing"}

    # 5. throughput_bps >= 0
    if "throughput_bps" in df.columns:
        tp = df["throughput_bps"].dropna()
        n_neg = int((tp < 0).sum())
        report["checks"]["throughput_nonnegative"] = {
            "pass": n_neg == 0,
            "negative_count": n_neg,
        }
    else:
        report["checks"]["throughput_nonnegative"] = {"pass": False, "error": "column missing"}

    # 6. CQI >= 0 and <= 15
    if "CQI" in df.columns:
        cqi = df["CQI"].dropna()
        n_bad = int(((cqi < 0) | (cqi > 15)).sum())
        report["checks"]["cqi_range"] = {
            "pass": n_bad == 0,
            "out_of_range_count": n_bad,
        }
    else:
        report["checks"]["cqi_range"] = {"pass": False, "error": "CQI column missing"}

    # 7. ACS >= 0 and <= 1
    if "ACS" in df.columns:
        acs = df["ACS"].dropna()
        n_bad = int(((acs < 0) | (acs > 1)).sum())
        report["checks"]["acs_range"] = {
            "pass": n_bad == 0,
            "out_of_range_count": n_bad,
        }
    else:
        report["checks"]["acs_range"] = {"pass": False, "error": "ACS column missing"}

    # 8. SER >= BER (diagnostic - report but don't fail)
    if "BER" in df.columns and "SER" in df.columns:
        both = df[["BER", "SER"]].dropna()
        n_violations = int((both["SER"] < both["BER"] - 1e-12).sum())
        report["checks"]["ser_ge_ber"] = {
            "pass": True,  # diagnostic only, never fail
            "violation_count": n_violations,
            "total_compared": len(both),
            "note": "diagnostic only - SER >= BER is expected but not enforced",
        }
    else:
        report["checks"]["ser_ge_ber"] = {"pass": True, "error": "columns missing"}

    # 9. Valid waveform names
    if "waveform" in df.columns:
        bad_wf = df[~df["waveform"].isin(VALID_WAVEFORMS)]["waveform"].dropna().unique().tolist()
        report["checks"]["valid_waveforms"] = {
            "pass": len(bad_wf) == 0,
            "invalid_values": bad_wf,
        }
    else:
        report["checks"]["valid_waveforms"] = {"pass": False, "error": "column missing"}

    # 10. Valid channel names
    if "channel_profile" in df.columns:
        bad_ch = df[~df["channel_profile"].isin(VALID_CHANNELS)]["channel_profile"].dropna().unique().tolist()
        report["checks"]["valid_channels"] = {
            "pass": len(bad_ch) == 0,
            "invalid_values": bad_ch,
        }
    else:
        report["checks"]["valid_channels"] = {"pass": False, "error": "column missing"}

    # 11. Valid modulation values
    if "modulation" in df.columns:
        mods = df["modulation"].dropna().unique()
        bad_mods = [int(m) for m in mods if int(m) not in VALID_MODULATIONS]
        report["checks"]["valid_modulations"] = {
            "pass": len(bad_mods) == 0,
            "invalid_values": bad_mods,
        }
    else:
        report["checks"]["valid_modulations"] = {"pass": False, "error": "column missing"}

    # 12. Valid strategies
    if "strategy" in df.columns:
        bad_strats = df[~df["strategy"].isin(VALID_STRATEGIES)]["strategy"].dropna().unique().tolist()
        report["checks"]["valid_strategies"] = {
            "pass": len(bad_strats) == 0,
            "invalid_values": bad_strats,
        }
    else:
        report["checks"]["valid_strategies"] = {"pass": False, "error": "column missing"}

    # 13. Consistent seeds (same chan_checksum/payload_sum per frame across strategies)
    if all(c in df.columns for c in ["scenario_id", "frame", "chan_checksum", "payload_sum", "strategy"]):
        grouped = df.groupby(["scenario_id", "frame"])
        n_inconsistent = 0
        examples = []
        for (sc, fr), grp in grouped:
            if len(grp) < 2:
                continue
            for col in ["chan_checksum", "payload_sum"]:
                vals = grp[col].dropna().unique()
                if len(vals) > 1:
                    n_inconsistent += 1
                    if len(examples) < 5:
                        examples.append(
                            f"scenario={sc} frame={fr} {col} values={vals.tolist()}"
                        )
        report["checks"]["consistent_seeds"] = {
            "pass": n_inconsistent == 0,
            "inconsistent_count": n_inconsistent,
            "examples": examples,
        }
    else:
        report["checks"]["consistent_seeds"] = {"pass": False, "error": "missing columns"}

    # 14. latency_ms_modeled always NaN
    if "latency_ms_modeled" in df.columns:
        n_not_nan = int(df["latency_ms_modeled"].notna().sum())
        report["checks"]["latency_modeled_nan"] = {
            "pass": n_not_nan == 0,
            "non_nan_count": n_not_nan,
        }
    else:
        report["checks"]["latency_modeled_nan"] = {"pass": True, "note": "column absent"}

    # 15. AI rows have prediction columns
    ai = df[df["strategy"] == "ai_adaptive"]
    if not ai.empty:
        pred_cols = [
            "predicted_OTFS_BER", "predicted_ODDM_BER",
            "predicted_OTFS_ACS", "predicted_ODDM_ACS",
        ]
        pred_details = {}
        all_ok = True
        for pc in pred_cols:
            if pc in ai.columns:
                n_valid = int(ai[pc].notna().sum())
                pred_details[pc] = {"non_null": n_valid, "total_ai_rows": len(ai)}
            else:
                pred_details[pc] = {"error": "column absent"}
                all_ok = False
        report["checks"]["ai_prediction_columns"] = {
            "pass": all_ok,
            "details": pred_details,
        }
    else:
        report["checks"]["ai_prediction_columns"] = {
            "pass": False, "error": "no ai_adaptive rows found"
        }

    # 16. Oracle comparison fields present
    if not ai.empty:
        oracle_cols = ["oracle_waveform", "oracle_BER", "oracle_ACS", "decision_correct"]
        oracle_details = {}
        all_ok = True
        for oc in oracle_cols:
            if oc in ai.columns:
                n_valid = int(ai[oc].notna().sum())
                oracle_details[oc] = {"non_null": n_valid, "total_ai_rows": len(ai)}
            else:
                oracle_details[oc] = {"error": "column absent"}
                all_ok = False
        report["checks"]["oracle_comparison_fields"] = {
            "pass": all_ok,
            "details": oracle_details,
        }
    else:
        report["checks"]["oracle_comparison_fields"] = {
            "pass": False, "error": "no ai_adaptive rows found"
        }

    # Overall pass/fail
    all_pass = all(
        chk.get("pass", False) for chk in report["checks"].values()
    )
    report["overall_pass"] = all_pass

    return report


# ---------------------------------------------------------------------------
# Metadata
# ---------------------------------------------------------------------------
def build_metadata(df, load_report, quality_report):
    """Build final_dataset_metadata.json content."""
    meta = {
        "phase": 6,
        "description": "Final consolidated dataset from MATLAB Digital Twin traces",
        "generator": "phase6_final_dataset.py",
        "total_rows": int(len(df)),
        "total_columns": int(len(df.columns)),
        "columns": list(df.columns),
        "scenarios": sorted(df["scenario_id"].unique().tolist())
        if "scenario_id" in df.columns else [],
        "strategies": sorted(df["strategy"].unique().tolist())
        if "strategy" in df.columns else [],
        "environments": sorted(df["environment"].unique().tolist())
        if "environment" in df.columns else [],
        "modulations": sorted(df["modulation_label"].unique().tolist())
        if "modulation_label" in df.columns else [],
        "channel_profiles": sorted(df["channel_profile"].unique().tolist())
        if "channel_profile" in df.columns else [],
        "waveforms_used": sorted(df["waveform"].dropna().unique().tolist())
        if "waveform" in df.columns else [],
        "load_report_summary": {
            "total_attempts": len(load_report),
            "successful": sum(1 for _, _, s in load_report if s.startswith("ok")),
            "missing": sum(1 for _, _, s in load_report if s == "file_not_found"),
            "empty": sum(1 for _, _, s in load_report if s == "empty_csv"),
            "errors": sum(
                1 for _, _, s in load_report
                if "error" in s.lower() or "parse_error" in s.lower()
            ),
        },
        "data_quality_overall_pass": quality_report.get("overall_pass", False),
        "snr_range": [
            float(df["snr_db"].min()) if "snr_db" in df.columns else None,
            float(df["snr_db"].max()) if "snr_db" in df.columns else None,
        ],
        "speed_range_kmph": [
            float(df["speed_kmph"].min()) if "speed_kmph" in df.columns else None,
            float(df["speed_kmph"].max()) if "speed_kmph" in df.columns else None,
        ],
        "frames_per_scenario": (
            df.groupby("scenario_id")["frame"].nunique().to_dict()
            if all(c in df.columns for c in ["scenario_id", "frame"])
            else {}
        ),
        "policy_version": (
            df["policy_version"].mode().iloc[0]
            if "policy_version" in df.columns and not df["policy_version"].mode().empty
            else "unknown"
        ),
    }
    return meta


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Phase 6: Consolidate Digital Twin traces into final dataset"
    )
    parser.add_argument(
        "--dt-root",
        default=None,
        help="Path to DigitalTwin root directory",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Path to output directory",
    )
    args = parser.parse_args()

    dt_root = args.dt_root or DEFAULT_DT_ROOT
    output_dir = args.output_dir or OUTPUT_DIR

    t0 = time.time()

    print("=" * 70)
    print("  PHASE 6: FINAL DATASET CONSOLIDATION")
    print("=" * 70)
    print(f"  DigitalTwin root : {dt_root}")
    print(f"  Output directory : {output_dir}")
    print()

    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)

    # ------------------------------------------------------------------
    # Step 1: Load all traces
    # ------------------------------------------------------------------
    print("[1/13] Loading trace CSVs and manifests...")
    all_traces, manifest_info, load_report = load_all_traces(dt_root)

    n_loaded = sum(1 for _, _, s in load_report if s.startswith("ok"))
    n_missing = sum(1 for _, _, s in load_report if s == "file_not_found")
    print(f"  Loaded {n_loaded} traces, {n_missing} files not found")
    for sc in sorted(manifest_info.keys()):
        ms = manifest_info[sc].get("master_seed", "N/A")
        pv = manifest_info[sc].get("policy_version", "N/A")
        print(f"  Scenario {sc.upper()}: master_seed={ms}, policy={pv}")

    if not all_traces:
        print("  ERROR: No traces loaded. Exiting.")
        sys.exit(1)

    # ------------------------------------------------------------------
    # Step 2: Concatenate all traces
    # ------------------------------------------------------------------
    print("[2/13] Concatenating traces...")
    df = pd.concat(all_traces, ignore_index=True)
    print(f"  Total rows: {len(df)}, columns: {len(df.columns)}")

    # ------------------------------------------------------------------
    # Step 3: Derive columns and rename
    # ------------------------------------------------------------------
    print("[3/13] Deriving columns and renaming...")
    df = derive_and_rename(df, manifest_info)
    print(f"  Columns after derivation: {len(df.columns)}")
    print(f"  Added: master_seed, policy_version, experiment_id, modulation_label")

    # ------------------------------------------------------------------
    # Step 4: Write final_dataset.csv
    # ------------------------------------------------------------------
    print("[4/13] Writing final_dataset.csv...")
    final_csv_path = os.path.join(output_dir, "final_dataset.csv")
    df.to_csv(final_csv_path, index=False, encoding="utf-8")
    print(f"  Written: {final_csv_path} ({len(df)} rows)")

    # ------------------------------------------------------------------
    # Step 5: Summary files
    # ------------------------------------------------------------------
    print("[5/13] Creating environment_summary.csv...")
    env_sum = build_environment_summary(df)
    env_sum.to_csv(os.path.join(output_dir, "environment_summary.csv"), index=False, encoding="utf-8")

    print("[6/13] Creating scenario_summary.csv...")
    sc_sum = build_scenario_summary(df)
    sc_sum.to_csv(os.path.join(output_dir, "scenario_summary.csv"), index=False, encoding="utf-8")

    print("[7/13] Creating snr_summary.csv...")
    snr_sum = build_snr_summary(df)
    snr_sum.to_csv(os.path.join(output_dir, "snr_summary.csv"), index=False, encoding="utf-8")

    print("  Creating mobility_summary.csv...")
    mob_sum = build_mobility_summary(df)
    mob_sum.to_csv(os.path.join(output_dir, "mobility_summary.csv"), index=False, encoding="utf-8")

    print("  Creating channel_summary.csv...")
    ch_sum = build_channel_summary(df)
    ch_sum.to_csv(os.path.join(output_dir, "channel_summary.csv"), index=False, encoding="utf-8")

    print("  Creating modulation_summary.csv...")
    mod_sum = build_modulation_summary(df)
    mod_sum.to_csv(os.path.join(output_dir, "modulation_summary.csv"), index=False, encoding="utf-8")

    # ------------------------------------------------------------------
    # Step 8: predicted_vs_actual.csv
    # ------------------------------------------------------------------
    print("[8/13] Creating predicted_vs_actual.csv...")
    pva = build_predicted_vs_actual(df)
    pva.to_csv(os.path.join(output_dir, "predicted_vs_actual.csv"), index=False, encoding="utf-8")
    print(f"  Rows: {len(pva)}")

    # ------------------------------------------------------------------
    # Step 9: oracle_comparison.csv
    # ------------------------------------------------------------------
    print("[9/13] Creating oracle_comparison.csv...")
    oc = build_oracle_comparison(df)
    oc.to_csv(os.path.join(output_dir, "oracle_comparison.csv"), index=False, encoding="utf-8")
    print(f"  Rows: {len(oc)}")

    # ------------------------------------------------------------------
    # Step 10: fixed_vs_adaptive.csv
    # ------------------------------------------------------------------
    print("[10/13] Creating fixed_vs_adaptive.csv...")
    fva = build_fixed_vs_adaptive(df)
    fva.to_csv(os.path.join(output_dir, "fixed_vs_adaptive.csv"), index=False, encoding="utf-8")
    print(f"  Rows: {len(fva)} (one per strategy)")

    # ------------------------------------------------------------------
    # Step 11: switching_analysis.csv
    # ------------------------------------------------------------------
    print("[11/13] Creating switching_analysis.csv...")
    swa = build_switching_analysis(df)
    swa.to_csv(os.path.join(output_dir, "switching_analysis.csv"), index=False, encoding="utf-8")
    print(f"  Rows: {len(swa)} (total + per-environment)")

    # ------------------------------------------------------------------
    # Step 12: Data quality checks
    # ------------------------------------------------------------------
    print("[12/13] Running data quality checks...")
    quality_report = run_data_quality_checks(df)
    quality_path = os.path.join(output_dir, "data_quality_report.json")
    with open(quality_path, "w", encoding="utf-8") as fh:
        json.dump(quality_report, fh, indent=2, default=str)
    print(f"  Overall pass: {quality_report['overall_pass']}")
    for check_name, check_result in quality_report["checks"].items():
        status = "PASS" if check_result.get("pass", False) else "FAIL"
        extra = ""
        if not check_result.get("pass", False):
            if "error" in check_result:
                extra = f" ({check_result['error']})"
            elif "violation_count" in check_result:
                extra = f" (violations: {check_result['violation_count']})"
            elif "duplicate_count" in check_result and check_result["duplicate_count"] > 0:
                extra = f" (duplicates: {check_result['duplicate_count']})"
            elif "out_of_range_count" in check_result and check_result["out_of_range_count"] > 0:
                extra = f" (out of range: {check_result['out_of_range_count']})"
        print(f"    [{status}] {check_name}{extra}")

    # ------------------------------------------------------------------
    # Step 13: Metadata
    # ------------------------------------------------------------------
    print("[13/13] Writing final_dataset_metadata.json...")
    metadata = build_metadata(df, load_report, quality_report)
    meta_path = os.path.join(output_dir, "final_dataset_metadata.json")
    with open(meta_path, "w", encoding="utf-8") as fh:
        json.dump(metadata, fh, indent=2, default=str)
    print(f"  Written: {meta_path}")

    # ------------------------------------------------------------------
    # Print summary statistics to stdout
    # ------------------------------------------------------------------
    elapsed = time.time() - t0
    print()
    print("=" * 70)
    print("  SUMMARY STATISTICS")
    print("=" * 70)

    print(f"\n  Dataset shape: {len(df)} rows x {len(df.columns)} columns")
    print(f"  Scenarios: {metadata['scenarios']}")
    print(f"  Strategies: {metadata['strategies']}")
    print(f"  Environments: {metadata['environments']}")
    print(f"  Modulations: {metadata['modulations']}")
    print(f"  Channel profiles: {metadata['channel_profiles']}")
    print(f"  Waveforms used: {metadata['waveforms_used']}")
    print(f"  Policy version: {metadata['policy_version']}")

    # Per-strategy metrics
    print("\n  Per-strategy aggregate metrics:")
    print(f"  {'Strategy':<16} {'Mean BER':>10} {'Mean TP (bps)':>16} {'Mean CQI':>10} {'Mean ACS':>10} {'Rows':>8}")
    print("  " + "-" * 72)
    for _, row in fva.iterrows():
        ber_str = f"{row['mean_BER']:.6f}" if pd.notna(row.get("mean_BER")) else "N/A"
        tp_str = f"{row['mean_throughput']:.0f}" if pd.notna(row.get("mean_throughput")) else "N/A"
        cqi_str = f"{row['mean_CQI']:.2f}" if pd.notna(row.get("mean_CQI")) else "N/A"
        acs_str = f"{row['mean_ACS']:.4f}" if pd.notna(row.get("mean_ACS")) else "N/A"
        strat_count = len(df[df["strategy"] == row["strategy"]])
        print(f"  {row['strategy']:<16} {ber_str:>10} {tp_str:>16} {cqi_str:>10} {acs_str:>10} {strat_count:>8}")

    # AI adaptive specifics
    ai_df = df[df["strategy"] == "ai_adaptive"]
    if not ai_df.empty and "decision_correct" in ai_df.columns:
        dc = ai_df["decision_correct"].dropna()
        print(f"\n  AI Adaptive Details:")
        print(f"    Oracle agreement: {dc.mean():.4f} ({int(dc.sum())}/{len(dc)})")
        if "switched" in ai_df.columns:
            n_sw = int(ai_df["switched"].sum())
            print(f"    Total switches: {n_sw} ({n_sw/len(ai_df)*100:.1f}% switch rate)")
        if "ACS_regret" in ai_df.columns:
            reg = ai_df["ACS_regret"].dropna()
            print(f"    Mean ACS regret: {reg.mean():.6f}")
            print(f"    P90 ACS regret: {_percentile_safe(reg, 90):.6f}")
        if "BER_regret" in ai_df.columns:
            br = ai_df["BER_regret"].dropna()
            print(f"    Mean BER regret: {br.mean():.6f}")

    # Waveform distribution
    if "waveform" in df.columns:
        print(f"\n  Waveform distribution:")
        wf_counts = df["waveform"].value_counts()
        for wf, cnt in wf_counts.items():
            print(f"    {wf}: {cnt} ({cnt/len(df)*100:.1f}%)")

    # Environment distribution
    if "environment" in df.columns:
        print(f"\n  Environment distribution:")
        env_counts = df["environment"].value_counts()
        for env, cnt in env_counts.items():
            print(f"    {env}: {cnt} ({cnt/len(df)*100:.1f}%)")

    # Load report summary
    print(f"\n  Load report:")
    print(f"    Successful loads: {metadata['load_report_summary']['successful']}")
    print(f"    Files not found: {metadata['load_report_summary']['missing']}")
    print(f"    Empty CSVs: {metadata['load_report_summary']['empty']}")
    print(f"    Errors: {metadata['load_report_summary']['errors']}")

    # Output files
    print(f"\n  Output files written to: {output_dir}")
    output_files = [
        "final_dataset.csv",
        "environment_summary.csv",
        "scenario_summary.csv",
        "snr_summary.csv",
        "mobility_summary.csv",
        "channel_summary.csv",
        "modulation_summary.csv",
        "predicted_vs_actual.csv",
        "oracle_comparison.csv",
        "fixed_vs_adaptive.csv",
        "switching_analysis.csv",
        "data_quality_report.json",
        "final_dataset_metadata.json",
    ]
    for fname in output_files:
        fpath = os.path.join(output_dir, fname)
        exists = os.path.isfile(fpath)
        size = os.path.getsize(fpath) if exists else 0
        print(f"    {fname:<42} {'OK' if exists else 'MISSING':<8} ({size:,} bytes)")

    print(f"\n  Runtime: {elapsed:.2f} seconds")
    print("=" * 70)
    print("  PHASE 6 COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    main()
