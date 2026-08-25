"""Pydantic models for request/response validation."""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class Strategy(str, Enum):
    FIXED_OTFS = "fixed_otfs"
    FIXED_ODDM = "fixed_oddm"
    AI_ADAPTIVE = "ai_adaptive"
    ORACLE = "oracle"


class Policy(str, Enum):
    PHASE3 = "phase3"
    PHASE4 = "phase4"


class SimMode(str, Enum):
    FAST = "FAST"
    FULL = "FULL"


class SimStatus(str, Enum):
    CREATED = "CREATED"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    STOPPED = "STOPPED"
    COMPLETED = "COMPLETED"
    ERROR = "ERROR"


class SimulationStartRequest(BaseModel):
    mode: SimMode = SimMode.FAST
    scenario: str = "A"
    strategy: Strategy = Strategy.AI_ADAPTIVE
    policy: Policy = Policy.PHASE3
    seed0: int = 20260823
    duration_frames: Optional[int] = None
    environment: Optional[str] = None
    speed_kmph: Optional[float] = None
    snr_db: Optional[float] = None
    channel_profile: Optional[str] = None
    modulation: Optional[int] = None


class SimulationStatus(BaseModel):
    run_id: str
    status: SimStatus
    scenario: str
    strategy: str
    policy: str
    mode: str
    current_frame: int
    total_frames: int
    elapsed_seconds: float


class SimulationState(BaseModel):
    frame: int
    scenario_id: str
    environment: str
    speed_kmph: float
    snr_db: float
    doppler_hz: float
    channel_profile: str
    modulation: int
    waveform: str
    strategy: str


class AIInfo(BaseModel):
    selected_waveform: Optional[str] = None
    confidence: Optional[float] = None
    predicted_otfs_acs: Optional[float] = None
    predicted_oddm_acs: Optional[float] = None
    reason: Optional[str] = None
    fallback_used: bool = False


class FrameMetrics(BaseModel):
    ber: Optional[float] = None
    ser: Optional[float] = None
    per: Optional[float] = None
    throughput_bps: Optional[float] = None
    spectral_efficiency: Optional[float] = None
    cqi: Optional[float] = None
    acs: Optional[float] = None
    detector_time_ms: Optional[float] = None
    latency_ms_modeled: Optional[float] = None


class FrameResponse(BaseModel):
    run_id: str
    frame: int
    status: str
    state: SimulationState
    decision: AIInfo
    metrics: FrameMetrics
    oracle: Optional[dict] = None


class MetricsSummary(BaseModel):
    frames_processed: int
    otfs_frames: int
    oddm_frames: int
    switches: int
    mean_ber: float
    mean_throughput: float
    mean_cqi: float
    mean_acs: float
    oracle_agreement: float
    mean_acs_regret: float


class HealthResponse(BaseModel):
    status: str
    service: str
    phase: int
    policy: str
    digital_twin: str
    matlab: str
    ai_engine: str


class ConfigResponse(BaseModel):
    default_policy: str
    available_policies: list[str]
    available_strategies: list[str]
    supported_environments: list[str]
    supported_channels: list[str]
    supported_modulations: list[int]
    simulation_modes: list[str]


class ScenarioInfo(BaseModel):
    id: str
    name: str
    environment: Optional[str] = None
    description: Optional[str] = None
    duration_frames: Optional[int] = None


class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None


class WSFrameEvent(BaseModel):
    type: str
    run_id: str
    frame: int
    state: Optional[SimulationState] = None
    decision: Optional[AIInfo] = None
    metrics: Optional[FrameMetrics] = None
    status: Optional[str] = None
    error: Optional[str] = None


# ── Phase 11: Custom Evaluation ──────────────────────────────────────────────

class CustomEvaluationRequest(BaseModel):
    environment: str
    speed_kmph: float
    snr_db: float
    channel_profile: str
    modulation: int
    detector: Optional[str] = None


class PredictionUncertaintyModel(BaseModel):
    mean: float
    std: float
    p10: Optional[float] = None
    p90: Optional[float] = None


class WaveformPredictionModel(BaseModel):
    waveform: str
    detector: str
    BER: Optional[PredictionUncertaintyModel] = None
    throughput_bps: Optional[PredictionUncertaintyModel] = None
    CQI: Optional[PredictionUncertaintyModel] = None
    ACS: Optional[PredictionUncertaintyModel] = None
    PER: Optional[PredictionUncertaintyModel] = None
    spectral_efficiency: Optional[PredictionUncertaintyModel] = None


class NeighborModel(BaseModel):
    distance: float
    speed_difference: float
    snr_difference: float
    doppler_difference: float
    source_scenario: str
    source_frame: int
    environment: str
    channel_profile: str
    modulation: int
    otfs_ber: Optional[float] = None
    otfs_acs: Optional[float] = None
    oddm_ber: Optional[float] = None
    oddm_acs: Optional[float] = None


class NeighborhoodConsistencyModel(BaseModel):
    waveform: str
    predicted_acs: Optional[float] = None
    neighbor_acs_mean: Optional[float] = None
    neighbor_acs_median: Optional[float] = None
    neighbor_acs_range: Optional[list] = None
    deviation: Optional[float] = None
    consistent: Optional[bool] = None


class CustomEvaluationResponse(BaseModel):
    status: str
    coverage: str
    confidence: str
    input: dict
    nearest_neighbors: list[NeighborModel]
    predictions: dict
    consistency: dict
    decision: dict
    warnings: list[str]


class CustomSchemaResponse(BaseModel):
    supported_environments: list[str]
    supported_channel_profiles: list[str]
    supported_modulations: list[int]
    supported_detectors: list[str]
    model_targets: list[str]
    target_columns: dict
    numerical_ranges: dict
    doppler_derivation: dict
    coverage_rules: dict
    policy_version: str
    model_version: str
