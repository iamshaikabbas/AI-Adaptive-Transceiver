"""
phase7_visualizations.py
=========================
Phase 7: Generate ~33 communication-system visualizations from Phase 6 dataset.

Reads:  Results/FinalEvaluation/final_dataset.csv
        Results/FinalEvaluation/*.csv summary files
Writes: Results/FinalEvaluation/Visualizations/<category>/<graph>.png
        Results/FinalEvaluation/Visualizations/graph_index.json

Usage:
    python phase7_visualizations.py
    python phase7_visualizations.py --dataset <path> --output <path>
"""

import argparse
import hashlib
import json
import math
import os
import sys
import time
from collections import OrderedDict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

DEFAULT_DS = os.path.normpath(os.path.join(
    SCRIPT_DIR, os.pardir,
    "Results", "FinalEvaluation", "final_dataset.csv"))
DEFAULT_OUT = os.path.normpath(os.path.join(
    SCRIPT_DIR, os.pardir,
    "Results", "FinalEvaluation", "Visualizations"))

STRATEGY_ORDER = ["fixed_otfs", "fixed_oddm", "ai_adaptive", "oracle"]
STRATEGY_LABELS = {
    "fixed_otfs": "Fixed OTFS",
    "fixed_oddm": "Fixed ODDM",
    "ai_adaptive": "AI Adaptive",
    "oracle": "Oracle",
}
STRATEGY_COLORS = {
    "fixed_otfs": "#2196F3",
    "fixed_oddm": "#FF9800",
    "ai_adaptive": "#4CAF50",
    "oracle": "#9C27B0",
}
WAVEFORM_COLORS = {"OTFS": "#2196F3", "ODDM": "#FF9800"}
CHANNEL_COLORS = {"EPA": "#4CAF50", "EVA": "#FF9800", "ETU": "#F44336"}
MOD_ORDER = ["QPSK", "16QAM", "64QAM"]
MOD_COLORS = {"QPSK": "#4CAF50", "16QAM": "#2196F3", "64QAM": "#F44336"}
ENV_ORDER = ["Pedestrian", "Urban", "UrbanFast", "Highway", "HighSpeedRail"]
ENV_COLORS = {
    "Pedestrian": "#4CAF50", "Urban": "#2196F3", "UrbanFast": "#FF9800",
    "Highway": "#FF5722", "HighSpeedRail": "#9C27B0",
}

FONT_TITLE = 14
FONT_LABEL = 12
FONT_TICK = 10
FONT_LEGEND = 10
FIG_DPI = 150
FIG_WIDTH = 10
FIG_HEIGHT = 6

graph_index = []


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _save(fig, path, graph_id, title, source, category, desc="", interp=""):
    fig.tight_layout()
    fig.savefig(path, dpi=FIG_DPI, bbox_inches="tight")
    plt.close(fig)
    fname = os.path.basename(path)
    graph_index.append({
        "graph_id": graph_id,
        "title": title,
        "filename": fname,
        "category": category,
        "data_source": source,
        "description": desc,
        "interpretation": interp,
    })
    print(f"  [{graph_id:02d}] {fname}")


def _bar(ax, labels, values, colors, ylabel, title, fmt="{:.3f}"):
    bars = ax.bar(labels, values, color=colors, edgecolor="white", linewidth=0.5)
    for bar, val in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.003,
                fmt.format(val), ha="center", va="bottom", fontsize=FONT_TICK)
    ax.set_ylabel(ylabel, fontsize=FONT_LABEL)
    ax.set_title(title, fontsize=FONT_TITLE, fontweight="bold")
    ax.tick_params(axis="x", labelsize=FONT_TICK)
    ax.tick_params(axis="y", labelsize=FONT_TICK)
    ax.grid(axis="y", alpha=0.3)


def _line_grouped(ax, groups, x_vals, series_map, xlabel, ylabel, title,
                   logx=False, fmt="{:.2f}"):
    for label, color in series_map.items():
        vals = groups.get(label, {})
        ys = [vals.get(x, np.nan) for x in x_vals]
        ax.plot(x_vals, ys, "-o", label=label, color=color, markersize=4,
                linewidth=2)
    ax.set_xlabel(xlabel, fontsize=FONT_LABEL)
    ax.set_ylabel(ylabel, fontsize=FONT_LABEL)
    ax.set_title(title, fontsize=FONT_TITLE, fontweight="bold")
    ax.legend(fontsize=FONT_LEGEND)
    ax.grid(alpha=0.3)
    ax.tick_params(labelsize=FONT_TICK)
    if logx:
        ax.set_xscale("log")


def _metric_bar(ax, df, metric, strategies, title, ylabel, fmt="{:.3f}"):
    means = [df[df.strategy == s][metric].mean() for s in strategies]
    labels = [STRATEGY_LABELS[s] for s in strategies]
    colors = [STRATEGY_COLORS[s] for s in strategies]
    _bar(ax, labels, means, colors, ylabel, title, fmt)


def _round_col(series, base):
    return (series / base).round() * base


# ---------------------------------------------------------------------------
# CATEGORY 1: SYSTEM OVERVIEW
# ---------------------------------------------------------------------------
def graph_01(df, out):
    fig, ax = plt.subplots(figsize=(FIG_WIDTH, FIG_HEIGHT))
    _metric_bar(ax, df, "ACS", STRATEGY_ORDER,
                "Overall Adaptive Channel Score (ACS) by Strategy", "Mean ACS")
    _save(fig, os.path.join(out, "01_overall_acs.png"), 1,
          "Overall ACS by Strategy", "final_dataset.csv",
          "01_system_overview",
          "Mean ACS across all scenarios and frames for each strategy.",
          "Oracle achieves highest ACS (0.444). AI Adaptive (0.434) closely "
          "matches Fixed OTFS (0.435) and exceeds Fixed ODDM (0.390).")


def graph_02(df, out):
    fig, ax = plt.subplots(figsize=(FIG_WIDTH, FIG_HEIGHT))
    _metric_bar(ax, df, "BER", STRATEGY_ORDER,
                "Overall Bit Error Rate (BER) by Strategy", "Mean BER",
                "{:.4f}")
    _save(fig, os.path.join(out, "01_overall_ber.png"), 2,
          "Overall BER by Strategy", "final_dataset.csv",
          "01_system_overview",
          "Mean BER across all scenarios and frames for each strategy.",
          "Oracle (0.063) < Fixed OTFS (0.064) ≈ AI Adaptive (0.065) < "
          "Fixed ODDM (0.084). AI Adaptive BER close to best fixed strategy.")


def graph_03(df, out):
    fig, ax = plt.subplots(figsize=(FIG_WIDTH, FIG_HEIGHT))
    means = [df[df.strategy == s]["throughput_bps"].mean() / 1000 for s in STRATEGY_ORDER]
    labels = [STRATEGY_LABELS[s] for s in STRATEGY_ORDER]
    colors = [STRATEGY_COLORS[s] for s in STRATEGY_ORDER]
    _bar(ax, labels, means, colors, "Mean Throughput (kbps)",
         "Overall Throughput by Strategy", "{:.0f}")
    _save(fig, os.path.join(out, "01_overall_throughput.png"), 3,
          "Overall Throughput by Strategy", "final_dataset.csv",
          "01_system_overview",
          "Mean throughput in kbps across all scenarios and frames.",
          "Oracle (272 kbps) > AI Adaptive (263 kbps) > Fixed OTFS "
          "(260 kbps) > Fixed ODDM (242 kbps).")


def graph_04(df, out):
    fig, ax = plt.subplots(figsize=(FIG_WIDTH, FIG_HEIGHT))
    _metric_bar(ax, df, "CQI", STRATEGY_ORDER,
                "Overall Channel Quality Index (CQI) by Strategy", "Mean CQI",
                "{:.2f}")
    _save(fig, os.path.join(out, "01_overall_cqi.png"), 4,
          "Overall CQI by Strategy", "final_dataset.csv",
          "01_system_overview",
          "Mean CQI across all scenarios and frames.",
          "All strategies show similar CQI (10-10.3), indicating the "
          "channel quality is a property of the scenario, not the strategy.")


