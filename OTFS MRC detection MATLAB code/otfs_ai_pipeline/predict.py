"""
predict.py
==========
Phase-2 "AI Communication Prediction" + "Detector Recommendation" +
"Prediction Evaluation" module.

Two modes:

  A) FORWARD prediction (no --input, or --input is a fresh scenario, not a
     results table): reads detected_environment.json (from
     parameter_mapper.py) -- or explicit --environment/--speed/--delay_profile/
     --doppler_scale flags -- sweeps modulation x SNR, recommends the best
     detector for each combo, predicts its metrics, and writes:
        AI_Results/AI_Predictions_<timestamp>.csv
        AI_Results/ai_recommended_scenarios.json   <- feed this back into
                                                       MATLAB for ground-truth
                                                       validation (Phase-2's
                                                       "MATLAB OTFS Validation" step)

  B) VALIDATION mode (--input points at an actual MATLAB results CSV with
     the full OTFS_Dataset schema, e.g. the fresh run MATLAB just produced
     for the recommended scenarios): for every row, predicts what the model
     WOULD have said (metrics for the actual detector used, and which
     detector it would have recommended for that scenario), compares to the
     real simulated values, and writes:
        AI_Results/predictions_vs_actual.csv
     printing MAE/RMSE per metric and detector-recommendation accuracy.
     dashboard.py consumes this file next.

Called by MATLAB's Module 6 as:  python predict.py --input <temp_csv>
(MATLAB always has an actual results table at that point, so it lands in mode B).
"""

import argparse
import json
import os
import sys
from datetime import datetime

import numpy as np
import pandas as pd
import joblib

from config import (
    AI_RESULTS_DIR, DATASET_FILE, DETECTED_ENV_FILE, DETECTOR_MODEL_FILE,
    METRIC_MODEL_FILE, FEATURE_META_FILE, METRIC_TARGETS, DETECTOR_LIST,
    MOD_NAMES, SNR_SWEEP, ALL_COLUMNS,
)
# train_model defines the named (picklable) log10 transform functions that
# the saved TransformedTargetRegressor models reference -- importing them
# here (even unused directly) makes them resolvable at unpickle time.
from train_model import _log10_transform, _inverse_log10_transform  # noqa: F401
from communication_quality import classify_quality_frame, build_throughput_reference
import graphs
import dashboard


def _require_models():
    if not os.path.exists(DETECTOR_MODEL_FILE) or not os.path.exists(FEATURE_META_FILE):
        print("ERROR: no trained models found. Run train_model.py first "
              "(needs Results/OTFS_Dataset.csv from the MATLAB script).", file=sys.stderr)
        sys.exit(1)


def _load_metric_models():
    models = {}
    for target in METRIC_TARGETS:
        path = METRIC_MODEL_FILE.format(target=target)
        if os.path.exists(path):
            models[target] = joblib.load(path)
    return models


def recommend_detector(clf, scenario_df: pd.DataFrame) -> pd.DataFrame:
    """scenario_df has one row per scenario (no Detector column yet)."""
    preds = clf.predict(scenario_df)
    proba = clf.predict_proba(scenario_df)
    confidence = proba.max(axis=1)
    out = scenario_df.copy()
    out["Recommended_Detector"] = preds
    out["Recommendation_Confidence"] = confidence
    return out


def predict_metrics(metric_models: dict, rows_with_detector: pd.DataFrame) -> pd.DataFrame:
    out = rows_with_detector.copy()
    for target, model in metric_models.items():
        out[f"Predicted_{target}"] = model.predict(rows_with_detector)
    return out


def _load_metric_r2() -> dict:
    """Per-target held-out R2 of the winning model, from train_model.py's
    feature_metadata.json. Used as a simple, model-level 'how much should I
    trust this metric's predictions' confidence score (same value for every
    row of that metric -- not row-level, but cheap, honest, and always
    available for every model type, unlike tree-variance estimates)."""
    if not os.path.exists(FEATURE_META_FILE):
        return {}
    with open(FEATURE_META_FILE) as f:
        meta = json.load(f)
    return {t: float(np.clip(v.get("r2", 0.0), 0.0, 1.0))
            for t, v in meta.get("metric_eval", {}).items()}


