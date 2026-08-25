# OTFS Phase 2 — Python AI Pipeline (Communication Intelligence Engine)

Consumes `Results/OTFS_Dataset.csv` (produced by your MATLAB script) and implements
everything downstream of it:

```
Dataset Analysis & Report   -> dataset_report.py     (called by train_model.py)
Machine Learning Training   -> train_model.py         (RF / GB / DT compared per metric)
Environment Detection       -> record_audio.py + environment_classifier.py + parameter_mapper.py
  MODE 1 (manual scenario)  -> parameter_mapper.py --scenario Traffic|Bus|Train|Office|Highway
  MODE 2 (microphone)       -> record_audio.py -> environment_classifier.py -> parameter_mapper.py
AI Communication Prediction -> predict.py  (forward mode)
Detector Recommendation     -> predict.py  (forward mode, same call)
Communication Quality       -> communication_quality.py (Excellent/Good/Moderate/Poor)
MATLAB OTFS Validation      -> you re-run MATLAB on AI_Results/ai_recommended_scenarios.json
Prediction Evaluation       -> predict.py  (validation mode)
Dashboard                   -> dashboard.py
Graphs (Sections B/C/D)     -> graphs.py    (called by train_model.py / predict.py / dashboard.py)
```

Section A graphs (raw MATLAB communication-performance plots: BER vs SNR, BER vs
Speed, Throughput vs SNR, etc.) already exist on the MATLAB side and are not
regenerated here.

## Setup

```bash
pip install pandas scikit-learn joblib matplotlib numpy scipy
# only needed on the machine that actually records mic audio:
pip install sounddevice soundfile
```

Put this folder **next to** your MATLAB script's `Results/` folder and
`environment_profiles.csv` (a placeholder `environment_profiles.csv` is
included here — replace it with your real one, columns must match:
`Environment,SpeedMin,SpeedMax,DelayProfile,DopplerScale,Category`).

## 1. Train the models

```bash
python train_model.py --input Results/OTFS_Dataset.csv
```

For each target in `config.METRIC_TARGETS` (BER, SER, PER, Throughput_bps,
SpectralEfficiency_bps_per_Hz, CQI), trains **RandomForest, GradientBoosting
and DecisionTree**, compares them on MAE / RMSE / R² / Explained Variance /
MAPE, and keeps the best one. Also trains `detector_classifier.joblib`
(RandomForestClassifier recommending MRC / LMMSE / MPA from scenario
features alone). BER/SER/PER are trained in log10 space since they span
many decades.

Outputs:
- `models/metric_regressor_<Target>.joblib`, `models/detector_classifier.joblib`
- `AI_Results/Reports/dataset_report.txt` — row/column counts, missing/duplicate
  values, unique Environments/Modulations/Detectors/DelayProfiles
- `AI_Results/Reports/model_comparison.csv` — every candidate model's scores,
  per target, with the winner flagged
- `AI_Results/Graphs/` — dataset distribution graphs (correlation matrix, BER/SNR
  distributions, Environment/Detector/DelayProfile distributions), per-target
  feature importance, and the Section C advanced graphs (environment radar
  chart, BER/Throughput surface plots, detector decision heatmap)

Prints held-out R²/MAE per metric and accuracy/F1 for the detector
classifier so you can see if you need more MATLAB scenarios before trusting
the models (more `N_SCENARIOS_PER_ENV` / `N_FRAM_PER_SCENARIO` in the .m
script = better ground truth = better models here).

## 2. Environment detection

**MODE 1 — manual scenario picker** (no microphone needed):

```bash
python parameter_mapper.py --scenario Traffic   # or Bus / Train / Office / Highway
```

**MODE 2 — microphone**, mirrors MATLAB's `USE_PYTHON_DETECTION`:

```bash
python record_audio.py                # -> recorded_audio.wav
python environment_classifier.py      # -> audio_classification.json
python parameter_mapper.py            # -> detected_environment.json
```

`environment_classifier.py` extracts RMS/ZCR/spectral-centroid/bandwidth/
rolloff/flatness features (no librosa dependency) and classifies into one of
8 real-world labels (Office, Traffic, Bus, Train, Highway, Construction,
Indoor, Outdoor), each snapped onto a physical channel profile (Indoor /
Urban / Rural / Highway) via `config.ENV_LABEL_TO_PROFILE`. Alongside the
label it estimates a confidence score, a coarse **noise level** (Low /
Moderate / High / Very High, from RMS energy) and an **estimated mobility**
bucket. Falls back to a heuristic classifier until you train a real one on
your own recordings:

```bash
# audio_dataset/Office/*.wav, audio_dataset/Traffic/*.wav, ... (folder = label)
python environment_classifier.py --train --data_dir audio_dataset/
```

