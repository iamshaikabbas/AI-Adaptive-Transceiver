"""Evaluation run manager — async execution with live progress tracking.

Manages evaluation runs, persists results, and broadcasts live progress
events via WebSocket.
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

from .cases import generate_cases
from .engine import EvalEngine
from .golden_dataset import get_golden_dataset
from .metrics import aggregate_metrics
from .schemas import (
    CaseResult,
    CaseType,
    EvalCaseResult,
    EvalRunConfig,
    EvalRunResult,
    EvalRunSummary,
    EvalSuite,
    RunStatus,
    WSEvalEvent,
)

logger = logging.getLogger(__name__)

_RUNS_DIR = Path(__file__).resolve().parent.parent.parent / "deployment" / "evals" / "runs"


def _make_run_id() -> str:
    now = datetime.now()
    short = uuid.uuid4().hex[:6]
    return f"EVAL-{now.strftime('%Y-%m-%d')}-{short}"


def _ensure_runs_dir():
    _RUNS_DIR.mkdir(parents=True, exist_ok=True)


class EvalRunner:
    """Manages evaluation run lifecycle.

    Executes cases sequentially in a background thread, accumulating
    results and broadcasting progress via a callback.
    """

    def __init__(self):
        self._engine = EvalEngine()
        self._active_run_id: Optional[str] = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self._runs: dict[str, dict] = {}
        self._load_existing_runs()

    def _load_existing_runs(self):
        """Load existing run summaries from disk."""
        _ensure_runs_dir()
        for run_dir in _RUNS_DIR.iterdir():
            if run_dir.is_dir():
                summary_path = run_dir / "summary.json"
                if summary_path.exists():
                    try:
                        with open(summary_path, encoding="utf-8") as f:
                            self._runs[run_dir.name] = json.load(f)
                    except Exception:
                        pass

    def is_running(self) -> bool:
        return self._active_run_id is not None

    def get_active_run_id(self) -> Optional[str]:
        return self._active_run_id

    def list_runs(self) -> list[dict]:
        """List all completed/persisted runs."""
        _ensure_runs_dir()
        runs = []
        for run_dir in sorted(_RUNS_DIR.iterdir(), reverse=True):
            if run_dir.is_dir():
                summary_path = run_dir / "summary.json"
                if summary_path.exists():
                    try:
                        with open(summary_path, encoding="utf-8") as f:
                            runs.append(json.load(f))
                    except Exception:
                        pass
        return runs

    def get_run(self, run_id: str) -> Optional[dict]:
        """Get full run data."""
        run_dir = _RUNS_DIR / run_id
        if not run_dir.is_dir():
            return None

        result: dict[str, Any] = {}

        for fname in ["summary.json", "config.json", "cases.json", "report.json", "graph_data.json"]:
            fpath = run_dir / fname
            if fpath.exists():
                try:
                    with open(fpath, encoding="utf-8") as f:
                        key = fname.replace(".json", "")
                        result[key] = json.load(f)
                except Exception:
                    pass

        return result

    def start_run(
        self,
        config: EvalRunConfig,
        on_progress: Optional[Callable] = None,
    ) -> EvalRunSummary:
        """Start a new evaluation run in a background thread."""
        if self.is_running():
            raise ValueError("An evaluation run is already active")

        dataset = get_golden_dataset()
        manifest = dataset.build_manifest()

        if not manifest.checksum_verified:
            raise ValueError(
                f"Golden Dataset checksum verification FAILED. "
                f"Expected: {manifest.checksum_md5}"
            )

        run_id = _make_run_id()
        cases = generate_cases(dataset, config.suite)

        summary = EvalRunSummary(
            run_id=run_id,
            suite=config.suite,
            status=RunStatus.RUNNING,
            created_at=_now_iso(),
            started_at=_now_iso(),
            total_cases=len(cases),
            dataset_checksum=manifest.checksum_md5,
            model_version=config.model_version,
            policy_version=config.policy_version,
        )

        _ensure_runs_dir()
        run_dir = _RUNS_DIR / run_id
        run_dir.mkdir(parents=True, exist_ok=True)

        config_path = run_dir / "config.json"
        config_path.write_text(config.model_dump_json(indent=2), encoding="utf-8")

        summary_path = run_dir / "summary.json"
        summary_path.write_text(summary.model_dump_json(indent=2), encoding="utf-8")

        self._active_run_id = run_id
        self._stop_event.clear()

        thread = threading.Thread(
            target=self._run_loop,
            args=(run_id, config, cases, summary, on_progress),
            daemon=True,
        )
        thread.start()

        return summary

    def stop_run(self):
        """Stop the active evaluation run."""
        self._stop_event.set()

    def _run_loop(
        self,
        run_id: str,
        config: EvalRunConfig,
        cases: list,
        summary: EvalRunSummary,
        on_progress: Optional[Callable],
    ):
        """Background thread: evaluate all cases sequentially."""
        case_results: list[dict] = []
        all_metrics: dict[str, list[float]] = {}
        graph_data: dict[str, list] = {
            "elapsed_seconds": [],
            "case_index": [],
            "ber_error": [],
            "throughput_error": [],
            "cqi_error": [],
            "acs_error": [],
            "confidence": [],
            "pass_cumulative": [],
            "fail_cumulative": [],
            "rejected_cumulative": [],
            "pass_rate": [],
            "ood_rejection_rate": [],
            "ber_pred": [],
            "ber_gt": [],
            "tp_pred": [],
            "tp_gt": [],
            "cqi_pred": [],
            "cqi_gt": [],
            "regret_ber": [],
            "case_types": [],
        }

        run_dir = _RUNS_DIR / run_id
        t_start = time.time()

        try:
            for i, case in enumerate(cases):
                if self._stop_event.is_set():
                    summary.status = RunStatus.STOPPED
                    break

                result = self._engine.evaluate_case(case)
                result_dict = result.model_dump()
                case_results.append(result_dict)

                elapsed = time.time() - t_start
                summary.completed_cases = i + 1
                summary.elapsed_seconds = elapsed
                summary.current_case_id = case.case_id
                summary.current_case_type = case.case_type
                summary.progress_pct = round((i + 1) / len(cases) * 100, 1)

                if result.result == CaseResult.PASS:
                    summary.passed += 1
                elif result.result == CaseResult.FAIL:
                    summary.failed += 1
                elif result.result == CaseResult.REJECTED:
                    summary.rejected += 1
                elif result.result == CaseResult.UNAVAILABLE:
                    summary.unavailable += 1

                _update_graph_data(graph_data, result, i, elapsed, summary)

                _append_case_result(run_dir, result_dict)

                if on_progress and (i % max(1, len(cases) // 100) == 0 or i == len(cases) - 1):
                    try:
                        on_progress(summary, result, graph_data)
                    except Exception as e:
                        logger.debug("Progress callback error: %s", e)

            if summary.status == RunStatus.RUNNING:
                summary.status = RunStatus.COMPLETED
                summary.completed_at = _now_iso()

        except Exception as e:
            logger.error("Eval run %s failed: %s", run_id, e, exc_info=True)
            summary.status = RunStatus.FAILED

        summary.elapsed_seconds = time.time() - t_start

        try:
            agg = aggregate_metrics(case_results)
            report = _build_report(summary, agg, case_results)

            summary_path = run_dir / "summary.json"
            summary_path.write_text(summary.model_dump_json(indent=2), encoding="utf-8")

            cases_path = run_dir / "cases.json"
            cases_path.write_text(json.dumps(case_results, indent=2, default=str), encoding="utf-8")

            report_path = run_dir / "report.json"
            report_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")

            graph_path = run_dir / "graph_data.json"
            graph_path.write_text(json.dumps(graph_data, indent=2, default=str), encoding="utf-8")

        except Exception as e:
            logger.error("Failed to persist run results: %s", e)

        self._active_run_id = None

        if on_progress:
            try:
                on_progress(summary, None, graph_data)
            except Exception:
                pass


def _update_graph_data(
    graph_data: dict,
    result: EvalCaseResult,
    index: int,
    elapsed: float,
    summary: EvalRunSummary,
):
    """Append data points for live graph updates."""
    graph_data["elapsed_seconds"].append(round(elapsed, 3))
    graph_data["case_index"].append(index + 1)
    graph_data["case_types"].append(result.case_type.value)

    m = result.metrics or {}
    graph_data["ber_error"].append(m.get("ber_error"))
    graph_data["throughput_error"].append(m.get("throughput_error"))
    graph_data["cqi_error"].append(m.get("cqi_error"))
    graph_data["acs_error"].append(m.get("acs_error"))
    graph_data["confidence"].append(result.confidence)
    graph_data["regret_ber"].append(m.get("regret_ber"))

    graph_data["pass_cumulative"].append(summary.passed)
    graph_data["fail_cumulative"].append(summary.failed)
    graph_data["rejected_cumulative"].append(summary.rejected)

    total = summary.completed_cases or 1
    graph_data["pass_rate"].append(round(summary.passed / total, 4))
    graph_data["ood_rejection_rate"].append(
        round(summary.rejected / max(1, summary.rejected + summary.failed + summary.passed), 4)
    )

    if result.ground_truth and result.prediction:
        selected = result.prediction.get("selected_waveform", "OTFS")
        pred_wf = result.prediction.get(selected, {})
        graph_data["ber_pred"].append(pred_wf.get("BER"))
        graph_data["ber_gt"].append(result.ground_truth.get("BER"))
        graph_data["tp_pred"].append(pred_wf.get("throughput_bps"))
        graph_data["tp_gt"].append(result.ground_truth.get("throughput_bps"))
        graph_data["cqi_pred"].append(pred_wf.get("CQI"))
        graph_data["cqi_gt"].append(result.ground_truth.get("CQI"))
    else:
        graph_data["ber_pred"].append(None)
        graph_data["ber_gt"].append(None)
        graph_data["tp_pred"].append(None)
        graph_data["tp_gt"].append(None)
        graph_data["cqi_pred"].append(None)
        graph_data["cqi_gt"].append(None)


def _append_case_result(run_dir: Path, result: dict):
    """Append a single case result to the cases file (incremental write)."""
    cases_path = run_dir / "cases.jsonl"
    try:
        with open(cases_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(result, default=str) + "\n")
    except Exception as e:
        logger.debug("Failed to append case result: %s", e)


def _build_report(summary: EvalRunSummary, agg: dict, case_results: list) -> dict:
    """Build final evaluation report with case-type separation.

    Report structure:
      - overall: top-level counts
      - exact: prediction accuracy (EXACT only — genuine GT comparison)
      - interior: generalization (INTERIOR — model estimates, no GT)
      - boundary: boundary robustness (BOUNDARY — model estimates, no GT)
      - ood: safety (OOD — rejection rate, fabricated predictions)
      - aggregated_metrics: EXACT-only prediction accuracy metrics
    """
    by_type: dict[str, dict] = {}
    for cr in case_results:
        ct = cr.get("case_type", "UNKNOWN")
        if ct not in by_type:
            by_type[ct] = {
                "count": 0, "pass": 0, "fail": 0,
                "rejected": 0, "unavailable": 0,
            }
        by_type[ct]["count"] += 1
        r = cr.get("result", "UNKNOWN")
        if r == "PASS":
            by_type[ct]["pass"] += 1
        elif r == "FAIL":
            by_type[ct]["fail"] += 1
        elif r == "REJECTED":
            by_type[ct]["rejected"] += 1
        elif r == "UNAVAILABLE":
            by_type[ct]["unavailable"] += 1

    exact_metrics = aggregate_metrics(case_results, case_type_filter="EXACT")

    exact_info = by_type.get("EXACT", {"count": 0, "pass": 0, "fail": 0, "rejected": 0, "unavailable": 0})
    interior_info = by_type.get("INTERIOR", {"count": 0, "pass": 0, "fail": 0, "rejected": 0, "unavailable": 0})
    boundary_info = by_type.get("BOUNDARY", {"count": 0, "pass": 0, "fail": 0, "rejected": 0, "unavailable": 0})
    ood_info = by_type.get("OOD", {"count": 0, "pass": 0, "fail": 0, "rejected": 0, "unavailable": 0})

    ood_total = ood_info["count"]
    ood_rejected = ood_info["rejected"]
    ood_fabricated = ood_info["pass"] + ood_info["fail"]

    return {
        "run_id": summary.run_id,
        "suite": summary.suite.value,
        "status": summary.status.value,
        "total_cases": summary.total_cases,
        "completed_cases": summary.completed_cases,
        "elapsed_seconds": summary.elapsed_seconds,
        "dataset_checksum": summary.dataset_checksum,
        "model_version": summary.model_version,
        "policy_version": summary.policy_version,

        # Overall counts
        "overall": {
            "total": summary.total_cases,
            "completed": summary.completed_cases,
            "passed": summary.passed,
            "failed": summary.failed,
            "rejected": summary.rejected,
            "unavailable": summary.unavailable,
        },

        # EXACT: genuine prediction accuracy (has ground truth)
        "exact": {
            "total": exact_info["count"],
            "completed": exact_info["pass"] + exact_info["fail"],
            "pass": exact_info["pass"],
            "fail": exact_info["fail"],
            "pass_rate": round(
                exact_info["pass"] / max(1, exact_info["pass"] + exact_info["fail"]), 4
            ),
        },

        # INTERIOR: generalization (no ground truth — model estimates only)
        "interior": {
            "total": interior_info["count"],
            "completed": interior_info["count"],
            "model_estimates": interior_info["unavailable"],
            "note": "No ground truth available — predictions are model estimates, not verified accuracy",
        },

        # BOUNDARY: boundary robustness (no ground truth)
        "boundary": {
            "total": boundary_info["count"],
            "completed": boundary_info["count"],
            "model_estimates": boundary_info["unavailable"],
            "rejected": boundary_info["rejected"],
            "note": "No ground truth at boundary — predictions are model estimates",
        },

        # OOD: safety evaluation
        "ood": {
            "total": ood_total,
            "rejected": ood_rejected,
            "fabricated_predictions": ood_fabricated,
            "rejection_rate": round(ood_rejected / max(1, ood_total), 4),
            "false_prediction_rate": round(ood_fabricated / max(1, ood_total), 4),
        },

        # Prediction accuracy metrics (EXACT only — the only valid accuracy numbers)
        "aggregated_metrics": exact_metrics,

        # Backward-compatible by_case_type
        "by_case_type": by_type,
    }


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
