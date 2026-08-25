"""
parameter_mapper.py
====================
Reads config.AUDIO_CLASSIFICATION_FILE (written by environment_classifier.py)
plus environment_profiles.csv, and writes config.DETECTED_ENV_FILE with
EXACTLY the fields MATLAB's Module 1 requires:

    { "environment": ..., "speed_kmh": ..., "delay_profile": ..., "doppler_scale": ... }

MATLAB then runs its scenario generator in FOCUS mode around this single
environment. Called by the MATLAB script as:  python parameter_mapper.py
"""

import argparse
import json
import os
import random
import sys

import pandas as pd

from config import (AUDIO_CLASSIFICATION_FILE, DETECTED_ENV_FILE, ENV_PROFILE_FILE,
                     ENV_LABEL_TO_PROFILE, SCENARIO_MODE_CHOICES, SCENARIO_TO_ENV_PROFILE)


def _lookup_profile_row(profiles: pd.DataFrame, physical_label: str):
    row = profiles[profiles["Environment"] == physical_label]
    if row.empty:
        print(f"WARNING: '{physical_label}' not found in the profile table; "
              f"falling back to the first profile row.", file=sys.stderr)
        row = profiles.iloc[[0]]
        physical_label = row["Environment"].iloc[0]
    return row.iloc[0], physical_label


def _build_result(display_label: str, physical_label: str, row: pd.Series, extra: dict = None) -> dict:
    speed_kmh = round(random.uniform(float(row["SpeedMin"]), float(row["SpeedMax"])))
    result = {
        # MATLAB Module 1 requires exactly these 4 keys -- never rename/remove them.
        "environment": display_label,
        "speed_kmh": int(speed_kmh),
        "delay_profile": str(row["DelayProfile"]),
        "doppler_scale": float(row["DopplerScale"]),
        # Additional, optional metadata (ignored by MATLAB, used by predict.py /
        # dashboard.py / graphs.py for richer real-world-mode reporting).
        "physical_profile": physical_label,
        "delay_spread": None,
        "num_paths": None,
    }
    if extra:
        result.update(extra)
    return result


# ---------------------------------------------------------------------------
# MODE 2: microphone-detected environment -> channel parameters
# ---------------------------------------------------------------------------
def map_parameters(env_profile_file: str = ENV_PROFILE_FILE,
                    classification_file: str = AUDIO_CLASSIFICATION_FILE) -> dict:
    if not os.path.exists(classification_file):
        print(f"ERROR: {classification_file} not found. Run environment_classifier.py first.",
              file=sys.stderr)
        sys.exit(1)
    if not os.path.exists(env_profile_file):
        print(f"ERROR: {env_profile_file} not found.", file=sys.stderr)
        sys.exit(1)

    with open(classification_file) as f:
        detection = json.load(f)

    label = detection["environment"]
    # Real-world audio labels (Office/Traffic/Bus/Train/Highway/Construction/
    # Indoor/Outdoor) are broader than environment_profiles.csv's physical
    # rows (Indoor/Urban/Rural/Highway) -- snap onto the matching physical
    # profile for the numeric channel parameters, but keep reporting the
    # original real-world label so the person can see what was detected.
    physical_label = ENV_LABEL_TO_PROFILE.get(label, label)

    profiles = pd.read_csv(env_profile_file)
    row, physical_label = _lookup_profile_row(profiles, physical_label)

    extra = {
        "confidence": detection.get("confidence"),
        "estimated_mobility": detection.get("estimated_mobility"),
        "noise_level": detection.get("noise_level"),
    }
    result = _build_result(label, physical_label, row, extra)

    with open(DETECTED_ENV_FILE, "w") as f:
        json.dump(result, f, indent=2)

    print(f"Mapped '{label}' (-> physical profile '{physical_label}') -> {result}")
    print(f"Saved -> {DETECTED_ENV_FILE}")
    return result


# ---------------------------------------------------------------------------
# MODE 1: manual scenario picker -> channel parameters
# ---------------------------------------------------------------------------
def map_scenario(scenario: str, env_profile_file: str = ENV_PROFILE_FILE) -> dict:
    """MODE 1 -- user manually picks one of SCENARIO_MODE_CHOICES
    (Traffic/Bus/Train/Office/Highway) instead of recording audio."""
    if scenario not in SCENARIO_TO_ENV_PROFILE:
        print(f"ERROR: unknown scenario '{scenario}'. Choose one of {SCENARIO_MODE_CHOICES}.",
              file=sys.stderr)
        sys.exit(1)
    if not os.path.exists(env_profile_file):
        print(f"ERROR: {env_profile_file} not found.", file=sys.stderr)
        sys.exit(1)

    physical_label = SCENARIO_TO_ENV_PROFILE[scenario]
    profiles = pd.read_csv(env_profile_file)
    row, physical_label = _lookup_profile_row(profiles, physical_label)

    result = _build_result(scenario, physical_label, row,
                            extra={"confidence": 1.0, "estimated_mobility": None, "noise_level": None})

    with open(DETECTED_ENV_FILE, "w") as f:
        json.dump(result, f, indent=2)

    print(f"Scenario '{scenario}' (-> physical profile '{physical_label}') -> {result}")
    print(f"Saved -> {DETECTED_ENV_FILE}")
    return result


if __name__ == "__main__":
    ap = argparse.ArgumentParser(
        description="Map a detected/selected environment onto OTFS channel parameters.")
    ap.add_argument("--scenario", type=str, default=None, choices=SCENARIO_MODE_CHOICES,
                     help=f"MODE 1: manually pick a scenario ({', '.join(SCENARIO_MODE_CHOICES)}) "
                          f"instead of reading the microphone classification.")
    args = ap.parse_args()

    if args.scenario:
        map_scenario(args.scenario)
    else:
        map_parameters()