Either mode writes `detected_environment.json` with the exact 4 keys
MATLAB's Module 1 requires (`environment`, `speed_kmh`, `delay_profile`,
`doppler_scale`) plus extra optional metadata (`confidence`,
`estimated_mobility`, `noise_level`, `physical_profile`) that MATLAB ignores
but `predict.py`/`dashboard.py` can use.

## 3. AI prediction + detector recommendation + communication quality

```bash
# uses detected_environment.json if present, or pass explicitly:
python predict.py --environment Urban --speed 30 --delay_profile EVA --doppler_scale 1
```

Sweeps QPSK/16QAM/64QAM × SNR 0:5:30, recommends a detector per combo,
predicts its BER/SER/PER/Throughput/SE/CQI, and classifies each combo's
**Communication Quality** (Excellent/Good/Moderate/Poor — see
`communication_quality.py`, tunable via `config.QUALITY_THRESHOLDS`). Writes:
- `AI_Results/AI_Predictions_<timestamp>.csv`
- `AI_Results/ai_recommended_scenarios.json` — feed this into a focused
  MATLAB re-run (this is the "MATLAB OTFS Validation" step) to get real
  simulated ground truth for exactly the scenarios the AI picked
- `AI_Results/Graphs/25_communication_decision_dashboard.png` — Environment /
  Detector / Quality / Confidence breakdown for this run

## 4. Validate against fresh MATLAB ground truth

Once MATLAB has simulated the recommended scenarios and appended to
`OTFS_Dataset.csv` (or produced a standalone results CSV with the same
schema):

```bash
python predict.py --input Results/OTFS_Dataset.csv
```

This is what MATLAB's Module 6 calls automatically
(`system('python predict.py --input ...')`). Writes:
- `AI_Results/predictions_vs_actual.csv`, `AI_Results/detector_recommendation_eval.csv`
- `AI_Results/evaluation_summary.json` — MAE/RMSE/relative-error per metric
  + detector recommendation accuracy
- `AI_Results/Graphs/13..17` and `25` — predicted-vs-actual BER/Throughput,
  prediction error vs Environment, detector recommendation accuracy,
  communication decision dashboard

## 5. Dashboard

```bash
python dashboard.py
```

Renders `AI_Results/AI_Dashboard_latest.png`: predicted-vs-actual scatter
per metric (log scale for BER/SER/PER), communication-quality distribution,
and a detector-recommendation confusion matrix. Also writes
`AI_Results/Reports/dashboard_summary.csv` — one row per prediction with
Environment, Predicted/Actual BER, Prediction Error %, CQI, Detector,
Confidence, Runtime, Throughput, Spectral Efficiency and Communication
Quality. MATLAB's Module 6 calls this non-blocking after `predict.py`.

## Testing without a real MATLAB dataset yet

```bash
python generate_synthetic_dataset.py   # writes a fake Results/OTFS_Dataset.csv
python train_model.py
python parameter_mapper.py --scenario Traffic
python predict.py
python predict.py --input Results/OTFS_Dataset.csv   # sanity-check validation mode
python dashboard.py
```

Delete `generate_synthetic_dataset.py`'s output once your real MATLAB
`OTFS_Dataset.csv` exists — everything else works unchanged against it.

## Notes / things to revisit as your real dataset comes in

- The detector classifier's accuracy depends heavily on how *separable*
  the detectors are in your data — if MRC/LMMSE/MPA perform similarly at
  a given SNR/scenario, expect middling classification accuracy even
  though the underlying metric regressors are accurate. That's expected,
  not a bug.
- `compute_best_detector_table()` in `train_model.py` currently defines
  "best" as lowest BER (tie-break PER, then Runtime). If you'd rather
  optimize for e.g. lowest runtime at acceptable BER, or a weighted
  BER/throughput/runtime score, that function is the one place to change it.
- `config.QUALITY_THRESHOLDS` defines "Excellent/Good/Moderate/Poor" purely
  from BER + CQI + relative Throughput. Adjust the thresholds there if your
  real dataset's throughput/CQI ranges differ noticeably from the synthetic
  smoke-test data.
- Graphs 18 (Scenario AI vs Real-world AI vs MATLAB), 23 (Mic Confidence vs
  Prediction Accuracy) and 24 (Real vs Simulated Environment) need data
  accumulated across multiple real prediction/validation runs — the
  functions in `graphs.py` are ready, they just need real session data
  (e.g. logging each mic-mode run's confidence + resulting BER error to
  `AI_Results/Reports/realworld_session_log.csv`) once you're running this
  on real hardware.
- Everything reads column names from `config.py` — if you rename/add
  columns in the MATLAB `VarNames` list, update `config.py` to match and
  every script picks it up automatically.

