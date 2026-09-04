"""Phase 11 — Deployment Data Service.

Hybrid model-based deployment: validated dataset + Phase-3 models.
No MATLAB required at runtime.

Provides:
  - Exact lookup (dataset row retrieval)
  - Nearest-neighbor retrieval (normalized distance)
  - RF model regression (OTFS + ODDM) via shared model registry
  - RF uncertainty estimation (tree dispersion)
  - Neighborhood consistency analysis
  - Coverage / OOD detection
  - Confidence classification
  - AI waveform decision

Source: final_dataset.csv (Phase 6, frozen checksum faa877a248c0f599a87f21dabf4df358)
Models: versioned via otfs_ai_pipeline/model_registry.py
        (default MODEL_VERSION=v4-b1; MODEL_VERSION=v2 for rollback;
        missing active-version artifacts fail loudly, never fall back)
Policy: adaptive_config_v2.json (Phase 3, canonical)
"""

from __future__ import annotations

import csv
import importlib.util
import json
import math
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import joblib
import numpy as np

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_MATLAB_DIR   = _PROJECT_ROOT / "OTFS MRC detection MATLAB code"
_CSV_PATH     = _MATLAB_DIR / "Results" / "FinalEvaluation" / "final_dataset.csv"
_MODELS_DIR   = _MATLAB_DIR / "otfs_ai_pipeline" / "models" / "metric_models_v2"
_META_PATH    = _MODELS_DIR / "metric_models_v2_meta.json"
_CONFIG_PATH  = _MATLAB_DIR / "adaptive_config_v2.json"

# Carrier frequency (Hz) — constant across all dataset rows
_CARRIER_FREQ_HZ = 4_000_000_000.0
_BANDWIDTH_HZ    = 480_000.0
_SPEED_OF_LIGHT  = 299_792_458.0  # m/s

# ---------------------------------------------------------------------------
# Default Phase-3 policy (fallback if config missing)
# ---------------------------------------------------------------------------
_DEFAULT_POLICY = {
    "objective": "ACS",
    "min_confidence": 0.0,
    "switch_margin_acs": 0.01,
    "switch_margin_rel": 0.02,
    "min_dwell_frames": 3,
}

# ---------------------------------------------------------------------------
# Model versioning -- shared source of truth:
# OTFS MRC detection MATLAB code/otfs_ai_pipeline/model_registry.py
# ---------------------------------------------------------------------------
_AI_PIPELINE_DIR = _MATLAB_DIR / "otfs_ai_pipeline"
_MODEL_REGISTRY = None


