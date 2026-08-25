"""train_metric_regressors_v2.py -- Phase 3 / section 2.

Retrains the AI PERFORMANCE-PREDICTION chain on the EXPANDED Phase-2
dataset (phase2_dataset.csv: 579 conditions x {OTFS, ODDM} x 3 paired
trials, aggregated metrics). One regressor per target:

    Log10BER, Throughput_bps, CQI, ACS, PER, SpectralEfficiency

Features are exactly the Digital-Twin state available at decision time
(environment/speed/SNR/Doppler/carrier/BW/profile/delays/paths/modulation)
plus the candidate waveform. Latency is NOT regressed -- it uses the
per-waveform training-median lookup (same derived convention as v1).

NO synthetic rows are created. Evaluation uses the dataset's own
condition-level split column (train / val / test); test axis values were
UNSEEN by construction (Phase 2 lattice design).

Models compared per target: RandomForest / GradientBoosting / DecisionTree.
Selection by validation R^2; val+test MAE/RMSE/R^2 reported.

Outputs (v1 models under models/ are PRESERVED untouched):
    models/metric_models_v2/metric_reg_v2_<target>.joblib
    models/metric_models_v2/metric_models_v2_meta.json
    AI_Results/Reports/metric_regressor_v2_report.md
"""

import json
import os

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import (GradientBoostingRegressor,
                              RandomForestRegressor)
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder
from sklearn.tree import DecisionTreeRegressor

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
DATASET = os.path.join(ROOT, "Results", "WaveformComparison",
                       "phase2_dataset.csv")
MODELS_DIR = os.path.join(HERE, "models", "metric_models_v2")
REPORTS_DIR = os.path.join(HERE, "AI_Results", "Reports")
os.makedirs(MODELS_DIR, exist_ok=True)
os.makedirs(REPORTS_DIR, exist_ok=True)

RANDOM_STATE = 42

FEATURES_NUM = ["speed_kmph", "snr_db", "doppler_hz", "carrier_frequency_hz",
                "bandwidth_hz", "delay_spread_taps", "num_paths",
                "doppler_spread_hz", "modulation"]
FEATURES_CAT = ["environment", "channel_profile", "waveform"]
FEATURES = FEATURES_CAT + FEATURES_NUM

TARGET_COLS = {
    "Log10BER": ("log10_ber", None),
    "Throughput": ("throughput_bps", None),
    "CQI": ("CQI", None),
    "ACS": ("ACS", None),
    "PER": ("PER", None),
    "SE": ("spectral_efficiency", None),
}


