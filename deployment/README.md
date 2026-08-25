## Phase 11A — MATLAB Digital Twin Results (JSON Export)

### Purpose
Export the validated MATLAB Digital Twin simulation results into a deployment-ready JSON dataset.
**No MATLAB required at runtime.** All data is precomputed and stored in `digital_twin_results.json`.

### Files
| File | Purpose |
|------|---------|
| `data/digital_twin_results.json` | 584 operating points (1.15 MB), OTFS+ODDM metrics, AI predictions, oracle ground truth |
| `data/metadata.json` | Dataset metadata, value ranges, known limitations |
| `export_deployment_data.py` | Exporter: reads `final_dataset.csv`, produces the JSON |
| `validate_deployment_data.py` | 20-test validation suite |
| `test_lookup.py` | 5-point lookup verification against source CSV |

### JSON Schema (`digital_twin_results.json`)
```json
{
  "schema_version": "1.0",
  "policy_version": "phase3",
  "master_seed": 20260823,
  "operating_points": [
    {
      "id": "UrbanFast_21.6_13.5_119.8_ETU_4",
      "source_scenario": "A",
      "source_frame": 1,
      "conditions": {
        "environment": "UrbanFast",
        "speed_kmph": 21.6,
        "snr_db": 13.5,
        "doppler_hz": 119.8,
        "channel_profile": "ETU",
        "modulation": 4
      },
      "waveforms": {
        "OTFS": { "BER": 0.0, "SER": 0.0, "PER": 0.0, "throughput_bps": ..., "CQI": ..., "ACS": ..., "detector": "MRC" },
        "ODDM": { "BER": 0.003, "SER": 0.001, "PER": 0.0, "throughput_bps": ..., "CQI": ..., "ACS": ..., "detector": "LMMSE" }
      },
      "ai_prediction": {
        "predicted_OTFS_BER": ..., "predicted_ODDM_BER": ...,
        "predicted_OTFS_ACS": ..., "predicted_ODDM_ACS": ...,
        "selected_waveform": "OTFS",
        "oracle_waveform": "OTFS",
        "confidence": 0.92,
        "switched": false,
        "switch_reason": null
      },
      "oracle": {
        "oracle_waveform": "OTFS",
        "oracle_BER": 0.0,
        "oracle_ACS": 0.95,
        "ACS_regret": 0.009,
        "decision_correct": 1
      }
    }
  ]
}
```

### Operating-Point Model
Each entry groups **both OTFS and ODDM** results under shared physical conditions
(speed, SNR, doppler, environment, channel, modulation). One entry = one unique physical scenario.

- **OTFS metrics**: From `fixed_otfs` strategy rows (MRC detector).
- **ODDM metrics**: From `fixed_oddm` strategy rows (LMMSE detector).
- **AI predictions**: From `ai_adaptive` rows (neural network only — no detector data).
- **Oracle**: From `oracle` strategy rows (brute-force optimal selection).

### Detector Assignment (Waveform-Dependent)
| Waveform | Detector |
|----------|----------|
| OTFS | MRC (Maximum Ratio Combining) |
| ODDM | LMMSE (Linear Minimum Mean Square Error) |

Detectors are **not** part of `conditions` — they are intrinsic to the waveform.

### Provenance
Every operating point carries `source_scenario` and `source_frame` linking back to
`final_dataset.csv` rows. The `source_checksum` in the JSON header matches the frozen
Phase 6 dataset checksum (`faa877a248c0f599a87f21dabf4df358`).

### Usage (without MATLAB)
```python
import json

with open("deployment/data/digital_twin_results.json") as f:
    data = json.load(f)

# Find operating point for given conditions
target_speed = 30.0  # km/h
target_snr = 10.0    # dB

best = None
best_ber = float("inf")

for op in data["operating_points"]:
    conds = op["conditions"]
    if abs(conds["speed_kmph"] - target_speed) < 0.1 and abs(conds["snr_db"] - target_snr) < 0.1:
        otfs_ber = op["waveforms"]["OTFS"]["BER"]
        oddm_ber = op["waveforms"]["ODDM"]["BER"]
        if otfs_ber < best_ber:
            best_ber = otfs_ber
            best = ("OTFS", otfs_ber)
        if oddm_ber < best_ber:
            best_ber = oddm_ber
            best = ("ODDM", oddm_ber)

print(f"Best waveform: {best[0]}, BER={best[1]}")
```

### Validation
```bash
python deployment/validate_deployment_data.py   # 20/20 tests
python deployment/test_lookup.py                # 5/5 lookup tests
```

### Known Limitations
- 584 unique continuous operating points (one per frame per scenario)
- AI predictions only available for `ai_adaptive` strategy frames
- `latency_ms_modeled`, `packet_loss`, `recovery_rate`, `ai_error`, `fallback_used`, `fallback_reason`, `confidence_band` all null in source — excluded from export
