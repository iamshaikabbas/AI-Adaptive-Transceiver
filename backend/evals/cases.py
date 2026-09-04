"""Evaluation case generation for the Evals Platform.

Generates deterministic evaluation cases from the Golden Dataset:

- EXACT: Operating points that exist in the dataset with ground truth
- INTERIOR: Points inside the domain but not exact dataset rows
- BOUNDARY: Points near domain boundaries
- OOD: Out-of-domain points that should be rejected
"""

from __future__ import annotations

import itertools
from typing import Any, Optional

from .golden_dataset import GoldenDataset
from .schemas import EvalCase, CaseType, EvalSuite, EvalCaseInput


def generate_exact_cases(dataset: GoldenDataset, suite: EvalSuite) -> list[EvalCase]:
    """Generate EXACT cases from fixed_otfs rows in the Golden Dataset.

    Each case corresponds to a measured operating point where ground truth
    BER, SER, PER, throughput, CQI, ACS are available from simulation.
    """
    cases: list[EvalCase] = []
    seen_operating_points: set[tuple] = set()

    for row in dataset.get_fixed_otfs_rows():
        key = (
            row["environment"],
            row["speed_kmph"],
            row["snr_db"],
            row["channel_profile"],
            row["modulation"],
        )
        if key in seen_operating_points:
            continue
        seen_operating_points.add(key)

        doppler_hz = float(row.get("doppler_hz", 0))
        input_conds = EvalCaseInput(
            environment=row["environment"],
            speed_kmph=float(row["speed_kmph"]),
            snr_db=float(row["snr_db"]),
            doppler_hz=doppler_hz,
            channel_profile=row["channel_profile"],
            modulation=int(float(row["modulation"])),
            detector=row.get("detector"),
        )

        # Ground truth from measured simulation
        ground_truth = {
            "BER": _safe_float(row.get("BER")),
            "SER": _safe_float(row.get("SER")),
            "PER": _safe_float(row.get("PER")),
            "throughput_bps": _safe_float(row.get("throughput_bps")),
            "spectral_efficiency": _safe_float(row.get("spectral_efficiency")),
            "CQI": _safe_float(row.get("CQI")),
            "ACS": _safe_float(row.get("ACS")),
        }

        # Also get ODDM ground truth from the same group
        group = dataset.get_group(row["scenario_id"], int(row["frame"]))
        oddm_row = group.get("fixed_oddm")
        if oddm_row:
            ground_truth["ODDM_BER"] = _safe_float(oddm_row.get("BER"))
            ground_truth["ODDM_ACS"] = _safe_float(oddm_row.get("ACS"))
            ground_truth["ODDM_throughput_bps"] = _safe_float(oddm_row.get("throughput_bps"))

        # Oracle reference
        oracle_row = group.get("oracle")
        if oracle_row:
            ground_truth["oracle_waveform"] = oracle_row.get("oracle_waveform")
            ground_truth["oracle_BER"] = _safe_float(oracle_row.get("oracle_BER"))
            ground_truth["oracle_ACS"] = _safe_float(oracle_row.get("oracle_ACS"))

        case_id = f"E-{row['scenario_id']}{int(row['frame']):03d}"
        cases.append(EvalCase(
            case_id=case_id,
            case_type=CaseType.EXACT,
            suite=suite,
            input_conditions=input_conds,
            ground_truth_available=True,
            ground_truth=ground_truth,
            ood=False,
        ))

    return cases


def generate_interior_cases(dataset: GoldenDataset, suite: EvalSuite) -> list[EvalCase]:
    """Generate INTERIOR cases at midpoints between existing dataset rows.

    These are inside the supported domain but not exact dataset rows.
    Ground truth is NOT available — predictions are labeled MODEL ESTIMATE.
    """
    cases: list[EvalCase] = []
    boundaries = dataset.get_domain_boundaries()

    snr_min = boundaries["snr_db"]["min"]
    snr_max = boundaries["snr_db"]["max"]
    speed_min = boundaries["speed_kmph"]["min"]
    speed_max = boundaries["speed_kmph"]["max"]

    # Generate interior points at mid-intervals
    snr_midpoints = [snr_min + (snr_max - snr_min) * f for f in [0.25, 0.5, 0.75]]
    speed_midpoints = [speed_min + (speed_max - speed_min) * f for f in [0.25, 0.5, 0.75]]

    envs = boundaries["environments"]
    channels = boundaries["channel_profiles"]
    mods = boundaries["modulations"]

    case_idx = 0
    for env, ch, mod, snr, speed in itertools.product(
        envs, channels, mods, snr_midpoints, speed_midpoints
    ):
        # Skip if this exact point exists in dataset
        if dataset.find_exact_match(env, speed, snr, ch, mod) is not None:
            continue

        doppler_hz = speed * (1000.0 / 3600.0) * 4e9 / 299_792_458.0

        input_conds = EvalCaseInput(
            environment=env,
            speed_kmph=speed,
            snr_db=snr,
            doppler_hz=doppler_hz,
            channel_profile=ch,
            modulation=mod,
        )

        case_idx += 1
        case_id = f"I-{case_idx:04d}"
        cases.append(EvalCase(
            case_id=case_id,
            case_type=CaseType.INTERIOR,
            suite=suite,
            input_conditions=input_conds,
            ground_truth_available=False,
            ground_truth=None,
            ood=False,
        ))

        if len(cases) >= 50:
            break

    return cases[:50]