def graph_05(df, out):
    fig, ax = plt.subplots(figsize=(FIG_WIDTH, FIG_HEIGHT))
    _metric_bar(ax, df, "spectral_efficiency", STRATEGY_ORDER,
                "Overall Spectral Efficiency by Strategy",
                "Mean Spectral Efficiency (bps/Hz)", "{:.2f}")
    _save(fig, os.path.join(out, "01_overall_se.png"), 5,
          "Overall Spectral Efficiency by Strategy", "final_dataset.csv",
          "01_system_overview",
          "Mean spectral efficiency for each strategy.",
          "Oracle leads; AI Adaptive and Fixed OTFS comparable; "
          "Fixed ODDM lower.")


def graph_06(df, out):
    fig, ax = plt.subplots(figsize=(FIG_WIDTH, FIG_HEIGHT))
    means = [df[df.strategy == s]["detector_time_ms"].mean() for s in STRATEGY_ORDER]
    labels = [STRATEGY_LABELS[s] for s in STRATEGY_ORDER]
    colors = [STRATEGY_COLORS[s] for s in STRATEGY_ORDER]
    _bar(ax, labels, means, colors, "Mean Detector Time (ms)",
         "Detector Execution Time by Strategy", "{:.1f}")
    ax.set_ylabel("Mean Detector Execution Time (ms)", fontsize=FONT_LABEL)
    _save(fig, os.path.join(out, "01_overall_detector_time.png"), 6,
          "Detector Execution Time by Strategy", "final_dataset.csv",
          "01_system_overview",
          "Mean wall-clock detector computation time (not communication "
          "latency). Oracle runs both detectors.",
          "Oracle ~2x single-detector time. AI Adaptive and Fixed strategies "
          "similar detector times (~single waveform detector).")


# ---------------------------------------------------------------------------
# CATEGORY 2: WAVEFORM COMPARISON
# ---------------------------------------------------------------------------
def graph_07(df, out):
    fig, ax = plt.subplots(figsize=(FIG_WIDTH, FIG_HEIGHT))
    otfs = df[df.waveform == "OTFS"]["BER"]
    oddm = df[df.waveform == "ODDM"]["BER"]
    bp = ax.boxplot([otfs.values, oddm.values],
                    tick_labels=["OTFS", "ODDM"], patch_artist=True,
                    widths=0.5, showfliers=True, flierprops=dict(marker=".", markersize=3))
    bp["boxes"][0].set_facecolor(WAVEFORM_COLORS["OTFS"])
    bp["boxes"][1].set_facecolor(WAVEFORM_COLORS["ODDM"])
    ax.set_ylabel("BER", fontsize=FONT_LABEL)
    ax.set_title("OTFS vs ODDM: BER Distribution", fontsize=FONT_TITLE,
                 fontweight="bold")
    ax.grid(axis="y", alpha=0.3)
    _save(fig, os.path.join(out, "02_wf_ber_boxplot.png"), 7,
          "OTFS vs ODDM BER Distribution", "final_dataset.csv",
          "02_waveform_comparison",
          "Boxplot of BER values for OTFS vs ODDM waveform selections.",
          "OTFS shows lower median BER and tighter distribution than ODDM.")


def graph_08(df, out):
    fig, ax = plt.subplots(figsize=(FIG_WIDTH, FIG_HEIGHT))
    otfs = df[df.waveform == "OTFS"]["throughput_bps"] / 1000
    oddm = df[df.waveform == "ODDM"]["throughput_bps"] / 1000
    bp = ax.boxplot([otfs.values, oddm.values],
                    tick_labels=["OTFS", "ODDM"], patch_artist=True,
                    widths=0.5, showfliers=True, flierprops=dict(marker=".", markersize=3))
    bp["boxes"][0].set_facecolor(WAVEFORM_COLORS["OTFS"])
    bp["boxes"][1].set_facecolor(WAVEFORM_COLORS["ODDM"])
    ax.set_ylabel("Throughput (kbps)", fontsize=FONT_LABEL)
    ax.set_title("OTFS vs ODDM: Throughput Distribution", fontsize=FONT_TITLE,
                 fontweight="bold")
    ax.grid(axis="y", alpha=0.3)
    _save(fig, os.path.join(out, "02_wf_throughput_boxplot.png"), 8,
          "OTFS vs ODDM Throughput Distribution", "final_dataset.csv",
          "02_waveform_comparison",
          "Boxplot of throughput for OTFS vs ODDM selections.",
          "OTFS median throughput higher than ODDM across all frames.")


def graph_09(df, out):
    fig, ax = plt.subplots(figsize=(FIG_WIDTH, FIG_HEIGHT))
    otfs = df[df.waveform == "OTFS"]["ACS"]
    oddm = df[df.waveform == "ODDM"]["ACS"]
    bp = ax.boxplot([otfs.values, oddm.values],
                    tick_labels=["OTFS", "ODDM"], patch_artist=True,
                    widths=0.5, showfliers=True, flierprops=dict(marker=".", markersize=3))
    bp["boxes"][0].set_facecolor(WAVEFORM_COLORS["OTFS"])
    bp["boxes"][1].set_facecolor(WAVEFORM_COLORS["ODDM"])
    ax.set_ylabel("ACS", fontsize=FONT_LABEL)
    ax.set_title("OTFS vs ODDM: ACS Distribution", fontsize=FONT_TITLE,
                 fontweight="bold")
    ax.grid(axis="y", alpha=0.3)
    _save(fig, os.path.join(out, "02_wf_acs_boxplot.png"), 9,
          "OTFS vs ODDM ACS Distribution", "final_dataset.csv",
          "02_waveform_comparison",
          "Boxplot of ACS for OTFS vs ODDM selections.",
          "OTFS achieves higher median ACS than ODDM.")


def graph_10(df, out):
    fig, ax = plt.subplots(figsize=(FIG_WIDTH, FIG_HEIGHT))
    otfs = df[df.waveform == "OTFS"]["CQI"]
    oddm = df[df.waveform == "ODDM"]["CQI"]
    bp = ax.boxplot([otfs.values, oddm.values],
                    tick_labels=["OTFS", "ODDM"], patch_artist=True,
                    widths=0.5, showfliers=True, flierprops=dict(marker=".", markersize=3))
    bp["boxes"][0].set_facecolor(WAVEFORM_COLORS["OTFS"])
    bp["boxes"][1].set_facecolor(WAVEFORM_COLORS["ODDM"])
    ax.set_ylabel("CQI", fontsize=FONT_LABEL)
    ax.set_title("OTFS vs ODDM: CQI Distribution", fontsize=FONT_TITLE,
                 fontweight="bold")
    ax.grid(axis="y", alpha=0.3)
    _save(fig, os.path.join(out, "02_wf_cqi_boxplot.png"), 10,
          "OTFS vs ODDM CQI Distribution", "final_dataset.csv",
          "02_waveform_comparison",
          "Boxplot of CQI for OTFS vs ODDM selections.",
          "CQI distributions similar since CQI depends on channel, not waveform.")


def graph_11(df, out):
    ai = df[df.strategy == "ai_adaptive"]
    wf_counts = ai.waveform.value_counts()
    fig, ax = plt.subplots(figsize=(7, 7))
    labels = [f"{w}\n({c} frames)" for w, c in wf_counts.items()]
    colors = [WAVEFORM_COLORS.get(w, "#999") for w in wf_counts.index]
    wedges, texts, autotexts = ax.pie(
        wf_counts.values, labels=labels, colors=colors,
        autopct="%1.1f%%", startangle=90, textprops={"fontsize": FONT_TICK})
    for t in autotexts:
        t.set_fontsize(FONT_LABEL)
        t.set_fontweight("bold")
    ax.set_title("AI Adaptive: Waveform Selection Distribution",
                 fontsize=FONT_TITLE, fontweight="bold")
    _save(fig, os.path.join(out, "02_wf_usage_pie.png"), 11,
          "Waveform Usage by AI Adaptive System", "final_dataset.csv",
          "02_waveform_comparison",
          "Distribution of OTFS vs ODDM selections by the AI adaptive system.",
          "AI selects OTFS ~70% and ODDM ~30% of frames. Distribution "
          "reflects the AI's learned policy, not a predetermined split.")


