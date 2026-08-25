"""
train_model.py
===============
Phase-2 "Machine Learning Training" module.

Trains two families of models straight off MATLAB's Results/OTFS_Dataset.csv:

  1. Metric regressors  -- one RandomForestRegressor per target in
     config.METRIC_TARGETS (BER, SER, PER, Throughput_bps,
     SpectralEfficiency_bps_per_Hz, CQI), predicting from scenario +
     detector features (config.FEATURE_COLS_METRIC). BER/SER/PER are
     trained in log10 space since they span many orders of magnitude.

  2. Detector recommendation classifier -- a RandomForestClassifier that,
     for a given scenario (NOT knowing the detector yet), predicts which
     detector in config.DETECTOR_LIST will give the lowest BER (tie-broken
     by lower PER, then lower Runtime_sec). Trained on scenario features
     only (config.FEATURE_COLS_DETECTOR).

Usage:
    python train_model.py [--input Results/OTFS_Dataset.csv]

Outputs (under models/):
    metric_regressor_<Target>.joblib   x len(METRIC_TARGETS)
    detector_classifier.joblib
    feature_metadata.json              (column lists + label categories, for predict.py)
"""

import argparse
import json
import os
import sys

import numpy as np
import pandas as pd
import joblib

from sklearn.compose import ColumnTransformer
from sklearn.ensemble import (RandomForestRegressor, RandomForestClassifier,
                               GradientBoostingRegressor)
from sklearn.tree import DecisionTreeRegressor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.compose import TransformedTargetRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import (r2_score, mean_absolute_error, mean_squared_error,
                              explained_variance_score, mean_absolute_percentage_error,
                              accuracy_score, f1_score, classification_report)

from config import (
    DATASET_FILE, CATEGORICAL_COLS, NUMERIC_SCENARIO_COLS,
    FEATURE_COLS_METRIC, FEATURE_COLS_DETECTOR, METRIC_TARGETS,
    LOG_SCALE_TARGETS, LOG_FLOOR, DETECTOR_MODEL_FILE, METRIC_MODEL_FILE,
    FEATURE_META_FILE, RANDOM_STATE, REGRESSOR_CANDIDATES, MODEL_COMPARISON_FILE,
)
from dataset_report import analyze_and_report
import graphs


def _log10_transform(v):
    return np.log10(np.clip(v, LOG_FLOOR, None))


def _inverse_log10_transform(v):
    return 10 ** v


def _build_preprocessor(categorical_cols, numeric_cols):
    return ColumnTransformer(
        transformers=[
            ("cat", OneHotEncoder(handle_unknown="ignore"), categorical_cols),
            ("num", StandardScaler(), numeric_cols),
        ]
    )


def _build_candidate(name: str):
    """One of the three algorithms requested in the spec (Random Forest /
    Gradient Boosting / Decision Tree), all wrapped identically so they're
    drop-in interchangeable inside the same preprocessing pipeline."""
    if name == "RandomForest":
        return RandomForestRegressor(n_estimators=300, max_depth=None,
                                      n_jobs=-1, random_state=RANDOM_STATE)
    if name == "GradientBoosting":
        return GradientBoostingRegressor(n_estimators=300, max_depth=3,
                                          learning_rate=0.05, random_state=RANDOM_STATE)
    if name == "DecisionTree":
        return DecisionTreeRegressor(max_depth=None, random_state=RANDOM_STATE)
    raise ValueError(f"Unknown regressor candidate: {name}")


