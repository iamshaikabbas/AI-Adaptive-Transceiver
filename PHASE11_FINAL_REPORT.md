# PHASE 11 FINAL REPORT

## A. Objective
Extend the AI-Adaptive-Transceiver so users can evaluate custom operating conditions without requiring MATLAB at runtime, using a hybrid model-based deployment approach.

## B. Existing Architecture
- Phase 8: FastAPI + 21 REST endpoints + 2 graph-serving endpoints
- Phase 9.1: Frame-by-frame MATLAB execution with PAUSE/STOP/RESUME
- Phase 10: React + TypeScript + Vite + Tailwind CSS frontend (light theme)
- Phase 3: Canonical AI policy (adaptive_config_v2.json + ai_engine_v2.py)

## C. Hybrid Architecture
```
React → FastAPI → DeploymentDataService
                      ├── Validated Dataset (584 operating points)
                      ├── Phase-3 RF Models (6 targets × 2 waveforms)
                      ├── Neighborhood Retrieval (k=5, normalized distance)
                      ├── OOD Detection (empirical percentile thresholds)
                      ├── Confidence Classification (4 levels)
                      └── Phase-3 AI Decision (canonical logic)
```

## D. Dataset
- Source: final_dataset.csv (2336 rows × 82 columns)
- Operating points: 584 unique (scenario, frame) groups
- Checksum: faa877a248c0f599a87f21dabf4df358 (unchanged)
- 18 scenarios, 4 strategies, 5 environments, 3 channel profiles

## E. Phase-3 Models
- 6 RandomForest regressors: Log10BER, Throughput, CQI, ACS, PER, SE
- Wrapped in sklearn Pipelines (preprocessing + RF)
- Input: 12 features (3 categorical + 9 numerical)
- Output: 6 metric predictions per waveform
- Tree-level dispersion used for uncertainty estimation

## F. Custom Input
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
- Doppler derived deterministically from speed × carrier_freq / c
- waveform not a user input — model called twice (OTFS, ODDM)
- detector is informational only (waveform-dependent)

## G. Regression
- 6 targets × 2 waveforms = 12 predictions per evaluation
- Post-processing: clip to valid ranges, max(0, ...) for throughput
- Latency lookup from training medians

## H. Neighbor Retrieval
- Normalized Euclidean distance: (speed_dist + snr_dist + doppler_dist) / 3
- Each feature normalized by dataset range
- Same categorical group required (environment, channel, modulation)
- k=5 nearest neighbors returned

## I. Uncertainty
- RandomForest tree-level dispersion
- Per-prediction: mean, std, p10, p90
- Delta method approximation for Log10BER → BER transformation
- No fabricated confidence — null where unreliable

## J. OOD Detection
- EXACT: exact match in 584 operating points
- COVERED: inside envelope, distance < 75th percentile
- NEAR_BOUNDARY: inside ranges but sparse/distant
- OOD: outside ranges or invalid categorical combination
- Empirical thresholds from dataset's own NN distance distribution

## K. Confidence
- Based on: coverage, NN distance, RF dispersion, neighborhood consistency
- HIGH: exact or dense, low dispersion, strong agreement
- MEDIUM: moderate distance or some disagreement
- LOW: sparse or high uncertainty
- UNAVAILABLE: OOD or unsupported

## L. Phase-3 Decision
- Canonical logic from ai_engine_v2.py
- Objective: ACS (maximize)
- Switch margin: 0.01 abs or 2% relative
- Min dwell: 3 frames
- policy_version = "phase3"

## M. API
- POST /api/custom/evaluate → full evaluation
- GET /api/custom/schema → supported values for form generation
- 2 new endpoints, 12 new Pydantic models
- No MATLAB invocation in deployment mode

## N. Frontend
- New page: Custom Evaluation (sidebar nav item)
- Dynamic form from schema endpoint
- Coverage/confidence badges
- OTFS/ODDM prediction panels with uncertainty
- Neighborhood consistency display
- Phase-3 decision with reason
- Nearest operating points table
- Disclaimer about model-based estimates

## O. Edge Cases
19 edge cases tested: exact, interior, boundary, OOD, malformed, NaN, negative speed, unknown environment, etc.

## P. Validation
- 40/40 tests passing
- 9 categories: dataset, model, exact, regression, neighborhood, uncertainty, OOD, AI, API, edge cases
- All tests non-vacuous

## Q. Data Integrity
- Phase-6 checksum: faa877a248c0f599a87f21dabf4df358 ✓
- 42 graphs: unchanged ✓
- Phase-3 models: 6 files unchanged ✓
- Phase-3 config: unchanged ✓
- Frontend build: 0 TypeScript errors ✓
- Bundle: 589 KB JS, 20.6 KB CSS

## R. Limitations
1. Predictions are model-based estimates, not physical measurements
2. Uncertainty is tree dispersion, not true aleatoric uncertainty
3. Doppler derived from speed, not independently specified
4. Constant features (carrier_freq, bandwidth) fixed to training values
5. Channel parameters (delay_spread, num_paths) looked up from dataset
6. Model trained on 1158 rows — may not generalize far from training domain

## S. Deployment Readiness
- All implementation tests pass (40/40)
- Frontend builds (0 TS errors)
- Existing Digital Twin page still works
- Phase-3 policy remains canonical
- Phase-6 checksum unchanged
- No MATLAB required for deployment mode
- Custom in-range conditions produce model-based estimates
- OOD conditions explicitly rejected
- No fabricated metrics

## T. Files Created
- `backend/deployment_data_service.py` — Core service
- `frontend/src/pages/CustomEvaluation.tsx` — UI page
- `otfs_ai_pipeline/phase11_validation.py` — 40-test suite
- `PHASE11_ARCHITECTURE.md`
- `PHASE11_CUSTOM_EVALUATION.md`
- `PHASE11_OOD_METHOD.md`
- `PHASE11_VALIDATION.md`
- `PHASE11_FINAL_REPORT.md`

## U. Files Modified
- `backend/main.py` — 2 new endpoints + imports
- `backend/models.py` — 12 new Pydantic models
- `frontend/src/App.tsx` — Custom Evaluation page route
- `frontend/src/components/Sidebar.tsx` — Nav item
- `frontend/src/types/api.ts` — TypeScript types
- `frontend/src/services/api.ts` — API functions

## V. Files Preserved
- `final_dataset.csv` — Frozen, checksum unchanged
- `metric_models_v2/` — All 7 files unchanged
- `adaptive_config_v2.json` — Phase-3 config unchanged
- `ai_engine_v2.py` — Phase-3 engine unchanged
- `dt_step_frame.m` — MATLAB execution unchanged
- All Phase-8/9/10 files unchanged
- All Phase-7 graphs unchanged

## W. Final Recommendation
Phase 11 is **COMPLETE**. The hybrid model-based deployment is functional, validated, and ready for use. No deployment action is taken per instructions.