def attach_quality_and_confidence(df: pd.DataFrame, metric_models: dict,
                                   throughput_ref: dict = None) -> pd.DataFrame:
    """Adds a 'Quality' column (Excellent/Good/Moderate/Poor, from
    Predicted_ metrics where available, else raw metrics) and a
    'Metric_Confidence' column (mean held-out R2 across whichever metrics
    were actually predicted for these rows)."""
    out = df.copy()

    ber_col = "Predicted_BER" if "Predicted_BER" in out.columns else "BER"
    cqi_col = "Predicted_CQI" if "Predicted_CQI" in out.columns else "CQI"
    thr_col = "Predicted_Throughput_bps" if "Predicted_Throughput_bps" in out.columns else "Throughput_bps"

    if {ber_col, cqi_col, thr_col}.issubset(out.columns):
        out["Quality"] = classify_quality_frame(
            out, ber_col=ber_col, cqi_col=cqi_col, throughput_col=thr_col,
            throughput_ref=throughput_ref)

    r2_by_target = _load_metric_r2()
    used_r2 = [r2_by_target[t] for t in metric_models if t in r2_by_target]
    out["Metric_Confidence"] = float(np.mean(used_r2)) if used_r2 else np.nan

    return out


# ---------------------------------------------------------------------------
# Mode A: forward prediction for a new scenario
# ---------------------------------------------------------------------------
def run_forward_mode(environment, speed_kmh, delay_profile, doppler_scale,
                      delay_spread, num_paths, category):
    _require_models()
    clf = joblib.load(DETECTOR_MODEL_FILE)
    metric_models = _load_metric_models()

    combos = []
    for mod in MOD_NAMES:
        for snr in SNR_SWEEP:
            combos.append({
                "Environment": environment, "Speed_kmh": speed_kmh,
                "DelayProfile": delay_profile, "DelaySpread": delay_spread,
                "NumPaths": num_paths, "DopplerSpread": doppler_scale,
                "Modulation": mod, "SNR_dB": snr, "Category": category,
            })
    scenario_df = pd.DataFrame(combos)

    recommended = recommend_detector(clf, scenario_df)
    recommended = recommended.rename(columns={"Recommended_Detector": "Detector"})
    predicted = predict_metrics(metric_models, recommended)

    throughput_ref = None
    if os.path.exists(DATASET_FILE):
        try:
            throughput_ref = build_throughput_reference(pd.read_csv(DATASET_FILE))
        except Exception:
            throughput_ref = None
    predicted = attach_quality_and_confidence(predicted, metric_models, throughput_ref)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_csv = os.path.join(AI_RESULTS_DIR, f"AI_Predictions_{ts}.csv")
    predicted.to_csv(out_csv, index=False)
    predicted.to_csv(os.path.join(AI_RESULTS_DIR, "AI_Predictions_latest.csv"), index=False)

    # Also emit a MATLAB-friendly scenario list for ground-truth validation:
    # one recommended (modulation, SNR, detector) config per row, plus the
    # channel parameters MATLAB's scenario struct needs.
    scenario_cols = [
        "Environment", "Speed_kmh", "DelayProfile", "DopplerSpread",
        "Modulation", "SNR_dB", "Detector", "Recommendation_Confidence",
    ]
    if "Quality" in predicted.columns:
        scenario_cols.append("Quality")
    scenario_list = predicted[scenario_cols].to_dict(orient="records")
    with open(os.path.join(AI_RESULTS_DIR, "ai_recommended_scenarios.json"), "w") as f:
        json.dump(scenario_list, f, indent=2)

    print(f"Forward predictions written -> {out_csv}")
    print(f"Recommended scenarios for MATLAB validation -> "
          f"{os.path.join(AI_RESULTS_DIR, 'ai_recommended_scenarios.json')}")
    print("\nSample (first 5 rows):")
    cols_to_show = ["Modulation", "SNR_dB", "Detector", "Recommendation_Confidence"] + \
                    [f"Predicted_{t}" for t in metric_models]
    if "Quality" in predicted.columns:
        cols_to_show.append("Quality")
    print(predicted[cols_to_show].head().to_string(index=False))

    # Interactive decision dashboard for this forward-mode run (Environment
    # mix, Detector mix, Quality mix, Confidence -- built from `predicted`
    # directly, no disk round-trip needed).
    dashboard.build_dashboard(predicted)

    return predicted


