"""model_registry.py -- single source of truth for production model selection.

Resolves which trained artifact backs each metric target, based on the active
model version. The active version is chosen by the MODEL_VERSION environment
variable (default: "v4-b1"); set MODEL_VERSION=v2 to roll back to the frozen
metric_models_v2 set. This module is importable both from this pipeline folder
(ai_engine_v2.py, ai_engine_v3.py) and from the backend deployment service.

Versions:
  - v2      all 6 targets from models/metric_models_v2/      (frozen Phase 3)
  - v4-b1   Log10BER from models/metric_models_v4/candidate_B1/
            (experiment-4 B1 model), the other 5 targets stay v2.

Rules:
  - Resolution is explicit per target. A missing artifact for the active
    version raises FileNotFoundError -- there is NO silent fallback to v2.
  - Paths are derived from this file's location, never machine-specific.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

PIPELINE_DIR = Path(__file__).resolve().parent
MODELS_ROOT = PIPELINE_DIR / "models"
V2_DIR = MODELS_ROOT / "metric_models_v2"
V4_DIR = MODELS_ROOT / "metric_models_v4"

MODEL_VERSION_ENV = "MODEL_VERSION"
DEFAULT_MODEL_VERSION = "v4-b1"
ROLLBACK_MODEL_VERSION = "v2"
SUPPORTED_MODEL_VERSIONS = (ROLLBACK_MODEL_VERSION, DEFAULT_MODEL_VERSION)

# v2 target -> exact artifact (authoritative names from metric_models_v2_meta.json)
_V2_FILES = {
    "Log10BER": "metric_reg_v2_Log10BER.joblib",
    "Throughput": "metric_reg_v2_Throughput.joblib",
    "CQI": "metric_reg_v2_CQI.joblib",
    "ACS": "metric_reg_v2_ACS.joblib",
    "PER": "metric_reg_v2_PER.joblib",
    "SE": "metric_reg_v2_SE.joblib",
}

# v4-b1 target -> exact artifact (Log10BER only; everything else stays v2)
_V4_B1_FILES = {
    "Log10BER": "candidate_B1/metric_reg_v4_Log10BER_B1.joblib",
}

ALL_TARGETS = tuple(sorted(set(_V2_FILES) | set(_V4_B1_FILES)))


def get_active_model_version(override: Optional[str] = None) -> str:
    """Return the active model version (env var or explicit override)."""
    raw = override if override is not None else os.environ.get(
        MODEL_VERSION_ENV, DEFAULT_MODEL_VERSION)
    version = str(raw).strip().lower()
    if version not in SUPPORTED_MODEL_VERSIONS:
        raise ValueError(
            "unsupported MODEL_VERSION %r (supported: %s)"
            % (raw, ", ".join(SUPPORTED_MODEL_VERSIONS)))
    return version


def resolve_target_model(target: str, override: Optional[str] = None) -> Path:
    """Return the artifact path for `target` under the active (or given) version."""
    version = get_active_model_version(override)
    if version == DEFAULT_MODEL_VERSION and target in _V4_B1_FILES:
        return V4_DIR / _V4_B1_FILES[target]
    if target not in _V2_FILES:
        raise KeyError("no registered model artifact for target %r" % target)
    return V2_DIR / _V2_FILES[target]


def validate_active_version(override: Optional[str] = None) -> dict:
    """Resolve every required artifact for the active version.

    Raises FileNotFoundError if any artifact is missing -- the registry never
    silently falls back to another version. Returns {target: artifact_path}.
    """
    version = get_active_model_version(override)
    resolved = {t: str(resolve_target_model(t, override)) for t in ALL_TARGETS}
    missing = [p for p in resolved.values() if not Path(p).is_file()]
    if missing:
        raise FileNotFoundError(
            "model artifact(s) missing for MODEL_VERSION=%s: %s"
            % (version, "; ".join(missing)))
    return resolved


def target_sources() -> dict:
    """Map target -> {version: artifact_path} across all supported versions."""
    return {
        t: {
            ROLLBACK_MODEL_VERSION: str(V2_DIR / _V2_FILES[t]),
            DEFAULT_MODEL_VERSION: (
                str(V4_DIR / _V4_B1_FILES[t])
                if t in _V4_B1_FILES else str(V2_DIR / _V2_FILES[t])),
        }
        for t in ALL_TARGETS
    }


def is_rollback_available() -> bool:
    """True when every v2 artifact exists (v2 remains the rollback baseline)."""
    return all((V2_DIR / f).is_file() for f in _V2_FILES.values())


def version_info() -> dict:
    """Observability snapshot of the active version and its artifacts."""
    return {
        "model_version": get_active_model_version(),
        "default_model_version": DEFAULT_MODEL_VERSION,
        "rollback_model_version": ROLLBACK_MODEL_VERSION,
        "rollback_available": is_rollback_available(),
        "source": MODEL_VERSION_ENV,
        "target_sources": target_sources(),
    }