def graph_12(df, out):
    ai = df[df.strategy == "ai_adaptive"]
    mat = pd.crosstab(ai.waveform, ai.oracle_waveform)
    mat = mat.reindex(index=["OTFS", "ODDM"], columns=["OTFS", "ODDM"], fill_value=0)
    fig, ax = plt.subplots(figsize=(7, 6))
    im = ax.imshow(mat.values, cmap="YlGnBu", aspect="auto")
    for i in range(2):
        for j in range(2):
            ax.text(j, i, str(mat.values[i, j]), ha="center", va="center",
                    fontsize=18, fontweight="bold",
                    color="white" if mat.values[i, j] > mat.values.max() / 2 else "black")
    ax.set_xticks([0, 1])
    ax.set_xticklabels(["Oracle OTFS", "Oracle ODDM"], fontsize=FONT_TICK)
    ax.set_yticks([0, 1])
    ax.set_yticklabels(["AI OTFS", "AI ODDM"], fontsize=FONT_TICK)
    ax.set_xlabel("Oracle Recommendation", fontsize=FONT_LABEL)
    ax.set_ylabel("AI Selection", fontsize=FONT_LABEL)
    ax.set_title("AI Selection vs Oracle Recommendation (Confusion Matrix)",
                 fontsize=FONT_TITLE, fontweight="bold")
    plt.colorbar(im, ax=ax, label="Frame Count")
    _save(fig, os.path.join(out, "02_wf_confusion_matrix.png"), 12,
          "AI Selected Waveform vs Oracle Waveform", "final_dataset.csv",
          "02_waveform_comparison",
          "Confusion matrix of AI waveform selection vs oracle recommendation.",
          "Diagonal = agreement. High diagonal values indicate strong "
          "AI-oracle alignment.")


# ---------------------------------------------------------------------------
# CATEGORY 3: SNR ANALYSIS
# ---------------------------------------------------------------------------
def _build_snr_groups(df, metric):
    """Build {strategy: {snr_rounded: mean_metric}}."""
    df2 = df.copy()
    df2["snr_r"] = _round_col(df2["snr_db"], 1).astype(int)
    groups = {}
    for s in STRATEGY_ORDER:
        sub = df2[df2.strategy == s]
        groups[s] = sub.groupby("snr_r")[metric].mean().to_dict()
    return groups


def _snr_xvals(groups):
    all_vals = set()
    for s in groups.values():
        all_vals.update(s.keys())
    return sorted(all_vals)


def _label_groups(groups):
    """Remap {strategy_key: {x: y}} -> {strategy_label: {x: y}}."""
    return {STRATEGY_LABELS[k]: v for k, v in groups.items()}


def graph_13(df, out):
    fig, ax = plt.subplots(figsize=(FIG_WIDTH, FIG_HEIGHT))
    groups = _build_snr_groups(df, "BER")
    xvals = _snr_xvals(groups)
    _line_grouped(ax, _label_groups(groups), xvals,
                  {STRATEGY_LABELS[s]: STRATEGY_COLORS[s] for s in STRATEGY_ORDER},
                  "SNR (dB)", "Mean BER", "BER vs SNR by Strategy")
    ax.set_yscale("log")
    ax.set_ylim(bottom=1e-4)
    _save(fig, os.path.join(out, "03_ber_vs_snr.png"), 13,
          "BER vs SNR by Strategy", "final_dataset.csv",
          "03_snr_analysis",
          "Mean BER at each SNR level for all four strategies.",
          "BER decreases with SNR for all strategies. AI Adaptive tracks "
          "Fixed OTFS closely across SNR range.")


def graph_14(df, out):
    fig, ax = plt.subplots(figsize=(FIG_WIDTH, FIG_HEIGHT))
    df2 = df.copy()
    df2["snr_r"] = _round_col(df2["snr_db"], 1).astype(int)
    groups = {}
    for s in STRATEGY_ORDER:
        sub = df2[df2.strategy == s]
        groups[s] = (sub.groupby("snr_r")["throughput_bps"].mean() / 1000).to_dict()
    xvals = sorted(set().union(*[g.keys() for g in groups.values()]))
    _line_grouped(ax, _label_groups(groups), xvals,
                  {STRATEGY_LABELS[s]: STRATEGY_COLORS[s] for s in STRATEGY_ORDER},
                  "SNR (dB)", "Mean Throughput (kbps)", "Throughput vs SNR by Strategy")
    _save(fig, os.path.join(out, "03_tp_vs_snr.png"), 14,
          "Throughput vs SNR by Strategy", "final_dataset.csv",
          "03_snr_analysis",
          "Mean throughput at each SNR level.",
          "Throughput increases with SNR. AI Adaptive tracks Fixed OTFS.")


def graph_15(df, out):
    fig, ax = plt.subplots(figsize=(FIG_WIDTH, FIG_HEIGHT))
    groups = _build_snr_groups(df, "ACS")
    xvals = _snr_xvals(groups)
    _line_grouped(ax, _label_groups(groups), xvals,
                  {STRATEGY_LABELS[s]: STRATEGY_COLORS[s] for s in STRATEGY_ORDER},
                  "SNR (dB)", "Mean ACS", "ACS vs SNR by Strategy")
    _save(fig, os.path.join(out, "03_acs_vs_snr.png"), 15,
          "ACS vs SNR by Strategy", "final_dataset.csv",
          "03_snr_analysis",
          "Mean ACS at each SNR level.",
          "ACS improves with SNR. AI Adaptive close to oracle across range.")


def graph_16(df, out):
    fig, ax = plt.subplots(figsize=(FIG_WIDTH, FIG_HEIGHT))
    groups = _build_snr_groups(df, "CQI")
    xvals = _snr_xvals(groups)
    _line_grouped(ax, _label_groups(groups), xvals,
                  {STRATEGY_LABELS[s]: STRATEGY_COLORS[s] for s in STRATEGY_ORDER},
                  "SNR (dB)", "Mean CQI", "CQI vs SNR by Strategy")
    _save(fig, os.path.join(out, "03_cqi_vs_snr.png"), 16,
          "CQI vs SNR by Strategy", "final_dataset.csv",
          "03_snr_analysis",
          "Mean CQI at each SNR level.",
          "CQI increases with SNR. Nearly identical across strategies.")


def graph_17(df, out):
    fig, ax = plt.subplots(figsize=(FIG_WIDTH, FIG_HEIGHT))
    groups = _build_snr_groups(df, "spectral_efficiency")
    xvals = _snr_xvals(groups)
    _line_grouped(ax, _label_groups(groups), xvals,
                  {STRATEGY_LABELS[s]: STRATEGY_COLORS[s] for s in STRATEGY_ORDER},
                  "SNR (dB)", "Mean Spectral Efficiency (bps/Hz)",
                  "Spectral Efficiency vs SNR by Strategy")
    _save(fig, os.path.join(out, "03_se_vs_snr.png"), 17,
          "Spectral Efficiency vs SNR by Strategy", "final_dataset.csv",
          "03_snr_analysis",
          "Mean spectral efficiency at each SNR level.",
          "SE improves with SNR. Oracle leads; AI close to Fixed OTFS.")


# ---------------------------------------------------------------------------
# CATEGORY 4: MOBILITY ANALYSIS
# ---------------------------------------------------------------------------
def _build_speed_groups(df, metric, base=10):
    df2 = df.copy()
    df2["speed_r"] = _round_col(df2["speed_kmph"], base).astype(int)
    groups = {}
    for s in STRATEGY_ORDER:
        sub = df2[df2.strategy == s]
        groups[s] = sub.groupby("speed_r")[metric].mean().to_dict()
    return groups


def _speed_xvals(groups):
    all_vals = set()
    for s in groups.values():
        all_vals.update(s.keys())
    return sorted(all_vals)


def graph_18(df, out):
    fig, ax = plt.subplots(figsize=(FIG_WIDTH, FIG_HEIGHT))
    groups = _build_speed_groups(df, "BER", 25)
    xvals = _speed_xvals(groups)
    _line_grouped(ax, _label_groups(groups), xvals,
                  {STRATEGY_LABELS[s]: STRATEGY_COLORS[s] for s in STRATEGY_ORDER},
                  "Speed (km/h)", "Mean BER", "BER vs Speed by Strategy")
    ax.set_yscale("log")
    ax.set_ylim(bottom=1e-4)
    _save(fig, os.path.join(out, "04_ber_vs_speed.png"), 18,
          "BER vs Speed by Strategy", "final_dataset.csv",
          "04_mobility_analysis",
          "Mean BER at each speed bin (rounded to nearest 25 km/h).",
          "Higher speed generally increases BER. AI tracks Fixed OTFS.")


