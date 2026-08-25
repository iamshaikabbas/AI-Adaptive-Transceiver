# PHASE 11 ARCHITECTURE

## Hybrid Model-Based Deployment

### Overview

Phase 11 extends the AI-Adaptive-Transceiver so users can enter custom operating conditions without requiring MATLAB at runtime. The system uses a **hybrid** approach: frozen validated dataset for exact lookup, frozen Phase-3 RF models for regression, and neighborhood analysis for confidence estimation.

### Architecture

```
React Frontend
    │
    ▼
FastAPI Backend (/api/custom/evaluate, /api/custom/schema)
    │
    ├── DeploymentDataService
    │     ├── Validated Dataset (final_dataset.csv, frozen)
    │     ├── Phase-3 RF Models (metric_models_v2, frozen)
    │     ├── Neighborhood Retrieval
    │     ├── OOD Detection
    │     └── Confidence Classification
    │
    └── Phase-3 AI Decision Logic
          └── ai_engine_v2.py (canonical, unchanged)
```

### Data Flow (Custom Evaluation)

1. **User Input**: environment, speed_kmph, snr_db, channel_profile, modulation
2. **Doppler Derivation**: speed × 1000/3600 × 4e9 / c (deterministic)
3. **Exact Lookup**: Search 584 operating points for exact match
4. **Nearest Neighbors**: Find k=5 nearest within same categorical group
5. **RF Regression**: Run 6 regressors × 2 waveforms (OTFS, ODDM)
6. **Uncertainty**: Tree-level dispersion (mean, std, p10, p90)
7. **Neighborhood Consistency**: Predicted ACS vs. neighbor ACS
8. **Coverage Classification**: EXACT / COVERED / NEAR_BOUNDARY / OOD
9. **Confidence Classification**: HIGH / MEDIUM / LOW / UNAVAILABLE
10. **Phase-3 Decision**: Canonical waveform selection

### Key Design Decisions

1. **Doppler is derived, not independent**: Matches MATLAB derivation
2. **Waveform is a model input**: Model called twice (OTFS, ODDM)
3. **Constants**: carrier_frequency_hz=4e9, bandwidth_hz=480000
4. **detector is informational only**: Not a model input (waveform-dependent)
5. **No MATLAB in deployment mode**: Pure Python pipeline

### Files Modified
- `backend/main.py` — Added 2 endpoints
- `backend/models.py` — Added Pydantic models
- `frontend/src/App.tsx` — Added Custom Evaluation page
- `frontend/src/components/Sidebar.tsx` — Added nav item
- `frontend/src/types/api.ts` — Added TypeScript types
- `frontend/src/services/api.ts` — Added API functions

### Files Created
- `backend/deployment_data_service.py` — Core service (700+ lines)
- `frontend/src/pages/CustomEvaluation.tsx` — UI page
- `otfs_ai_pipeline/phase11_validation.py` — 40-test validation
- 5 documentation files (this + 4 others)

### Files Preserved (No Changes)
- `final_dataset.csv` — Frozen, checksum unchanged
- `metric_models_v2/` — All 7 files unchanged
- `adaptive_config_v2.json` — Phase-3 config unchanged
- `ai_engine_v2.py` — Phase-3 engine unchanged
- All Phase-8/9/10 files unchanged
