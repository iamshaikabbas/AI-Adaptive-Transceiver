"""
config.py
=========
Single source of truth for paths, filenames and column/schema definitions
used across every Phase-2 script (train_model.py, predict.py, dashboard.py,
record_audio.py, environment_classifier.py, parameter_mapper.py).

Keeping this centralised means the MATLAB-side filenames (PYTHON_JSON_OUT,
ENV_PROFILE_FILE, DATASET_FILE, etc. in the .m script) and the Python-side
filenames always agree.
"""

import os

# ---------------------------------------------------------------------------
# Folders (relative to wherever you run the scripts from -- keep this
# pipeline folder next to your MATLAB Results/ folder and environment_profiles.csv)
# ---------------------------------------------------------------------------
RESULTS_DIR    = "Results"          # produced by MATLAB (Module 4)
MODELS_DIR     = "models"           # trained sklearn models (this pipeline)
AI_RESULTS_DIR = "AI_Results"       # predictions / evaluation / dashboards (this pipeline)
GRAPHS_DIR     = os.path.join(AI_RESULTS_DIR, "Graphs")   # all generated PNGs (Sections A-D)
REPORTS_DIR    = os.path.join(AI_RESULTS_DIR, "Reports")  # dataset_report.txt, model_comparison.csv

for _d in (RESULTS_DIR, MODELS_DIR, AI_RESULTS_DIR, GRAPHS_DIR, REPORTS_DIR):
    os.makedirs(_d, exist_ok=True)

# ---------------------------------------------------------------------------
# Files shared with the MATLAB script (names must match the .m constants)
# ---------------------------------------------------------------------------
ENV_PROFILE_FILE   = "environment_profiles.csv"                 # MATLAB: ENV_PROFILE_FILE
DATASET_FILE        = os.path.join(RESULTS_DIR, "OTFS_Dataset.csv")  # MATLAB: DATASET_FILE

AUDIO_FILE                 = "recorded_audio.wav"       # written by record_audio.py
AUDIO_CLASSIFICATION_FILE  = "audio_classification.json"  # written by environment_classifier.py
DETECTED_ENV_FILE          = "detected_environment.json"  # MATLAB: PYTHON_JSON_OUT (required fields below)

# MATLAB requires exactly these fields in detected_environment.json:
#   environment, speed_kmh, delay_profile, doppler_scale

# ---------------------------------------------------------------------------
# Model artifact filenames
# ---------------------------------------------------------------------------
DETECTOR_MODEL_FILE  = os.path.join(MODELS_DIR, "detector_classifier.joblib")
METRIC_MODEL_FILE    = os.path.join(MODELS_DIR, "metric_regressor_{target}.joblib")
AUDIO_MODEL_FILE     = os.path.join(MODELS_DIR, "env_audio_classifier.joblib")
FEATURE_META_FILE    = os.path.join(MODELS_DIR, "feature_metadata.json")

# Dataset analysis / model comparison artifacts (train_model.py)
DATASET_REPORT_FILE     = os.path.join(REPORTS_DIR, "dataset_report.txt")
MODEL_COMPARISON_FILE   = os.path.join(REPORTS_DIR, "model_comparison.csv")

# Candidate regression algorithms compared for every metric target
# (train_model.py trains all three, per target, and keeps the best one)
REGRESSOR_CANDIDATES = ["RandomForest", "GradientBoosting", "DecisionTree"]

# ---------------------------------------------------------------------------
# Dataset schema (must exactly match VarNames in the MATLAB script, Module 4)
# ---------------------------------------------------------------------------
ALL_COLUMNS = [
    'Environment', 'Speed_kmh', 'DelayProfile', 'DelaySpread', 'NumPaths',
    'DopplerSpread', 'Modulation', 'Detector', 'SNR_dB', 'BER', 'SER', 'PER',
    'EVM_percent', 'SINR_est_dB', 'CQI', 'Throughput_bps',
    'SpectralEfficiency_bps_per_Hz', 'Runtime_sec', 'AvgIterations',
    'ScenarioID', 'Category', 'FocusMode', 'Timestamp',
]

# Categorical columns (one-hot encoded for ML)
CATEGORICAL_COLS = ['Environment', 'DelayProfile', 'Modulation', 'Category']