# ---------------------------------------------------------------------------
# Mode B: evaluate predictions against real MATLAB ground truth
# ---------------------------------------------------------------------------
def run_validation_mode(input_csv: str):
    _require_models()
    clf = joblib.load(DETECTOR_MODEL_FILE)
    metric_models = _load_metric_models()

    actual = pd.read_csv(input_csv)
    missing = [c for c in ALL_COLUMNS if c not in actual.columns]
    if missing:
        print(f"WARNING: input CSV is missing columns {missing}; "
              f"continuing with what's available.", file=sys.stderr)

    # --- metric prediction accuracy: predict each row's metrics for the
    # detector actually used, compare to actual simulated values ---
    predicted = predict_metrics(metric_models, actual)
    throughput_ref = build_throughput_reference(actual)
    predicted_with_quality = attach_quality_and_confidence(predicted, metric_models, throughput_ref)
    if "Modulation" in actual.columns and "Modulation" not in predicted_with_quality.columns:
        predicted_with_quality["Modulation"] = actual["Modulation"].values
    if "BER" in actual.columns:
        predicted_with_quality["Actual_Quality"] = classify_quality_frame(
            actual, ber_col="BER", cqi_col="CQI", throughput_col="Throughput_bps",
            throughput_ref=throughput_ref)
    predicted = predicted_with_quality

    errors = {}
    for target in metric_models:
        if target not in actual.columns:
            continue
        y_true = actual[target].astype(float).values
        y_pred = predicted[f"Predicted_{target}"].values
        mae = float(np.mean(np.abs(y_true - y_pred)))
        rmse = float(np.sqrt(np.mean((y_true - y_pred) ** 2)))
        # Relative error is only meaningful away from ~0 (e.g. throughput at
        # very low SNR can be near-zero and blow up a naive ratio) -- floor
        # the denominator at 1% of this target's typical (median) magnitude.
        denom_floor = max(np.median(np.abs(y_true)) * 0.01, 1e-9)
        rel = float(np.mean(np.abs(y_true - y_pred) / np.maximum(np.abs(y_true), denom_floor)))
        errors[target] = {"mae": mae, "rmse": rmse, "mean_rel_error": rel}

    # --- detector recommendation accuracy: what the classifier WOULD have
    # recommended per scenario, vs. which detector was actually best in
    # this ground-truth run ---
    from train_model import compute_best_detector_table
    from config import FEATURE_COLS_DETECTOR

    best_actual = compute_best_detector_table(actual)
    scenario_features = best_actual[FEATURE_COLS_DETECTOR]
    best_actual = best_actual.copy()
    best_actual["Predicted_Best_Detector"] = clf.predict(scenario_features)

    det_correct = (best_actual["Predicted_Best_Detector"] == best_actual["Detector"]).mean()

    # --- save merged comparison ---
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_csv = os.path.join(AI_RESULTS_DIR, "predictions_vs_actual.csv")
    predicted.to_csv(out_csv, index=False)
    predicted.to_csv(os.path.join(AI_RESULTS_DIR, f"predictions_vs_actual_{ts}.csv"), index=False)

    det_csv = os.path.join(AI_RESULTS_DIR, "detector_recommendation_eval.csv")
    best_actual.to_csv(det_csv, index=False)

    summary = {
        "n_rows_evaluated": len(actual),
        "metric_errors": errors,
        "detector_recommendation_accuracy": float(det_correct),
        "n_scenarios_for_detector_eval": len(best_actual),
    }
    with open(os.path.join(AI_RESULTS_DIR, "evaluation_summary.json"), "w") as f:
        json.dump(summary, f, indent=2)

    print(f"\n=== Prediction Evaluation (vs MATLAB ground truth: {input_csv}) ===")
    print(f"Rows evaluated: {len(actual)}")
    for target, e in errors.items():
        print(f"  {target:<28s} MAE={e['mae']:.4g}  RMSE={e['rmse']:.4g}  "
              f"MeanRelErr={e['mean_rel_error']*100:.1f}%")
    print(f"Detector recommendation accuracy: {det_correct*100:.1f}% "
          f"({len(best_actual)} scenarios)")
    print(f"\nSaved -> {out_csv}")
    print(f"Saved -> {det_csv}")
    print(f"Saved -> {os.path.join(AI_RESULTS_DIR, 'evaluation_summary.json')}")

    # Section B exploratory graphs (13, 14, 15, 17) stay as static PNGs --
    # the composite decision/accuracy dashboard (formerly graph 25) is now
    # the single interactive HTML dashboard instead, built straight from
    # `predicted` (validation mode) so it includes the accuracy panels too.
    print("\n=== Generating validation graphs ===")
    graphs.plot_predicted_vs_actual(predicted, "BER", "13_predicted_vs_actual_ber.png",
                                     "Predicted vs Actual BER", log_scale=True)
    graphs.plot_predicted_vs_actual(predicted, "Throughput_bps", "14_predicted_vs_actual_throughput.png",
                                     "Predicted vs Actual Throughput")
    graphs.plot_prediction_error_vs_environment(predicted, target="BER")
    graphs.plot_detector_recommendation_accuracy(best_actual)
    dashboard.build_dashboard(predicted)

    return summary


