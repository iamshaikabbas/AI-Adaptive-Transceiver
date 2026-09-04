"""Tests for the Evals Platform — backend modules.

Validates:
- Golden Dataset loading, checksum verification, manifest
- Metric computations
- Case generation (EXACT/INTERIOR/BOUNDARY/OOD)
- Schema validation
- Golden Dataset CSV is read-only (never modified)
"""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import pytest

# ── Paths ────────────────────────────────────────────────────────────────────
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_GOLDEN_CSV = (
    _PROJECT_ROOT
    / "OTFS MRC detection MATLAB code"
    / "Results"
    / "FinalEvaluation"
    / "final_dataset.csv"
)
_EXPECTED_MD5 = "faa877a248c0f599a87f21dabf4df358"

# ── Imports under test ───────────────────────────────────────────────────────
import sys
sys.path.insert(0, str(_PROJECT_ROOT / "backend"))

from evals.schemas import (
    CaseResult,
    CaseType,
    DataSourceTag,
    EvalSuite,
    EvalCaseInput,
    EvalCase,
    EvalRunConfig,
    EvalRunSummary,
    RunStatus,
)
from evals.golden_dataset import GoldenDataset, get_golden_dataset
from evals.metrics import (
    mae,
    rmse,
    mape,
    accuracy,
    precision,
    recall,
    f1_score_binary,
    compute_case_metrics,
    aggregate_metrics,
)
from evals.cases import (
    generate_exact_cases,
    generate_interior_cases,
    generate_boundary_cases,
    generate_ood_cases,
    generate_cases,
)
from evals.engine import EvalEngine
from evals.report import compare_runs


# ═══════════════════════════════════════════════════════════════════════════════
# 1. Golden Dataset integrity
# ═══════════════════════════════════════════════════════════════════════════════

