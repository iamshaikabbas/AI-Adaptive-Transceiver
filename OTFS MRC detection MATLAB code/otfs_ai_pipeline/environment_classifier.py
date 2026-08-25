"""
environment_classifier.py
==========================
Reads config.AUDIO_FILE (written by record_audio.py), extracts a small set
of hand-built spectral/energy features (no librosa dependency -- just numpy
+ scipy, so this runs anywhere), and classifies the clip into one of the
Environment labels used in environment_profiles.csv.

Two modes:

  1. Classify (default, what MATLAB calls):
        python environment_classifier.py
     Reads AUDIO_FILE, writes AUDIO_CLASSIFICATION_FILE with the predicted
     label + confidence. parameter_mapper.py reads that file next.

  2. Train (build the classifier from your own labelled recordings):
        python environment_classifier.py --train --data_dir audio_dataset/
     Expects audio_dataset/<EnvironmentLabel>/*.wav (label = folder name,
     must match an Environment value in environment_profiles.csv), trains a
     RandomForestClassifier on the extracted features, saves it to
     config.AUDIO_MODEL_FILE.

Until you have labelled recordings and run --train, this falls back to a
simple heuristic (RMS energy + spectral centroid thresholds) so the pipeline
is runnable end-to-end from day one -- swap in the trained model whenever
it's ready, no other script needs to change.
"""

import argparse
import glob
import json
import os
import sys

import numpy as np

from config import (AUDIO_FILE, AUDIO_CLASSIFICATION_FILE, AUDIO_MODEL_FILE,
                     RANDOM_STATE, AUDIO_ENV_LABELS, ENV_LABEL_TO_PROFILE,
                     NOISE_LEVEL_BANDS)


def _load_wav(path):
    from scipy.io import wavfile
    sr, data = wavfile.read(path)
    if data.ndim > 1:
        data = data.mean(axis=1)
    data = data.astype(np.float64)
    peak = np.max(np.abs(data)) or 1.0
    return sr, data / peak


def extract_features(wav_path: str) -> np.ndarray:
    """Hand-built features: RMS energy, zero-crossing rate, spectral
    centroid, spectral bandwidth, spectral rolloff (85%), spectral flatness.
    Cheap, dependency-light, and enough to separate broad noise environments
    (quiet indoor vs steady urban hum vs loud broadband highway noise, etc.)."""
    sr, x = _load_wav(wav_path)
    if len(x) == 0:
        raise ValueError(f"Empty audio file: {wav_path}")

    rms = float(np.sqrt(np.mean(x ** 2)))
    zcr = float(np.mean(np.abs(np.diff(np.sign(x))) > 0))

    spec = np.abs(np.fft.rfft(x))
    freqs = np.fft.rfftfreq(len(x), d=1.0 / sr)
    spec_sum = np.sum(spec) + 1e-12

    centroid = float(np.sum(freqs * spec) / spec_sum)
    bandwidth = float(np.sqrt(np.sum(((freqs - centroid) ** 2) * spec) / spec_sum))

    cumulative = np.cumsum(spec)
    rolloff_idx = np.searchsorted(cumulative, 0.85 * cumulative[-1])
    rolloff = float(freqs[min(rolloff_idx, len(freqs) - 1)])

    geo_mean = np.exp(np.mean(np.log(spec + 1e-12)))
    arith_mean = np.mean(spec) + 1e-12
    flatness = float(geo_mean / arith_mean)

    return np.array([rms, zcr, centroid, bandwidth, rolloff, flatness])


FEATURE_NAMES = ["rms", "zcr", "centroid_hz", "bandwidth_hz", "rolloff_hz", "flatness"]

# Mobility bucket implied by each real-world label (matches the Doppler/
# speed regime of the physical profile it snaps to via ENV_LABEL_TO_PROFILE)
MOBILITY_BY_LABEL = {
    "Office": "Stationary", "Indoor": "Stationary", "Construction": "Stationary",
    "Traffic": "Low", "Bus": "Medium", "Outdoor": "Low",
    "Train": "High", "Highway": "Very High",
}


def estimate_noise_level(rms: float) -> str:
    """Coarse, descriptive noise-level bucket from RMS energy (see
    config.NOISE_LEVEL_BANDS)."""
    for max_rms, label in NOISE_LEVEL_BANDS:
        if rms <= max_rms:
            return label
    return NOISE_LEVEL_BANDS[-1][1]


def estimate_mobility(label: str) -> str:
    return MOBILITY_BY_LABEL.get(label, "Unknown")


