"""Report generation and regression comparison for the Evals Platform."""

from __future__ import annotations

from typing import Any

from .schemas import EvalRunSummary, RegressionComparison


# Interpretation thresholds
_IMPROVED_THRESHOLDS = {
    "ber_mae": ("lower", 0.01),
    "ber_rmse": ("lower", 0.01),
    "throughput_mae": ("lower", 0.01),
    "cqi_mae": ("lower", 0.01),
    "acs_mae": ("lower", 0.01),
    "mean_ber_regret": ("lower", 0.01),
    "mean_acs_regret": ("lower", 0.01),
    "selection_accuracy": ("higher", 0.01),
    "mean_confidence": ("higher", 0.01),
}


def compare_runs(
    run_a_summary: EvalRunSummary,
    run_b_summary: EvalRunSummary,
    run_a_report: dict,
    run_b_report: dict,
) -> RegressionComparison:
    """Compare two completed evaluation runs.

    Correctly handles whether higher or lower is better for each metric.
    """
    agg_a = run_a_report.get("aggregated_metrics", {})
    agg_b = run_b_report.get("aggregated_metrics", {})

    all_keys = sorted(set(list(agg_a.keys()) + list(agg_b.keys())))
    metric_comparison = []
    improved = []
    degraded = []
    unchanged = []

    for key in all_keys:
        val_a = agg_a.get(key)
        val_b = agg_b.get(key)

        if val_a is None or val_b is None:
            continue
        if not isinstance(val_a, (int, float)) or not isinstance(val_b, (int, float)):
            continue

        delta = val_b - val_a
        pct_change = (delta / abs(val_a) * 100) if val_a != 0 else 0

        direction, threshold = _IMPROVED_THRESHOLDS.get(key, ("lower", 0.01))

        if direction == "lower":
            is_improved = delta < -threshold
            is_degraded = delta > threshold
        else:
            is_improved = delta > threshold
            is_degraded = delta < -threshold

        if is_improved:
            interp = "IMPROVED"
            improved.append(key)
        elif is_degraded:
            interp = "DEGRADED"
            degraded.append(key)
        else:
            interp = "STABLE"
            unchanged.append(key)

        metric_comparison.append({
            "metric": key,
            "run_a": round(val_a, 6),
            "run_b": round(val_b, 6),
            "delta": round(delta, 6),
            "pct_change": round(pct_change, 2),
            "direction_preference": direction,
            "interpretation": interp,
        })

    if improved and not degraded:
        interpretation = "Run B shows overall improvement over Run A"
    elif degraded and not improved:
        interpretation = "Run B shows overall degradation compared to Run A"
    elif improved and degraded:
        interpretation = "Run B shows mixed results: improvements and degradations"
    else:
        interpretation = "No significant differences between Run A and Run B"

    return RegressionComparison(
        run_a_id=run_a_summary.run_id,
        run_b_id=run_b_summary.run_id,
        run_a_summary=run_a_summary,
        run_b_summary=run_b_summary,
        metric_comparison=metric_comparison,
        interpretation=interpretation,
        improved=improved,
        degraded=degraded,
        unchanged=unchanged,
    )
