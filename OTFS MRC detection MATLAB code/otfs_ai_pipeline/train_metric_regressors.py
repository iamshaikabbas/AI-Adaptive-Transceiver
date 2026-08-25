"""
train_metric_regressors.py
==========================
Trains the AI PERFORMANCE-PREDICTION layer (spec section 11/12): given a
channel condition + candidate (waveform, detector), predict

    log10(BER), Throughput_bps, CQI

from REAL paired-trial simulation data (Results/WaveformComparison/
waveform_dataset.csv, 9720 rows). One model per target with Waveform and
Detector as categorical features -- so OTFS-MRC, ODDM-LMMSE, ODDM-MMSETAP,
OFDM-*, ... are all served by shared statistical strength.

Derived quantities used downstream (NOT regressed):
    SpectralEfficiency = Throughput_bps / BW          (analytic)
    PER_hat            = 1-(1-BER)^N_bits             (independent-bit model)
    Latency_ms         = per-(Waveform,Detector) training median (lookup)

Holdout is GROUP-AWARE (whole CondIDs unseen). Models are compared
(RandomForest / GradientBoosting / DecisionTree) and scored with
MAE / RMSE / R^2 per target -> also rendered as the required
predicted-vs-actual graphs (#19-21).

Outputs:
    models/metric_reg_Log10BER.joblib | _Throughput.joblib | _CQI.joblib
    models/metric_regressors_meta.json
    AI_Results/Reports/metric_regressor_report.txt (+ .csv)
    AI_Results/Graphs/pred_vs_actual_{Log10BER,Throughput,CQI}.png
"""

import json
import os

import joblib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import GroupShuffleSplit
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder
from sklearn.tree import DecisionTreeRegressor

from train_waveform_selector import RANDOM_STATE

HERE = os.path.dirname(os.path.abspath(__file__))
DATASET_FILE = os.path.join(HERE, "..", "Results", "WaveformComparison",
                            "waveform_dataset.csv")
MODELS_DIR = os.path.join(HERE, "models")
REPORTS_DIR = os.path.join(HERE, "AI_Results", "Reports")
GRAPHS_DIR = os.path.join(HERE, "AI_Results", "Graphs")
for d in (MODELS_DIR, REPORTS_DIR, GRAPHS_DIR):
    os.makedirs(d, exist_ok=True)

TARGETS = {
    "Log10BER": ("log10_ber", True),
    "Throughput": ("Throughput_bps", False),
    "CQI": ("CQI", False),
}
CATEGORICAL = ["Environment", "DelayProfile", "Waveform", "Detector"]
NUMERIC = ["Speed_kmh", "DelaySpread", "NumPaths", "DopplerSpread",
           "Modulation", "SNR_dB"]