# Numeric scenario-level columns (detector-independent physical features)
NUMERIC_SCENARIO_COLS = ['Speed_kmh', 'DelaySpread', 'NumPaths', 'DopplerSpread', 'SNR_dB']

# Features used to recommend a detector (nothing that depends on which
# detector was used -- this must be predictable BEFORE a detector is chosen)
FEATURE_COLS_DETECTOR = CATEGORICAL_COLS + NUMERIC_SCENARIO_COLS

# Features used to predict communication metrics (includes Detector, since
# BER/Throughput/etc. depend on which detector will be used)
FEATURE_COLS_METRIC = CATEGORICAL_COLS + NUMERIC_SCENARIO_COLS + ['Detector']

# Metrics the regression models predict
METRIC_TARGETS = ['BER', 'SER', 'PER', 'Throughput_bps',
                   'SpectralEfficiency_bps_per_Hz', 'CQI']

# Targets that span orders of magnitude -> trained in log10 space
LOG_SCALE_TARGETS = ['BER', 'SER', 'PER']
LOG_FLOOR = 1e-8  # clip before log10 to avoid log(0)

# Detector labels the classifier can choose from (kept in sync with MATLAB DETECTOR_LIST)
DETECTOR_LIST = ['MRC', 'LMMSE', 'MPA']

# Modulations (kept in sync with MATLAB MOD_LIST / MOD_NAMES)
MOD_NAMES = ['QPSK', '16QAM', '64QAM']

# Default SNR sweep for forward AI prediction (kept in sync with MATLAB SNR_dB)
SNR_SWEEP = list(range(0, 31, 5))

RANDOM_STATE = 42

# ---------------------------------------------------------------------------
# Real-world input modes (MODE 1: manual scenario picker, MODE 2: microphone)
# ---------------------------------------------------------------------------
# MODE 1 -- the coarse, user-facing scenario names shown in the CLI/UI. Each
# maps onto one of the physical Environment rows in environment_profiles.csv
# (several everyday scenarios can share one underlying channel profile).
SCENARIO_MODE_CHOICES = ["Traffic", "Bus", "Train", "Office", "Highway"]
SCENARIO_TO_ENV_PROFILE = {
    "Traffic":  "Urban",
    "Bus":      "Urban",
    "Train":    "Rural",
    "Office":   "Indoor",
    "Highway":  "Highway",
}

# MODE 2 -- environments the microphone pipeline can recognise. Kept broader
# than environment_profiles.csv on purpose (real audio is noisier/ more
# varied than the channel-profile table); anything without its own profile
# row snaps to the closest physical profile via ENV_LABEL_TO_PROFILE below.
AUDIO_ENV_LABELS = ["Office", "Traffic", "Bus", "Train", "Highway",
                    "Construction", "Indoor", "Outdoor"]
ENV_LABEL_TO_PROFILE = {
    "Office": "Indoor", "Indoor": "Indoor",
    "Traffic": "Urban", "Bus": "Urban", "Outdoor": "Urban",
    "Train": "Rural",
    "Highway": "Highway", "Construction": "Highway",  # loud, broadband, low mobility-ish but high noise
}

# Coarse noise-level bucket, purely descriptive (derived from RMS energy)
NOISE_LEVEL_BANDS = [  # (max_rms, label)
    (0.02, "Low"),
    (0.08, "Moderate"),
    (0.20, "High"),
    (1.01, "Very High"),
]

# ---------------------------------------------------------------------------
# Communication quality classification (BER + CQI + Throughput -> label)
# ---------------------------------------------------------------------------
QUALITY_LABELS = ["Excellent", "Good", "Moderate", "Poor"]

# Thresholds are evaluated top-down; first matching row wins.
# throughput_frac = Throughput_bps / (max Throughput_bps seen for that
# Modulation at CQI=15, i.e. near-ideal) -- computed relative so it scales
# with whatever bandwidth/numerology the MATLAB link budget uses.
QUALITY_THRESHOLDS = [
    # label,      max_ber,  min_cqi, min_throughput_frac
    ("Excellent", 1e-4,     11,      0.70),
    ("Good",      1e-3,     7,       0.40),
    ("Moderate",  1e-2,     3,       0.15),
    ("Poor",      1.0,      0,       0.0),
]
