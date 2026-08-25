"""
train_waveform_selector.py
==========================
Phase "AI Waveform Selection" module.

Trains a classifier that recommends the best-performing waveform
(OTFS vs ODDM -- optionally OFDM as a third choice) for a given channel
condition, straight off the combined paired-trial dataset written by
MATLAB's build_waveform_dataset.m:

    ../Results/WaveformComparison/waveform_dataset.csv

Pair groups (CondID, TrialIdx) share an identical channel realization,
payload and noise seed, so the label

    winner = argmin BER   (ties -> lower PER -> lower runtime)

is a valid paired-selection oracle. Because OTFS-MRC wins most pairs in the
current grid (class imbalance), class-weighted variants of every candidate
are trained as well, and models are additionally scored by *regret*:

    regret = mean log10( BER_selected / BER_oracle )

which measures how far the chosen waveform is from the per-pair optimum,
independent of class frequency.

Evaluation is GROUP-AWARE: the train/test split partitions whole CondIDs.

Outputs:
    models/waveform_selector.joblib          best pipeline
    models/waveform_selector_meta.json       features/classes/rule info
    AI_Results/Reports/waveform_model_comparison.csv
    AI_Results/Reports/waveform_selector_report.txt
    AI_Results/Graphs/waveform_confusion_matrix.png
    AI_Results/Graphs/waveform_feature_importance.png
    AI_Results/Graphs/waveform_accuracy_vs_snr.png

Usage:
    python train_waveform_selector.py [--classes 2|3]
"""

import argparse
import json
import os

import joblib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.metrics import (accuracy_score, classification_report,
                             confusion_matrix, f1_score)
from sklearn.model_selection import GroupShuffleSplit
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.tree import DecisionTreeClassifier

HERE = os.path.dirname(os.path.abspath(__file__))
DATASET_FILE = os.path.join(HERE, "..", "Results", "WaveformComparison",
                            "waveform_dataset.csv")
MODELS_DIR = os.path.join(HERE, "models")
REPORTS_DIR = os.path.join(HERE, "AI_Results", "Reports")
GRAPHS_DIR = os.path.join(HERE, "AI_Results", "Graphs")
for _d in (MODELS_DIR, REPORTS_DIR, GRAPHS_DIR):
    os.makedirs(_d, exist_ok=True)

RANDOM_STATE = 42

FEATURE_COLS = ["Environment", "Speed_kmh", "DelayProfile", "DelaySpread",
                "NumPaths", "DopplerSpread", "Modulation", "SNR_dB"]
CATEGORICAL = ["Environment", "DelayProfile"]
NUMERIC = [c for c in FEATURE_COLS if c not in CATEGORICAL]


def build_group_table(df: pd.DataFrame, classes):
    """Collapse the long dataset into one row per pair group.

    Returns a table with columns [CondID, TrialIdx] + FEATURE_COLS +
    'label' + 'BER__<waveform>' for every class.
    """
    cand = df[df["Waveform"].isin(classes)]
    wide = cand.pivot_table(index=["CondID", "TrialIdx"], columns="Waveform",
                            values="BER", aggfunc="first")
    first = cand.sort_values(["CondID", "TrialIdx"]).groupby(
        ["CondID", "TrialIdx"], sort=False).first()
    feats = first[FEATURE_COLS]

    win = {}
    for key, sub in cand.groupby(["CondID", "TrialIdx"], sort=False):
        s = sub.sort_values(["BER", "PER", "Runtime_sec", "Waveform"])
        win[key] = s.iloc[0]["Waveform"]
    labels = pd.Series([win[k] for k in wide.index], index=wide.index,
                       name="label")

    idx = wide.index.to_frame(index=False)          # CondID, TrialIdx
    tab = pd.concat([idx, feats.reset_index(drop=True),
                     labels.reset_index(drop=True)], axis=1)
    for w in classes:
        tab[f"BER__{w}"] = (wide[w].to_numpy()
                            if w in wide.columns else np.nan)
    return tab


