"""Backend configuration — environment variables, paths, constants."""

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MATLAB_DIR = PROJECT_ROOT / "OTFS MRC detection MATLAB code"
OTFS_PIPELINE = MATLAB_DIR / "otfs_ai_pipeline"
RESULTS_DIR = MATLAB_DIR / "Results"
FINAL_EVAL_DIR = RESULTS_DIR / "FinalEvaluation"
LIVE_SIM_DIR = RESULTS_DIR / "LiveSimulation"

DEFAULT_SEED = 20260823
DEFAULT_POLICY = "phase3"
DEFAULT_STRATEGY = "ai_adaptive"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000

MATLAB_EXECUTABLE = os.environ.get(
    "MATLAB_EXECUTABLE",
    os.environ.get("MATLAB_PATH", "matlab"),
)

VALID_STRATEGIES = ["fixed_otfs", "fixed_oddm", "ai_adaptive", "oracle"]
VALID_POLICIES = ["phase3", "phase4"]
VALID_MODES = ["FAST", "FULL"]
VALID_CHANNELS = ["EPA", "EVA", "ETU"]
VALID_MODULATIONS = [4, 16, 64]

ENVIRONMENTS = {
    "Pedestrian": {"speed_range": [0, 10], "channel": "EPA", "snr_base": 20},
    "Urban": {"speed_range": [10, 60], "channel": "EVA", "snr_base": 15},
    "UrbanFast": {"speed_range": [10, 60], "channel": "ETU", "snr_base": 15},
    "Highway": {"speed_range": [60, 140], "channel": "EVA", "snr_base": 12},
    "HighSpeedRail": {"speed_range": [140, 350], "channel": "EVA", "snr_base": 8},
}

SCENARIOS = {}
SCENARIO_LETTERS = list("ABCDEFGHIJKLMNOPQR")
for letter in SCENARIO_LETTERS:
    SCENARIOS[letter] = {"id": letter, "name": f"Scenario {letter}"}