def main():
    ap = argparse.ArgumentParser(description="AI communication prediction / detector recommendation / evaluation.")
    ap.add_argument("--input", type=str, default=None,
                     help="Actual MATLAB results CSV (full OTFS_Dataset schema) -> validation mode. "
                          "Omit for forward prediction mode.")
    ap.add_argument("--environment", type=str, default=None)
    ap.add_argument("--speed", type=float, default=None)
    ap.add_argument("--delay_profile", type=str, default=None)
    ap.add_argument("--doppler_scale", type=float, default=None)
    ap.add_argument("--delay_spread", type=float, default=5)
    ap.add_argument("--num_paths", type=float, default=4)
    ap.add_argument("--category", type=str, default="Unknown")
    args = ap.parse_args()

    if args.input:
        run_validation_mode(args.input)
        return

    # Forward mode: prefer explicit CLI args, fall back to detected_environment.json
    if args.environment and args.speed is not None and args.delay_profile and args.doppler_scale is not None:
        run_forward_mode(args.environment, args.speed, args.delay_profile,
                          args.doppler_scale, args.delay_spread, args.num_paths, args.category)
        return

    if os.path.exists(DETECTED_ENV_FILE):
        with open(DETECTED_ENV_FILE) as f:
            det = json.load(f)
        run_forward_mode(det["environment"], det["speed_kmh"], det["delay_profile"],
                          det["doppler_scale"], args.delay_spread, args.num_paths, args.category)
        return

    print(f"ERROR: no --input CSV given and {DETECTED_ENV_FILE} not found. "
          f"Either run parameter_mapper.py first, pass --input <results.csv>, "
          f"or pass --environment/--speed/--delay_profile/--doppler_scale explicitly.",
          file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    main()
