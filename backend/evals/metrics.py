"""Metric calculations for the Evals Platform."""

from __future__ import annotations

import math
from typing import Any, Optional


def mae(values: list[float]) -> float:
    """Mean Absolute Error."""
    if not values:
        return 0.0
    return sum(abs(v) for v in values) / len(values)


def rmse(values: list[float]) -> float:
    """Root Mean Squared Error."""
    if not values:
        return 0.0
    return math.sqrt(sum(v * v for v in values) / len(values))


def mape(values: list[float]) -> Optional[float]:
    """Mean Absolute Percentage Error. Only valid when all values != 0."""
    valid = [v for v in values if abs(v) > 1e-12]
    if not valid or len(valid) != len(values):
        return None
    return sum(abs(v) for v in valid) / len(valid)


def accuracy(correct: int, total: int) -> float:
    """Classification accuracy."""
    if total == 0:
        return 0.0
    return correct / total


def precision(tp: int, fp: int) -> float:
    """Precision for a binary class."""
    if tp + fp == 0:
        return 0.0
    return tp / (tp + fp)


def recall(tp: int, fn: int) -> float:
    """Recall for a binary class."""
    if tp + fn == 0:
        return 0.0
    return tp / (tp + fn)


def f1_score_binary(tp: int, fp: int, fn: int) -> float:
    """F1 score for a binary class."""
    p = precision(tp, fp)
    r = recall(tp, fn)
    if p + r == 0:
        return 0.0
    return 2 * p * r / (p + r)


def regret_ber(chosen_ber: float, oracle_ber: float) -> float:
    """BER regret: log10(chosen_ber / oracle_ber).

    Matches the existing project definition from train_waveform_selector.py:
        regret = mean log10(BER_selected / BER_oracle)
    """
    if oracle_ber <= 0 or oracle_ber < 1e-12:
        return 0.0
    ratio = max(chosen_ber, 1e-12) / oracle_ber
    return math.log10(max(ratio, 1.0))


def regret_acs(chosen_acs: float, oracle_acs: float) -> float:
    """ACS regret: oracle_acs - chosen_acs (clamped to >= 0)."""
    return max(oracle_acs - chosen_acs, 0.0)


def compute_case_metrics(
    prediction: Optional[dict],
    ground_truth: Optional[dict],
    case_type: str,
    ood: bool,
) -> dict[str, Any]:
    """Compute per-case metrics given prediction and ground truth.

    Returns a dict of metric_name -> value. Only computes metrics where
    both prediction and ground truth are available and meaningful.
    """
    metrics: dict[str, Any] = {}

    if ood:
        return metrics

    if prediction is None or ground_truth is None:
        return metrics

    # BER error
    pred_ber = prediction.get("BER")
    gt_ber = ground_truth.get("BER")
    if pred_ber is not None and gt_ber is not None:
        metrics["ber_error"] = abs(pred_ber - gt_ber)
        metrics["ber_abs_error"] = abs(pred_ber - gt_ber)
        metrics["regret_ber"] = regret_ber(pred_ber, gt_ber)

    # Throughput error
    pred_tp = prediction.get("throughput_bps")
    gt_tp = ground_truth.get("throughput_bps")
    if pred_tp is not None and gt_tp is not None:
        metrics["throughput_error"] = abs(pred_tp - gt_tp)

    # CQI error
    pred_cqi = prediction.get("CQI")
    gt_cqi = ground_truth.get("CQI")
    if pred_cqi is not None and gt_cqi is not None:
        metrics["cqi_error"] = abs(pred_cqi - gt_cqi)

    # ACS error and regret
    pred_acs = prediction.get("ACS")
    gt_acs = ground_truth.get("ACS")
    if pred_acs is not None and gt_acs is not None:
        metrics["acs_error"] = abs(pred_acs - gt_acs)
        metrics["regret_acs"] = regret_acs(pred_acs, gt_acs)

    # SER error
    pred_ser = prediction.get("SER")
    gt_ser = ground_truth.get("SER")
    if pred_ser is not None and gt_ser is not None:
        metrics["ser_error"] = abs(pred_ser - gt_ser)

    # PER error
    pred_per = prediction.get("PER")
    gt_per = ground_truth.get("PER")
    if pred_per is not None and gt_per is not None:
        metrics["per_error"] = abs(pred_per - gt_per)

    # Selection correctness (waveform oracle match)
    pred_wf = prediction.get("selected_waveform") or prediction.get("waveform")
    gt_wf = ground_truth.get("oracle_waveform") or ground_truth.get("waveform")
    if pred_wf and gt_wf:
        metrics["selection_correct"] = 1.0 if pred_wf == gt_wf else 0.0

    return metrics


def aggregate_metrics(
    case_results: list[dict],
    case_type_filter: Optional[str] = None,
) -> dict[str, Any]:
    """Aggregate per-case metrics into summary metrics.

    Takes a list of case result dicts (each containing a 'metrics' field).
    Returns aggregated metrics.

    If case_type_filter is provided (e.g. "EXACT"), only cases of that type
    are included in the aggregation.
    """
    all_ber_errors: list[float] = []
    all_throughput_errors: list[float] = []
    all_cqi_errors: list[float] = []
    all_acs_errors: list[float] = []
    all_ber_regrets: list[float] = []
    all_acs_regrets: list[float] = []
    all_selection: list[float] = []
    all_confidence: list[float] = []

    for cr in case_results:
        if case_type_filter and cr.get("case_type") != case_type_filter:
            continue

        m = cr.get("metrics") or {}
        if m.get("ber_error") is not None:
            all_ber_errors.append(m["ber_error"])
        if m.get("throughput_error") is not None:
            all_throughput_errors.append(m["throughput_error"])
        if m.get("cqi_error") is not None:
            all_cqi_errors.append(m["cqi_error"])
        if m.get("acs_error") is not None:
            all_acs_errors.append(m["acs_error"])
        if m.get("regret_ber") is not None:
            all_ber_regrets.append(m["regret_ber"])
        if m.get("regret_acs") is not None:
            all_acs_regrets.append(m["regret_acs"])
        if m.get("selection_correct") is not None:
            all_selection.append(m["selection_correct"])
        conf = cr.get("confidence")
        if conf is not None:
            all_confidence.append(conf)

    agg: dict[str, Any] = {}

    if all_ber_errors:
        agg["ber_mae"] = mae(all_ber_errors)
        agg["ber_rmse"] = rmse(all_ber_errors)
    if all_throughput_errors:
        agg["throughput_mae"] = mae(all_throughput_errors)
        agg["throughput_rmse"] = rmse(all_throughput_errors)
    if all_cqi_errors:
        agg["cqi_mae"] = mae(all_cqi_errors)
        agg["cqi_rmse"] = rmse(all_cqi_errors)
    if all_acs_errors:
        agg["acs_mae"] = mae(all_acs_errors)
        agg["acs_rmse"] = rmse(all_acs_errors)
    if all_ber_regrets:
        agg["mean_ber_regret"] = sum(all_ber_regrets) / len(all_ber_regrets)
        agg["median_ber_regret"] = sorted(all_ber_regrets)[len(all_ber_regrets) // 2]
        agg["max_ber_regret"] = max(all_ber_regrets)
    if all_acs_regrets:
        agg["mean_acs_regret"] = sum(all_acs_regrets) / len(all_acs_regrets)
    if all_selection:
        agg["selection_accuracy"] = sum(all_selection) / len(all_selection)
    if all_confidence:
        agg["mean_confidence"] = sum(all_confidence) / len(all_confidence)

    return agg
