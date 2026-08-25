"""
dataset_report.py
==================
"AI Training" steps 2-4 from the project spec, factored out of
train_model.py so that file doesn't balloon:

  2. Dataset analysis    -> printed to stdout
  3. dataset_report.txt  -> AI_Results/Reports/dataset_report.txt
  4. Dataset visualisation:
        Correlation Matrix, BER Distribution, SNR Distribution,
        Environment Distribution, Detector Distribution,
        Delay Profile Distribution
     -> AI_Results/Graphs/01_dataset_*.png

Called from train_model.py as:
    from dataset_report import analyze_and_report
    analyze_and_report(df)
"""

import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from config import DATASET_REPORT_FILE, GRAPHS_DIR, ALL_COLUMNS

NUMERIC_HINT_COLS = [
    "Speed_kmh", "DelaySpread", "NumPaths", "DopplerSpread", "SNR_dB",
    "BER", "SER", "PER", "EVM_percent", "SINR_est_dB", "CQI",
    "Throughput_bps", "SpectralEfficiency_bps_per_Hz", "Runtime_sec",
    "AvgIterations",
]


def _savefig(fig, filename):
    path = os.path.join(GRAPHS_DIR, filename)
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return path


def analyze_dataset(df: pd.DataFrame) -> dict:
    """Step 2: dataset analysis. Returns a dict of everything printed +
    written to the report, so callers (train_model.py) can reuse the
    numbers without re-deriving them."""
    info = {
        "rows": len(df),
        "columns": len(df.columns),
        "missing_values": int(df.isna().sum().sum()),
        "missing_by_column": {c: int(n) for c, n in df.isna().sum().items() if n > 0},
        "duplicate_rows": int(df.duplicated().sum()),
        "unique_environments": sorted(df["Environment"].dropna().unique().tolist()) if "Environment" in df else [],
        "unique_modulations": sorted(df["Modulation"].dropna().unique().tolist()) if "Modulation" in df else [],
        "unique_detectors": sorted(df["Detector"].dropna().unique().tolist()) if "Detector" in df else [],
        "unique_delay_profiles": sorted(df["DelayProfile"].dropna().unique().tolist()) if "DelayProfile" in df else [],
        "missing_expected_columns": [c for c in ALL_COLUMNS if c not in df.columns],
    }

    print("\n=== Dataset Analysis ===")
    print(f"  Rows                 : {info['rows']}")
    print(f"  Columns              : {info['columns']}")
    print(f"  Missing values       : {info['missing_values']}")
    print(f"  Duplicate rows       : {info['duplicate_rows']}")
    print(f"  Unique Environments  : {len(info['unique_environments'])}  {info['unique_environments']}")
    print(f"  Unique Modulations   : {len(info['unique_modulations'])}  {info['unique_modulations']}")
    print(f"  Unique Detectors     : {len(info['unique_detectors'])}  {info['unique_detectors']}")
    print(f"  Unique DelayProfiles : {len(info['unique_delay_profiles'])}  {info['unique_delay_profiles']}")
    if info["missing_expected_columns"]:
        print(f"  WARNING: expected columns not found: {info['missing_expected_columns']}")

    return info


def write_report(info: dict, df: pd.DataFrame, path: str = DATASET_REPORT_FILE):
    """Step 3: dataset_report.txt"""
    lines = []
    lines.append("OTFS AI PIPELINE -- DATASET REPORT")
    lines.append("=" * 60)
    lines.append(f"Generated: {pd.Timestamp.now()}")
    lines.append("")
    lines.append(f"Rows                : {info['rows']}")
    lines.append(f"Columns             : {info['columns']}")
    lines.append(f"Missing values      : {info['missing_values']}")
    if info["missing_by_column"]:
        lines.append(f"  by column         : {info['missing_by_column']}")
    lines.append(f"Duplicate rows      : {info['duplicate_rows']}")
    lines.append("")
    lines.append(f"Unique Environments ({len(info['unique_environments'])}): {info['unique_environments']}")
    lines.append(f"Unique Modulations  ({len(info['unique_modulations'])}): {info['unique_modulations']}")
    lines.append(f"Unique Detectors    ({len(info['unique_detectors'])}): {info['unique_detectors']}")
    lines.append(f"Unique DelayProfiles({len(info['unique_delay_profiles'])}): {info['unique_delay_profiles']}")
    if info["missing_expected_columns"]:
        lines.append("")
        lines.append(f"WARNING -- expected schema columns missing: {info['missing_expected_columns']}")
    lines.append("")
    lines.append("-" * 60)
    lines.append("Per-numeric-column summary (mean / std / min / max)")
    lines.append("-" * 60)
    num_cols = [c for c in NUMERIC_HINT_COLS if c in df.columns]
    if num_cols:
        desc = df[num_cols].describe().T[["mean", "std", "min", "max"]]
        lines.append(desc.to_string(float_format=lambda v: f"{v:.6g}"))

    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"Dataset report written -> {path}")