def _heuristic_classify(feat: np.ndarray, known_envs=None):
    """Fallback used until a trained model exists. Coarse buckets by energy,
    zero-crossing rate and spectral centroid across the 8 real-world labels
    in config.AUDIO_ENV_LABELS (Office/Traffic/Bus/Train/Highway/
    Construction/Indoor/Outdoor). Swap in environment_classifier.py --train
    on real recordings whenever labelled audio is available; nothing else
    in the pipeline needs to change."""
    rms, zcr, centroid, bandwidth, rolloff, flatness = feat

    if rms < 0.015:
        bucket = "Indoor"                                  # near-silent room tone
    elif rms < 0.03 and centroid < 1500:
        bucket = "Office"                                   # quiet, low-frequency HVAC/keyboard hum
    elif rms >= 0.25 and zcr > 0.20:
        bucket = "Construction"                             # loud, broadband, impulsive (drills/hammering)
    elif rms >= 0.15 and centroid >= 2500:
        bucket = "Highway"                                  # loud, high-frequency wind/engine noise
    elif 0.06 <= rms < 0.15 and centroid < 1800:
        bucket = "Bus"                                       # steady mid-level engine drone
    elif rolloff > 3000 and zcr > 0.12:
        bucket = "Train"                                     # rhythmic, higher spectral rolloff (rail/wheel noise)
    elif 0.03 <= rms < 0.10 and centroid < 2200:
        bucket = "Traffic"                                   # moderate, mixed engine + horn transients
    else:
        bucket = "Outdoor"                                   # generic open-air fallback

    confidence = 0.55  # heuristic, deliberately modest -- train a real model for higher confidence

    candidates = known_envs if known_envs else AUDIO_ENV_LABELS
    if bucket in candidates:
        return bucket, confidence
    # snap to the closest matching known label (case-insensitive substring)
    for env in candidates:
        if bucket.lower() in env.lower() or env.lower() in bucket.lower():
            return env, confidence
    return candidates[0], confidence * 0.7  # no good match -> low-confidence default


def classify(wav_path: str, env_profile_labels=None):
    feat = extract_features(wav_path)
    rms = float(feat[0])

    if os.path.exists(AUDIO_MODEL_FILE):
        import joblib
        clf = joblib.load(AUDIO_MODEL_FILE)
        pred = clf.predict(feat.reshape(1, -1))[0]
        proba = clf.predict_proba(feat.reshape(1, -1))[0]
        confidence = float(np.max(proba))
    else:
        pred, confidence = _heuristic_classify(feat, env_profile_labels)

    extras = {
        "noise_level": estimate_noise_level(rms),
        "estimated_mobility": estimate_mobility(pred),
        "mapped_profile": ENV_LABEL_TO_PROFILE.get(pred, pred),
    }
    return pred, confidence, dict(zip(FEATURE_NAMES, feat.tolist())), extras


def train(data_dir: str):
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import classification_report
    import joblib

    X, y = [], []
    for label_dir in sorted(glob.glob(os.path.join(data_dir, "*"))):
        if not os.path.isdir(label_dir):
            continue
        label = os.path.basename(label_dir)
        wavs = glob.glob(os.path.join(label_dir, "*.wav"))
        if not wavs:
            continue
        for wav in wavs:
            try:
                X.append(extract_features(wav))
                y.append(label)
            except Exception as e:
                print(f"  skipping {wav}: {e}")

    if len(set(y)) < 2:
        print("ERROR: need labelled audio in at least 2 subfolders of --data_dir "
              "(one subfolder per Environment label). Nothing trained.", file=sys.stderr)
        sys.exit(1)

    X, y = np.array(X), np.array(y)
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=RANDOM_STATE, stratify=y)

    clf = RandomForestClassifier(n_estimators=200, random_state=RANDOM_STATE)
    clf.fit(X_train, y_train)

    print("\nAudio environment classifier -- held-out evaluation:")
    print(classification_report(y_test, clf.predict(X_test)))

    joblib.dump(clf, AUDIO_MODEL_FILE)
    print(f"Saved model -> {AUDIO_MODEL_FILE}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Classify recorded audio into an environment label.")
    ap.add_argument("--train", action="store_true", help="Train mode instead of classify mode")
    ap.add_argument("--data_dir", type=str, default="audio_dataset",
                     help="Folder of <EnvironmentLabel>/*.wav for --train")
    ap.add_argument("--input", type=str, default=AUDIO_FILE, help="WAV file to classify")
    ap.add_argument("--env_profiles", type=str, default="environment_profiles.csv",
                     help="(unused by default) restrict labels to this profile file's "
                          "Environment column instead of the full AUDIO_ENV_LABELS set")
    ap.add_argument("--restrict_to_profiles", action="store_true",
                     help="Snap onto environment_profiles.csv labels only, instead of "
                          "the broader 8-label real-world set (Office/Traffic/Bus/Train/"
                          "Highway/Construction/Indoor/Outdoor)")
    args = ap.parse_args()

    if args.train:
        train(args.data_dir)
        sys.exit(0)

    known_envs = AUDIO_ENV_LABELS
    if args.restrict_to_profiles and os.path.exists(args.env_profiles):
        import pandas as pd
        known_envs = pd.read_csv(args.env_profiles)["Environment"].unique().tolist()

    if not os.path.exists(args.input):
        print(f"ERROR: audio file not found: {args.input}. Run record_audio.py first.",
              file=sys.stderr)
        sys.exit(1)

    label, confidence, feats, extras = classify(args.input, known_envs)
    result = {
        "environment": label,
        "confidence": confidence,
        "estimated_mobility": extras["estimated_mobility"],
        "noise_level": extras["noise_level"],
        "mapped_profile": extras["mapped_profile"],
        "features": feats,
    }

    with open(AUDIO_CLASSIFICATION_FILE, "w") as f:
        json.dump(result, f, indent=2)

    print(f"Classified environment: {label} (confidence={confidence:.2f})  "
          f"mobility={extras['estimated_mobility']}  noise={extras['noise_level']}")
    print(f"Saved -> {AUDIO_CLASSIFICATION_FILE}")