def graph_19(df, out):
    fig, ax = plt.subplots(figsize=(FIG_WIDTH, FIG_HEIGHT))
    groups = _build_speed_groups(df, "ACS", 25)
    xvals = _speed_xvals(groups)
    _line_grouped(ax, _label_groups(groups), xvals,
                  {STRATEGY_LABELS[s]: STRATEGY_COLORS[s] for s in STRATEGY_ORDER},
                  "Speed (km/h)", "Mean ACS", "ACS vs Speed by Strategy")
    _save(fig, os.path.join(out, "04_acs_vs_speed.png"), 19,
          "ACS vs Speed by Strategy", "final_dataset.csv",
          "04_mobility_analysis",
          "Mean ACS at each speed bin.",
          "ACS degrades at higher speeds for all strategies.")


def graph_20(df, out):
    fig, ax = plt.subplots(figsize=(FIG_WIDTH, FIG_HEIGHT))
    df2 = df.copy()
    df2["speed_r"] = _round_col(df2["speed_kmph"], 25).astype(int)
    groups = {}
    for s in STRATEGY_ORDER:
        sub = df2[df2.strategy == s]
        groups[s] = (sub.groupby("speed_r")["throughput_bps"].mean() / 1000).to_dict()
    xvals = sorted(set().union(*[g.keys() for g in groups.values()]))
    _line_grouped(ax, _label_groups(groups), xvals,
                  {STRATEGY_LABELS[s]: STRATEGY_COLORS[s] for s in STRATEGY_ORDER},
                  "Speed (km/h)", "Mean Throughput (kbps)",
                  "Throughput vs Speed by Strategy")
    _save(fig, os.path.join(out, "04_tp_vs_speed.png"), 20,
          "Throughput vs Speed by Strategy", "final_dataset.csv",
          "04_mobility_analysis",
          "Mean throughput at each speed bin.",
          "Throughput decreases at higher speeds.")


def graph_21(df, out):
    fig, ax = plt.subplots(figsize=(FIG_WIDTH, FIG_HEIGHT))
    df2 = df.copy()
    df2["dop_r"] = _round_col(df2["doppler_hz"], 10).astype(int)
    groups = {}
    for s in STRATEGY_ORDER:
        sub = df2[df2.strategy == s]
        groups[s] = sub.groupby("dop_r")["BER"].mean().to_dict()
    xvals = sorted(set().union(*[g.keys() for g in groups.values()]))
    _line_grouped(ax, _label_groups(groups), xvals,
                  {STRATEGY_LABELS[s]: STRATEGY_COLORS[s] for s in STRATEGY_ORDER},
                  "Doppler Frequency (Hz)", "Mean BER", "BER vs Doppler by Strategy")
    ax.set_yscale("log")
    ax.set_ylim(bottom=1e-4)
    _save(fig, os.path.join(out, "04_ber_vs_doppler.png"), 21,
          "BER vs Doppler Frequency by Strategy", "final_dataset.csv",
          "04_mobility_analysis",
          "Mean BER at each Doppler frequency bin (rounded to nearest 10 Hz).",
          "Higher Doppler generally correlates with higher BER.")


def graph_22(df, out):
    fig, ax = plt.subplots(figsize=(FIG_WIDTH, FIG_HEIGHT))
    df2 = df.copy()
    df2["dop_r"] = _round_col(df2["doppler_hz"], 10).astype(int)
    groups = {}
    for s in STRATEGY_ORDER:
        sub = df2[df2.strategy == s]
        groups[s] = sub.groupby("dop_r")["ACS"].mean().to_dict()
    xvals = sorted(set().union(*[g.keys() for g in groups.values()]))
    _line_grouped(ax, _label_groups(groups), xvals,
                  {STRATEGY_LABELS[s]: STRATEGY_COLORS[s] for s in STRATEGY_ORDER},
                  "Doppler Frequency (Hz)", "Mean ACS", "ACS vs Doppler by Strategy")
    _save(fig, os.path.join(out, "04_acs_vs_doppler.png"), 22,
          "ACS vs Doppler Frequency by Strategy", "final_dataset.csv",
          "04_mobility_analysis",
          "Mean ACS at each Doppler frequency bin.",
          "ACS degrades with higher Doppler. AI tracks Fixed OTFS.")


# ---------------------------------------------------------------------------
# CATEGORY 5: CHANNEL ANALYSIS
# ---------------------------------------------------------------------------
def _grouped_bar_by_channel(df, metric, title, ylabel, fmt="{:.3f}"):
    fig, ax = plt.subplots(figsize=(FIG_WIDTH, FIG_HEIGHT))
    channels = ["EPA", "EVA", "ETU"]
    n_strats = len(STRATEGY_ORDER)
    width = 0.22
    x = np.arange(len(channels))
    for i, s in enumerate(STRATEGY_ORDER):
        vals = []
        for ch in channels:
            sub = df[(df.channel_profile == ch) & (df.strategy == s)]
            vals.append(sub[metric].mean())
        offset = (i - n_strats / 2 + 0.5) * width
        ax.bar(x + offset, vals, width, label=STRATEGY_LABELS[s],
               color=STRATEGY_COLORS[s], edgecolor="white", linewidth=0.5)
    ax.set_xticks(x)
    ax.set_xticklabels(channels, fontsize=FONT_TICK)
    ax.set_ylabel(ylabel, fontsize=FONT_LABEL)
    ax.set_title(title, fontsize=FONT_TITLE, fontweight="bold")
    ax.legend(fontsize=FONT_LEGEND)
    ax.grid(axis="y", alpha=0.3)
    ax.tick_params(labelsize=FONT_TICK)
    return fig


def graph_23(df, out):
    fig = _grouped_bar_by_channel(df, "BER",
                                  "BER by Channel Profile and Strategy",
                                  "Mean BER", "{:.4f}")
    _save(fig, os.path.join(out, "05_channel_ber.png"), 23,
          "BER by Channel Profile", "final_dataset.csv",
          "05_channel_analysis",
          "Mean BER for each channel profile across all strategies.",
          "ETU (most dispersive) generally shows highest BER. "
          "AI Adaptive tracks Fixed OTFS across all channels.")


def graph_24(df, out):
    fig = _grouped_bar_by_channel(df, "ACS",
                                  "ACS by Channel Profile and Strategy",
                                  "Mean ACS")
    _save(fig, os.path.join(out, "05_channel_acs.png"), 24,
          "ACS by Channel Profile", "final_dataset.csv",
          "05_channel_analysis",
          "Mean ACS for each channel profile across all strategies.",
          "EPA (least dispersive) shows highest ACS.")


def graph_25(df, out):
    fig, ax = plt.subplots(figsize=(FIG_WIDTH, FIG_HEIGHT))
    channels = ["EPA", "EVA", "ETU"]
    n_strats = len(STRATEGY_ORDER)
    width = 0.22
    x = np.arange(len(channels))
    for i, s in enumerate(STRATEGY_ORDER):
        vals = []
        for ch in channels:
            sub = df[(df.channel_profile == ch) & (df.strategy == s)]
            vals.append(sub["throughput_bps"].mean() / 1000)
        offset = (i - n_strats / 2 + 0.5) * width
        ax.bar(x + offset, vals, width, label=STRATEGY_LABELS[s],
               color=STRATEGY_COLORS[s], edgecolor="white", linewidth=0.5)
    ax.set_xticks(x)
    ax.set_xticklabels(channels, fontsize=FONT_TICK)
    ax.set_ylabel("Mean Throughput (kbps)", fontsize=FONT_LABEL)
    ax.set_title("Throughput by Channel Profile and Strategy",
                 fontsize=FONT_TITLE, fontweight="bold")
    ax.legend(fontsize=FONT_LEGEND)
    ax.grid(axis="y", alpha=0.3)
    ax.tick_params(labelsize=FONT_TICK)
    _save(fig, os.path.join(out, "05_channel_tp.png"), 25,
          "Throughput by Channel Profile", "final_dataset.csv",
          "05_channel_analysis",
          "Mean throughput for each channel profile.",
          "EPA yields highest throughput; ETU lowest.")