def generate_distribution_graphs(df: pd.DataFrame) -> list:
    """Step 4: Correlation Matrix, BER/SNR distributions, Environment /
    Detector / DelayProfile distributions. Returns list of saved file paths."""
    saved = []
    num_cols = [c for c in NUMERIC_HINT_COLS if c in df.columns]

    # --- Correlation matrix ---
    if len(num_cols) >= 2:
        corr = df[num_cols].corr(numeric_only=True)
        fig, ax = plt.subplots(figsize=(9, 8))
        im = ax.imshow(corr.values, cmap="coolwarm", vmin=-1, vmax=1)
        ax.set_xticks(range(len(num_cols))); ax.set_xticklabels(num_cols, rotation=60, ha="right")
        ax.set_yticks(range(len(num_cols))); ax.set_yticklabels(num_cols)
        for i in range(len(num_cols)):
            for j in range(len(num_cols)):
                ax.text(j, i, f"{corr.values[i, j]:.2f}", ha="center", va="center", fontsize=6)
        fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
        ax.set_title("Dataset Correlation Matrix")
        saved.append(_savefig(fig, "01_dataset_correlation_matrix.png"))

    # --- BER distribution (log scale) ---
    if "BER" in df.columns:
        fig, ax = plt.subplots(figsize=(7, 5))
        vals = np.clip(df["BER"].astype(float).values, 1e-8, None)
        ax.hist(np.log10(vals), bins=40, color="#4C72B0", edgecolor="black", alpha=0.8)
        ax.set_xlabel("log10(BER)"); ax.set_ylabel("Count")
        ax.set_title("BER Distribution")
        ax.grid(True, alpha=0.3)
        saved.append(_savefig(fig, "02_dataset_ber_distribution.png"))

    # --- SNR distribution ---
    if "SNR_dB" in df.columns:
        fig, ax = plt.subplots(figsize=(7, 5))
        ax.hist(df["SNR_dB"].astype(float).values, bins=30, color="#55A868", edgecolor="black", alpha=0.8)
        ax.set_xlabel("SNR (dB)"); ax.set_ylabel("Count")
        ax.set_title("SNR Distribution")
        ax.grid(True, alpha=0.3)
        saved.append(_savefig(fig, "03_dataset_snr_distribution.png"))

    # --- Environment / Detector / DelayProfile distributions ---
    for col, fname, title, color in [
        ("Environment", "04_dataset_environment_distribution.png", "Environment Distribution", "#C44E52"),
        ("Detector", "05_dataset_detector_distribution.png", "Detector Distribution", "#8172B2"),
        ("DelayProfile", "06_dataset_delayprofile_distribution.png", "Delay Profile Distribution", "#CCB974"),
    ]:
        if col not in df.columns:
            continue
        counts = df[col].value_counts()
        fig, ax = plt.subplots(figsize=(7, 5))
        ax.bar(counts.index.astype(str), counts.values, color=color, edgecolor="black", alpha=0.85)
        ax.set_xlabel(col); ax.set_ylabel("Count")
        ax.set_title(title)
        ax.tick_params(axis="x", rotation=30)
        ax.grid(True, alpha=0.3, axis="y")
        saved.append(_savefig(fig, fname))

    print(f"Dataset visualisation graphs saved ({len(saved)}) -> {GRAPHS_DIR}/")
    return saved


def analyze_and_report(df: pd.DataFrame) -> dict:
    """Convenience wrapper doing steps 2-4 in one call."""
    info = analyze_dataset(df)
    write_report(info, df)
    graph_paths = generate_distribution_graphs(df)
    info["graph_paths"] = graph_paths
    return info
