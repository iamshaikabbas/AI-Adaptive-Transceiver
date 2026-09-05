"""Evals-side adapter for the shared production model registry.

Single source of truth for active-model resolution is
``OTFS MRC detection MATLAB code/otfs_ai_pipeline/model_registry.py``
(the same module the deployment / custom-evaluation path uses).

This module only re-exports the registry's resolution calls so the Evals
engine loads the ACTIVE model version (MODEL_VERSION, default v4-b1),
exactly like production. No model-loading logic is duplicated here and
no version is hard-coded in the Evals package.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

_PIPELINE_DIR = (
    Path(__file__).resolve().parent.parent.parent
    / "OTFS MRC detection MATLAB code"
    / "otfs_ai_pipeline"
)
_REGISTRY = None


def _registry():
    """Import the shared model_registry module (resolved by absolute path)."""
    global _REGISTRY
    if _REGISTRY is None:
        spec = importlib.util.spec_from_file_location(
            "model_registry", _PIPELINE_DIR / "model_registry.py"
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _REGISTRY = module
    return _REGISTRY


def get_active_model_version() -> str:
    """Return the active production model version label (e.g. ``v4-b1``)."""
    return _registry().get_active_model_version()


def resolve_target_model(target: str) -> Path:
    """Resolve the artifact path for ``target`` under the active model version."""
    return _registry().resolve_target_model(target)


def version_info() -> dict:
    """Observability snapshot of the active version and its artifacts."""
    return _registry().version_info()