def _model_registry():
    """Import the shared model_registry module (resolved by absolute path)."""
    global _MODEL_REGISTRY
    if _MODEL_REGISTRY is None:
        spec = importlib.util.spec_from_file_location(
            "model_registry", _AI_PIPELINE_DIR / "model_registry.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _MODEL_REGISTRY = module
    return _MODEL_REGISTRY

# ---------------------------------------------------------------------------
# Internal data structures
# ---------------------------------------------------------------------------

@dataclass
class DatasetRow:
    """One row from final_dataset.csv."""
    scenario_id: str
    frame: int
    environment: str
    speed_kmph: float
    snr_db: float
    doppler_hz: float
    channel_profile: str
    modulation: int
    strategy: str
    waveform: str
    detector: str
    # Metrics
    BER: Optional[float] = None
    SER: Optional[float] = None
    PER: Optional[float] = None
    throughput_bps: Optional[float] = None
    spectral_efficiency: Optional[float] = None
    CQI: Optional[float] = None
    ACS: Optional[float] = None
    detector_time_ms: Optional[float] = None
    wall_clock_ms: Optional[float] = None
    # AI predictions (ai_adaptive rows only)
    predicted_OTFS_BER: Optional[float] = None
    predicted_ODDM_BER: Optional[float] = None
    predicted_OTFS_ACS: Optional[float] = None
    predicted_ODDM_ACS: Optional[float] = None
    predicted_OTFS_throughput: Optional[float] = None
    predicted_ODDM_throughput: Optional[float] = None
    predicted_OTFS_CQI: Optional[float] = None
    predicted_ODDM_CQI: Optional[float] = None
    selected_waveform: Optional[str] = None
    oracle_waveform: Optional[str] = None
    oracle_BER: Optional[float] = None
    oracle_ACS: Optional[float] = None
    ACS_regret: Optional[float] = None
    BER_regret: Optional[float] = None
    decision_correct: Optional[float] = None
    confidence: Optional[float] = None
    switch_reason: Optional[str] = None
    switched: Optional[bool] = None
    # Raw dict for anything else
    _raw: dict = field(default_factory=dict, repr=False)


@dataclass
class Neighbor:
    """A nearest neighbor result."""
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


@dataclass
class PredictionUncertainty:
    """RF uncertainty for a single target."""
    mean: float
    std: float
    p10: Optional[float] = None
    p90: Optional[float] = None


@dataclass
class WaveformPrediction:
    """Model predictions for one waveform (OTFS or ODDM)."""
    waveform: str
    detector: str
    BER: Optional[PredictionUncertainty] = None
    throughput_bps: Optional[PredictionUncertainty] = None
    CQI: Optional[PredictionUncertainty] = None
    ACS: Optional[PredictionUncertainty] = None
    PER: Optional[PredictionUncertainty] = None
    spectral_efficiency: Optional[PredictionUncertainty] = None


@dataclass
class NeighborhoodConsistency:
    """Consistency analysis for one waveform."""
    waveform: str
    predicted_acs: Optional[float] = None
    neighbor_acs_mean: Optional[float] = None
    neighbor_acs_median: Optional[float] = None
    neighbor_acs_min: Optional[float] = None
    neighbor_acs_max: Optional[float] = None
    deviation: Optional[float] = None  # predicted - neighbor_mean
    consistent: Optional[bool] = None  # |deviation| < 0.10


@dataclass
class EvaluationResult:
    """Full evaluation result."""
    coverage: str  # EXACT / COVERED / NEAR_BOUNDARY / OOD
    confidence: str  # HIGH / MEDIUM / LOW / UNAVAILABLE
    input_conditions: dict
    nearest_neighbors: list[Neighbor]
    otfs_prediction: Optional[WaveformPrediction]
    oddm_prediction: Optional[WaveformPrediction]
    otfs_consistency: Optional[NeighborhoodConsistency]
    oddm_consistency: Optional[NeighborhoodConsistency]
    decision: dict  # Phase-3 AI decision
    warnings: list[str]


# ---------------------------------------------------------------------------
# Doppler derivation (deterministic, matches dataset pattern)
# ---------------------------------------------------------------------------

def derive_doppler_hz(speed_kmph: float, environment: str) -> float:
    """Compute Doppler shift from speed and environment.

    Matches the MATLAB Digital Twin derivation:
      doppler = speed_kmph * (1000/3600) * carrier_freq / speed_of_light

    Carrier frequency is 4 GHz (constant across all scenarios).
    """
    speed_ms = speed_kmph * 1000.0 / 3600.0
    return speed_ms * _CARRIER_FREQ_HZ / _SPEED_OF_LIGHT


# ---------------------------------------------------------------------------
# Main service class
# ---------------------------------------------------------------------------

class DeploymentDataService:
    """Phase 11 deployment data service.

    Loads frozen dataset + Phase-3 models on construction.
    Provides lookup, neighborhood, regression, OOD, confidence, and AI decision.
    """

    def __init__(self):
        self._loaded = False
        self._rows: list[DatasetRow] = []
        self._by_scenario_frame: dict[tuple[str, int], dict[str, DatasetRow]] = {}
        self._group_keys: list[tuple[str, int]] = []  # unique (scenario, frame)
        # Feature ranges (from dataset)
        self._feature_ranges: dict[str, dict[str, float]] = {}
        self._categorical_values: dict[str, list[str]] = {}
        # Phase-3 models
        self._models: dict[str, Any] = {}
        self._meta: dict = {}
        self.model_version: str = ""
        self._policy: dict = dict(_DEFAULT_POLICY)
        # Nearest-neighbor distance distribution (for OOD thresholds)
        self._nn_distances_sorted: list[float] = []
        # Channel profile → (delay_spread_taps, num_paths) lookup
        self._channel_params: dict[str, dict[str, Any]] = {}
        # Fixed parameters for model input
        self._fixed_params: dict[str, float] = {}
        # Load everything
        self._load()

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def _load(self):
        """Load dataset, models, and config."""
        self._load_dataset()
        self._load_models()
        self._load_config()
        self._build_feature_ranges()
        self._build_channel_params()
        self._build_nn_distance_distribution()
        self._loaded = True

    def _load_dataset(self):
        """Load final_dataset.csv into memory."""
        with open(_CSV_PATH, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for raw in reader:
                row = DatasetRow(
                    scenario_id=raw["scenario_id"],
                    frame=int(raw["frame"]),
                    environment=raw["environment"],
                    speed_kmph=float(raw["speed_kmph"]),
                    snr_db=float(raw["snr_db"]),
                    doppler_hz=float(raw["doppler_hz"]),
                    channel_profile=raw["channel_profile"],
                    modulation=int(raw["modulation"]),
                    strategy=raw["strategy"],
                    waveform=raw["waveform"],
                    detector=raw["detector"],
                    BER=_opt_float(raw.get("BER")),
                    SER=_opt_float(raw.get("SER")),
                    PER=_opt_float(raw.get("PER")),
                    throughput_bps=_opt_float(raw.get("throughput_bps")),
                    spectral_efficiency=_opt_float(raw.get("spectral_efficiency")),
                    CQI=_opt_float(raw.get("CQI")),
                    ACS=_opt_float(raw.get("ACS")),
                    detector_time_ms=_opt_float(raw.get("detector_time_ms")),
                    wall_clock_ms=_opt_float(raw.get("wall_clock_ms")),
                    predicted_OTFS_BER=_opt_float(raw.get("predicted_OTFS_BER")),
                    predicted_ODDM_BER=_opt_float(raw.get("predicted_ODDM_BER")),
                    predicted_OTFS_ACS=_opt_float(raw.get("predicted_OTFS_ACS")),
                    predicted_ODDM_ACS=_opt_float(raw.get("predicted_ODDM_ACS")),
                    predicted_OTFS_throughput=_opt_float(raw.get("predicted_OTFS_throughput")),
                    predicted_ODDM_throughput=_opt_float(raw.get("predicted_ODDM_throughput")),
                    predicted_OTFS_CQI=_opt_float(raw.get("predicted_OTFS_CQI")),
                    predicted_ODDM_CQI=_opt_float(raw.get("predicted_ODDM_CQI")),
                    selected_waveform=raw.get("selected_waveform") or None,
                    oracle_waveform=raw.get("oracle_waveform") or None,
                    oracle_BER=_opt_float(raw.get("oracle_BER")),
                    oracle_ACS=_opt_float(raw.get("oracle_ACS")),
                    ACS_regret=_opt_float(raw.get("ACS_regret")),
                    BER_regret=_opt_float(raw.get("BER_regret")),
                    decision_correct=_opt_float(raw.get("decision_correct")),
                    confidence=_opt_float(raw.get("confidence")),
                    switch_reason=raw.get("switch_reason") or None,
                    switched=raw.get("switched") in ("1", "True", "true"),
                    _raw=raw,
                )
                self._rows.append(row)
                key = (row.scenario_id, row.frame)
                if key not in self._by_scenario_frame:
                    self._by_scenario_frame[key] = {}
                    self._group_keys.append(key)
                self._by_scenario_frame[key][row.strategy] = row

        self._group_keys.sort()

    def _load_models(self):
        """Load active-version regressors and metadata.

        Artifacts are resolved by the shared model_registry (MODEL_VERSION,
        default v4-b1). A missing artifact for the active version raises
        explicitly -- there is no silent fallback to metric_models_v2.
        """
        registry = _model_registry()
        self.model_version = registry.get_active_model_version()
        artifacts = registry.validate_active_version()
        with open(_META_PATH, encoding="utf-8") as f:
            self._meta = json.load(f)
        for target_name in self._meta["targets"].keys():
            self._models[target_name] = joblib.load(artifacts[target_name])

    def _load_config(self):
        """Load Phase-3 adaptive config."""
        if _CONFIG_PATH.exists():
            try:
                with open(_CONFIG_PATH, encoding="utf-8") as f:
                    cfg = json.load(f)
                for k in _DEFAULT_POLICY:
                    if k in cfg:
                        self._policy[k] = cfg[k]
            except (json.JSONDecodeError, ValueError):
                pass

    def _build_feature_ranges(self):
        """Compute min/max for numerical features from the dataset."""
        num_features = self._meta["features_num"]
        cat_features = self._meta["features_cat"]

        for feat in num_features:
            vals = []
            for row in self._rows:
                raw_val = row._raw.get(feat, "")
                if raw_val not in ("", "nan", "None"):
                    try:
                        vals.append(float(raw_val))
                    except (ValueError, TypeError):
                        pass
            if vals:
                self._feature_ranges[feat] = {
                    "min": min(vals),
                    "max": max(vals),
                    "range": max(vals) - min(vals),
                }
            else:
                self._feature_ranges[feat] = {"min": 0.0, "max": 0.0, "range": 1.0}

        for feat in cat_features:
            unique_vals = sorted(set(row._raw.get(feat, "") for row in self._rows))
            self._categorical_values[feat] = unique_vals

        # modulation is in features_num but is a discrete input for validation
        mod_vals = sorted(set(int(float(row._raw.get("modulation", "0")))
                              for row in self._rows
                              if row._raw.get("modulation", "") not in ("", "nan")))
        self._categorical_values["modulation_int"] = mod_vals

    def _build_channel_params(self):
        """Derive delay_spread_taps and num_paths from channel_profile + environment."""
        combos: dict[tuple[str, str], dict[str, Any]] = {}
        for row in self._rows:
            key = (row.environment, row.channel_profile)
            if key not in combos:
                combos[key] = {
                    "delay_spread_taps_values": set(),
                    "num_paths_values": set(),
                }
            ds = row._raw.get("delay_spread_taps", "")
            np_ = row._raw.get("num_paths", "")
            if ds not in ("", "nan"):
                combos[key]["delay_spread_taps_values"].add(int(float(ds)))
            if np_ not in ("", "nan"):
                combos[key]["num_paths_values"].add(int(float(np_)))

        # For each (environment, channel_profile) combo, pick the most common values
        for (env, ch), info in combos.items():
            ds_vals = info["delay_spread_taps_values"]
            np_vals = info["num_paths_values"]
            self._channel_params[f"{env}|{ch}"] = {
                "delay_spread_taps": max(ds_vals) if ds_vals else 1,
                "num_paths": max(np_vals) if np_vals else 9,
            }

        # Fallback for unknown combos
        self._channel_params["__default__"] = {"delay_spread_taps": 1, "num_paths": 9}

        # Also store per-environment defaults (for fallback)
        env_defaults: dict[str, dict] = {}
        for row in self._rows:
            env = row.environment
            if env not in env_defaults:
                env_defaults[env] = {"delay_spread_taps": set(), "num_paths": set()}
            ds = row._raw.get("delay_spread_taps", "")
            np_ = row._raw.get("num_paths", "")
            if ds not in ("", "nan"):
                env_defaults[env]["delay_spread_taps"].add(int(float(ds)))
            if np_ not in ("", "nan"):
                env_defaults[env]["num_paths"].add(int(float(np_)))

        for env, info in env_defaults.items():
            ds_vals = info["delay_spread_taps"]
            np_vals = info["num_paths"]
            self._channel_params[f"{env}|__default__"] = {
                "delay_spread_taps": max(ds_vals) if ds_vals else 1,
                "num_paths": max(np_vals) if np_vals else 9,
            }

    def _build_nn_distance_distribution(self):
        """Pre-compute nearest-neighbor distance distribution for OOD thresholds.

        For each unique (environment, channel_profile, modulation) group,
        compute the mean nearest-neighbor distance within that group.
        Then build a sorted list of all pairwise normalized distances for
        empirical percentile lookup.
        """
        all_distances: list[float] = []

        for gk in self._group_keys:
            strats = self._by_scenario_frame[gk]
            if "fixed_otfs" not in strats:
                continue
            row = strats["fixed_otfs"]
            neighbors = self._find_nearest_neighbors(row, exclude_self=True, k=1)
            if neighbors:
                all_distances.append(neighbors[0].distance)

        all_distances.sort()
        self._nn_distances_sorted = all_distances

    # ------------------------------------------------------------------
    # Query schema
    # ------------------------------------------------------------------

    def get_schema(self) -> dict:
        """Return supported input schema for frontend dynamic form generation."""
        num_ranges = {}
        for feat in self._meta["features_num"]:
            r = self._feature_ranges.get(feat, {})
            num_ranges[feat] = {"min": r.get("min", 0), "max": r.get("max", 0)}

        return {
            "supported_environments": self._categorical_values.get("environment", []),
            "supported_channel_profiles": self._categorical_values.get("channel_profile", []),
            "supported_modulations": [int(m) for m in self._categorical_values.get("modulation", [])],
            "supported_detectors": ["MRC", "LMMSE"],
            "model_targets": list(self._meta["targets"].keys()),
            "target_columns": {
                t: info["column"] for t, info in self._meta["targets"].items()
            },
            "numerical_ranges": {
                "speed_kmph": num_ranges.get("speed_kmph", {}),
                "snr_db": num_ranges.get("snr_db", {}),
            },
            "doppler_derivation": {
                "method": "deterministic",
                "formula": "speed_kmph * 1000/3600 * 4e9 / speed_of_light",
                "note": "Doppler is derived from speed and environment; not independently specified",
            },
            "coverage_rules": {
                "EXACT": "Exact validated operating point exists in dataset",
                "COVERED": "Inside observed feature envelope, close to validated neighbors",
                "NEAR_BOUNDARY": "Inside broad ranges but sparse neighborhood or elevated distance",
                "OOD": "Outside validated/model-supported region",
            },
            "policy_version": "phase3",
            "model_version": self.model_version,
        }

    # ------------------------------------------------------------------
    # Query validation
    # ------------------------------------------------------------------

    def validate_query(self, query: dict) -> tuple[bool, list[str]]:
        """Validate a custom evaluation query. Returns (is_valid, errors)."""
        errors = []

        # Required fields
        required = ["environment", "speed_kmph", "snr_db", "channel_profile", "modulation"]
        for field in required:
            if field not in query or query[field] is None:
                errors.append(f"Missing required field: {field}")

        if errors:
            return False, errors

        # Environment
        valid_envs = self._categorical_values.get("environment", [])
        if query["environment"] not in valid_envs:
            errors.append(f"Invalid environment: {query['environment']}. Supported: {valid_envs}")

        # Channel profile
        valid_chs = self._categorical_values.get("channel_profile", [])
        if query["channel_profile"] not in valid_chs:
            errors.append(f"Invalid channel_profile: {query['channel_profile']}. Supported: {valid_chs}")

        # Modulation
        valid_mods = self._categorical_values.get("modulation_int",
                    [int(m) for m in self._categorical_values.get("modulation", [])])
        try:
            mod = int(query["modulation"])
            if mod not in valid_mods:
                errors.append(f"Invalid modulation: {mod}. Supported: {valid_mods}")
        except (ValueError, TypeError):
            errors.append(f"Modulation must be an integer. Got: {query['modulation']}")

        # Speed
        try:
            speed = float(query["speed_kmph"])
            if speed < 0:
                errors.append(f"Speed must be >= 0. Got: {speed}")
            if math.isnan(speed) or math.isinf(speed):
                errors.append(f"speed_kmph must be a finite number. Got: {query['speed_kmph']}")
        except (ValueError, TypeError):
            errors.append(f"speed_kmph must be numeric. Got: {query['speed_kmph']}")

        # SNR
        try:
            snr = float(query["snr_db"])
            if math.isnan(snr) or math.isinf(snr):
                errors.append(f"snr_db must be a finite number. Got: {query['snr_db']}")
        except (ValueError, TypeError):
            errors.append(f"snr_db must be numeric. Got: {query['snr_db']}")

        # Detector (optional, informational only — not a model input)
        detector = query.get("detector")
        if detector is not None and detector not in ("MRC", "LMMSE"):
            errors.append(f"Invalid detector: {detector}. Supported: MRC, LMMSE")

        return len(errors) == 0, errors

    # ------------------------------------------------------------------
    # Exact lookup
    # ------------------------------------------------------------------

    def find_exact_match(self, query: dict) -> Optional[dict]:
        """Find an exact match in the dataset.

        Returns the operating point data if found, None otherwise.
        """
        env = query["environment"]
        speed = float(query["speed_kmph"])
        snr = float(query["snr_db"])
        ch = query["channel_profile"]
        mod = int(query["modulation"])

        for gk in self._group_keys:
            strats = self._by_scenario_frame[gk]
            ref = next(iter(strats.values()))
            if (ref.environment == env
                    and abs(ref.speed_kmph - speed) < 1e-6
                    and abs(ref.snr_db - snr) < 1e-6
                    and ref.channel_profile == ch
                    and ref.modulation == mod):
                # Found exact match — return both OTFS and ODDM measured values
                result = {
                    "source_scenario": ref.scenario_id,
                    "source_frame": ref.frame,
                    "conditions": {
                        "environment": env,
                        "speed_kmph": speed,
                        "snr_db": snr,
                        "doppler_hz": ref.doppler_hz,
                        "channel_profile": ch,
                        "modulation": mod,
                    },
                    "OTFS": {},
                    "ODDM": {},
                }
                if "fixed_otfs" in strats:
                    o = strats["fixed_otfs"]
                    result["OTFS"] = {
                        "BER": o.BER, "SER": o.SER, "PER": o.PER,
                        "throughput_bps": o.throughput_bps,
                        "spectral_efficiency": o.spectral_efficiency,
                        "CQI": o.CQI, "ACS": o.ACS,
                        "detector": o.detector,
                    }
                if "fixed_oddm" in strats:
                    d = strats["fixed_oddm"]
                    result["ODDM"] = {
                        "BER": d.BER, "SER": d.SER, "PER": d.PER,
                        "throughput_bps": d.throughput_bps,
                        "spectral_efficiency": d.spectral_efficiency,
                        "CQI": d.CQI, "ACS": d.ACS,
                        "detector": d.detector,
                    }
                return result
        return None

    # ------------------------------------------------------------------
    # Nearest neighbors
    # ------------------------------------------------------------------

    def _normalize_distance(self, query_val: float, feat_range: dict) -> float:
        """Normalized distance for a single numerical feature.

        normalized_distance = abs(query - value) / training_range
        If range is 0 (constant feature), distance is 0.
        """
        rng = feat_range.get("range", 1.0)
        if rng < 1e-12:
            return 0.0
        return abs(query_val) / rng  # query_val is already the difference

    def _compute_distance(
        self,
        query_speed: float,
        query_snr: float,
        query_doppler: float,
        row_speed: float,
        row_snr: float,
        row_doppler: float,
    ) -> tuple[float, float, float, float]:
        """Compute normalized distance between query and a dataset row.

        Weights are 1/N per dimension (equal weighting).
        Returns (total_distance, speed_dist, snr_dist, doppler_dist).
        """
        speed_range = self._feature_ranges.get("speed_kmph", {"range": 1.0})
        snr_range = self._feature_ranges.get("snr_db", {"range": 1.0})
        doppler_range = self._feature_ranges.get("doppler_hz", {"range": 1.0})

        speed_d = abs(query_speed - row_speed) / max(speed_range["range"], 1e-12)
        snr_d = abs(query_snr - row_snr) / max(snr_range["range"], 1e-12)
        doppler_d = abs(query_doppler - row_doppler) / max(doppler_range["range"], 1e-12)

        # Equal weighting across 3 dynamic numerical features
        total = (speed_d + snr_d + doppler_d) / 3.0
        return total, speed_d, snr_d, doppler_d

    def _find_nearest_neighbors(
        self,
        reference_row: DatasetRow,
        exclude_self: bool = True,
        k: int = 5,
    ) -> list[Neighbor]:
        """Find k nearest neighbors for a reference row within same categorical group.

        Only compares against rows with same environment, channel_profile, modulation.
        """
        env = reference_row.environment
        ch = reference_row.channel_profile
        mod = reference_row.modulation
        speed = reference_row.speed_kmph
        snr = reference_row.snr_db
        doppler = reference_row.doppler_hz

        candidates: list[Neighbor] = []

        for gk in self._group_keys:
            strats = self._by_scenario_frame[gk]
            if "fixed_otfs" not in strats:
                continue
            ref = strats["fixed_otfs"]

            # Categorical must match
            if ref.environment != env or ref.channel_profile != ch or ref.modulation != mod:
                continue

            # Skip self
            if exclude_self and ref.scenario_id == reference_row.scenario_id and ref.frame == reference_row.frame:
                continue

            total_d, speed_d, snr_d, doppler_d = self._compute_distance(
                speed, snr, doppler,
                ref.speed_kmph, ref.snr_db, ref.doppler_hz,
            )

            oddm = strats.get("fixed_oddm")
            neighbors = Neighbor(
                distance=round(total_d, 6),
                speed_difference=round(ref.speed_kmph - speed, 4),
                snr_difference=round(ref.snr_db - snr, 4),
                doppler_difference=round(ref.doppler_hz - doppler, 4),
                source_scenario=ref.scenario_id,
                source_frame=ref.frame,
                environment=ref.environment,
                channel_profile=ref.channel_profile,
                modulation=ref.modulation,
                otfs_ber=ref.BER,
                otfs_acs=ref.ACS,
                oddm_ber=oddm.BER if oddm else None,
                oddm_acs=oddm.ACS if oddm else None,
            )
            candidates.append(neighbors)

        candidates.sort(key=lambda n: n.distance)
        return candidates[:k]

    def find_nearest_neighbors(
        self,
        query: dict,
        k: int = 5,
    ) -> list[Neighbor]:
        """Find k nearest neighbors for a custom query.

        Creates a synthetic reference row from query, then searches.
        """
        speed = float(query["speed_kmph"])
        snr = float(query["snr_db"])
        doppler = derive_doppler_hz(speed, query["environment"])

        ref = DatasetRow(
            scenario_id="__query__",
            frame=0,
            environment=query["environment"],
            speed_kmph=speed,
            snr_db=snr,
            doppler_hz=doppler,
            channel_profile=query["channel_profile"],
            modulation=int(query["modulation"]),
            strategy="",
            waveform="",
            detector="",
        )
        return self._find_nearest_neighbors(ref, exclude_self=True, k=k)

    # ------------------------------------------------------------------
    # Phase-3 RF model regression
    # ------------------------------------------------------------------

    def _build_model_row(self, waveform: str, query: dict) -> dict:
        """Build the feature row expected by the Phase-3 regressors.

        Matches ai_engine_v2.py design_row() exactly.
        """
        speed = float(query["speed_kmph"])
        snr = float(query["snr_db"])
        doppler = derive_doppler_hz(speed, query["environment"])
        env = query["environment"]
        ch = query["channel_profile"]
        mod = int(query["modulation"])

        # Look up channel parameters
        key = f"{env}|{ch}"
        params = self._channel_params.get(key, self._channel_params.get("__default__", {}))

        return {
            "environment": env,
            "channel_profile": ch,
            "waveform": waveform,
            "speed_kmph": speed,
            "snr_db": snr,
            "doppler_hz": doppler,
            "carrier_frequency_hz": _CARRIER_FREQ_HZ,
            "bandwidth_hz": _BANDWIDTH_HZ,
            "delay_spread_taps": params["delay_spread_taps"],
            "num_paths": params["num_paths"],
            "doppler_spread_hz": 0.0,  # always empty in dataset
            "modulation": mod,
        }

    def _predict_with_uncertainty(
        self,
        waveform: str,
        query: dict,
    ) -> WaveformPrediction:
        """Run all 6 RF regressors for one waveform, with uncertainty.

        For RandomForest: uncertainty = std of individual tree predictions.
        """
        import pandas as pd

        row_dict = self._build_model_row(waveform, query)
        features = self._meta["features_cat"] + self._meta["features_num"]
        X = pd.DataFrame([{c: row_dict.get(c, 0) for c in features}])

        detector = "MRC" if waveform == "OTFS" else "LMMSE"

        pred = WaveformPrediction(waveform=waveform, detector=detector)

        target_map = {
            "Log10BER": "BER",
            "Throughput": "throughput_bps",
            "CQI": "CQI",
            "ACS": "ACS",
            "PER": "PER",
            "SE": "spectral_efficiency",
        }

        for target_name, attr_name in target_map.items():
            model = self._models.get(target_name)
            if model is None:
                continue

            # Handle Pipeline (preprocessing + estimator) or raw estimator
            if hasattr(model, "named_steps"):
                # sklearn Pipeline — get the preprocessor and final estimator
                step_names = list(model.named_steps.keys())
                preprocessor = model.named_steps[step_names[0]]
                final_est = model.named_steps[step_names[-1]]

                # Transform X through preprocessing
                X_transformed = preprocessor.transform(X)

                # Get predictions from all trees
                if hasattr(final_est, "estimators_"):
                    tree_preds = np.array([tree.predict(X_transformed)[0] for tree in final_est.estimators_])
                else:
                    tree_preds = np.array([model.predict(X)[0]])
            else:
                if hasattr(model, "estimators_"):
                    tree_preds = np.array([tree.predict(X)[0] for tree in model.estimators_])
                else:
                    tree_preds = np.array([model.predict(X)[0]])
            mean_val = float(np.mean(tree_preds))
            std_val = float(np.std(tree_preds))
            p10 = float(np.percentile(tree_preds, 10))
            p90 = float(np.percentile(tree_preds, 90))

            # Post-processing (match ai_engine_v2.py logic)
            if target_name == "Log10BER":
                mean_val = float(np.clip(10 ** mean_val, 0.0, 1.0))
                std_val = float(std_val * math.log(10) * mean_val)  # delta method approximation
                p10 = float(np.clip(10 ** p10, 0.0, 1.0))
                p90 = float(np.clip(10 ** p90, 0.0, 1.0))
            elif target_name == "Throughput":
                mean_val = max(mean_val, 0.0)
                p10 = max(p10, 0.0)
                p90 = max(p90, 0.0)
            elif target_name == "CQI":
                mean_val = float(np.clip(mean_val, 0, 15))
                p10 = float(np.clip(p10, 0, 15))
                p90 = float(np.clip(p90, 0, 15))
            elif target_name == "ACS":
                mean_val = float(np.clip(mean_val, 0, 1))
                p10 = float(np.clip(p10, 0, 1))
                p90 = float(np.clip(p90, 0, 1))
            elif target_name == "PER":
                mean_val = float(np.clip(mean_val, 0, 1))
                p10 = float(np.clip(p10, 0, 1))
                p90 = float(np.clip(p90, 0, 1))
            elif target_name == "SE":
                mean_val = max(mean_val, 0.0)
                p10 = max(p10, 0.0)
                p90 = max(p90, 0.0)

            uncertainty = PredictionUncertainty(
                mean=round(mean_val, 6),
                std=round(std_val, 6),
                p10=round(p10, 6),
                p90=round(p90, 6),
            )
            setattr(pred, attr_name, uncertainty)

        return pred

    def predict_both_waveforms(self, query: dict) -> tuple[WaveformPrediction, WaveformPrediction]:
        """Predict metrics for both OTFS and ODDM."""
        otfs = self._predict_with_uncertainty("OTFS", query)
        oddm = self._predict_with_uncertainty("ODDM", query)
        return otfs, oddm

    # ------------------------------------------------------------------
    # Neighborhood consistency
    # ------------------------------------------------------------------

    def compute_neighborhood_consistency(
        self,
        waveform: str,
        prediction: WaveformPrediction,
        neighbors: list[Neighbor],
    ) -> NeighborhoodConsistency:
        """Compare model predictions against neighborhood ACS values."""
        pred_acs = prediction.ACS.mean if prediction.ACS else None

        # Collect neighbor ACS for this waveform
        acs_values = []
        for n in neighbors:
            if waveform == "OTFS" and n.otfs_acs is not None:
                acs_values.append(n.otfs_acs)
            elif waveform == "ODDM" and n.oddm_acs is not None:
                acs_values.append(n.oddm_acs)

        if not acs_values or pred_acs is None:
            return NeighborhoodConsistency(waveform=waveform, predicted_acs=pred_acs)

        neighbor_mean = float(np.mean(acs_values))
        neighbor_median = float(np.median(acs_values))
        neighbor_min = float(np.min(acs_values))
        neighbor_max = float(np.max(acs_values))
        deviation = pred_acs - neighbor_mean
        consistent = abs(deviation) < 0.10

        return NeighborhoodConsistency(
            waveform=waveform,
            predicted_acs=round(pred_acs, 6),
            neighbor_acs_mean=round(neighbor_mean, 6),
            neighbor_acs_median=round(neighbor_median, 6),
            neighbor_acs_min=round(neighbor_min, 6),
            neighbor_acs_max=round(neighbor_max, 6),
            deviation=round(deviation, 6),
            consistent=consistent,
        )

    # ------------------------------------------------------------------
    # Coverage / OOD detection
    # ------------------------------------------------------------------

    def classify_coverage(
        self,
        query: dict,
        exact_match: Optional[dict],
        neighbors: list[Neighbor],
    ) -> str:
        """Classify coverage level for a query.

        Uses multidimensional feature space, not simplistic range checks.

        Thresholds are derived from the empirical nearest-neighbor distance
        distribution computed during initialization.

        - EXACT: exact match found
        - COVERED: inside envelope, dense neighborhood (distance < 75th percentile)
        - NEAR_BOUNDARY: inside ranges but sparse (distance between 75th and 95th percentile)
        - OOD: outside ranges or distance > 95th percentile
        """
        if exact_match is not None:
            return "EXACT"

        # Check categorical validity
        env = query["environment"]
        ch = query["channel_profile"]
        mod = int(query["modulation"])

        if env not in self._categorical_values.get("environment", []):
            return "OOD"
        if ch not in self._categorical_values.get("channel_profile", []):
            return "OOD"
        if mod not in self._categorical_values.get("modulation_int",
                [int(m) for m in self._categorical_values.get("modulation", [])]):
            return "OOD"

        # Check numerical ranges
        speed = float(query["speed_kmph"])
        snr = float(query["snr_db"])
        doppler = derive_doppler_hz(speed, env)

        speed_range = self._feature_ranges.get("speed_kmph", {})
        snr_range = self._feature_ranges.get("snr_db", {})
        doppler_range = self._feature_ranges.get("doppler_hz", {})

        # Hard OOD: outside extended range (>120% of observed range)
        margin = 0.20
        if speed < speed_range.get("min", 0) * (1 - margin) or speed > speed_range.get("max", 1) * (1 + margin):
            return "OOD"
        if snr < snr_range.get("min", -10) - 2.0 or snr > snr_range.get("max", 30) + 2.0:
            return "OOD"
        if doppler < 0 or doppler > doppler_range.get("max", 1000) * (1 + margin):
            return "OOD"

        # If no neighbors found in same categorical group
        if not neighbors:
            return "NEAR_BOUNDARY"

        # Use nearest neighbor distance
        nn_distance = neighbors[0].distance

        # Empirical percentile thresholds from the dataset's own NN distances
        if self._nn_distances_sorted:
            n = len(self._nn_distances_sorted)
            p75 = self._nn_distances_sorted[int(n * 0.75)]
            p95 = self._nn_distances_sorted[int(n * 0.95)]
        else:
            p75 = 0.10
            p95 = 0.25

        if nn_distance <= p75:
            return "COVERED"
        elif nn_distance <= p95:
            return "NEAR_BOUNDARY"
        else:
            return "NEAR_BOUNDARY"  # Inside ranges but far from any neighbor

    # ------------------------------------------------------------------
    # Confidence classification
    # ------------------------------------------------------------------

    def classify_confidence(
        self,
        coverage: str,
        neighbors: list[Neighbor],
        otfs_pred: Optional[WaveformPrediction],
        oddm_pred: Optional[WaveformPrediction],
        otfs_consistency: Optional[NeighborhoodConsistency],
        oddm_consistency: Optional[NeighborhoodConsistency],
    ) -> str:
        """Classify confidence level based on measurable evidence.

        Evidence sources:
        - Coverage level (from classify_coverage)
        - Nearest-neighbor distance
        - RF prediction dispersion (std/mean ratio)
        - Neighborhood consistency (predicted vs neighbor ACS)

        HIGH:   exact or dense neighborhood, low prediction dispersion, strong agreement
        MEDIUM: moderate distance, some disagreement or uncertainty
        LOW:    sparse neighborhood, high model uncertainty, significant disagreement
        UNAVAILABLE: OOD, unsupported categorical, missing model coverage
        """
        if coverage == "OOD":
            return "UNAVAILABLE"

        if coverage == "EXACT":
            return "HIGH"

        # Score components (0 = worst, 1 = best)
        scores = []

        # 1. Neighbor distance (lower is better)
        if neighbors:
            nn_dist = neighbors[0].distance
            if self._nn_distances_sorted:
                n = len(self._nn_distances_sorted)
                p25 = self._nn_distances_sorted[int(n * 0.25)]
                p75 = self._nn_distances_sorted[int(n * 0.75)]
                if nn_dist <= p25:
                    scores.append(1.0)
                elif nn_dist <= p75:
                    scores.append(0.6)
                else:
                    scores.append(0.3)
            else:
                scores.append(0.5 if nn_dist < 0.15 else 0.3)
        else:
            scores.append(0.0)

        # 2. RF uncertainty dispersion (lower std/mean is better)
        for pred in [otfs_pred, oddm_pred]:
            if pred and pred.ACS and pred.ACS.mean > 0:
                cv = pred.ACS.std / abs(pred.ACS.mean)  # coefficient of variation
                if cv < 0.05:
                    scores.append(1.0)
                elif cv < 0.15:
                    scores.append(0.6)
                else:
                    scores.append(0.3)

        # 3. Neighborhood consistency
        for cons in [otfs_consistency, oddm_consistency]:
            if cons and cons.consistent is not None:
                scores.append(1.0 if cons.consistent else 0.3)
            elif cons and cons.deviation is not None:
                dev = abs(cons.deviation)
                if dev < 0.05:
                    scores.append(0.9)
                elif dev < 0.10:
                    scores.append(0.6)
                else:
                    scores.append(0.3)

        if not scores:
            return "UNAVAILABLE"

        avg_score = sum(scores) / len(scores)

        if avg_score >= 0.7:
            return "HIGH"
        elif avg_score >= 0.4:
            return "MEDIUM"
        else:
            return "LOW"

    # ------------------------------------------------------------------
    # Phase-3 AI decision
    # ------------------------------------------------------------------

    def run_phase3_decision(
        self,
        otfs_pred: WaveformPrediction,
        oddm_pred: WaveformPrediction,
        state: Optional[dict] = None,
    ) -> dict:
        """Run the canonical Phase-3 AI waveform decision logic.

        Uses ai_engine_v2.py logic (reimplemented to avoid import dependencies).
        """
        pol = self._policy
        obj = str(pol["objective"]).upper()

        s_otfs = otfs_pred.ACS.mean if (obj == "ACS" and otfs_pred.ACS) else (
            otfs_pred.BER.mean if (obj == "BER" and otfs_pred.BER) else 0.0
        )
        s_oddm = oddm_pred.ACS.mean if (obj == "ACS" and oddm_pred.ACS) else (
            oddm_pred.BER.mean if (obj == "BER" and oddm_pred.BER) else 0.0
        )

        if obj == "BER":
            best = "OTFS" if s_otfs <= s_oddm else "ODDM"
        else:
            best = "OTFS" if s_otfs >= s_oddm else "ODDM"

        # State-based gating
        cur = (state or {}).get("current_waveform")
        dwell = int((state or {}).get("frames_since_switch", 999))

        if cur not in ("OTFS", "ODDM"):
            rec, switched, reason = best, True, f"initial selection ({obj}={max(s_otfs, s_oddm) if obj == 'ACS' else min(s_otfs, s_oddm):.4f})"
        else:
            alt = "ODDM" if cur == "OTFS" else "OTFS"
            cur_s = s_otfs if cur == "OTFS" else s_oddm
            alt_s = s_otfs if alt == "OTFS" else s_oddm
            gain = (cur_s - alt_s) if obj == "BER" else (alt_s - cur_s)
            rel = gain / max(abs(cur_s), 1e-9)
            gain_best = max(s_otfs, s_oddm) if obj == "ACS" else min(s_otfs, s_oddm)
            conf_raw = abs(s_otfs - s_oddm) / max(abs(gain_best), 1e-9)
            confidence = float(min(1.0, conf_raw))

            if dwell < pol["min_dwell_frames"]:
                rec, switched = cur, False
                reason = f"hold {cur}: min-dwell ({dwell}/{pol['min_dwell_frames']})"
            elif gain <= 0:
                rec, switched = cur, False
                reason = f"keep {cur}: already best by {obj}"
            elif not (abs(gain) > pol["switch_margin_acs"] or rel > pol["switch_margin_rel"]):
                rec, switched = cur, False
                reason = f"keep {cur}: margin below threshold (gain {gain:+.4f} / {100*rel:.1f}%)"
            elif confidence < pol["min_confidence"]:
                rec, switched = cur, False
                reason = f"hold {cur}: normalized margin confidence {confidence:.2f} < {pol['min_confidence']}"
            else:
                rec, switched = alt, True
                reason = f"switch to {alt}: {obj} improvement {gain:+.4f} abs / {100*rel:.1f}% rel, confidence {confidence:.2f}"

        gain_best = max(s_otfs, s_oddm) if obj == "ACS" else min(s_otfs, s_oddm)
        conf_raw = abs(s_otfs - s_oddm) / max(abs(gain_best), 1e-9)
        confidence = float(min(1.0, conf_raw))

        return {
            "selected_waveform": rec,
            "best_by_objective": best,
            "detector": "MRC" if rec == "OTFS" else "LMMSE",
            "switched": switched,
            "reason": reason,
            "confidence": round(confidence, 4),
            "objective": obj,
            "predicted_OTFS_ACS": round(otfs_pred.ACS.mean, 6) if otfs_pred.ACS else None,
            "predicted_ODDM_ACS": round(oddm_pred.ACS.mean, 6) if oddm_pred.ACS else None,
            "predicted_OTFS_BER": round(otfs_pred.BER.mean, 6) if otfs_pred.BER else None,
            "predicted_ODDM_BER": round(oddm_pred.BER.mean, 6) if oddm_pred.BER else None,
            "policy_version": "phase3",
        }

    # ------------------------------------------------------------------
    # Full evaluation pipeline
    # ------------------------------------------------------------------

    def evaluate(self, query: dict) -> EvaluationResult:
        """Run the full hybrid evaluation pipeline.

        1. Validate query
        2. Exact lookup
        3. Nearest neighbors
        4. Phase-3 RF regression (OTFS + ODDM)
        5. RF uncertainty estimation
        6. Neighborhood consistency
        7. Coverage / OOD classification
        8. Confidence classification
        9. Phase-3 AI decision
        10. Assemble result with warnings
        """
        warnings: list[str] = []

        # 1. Validate
        is_valid, errors = self.validate_query(query)
        if not is_valid:
            return EvaluationResult(
                coverage="OOD",
                confidence="UNAVAILABLE",
                input_conditions=query,
                nearest_neighbors=[],
                otfs_prediction=None,
                oddm_prediction=None,
                otfs_consistency=None,
                oddm_consistency=None,
                decision={},
                warnings=errors,
            )

        # 2. Exact lookup
        exact = self.find_exact_match(query)

        # 3. Nearest neighbors
        neighbors = self.find_nearest_neighbors(query, k=5)

        # 4. RF regression
        otfs_pred, oddm_pred = self.predict_both_waveforms(query)

        # 5. Neighborhood consistency
        otfs_consistency = self.compute_neighborhood_consistency("OTFS", otfs_pred, neighbors)
        oddm_consistency = self.compute_neighborhood_consistency("ODDM", oddm_pred, neighbors)

        # 6. Coverage
        coverage = self.classify_coverage(query, exact, neighbors)

        # 7. Confidence
        confidence = self.classify_confidence(
            coverage, neighbors, otfs_pred, oddm_pred, otfs_consistency, oddm_consistency,
        )

        # 8. Phase-3 decision
        decision = self.run_phase3_decision(otfs_pred, oddm_pred)

        # 9. Warnings
        if coverage == "OOD":
            warnings.append("Operating point is outside validated model coverage.")
        elif coverage == "NEAR_BOUNDARY":
            warnings.append("Operating point is near the boundary of validated coverage. Predictions may be less reliable.")
        if confidence == "LOW":
            warnings.append("Low confidence: predictions have high uncertainty or poor neighborhood consistency.")
        elif confidence == "UNAVAILABLE":
            warnings.append("Confidence unavailable: model cannot provide reliable predictions for this operating point.")

        # 10. Add measured data info if exact
        if exact:
            warnings.append(f"Exact match found: Scenario {exact['source_scenario']}, Frame {exact['source_frame']}. Measured values available.")

        return EvaluationResult(
            coverage=coverage,
            confidence=confidence,
            input_conditions={
                "environment": query["environment"],
                "speed_kmph": float(query["speed_kmph"]),
                "snr_db": float(query["snr_db"]),
                "doppler_hz": derive_doppler_hz(float(query["speed_kmph"]), query["environment"]),
                "channel_profile": query["channel_profile"],
                "modulation": int(query["modulation"]),
                "detector": query.get("detector"),
            },
            nearest_neighbors=neighbors,
            otfs_prediction=otfs_pred,
            oddm_prediction=oddm_pred,
            otfs_consistency=otfs_consistency,
            oddm_consistency=oddm_consistency,
            decision=decision,
            warnings=warnings,
        )

    # ------------------------------------------------------------------
    # Serialisation helpers
    # ------------------------------------------------------------------

    def result_to_dict(self, result: EvaluationResult) -> dict:
        """Convert EvaluationResult to a JSON-serialisable dict."""
        def _unc(u: Optional[PredictionUncertainty]) -> Optional[dict]:
            if u is None:
                return None
            return {"mean": u.mean, "std": u.std, "p10": u.p10, "p90": u.p90}

        def _waveform(w: Optional[WaveformPrediction]) -> Optional[dict]:
            if w is None:
                return None
            return {
                "waveform": w.waveform,
                "detector": w.detector,
                "BER": _unc(w.BER),
                "throughput_bps": _unc(w.throughput_bps),
                "CQI": _unc(w.CQI),
                "ACS": _unc(w.ACS),
                "PER": _unc(w.PER),
                "spectral_efficiency": _unc(w.spectral_efficiency),
            }

        def _consistency(c: Optional[NeighborhoodConsistency]) -> Optional[dict]:
            if c is None:
                return None
            return {
                "waveform": c.waveform,
                "predicted_acs": c.predicted_acs,
                "neighbor_acs_mean": c.neighbor_acs_mean,
                "neighbor_acs_median": c.neighbor_acs_median,
                "neighbor_acs_range": [c.neighbor_acs_min, c.neighbor_acs_max] if c.neighbor_acs_min is not None else None,
                "deviation": c.deviation,
                "consistent": c.consistent,
            }

        def _neighbor(n: Neighbor) -> dict:
            return {
                "distance": n.distance,
                "speed_difference": n.speed_difference,
                "snr_difference": n.snr_difference,
                "doppler_difference": n.doppler_difference,
                "source_scenario": n.source_scenario,
                "source_frame": n.source_frame,
                "environment": n.environment,
                "channel_profile": n.channel_profile,
                "modulation": n.modulation,
                "otfs_ber": n.otfs_ber,
                "otfs_acs": n.otfs_acs,
                "oddm_ber": n.oddm_ber,
                "oddm_acs": n.oddm_acs,
            }

        return {
            "status": "ok",
            "coverage": result.coverage,
            "confidence": result.confidence,
            "input": result.input_conditions,
            "nearest_neighbors": [_neighbor(n) for n in result.nearest_neighbors],
            "predictions": {
                "OTFS": _waveform(result.otfs_prediction),
                "ODDM": _waveform(result.oddm_prediction),
            },
            "consistency": {
                "OTFS": _consistency(result.otfs_consistency),
                "ODDM": _consistency(result.oddm_consistency),
            },
            "decision": result.decision,
            "warnings": result.warnings,
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _opt_float(val: Any) -> Optional[float]:
    """Convert to float or None."""
    if val is None or val == "" or val == "nan":
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------------------
# Module-level singleton (lazy)
# ---------------------------------------------------------------------------

_service: Optional[DeploymentDataService] = None


def get_service() -> DeploymentDataService:
    """Get or create the singleton DeploymentDataService."""
    global _service
    if _service is None:
        _service = DeploymentDataService()
    return _service
