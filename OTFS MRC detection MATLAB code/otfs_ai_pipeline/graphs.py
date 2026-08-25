"""
graphs.py
=========
Section B / C / D graphs from the project spec (Section A -- raw MATLAB
communication-performance graphs -- already exists on the MATLAB side and
is not regenerated here).

  Section B (AI graphs, from predict.py validation-mode output):
    13 Predicted vs Actual BER
    14 Predicted vs Actual Throughput
    15 Prediction Error vs Environment
    16 Feature Importance                  (called from train_model.py)
    17 Detector Recommendation Accuracy (per environment)
    18 Scenario AI vs Real-world AI vs MATLAB

  Section C (advanced, from the training dataset):
    19 Environment Communication Radar Chart
    20 BER Surface Plot
    21 Throughput Surface Plot
    22 Detector Decision Heatmap

  Section D (novelty):
    23 Microphone Confidence vs Prediction Accuracy
    24 Real Environment vs Simulated Environment
    25 Communication Decision Dashboard

Every function is defensive about missing columns/files (prints a skip
message and returns None) so a partially-populated pipeline never crashes
graph generation -- callers just get fewer PNGs.

All functions save under config.GRAPHS_DIR and return the saved path (or
None if skipped).
"""

import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D  # noqa: F401  (registers 3d projection)
import numpy as np
import pandas as pd

from config import GRAPHS_DIR, DETECTOR_LIST
from communication_quality import classify_quality_frame, QUALITY_ORDER


def _save(fig, filename):
    path = os.path.join(GRAPHS_DIR, filename)
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Graph saved -> {path}")
    return path


def _skip(name, reason):
    print(f"  [skip] {name}: {reason}")
    return None


# ---------------------------------------------------------------------------
# Section B -- AI prediction graphs
# ---------------------------------------------------------------------------
def plot_predicted_vs_actual(df: pd.DataFrame, target: str, filename: str,
                              title: str, log_scale: bool = False):
    """Graphs 13 & 14 (and reusable for any other metric)."""
    col_pred = f"Predicted_{target}"
    if target not in df.columns or col_pred not in df.columns:
        return _skip(title, f"missing '{target}' or '{col_pred}'")

    y_true = df[target].astype(float).values
    y_pred = df[col_pred].astype(float).values
    if log_scale:
        y_true = np.clip(y_true, 1e-8, None)
        y_pred = np.clip(y_pred, 1e-8, None)

    fig, ax = plt.subplots(figsize=(6.5, 6))
    ax.scatter(y_true, y_pred, s=14, alpha=0.5, edgecolors="none", color="#4C72B0")
    lims = [min(y_true.min(), y_pred.min()), max(y_true.max(), y_pred.max())]
    if lims[0] == lims[1]:
        lims = [lims[0] - 1, lims[1] + 1]
    ax.plot(lims, lims, "r--", linewidth=1, label="Ideal (y = x)")
    if log_scale:
        ax.set_xscale("log"); ax.set_yscale("log")
    ax.set_xlabel(f"Actual {target}"); ax.set_ylabel(f"Predicted {target}")
    ax.set_title(title)
    ax.grid(True, alpha=0.3); ax.legend()
    return _save(fig, filename)


def plot_prediction_error_vs_environment(df: pd.DataFrame, target: str = "BER"):
    """Graph 15: Prediction Error vs Environment (boxplot of relative error)."""
    col_pred = f"Predicted_{target}"
    if "Environment" not in df.columns or target not in df.columns or col_pred not in df.columns:
        return _skip("Prediction Error vs Environment", "missing Environment/target/prediction columns")

    d = df.copy()
    denom = np.maximum(np.abs(d[target].astype(float)), max(d[target].astype(float).median() * 0.01, 1e-9))
    d["_rel_err_pct"] = 100.0 * np.abs(d[target].astype(float) - d[col_pred].astype(float)) / denom

    envs = sorted(d["Environment"].dropna().unique().tolist())
    data = [d.loc[d["Environment"] == e, "_rel_err_pct"].values for e in envs]

    fig, ax = plt.subplots(figsize=(8, 5.5))
    ax.boxplot(data, labels=envs, showfliers=False)
    ax.set_ylabel(f"{target} relative error (%)")
    ax.set_title(f"Prediction Error vs Environment ({target})")
    ax.tick_params(axis="x", rotation=25)
    ax.grid(True, alpha=0.3, axis="y")
    return _save(fig, "15_prediction_error_vs_environment.png")


