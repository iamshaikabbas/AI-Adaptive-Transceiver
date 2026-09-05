"""Pydantic models for the Evals Platform."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field

from .registry import get_active_model_version


def _active_model_version() -> str:
    """Resolve the active production model version (shared registry)."""
    return get_active_model_version()


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class CaseType(str, Enum):
    EXACT = "EXACT"
    INTERIOR = "INTERIOR"
    BOUNDARY = "BOUNDARY"
    OOD = "OOD"


class CaseResult(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    REJECTED = "REJECTED"
    UNAVAILABLE = "UNAVAILABLE"


class RunStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    STOPPED = "STOPPED"


class DataSourceTag(str, Enum):
    GOLDEN = "GOLDEN"
    REFERENCE = "REFERENCE"
    AI_OUTPUT = "AI_OUTPUT"
    DERIVED = "DERIVED"


class EvalSuite(str, Enum):
    FULL_REGRESSION = "FULL_REGRESSION"
    PREDICTION_ACCURACY = "PREDICTION_ACCURACY"
    OOD_SAFETY = "OOD_SAFETY"
    ROBUSTNESS = "ROBUSTNESS"


# ---------------------------------------------------------------------------
# Golden Dataset
# ---------------------------------------------------------------------------

class GoldenDatasetManifest(BaseModel):
    name: str = "final_dataset"
    version: str = "phase6"
    source_path: str
    row_count: int
    column_count: int
    columns: list[str]
    scenario_count: int
    scenario_ids: list[str]
    strategies: list[str]
    environments: list[str]
    channel_profiles: list[str]
    modulations: list[int]
    waveform_types: list[str]
    snr_range: list[float]
    speed_range: list[float]
    doppler_range: list[float]
    checksum_md5: str
    checksum_verified: bool
    creation_timestamp: Optional[str] = None
    policy_version: str
    provenance: str = "MATLAB Digital Twin validated simulation pipeline"
    generation_source: str = "phase6_final_dataset.py"
    evaluation_eligible: bool = True


# ---------------------------------------------------------------------------
# Evaluation Cases
# ---------------------------------------------------------------------------

class EvalCaseInput(BaseModel):
    environment: str
    speed_kmph: float
    snr_db: float
    doppler_hz: float
    channel_profile: str
    modulation: int
    detector: Optional[str] = None


class EvalCase(BaseModel):
    case_id: str
    case_type: CaseType
    suite: EvalSuite
    input_conditions: EvalCaseInput
    ground_truth_available: bool = False
    ground_truth_source: Optional[DataSourceTag] = None
    ground_truth: Optional[dict] = None
    expected_behavior: Optional[str] = None
    ood: bool = False
    ood_reason: Optional[str] = None


class EvalCaseResult(BaseModel):
    case_id: str
    case_type: CaseType
    suite: EvalSuite
    input_conditions: EvalCaseInput
    ground_truth_available: bool
    ground_truth_source: Optional[DataSourceTag] = None
    ground_truth: Optional[dict] = None
    prediction: Optional[dict] = None
    prediction_source: DataSourceTag = DataSourceTag.AI_OUTPUT
    confidence: Optional[float] = None
    coverage: Optional[str] = None
    ood: bool = False
    ood_decision: Optional[str] = None
    ood_reason: Optional[str] = None
    result: CaseResult
    result_reason: Optional[str] = None
    metrics: Optional[dict] = None
    elapsed_seconds: Optional[float] = None
    timestamp: Optional[str] = None


# ---------------------------------------------------------------------------
# Evaluation Run
# ---------------------------------------------------------------------------

class EvalRunConfig(BaseModel):
    suite: EvalSuite
    model_version: str = Field(default_factory=_active_model_version)
    policy_version: str = "phase3"
    dataset_version: str = "phase6"
    random_seed: int = 42
    update_interval_seconds: float = 1.0


class EvalRunSummary(BaseModel):
    run_id: str
    suite: EvalSuite
    status: RunStatus
    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    elapsed_seconds: float = 0.0
    total_cases: int = 0
    completed_cases: int = 0
    passed: int = 0
    failed: int = 0
    rejected: int = 0
    unavailable: int = 0
    progress_pct: float = 0.0
    current_case_id: Optional[str] = None
    current_case_type: Optional[CaseType] = None
    dataset_checksum: str = ""
    model_version: str = Field(default_factory=_active_model_version)
    policy_version: str = "phase3"


class EvalRunResult(BaseModel):
    run_config: EvalRunConfig
    summary: EvalRunSummary
    metrics: dict[str, Any] = {}
    case_results: list[EvalCaseResult] = []
    graph_data: dict[str, Any] = {}
    report: Optional[dict[str, Any]] = None


# ---------------------------------------------------------------------------
# WebSocket Events
# ---------------------------------------------------------------------------

class WSEvalEvent(BaseModel):
    type: str
    run_id: str
    timestamp: str
    progress_pct: float = 0.0
    completed_cases: int = 0
    total_cases: int = 0
    elapsed_seconds: float = 0.0
    current_case_id: Optional[str] = None
    current_case_type: Optional[CaseType] = None
    case_result: Optional[EvalCaseResult] = None
    running_metrics: Optional[dict[str, Any]] = None
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# Regression Comparison
# ---------------------------------------------------------------------------

class RegressionComparison(BaseModel):
    run_a_id: str
    run_b_id: str
    run_a_summary: EvalRunSummary
    run_b_summary: EvalRunSummary
    metric_comparison: list[dict[str, Any]]
    interpretation: str
    improved: list[str]
    degraded: list[str]
    unchanged: list[str]