def train_metric_regressors(df: pd.DataFrame) -> dict:
    """Trains RandomForest / GradientBoosting / DecisionTree for every
    target in METRIC_TARGETS, compares them on MAE / RMSE / R2 / Explained
    Variance / MAPE, keeps the best one per target, and writes
    AI_Results/Reports/model_comparison.csv with every candidate's scores
    (so you can see *why* a model won, not just which one did)."""
    print("\n=== Training & comparing metric regressors "
          f"({', '.join(REGRESSOR_CANDIDATES)}) ===")
    cat_cols = [c for c in CATEGORICAL_COLS + ["Detector"] if c in FEATURE_COLS_METRIC]
    num_cols = [c for c in NUMERIC_SCENARIO_COLS if c in FEATURE_COLS_METRIC]

    metrics_summary = {}
    comparison_rows = []
    X = df[FEATURE_COLS_METRIC]

    for target in METRIC_TARGETS:
        if target not in df.columns:
            print(f"  [skip] '{target}' not present in dataset.")
            continue

        y = df[target].astype(float).values
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=RANDOM_STATE)

        best_candidate = None
        best_model = None
        best_pipe = None  # the raw fitted pipeline (for feature importance)
        best_score = None  # higher R2 is better

        print(f"\n  -- {target} --")
        for cand_name in REGRESSOR_CANDIDATES:
            base_model = _build_candidate(cand_name)
            preprocessor = _build_preprocessor(cat_cols, num_cols)
            pipe = Pipeline([("prep", preprocessor), ("model", base_model)])

            if target in LOG_SCALE_TARGETS:
                model = TransformedTargetRegressor(
                    regressor=pipe, func=_log10_transform, inverse_func=_inverse_log10_transform)
            else:
                model = pipe

            model.fit(X_train, y_train)
            y_pred = model.predict(X_test)

            r2 = r2_score(y_test, y_pred)
            mae = mean_absolute_error(y_test, y_pred)
            rmse = float(np.sqrt(mean_squared_error(y_test, y_pred)))
            evs = explained_variance_score(y_test, y_pred)
            try:
                mape = mean_absolute_percentage_error(
                    np.clip(y_test, LOG_FLOOR, None), np.clip(y_pred, LOG_FLOOR, None))
            except Exception:
                mape = float("nan")

            print(f"    {cand_name:<18s} R2={r2:6.3f}  MAE={mae:.4g}  RMSE={rmse:.4g}  "
                  f"ExplVar={evs:6.3f}  MAPE={mape*100:.1f}%")

            comparison_rows.append({
                "Target": target, "Model": cand_name, "R2": r2, "MAE": mae,
                "RMSE": rmse, "ExplainedVariance": evs, "MAPE_pct": mape * 100,
                "n_test": len(y_test), "Selected": False,
            })

            if best_score is None or r2 > best_score:
                best_score = r2
                best_candidate = cand_name
                best_model = model
                # TransformedTargetRegressor.fit() clones `pipe` internally and
                # fits the clone (stored as .regressor_) -- the original `pipe`
                # object is left unfitted. Grab the *actually fitted* pipeline
                # so feature_importances_ below reflects the trained model.
                best_pipe = model.regressor_ if hasattr(model, "regressor_") else pipe

        for row in comparison_rows:
            if row["Target"] == target and row["Model"] == best_candidate:
                row["Selected"] = True

        y_pred_best = best_model.predict(X_test)
        metrics_summary[target] = {
            "best_model": best_candidate,
            "r2": r2_score(y_test, y_pred_best),
            "mae": mean_absolute_error(y_test, y_pred_best),
            "n_test": len(y_test),
        }
        print(f"  -> best for {target}: {best_candidate} (R2={best_score:.3f})")

        out_path = METRIC_MODEL_FILE.format(target=target)
        joblib.dump(best_model, out_path)

        # Feature importance graph for the winning model (tree-based models only)
        fitted_tree_model = best_pipe.named_steps["model"]
        if hasattr(fitted_tree_model, "feature_importances_"):
            feature_names = best_pipe.named_steps["prep"].get_feature_names_out()
            graphs.plot_feature_importance(fitted_tree_model, feature_names, target)

    comparison_df = pd.DataFrame(comparison_rows)
    comparison_df.to_csv(MODEL_COMPARISON_FILE, index=False)
    print(f"\nModel comparison table written -> {MODEL_COMPARISON_FILE}")

    return metrics_summary


def compute_best_detector_table(df: pd.DataFrame) -> pd.DataFrame:
    """For each unique scenario+modulation+SNR combo, pick the detector with
    the lowest BER (tie-break: lower PER, then lower Runtime_sec)."""
    group_cols = ["Environment", "Speed_kmh", "DelayProfile", "Modulation",
                  "SNR_dB", "ScenarioID"]
    group_cols = [c for c in group_cols if c in df.columns]

    sort_cols = [c for c in ["BER", "PER", "Runtime_sec"] if c in df.columns]
    df_sorted = df.sort_values(sort_cols)
    best = df_sorted.groupby(group_cols, as_index=False).first()
    return best