def main():
    df = pd.read_csv(DATASET)
    print(f"Loaded {len(df)} rows ({df.scenario_id.nunique()} conditions)")
    df["log10_ber"] = np.log10(df.BER.clip(lower=1e-12))

    X = df[FEATURES]
    tr = (df.split == "train").to_numpy()
    va = (df.split == "val").to_numpy()
    te = (df.split == "test").to_numpy()

    def pre():
        return ColumnTransformer(
            [("cat", OneHotEncoder(handle_unknown="ignore"), FEATURES_CAT),
             ("num", "passthrough", FEATURES_NUM)])

    candidates = {
        "RandomForest": lambda: RandomForestRegressor(
            n_estimators=300, random_state=RANDOM_STATE, n_jobs=-1),
        "GradientBoosting": lambda: GradientBoostingRegressor(
            n_estimators=300, learning_rate=0.05, max_depth=3,
            random_state=RANDOM_STATE),
        "DecisionTree": lambda: DecisionTreeRegressor(random_state=RANDOM_STATE),
    }

    rows = []
    best_models = {}
    for tgt, (col, _) in TARGET_COLS.items():
        y = df[col].to_numpy()
        best = None
        for name, ctor in candidates.items():
            pipe = Pipeline([("pre", pre()), ("reg", ctor())])
            pipe.fit(X[tr], y[tr])
            pv = pipe.predict(X[va])
            r2v = r2_score(y[va], pv)
            rows.append({"target": tgt, "model": name,
                         "val_MAE": mean_absolute_error(y[va], pv),
                         "val_RMSE": float(np.sqrt(
                             mean_squared_error(y[va], pv))),
                         "val_R2": r2v})
            if best is None or r2v > best["val_R2"]:
                pt = pipe.predict(X[te])
                best = {"model_name": name, "pipeline": pipe,
                        "val_R2": r2v,
                        "test_MAE": mean_absolute_error(y[te], pt),
                        "test_RMSE": float(np.sqrt(
                            mean_squared_error(y[te], pt))),
                        "test_R2": r2_score(y[te], pt)}
        best_models[tgt] = best
        rows.append({"target": tgt, "model": f"*BEST:{best['model_name']}*",
                     "val_MAE": "", "val_RMSE": "",
                     "val_R2": best["val_R2"]})
        print(f"{tgt:11s} -> {best['model_name']:16s} "
              f"valR2={best['val_R2']:.3f} testR2={best['test_R2']:.3f} "
              f"testMAE={best['test_MAE']:.4g}")

    comp = pd.DataFrame(rows)
    comp.to_csv(os.path.join(REPORTS_DIR,
                             "metric_regressor_v2_comparison.csv"),
                index=False)

    # latency lookup (training medians by waveform)
    lat = (df.groupby("waveform")["latency_ms"].median()
             .reset_index()
             .rename(columns={"latency_ms": "latency_median_ms"}))

    meta = {
        "version": "metric-models-v2 (phase 3)",
        "trained_from": os.path.relpath(DATASET, ROOT),
        "n_rows": int(len(df)),
        "features_cat": FEATURES_CAT,
        "features_num": FEATURES_NUM,
        "split_rule": ("dataset split column (train/val/test); test axis "
                       "values unseen by construction"),
        "random_state": RANDOM_STATE,
        "targets": {t: {"file": f"metric_reg_v2_{t}.joblib",
                        "column": TARGET_COLS[t][0],
                        "best_model": best_models[t]["model_name"],
                        "val_R2": best_models[t]["val_R2"],
                        "test_R2": best_models[t]["test_R2"],
                        "test_MAE": best_models[t]["test_MAE"],
                        "test_RMSE": best_models[t]["test_RMSE"]}
                    for t in TARGET_COLS},
        "latency_lookup_ms": lat.to_dict(orient="records"),
        "derived_note": ("Latency not regressed: per-waveform training "
                         "median (v1 convention). SpectralEfficiency and "
                         "PER regressed directly from measured columns."),
    }
    for t, b in best_models.items():
        joblib.dump(b["pipeline"],
                    os.path.join(MODELS_DIR, f"metric_reg_v2_{t}.joblib"))
    with open(os.path.join(MODELS_DIR, "metric_models_v2_meta.json"),
              "w") as fh:
        json.dump(meta, fh, indent=2)

    lines = ["# Metric regressors v2 - training report", "",
             f"Data: {len(df)} rows / {df.scenario_id.nunique()} conditions "
             "(Phase-2 paired dataset, no synthetic rows).",
             "Split: train/val/test by condition (unseen-axis test).", "",
             "| target | model | val R2 | test R2 | test MAE | test RMSE |",
             "|---|---|---|---|---|---|"]
    for t, b in best_models.items():
        lines.append(f"| {t} | {b['model_name']} | {b['val_R2']:.3f} | "
                     f"{b['test_R2']:.3f} | {b['test_MAE']:.4g} | "
                     f"{b['test_RMSE']:.4g} |")
    with open(os.path.join(REPORTS_DIR,
                           "metric_regressor_v2_report.md"), "w") as fh:
        fh.write("\n".join(lines) + "\n")
    print("\nsaved -> models/metric_models_v2/ + report")


if __name__ == "__main__":
    main()