def graph_26(df, out):
    fig = _grouped_bar_by_channel(df, "CQI",
                                  "CQI by Channel Profile and Strategy",
                                  "Mean CQI", "{:.2f}")
    _save(fig, os.path.join(out, "05_channel_cqi.png"), 26,
          "CQI by Channel Profile", "final_dataset.csv",
          "05_channel_analysis",
          "Mean CQI for each channel profile.",
          "CQI relatively stable across channels since it is a channel property.")


# ---------------------------------------------------------------------------
# CATEGORY 6: MODULATION ANALYSIS
# ---------------------------------------------------------------------------
def _grouped_bar_by_mod(df, metric, title, ylabel, fmt="{:.3f}"):
    fig, ax = plt.subplots(figsize=(FIG_WIDTH, FIG_HEIGHT))
    n_strats = len(STRATEGY_ORDER)
    width = 0.22
    x = np.arange(len(MOD_ORDER))
    for i, s in enumerate(STRATEGY_ORDER):
        vals = []
        for m in MOD_ORDER:
            sub = df[(df.modulation_label == m) & (df.strategy == s)]
            vals.append(sub[metric].mean() if len(sub) > 0 else np.nan)
        offset = (i - n_strats / 2 + 0.5) * width
        ax.bar(x + offset, vals, width, label=STRATEGY_LABELS[s],
               color=STRATEGY_COLORS[s], edgecolor="white", linewidth=0.5)
    ax.set_xticks(x)
    ax.set_xticklabels(MOD_ORDER, fontsize=FONT_TICK)
    ax.set_ylabel(ylabel, fontsize=FONT_LABEL)
    ax.set_title(title, fontsize=FONT_TITLE, fontweight="bold")
    ax.legend(fontsize=FONT_LEGEND)
    ax.grid(axis="y", alpha=0.3)
    ax.tick_params(labelsize=FONT_TICK)
    return fig


def graph_27(df, out):
    fig = _grouped_bar_by_mod(df, "BER",
                              "BER by Modulation and Strategy",
                              "Mean BER", "{:.4f}")
    _save(fig, os.path.join(out, "06_mod_ber.png"), 27,
          "BER by Modulation", "final_dataset.csv",
          "06_modulation_analysis",
          "Mean BER for each modulation type across strategies.",
          "64-QAM shows highest BER as expected (dense constellation). "
          "AI Adaptive tracks Fixed OTFS across all modulations.")


def graph_28(df, out):
    fig, ax = plt.subplots(figsize=(FIG_WIDTH, FIG_HEIGHT))
    n_strats = len(STRATEGY_ORDER)
    width = 0.22
    x = np.arange(len(MOD_ORDER))
    for i, s in enumerate(STRATEGY_ORDER):
        vals = []
        for m in MOD_ORDER:
            sub = df[(df.modulation_label == m) & (df.strategy == s)]
            vals.append(sub["throughput_bps"].mean() / 1000 if len(sub) > 0 else np.nan)
        offset = (i - n_strats / 2 + 0.5) * width
        ax.bar(x + offset, vals, width, label=STRATEGY_LABELS[s],
               color=STRATEGY_COLORS[s], edgecolor="white", linewidth=0.5)
    ax.set_xticks(x)
    ax.set_xticklabels(MOD_ORDER, fontsize=FONT_TICK)
    ax.set_ylabel("Mean Throughput (kbps)", fontsize=FONT_LABEL)
    ax.set_title("Throughput by Modulation and Strategy",
                 fontsize=FONT_TITLE, fontweight="bold")
    ax.legend(fontsize=FONT_LEGEND)
    ax.grid(axis="y", alpha=0.3)
    ax.tick_params(labelsize=FONT_TICK)
    _save(fig, os.path.join(out, "06_mod_tp.png"), 28,
          "Throughput by Modulation", "final_dataset.csv",
          "06_modulation_analysis",
          "Mean throughput for each modulation type.",
          "64-QAM throughput lower due to high BER. QPSK most robust.")


def graph_29(df, out):
    fig = _grouped_bar_by_mod(df, "ACS",
                              "ACS by Modulation and Strategy",
                              "Mean ACS")
    _save(fig, os.path.join(out, "06_mod_acs.png"), 29,
          "ACS by Modulation", "final_dataset.csv",
          "06_modulation_analysis",
          "Mean ACS for each modulation type.",
          "QPSK achieves highest ACS. 64-QAM lowest.")


def graph_30(df, out):
    fig = _grouped_bar_by_mod(df, "CQI",
                              "CQI by Modulation and Strategy",
                              "Mean CQI", "{:.2f}")
    _save(fig, os.path.join(out, "06_mod_cqi.png"), 30,
          "CQI by Modulation", "final_dataset.csv",
          "06_modulation_analysis",
          "Mean CQI for each modulation type.",
          "CQI similar across modulations since it is channel-dependent.")


# ---------------------------------------------------------------------------
# CATEGORY 7: AI ANALYSIS
# ---------------------------------------------------------------------------
def _scatter_pred_actual(ax, pred, actual, label, color):
    mask = pred.notna() & actual.notna()
    p, a = pred[mask].values, actual[mask].values
    ax.scatter(p, a, alpha=0.4, s=15, label=label, color=color, edgecolors="none")
    lims = [min(p.min(), a.min()), max(p.max(), a.max())]
    ax.plot(lims, lims, "k--", alpha=0.5, linewidth=1, label="Ideal y=x")
    ax.set_xlim(left=min(0, lims[0]))
    ax.set_ylim(bottom=min(0, lims[1]))


def _scatter_stats(pred, actual):
    mask = pred.notna() & actual.notna()
    p, a = pred[mask].values, actual[mask].values
    if len(p) < 3:
        return "n<3"
    mae = np.mean(np.abs(p - a))
    rmse = np.sqrt(np.mean((p - a) ** 2))
    ss_res = np.sum((a - p) ** 2)
    ss_tot = np.sum((a - np.mean(a)) ** 2)
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else np.nan
    return f"MAE={mae:.4f}  RMSE={rmse:.4f}  R2={r2:.4f}"


def graph_31(df, out):
    ai = df[df.strategy == "ai_adaptive"]
    fig, ax = plt.subplots(figsize=(FIG_WIDTH, FIG_HEIGHT))
    _scatter_pred_actual(ax, ai["predicted_OTFS_BER"], ai["actual_BER_OTFS"],
                         "OTFS", WAVEFORM_COLORS["OTFS"])
    _scatter_pred_actual(ax, ai["predicted_ODDM_BER"], ai["actual_BER_ODDM"],
                         "ODDM", WAVEFORM_COLORS["ODDM"])
    stats_otfs = _scatter_stats(ai["predicted_OTFS_BER"], ai["actual_BER_OTFS"])
    stats_oddm = _scatter_stats(ai["predicted_ODDM_BER"], ai["actual_BER_ODDM"])
    ax.set_xlabel("Predicted BER", fontsize=FONT_LABEL)
    ax.set_ylabel("Actual BER", fontsize=FONT_LABEL)
    ax.set_title(f"Predicted vs Actual BER\nOTFS: {stats_otfs}\nODDM: {stats_oddm}",
                 fontsize=FONT_TITLE, fontweight="bold")
    ax.legend(fontsize=FONT_LEGEND)
    ax.grid(alpha=0.3)
    _save(fig, os.path.join(out, "07_pred_actual_ber.png"), 31,
          "Predicted vs Actual BER", "predicted_vs_actual.csv",
          "07_ai_analysis",
          "AI engine predicted BER vs actual measured BER for both waveforms.",
          "Scatter around y=x indicates prediction quality.")


def graph_32(df, out):
    ai = df[df.strategy == "ai_adaptive"]
    fig, ax = plt.subplots(figsize=(FIG_WIDTH, FIG_HEIGHT))
    _scatter_pred_actual(ax, ai["predicted_OTFS_throughput"] / 1000,
                         ai["actual_TP_OTFS"] / 1000,
                         "OTFS", WAVEFORM_COLORS["OTFS"])
    _scatter_pred_actual(ax, ai["predicted_ODDM_throughput"] / 1000,
                         ai["actual_TP_ODDM"] / 1000,
                         "ODDM", WAVEFORM_COLORS["ODDM"])
    ax.set_xlabel("Predicted Throughput (kbps)", fontsize=FONT_LABEL)
    ax.set_ylabel("Actual Throughput (kbps)", fontsize=FONT_LABEL)
    ax.set_title("Predicted vs Actual Throughput", fontsize=FONT_TITLE,
                 fontweight="bold")
    ax.legend(fontsize=FONT_LEGEND)
    ax.grid(alpha=0.3)
    _save(fig, os.path.join(out, "07_pred_actual_tp.png"), 32,
          "Predicted vs Actual Throughput", "predicted_vs_actual.csv",
          "07_ai_analysis",
          "AI engine predicted throughput vs actual throughput.",
          "Clustering along y=x indicates good prediction.")


