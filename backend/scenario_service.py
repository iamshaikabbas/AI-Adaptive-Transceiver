"""Scenario service — maps API requests to Phase 5 scenario definitions."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

from .config import ENVIRONMENTS, MATLAB_DIR, SCENARIOS, SCENARIO_LETTERS

logger = logging.getLogger(__name__)

SCENARIOS_DIR = MATLAB_DIR / "Results" / "DigitalTwin"


def list_scenarios() -> list[dict]:
    scenarios = []
    for letter in SCENARIO_LETTERS:
        jf = SCENARIOS_DIR / f"scenario_{letter.lower()}.json"
        info = {
            "id": letter,
            "name": f"Scenario {letter}",
            "environment": None,
            "description": None,
            "duration_frames": None,
        }
        if jf.exists():
            try:
                with open(jf, encoding="utf-8") as f:
                    data = json.load(f)
                pts = data.get("points", [])
                info["duration_frames"] = len(pts)
                envs = set()
                for p in pts:
                    envs.add(p.get("environment", "Unknown"))
                if envs:
                    info["environment"] = ", ".join(sorted(envs))
                meta = data.get("meta", {})
                if "tier" in meta:
                    info["description"] = f"Tier: {meta['tier']}"
            except Exception as e:
                logger.warning("Failed to load scenario %s: %s", letter, e)
        scenarios.append(info)
    return scenarios


def get_scenario(scenario_id: str) -> Optional[dict]:
    sid = scenario_id.upper()
    if sid in SCENARIOS:
        jf = SCENARIOS_DIR / f"scenario_{sid.lower()}.json"
        info = SCENARIOS[sid].copy()
        if jf.exists():
            try:
                with open(jf, encoding="utf-8") as f:
                    data = json.load(f)
                pts = data.get("points", [])
                info["duration_frames"] = len(pts)
                envs = set()
                for p in pts:
                    envs.add(p.get("environment", "Unknown"))
                if envs:
                    info["environment"] = ", ".join(sorted(envs))
                info["points"] = pts
            except Exception as e:
                logger.warning("Failed to load scenario %s: %s", sid, e)
        return info
    return None


def build_custom_scenario(
    environment: str,
    speed_kmph: float,
    snr_db: float,
    channel_profile: str,
    modulation: int,
    duration_frames: int,
) -> dict:
    """Build a scenario JSON from custom parameters."""
    pts = []
    for i in range(duration_frames):
        pts.append({
            "t_s": float(i),
            "frame": i,
            "environment": environment,
            "speed_kmph": speed_kmph,
            "snr_db": snr_db,
            "delay_profile": channel_profile,
            "doppler_scale": ENVIRONMENTS.get(environment, {}).get(
                "doppler_scale", 1.0
            ),
            "modulation": modulation,
        })
    return {"name": "custom", "points": pts}