def generate_boundary_cases(dataset: GoldenDataset, suite: EvalSuite) -> list[EvalCase]:
    """Generate BOUNDARY cases near the edges of the supported domain."""
    cases: list[EvalCase] = []
    boundaries = dataset.get_domain_boundaries()

    snr_min = boundaries["snr_db"]["min"]
    snr_max = boundaries["snr_db"]["max"]
    speed_min = boundaries["speed_kmph"]["min"]
    speed_max = boundaries["speed_kmph"]["max"]

    margin_snr = (snr_max - snr_min) * 0.05
    margin_speed = (speed_max - speed_min) * 0.05

    boundary_points = [
        # Near SNR min
        (env, speed_min + margin_speed, snr_min + margin_speed, ch, mod)
        for env, ch, mod in itertools.product(
            boundaries["environments"][:2],
            boundaries["channel_profiles"][:2],
            boundaries["modulations"][:2],
        )
    ] + [
        # Near SNR max
        (env, speed_max - margin_speed, snr_max - margin_speed, ch, mod)
        for env, ch, mod in itertools.product(
            boundaries["environments"][:2],
            boundaries["channel_profiles"][:2],
            boundaries["modulations"][:2],
        )
    ] + [
        # Near speed max
        (env, speed_max - margin_speed, snr_min + margin_speed * 2, ch, mod)
        for env, ch, mod in itertools.product(
            ["Highway", "HighSpeedRail"],
            ["EVA"],
            [4],
        )
    ]

    case_idx = 0
    for env, speed, snr, ch, mod in boundary_points:
        speed = max(0.0, min(speed, speed_max + margin_speed))
        snr = max(snr_min - margin_snr, min(snr, snr_max + margin_snr))

        doppler_hz = speed * (1000.0 / 3600.0) * 4e9 / 299_792_458.0

        input_conds = EvalCaseInput(
            environment=env,
            speed_kmph=speed,
            snr_db=snr,
            doppler_hz=doppler_hz,
            channel_profile=ch,
            modulation=mod,
        )

        exact = dataset.find_exact_match(env, speed, snr, ch, mod)
        has_gt = exact is not None

        case_idx += 1
        case_id = f"B-{case_idx:03d}"
        cases.append(EvalCase(
            case_id=case_id,
            case_type=CaseType.BOUNDARY,
            suite=suite,
            input_conditions=input_conds,
            ground_truth_available=has_gt,
            ground_truth=None,
            ood=False,
        ))

    return cases


def generate_ood_cases(dataset: GoldenDataset, suite: EvalSuite) -> list[EvalCase]:
    """Generate OOD (Out-of-Domain) cases.

    These test whether the AI system correctly REJECTS predictions
    for operating points outside the validated domain.

    Expected behavior: prediction must be REJECTED or UNAVAILABLE.
    BER/SER/PER/throughput/CQI must NEVER be fabricated.
    """
    cases: list[EvalCase] = []
    boundaries = dataset.get_domain_boundaries()

    snr_max = boundaries["snr_db"]["max"]
    speed_max = boundaries["speed_kmph"]["max"]

    ood_points = [
        # Extreme speed (beyond domain)
        ("Highway", speed_max + 100, 10.0, "EVA", 4, "speed_exceeds_domain"),
        ("HighSpeedRail", speed_max + 200, 5.0, "EVA", 4, "extreme_speed"),

        # Extreme SNR (below domain)
        ("Urban", 30.0, snr_max + 15, "EVA", 4, "snr_exceeds_domain"),

        # Invalid environment
        ("Space", 1000.0, 30.0, "EVA", 4, "invalid_environment"),

        # Invalid channel profile
        ("Urban", 30.0, 15.0, "CUSTOM_channel", 4, "invalid_channel"),

        # Invalid modulation
        ("Urban", 30.0, 15.0, "EVA", 256, "invalid_modulation"),

        # Extreme speed + extreme SNR combined
        ("Highway", speed_max + 50, snr_max + 10, "ETU", 64, "compound_ood"),
    ]

    for i, (env, speed, snr, ch, mod, reason) in enumerate(ood_points, 1):
        doppler_hz = speed * (1000.0 / 3600.0) * 4e9 / 299_792_458.0

        input_conds = EvalCaseInput(
            environment=env,
            speed_kmph=speed,
            snr_db=snr,
            doppler_hz=doppler_hz,
            channel_profile=ch,
            modulation=mod,
        )

        case_id = f"OOD-{i:03d}"
        cases.append(EvalCase(
            case_id=case_id,
            case_type=CaseType.OOD,
            suite=suite,
            input_conditions=input_conds,
            ground_truth_available=False,
            ground_truth=None,
            ood=True,
            ood_reason=reason,
            expected_behavior="REJECTED or UNAVAILABLE — no BER/SER/PER/throughput/CQI fabricated",
        ))

    return cases


def generate_cases(
    dataset: GoldenDataset,
    suite: EvalSuite,
) -> list[EvalCase]:
    """Generate all evaluation cases for a given suite."""
    if suite == EvalSuite.FULL_REGRESSION:
        cases = []
        cases.extend(generate_exact_cases(dataset, suite))
        cases.extend(generate_interior_cases(dataset, suite))
        cases.extend(generate_boundary_cases(dataset, suite))
        cases.extend(generate_ood_cases(dataset, suite))
        return cases

    elif suite == EvalSuite.PREDICTION_ACCURACY:
        return generate_exact_cases(dataset, suite)

    elif suite == EvalSuite.OOD_SAFETY:
        return generate_ood_cases(dataset, suite)

    elif suite == EvalSuite.ROBUSTNESS:
        cases = []
        cases.extend(generate_boundary_cases(dataset, suite))
        cases.extend(generate_ood_cases(dataset, suite))
        return cases

    return []


def _safe_float(val: Any) -> Optional[float]:
    """Safely convert a value to float, returning None for NaN/missing."""
    if val is None or val == "" or val == "nan" or val == "None":
        return None
    try:
        f = float(val)
        if f != f:  # NaN check
            return None
        return f
    except (ValueError, TypeError):
        return None