def plot_feature_importance(model, feature_names, target: str):
    """Graph 16: Feature Importance for the winning model of a given target.
    Works for any sklearn estimator exposing `feature_importances_`
    (RandomForest / GradientBoosting / DecisionTree), including inside a
    Pipeline / TransformedTargetRegressor -- caller passes the raw fitted
    tree estimator + already-expanded (post-one-hot) feature names."""
    if not hasattr(model, "feature_importances_"):
        return _skip(f"Feature Importance ({target})", "model has no feature_importances_")

    importances = model.feature_importances_
    order = np.argsort(importances)[::-1][:20]  # top 20
    names = np.array(feature_names)[order]
    vals = importances[order]

    fig, ax = plt.subplots(figsize=(8, max(4, 0.35 * len(names))))
    ax.barh(range(len(names)), vals[::-1], color="#55A868", edgecolor="black")
    ax.set_yticks(range(len(names))); ax.set_yticklabels(names[::-1], fontsize=8)
    ax.set_xlabel("Importance")
    ax.set_title(f"Feature Importance -- {target}")
    ax.grid(True, alpha=0.3, axis="x")
    return _save(fig, f"16_feature_importance_{target}.png")


def plot_detector_recommendation_accuracy(det_eval_df: pd.DataFrame):
    """Graph 17: per-environment detector recommendation accuracy bar chart.
    Expects det_eval_df with 'Detector' (actual best) and
    'Predicted_Best_Detector' columns (as written by predict.py)."""
    need = {"Detector", "Predicted_Best_Detector"}
    if not need.issubset(det_eval_df.columns):
        return _skip("Detector Recommendation Accuracy", f"missing columns {need}")

    d = det_eval_df.copy()
    d["_correct"] = (d["Detector"] == d["Predicted_Best_Detector"]).astype(float)

    if "Environment" in d.columns:
        acc = d.groupby("Environment")["_correct"].mean().sort_index()
        xlabel = "Environment"
    else:
        acc = pd.Series({"Overall": d["_correct"].mean()})
        xlabel = ""

    fig, ax = plt.subplots(figsize=(7.5, 5))
    ax.bar(acc.index.astype(str), acc.values * 100, color="#8172B2", edgecolor="black")
    ax.set_ylim(0, 100)
    ax.set_ylabel("Detector recommendation accuracy (%)")
    ax.set_xlabel(xlabel)
    ax.set_title("Detector Recommendation Accuracy")
    ax.tick_params(axis="x", rotation=25)
    ax.grid(True, alpha=0.3, axis="y")
    return _save(fig, "17_detector_recommendation_accuracy.png")


def plot_scenario_vs_realworld_vs_matlab(scenario_df: pd.DataFrame = None,
                                          realworld_df: pd.DataFrame = None,
                                          matlab_df: pd.DataFrame = None,
                                          target: str = "BER"):
    """Graph 18: compares mean `target` across up to three sources --
    Scenario-Mode AI predictions, Real-world (microphone) AI predictions,
    and MATLAB ground truth -- grouped by SNR_dB. Any source that's None or
    missing the target column is silently omitted."""
    sources = {
        "Scenario AI": scenario_df, "Real-world AI": realworld_df, "MATLAB": matlab_df,
    }
    col_map = {"Scenario AI": f"Predicted_{target}", "Real-world AI": f"Predicted_{target}",
               "MATLAB": target}

    fig, ax = plt.subplots(figsize=(8, 5.5))
    plotted = False
    for label, d in sources.items():
        col = col_map[label]
        if d is None or "SNR_dB" not in d.columns or col not in d.columns:
            continue
        g = d.groupby("SNR_dB")[col].mean().sort_index()
        vals = np.clip(g.values, 1e-8, None) if target in ("BER", "SER", "PER") else g.values
        ax.plot(g.index, vals, marker="o", label=label)
        plotted = True

    if not plotted:
        plt.close(fig)
        return _skip("Scenario AI vs Real-world AI vs MATLAB", "no usable sources provided")

    if target in ("BER", "SER", "PER"):
        ax.set_yscale("log")
    ax.set_xlabel("SNR (dB)"); ax.set_ylabel(f"Mean {target}")
    ax.set_title(f"Scenario AI vs Real-world AI vs MATLAB -- {target}")
    ax.grid(True, alpha=0.3, which="both"); ax.legend()
    return _save(fig, "18_scenario_vs_realworld_vs_matlab.png")


