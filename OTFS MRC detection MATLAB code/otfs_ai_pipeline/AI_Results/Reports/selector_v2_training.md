# Waveform selector v2 - training report

Decisive conditions: 356 (train 160, val 31, unseen test 165); ties excluded: 223.
Selected model: **random_forest**.

| model | val acc | val macroF1 | test acc | test macroF1 | test regretBER(abs) | test frac regret>10% |
|---|---|---|---|---|---|---|
| random_forest | 0.935 | 0.733 | 0.945 | 0.640 | 6.75e-03 | 25.5% |
| gradient_boosting | 0.935 | 0.733 | 0.952 | 0.588 | 6.85e-03 | 27.3% |
| decision_tree | 0.935 | 0.733 | 0.952 | 0.654 | 6.83e-03 | 26.1% |
| dummy_majority | 0.935 | 0.483 | 0.952 | 0.488 | 6.85e-03 | 27.3% |

## Feature importance

- `modulation`: 0.3129
- `snr_db`: 0.2024
- `delay_spread_taps`: 0.0985
- `channel_profile`: 0.0933
- `doppler_spread_hz`: 0.0764
- `doppler_hz`: 0.0694
- `environment`: 0.0671
- `speed_kmph`: 0.0395
- `carrier_frequency_hz`: 0.0272
- `num_paths`: 0.0132
- `bandwidth_hz`: 0.0

## Confusion matrix on unseen test (rows=oracle, cols=pred)

| | OTFS | ODDM |
|---|---|---|
| OTFS | 154 | 3 |
| ODDM | 6 | 2 |

## Behaviour inside tie regions (no correct answer)

{'OTFS': 207, 'ODDM': 16}
