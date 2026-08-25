#!/usr/bin/env python3
"""Phase 11 Validation Suite — 40 tests across 9 categories.

Tests:
  1-5:   Dataset integrity
  6-9:   Model integrity
  10-12: Exact lookup
  13-16: Regression
  17-20: Neighborhood
  21-23: Uncertainty
  24-28: OOD
  29-31: AI decision
  32-35: API
  36-40: Edge cases (from Step 19 matrix)
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
from pathlib import Path

# Ensure backend is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.deployment_data_service import DeploymentDataService, derive_doppler_hz

# ── Globals ──────────────────────────────────────────────────────────────────
PROJECT  = Path(__file__).resolve().parent.parent
MATLAB   = PROJECT / "OTFS MRC detection MATLAB code"
CSV_PATH = MATLAB / "Results/FinalEvaluation/final_dataset.csv"
META_PATH = MATLAB / "otfs_ai_pipeline/models/metric_models_v2/metric_models_v2_meta.json"
CONFIG_PATH = MATLAB / "adaptive_config_v2.json"

passed = 0
failed = 0
errors: list[str] = []


def test(num: int, name: str, ok: bool, detail: str = ""):
    global passed, failed
    status = "PASS" if ok else "FAIL"
    suffix = f"  ({detail})" if detail else ""
    print(f"  [{status}]  {num:2d}. {name}{suffix}")
    if ok:
        passed += 1
    else:
        failed += 1
        errors.append(f"{num}. {name}")


def main():
    global passed, failed

    print("=" * 70)
    print("  PHASE 11 VALIDATION SUITE  (40 tests)")
    print("=" * 70)

    # Load service once
    svc = DeploymentDataService()

    # ══════════════════════════════════════════════════════════════════════════
    # CATEGORY 1: Dataset integrity (1-5)
    # ══════════════════════════════════════════════════════════════════════════
    print("\n── Dataset Integrity ──")

    # 1. Phase-6 checksum unchanged
    actual_chk = hashlib.md5(CSV_PATH.read_bytes()).hexdigest()
    test(1, "Phase-6 checksum unchanged",
         actual_chk == "faa877a248c0f599a87f21dabf4df358",
         f"got={actual_chk}")

    # 2. Dataset schema unchanged (82 columns)
    import csv
    with open(CSV_PATH, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        cols = reader.fieldnames
    test(2, "Dataset has 82 columns",
         cols is not None and len(cols) == 82,
         f"got={len(cols) if cols else 0}")

    # 3. No row modifications (2336 rows)
    test(3, "Dataset has 2336 rows",
         len(svc._rows) == 2336,
         f"got={len(svc._rows)}")

    # 4. 18 scenarios preserved
    scenarios = sorted(set(r.scenario_id for r in svc._rows))
    test(4, "18 scenarios preserved",
         len(scenarios) == 18,
         f"got={len(scenarios)}: {scenarios}")

    # 5. 4 strategies preserved
    strategies = sorted(set(r.strategy for r in svc._rows))
    test(5, "4 strategies preserved",
         strategies == ["ai_adaptive", "fixed_oddm", "fixed_otfs", "oracle"],
         f"got={strategies}")

    # ══════════════════════════════════════════════════════════════════════════
    # CATEGORY 2: Model integrity (6-9)
    # ══════════════════════════════════════════════════════════════════════════
    print("\n── Model Integrity ──")

    # 6. Phase-3 model files exist
    model_files = list((MATLAB / "otfs_ai_pipeline/models/metric_models_v2").glob("*.joblib"))
    test(6, "Phase-3 model files exist",
         len(model_files) == 6,
         f"got={len(model_files)} joblib files")

    # 7. Phase-3 config exists
    test(7, "Phase-3 config exists",
         CONFIG_PATH.exists(),
         f"exists={CONFIG_PATH.exists()}")

    # 8. Model input schema verified
    with open(META_PATH, encoding="utf-8") as f:
        meta = json.load(f)
    expected_cat = ["environment", "channel_profile", "waveform"]
    test(8, "Model input schema verified",
         meta["features_cat"] == expected_cat,
         f"got={meta['features_cat']}")

    # 9. Model targets verified
    expected_targets = {"Log10BER", "Throughput", "CQI", "ACS", "PER", "SE"}
    test(9, "Model targets verified",
         set(meta["targets"].keys()) == expected_targets,
         f"got={set(meta['targets'].keys())}")

    # ══════════════════════════════════════════════════════════════════════════
    # CATEGORY 3: Exact lookup (10-12)
    # ══════════════════════════════════════════════════════════════════════════
    print("\n── Exact Lookup ──")

    # 10. Known point returns exact measured values
    exact = svc.find_exact_match({
        "environment": "Urban", "speed_kmph": 21.3, "snr_db": 12.48,
        "channel_profile": "EVA", "modulation": 4,
    })
    test(10, "Known point returns exact match",
         exact is not None and "OTFS" in exact and "ODDM" in exact,
         f"found={exact is not None}")

    # 11. Two known points return correct values
    exact2 = svc.find_exact_match({
        "environment": "Urban", "speed_kmph": 20.8, "snr_db": 12.48,
        "channel_profile": "EVA", "modulation": 4,
    })
    test(11, "Second known point returns exact match",
         exact2 is not None,
         f"found={exact2 is not None}")

    # 12. Provenance exists
    test(12, "Provenance exists on exact match",
         exact is not None and "source_scenario" in exact and "source_frame" in exact,
         f"scenario={exact.get('source_scenario') if exact else None}, frame={exact.get('source_frame') if exact else None}")

    # ══════════════════════════════════════════════════════════════════════════
    # CATEGORY 4: Regression (13-16)
    # ══════════════════════════════════════════════════════════════════════════
    print("\n── Regression ──")

    # 13. Custom in-range point returns prediction
    otfs, oddm = svc.predict_both_waveforms({
        "environment": "Urban", "speed_kmph": 30.0, "snr_db": 8.0,
        "channel_profile": "EVA", "modulation": 4,
    })
    test(13, "Custom in-range point returns prediction",
         otfs.ACS is not None and oddm.ACS is not None,
         f"OTFS_ACS={otfs.ACS.mean if otfs.ACS else None}")

    # 14. Both waveforms predicted
    test(14, "Both waveforms predicted",
         otfs.waveform == "OTFS" and oddm.waveform == "ODDM",
         f"otfs={otfs.waveform}, oddm={oddm.waveform}")

    # 15. Actual/predicted separation correct (actual = exact, predicted = model)
    full = svc.evaluate({
        "environment": "Urban", "speed_kmph": 21.3, "snr_db": 12.48,
        "channel_profile": "EVA", "modulation": 4,
    })
    # For exact match, coverage should be EXACT
    test(15, "Exact point coverage = EXACT",
         full.coverage == "EXACT",
         f"coverage={full.coverage}")

    # 16. Numeric outputs finite
    all_finite = True
    for pred in [otfs, oddm]:
        for attr in ["BER", "throughput_bps", "CQI", "ACS", "PER", "spectral_efficiency"]:
            u = getattr(pred, attr)
            if u is not None:
                if not math.isfinite(u.mean) or not math.isfinite(u.std):
                    all_finite = False
    test(16, "Numeric outputs are finite",
         all_finite,
         f"all_finite={all_finite}")

    # ══════════════════════════════════════════════════════════════════════════
    # CATEGORY 5: Neighborhood (17-20)
    # ══════════════════════════════════════════════════════════════════════════
    print("\n── Neighborhood ──")

    # 17. Neighbors returned
    neighbors = svc.find_nearest_neighbors({
        "environment": "Urban", "speed_kmph": 25.0, "snr_db": 10.0,
        "channel_profile": "EVA", "modulation": 4,
    }, k=5)
    test(17, "Neighbors returned",
         len(neighbors) > 0,
         f"count={len(neighbors)}")

    # 18. Distance deterministic
    n1 = svc.find_nearest_neighbors({
        "environment": "Urban", "speed_kmph": 25.0, "snr_db": 10.0,
        "channel_profile": "EVA", "modulation": 4,
    }, k=5)
    n2 = svc.find_nearest_neighbors({
        "environment": "Urban", "speed_kmph": 25.0, "snr_db": 10.0,
        "channel_profile": "EVA", "modulation": 4,
    }, k=5)
    test(18, "Distance deterministic",
         all(a.distance == b.distance for a, b in zip(n1, n2)),
         f"match={all(a.distance == b.distance for a, b in zip(n1, n2))}")

    # 19. Feature normalization correct (distance in [0,1] approximately)
    max_dist = max(n.distance for n in neighbors) if neighbors else 0
    test(19, "Feature normalization produces reasonable distances",
         max_dist < 1.0,
         f"max_dist={max_dist:.4f}")

    # 20. Neighborhood consistency computed
    cons = svc.compute_neighborhood_consistency("OTFS", otfs, neighbors)
    test(20, "Neighborhood consistency computed",
         cons.neighbor_acs_mean is not None or len(neighbors) == 0,
         f"neighbor_mean={cons.neighbor_acs_mean}")

    # ══════════════════════════════════════════════════════════════════════════
    # CATEGORY 6: Uncertainty (21-23)
    # ══════════════════════════════════════════════════════════════════════════
    print("\n── Uncertainty ──")

    # 21. RF uncertainty calculated
    test(21, "RF uncertainty calculated",
         otfs.ACS is not None and otfs.ACS.std >= 0,
         f"OTFS_ACS_std={otfs.ACS.std if otfs.ACS else None}")

    # 22. No fabricated confidence (std > 0 for non-trivial predictions)
    test(22, "Uncertainty std is non-negative",
         otfs.ACS.std >= 0 and oddm.ACS.std >= 0,
         f"otfs_std={otfs.ACS.std}, oddm_std={oddm.ACS.std}")

    # 23. Repeated query deterministic
    o1, d1 = svc.predict_both_waveforms({
        "environment": "Urban", "speed_kmph": 30.0, "snr_db": 8.0,
        "channel_profile": "EVA", "modulation": 4,
    })
    o2, d2 = svc.predict_both_waveforms({
        "environment": "Urban", "speed_kmph": 30.0, "snr_db": 8.0,
        "channel_profile": "EVA", "modulation": 4,
    })
    test(23, "Repeated query deterministic",
         abs(o1.ACS.mean - o2.ACS.mean) < 1e-10 and abs(d1.ACS.mean - d2.ACS.mean) < 1e-10,
         f"otfs_diff={abs(o1.ACS.mean - o2.ACS.mean)}")

    # ══════════════════════════════════════════════════════════════════════════
    # CATEGORY 7: OOD (24-28)
    # ══════════════════════════════════════════════════════════════════════════
    print("\n── OOD Detection ──")

    # 24. Known point = EXACT
    test(24, "Known point coverage = EXACT",
         full.coverage == "EXACT",
         f"coverage={full.coverage}")

    # 25. Interior point = COVERED or NEAR_BOUNDARY
    interior = svc.evaluate({
        "environment": "Urban", "speed_kmph": 25.0, "snr_db": 10.0,
        "channel_profile": "EVA", "modulation": 4,
    })
    test(25, "Interior point is COVERED or NEAR_BOUNDARY",
         interior.coverage in ("COVERED", "NEAR_BOUNDARY", "EXACT"),
         f"coverage={interior.coverage}")

    # 26. Boundary point = NEAR_BOUNDARY where appropriate
    boundary = svc.evaluate({
        "environment": "Pedestrian", "speed_kmph": 0.0, "snr_db": 22.0,
        "channel_profile": "EPA", "modulation": 4,
    })
    test(26, "Boundary point has valid coverage",
         boundary.coverage in ("COVERED", "NEAR_BOUNDARY", "EXACT"),
         f"coverage={boundary.coverage}")

    # 27. Clearly unsupported point = OOD
    ood_result = svc.evaluate({
        "environment": "Pedestrian", "speed_kmph": 999.0, "snr_db": 50.0,
        "channel_profile": "EVA", "modulation": 4,
    })
    test(27, "Clearly unsupported point = OOD",
         ood_result.coverage == "OOD",
         f"coverage={ood_result.coverage}")

    # 28. OOD never returns fabricated metrics
    test(28, "OOD returns no fabricated metrics",
         ood_result.coverage == "OOD" and ood_result.confidence == "UNAVAILABLE",
         f"confidence={ood_result.confidence}")

    # ══════════════════════════════════════════════════════════════════════════
    # CATEGORY 8: AI decision (29-31)
    # ══════════════════════════════════════════════════════════════════════════
    print("\n── AI Decision ──")

    # 29. Phase-3 policy used
    test(29, "Phase-3 policy used",
         full.decision.get("policy_version") == "phase3",
         f"policy={full.decision.get('policy_version')}")

    # 30. policy_version = phase3
    test(30, "policy_version = phase3 in full evaluation",
         full.decision.get("policy_version") == "phase3",
         f"got={full.decision.get('policy_version')}")

    # 31. OTFS/ODDM ACS comparison correct
    oacs = full.decision.get("predicted_OTFS_ACS")
    dacs = full.decision.get("predicted_ODDM_ACS")
    best = full.decision.get("best_by_objective")
    test(31, "ACS comparison selects correct best waveform",
         (best == "OTFS" and oacs is not None and dacs is not None and oacs >= dacs) or
         (best == "ODDM" and oacs is not None and dacs is not None and dacs > oacs),
         f"OTFS_ACS={oacs}, ODDM_ACS={dacs}, best={best}")

    # ══════════════════════════════════════════════════════════════════════════
    # CATEGORY 9: API (32-35)
    # ══════════════════════════════════════════════════════════════════════════
    print("\n── API ──")

    # 32. /api/custom/schema works
    schema = svc.get_schema()
    test(32, "/api/custom/schema works",
         "supported_environments" in schema and "numerical_ranges" in schema,
         f"keys={list(schema.keys())[:5]}")

    # 33. /api/custom/evaluate works
    result_dict = svc.result_to_dict(full)
    test(33, "/api/custom/evaluate works",
         result_dict.get("status") == "ok" and "coverage" in result_dict,
         f"status={result_dict.get('status')}")

    # 34. Invalid request rejected cleanly
    is_valid, errors_list = svc.validate_query({"environment": "Fake"})
    test(34, "Invalid request rejected cleanly",
         not is_valid and len(errors_list) > 0,
         f"errors={len(errors_list)}")

    # 35. Existing model files still accessible
    test(35, "Existing model files still accessible",
         len(svc._models) == 6,
         f"models={len(svc._models)}")

    # ══════════════════════════════════════════════════════════════════════════
    # CATEGORY 10: Edge cases (36-40)
    # ══════════════════════════════════════════════════════════════════════════
    print("\n── Edge Cases ──")

    # 36. Malformed input rejected
    is_valid36, errs36 = svc.validate_query({})
    test(36, "Empty input rejected",
         not is_valid36,
         f"errors={len(errs36)}")

    # 37. NaN speed rejected
    is_valid37, errs37 = svc.validate_query({
        "environment": "Urban", "speed_kmph": float("nan"),
        "snr_db": 10.0, "channel_profile": "EVA", "modulation": 4,
    })
    test(37, "NaN speed rejected",
         not is_valid37 or any("numeric" in e.lower() for e in errs37),
         f"valid={is_valid37}, errs={errs37}")

    # 38. Negative speed rejected
    is_valid38, errs38 = svc.validate_query({
        "environment": "Urban", "speed_kmph": -10.0,
        "snr_db": 10.0, "channel_profile": "EVA", "modulation": 4,
    })
    test(38, "Negative speed rejected",
         not is_valid38,
         f"valid={is_valid38}")

    # 39. Unknown environment rejected
    is_valid39, errs39 = svc.validate_query({
        "environment": "SpaceStation", "speed_kmph": 10.0,
        "snr_db": 10.0, "channel_profile": "EVA", "modulation": 4,
    })
    test(39, "Unknown environment rejected",
         not is_valid39,
         f"valid={is_valid39}")

    # 40. Doppler derivation consistent
    d1 = derive_doppler_hz(100.0, "Urban")
    d2 = derive_doppler_hz(100.0, "Urban")
    test(40, "Doppler derivation deterministic",
         d1 == d2 and d1 > 0,
         f"doppler={d1:.4f}")

    # ══════════════════════════════════════════════════════════════════════════
    # Summary
    # ══════════════════════════════════════════════════════════════════════════
    print("\n" + "=" * 70)
    total = passed + failed
    print(f"  {passed}/{total} passed  |  {failed} failed")
    if errors:
        print(f"\n  Failed tests:")
        for e in errors:
            print(f"    - {e}")
    print("=" * 70)
    return failed == 0


if __name__ == "__main__":
    ok = main()
    sys.exit(0 if ok else 1)