def regret(B, pred, classes):
    """Mean log10(selected BER / oracle BER); 0 == always optimal."""
    sel = np.array([B.loc[i, f"BER__{c}"] for i, c in enumerate(pred)])
    oracle = B.min(axis=1).to_numpy()
    ratio = np.clip(sel / np.maximum(oracle, 1e-12), 1.0, None)
    return float(np.mean(np.log10(ratio)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--classes", type=int, default=2, choices=[2, 3],
                    help="2 = OTFS vs ODDM, 3 = include OFDM")
    args = ap.parse_args()
    classes = ["ODDM", "OFDM", "OTFS"] if args.classes == 3 else ["ODDM",
                                                                  "OTFS"]

    df = pd.read_csv(DATASET_FILE)
    print(f"Loaded {len(df)} rows from {os.path.basename(DATASET_FILE)}")

    tab = build_group_table(df, classes)
    X = tab[FEATURE_COLS]
    y = tab["label"]
    groups = tab["CondID"].to_numpy()
    print(f"{len(tab)} pair groups; class counts:\n{y.value_counts().to_string()}")

    splitter = GroupShuffleSplit(n_splits=1, test_size=0.25,
                                 random_state=RANDOM_STATE)
    tr_idx, te_idx = next(splitter.split(X, y, groups))
    X_tr, X_te = X.iloc[tr_idx], X.iloc[te_idx]
    y_tr, y_te = y.iloc[tr_idx], y.iloc[te_idx]
    B_te = tab.iloc[te_idx][[f"BER__{c}" for c in classes]].reset_index(
        drop=True)

    pre = ColumnTransformer([
        ("cat", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL),
        ("num", StandardScaler(), NUMERIC),
    ])

    candidates = {
        "RandomForest": RandomForestClassifier(n_estimators=300,
                                               random_state=RANDOM_STATE),
        "RandomForestBal": RandomForestClassifier(
            n_estimators=300, random_state=RANDOM_STATE,
            class_weight="balanced_subsample"),
        "GradientBoosting": GradientBoostingClassifier(
            random_state=RANDOM_STATE),
        "DecisionTreeBal": DecisionTreeClassifier(
            random_state=RANDOM_STATE, class_weight="balanced"),
    }

    rows, fitted = [], {}
    for name, clf in candidates.items():
        pipe = Pipeline([("pre", pre), ("clf", clf)])
        pipe.fit(X_tr[FEATURE_COLS], y_tr)
        pred = pipe.predict(X_te[FEATURE_COLS])
        acc = accuracy_score(y_te, pred)
        f1m = f1_score(y_te, pred, average="macro")
        reg = regret(B_te, pred, classes)
        rows.append({"Model": name, "Accuracy": acc, "MacroF1": f1m,
                     "Regret_log10": reg})
        fitted[name] = (pipe, pred)
        print(f"{name:18s} acc={acc:.4f} macroF1={f1m:.4f} "
              f"regret={reg:.3f} dec")

    comp = pd.DataFrame(rows).sort_values("MacroF1", ascending=False)
    comp.to_csv(os.path.join(REPORTS_DIR, f"waveform_model_comparison_{len(classes)}c.csv"),
                index=False)

    best_name = comp.iloc[0]["Model"]
    best_pipe, best_pred = fitted[best_name]
    base_acc = float((y_te == "OTFS").mean())
    base_reg = regret(B_te, np.array(["OTFS"] * len(y_te)), classes)

    joblib.dump(best_pipe, os.path.join(MODELS_DIR, f"waveform_selector_{len(classes)}c.joblib"))
    meta = {
        "model_file": f"waveform_selector_{len(classes)}c.joblib",
        "best_model": best_name,
        "classes": list(best_pipe.classes_),
        "features": FEATURE_COLS,
        "categorical": CATEGORICAL,
        "numeric": NUMERIC,
        "label_rule": "argmin BER within (CondID,TrialIdx); ties -> PER -> runtime",
        "selection_metric": "lowest test MacroF1 (regret reported alongside)",
        "test_accuracy": float(comp.iloc[0]["Accuracy"]),
        "baseline_always_otfs_accuracy": base_acc,
        "best_regret_log10": float(comp.iloc[0]["Regret_log10"]),
        "baseline_regret_log10": base_reg,
        "random_state": RANDOM_STATE,
    }
    with open(os.path.join(MODELS_DIR, f"waveform_selector_meta_{len(classes)}c.json"),
              "w") as fh:
        json.dump(meta, fh, indent=2)

    cm = confusion_matrix(y_te, best_pred, labels=best_pipe.classes_)
    lines = [
        "WAVEFORM SELECTOR TRAINING REPORT",
        "=" * 60,
        f"dataset            : {os.path.basename(DATASET_FILE)}",
        f"pair groups        : {len(X)} (train {len(tr_idx)} / test {len(te_idx)})",
        f"classes            : {list(best_pipe.classes_)}",
        f"group split        : by CondID (unseen test conditions)",
        "",
        comp.to_string(index=False),
        "",
        f"best model          : {best_name}",
        f"test accuracy       : {comp.iloc[0]['Accuracy']:.4f} "
        f"(always-OTFS baseline {base_acc:.4f})",
        f"regret [log10]      : {comp.iloc[0]['Regret_log10']:.4f} "
        f"(baseline {base_reg:.4f})",
        "",
        classification_report(y_te, best_pred),
    ]
    with open(os.path.join(REPORTS_DIR, f"waveform_selector_report_{len(classes)}c.txt"),
              "w") as fh:
        fh.write("\n".join(lines))
    print("\n".join(lines))

    fig, ax = plt.subplots(figsize=(5.2, 4.4))
    im = ax.imshow(cm, cmap="Blues")
    ax.set_xticks(range(len(best_pipe.classes_)))
    ax.set_yticks(range(len(best_pipe.classes_)))
    ax.set_xticklabels(best_pipe.classes_)
    ax.set_yticklabels(best_pipe.classes_)
    for i in range(cm.shape[0]):
        for j in range(cm.shape[1]):
            ax.text(j, i, str(cm[i, j]), ha="center", va="center",
                    color="white" if cm[i, j] > cm.max() / 2 else "black")
    ax.set_xlabel("Predicted"); ax.set_ylabel("True")
    ax.set_title(f"Waveform selection confusion ({best_name})")
    fig.colorbar(im, fraction=0.046)
    fig.tight_layout()
    fig.savefig(os.path.join(GRAPHS_DIR, f"waveform_confusion_matrix_{len(classes)}c.png"),
                dpi=150)
    plt.close(fig)

    ohe = best_pipe.named_steps["pre"].named_transformers_["cat"]
    cat_names = list(ohe.get_feature_names_out(CATEGORICAL))
    importances = best_pipe.named_steps["clf"].feature_importances_
    names = cat_names + NUMERIC
    order = np.argsort(importances)[::-1]
    fig, ax = plt.subplots(figsize=(7, 4.4))
    ax.barh([names[i] for i in order][::-1], importances[order][::-1],
            color="steelblue")
    ax.set_xlabel("Feature importance")
    ax.set_title(f"Waveform selector feature importance ({best_name})")
    fig.tight_layout()
    fig.savefig(os.path.join(GRAPHS_DIR, f"waveform_feature_importance_{len(classes)}c.png"),
                dpi=150)
    plt.close(fig)

    ev = X_te.copy()
    ev["pred"] = best_pred
    ev["true"] = y_te.to_numpy()
    ev["ok"] = (ev["pred"] == ev["true"]).astype(float)
    by_snr = ev.groupby("SNR_dB")["ok"].agg(["mean", "size"])
    fig, ax = plt.subplots(figsize=(6.4, 4.2))
    ax.plot(by_snr.index, by_snr["mean"], "o-", color="darkred")
    ax.axhline(base_acc, ls="--", color="gray",
               label=f"always-OTFS ({base_acc:.2f})")
    ax.set_xlabel("SNR [dB]"); ax.set_ylabel("Selection accuracy")
    ax.set_ylim(0, 1.05); ax.grid(True); ax.legend()
    ax.set_title("Selector accuracy vs SNR (held-out conditions)")
    fig.tight_layout()
    fig.savefig(os.path.join(GRAPHS_DIR, f"waveform_accuracy_vs_snr_{len(classes)}c.png"),
                dpi=150)
    plt.close(fig)

    print(f"\nSaved model + meta under {MODELS_DIR}, report under "
          f"{REPORTS_DIR}, graphs under {GRAPHS_DIR}")


if __name__ == "__main__":
    main()