def build_frame(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["log10_ber"] = np.log10(np.clip(df.BER, 1e-9, None))
    return df


def make_pre():
    return [("cat", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL),
            ("num", "passthrough", NUMERIC)]


def main():
    df = pd.read_csv(DATASET_FILE)
    print(f"Loaded {len(df)} simulation rows")
    df = build_frame(df)
    feats = [c for c in df.columns if c not in
             ("log10_ber",) and c in ("Environment", "Speed_kmh",
                                      "DelayProfile", "DelaySpread",
                                      "NumPaths", "DopplerSpread",
                                      "Modulation", "SNR_dB", "Waveform",
                                      "Detector")]
    X = df[feats]
    groups = df.CondID.to_numpy()

    splitter = GroupShuffleSplit(n_splits=1, test_size=0.25,
                                 random_state=RANDOM_STATE)
    tr, te = next(splitter.split(X, groups=groups))
    X_tr, X_te = X.iloc[tr], X.iloc[te]
    y_tr_all, y_te_all = df.iloc[tr], df.iloc[te]

    candidates = {
        "RandomForest": lambda: RandomForestRegressor(
            n_estimators=250, random_state=RANDOM_STATE, n_jobs=-1),
        "GradientBoosting": GradientBoostingRegressor,
        "DecisionTree": DecisionTreeRegressor,
    }
    # sklearn constructors need instances; normalize callables
    def make(name):
        if name == "RandomForest":
            return RandomForestRegressor(n_estimators=250,
                                         random_state=RANDOM_STATE, n_jobs=-1)
        if name == "GradientBoosting":
            return GradientBoostingRegressor(random_state=RANDOM_STATE)
        return DecisionTreeRegressor(random_state=RANDOM_STATE)

    report_rows, fitted_best, pred_test = [], {}, {}
    for tgt, (col, _) in TARGETS.items():
        y_tr = y_tr_all[col].to_numpy()
        y_te = y_te_all[col].to_numpy()
        best = None
        for name in candidates:
            pipe = Pipeline([("pre", ColumnTransformerLike(make_pre())),
                             ("reg", make(name))])
            pipe.fit(X_tr, y_tr)
            p = pipe.predict(X_te)
            mae = mean_absolute_error(y_te, p)
            rmse = float(np.sqrt(mean_squared_error(y_te, p)))
            r2 = r2_score(y_te, p)
            report_rows.append({"Target": tgt, "Model": name, "MAE": mae,
                                "RMSE": rmse, "R2": r2})
            print(f"{tgt:11s} {name:16s} MAE={mae:.4f} RMSE={rmse:.4f} "
                  f"R2={r2:.4f}")
            if best is None or r2 > best[0]:
                best = (r2, name, pipe, p)
        fitted_best[tgt] = best
        pred_test[tgt] = best[3]

    comp = pd.DataFrame(report_rows)
    comp.to_csv(os.path.join(REPORTS_DIR, "metric_regressor_comparison.csv"),
                index=False)

    # ---- persist best models + meta ---------------------------------------
    lat_med = (df.groupby(["Waveform", "Detector"])["Runtime_sec"]
                 .median().reset_index()
                 .rename(columns={"Runtime_sec": "runtime_median_s"}))
    meta = {
        "targets": {t: {"model": f"metric_reg_{t}.joblib",
                        "best_model": fitted_best[t][1],
                        "test_R2": fitted_best[t][0],
                        "column": TARGETS[t][0]}
                    for t in TARGETS},
        "features": feats,
        "categorical": CATEGORICAL,
        "group_split": "GroupShuffleSplit by CondID, test=0.25",
        "random_state": RANDOM_STATE,
        "runtime_table_s": lat_med.to_dict(orient="records"),
        "derived": {
            "SpectralEfficiency": "Throughput_bps / BW",
            "PER_hat": "1 - (1 - 10**Log10BER)**N_bits",
            "Latency_ms": "median lookup by (Waveform,Detector)",
        },
    }
    for t in TARGETS:
        joblib.dump(fitted_best[t][2],
                    os.path.join(MODELS_DIR, f"metric_reg_{t}.joblib"))
    with open(os.path.join(MODELS_DIR, "metric_regressors_meta.json"),
              "w") as fh:
        json.dump(meta, fh, indent=2)

    # ---- report ------------------------------------------------------------
    lines = ["METRIC REGRESSOR TRAINING REPORT", "=" * 60,
             f"rows={len(df)}  train={len(tr)}  test={len(te)} "
             f"(unseen CondIDs)", "",
             comp.pivot(index="Model", columns="Target",
                        values="R2").to_string(),
             "", "best:",]
    for t in TARGETS:
        lines.append(f"  {t:11s} -> {fitted_best[t][1]} "
                     f"(R2={fitted_best[t][0]:.4f})")
    with open(os.path.join(REPORTS_DIR, "metric_regressor_report.txt"),
              "w") as fh:
        fh.write("\n".join(lines))
    print("\n".join(lines))

    # ---- required graphs #19-21 -------------------------------------------
    labels = {"Log10BER": ("Predicted vs Actual log10(BER)", "log10(BER)"),
              "Throughput": ("Predicted vs Actual Throughput [kbps]",
                             "Throughput [kbps]"),
              "CQI": ("Predicted vs Actual CQI", "CQI")}
    for t in TARGETS:
        yt = y_te_all[TARGETS[t][0]].to_numpy()
        yp = pred_test[t]
        fig, ax = plt.subplots(figsize=(4.6, 4.6))
        ax.scatter(yt, yp, s=8, alpha=.5, color="steelblue")
        lim = [min(yt.min(), yp.min()), max(yt.max(), yp.max())]
        ax.plot(lim, lim, "k--", lw=1)
        r2 = r2_score(yt, yp)
        mae = mean_absolute_error(yt, yp)
        ax.set_xlabel("actual"); ax.set_ylabel("predicted")
        ax.set_title(f"{labels[t][0]}\nR2={r2:.3f}  MAE={mae:.3f}")
        fig.tight_layout()
        fig.savefig(os.path.join(GRAPHS_DIR, f"pred_vs_actual_{t}.png"),
                    dpi=150)
        plt.close(fig)


def ColumnTransformerLike(spec):
    """Small wrapper so the pipeline stays a single object without importing
    ColumnTransformer at module top (keeps parity with other scripts)."""
    from sklearn.compose import ColumnTransformer
    return ColumnTransformer(spec)


if __name__ == "__main__":
    main()