def graph_33(df, out):
    ai = df[df.strategy == "ai_adaptive"]
    fig, ax = plt.subplots(figsize=(FIG_WIDTH, FIG_HEIGHT))
    _scatter_pred_actual(ax, ai["predicted_OTFS_ACS"], ai["actual_ACS_OTFS"],
                         "OTFS", WAVEFORM_COLORS["OTFS"])
    _scatter_pred_actual(ax, ai["predicted_ODDM_ACS"], ai["actual_ACS_ODDM"],
                         "ODDM", WAVEFORM_COLORS["ODDM"])
    stats_otfs = _scatter_stats(ai["predicted_OTFS_ACS"], ai["actual_ACS_OTFS"])
    stats_oddm = _scatter_stats(ai["predicted_ODDM_ACS"], ai["actual_ACS_ODDM"])
    ax.set_xlabel("Predicted ACS", fontsize=FONT_LABEL)
    ax.set_ylabel("Actual ACS", fontsize=FONT_LABEL)
    ax.set_title(f"Predicted vs Actual ACS\nOTFS: {stats_otfs}\nODDM: {stats_oddm}",
                 fontsize=FONT_TITLE, fontweight="bold")
    ax.legend(fontsize=FONT_LEGEND)
    ax.grid(alpha=0.3)
    _save(fig, os.path.join(out, "07_pred_actual_acs.png"), 33,
          "Predicted vs Actual ACS", "predicted_vs_actual.csv",
          "07_ai_analysis",
          "AI engine predicted ACS vs actual ACS.",
          "Scatter along y=x indicates prediction calibration.")


# ---------------------------------------------------------------------------
# CATEGORY 8: AI DECISION QUALITY
# ---------------------------------------------------------------------------
def graph_34(df, out):
    ai = df[df.strategy == "ai_adaptive"]
    env_agree = ai.groupby("environment")["decision_correct"].mean().reindex(ENV_ORDER)
    env_count = ai.groupby("environment")["decision_correct"].count().reindex(ENV_ORDER)
    fig, ax = plt.subplots(figsize=(FIG_WIDTH, FIG_HEIGHT))
    colors = [ENV_COLORS.get(e, "#999") for e in env_agree.index]
    bars = ax.bar(range(len(env_agree)), env_agree.values, color=colors,
                  edgecolor="white", linewidth=0.5)
    for i, (bar, val, cnt) in enumerate(zip(bars, env_agree.values, env_count.values)):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.01,
                f"{val:.1%}\n(n={int(cnt)})", ha="center", va="bottom",
                fontsize=FONT_TICK)
    ax.set_xticks(range(len(env_agree)))
    ax.set_xticklabels(env_agree.index, fontsize=FONT_TICK, rotation=15, ha="right")
    ax.set_ylabel("Oracle Agreement Rate", fontsize=FONT_LABEL)
    ax.set_title("AI-Oracle Decision Agreement by Environment",
                 fontsize=FONT_TITLE, fontweight="bold")
    ax.set_ylim(0, 1.15)
    ax.grid(axis="y", alpha=0.3)
    ax.axhline(y=ai.decision_correct.mean(), color="gray", linestyle="--",
               alpha=0.7, label=f"Overall: {ai.decision_correct.mean():.1%}")
    ax.legend(fontsize=FONT_LEGEND)
    _save(fig, os.path.join(out, "08_ai_oracle_agreement_env.png"), 34,
          "AI-Oracle Decision Agreement by Environment", "oracle_comparison.csv",
          "08_oracle_analysis",
          "Oracle agreement rate by environment category.",
          "Pedestrian and UrbanFast show highest agreement. Urban "
          "(most dynamic) shows lower agreement where switching matters most.")


# ---------------------------------------------------------------------------
# CATEGORY 9: DIGITAL TWIN - SWITCHING TIMELINE
# ---------------------------------------------------------------------------
def graph_35(df, out):
    ai = df[df.strategy == "ai_adaptive"]
    scenarios_with_switches = ai.groupby("scenario_id")["switched"].sum()
    switch_scenarios = scenarios_with_switches[scenarios_with_switches > 0].index.tolist()
    if not switch_scenarios:
        switch_scenarios = ["A", "B", "C", "D"]
    n_show = min(4, len(switch_scenarios))
    show_scs = switch_scenarios[:n_show]
    fig, axes = plt.subplots(n_show, 1, figsize=(FIG_WIDTH, 3 * n_show),
                             sharex=False)
    if n_show == 1:
        axes = [axes]
    for idx, sc in enumerate(show_scs):
        ax = axes[idx]
        sc_ai = ai[ai.scenario_id == sc].sort_values("frame")
        wf_num = (sc_ai.waveform == "ODDM").astype(int)
        ax.step(sc_ai.frame.values, wf_num.values, where="post",
                color="#4CAF50", linewidth=1.5)
        sw = sc_ai[sc_ai.switched == 1]
        if len(sw) > 0:
            ax.scatter(sw.frame.values, (sw.waveform == "ODDM").astype(int).values,
                       color="red", s=60, zorder=5, label="Switch")
        ax.set_yticks([0, 1])
        ax.set_yticklabels(["OTFS", "ODDM"], fontsize=FONT_TICK)
        n_sw = int(sc_ai.switched.sum())
        ax.set_ylabel(f"Sc {sc}\n({n_sw} sw)", fontsize=FONT_TICK)
        ax.set_title("") if idx > 0 else None
        ax.grid(alpha=0.3)
        ax.legend(fontsize=8, loc="upper right")
    axes[-1].set_xlabel("Frame Index", fontsize=FONT_LABEL)
    fig.suptitle("AI Waveform Switching Timeline (Scenarios with Switches)",
                 fontsize=FONT_TITLE, fontweight="bold", y=1.01)
    _save(fig, os.path.join(out, "09_switching_timeline.png"), 35,
          "AI Waveform Switching Timeline", "oracle_comparison.csv",
          "09_digital_twin",
          "Step plot of AI waveform selection over frames for scenarios "
          "with at least one switch.",
          "Red markers indicate switching points. Total 22 switches across "
          "all scenarios.")


# ---------------------------------------------------------------------------
# CATEGORY 10: SUMMARY HEATMAPS
# ---------------------------------------------------------------------------
def graph_36(df, out):
    sc_sum = df.groupby(["scenario_id", "strategy"])["ACS"].mean().unstack()
    sc_sum = sc_sum.reindex(columns=STRATEGY_ORDER)
    sc_sum = sc_sum.sort_index()
    fig, ax = plt.subplots(figsize=(FIG_WIDTH, 8))
    im = ax.imshow(sc_sum.values, cmap="YlGnBu", aspect="auto", vmin=0.2, vmax=0.6)
    ax.set_xticks(range(len(sc_sum.columns)))
    ax.set_xticklabels([STRATEGY_LABELS[c] for c in sc_sum.columns],
                       fontsize=FONT_TICK, rotation=15, ha="right")
    ax.set_yticks(range(len(sc_sum.index)))
    ax.set_yticklabels(sc_sum.index, fontsize=FONT_TICK)
    for i in range(len(sc_sum.index)):
        for j in range(len(sc_sum.columns)):
            val = sc_sum.values[i, j]
            if not np.isnan(val):
                ax.text(j, i, f"{val:.3f}", ha="center", va="center",
                        fontsize=8,
                        color="white" if val > 0.45 else "black")
    plt.colorbar(im, ax=ax, label="Mean ACS")
    ax.set_title("Scenario ACS Heatmap: Strategy Comparison",
                 fontsize=FONT_TITLE, fontweight="bold")
    _save(fig, os.path.join(out, "10_scenario_acs_heatmap.png"), 36,
          "Scenario ACS Heatmap", "scenario_summary.csv",
          "10_summary",
          "Heatmap of mean ACS per scenario and strategy.",
          "Shows where adaptation helps (AI close to oracle) and where "
          "it does not.")