# ---------------------------------------------------------------------------
# Section C -- advanced graphs (from the training dataset)
# ---------------------------------------------------------------------------
def plot_environment_radar(df: pd.DataFrame):
    """Graph 19: radar chart comparing mean BER(inv)/CQI/Throughput/SE/Runtime(inv)
    per Environment, each axis min-max normalised to [0, 1] (higher = better)."""
    metrics = ["BER", "CQI", "Throughput_bps", "SpectralEfficiency_bps_per_Hz", "Runtime_sec"]
    metrics = [m for m in metrics if m in df.columns]
    if "Environment" not in df.columns or len(metrics) < 3:
        return _skip("Environment Communication Radar", "missing Environment or too few metrics")

    agg = df.groupby("Environment")[metrics].mean()

    # Normalise each metric to [0,1]; invert BER and Runtime so higher=better everywhere.
    norm = pd.DataFrame(index=agg.index)
    for m in metrics:
        col = agg[m].astype(float)
        lo, hi = col.min(), col.max()
        span = (hi - lo) or 1.0
        scaled = (col - lo) / span
        norm[m] = (1 - scaled) if m in ("BER", "Runtime_sec") else scaled

    labels = [("1/BER" if m == "BER" else "1/Runtime" if m == "Runtime_sec" else m) for m in metrics]
    n = len(labels)
    angles = np.linspace(0, 2 * np.pi, n, endpoint=False).tolist()
    angles += angles[:1]

    fig, ax = plt.subplots(figsize=(7, 7), subplot_kw=dict(polar=True))
    for env in norm.index:
        vals = norm.loc[env, metrics].tolist()
        vals += vals[:1]
        ax.plot(angles, vals, linewidth=1.5, label=str(env))
        ax.fill(angles, vals, alpha=0.08)
    ax.set_xticks(angles[:-1]); ax.set_xticklabels(labels)
    ax.set_yticklabels([])
    ax.set_title("Environment Communication Radar Chart\n(normalised, outer = better)")
    ax.legend(loc="upper right", bbox_to_anchor=(1.35, 1.1), fontsize=8)
    return _save(fig, "19_environment_radar_chart.png")


def _surface_plot(df, z_col, title, filename, log_z=False,
                   x_col="SNR_dB", y_col="Speed_kmh"):
    need = {x_col, y_col, z_col}
    if not need.issubset(df.columns):
        return _skip(title, f"missing columns {need}")

    d = df[[x_col, y_col, z_col]].dropna().astype(float)
    if d.empty:
        return _skip(title, "no data after dropna")

    # Bin y into ~8 buckets (speed/etc. is near-continuous in real datasets)
    y_bins = np.linspace(d[y_col].min(), d[y_col].max(), 9)
    d["_ybin"] = pd.cut(d[y_col], bins=y_bins, include_lowest=True)
    pivot = d.groupby([x_col, "_ybin"], observed=True)[z_col].mean().unstack()
    pivot = pivot.sort_index()
    if pivot.shape[0] < 2 or pivot.shape[1] < 2:
        return _skip(title, "not enough distinct x/y values for a surface")

    X = pivot.index.values.astype(float)
    Y = np.array([iv.mid for iv in pivot.columns])
    Xg, Yg = np.meshgrid(X, Y, indexing="ij")
    Z = pivot.values
    if log_z:
        Z = np.log10(np.clip(Z, 1e-8, None))

    fig = plt.figure(figsize=(8, 6.5))
    ax = fig.add_subplot(111, projection="3d")
    surf = ax.plot_surface(Xg, Yg, Z, cmap="viridis", edgecolor="none", antialiased=True)
    ax.set_xlabel(x_col); ax.set_ylabel(y_col)
    ax.set_zlabel(f"log10({z_col})" if log_z else z_col)
    ax.set_title(title)
    fig.colorbar(surf, ax=ax, shrink=0.6, pad=0.1)
    return _save(fig, filename)


