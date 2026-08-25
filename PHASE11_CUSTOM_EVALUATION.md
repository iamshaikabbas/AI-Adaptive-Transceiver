# PHASE 11 CUSTOM EVALUATION

## API

### POST /api/custom/evaluate

**Request:**
```json
{
  "environment": "Urban",
  "speed_kmph": 117,
  "snr_db": 9.3,
  "channel_profile": "EVA",
  "modulation": 16,
  "detector": "LMMSE"
}
```

**Response (COVERED):**
```json
{
  "status": "ok",
  "coverage": "COVERED",
  "confidence": "HIGH",
  "input": {
    "environment": "Urban",
    "speed_kmph": 117.0,
    "snr_db": 9.3,
    "doppler_hz": 433.4,
    "channel_profile": "EVA",
    "modulation": 16,
    "detector": "LMMSE"
  },
  "nearest_neighbors": [
    {
      "distance": 0.08,
      "speed_difference": 3.0,
      "snr_difference": 0.7,
      "source_scenario": "A",
      "source_frame": 23
    }
  ],
  "predictions": {
    "OTFS": {
      "waveform": "OTFS",
      "detector": "MRC",
      "ACS": {"mean": 0.731, "std": 0.04, "p10": 0.67, "p90": 0.77},
      "BER": {"mean": 0.012, "std": 0.003, "p10": 0.008, "p90": 0.016}
    },
    "ODDM": { "..." : "..." }
  },
  "consistency": {
    "OTFS": {
      "predicted_acs": 0.731,
      "neighbor_acs_mean": 0.724,
      "neighbor_acs_range": [0.701, 0.748],
      "deviation": 0.007,
      "consistent": true
    }
  },
  "decision": {
    "selected_waveform": "OTFS",
    "policy_version": "phase3",
    "reason": "keep OTFS: already best by ACS"
  },
  "warnings": []
}
```

**Response (OOD):**
```json
{
  "status": "ok",
  "coverage": "OOD",
  "confidence": "UNAVAILABLE",
  "predictions": {"OTFS": null, "ODDM": null},
  "decision": {"selected_waveform": null, "policy_version": "phase3"},
  "warnings": ["Operating point is outside validated model coverage."]
}
```

### GET /api/custom/schema

Returns supported environments, channel profiles, modulations, detectors, numerical ranges, and coverage rules.

## Frontend

### Custom Evaluation Page

Add sidebar item "Custom Eval" → CustomEvaluation.tsx

**Input controls:**
- Environment (dropdown)
- Speed (number input)
- SNR (number input)
- Channel Profile (dropdown)
- Modulation (dropdown)
- Detector (dropdown, optional)
- Evaluate button

**Results display:**
- Coverage badge (EXACT/COVERED/NEAR_BOUNDARY/OOD)
- Confidence badge (HIGH/MEDIUM/LOW/UNAVAILABLE)
- OTFS panel: BER, Throughput, CQI, ACS, PER, SE with uncertainty
- ODDM panel: same
- Neighborhood consistency for each waveform
- Phase-3 AI Decision: selected waveform, reason, policy
- Nearest operating points table
- Disclaimer about model-based estimates

## Limitations

- Predictions are model-based estimates, not physical measurements
- Coverage depends on training data distribution
- Uncertainty is estimated from tree dispersion, not true aleatoric uncertainty
- Doppler is derived deterministically from speed
- Constant features (carrier_freq, bandwidth) are fixed to training values