def graph_37(df, out):
    sc_sum = df.groupby(["scenario_id", "strategy"])["BER"].mean().unstack()
    sc_sum = sc_sum.reindex(columns=STRATEGY_ORDER)
    sc_sum = sc_sum.sort_index()
    fig, ax = plt.subplots(figsize=(FIG_WIDTH, 8))
    im = ax.imshow(sc_sum.values, cmap="YlOrRd_r", aspect="auto", vmin=0, vmax=0.15)
    ax.set_xticks(range(len(sc_sum.columns)))
    ax.set_xticklabels([STRATEGY_LABELS[c] for c in sc_sum.columns],
                       fontsize=FONT_TICK, rotation=15, ha="right")
    ax.set_yticks(range(len(sc_sum.index)))
    ax.set_yticklabels(sc_sum.index, fontsize=FONT_TICK)
    for i in range(len(sc_sum.index)):
        for j in range(len(sc_sum.columns)):
            val = sc_sum.values[i, j]
            if not np.isnan(val):
                ax.text(j, i, f"{val:.4f}", ha="center", va="center",
                        fontsize=7,
                        color="white" if val > 0.08 else "black")
    plt.colorbar(im, ax=ax, label="Mean BER")
    ax.set_title("Scenario BER Heatmap: Strategy Comparison",
                 fontsize=FONT_TITLE, fontweight="bold")
    _save(fig, os.path.join(out, "10_scenario_ber_heatmap.png"), 37,
          "Scenario BER Heatmap", "scenario_summary.csv",
          "10_summary",
          "Heatmap of mean BER per scenario and strategy.",
          "Lower BER is better. Shows where AI narrows the gap to oracle.")


# ---------------------------------------------------------------------------
# GRAPH 38: AI REGRET DISTRIBUTION
# ---------------------------------------------------------------------------
def graph_38(df, out):
    ai = df[df.strategy == "ai_adaptive"]
    fig, axes = plt.subplots(1, 2, figsize=(FIG_WIDTH * 2, FIG_HEIGHT))
    ax1, ax2 = axes
    ax1.hist(ai.ACS_regret.dropna(), bins=30, color="#4CAF50", edgecolor="white",
             alpha=0.8)
    ax1.axvline(ai.ACS_regret.mean(), color="red", linestyle="--",
                label=f"Mean={ai.ACS_regret.mean():.4f}")
    ax1.axvline(ai.ACS_regret.quantile(0.9), color="orange", linestyle="--",
                label=f"P90={ai.ACS_regret.quantile(0.9):.4f}")
    ax1.set_xlabel("ACS Regret", fontsize=FONT_LABEL)
    ax1.set_ylabel("Frame Count", fontsize=FONT_LABEL)
    ax1.set_title("ACS Regret Distribution", fontsize=FONT_TITLE,
                  fontweight="bold")
    ax1.legend(fontsize=FONT_LEGEND)
    ax1.grid(alpha=0.3)

    ax2.hist(ai.BER_regret.dropna(), bins=30, color="#2196F3", edgecolor="white",
             alpha=0.8)
    ax2.axvline(ai.BER_regret.mean(), color="red", linestyle="--",
                label=f"Mean={ai.BER_regret.mean():.4f}")
    ax2.axvline(ai.BER_regret.quantile(0.9), color="orange", linestyle="--",
                label=f"P90={ai.BER_regret.quantile(0.9):.4f}")
    ax2.set_xlabel("BER Regret", fontsize=FONT_LABEL)
    ax2.set_ylabel("Frame Count", fontsize=FONT_LABEL)
    ax2.set_title("BER Regret Distribution", fontsize=FONT_TITLE,
                  fontweight="bold")
    ax2.legend(fontsize=FONT_LEGEND)
    ax2.grid(alpha=0.3)
    fig.suptitle("AI Regret Analysis", fontsize=FONT_TITLE,
                 fontweight="bold", y=1.01)
    _save(fig, os.path.join(out, "08_regret_distribution.png"), 38,
          "ACS and BER Regret Distribution", "oracle_comparison.csv",
          "08_oracle_analysis",
          "Distribution of regret (oracle metric minus AI-selected metric).",
          "Low mean regret indicates AI close to oracle. Tail values show "
          "worst-case suboptimal decisions.")


# ---------------------------------------------------------------------------
# GRAPH 39: PERFORMANCE GAP TO ORACLE
# ---------------------------------------------------------------------------
def graph_39(df, out):
    ai = df[df.strategy == "ai_adaptive"]
    env_gap = ai.groupby("environment").agg(
        oracle_acs=("oracle_ACS", "mean"),
        ai_acs=("ACS", "mean"),
    ).reindex(ENV_ORDER)
    env_gap["gap"] = env_gap.oracle_acs - env_gap.ai_acs
    fig, ax = plt.subplots(figsize=(FIG_WIDTH, FIG_HEIGHT))
    x = np.arange(len(env_gap))
    width = 0.35
    ax.bar(x - width / 2, env_gap.oracle_acs.values, width,
           label="Oracle ACS", color=STRATEGY_COLORS["oracle"], alpha=0.8)
    ax.bar(x + width / 2, env_gap.ai_acs.values, width,
           label="AI Adaptive ACS", color=STRATEGY_COLORS["ai_adaptive"], alpha=0.8)
    for i, gap in enumerate(env_gap.gap.values):
        ax.annotate(f"Gap: {gap:.4f}",
                    xy=(x[i] + width / 2, env_gap.ai_acs.values[i]),
                    xytext=(0, 5), textcoords="offset points",
                    ha="center", fontsize=8, color="red")
    ax.set_xticks(x)
    ax.set_xticklabels(env_gap.index, fontsize=FONT_TICK, rotation=15, ha="right")
    ax.set_ylabel("Mean ACS", fontsize=FONT_LABEL)
    ax.set_title("AI vs Oracle ACS Gap by Environment",
                 fontsize=FONT_TITLE, fontweight="bold")
    ax.legend(fontsize=FONT_LEGEND)
    ax.grid(axis="y", alpha=0.3)
    _save(fig, os.path.join(out, "08_oracle_gap_env.png"), 39,
          "AI vs Oracle ACS Gap by Environment", "oracle_comparison.csv",
          "08_oracle_analysis",
          "Oracle ACS vs AI Adaptive ACS for each environment.",
          "Smaller gap means AI closer to ideal. Urban environments show "
          "largest gap where switching decisions matter most.")


# ---------------------------------------------------------------------------
# GRAPH 40: SUMMARY RADAR / OVERVIEW TABLE
# ---------------------------------------------------------------------------
def graph_40(df, out):
    fig, ax = plt.subplots(figsize=(FIG_WIDTH, FIG_HEIGHT))
    ax.axis("off")
    metrics = ["BER", "throughput_bps", "CQI", "ACS", "spectral_efficiency"]
    display = ["BER", "Throughput\n(kbps)", "CQI", "ACS", "SE\n(bps/Hz)"]
    data = []
    for s in STRATEGY_ORDER:
        row = []
        for m in metrics:
            row.append(df[df.strategy == s][m].mean())
        data.append(row)
    data = np.array(data)
    for i, m in enumerate(display):
        vals = data[:, i]
        best = vals.min() if m == "BER" else vals.max()
        for j in range(4):
            data[j, i] = data[j, i]
    table = ax.table(
        cellText=[[f"{data[j, i]:.4f}" if i == 0 else
                    f"{data[j, i]/1000:.1f}" if i == 1 else
                    f"{data[j, i]:.2f}"
                    for i in range(5)] for j in range(4)],
        rowLabels=[STRATEGY_LABELS[s] for s in STRATEGY_ORDER],
        colLabels=display,
        loc="center",
        cellLoc="center",
    )
    table.auto_set_font_size(False)
    table.set_fontsize(FONT_TICK)
    table.scale(1.2, 1.5)
    for (row, col), cell in table.get_celld().items():
        if col >= 0:
            cell.set_text_props(ha="center", va="center")
        if row == 0:
            cell.set_text_props(fontweight="bold")
            cell.set_facecolor("#E3F2FD")
        elif col == -1:
            cell.set_text_props(fontweight="bold")
            cell.set_facecolor("#F5F5F5")
    ax.set_title("Strategy Comparison Summary Table",
                 fontsize=FONT_TITLE, fontweight="bold", pad=20)
    _save(fig, os.path.join(out, "10_summary_table.png"), 40,
          "Strategy Comparison Summary Table", "final_dataset.csv",
          "10_summary",
          "Tabular comparison of key metrics across all strategies.",
          "Quick reference for overall strategy performance.")


