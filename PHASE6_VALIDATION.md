# PHASE 6 DATASET VALIDATION REPORT

## Metadata

| Field | Value |
|---|---|
| Dataset | final_dataset.csv (2336 rows x 82 columns) |
| Generated | 2026-08-25 |
| Generator | phase6_final_dataset.py |
| Scenarios loaded | 18 scenarios x 4 strategies = 72 trace files loaded |
| Overall data quality | PASS |

## Validation Tests

| # | Test | Status | Evidence |
|---|------|--------|----------|
| T01 | All 18 scenarios present (A–R) | PASS | `SCENARIOS: ['A','B','C','D','E','F','G','H','I','J','K','L','M','N','O','P','Q','R']` — 18 unique scenario IDs confirmed |
| T02 | All 4 strategies present | PASS | `STRATEGIES: ['ai_adaptive','fixed_oddm','fixed_otfs','oracle']` — 4 unique strategies confirmed |
| T03 | Row count = 2336 (sum of per-scenario frames) | PASS | `total_rows: 2336`; frames_per_scenario sums: 60+60+60+60+24+24+24+30+24+24+24+24+24+24+25+25+24+24 = 584 × 4 = 2336 |
| T04 | Equal rows per strategy (584 each) | PASS | `AI_ROWS: 584`; metadata shows 4 strategies; 2336 / 4 = 584 |
| T05 | No duplicate rows (scenario_id + frame + strategy unique) | PASS | `DUP_CHECK: 0` — zero duplicate composite keys found |
| T06 | No missing required fields in final_dataset.csv | PASS | data_quality_report.json `no_missing_required.pass: true`; all 22 required fields have 0 null values |
| T07 | BER >= 0 and finite for all rows | PASS | `BER_RANGE: 0.0 0.4507`; `ber_nonnegative_finite.pass: true`, negative_count=0, infinite_count=0 |
| T08 | BER <= 1 for all rows | PASS | `BER_RANGE: 0.0 0.4507`; `ber_le_1.pass: true`, over_one_count=0 |
| T09 | Throughput >= 0 for all rows | PASS | `THROUGHPUT_NEG: 0`; `throughput_nonnegative.pass: true` |
| T10 | CQI in [0, 15] for all rows | PASS | `CQI_RANGE: 2 15`; `cqi_range.pass: true`, out_of_range_count=0 |
| T11 | ACS in [0, 1] for all rows | PASS | `ACS_RANGE: 0.086 0.989`; `acs_range.pass: true`, out_of_range_count=0 |
| T12 | SER >= BER for all rows (diagnostic) | PASS | `SER_GE_BER: True`; `ser_ge_ber.pass: true`, violation_count=0, total_compared=2336 |
| T13 | Valid waveform names (OTFS, ODDM only) | PASS | `WAVEFORMS: ['ODDM','OTFS']`; `valid_waveforms.pass: true`, invalid_values=[] |
| T14 | Valid channel profiles (EPA, EVA, ETU only) | PASS | `CHANNELS: ['EPA','ETU','EVA']`; `valid_channels.pass: true`, invalid_values=[] |
| T15 | Valid modulation labels (QPSK, 16QAM, 64QAM) | PASS | `MOD_LABELS: ['16QAM','64QAM','QPSK']`; `valid_modulations.pass: true`, invalid_values=[] |
| T16 | master_seed = 20260823 for all rows | PASS | `MASTER_SEED: [20260823.]` — single consistent seed value across all rows |
| T17 | policy_version = phase3 for all rows | PASS | `POLICY: ['phase3']` — single consistent policy version |
| T18 | experiment_id present and non-empty | PASS | `EXP_ID: True` — column exists and is non-empty in all rows |
| T19 | predicted_OTFS_throughput column exists (renamed from predicted_OTFS_TP) | PASS | Column `predicted_OTFS_throughput` present in metadata column list (index 44 of 82 columns) |
| T20 | 16/16 automated data quality checks pass | PASS | data_quality_report.json `overall_pass: true`; all 16 checks (no_duplicates, no_missing_required, ber_nonnegative_finite, ber_le_1, throughput_nonnegative, cqi_range, acs_range, ser_ge_ber, valid_waveforms, valid_channels, valid_modulations, valid_strategies, consistent_seeds, latency_modeled_nan, ai_prediction_columns, oracle_comparison_fields) report pass=true |

## Summary Statistics

| Metric | Value |
|---|---|
| Total rows | 2,336 |
| Total columns | 82 |
| Scenarios | 18 (A–R) |
| Strategies | 4 (fixed_otfs, fixed_oddm, ai_adaptive, oracle) |
| Rows per strategy | 584 |
| AI adaptive switches | 22 |
| Oracle agreement rate | 82.7% |
| BER range | [0.000, 0.451] |
| Throughput range | [0, 900000] bps |
| CQI range | [2, 15] |
| ACS range | [0.086, 0.989] |
| SNR range | [-2.15, 22.99] dB |
| Speed range | [0, 350] km/h |

---

**RESULT: 20/20 PASS**
