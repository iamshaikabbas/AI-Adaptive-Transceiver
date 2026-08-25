"""
scenario.py -- Digital Twin scenario scheduler (SOFTWARE simulation).

Builds the time-varying virtual wireless scenario from the documented
environment profiles in ../environment_profiles.csv:

    Pedestrian    EPA  DopplerScale 1.0   (low speed)
    Urban         EVA  DopplerScale 1.0   (moderate)
    Highway       ETU  DopplerScale 1.0   (high)
    HighSpeedRail ETU  DopplerScale 1.5   (very high)

These are CONFIGURABLE SIMULATION PROFILES representing representative
scenarios -- not real-world measurements.

Default long scenario (spec section 2/16):
    0-10 s Pedestrian -> 10-20 Urban -> 20-30 Highway
    -> 30-40 HighSpeedRail -> 40-50 Urban -> 50-60 Highway

SNR follows an environment-dependent baseline plus a smooth sinusoidal
variation, so the twin experiences both good and stressed links.
"""

import os
import subprocess
import sys
from dataclasses import dataclass, asdict, field

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
PROFILE_FILE = os.path.join(os.path.dirname(HERE), "environment_profiles.csv")

DEFAULT_PLAN = [
    # (environment, seconds)
    ("Pedestrian", 10),
    ("Urban", 10),
    ("Highway", 10),
    ("HighSpeedRail", 10),
    ("Urban", 10),
    ("Highway", 10),
]

# SNR baselines [dB] per environment (simulation choice, not measurement)
SNR_BASE = {"Pedestrian": 20.0, "Urban": 15.0, "Highway": 12.0,
            "HighSpeedRail": 8.0}


@dataclass
class ScenarioPoint:
    t_s: float
    frame: int
    environment: str
    speed_kmph: float
    snr_db: float
    delay_profile: str
    doppler_scale: float
    modulation: int = 4          # QPSK default for the drive


def load_profiles() -> pd.DataFrame:
    df = pd.read_csv(PROFILE_FILE)
    return df.set_index("Environment")


def build_scenario(duration_s: float = None, dt_s: float = 1.0,
                   plan=None, seed: int = 7) -> list:
    """Return the ordered list of ScenarioPoints for a full drive."""
    prof = load_profiles()
    plan = plan or DEFAULT_PLAN
    if duration_s is not None:
        total = sum(s for _, s in plan)
        plan = [(e, max(1, round(s * duration_s / total))) for e, s in plan]

    rng = np.random.default_rng(seed)
    points = []
    frame = 0
    for env, seg_s in plan:
        row = prof.loc[env]
        v_lo, v_hi = float(row.SpeedMin), float(row.SpeedMax)
        # smooth speed trajectory inside the segment (random-walk between
        # the profile's documented bounds, pinned to the bounds at edges)
        steps = np.linspace(0, 1, seg_s + 1)
        base = rng.uniform(v_lo, v_hi)
        target = rng.uniform(v_lo, v_hi)
        wobble = 0.15 * (v_hi - v_lo) * np.sin(2 * np.pi * steps * rng.uniform(1, 3))
        speeds = np.clip(base + (target - base) * steps + wobble, v_lo, v_hi)
        for k in range(seg_s):
            t = len(points) * dt_s
            snr = SNR_BASE.get(env, 12.0) + 3.0 * np.sin(2 * np.pi * t / 25.0)
            points.append(ScenarioPoint(
                t_s=round(t, 3), frame=frame, environment=env,
                speed_kmph=round(float(speeds[k]), 1), snr_db=round(float(snr), 2),
                delay_profile=str(row.DelayProfile),
                doppler_scale=float(row.DopplerScale)))
            frame += 1
    return points


def write_scenario_json(points, path: str, carrier_hz=4e9):
    import json
    with open(path, "w") as fh:
        json.dump({"carrier_frequency_hz": carrier_hz,
                   "points": [asdict(p) for p in points]}, fh, indent=1)


if __name__ == "__main__":
    pts = build_scenario(duration_s=float(sys.argv[1]) if len(sys.argv) > 1 else 60.0)
    print(f"{len(pts)} frames; first/last:")
    print(asdict(pts[0])); print(asdict(pts[-1]))