def plot_ber_surface(df: pd.DataFrame):
    """Graph 20: BER surface over SNR x Speed."""
    return _surface_plot(df, "BER", "BER Surface Plot (SNR x Speed)",
                          "20_ber_surface_plot.png", log_z=True)


def plot_throughput_surface(df: pd.DataFrame):
    """Graph 21: Throughput surface over SNR x Speed."""
    return _surface_plot(df, "Throughput_bps", "Throughput Surface Plot (SNR x Speed)",
                          "21_throughput_surface_plot.png", log_z=False)


def plot_detector_decision_heatmap(df: pd.DataFrame):
    """Graph 22: which detector actually gives lowest BER, per
    Environment x SNR_dB grid (majority vote across rows in each cell)."""
    need = {"Environment", "SNR_dB", "Detector", "BER"}
    if not need.issubset(df.columns):
        return _skip("Detector Decision Heatmap", f"missing columns {need}")

    idx = df.groupby(["Environment", "SNR_dB"])["BER"].idxmin()
    best = df.loc[idx, ["Environment", "SNR_dB", "Detector"]]
    pivot = best.pivot(index="Environment", columns="SNR_dB", values="Detector")

    det_to_num = {d: i for i, d in enumerate(DETECTOR_LIST)}
    grid = pivot.apply(lambda col: col.map(lambda d: det_to_num.get(d, np.nan)))

    fig, ax = plt.subplots(figsize=(8, 5))
    im = ax.imshow(grid.values.astype(float), cmap="Set2", vmin=0, vmax=max(len(DETECTOR_LIST) - 1, 1))
    ax.set_xticks(range(len(grid.columns))); ax.set_xticklabels(grid.columns)
    ax.set_yticks(range(len(grid.index))); ax.set_yticklabels(grid.index)
    for i in range(grid.shape[0]):
        for j in range(grid.shape[1]):
            val = pivot.values[i, j]
            if pd.notna(val):
                ax.text(j, i, str(val), ha="center", va="center", fontsize=8)
    ax.set_xlabel("SNR (dB)"); ax.set_ylabel("Environment")
    ax.set_title("Detector Decision Heatmap (best detector by lowest BER)")
    return _save(fig, "22_detector_decision_heatmap.png")


# ---------------------------------------------------------------------------
# Section D -- novelty graphs
# ---------------------------------------------------------------------------
def plot_mic_confidence_vs_accuracy(confidence_log_df: pd.DataFrame):
    """Graph 23: scatter of microphone classification confidence vs the
    resulting prediction accuracy (1 - relative BER error) for that session.
    Expects columns: 'mic_confidence', 'ber_relative_error' (both in [0,1]),
    typically accumulated across repeated real-world runs -- see
    AI_Results/Reports/realworld_session_log.csv."""
    need = {"mic_confidence", "ber_relative_error"}
    if confidence_log_df is None or not need.issubset(confidence_log_df.columns) or confidence_log_df.empty:
        return _skip("Microphone Confidence vs Prediction Accuracy",
                     "no real-world session log yet (need repeated mic-mode runs)")

    d = confidence_log_df.dropna(subset=list(need))
    accuracy = 1 - np.clip(d["ber_relative_error"].astype(float).values, 0, 1)

    fig, ax = plt.subplots(figsize=(7, 5.5))
    ax.scatter(d["mic_confidence"].astype(float).values, accuracy, s=30, alpha=0.7, color="#C44E52")
    ax.set_xlabel("Microphone classification confidence")
    ax.set_ylabel("Prediction accuracy (1 - relative BER error)")
    ax.set_title("Microphone Confidence vs Prediction Accuracy")
    ax.set_xlim(0, 1); ax.set_ylim(0, 1)
    ax.grid(True, alpha=0.3)
    return _save(fig, "23_mic_confidence_vs_accuracy.png")