def train_detector_classifier(df: pd.DataFrame) -> dict:
    print("\n=== Training detector recommendation classifier ===")
    best = compute_best_detector_table(df)

    cat_cols = [c for c in CATEGORICAL_COLS if c in FEATURE_COLS_DETECTOR]
    num_cols = [c for c in NUMERIC_SCENARIO_COLS if c in FEATURE_COLS_DETECTOR]

    X = best[FEATURE_COLS_DETECTOR]
    y = best["Detector"].astype(str).values

    if len(set(y)) < 2:
        print("  [skip] Only one detector present in dataset -- nothing to classify between.")
        return {}

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=RANDOM_STATE, stratify=y)

    preprocessor = _build_preprocessor(cat_cols, num_cols)
    clf = RandomForestClassifier(n_estimators=300, n_jobs=-1, random_state=RANDOM_STATE)
    pipe = Pipeline([("prep", preprocessor), ("model", clf)])
    pipe.fit(X_train, y_train)

    y_pred = pipe.predict(X_test)
    acc = accuracy_score(y_test, y_pred)
    f1 = f1_score(y_test, y_pred, average="macro")

    print(f"  Accuracy={acc:.3f}  Macro-F1={f1:.3f}  (n_test={len(y_test)})")
    print(classification_report(y_test, y_pred, zero_division=0))

    joblib.dump(pipe, DETECTOR_MODEL_FILE)
    return {"accuracy": acc, "macro_f1": f1, "n_test": len(y_test)}


def main(input_path: str):
    print(f"Loading dataset: {input_path}")
    try:
        df = pd.read_csv(input_path)
    except FileNotFoundError:
        print(f"ERROR: {input_path} not found. Run the MATLAB Phase-1 script first "
              f"(or point --input at your OTFS_Dataset.csv).", file=sys.stderr)
        sys.exit(1)

    missing = [c for c in set(FEATURE_COLS_METRIC + FEATURE_COLS_DETECTOR + METRIC_TARGETS)
               if c not in df.columns]
    if missing:
        print(f"ERROR: dataset is missing expected column(s): {missing}", file=sys.stderr)
        sys.exit(1)

    # Steps 2-4: dataset analysis, dataset_report.txt, distribution graphs
    dataset_info = analyze_and_report(df)

    metric_summary = train_metric_regressors(df)
    detector_summary = train_detector_classifier(df)

    # Section C advanced graphs (dataset-level, don't need a trained model)
    print("\n=== Generating advanced (Section C) graphs ===")
    graphs.plot_environment_radar(df)
    graphs.plot_ber_surface(df)
    graphs.plot_throughput_surface(df)
    graphs.plot_detector_decision_heatmap(df)

    meta = {
        "feature_cols_metric": FEATURE_COLS_METRIC,
        "feature_cols_detector": FEATURE_COLS_DETECTOR,
        "metric_targets": METRIC_TARGETS,
        "log_scale_targets": LOG_SCALE_TARGETS,
        "regressor_candidates": REGRESSOR_CANDIDATES,
        "metric_eval": metric_summary,
        "detector_eval": detector_summary,
        "dataset_rows": dataset_info["rows"],
        "dataset_missing_values": dataset_info["missing_values"],
        "dataset_duplicate_rows": dataset_info["duplicate_rows"],
        "trained_rows": len(df),
    }
    with open(FEATURE_META_FILE, "w") as f:
        json.dump(meta, f, indent=2)

    print(f"\nTraining complete.")
    print(f"  Models              -> models/")
    print(f"  Dataset report      -> {os.path.join('AI_Results', 'Reports', 'dataset_report.txt')}")
    print(f"  Model comparison    -> {MODEL_COMPARISON_FILE}")
    print(f"  Graphs              -> {os.path.join('AI_Results', 'Graphs')}/")
    print(f"  Metadata            -> {FEATURE_META_FILE}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Train Phase-2 OTFS metric + detector-recommendation models.")
    ap.add_argument("--input", type=str, default=DATASET_FILE,
                     help="Path to OTFS_Dataset.csv (default: Results/OTFS_Dataset.csv)")
    args = ap.parse_args()
    main(args.input)