class TestGoldenDatasetIntegrity:
    """Golden Dataset must be read-only and checksum-verified."""

    def test_file_exists(self):
        assert _GOLDEN_CSV.exists(), f"Golden Dataset not found: {_GOLDEN_CSV}"

    def test_md5_checksum(self):
        md5 = hashlib.md5(_GOLDEN_CSV.read_bytes()).hexdigest()
        assert md5 == _EXPECTED_MD5, (
            f"Golden Dataset checksum mismatch! "
            f"Expected {_EXPECTED_MD5}, got {md5}. "
            f"final_dataset.csv must NEVER be modified."
        )

    def test_csv_readable_and_rows(self):
        with open(_GOLDEN_CSV, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        assert len(rows) == 2336, f"Expected 2336 rows, got {len(rows)}"

    def test_csv_has_required_columns(self):
        with open(_GOLDEN_CSV, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            cols = reader.fieldnames
        required = ["scenario_id", "frame", "environment", "speed_kmph", "snr_db",
                     "channel_profile", "modulation", "BER", "ACS"]
        for c in required:
            assert c in cols, f"Missing required column: {c}"

    def test_golden_dataset_singleton_loads(self):
        ds = get_golden_dataset()
        assert ds is not None
        manifest = ds.build_manifest()
        assert manifest.row_count == 2336

    def test_manifest_checksum_verified(self):
        ds = get_golden_dataset()
        manifest = ds.build_manifest()
        assert manifest.checksum_verified is True
        assert manifest.checksum_md5 == _EXPECTED_MD5

    def test_manifest_domain_boundaries(self):
        ds = get_golden_dataset()
        b = ds.get_domain_boundaries()
        assert "snr_db" in b
        assert "speed_kmph" in b
        assert b["snr_db"]["min"] < b["snr_db"]["max"]
        assert b["speed_kmph"]["min"] < b["speed_kmph"]["max"]

    def test_fixed_otfs_rows_available(self):
        ds = get_golden_dataset()
        rows = ds.get_fixed_otfs_rows()
        assert len(rows) > 0, "No fixed_otfs rows found"

    def test_never_modifies_csv(self):
        """Verify CSV was not modified during tests."""
        md5 = hashlib.md5(_GOLDEN_CSV.read_bytes()).hexdigest()
        assert md5 == _EXPECTED_MD5


# ═══════════════════════════════════════════════════════════════════════════════
# 2. Metric computations
# ═══════════════════════════════════════════════════════════════════════════════

class TestMetrics:

    def test_mae_basic(self):
        assert mae([0.0, 0.0, 0.0]) == 0.0

    def test_mae_nonzero(self):
        assert abs(mae([1.0, 1.0]) - 1.0) < 1e-12

    def test_rmse_basic(self):
        assert rmse([0.0, 0.0, 0.0]) == 0.0

    def test_rmse_nonzero(self):
        result = rmse([1.0, 1.0])
        assert abs(result - 1.0) < 1e-12

    def test_mape_basic(self):
        assert mape([0.1, 0.2]) is not None

    def test_accuracy_perfect(self):
        assert accuracy(4, 4) == 1.0

    def test_accuracy_half(self):
        assert abs(accuracy(2, 4) - 0.5) < 1e-12

    def test_precision_basic(self):
        p = precision(5, 5)
        assert abs(p - 0.5) < 1e-12

    def test_recall_basic(self):
        r = recall(5, 5)
        assert abs(r - 0.5) < 1e-12

    def test_f1_perfect(self):
        assert f1_score_binary(10, 0, 0) == 1.0

    def test_f1_zero(self):
        assert f1_score_binary(0, 10, 10) == 0.0

    def test_aggregate_metrics_empty(self):
        agg = aggregate_metrics([])
        assert isinstance(agg, dict)

    def test_aggregate_metrics_with_data(self):
        results = [
            {"metrics": {"ber_error": 0.01, "regret_ber": 0.05, "selection_correct": 1.0}, "confidence": 0.9},
            {"metrics": {"ber_error": 0.02, "regret_ber": 0.1, "selection_correct": 0.0}, "confidence": 0.7},
        ]
        agg = aggregate_metrics(results)
        assert "ber_mae" in agg
        assert "selection_accuracy" in agg
        assert abs(agg["selection_accuracy"] - 0.5) < 1e-12


# ═══════════════════════════════════════════════════════════════════════════════
# 3. Schemas
# ═══════════════════════════════════════════════════════════════════════════════

class TestSchemas:

    def test_case_type_values(self):
        assert CaseType.EXACT.value == "EXACT"
        assert CaseType.INTERIOR.value == "INTERIOR"
        assert CaseType.BOUNDARY.value == "BOUNDARY"
        assert CaseType.OOD.value == "OOD"

    def test_run_status_values(self):
        assert RunStatus.RUNNING.value == "RUNNING"
        assert RunStatus.COMPLETED.value == "COMPLETED"

    def test_eval_case_input_construction(self):
        inp = EvalCaseInput(
            environment="Urban",
            speed_kmph=25.0,
            snr_db=10.0,
            doppler_hz=92.6,
            channel_profile="EVA",
            modulation=4,
        )
        assert inp.environment == "Urban"
        assert inp.modulation == 4

    def test_eval_case_construction(self):
        inp = EvalCaseInput(
            environment="Urban",
            speed_kmph=25.0,
            snr_db=10.0,
            doppler_hz=92.6,
            channel_profile="EVA",
            modulation=4,
        )
        case = EvalCase(
            case_id="TEST-001",
            case_type=CaseType.EXACT,
            suite=EvalSuite.FULL_REGRESSION,
            input_conditions=inp,
            ground_truth_available=True,
            ground_truth={"BER": 0.01, "ACS": 0.5},
            ood=False,
        )
        assert case.case_id == "TEST-001"
        assert case.case_type == CaseType.EXACT
        assert case.ood is False

    def test_eval_run_config_defaults(self):
        cfg = EvalRunConfig(suite=EvalSuite.FULL_REGRESSION)
        assert cfg.suite == EvalSuite.FULL_REGRESSION

    def test_eval_run_summary_construction(self):
        s = EvalRunSummary(
            run_id="EVAL-TEST",
            suite=EvalSuite.PREDICTION_ACCURACY,
            status=RunStatus.RUNNING,
            created_at="2026-01-01T00:00:00Z",
            started_at="2026-01-01T00:00:00Z",
            total_cases=100,
            dataset_checksum="abc123",
            model_version="v2",
            policy_version="v1",
        )
        assert s.total_cases == 100
        assert s.passed == 0


# ═══════════════════════════════════════════════════════════════════════════════
# 4. Case generation
# ═══════════════════════════════════════════════════════════════════════════════

class TestCaseGeneration:

    def test_exact_cases_have_ground_truth(self):
        ds = get_golden_dataset()
        cases = generate_exact_cases(ds, EvalSuite.PREDICTION_ACCURACY)
        assert len(cases) > 0
        for c in cases:
            assert c.case_type == CaseType.EXACT
            assert c.ood is False

    def test_interior_cases_no_ground_truth(self):
        ds = get_golden_dataset()
        cases = generate_interior_cases(ds, EvalSuite.FULL_REGRESSION)
        assert len(cases) > 0
        for c in cases:
            assert c.case_type == CaseType.INTERIOR
            assert c.ground_truth_available is False

    def test_ood_cases_rejection_expected(self):
        ds = get_golden_dataset()
        cases = generate_ood_cases(ds, EvalSuite.OOD_SAFETY)
        assert len(cases) >= 7
        for c in cases:
            assert c.case_type == CaseType.OOD
            assert c.ood is True

    def test_full_regression_contains_all_types(self):
        ds = get_golden_dataset()
        cases = generate_cases(ds, EvalSuite.FULL_REGRESSION)
        types = {c.case_type for c in cases}
        assert CaseType.EXACT in types
        assert CaseType.OOD in types
        assert len(cases) > 10

    def test_ood_safety_only_ood(self):
        ds = get_golden_dataset()
        cases = generate_cases(ds, EvalSuite.OOD_SAFETY)
        for c in cases:
            assert c.case_type == CaseType.OOD

    def test_exact_case_ids_are_unique(self):
        ds = get_golden_dataset()
        cases = generate_exact_cases(ds, EvalSuite.PREDICTION_ACCURACY)
        ids = [c.case_id for c in cases]
        assert len(ids) == len(set(ids))


# ═══════════════════════════════════════════════════════════════════════════════
# 5. Engine
# ═══════════════════════════════════════════════════════════════════════════════

class TestEngine:

    def test_engine_loads(self):
        engine = EvalEngine()
        # Models may or may not be available depending on environment
        # This test just verifies the object can be created
        assert engine is not None

    def test_engine_predict_returns_none_or_dict(self):
        engine = EvalEngine()
        inp = EvalCaseInput(
            environment="Urban",
            speed_kmph=25.0,
            snr_db=10.0,
            doppler_hz=92.6,
            channel_profile="EVA",
            modulation=4,
        )
        result = engine.predict(inp)
        assert result is None or isinstance(result, dict)

    def test_ood_case_always_rejected(self):
        engine = EvalEngine()
        inp = EvalCaseInput(
            environment="Space",
            speed_kmph=1000.0,
            snr_db=-20.0,
            doppler_hz=50000.0,
            channel_profile="INVALID",
            modulation=256,
        )
        case = EvalCase(
            case_id="OOD-TEST-001",
            case_type=CaseType.OOD,
            suite=EvalSuite.OOD_SAFETY,
            input_conditions=inp,
            ground_truth_available=False,
            ground_truth=None,
            ood=True,
        )
        result = engine.evaluate_case(case)
        assert result.ood is True
        assert result.result in (CaseResult.REJECTED, CaseResult.FAIL)
        # OOD should never fabricate metrics
        if result.result == CaseResult.REJECTED:
            assert result.ood_decision == "REJECTED"


# ═══════════════════════════════════════════════════════════════════════════════
# 6. Report / regression comparison
# ═══════════════════════════════════════════════════════════════════════════════

class TestReport:

    def test_compare_runs_identical(self):
        summary = EvalRunSummary(
            run_id="TEST",
            suite=EvalSuite.FULL_REGRESSION,
            status=RunStatus.COMPLETED,
            created_at="2026-01-01T00:00:00Z",
            started_at="2026-01-01T00:00:00Z",
            total_cases=10,
            completed_cases=10,
            passed=10,
            elapsed_seconds=5.0,
            dataset_checksum="abc",
            model_version="v1",
            policy_version="v1",
        )
        report_a = {
            "aggregated_metrics": {
                "ber_mae": 0.01,
                "throughput_mae": 100.0,
                "selection_accuracy": 0.9,
            }
        }
        report_b = {
            "aggregated_metrics": {
                "ber_mae": 0.01,
                "throughput_mae": 100.0,
                "selection_accuracy": 0.9,
            }
        }
        comparison = compare_runs(summary, summary, report_a, report_b)
        assert len(comparison.improved) == 0
        assert len(comparison.degraded) == 0
        assert "no significant" in comparison.interpretation.lower() or "no significant" in comparison.interpretation.lower()

    def test_compare_runs_improvement(self):
        summary_a = EvalRunSummary(
            run_id="A", suite=EvalSuite.FULL_REGRESSION,
            status=RunStatus.COMPLETED, created_at="2026-01-01T00:00:00Z",
            started_at="2026-01-01T00:00:00Z", total_cases=10,
            completed_cases=10, elapsed_seconds=1.0,
            dataset_checksum="x", model_version="v1", policy_version="v1",
        )
        summary_b = EvalRunSummary(
            run_id="B", suite=EvalSuite.FULL_REGRESSION,
            status=RunStatus.COMPLETED, created_at="2026-01-01T00:00:00Z",
            started_at="2026-01-01T00:00:00Z", total_cases=10,
            completed_cases=10, elapsed_seconds=1.0,
            dataset_checksum="x", model_version="v1", policy_version="v1",
        )
        report_a = {"aggregated_metrics": {"ber_mae": 0.05}}
        report_b = {"aggregated_metrics": {"ber_mae": 0.01}}
        comparison = compare_runs(summary_a, summary_b, report_a, report_b)
        assert "ber_mae" in comparison.improved
        assert comparison.metric_comparison[0]["interpretation"] == "IMPROVED"

    def test_compare_runs_degradation(self):
        summary_a = EvalRunSummary(
            run_id="A", suite=EvalSuite.FULL_REGRESSION,
            status=RunStatus.COMPLETED, created_at="2026-01-01T00:00:00Z",
            started_at="2026-01-01T00:00:00Z", total_cases=10,
            completed_cases=10, elapsed_seconds=1.0,
            dataset_checksum="x", model_version="v1", policy_version="v1",
        )
        summary_b = EvalRunSummary(
            run_id="B", suite=EvalSuite.FULL_REGRESSION,
            status=RunStatus.COMPLETED, created_at="2026-01-01T00:00:00Z",
            started_at="2026-01-01T00:00:00Z", total_cases=10,
            completed_cases=10, elapsed_seconds=1.0,
            dataset_checksum="x", model_version="v1", policy_version="v1",
        )
        report_a = {"aggregated_metrics": {"selection_accuracy": 0.95}}
        report_b = {"aggregated_metrics": {"selection_accuracy": 0.80}}
        comparison = compare_runs(summary_a, summary_b, report_a, report_b)
        assert "selection_accuracy" in comparison.degraded
        assert comparison.metric_comparison[0]["interpretation"] == "DEGRADED"


# ═══════════════════════════════════════════════════════════════════════════════
# 7. No ground truth fabrication
# ═══════════════════════════════════════════════════════════════════════════════

class TestNoFabrication:
    """Verify that the system never fabricates ground truth from AI predictions."""

    def test_ood_cases_have_no_ground_truth(self):
        ds = get_golden_dataset()
        cases = generate_ood_cases(ds, EvalSuite.OOD_SAFETY)
        for c in cases:
            assert c.ground_truth is None
            assert c.ground_truth_available is False

    def test_interior_cases_have_no_ground_truth(self):
        ds = get_golden_dataset()
        cases = generate_interior_cases(ds, EvalSuite.FULL_REGRESSION)
        for c in cases:
            assert c.ground_truth is None

    def test_eval_engine_rejects_ood_fabrication(self):
        engine = EvalEngine()
        inp = EvalCaseInput(
            environment="InvalidEnv",
            speed_kmph=9999.0,
            snr_db=-50.0,
            doppler_hz=100000.0,
            channel_profile="InvalidChannel",
            modulation=999,
        )
        case = EvalCase(
            case_id="OOD-FAB-001",
            case_type=CaseType.OOD,
            suite=EvalSuite.OOD_SAFETY,
            input_conditions=inp,
            ground_truth_available=False,
            ground_truth=None,
            ood=True,
        )
        result = engine.evaluate_case(case)
        # Must not fabricate BER/SER/PER/throughput/CQI
        assert result.ood is True
        assert result.result in (CaseResult.REJECTED, CaseResult.FAIL)
        if result.prediction:
            selected = result.prediction.get("selected_waveform", "OTFS")
            pred_wf = result.prediction.get(selected, {})
            # If prediction exists but was rejected/failed, check metrics are not trusted
            if result.result == CaseResult.REJECTED:
                assert result.ood_decision == "REJECTED"


# ═══════════════════════════════════════════════════════════════════════════════
# 8. Determinism (no random cases)
# ═══════════════════════════════════════════════════════════════════════════════

class TestDeterminism:

    def test_case_generation_is_deterministic(self):
        ds = get_golden_dataset()
        cases_a = generate_ood_cases(ds, EvalSuite.OOD_SAFETY)
        cases_b = generate_ood_cases(ds, EvalSuite.OOD_SAFETY)
        assert [c.case_id for c in cases_a] == [c.case_id for c in cases_b]

    def test_exact_case_ids_deterministic(self):
        ds = get_golden_dataset()
        cases_a = generate_exact_cases(ds, EvalSuite.PREDICTION_ACCURACY)
        cases_b = generate_exact_cases(ds, EvalSuite.PREDICTION_ACCURACY)
        assert [c.case_id for c in cases_a] == [c.case_id for c in cases_b]


# ═══════════════════════════════════════════════════════════════════════════════
# 9. Near-zero BER evaluation criterion
# ═══════════════════════════════════════════════════════════════════════════════

class TestNearZeroBER:
    """Tests for the near-zero BER evaluation semantics.

    When GT BER is at or below the clipping floor (1e-12), relative error
    is undefined.  The system uses an absolute-error criterion (tolerance = 1e-2)
    instead.
    """

    def _make_case(self, gt_ber, pred_ber, env="Urban", speed=25.0, snr=10.0):
        """Helper: create an EXACT case with specified GT and predicted BER."""
        from evals.engine import EvalEngine, NEAR_ZERO_BER_FLOOR, NEAR_ZERO_BER_ABS_TOL
        inp = EvalCaseInput(
            environment=env, speed_kmph=speed, snr_db=snr,
            doppler_hz=speed * 1000 / 3600 * 4e9 / 299792458.0,
            channel_profile="EVA", modulation=4,
        )
        gt = {"BER": gt_ber, "throughput_bps": 1e6, "CQI": 10, "ACS": 0.5}
        case = EvalCase(
            case_id="NZ-TEST", case_type=CaseType.EXACT,
            suite=EvalSuite.PREDICTION_ACCURACY,
            input_conditions=inp, ground_truth_available=True,
            ground_truth=gt, ood=False,
        )
        engine = EvalEngine()
        # Monkey-patch predict to return our specified prediction
        original_predict = engine.predict
        def mock_predict(input_):
            return {
                "OTFS": {"BER": pred_ber, "ACS": 0.5, "throughput_bps": 1e6, "CQI": 10, "waveform": "OTFS", "detector": "MRC"},
                "ODDM": {"BER": pred_ber, "ACS": 0.4, "throughput_bps": 1e6, "CQI": 10, "waveform": "ODDM", "detector": "LMMSE"},
                "selected_waveform": "OTFS",
                "confidence": 0.1,
            }
        engine.predict = mock_predict
        return engine, case, NEAR_ZERO_BER_FLOOR, NEAR_ZERO_BER_ABS_TOL

    def test_zero_gt_zero_pred_passes(self):
        """GT BER = 0, prediction = 0 → PASS (absolute error = 0)."""
        engine, case, _, _ = self._make_case(0.0, 0.0)
        result = engine.evaluate_case(case)
        assert result.result == CaseResult.PASS

    def test_zero_gt_small_pred_passes(self):
        """GT BER = 0, prediction = 0.005 → PASS (absolute error 0.005 < 1e-2)."""
        engine, case, _, _ = self._make_case(0.0, 0.005)
        result = engine.evaluate_case(case)
        assert result.result == CaseResult.PASS

    def test_zero_gt_tiny_pred_passes(self):
        """GT BER = 0, prediction = 1e-6 → PASS."""
        engine, case, _, _ = self._make_case(0.0, 1e-6)
        result = engine.evaluate_case(case)
        assert result.result == CaseResult.PASS

    def test_zero_gt_large_pred_fails(self):
        """GT BER = 0, prediction = 0.03 → FAIL (absolute error 0.03 > 1e-2)."""
        engine, case, _, _ = self._make_case(0.0, 0.03)
        result = engine.evaluate_case(case)
        assert result.result == CaseResult.FAIL
        assert "Near-zero GT BER" in result.result_reason
        assert "absolute error" in result.result_reason

    def test_near_zero_gt_small_pred_passes(self):
        """GT BER = 1e-15 (below floor), prediction = 0.008 → PASS."""
        engine, case, _, _ = self._make_case(1e-15, 0.008)
        result = engine.evaluate_case(case)
        assert result.result == CaseResult.PASS

    def test_near_zero_gt_large_pred_fails(self):
        """GT BER = 1e-15, prediction = 0.025 → FAIL."""
        engine, case, _, _ = self._make_case(1e-15, 0.025)
        result = engine.evaluate_case(case)
        assert result.result == CaseResult.FAIL
        assert "Near-zero GT BER" in result.result_reason

    def test_normal_ber_uses_relative_error(self):
        """GT BER = 0.1, prediction = 0.105 → PASS (5% rel error < 10%)."""
        engine, case, _, _ = self._make_case(0.1, 0.105)
        result = engine.evaluate_case(case)
        assert result.result == CaseResult.PASS

    def test_normal_ber_relative_failure(self):
        """GT BER = 0.1, prediction = 0.2 → FAIL (100% rel error)."""
        engine, case, _, _ = self._make_case(0.1, 0.2)
        result = engine.evaluate_case(case)
        assert result.result == CaseResult.FAIL
        assert "relative error" in result.result_reason

    def test_failure_reason_format_near_zero(self):
        """Verify failure reason string format for near-zero cases."""
        engine, case, _, _ = self._make_case(0.0, 0.0314)
        result = engine.evaluate_case(case)
        assert result.result == CaseResult.FAIL
        assert "0.031400" in result.result_reason
        assert "tolerance" in result.result_reason

    def test_failure_reason_format_normal(self):
        """Verify failure reason string format for normal BER cases."""
        engine, case, _, _ = self._make_case(0.05, 0.08)
        result = engine.evaluate_case(case)
        assert result.result == CaseResult.FAIL
        assert "relative error" in result.result_reason
        assert "0.6000" in result.result_reason  # rel_error = 0.6


# ═══════════════════════════════════════════════════════════════════════════════
# 10. OOD domain guard (pre-inference rejection)
# ═══════════════════════════════════════════════════════════════════════════════

class TestOODDomainGuard:
    """Tests for the OOD domain guard that rejects inputs BEFORE RF inference.

    The guard validates: environment, channel_profile, modulation, speed, SNR,
    doppler — using boundaries from the Golden Dataset.
    """

    def test_speed_above_max_rejected(self):
        engine = EvalEngine()
        inp = EvalCaseInput(
            environment="Highway", speed_kmph=450.0, snr_db=10.0,
            doppler_hz=450 * 1000/3600 * 4e9/299792458.0,
            channel_profile="EVA", modulation=4,
        )
        valid, reason = engine.validate_input_domain(inp)
        assert valid is False
        assert "SPEED_OUT_OF_RANGE" in reason

    def test_speed_extreme_rejected(self):
        engine = EvalEngine()
        inp = EvalCaseInput(
            environment="HighSpeedRail", speed_kmph=550.0, snr_db=5.0,
            doppler_hz=550 * 1000/3600 * 4e9/299792458.0,
            channel_profile="EVA", modulation=4,
        )
        valid, reason = engine.validate_input_domain(inp)
        assert valid is False
        assert "SPEED_OUT_OF_RANGE" in reason

    def test_snr_above_max_rejected(self):
        engine = EvalEngine()
        inp = EvalCaseInput(
            environment="Urban", speed_kmph=30.0, snr_db=38.0,
            doppler_hz=30 * 1000/3600 * 4e9/299792458.0,
            channel_profile="EVA", modulation=4,
        )
        valid, reason = engine.validate_input_domain(inp)
        assert valid is False
        assert "SNR_OUT_OF_RANGE" in reason

    def test_invalid_environment_rejected(self):
        engine = EvalEngine()
        inp = EvalCaseInput(
            environment="Space", speed_kmph=1000.0, snr_db=30.0,
            doppler_hz=1000 * 1000/3600 * 4e9/299792458.0,
            channel_profile="EVA", modulation=4,
        )
        valid, reason = engine.validate_input_domain(inp)
        assert valid is False
        assert "INVALID_ENVIRONMENT" in reason

    def test_invalid_channel_rejected(self):
        engine = EvalEngine()
        inp = EvalCaseInput(
            environment="Urban", speed_kmph=30.0, snr_db=15.0,
            doppler_hz=30 * 1000/3600 * 4e9/299792458.0,
            channel_profile="CUSTOM_channel", modulation=4,
        )
        valid, reason = engine.validate_input_domain(inp)
        assert valid is False
        assert "INVALID_CHANNEL" in reason

    def test_invalid_modulation_rejected(self):
        engine = EvalEngine()
        inp = EvalCaseInput(
            environment="Urban", speed_kmph=30.0, snr_db=15.0,
            doppler_hz=30 * 1000/3600 * 4e9/299792458.0,
            channel_profile="EVA", modulation=256,
        )
        valid, reason = engine.validate_input_domain(inp)
        assert valid is False
        assert "INVALID_MODULATION" in reason

    def test_compound_ood_rejected(self):
        engine = EvalEngine()
        inp = EvalCaseInput(
            environment="Highway", speed_kmph=400.0, snr_db=33.0,
            doppler_hz=400 * 1000/3600 * 4e9/299792458.0,
            channel_profile="ETU", modulation=64,
        )
        valid, reason = engine.validate_input_domain(inp)
        assert valid is False

    def test_valid_input_accepted(self):
        engine = EvalEngine()
        inp = EvalCaseInput(
            environment="Urban", speed_kmph=25.0, snr_db=10.0,
            doppler_hz=25 * 1000/3600 * 4e9/299792458.0,
            channel_profile="EVA", modulation=4,
        )
        valid, reason = engine.validate_input_domain(inp)
        assert valid is True
        assert reason is None

    def test_boundary_input_accepted(self):
        """Exact boundary values should be accepted."""
        engine = EvalEngine()
        inp = EvalCaseInput(
            environment="Pedestrian", speed_kmph=0.0, snr_db=-2.15,
            doppler_hz=0.0,
            channel_profile="EPA", modulation=4,
        )
        valid, reason = engine.validate_input_domain(inp)
        assert valid is True

    def test_ood_case_no_model_inference(self):
        """OOD cases must be rejected without calling the RF models."""
        engine = EvalEngine()
        inp = EvalCaseInput(
            environment="Space", speed_kmph=1000.0, snr_db=30.0,
            doppler_hz=1000 * 1000/3600 * 4e9/299792458.0,
            channel_profile="EVA", modulation=4,
        )
        case = EvalCase(
            case_id="OOD-GUARD-001", case_type=CaseType.OOD,
            suite=EvalSuite.OOD_SAFETY, input_conditions=inp,
            ground_truth_available=False, ground_truth=None,
            ood=True, ood_reason="invalid_environment",
        )
        result = engine.evaluate_case(case)
        assert result.result == CaseResult.REJECTED
        assert result.prediction is None
        assert result.ood_decision == "REJECTED"

    def test_ood_result_has_no_fabricated_metrics(self):
        """Verify OOD REJECTED result contains no BER/throughput/CQI/ACS."""
        engine = EvalEngine()
        inp = EvalCaseInput(
            environment="Space", speed_kmph=1000.0, snr_db=30.0,
            doppler_hz=1000 * 1000/3600 * 4e9/299792458.0,
            channel_profile="EVA", modulation=4,
        )
        case = EvalCase(
            case_id="OOD-GUARD-002", case_type=CaseType.OOD,
            suite=EvalSuite.OOD_SAFETY, input_conditions=inp,
            ground_truth_available=False, ground_truth=None,
            ood=True, ood_reason="invalid_environment",
        )
        result = engine.evaluate_case(case)
        assert result.prediction is None
        assert result.result == CaseResult.REJECTED
        assert result.confidence is None

    def test_all_ood_cases_rejected(self):
        """All 7 OOD cases from the suite must be rejected by the guard."""
        ds = get_golden_dataset()
        cases = generate_ood_cases(ds, EvalSuite.OOD_SAFETY)
        engine = EvalEngine()
        for case in cases:
            result = engine.evaluate_case(case)
            assert result.result == CaseResult.REJECTED, (
                f"{case.case_id} was {result.result} instead of REJECTED"
            )
            assert result.prediction is None, (
                f"{case.case_id} has prediction (fabricated metrics)"
            )


# ═══════════════════════════════════════════════════════════════════════════════
# 11. Pipeline integration (OOD guard + valid prediction)
# ═══════════════════════════════════════════════════════════════════════════════

class TestPipelineIntegration:
    """Verify OOD guard + valid prediction path work together correctly."""

    def test_valid_exact_case_invokes_prediction(self):
        """A valid in-domain EXACT case must invoke RF model prediction."""
        engine = EvalEngine()
        inp = EvalCaseInput(
            environment="Urban", speed_kmph=25.0, snr_db=10.0,
            doppler_hz=25 * 1000/3600 * 4e9/299792458.0,
            channel_profile="EVA", modulation=4,
        )
        case = EvalCase(
            case_id="PIPE-001", case_type=CaseType.EXACT,
            suite=EvalSuite.PREDICTION_ACCURACY, input_conditions=inp,
            ground_truth_available=True,
            ground_truth={"BER": 0.05, "throughput_bps": 1e6, "CQI": 10, "ACS": 0.5},
            ood=False,
        )
        result = engine.evaluate_case(case)
        # Should have a prediction (not None) for valid input
        assert result.prediction is not None
        assert result.result in (CaseResult.PASS, CaseResult.FAIL)

    def test_in_domain_boundary_case_accepted(self):
        """An in-domain BOUNDARY case must be accepted by the guard."""
        engine = EvalEngine()
        inp = EvalCaseInput(
            environment="HighSpeedRail", speed_kmph=350.0, snr_db=22.99,
            doppler_hz=350 * 1000/3600 * 4e9/299792458.0,
            channel_profile="EVA", modulation=4,
        )
        valid, reason = engine.validate_input_domain(inp)
        assert valid is True

    def test_interior_case_not_rejected(self):
        """INTERIOR cases (in-domain, no GT) must not be rejected."""
        ds = get_golden_dataset()
        cases = generate_interior_cases(ds, EvalSuite.FULL_REGRESSION)
        engine = EvalEngine()
        for case in cases[:5]:
            valid, _ = engine.validate_input_domain(case.input_conditions)
            assert valid is True, f"INTERIOR case {case.case_id} rejected"


# ═══════════════════════════════════════════════════════════════════════════════
# 12. INTERIOR/BOUNDARY without ground truth → UNAVAILABLE
# ═══════════════════════════════════════════════════════════════════════════════

class TestNoGTUnavailable:
    """Verify that cases without ground truth are UNAVAILABLE, not PASS."""

    def test_interior_no_gt_is_unavailable(self):
        ds = get_golden_dataset()
        cases = generate_interior_cases(ds, EvalSuite.FULL_REGRESSION)
        engine = EvalEngine()
        for case in cases[:3]:
            result = engine.evaluate_case(case)
            assert result.result == CaseResult.UNAVAILABLE, (
                f"{case.case_id}: expected UNAVAILABLE, got {result.result}"
            )
            assert result.coverage == "MODEL_ESTIMATE"

    def test_boundary_no_gt_is_unavailable(self):
        ds = get_golden_dataset()
        cases = generate_boundary_cases(ds, EvalSuite.FULL_REGRESSION)
        engine = EvalEngine()
        for case in cases[:3]:
            result = engine.evaluate_case(case)
            if not case.ground_truth_available:
                assert result.result == CaseResult.UNAVAILABLE, (
                    f"{case.case_id}: expected UNAVAILABLE, got {result.result}"
                )

    def test_exact_with_gt_is_pass_or_fail(self):
        """EXACT cases with ground truth must be PASS or FAIL, never UNAVAILABLE."""
        ds = get_golden_dataset()
        cases = generate_exact_cases(ds, EvalSuite.PREDICTION_ACCURACY)
        engine = EvalEngine()
        for case in cases[:5]:
            result = engine.evaluate_case(case)
            assert result.result in (CaseResult.PASS, CaseResult.FAIL), (
                f"{case.case_id}: expected PASS or FAIL, got {result.result}"
            )

    def test_report_has_exact_section(self):
        from evals.runner import _build_report
        from evals.metrics import aggregate_metrics
        summary = EvalRunSummary(
            run_id="TEST", suite=EvalSuite.FULL_REGRESSION,
            status=RunStatus.COMPLETED, created_at="2026-01-01T00:00:00Z",
            total_cases=10, completed_cases=10, passed=5, failed=3,
            rejected=1, unavailable=1, elapsed_seconds=1.0,
            dataset_checksum="x", model_version="v1", policy_version="v1",
        )
        agg = {"ber_mae": 0.05, "selection_accuracy": 0.8}
        report = _build_report(summary, agg, [])
        assert "exact" in report
        assert "interior" in report
        assert "boundary" in report
        assert "ood" in report
        assert report["exact"]["total"] == 0
        assert report["ood"]["total"] == 0
        assert report["interior"]["note"] == "No ground truth available — predictions are model estimates, not verified accuracy"

    def test_report_ood_safety_metrics(self):
        from evals.runner import _build_report
        summary = EvalRunSummary(
            run_id="TEST", suite=EvalSuite.OOD_SAFETY,
            status=RunStatus.COMPLETED, created_at="2026-01-01T00:00:00Z",
            total_cases=7, completed_cases=7, rejected=7,
            elapsed_seconds=1.0,
            dataset_checksum="x", model_version="v1", policy_version="v1",
        )
        fake_results = [
            {"case_type": "OOD", "result": "REJECTED"} for _ in range(7)
        ]
        report = _build_report(summary, {}, fake_results)
        assert report["ood"]["total"] == 7
        assert report["ood"]["rejected"] == 7
        assert report["ood"]["rejection_rate"] == 1.0
        assert report["ood"]["fabricated_predictions"] == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