# ---------------------------------------------------------------------------
# GRAPH 41: SNR ACS BY ENVIRONMENT
# ---------------------------------------------------------------------------
def graph_41(df, out):
    fig, ax = plt.subplots(figsize=(FIG_WIDTH, FIG_HEIGHT))
    df2 = df.copy()
    df2["snr_r"] = _round_col(df2["snr_db"], 2).astype(int)
    ai = df2[df2.strategy == "ai_adaptive"]
    for env in ENV_ORDER:
        sub = ai[ai.environment == env]
        grp = sub.groupby("snr_r")["ACS"].mean()
        if len(grp) > 1:
            ax.plot(grp.index, grp.values, "-o", label=env,
                    color=ENV_COLORS[env], markersize=4, linewidth=2)
    ax.set_xlabel("SNR (dB)", fontsize=FONT_LABEL)
    ax.set_ylabel("Mean ACS", fontsize=FONT_LABEL)
    ax.set_title("AI Adaptive ACS vs SNR by Environment",
                 fontsize=FONT_TITLE, fontweight="bold")
    ax.legend(fontsize=FONT_LEGEND)
    ax.grid(alpha=0.3)
    _save(fig, os.path.join(out, "03_acs_snr_environment.png"), 41,
          "AI Adaptive ACS vs SNR by Environment", "final_dataset.csv",
          "03_snr_analysis",
          "AI Adaptive ACS at each SNR level, broken down by environment.",
          "Different environments show different ACS-SNR profiles.")


# ---------------------------------------------------------------------------
# GRAPH 42: AI CONFIDENCE HISTOGRAM
# ---------------------------------------------------------------------------
def graph_42(df, out):
    ai = df[df.strategy == "ai_adaptive"]
    fig, ax = plt.subplots(figsize=(FIG_WIDTH, FIG_HEIGHT))
    ax.hist(ai.confidence.dropna(), bins=30, color="#4CAF50", edgecolor="white",
            alpha=0.8)
    ax.axvline(ai.confidence.mean(), color="red", linestyle="--",
               label=f"Mean={ai.confidence.mean():.4f}")
    ax.set_xlabel("AI Prediction Confidence", fontsize=FONT_LABEL)
    ax.set_ylabel("Frame Count", fontsize=FONT_LABEL)
    ax.set_title("AI Adaptive: Prediction Confidence Distribution",
                 fontsize=FONT_TITLE, fontweight="bold")
    ax.legend(fontsize=FONT_LEGEND)
    ax.grid(alpha=0.3)
    _save(fig, os.path.join(out, "07_ai_confidence_hist.png"), 42,
          "AI Prediction Confidence Distribution", "final_dataset.csv",
          "07_ai_analysis",
          "Distribution of AI engine confidence scores.",
          "Low confidence values suggest the AI engine may benefit from "
          "calibration or richer features.")


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Phase 7 Visualizations")
    parser.add_argument("--dataset", default=None)
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    ds_path = args.dataset or DEFAULT_DS
    out_root = args.output or DEFAULT_OUT

    t0 = time.time()
    print("=" * 70)
    print("  PHASE 7: COMMUNICATION-SYSTEM VISUALIZATION")
    print("=" * 70)

    # Verify checksum
    with open(ds_path, "rb") as fh:
        checksum_before = hashlib.md5(fh.read()).hexdigest()
    print(f"  Dataset: {ds_path}")
    print(f"  Checksum (before): {checksum_before}")

    # Load
    df = pd.read_csv(ds_path)
    print(f"  Loaded: {len(df)} rows x {len(df.columns)} columns")

    # Ensure output dirs exist
    cats = [f"{i:02d}_{n}" for i, n in enumerate([
        "system_overview", "waveform_comparison", "snr_analysis",
        "mobility_analysis", "channel_analysis", "modulation_analysis",
        "ai_analysis", "oracle_analysis", "digital_twin", "summary"], 1)]
    for c in cats:
        os.makedirs(os.path.join(out_root, c), exist_ok=True)

    # Generate graphs
    print("\n[1/3] Generating graphs...")
    graph_01(df, os.path.join(out_root, "01_system_overview"))
    graph_02(df, os.path.join(out_root, "01_system_overview"))
    graph_03(df, os.path.join(out_root, "01_system_overview"))
    graph_04(df, os.path.join(out_root, "01_system_overview"))
    graph_05(df, os.path.join(out_root, "01_system_overview"))
    graph_06(df, os.path.join(out_root, "01_system_overview"))

    graph_07(df, os.path.join(out_root, "02_waveform_comparison"))
    graph_08(df, os.path.join(out_root, "02_waveform_comparison"))
    graph_09(df, os.path.join(out_root, "02_waveform_comparison"))
    graph_10(df, os.path.join(out_root, "02_waveform_comparison"))
    graph_11(df, os.path.join(out_root, "02_waveform_comparison"))
    graph_12(df, os.path.join(out_root, "02_waveform_comparison"))

    graph_13(df, os.path.join(out_root, "03_snr_analysis"))
    graph_14(df, os.path.join(out_root, "03_snr_analysis"))
    graph_15(df, os.path.join(out_root, "03_snr_analysis"))
    graph_16(df, os.path.join(out_root, "03_snr_analysis"))
    graph_17(df, os.path.join(out_root, "03_snr_analysis"))

    graph_18(df, os.path.join(out_root, "04_mobility_analysis"))
    graph_19(df, os.path.join(out_root, "04_mobility_analysis"))
    graph_20(df, os.path.join(out_root, "04_mobility_analysis"))
    graph_21(df, os.path.join(out_root, "04_mobility_analysis"))
    graph_22(df, os.path.join(out_root, "04_mobility_analysis"))

    graph_23(df, os.path.join(out_root, "05_channel_analysis"))
    graph_24(df, os.path.join(out_root, "05_channel_analysis"))
    graph_25(df, os.path.join(out_root, "05_channel_analysis"))
    graph_26(df, os.path.join(out_root, "05_channel_analysis"))

    graph_27(df, os.path.join(out_root, "06_modulation_analysis"))
    graph_28(df, os.path.join(out_root, "06_modulation_analysis"))
    graph_29(df, os.path.join(out_root, "06_modulation_analysis"))
    graph_30(df, os.path.join(out_root, "06_modulation_analysis"))

    graph_31(df, os.path.join(out_root, "07_ai_analysis"))
    graph_32(df, os.path.join(out_root, "07_ai_analysis"))
    graph_33(df, os.path.join(out_root, "07_ai_analysis"))

    graph_34(df, os.path.join(out_root, "08_oracle_analysis"))

    graph_35(df, os.path.join(out_root, "09_digital_twin"))

    graph_36(df, os.path.join(out_root, "10_summary"))
    graph_37(df, os.path.join(out_root, "10_summary"))

    graph_38(df, os.path.join(out_root, "08_oracle_analysis"))
    graph_39(df, os.path.join(out_root, "08_oracle_analysis"))

    graph_40(df, os.path.join(out_root, "10_summary"))
    graph_41(df, os.path.join(out_root, "03_snr_analysis"))
    graph_42(df, os.path.join(out_root, "07_ai_analysis"))

    # Write graph_index.json
    print(f"\n[2/3] Writing graph_index.json ({len(graph_index)} graphs)...")
    idx_path = os.path.join(out_root, "graph_index.json")
    with open(idx_path, "w", encoding="utf-8") as fh:
        json.dump(graph_index, fh, indent=2, ensure_ascii=False)

    # Verify checksum unchanged
    with open(ds_path, "rb") as fh:
        checksum_after = hashlib.md5(fh.read()).hexdigest()
    print(f"\n[3/3] Checksum verification:")
    print(f"  Before: {checksum_before}")
    print(f"  After:  {checksum_after}")
    print(f"  Match:  {checksum_before == checksum_after}")

    elapsed = time.time() - t0
    print(f"\n  Total graphs: {len(graph_index)}")
    print(f"  Runtime: {elapsed:.1f}s")
    print(f"  Output: {out_root}")
    print("\n" + "=" * 70)
    print("  PHASE 7 VISUALIZATION COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    main()
