"""AI bridge — Python-side AI engine for decisions without MATLAB."""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Optional

from .config import OTFS_PIPELINE

logger = logging.getLogger(__name__)


class AIBridge:
    """Invokes the canonical AI engine (ai_engine_v2.py) for decisions."""

    def __init__(self, policy: str = "phase3"):
        self.policy = policy
        self._engine = None
        self._available: Optional[bool] = None

    def _load_engine(self):
        if self._engine is not None:
            return True
        try:
            sys.path.insert(0, str(OTFS_PIPELINE))
            from ai_engine_v2 import AIEngineV2

            config_path = None
            if self.policy == "phase4":
                config_path = str(
                    Path(__file__).resolve().parent.parent
                    / "OTFS MRC detection MATLAB code"
                    / "adaptive_config_v4.json"
                )
            self._engine = AIEngineV2(config_file=config_path)
            self._available = True
            return True
        except Exception as e:
            logger.warning("AI engine load failed: %s", e)
            self._available = False
            return False

    def is_available(self) -> bool:
        if self._available is not None:
            return self._available
        return self._load_engine()

    def decide(self, state: dict) -> dict:
        """Run AI decision given a state dictionary."""
        if not self._load_engine():
            return self._fallback(state, "AI engine unavailable")
        try:
            decision = self._engine.decide(state)
            return decision
        except Exception as e:
            logger.error("AI decision failed: %s", e)
            return self._fallback(state, str(e))

    def predict_metrics(self, waveform: str, state: dict) -> dict:
        if not self._load_engine():
            return {}
        try:
            return self._engine.predict_metrics(waveform, state)
        except Exception as e:
            logger.error("AI prediction failed: %s", e)
            return {}

    @staticmethod
    def _fallback(state: dict, reason: str) -> dict:
        cur = state.get("current_waveform", "OTFS")
        return {
            "recommendation": cur,
            "best_by_objective": cur,
            "detector": "MRC" if cur == "OTFS" else "LMMSE",
            "switched": False,
            "reason": f"fallback: {reason}",
            "confidence": 0.0,
            "objective": "ACS",
            "predicted_ACS": {"OTFS": None, "ODDM": None},
            "predicted_BER": {"OTFS": None, "ODDM": None},
            "predicted_metrics": {"OTFS": {}, "ODDM": {}},
            "fallback_used": True,
            "fallback_reason": reason,
        }