def plot_real_vs_simulated_environment(detected_env: dict, env_profile_row: pd.Series):
    """Graph 24: bar comparison of the mic-detected scenario's parameters vs
    the nominal MATLAB environment_profiles.csv row it was snapped to."""
    if not detected_env or env_profile_row is None:
        return _skip("Real Environment vs Simulated Environment", "no detected_environment.json / profile row")

    fields = ["speed_kmh", "doppler_scale"]
    real_vals = [detected_env.get("speed_kmh", np.nan), detected_env.get("doppler_scale", np.nan)]
    sim_vals = [
        (float(env_profile_row["SpeedMin"]) + float(env_profile_row["SpeedMax"])) / 2,
        float(env_profile_row["DopplerScale"]),
    ]

    x = np.arange(len(fields))
    fig, ax = plt.subplots(figsize=(6.5, 5))
    ax.bar(x - 0.18, real_vals, width=0.36, label="Real (mic-detected)", color="#4C72B0")
    ax.bar(x + 0.18, sim_vals, width=0.36, label="Simulated (MATLAB profile mid-point)", color="#DD8452")
    ax.set_xticks(x); ax.set_xticklabels(["Speed (km/h)", "Doppler scale"])
    ax.set_title(f"Real vs Simulated Environment -- {detected_env.get('environment', '?')}")
    ax.legend(); ax.grid(True, alpha=0.3, axis="y")
    return _save(fig, "24_real_vs_simulated_environment.png")


def plot_communication_decision_dashboard(predictions_df: pd.DataFrame):
    """Graph 25: composite 4-panel decision dashboard from a single
    predict.py output (forward or validation mode) -- Environment breakdown,
    Detector recommendation mix, Communication Quality mix, Confidence
    distribution. This is the single graph most useful to show a
    non-technical audience "what did the AI decide, and how sure was it"."""
    if predictions_df is None or predictions_df.empty:
        return _skip("Communication Decision Dashboard", "empty predictions frame")

    df = predictions_df.copy()
    if "Quality" not in df.columns and {"BER", "CQI", "Throughput_bps"}.issubset(df.columns):
        pred_cols = {"BER": "Predicted_BER" if "Predicted_BER" in df.columns else "BER",
                     "CQI": "Predicted_CQI" if "Predicted_CQI" in df.columns else "CQI",
                     "Throughput_bps": "Predicted_Throughput_bps" if "Predicted_Throughput_bps" in df.columns else "Throughput_bps"}
        df["Quality"] = classify_quality_frame(
            df, ber_col=pred_cols["BER"], cqi_col=pred_cols["CQI"], throughput_col=pred_cols["Throughput_bps"])

    fig, axes = plt.subplots(2, 2, figsize=(12, 10))

    # Panel 1: Environment mix
    if "Environment" in df.columns:
        counts = df["Environment"].value_counts()
        axes[0, 0].bar(counts.index.astype(str), counts.values, color="#4C72B0", edgecolor="black")
        axes[0, 0].set_title("Environment"); axes[0, 0].tick_params(axis="x", rotation=25)
    else:
        axes[0, 0].axis("off")

    # Panel 2: Detector recommendation mix
    det_col = "Detector" if "Detector" in df.columns else (
        "Recommended_Detector" if "Recommended_Detector" in df.columns else None)
    if det_col:
        counts = df[det_col].value_counts()
        axes[0, 1].bar(counts.index.astype(str), counts.values, color="#55A868", edgecolor="black")
        axes[0, 1].set_title("Recommended Detector")
    else:
        axes[0, 1].axis("off")

    # Panel 3: Communication Quality mix
    if "Quality" in df.columns:
        order = [q for q in QUALITY_ORDER if q in df["Quality"].unique()]
        counts = df["Quality"].value_counts().reindex(order)
        colors = {"Excellent": "#2ca02c", "Good": "#8fbc8f", "Moderate": "#e6b800", "Poor": "#d62728"}
        axes[1, 0].bar(counts.index.astype(str), counts.values,
                        color=[colors.get(q, "#888") for q in counts.index], edgecolor="black")
        axes[1, 0].set_title("Communication Quality")
    else:
        axes[1, 0].axis("off")

    # Panel 4: Confidence distribution
    conf_col = "Recommendation_Confidence" if "Recommendation_Confidence" in df.columns else None
    if conf_col:
        axes[1, 1].hist(df[conf_col].astype(float).values, bins=20, color="#8172B2", edgecolor="black")
        axes[1, 1].set_title("Detector Recommendation Confidence")
        axes[1, 1].set_xlim(0, 1)
    else:
        axes[1, 1].axis("off")

    fig.suptitle("Communication Decision Dashboard", fontsize=15)
    fig.tight_layout(rect=[0, 0, 1, 0.96])
    return _save(fig, "25_communication_decision_dashboard.png")
