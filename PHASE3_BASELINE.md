# PHASE 3 BASELINE RECORD (frozen 2026-08-23)

This file freezes the Phase-3 results as the comparison baseline for
Phase 4. Phase-4 work must NOT overwrite these numbers or traces.

## Versions

- Decision engine: `ai_engine_v2.py` (policy: adaptive_config_v2.json)
- Metric models: `models/metric_models_v2/` (RandomForest, trained on
  `Results/WaveformComparison/phase2_dataset.csv`, 1158 rows / 579 paired
  conditions; splits 278 train / 55 val / 246 test; random_state 42)
- Waveform classifier (not used by runtime decisions): `waveform_selector_v2.joblib`
- Runtime: `digital_twin_runtime.m` (seed0 = 20260823)
- Scenario set: A commute, B high_speed_rail, C pedestrian_day, D stress
  (`dt_scenarios.m`, rng(20260823)) — FINAL EVALUATION scenarios

## Policy parameters (Phase 3)

| parameter | value |
|---|---|
| objective | ACS (max) |
| min_confidence | 0.0 (gate disabled after fix) |
| switch_margin_acs (abs) | 0.01 (strict >) |
| switch_margin_rel | 0.02 (strict >); abs OR rel suffices |
| min_dwell_frames | 3 |
| fallback on AI failure | keep previous waveform, fallback_used=true |

## Final A-D FULL results (240 frames per strategy, identical seeds/chan/payload)

| strategy | mean BER | mean Throughput kbps | mean CQI | mean SE bps/Hz | mean ACS | mean Latency ms |
|---|---|---|---|---|---|---|
| fixed_otfs | 0.0571 | 296.3 | 10.863 | 0.6172 | 0.4778 | 31.60 |
| fixed_oddm | 0.0799 | 303.2 | 10.175 | 0.6316 | 0.4517 | 78.56 |
| ai_adaptive (P3) | 0.0572 | 303.7 | 10.838 | 0.6326 | **0.4807** | 35.85 |
| oracle | 0.0547 | 318.7 | 11.017 | 0.6640 | **0.4941** | 36.05 |

## Switching statistics (ai_adaptive)

- switches: 10 — scenario A frames 1(→ODDM),5(→OTFS),16(→ODDM),21(→OTFS);
  scenario D frames 1(→ODDM),5(→OTFS),47(→ODDM),51(→OTFS),56(→ODDM),60(→OTFS)
- frame usage: OTFS 219 / ODDM 21; switch rate 4.2%
- average dwell between switches ≈ 22 frames (min gap 4 ≥ min_dwell 3)
- AI/oracle agreement: 82.5% overall (Urban 79.8%, HSR 76.3%, Highway 88.9%,
  Pedestrian 90.2%)

## Regret (ai_adaptive vs oracle)

- mean abs BER regret: 6.14e-3; p90 2.27e-2; max 0.1255
- mean ACS regret: 0.01342; p90 ACS regret 1.97e-2
- fraction frames with >10% relative-BER regret: 23.75%

## Predicted vs actual (per-frame)

- log10-BER MAE: OTFS 2.124 decades / ODDM 2.524 (dominated by clipped
  zero-BER frames — bursty single-frame BER artifact)
- ACS MAE: OTFS 0.157 / ODDM 0.159; ACS-order flips 31/240 (12.9%)

## Baseline artifacts preserved

`Results/DigitalTwin/baseline_phase3/`: canonical
{fixed_otfs, fixed_oddm, ai_adaptive, oracle}_trace.csv (240 rows x 58 cols).
Reports: AI_Results/Reports/phase3_*.md; PHASE3_VALIDATION.md.

## Known weaknesses carried into Phase 4

1. agreement drops in fast environments (HSR 76.3%),
2. ACS regret concentrated in low-SNR / very-fast pockets,
3. zero-BER clipping inflates BER-prediction error metrics,
4. no uncertainty awareness in decisions,
5. thresholds inherited from Phase 1, never tuned.
