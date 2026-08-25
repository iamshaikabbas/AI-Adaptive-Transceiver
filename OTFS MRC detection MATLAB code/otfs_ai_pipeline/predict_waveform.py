"""
predict_waveform.py
===================
CLI used by the MATLAB real-time adaptive loop (realtime_adaptive.m).

Reads a scenario-feature JSON file, runs the trained waveform selector
(models/waveform_selector_<n>c.joblib) and writes the decision to an
output JSON:

    {"waveform": "OTFS"|"ODDM"[|"OFDM"],
     "detector": "MRC"|"LMMSE"|"MMSETAP",
     "probabilities": {...},
     "model": "<name>"}

Usage:
    python predict_waveform.py --in scenario.json --out decision.json
                               [--classes 2|3]
"""

import argparse
import json
import os

import joblib
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))

DEFAULT_DETECTOR = {
    "OTFS": "MRC",
    "ODDM": "LMMSE",
    "OFDM": "LMMSE",
}

FEATURE_COLS = ["Environment", "Speed_kmh", "DelayProfile", "DelaySpread",
                "NumPaths", "DopplerSpread", "Modulation", "SNR_dB"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--infile", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--classes", type=int, default=2, choices=[2, 3])
    args = ap.parse_args()

    model_file = os.path.join(HERE, "models",
                              f"waveform_selector_{args.classes}c.joblib")
    pipe = joblib.load(model_file)

    with open(args.infile) as fh:
        scen = json.load(fh)

    row = {c: scen.get(c, 0) for c in FEATURE_COLS}
    if isinstance(row["NumPaths"], str) or row["NumPaths"] in (None, ""):
        row["NumPaths"] = 0
    X = pd.DataFrame([row], columns=FEATURE_COLS)

    proba = pipe.predict_proba(X)[0]
    choice = pipe.classes_[int(proba.argmax())]

    out = {
        "waveform": str(choice),
        "detector": DEFAULT_DETECTOR[str(choice)],
        "probabilities": {str(c): float(p)
                          for c, p in zip(pipe.classes_, proba)},
        "features": {c: row[c] for c in FEATURE_COLS},
        "model": os.path.basename(model_file),
    }
    with open(args.out, "w") as fh:
        json.dump(out, fh, indent=2)
    print(f"{out['waveform']} ({out['detector']}) "
          f"p={max(out['probabilities'].values()):.2f}")


if __name__ == "__main__":
    main()
