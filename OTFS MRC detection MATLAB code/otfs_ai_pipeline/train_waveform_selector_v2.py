"""train_waveform_selector_v2.py -- Phase 2 / STEPS 6+7+8.

Trains waveform_selector_v2 on the expanded phase2 dataset:

  * features : environment/speed/SNR/Doppler/carrier/profile/delays/paths/mod
               (superset of the v1 FEATURE_COLS)
  * labels   : best_waveform from the paired performance map
               ('OTFS' | 'ODDM'); tie rows are EXCLUDED from training and
               reported separately -- never fabricated into a class
  * split    : uses the simulation-time split column (train / val / test);
               test axis values were UNSEEN by construction (lattice disjoint)
  * models   : RandomForest / GradientBoosting / DecisionTree (+ dummy ref)
  * outputs  : waveform_selector_v2.joblib (bundle incl. feature list,
               encoders), training_meta.json, console + markdown report,
               feature importances

Evaluation follows the deployment metric chain: predicted waveform ->
its MEASURED metrics row -> accuracy, confidence, and AI-vs-oracle regret.
"""

import os
import json
import numpy as np
import pandas as pd
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import (RandomForestClassifier,
                              GradientBoostingClassifier)
from sklearn.tree import DecisionTreeClassifier
from sklearn.metrics import confusion_matrix
import joblib

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
OUT = os.path.join(ROOT, "Results", "WaveformComparison")
MODELS = os.path.join(HERE, "models")
REPORTS = os.path.join(HERE, "AI_Results", "Reports")
for d in (MODELS, REPORTS):
    os.makedirs(d, exist_ok=True)

FEATURE_COLS = ["environment", "speed_kmph", "snr_db", "doppler_hz",
                "carrier_frequency_hz", "bandwidth_hz", "channel_profile",
                "delay_spread_taps", "num_paths", "doppler_spread_hz",
                "modulation"]
CAT_COLS = ["environment", "channel_profile"]

mp = pd.read_csv(os.path.join(OUT, "phase2_performance_map.csv"))
ds = pd.read_csv(os.path.join(OUT, "phase2_dataset.csv"))

# two condition features are only stored in the long-format dataset;
# they are constant per scenario -> join once
_extra = (ds.groupby("scenario_id")[["bandwidth_hz", "doppler_spread_hz"]]
            .first().reset_index())
mp = mp.merge(_extra, on="scenario_id", how="left")

dec = mp[mp.best_waveform.isin(["OTFS", "ODDM"])].copy()
tie = mp[~mp.best_waveform.isin(["OTFS", "ODDM"])].copy()

# ---- categorical encoding (fixed vocabularies saved with the model) --------
env_vocab = sorted(mp.environment.unique().tolist())
prof_vocab = sorted(mp.channel_profile.unique().tolist())
X = dec[FEATURE_COLS].copy()
X["environment"] = X.environment.map({v: i for i, v in enumerate(env_vocab)})
X["channel_profile"] = X.channel_profile.map(
    {v: i for i, v in enumerate(prof_vocab)})
y = dec.best_waveform.to_numpy()


def split_mask(col, name):
    return (dec.split == name).to_numpy()


tr_m, va_m, te_m = (split_mask(dec.split, s) for s in ("train", "val", "test"))
labels = ["OTFS", "ODDM"]
print(f"decisive conditions: {len(dec)} "
      f"(train {tr_m.sum()} / val {va_m.sum()} / test {te_m.sum()}); "
      f"ties excluded: {len(tie)}")

MODELS_DEF = {
    "random_forest": lambda: RandomForestClassifier(
        n_estimators=400, min_samples_leaf=1, class_weight="balanced",
        random_state=42, n_jobs=-1),
    "gradient_boosting": lambda: GradientBoostingClassifier(
        n_estimators=300, learning_rate=0.05, max_depth=3, random_state=42),
    "decision_tree": lambda: DecisionTreeClassifier(
        class_weight="balanced", random_state=42),
    "dummy_majority": lambda: DummyClassifier(strategy="most_frequent"),
}

# metrics lookup for regret: (scenario_id, waveform) -> BER / ACS
mrow = ds.set_index(["scenario_id", "waveform"])


def evaluate(model, mask):
    sub = dec[mask]
    Xs = X[mask]
    pred = model.predict(Xs)
    proba = model.predict_proba(Xs).max(axis=1)
    y_true = sub.best_waveform.to_numpy()
    acc = float((pred == y_true).mean())
    # per-class recall + macro F1 (minority class visibility)
    rec, f1s = {}, []
    for c in labels:
        tp = int(((pred == c) & (y_true == c)).sum())
        fn = int(((pred != c) & (y_true == c)).sum())
        fp = int(((pred == c) & (y_true != c)).sum())
        prec = tp / max(tp + fp, 1)
        rcl = tp / max(tp + fn, 1)
        f1 = 0.0 if (prec + rcl) == 0 else 2 * prec * rcl / (prec + rcl)
        rec[c] = round(rcl, 3)
        f1s.append(f1)
    reg_rb, reg_ab, reg_ra, wrong = [], [], [], 0
    for (_, r), p in zip(sub.iterrows(), pred):
        b_pred = mrow.loc[(r.scenario_id, p)]
        o_ber, o_acs = r.best_by_BER, r.best_by_ACS
        if p != o_ber:
            wrong += 1
            b_or = mrow.loc[(r.scenario_id, o_ber)]
            rel = (b_pred.BER - b_or.BER) / max(b_or.BER, 1e-12)
            reg_rb.append(rel)                       # can be huge at BER floor
            reg_ab.append(b_pred.BER - b_or.BER)     # absolute delta
        else:
            reg_rb.append(0.0)
            reg_ab.append(0.0)
        if p != o_acs:
            a_or = mrow.loc[(r.scenario_id, o_acs)]
            reg_ra.append(max(a_or.ACS - b_pred.ACS, 0.0))
        else:
            reg_ra.append(0.0)
    reg_rb, reg_ab, reg_ra = map(np.asarray, (reg_rb, reg_ab, reg_ra))
    return {
        "accuracy": acc,
        "recall_per_class": rec,
        "macro_f1": float(np.mean(f1s)),
        "mean_confidence": float(np.mean(proba)),
        "wrong_conditions": int(wrong),
        "mean_BER_regret_rel": float(reg_rb.mean()),
        "median_BER_regret_rel": float(np.median(reg_rb)),
        "mean_BER_regret_abs": float(reg_ab.mean()),
        "mean_ACS_regret_abs": float(reg_ra.mean()),
        "frac_BER_regret_gt_10pct": float((reg_rb > 0.10).mean()),
    }


results, fitted = {}, {}
for name, ctor in MODELS_DEF.items():
    m = ctor()
    m.fit(X[tr_m], y[tr_m])
    fitted[name] = m
    results[name] = {"val": evaluate(m, va_m), "test": evaluate(m, te_m)}
    rv, rt = results[name]["val"], results[name]["test"]
    print(f"\n== {name}"
          f"\n   val : acc={rv['accuracy']:.3f} macroF1={rv['macro_f1']:.3f} "
          f"recall={rv['recall_per_class']}"
          f"\n   test: acc={rt['accuracy']:.3f} macroF1={rt['macro_f1']:.3f} "
          f"recall={rt['recall_per_class']}"
          f" regretBER(rel)={rt['mean_BER_regret_rel']:.4g}"
          f" regretBER(abs)={rt['mean_BER_regret_abs']:.2e}")

# ---- model choice: highest VAL accuracy, tie-break lower val regret ---------
cand = [n for n in results if n != "dummy_majority"]
best_name = sorted(cand, key=lambda n: (-results[n]["val"]["accuracy"],
                                        results[n]["val"]["mean_BER_regret_rel"]))[0]
print(f"\nselected model: {best_name}")
model = fitted[best_name]

# ---- feature importance -----------------------------------------------------
imp = pd.Series(model.feature_importances_, index=FEATURE_COLS)\
        .sort_values(ascending=False)
imp_out = imp.round(4).to_dict()

# ---- confusion matrix on unseen test ---------------------------------------
sub_te = dec[te_m]
pred_te = model.predict(X[te_m])
cm = confusion_matrix(sub_te.best_waveform, pred_te, labels=labels)

# ---- tie-region behaviour: what does the model do where oracle says tie? ---
tie_X = tie[FEATURE_COLS].copy()
tie_X["environment"] = tie_X.environment.map({v: i for i, v in enumerate(env_vocab)})
tie_X["channel_profile"] = tie_X.channel_profile.map(
    {v: i for i, v in enumerate(prof_vocab)})
tie_pred = pd.Series(model.predict(tie_X)).value_counts().to_dict()

# ---- save bundle -------------------------------------------------------------
bundle = {
    "version": "phase2-v2",
    "model_name": best_name,
    "model": model,
    "feature_cols": FEATURE_COLS,
    "cat_encodings": {"environment": env_vocab,
                      "channel_profile": prof_vocab},
    "classes": list(model.classes_),
    "trained_on": "phase2_performance_map.csv decisive labels only",
}
joblib.dump(bundle, os.path.join(MODELS, "waveform_selector_v2.joblib"))

meta = {
    "model_name": best_name,
    "features": FEATURE_COLS,
    "cat_encodings": bundle["cat_encodings"],
    "train_val_test_decisive": [int(tr_m.sum()), int(va_m.sum()),
                                int(te_m.sum())],
    "ties_excluded_from_training": int(len(tie)),
    "results": results,
    "feature_importance": imp_out,
    "confusion_matrix_test": {"labels": labels, "matrix": cm.tolist()},
    "tie_region_predictions": tie_pred,
}
with open(os.path.join(MODELS, "training_meta.json"), "w") as fh:
    json.dump(meta, fh, indent=2)

# ---- markdown report ---------------------------------------------------------
lines = [
    "# Waveform selector v2 - training report",
    "",
    f"Decisive conditions: {len(dec)} "
    f"(train {int(tr_m.sum())}, val {int(va_m.sum())}, "
    f"unseen test {int(te_m.sum())}); ties excluded: {len(tie)}.",
    f"Selected model: **{best_name}**.",
    "",
    "| model | val acc | val macroF1 | test acc | test macroF1 | "
    "test regretBER(abs) | test frac regret>10% |",
    "|---|---|---|---|---|---|---|",
]
for n, r in results.items():
    lines.append(f"| {n} | {r['val']['accuracy']:.3f} | "
                 f"{r['val']['macro_f1']:.3f} | "
                 f"{r['test']['accuracy']:.3f} | "
                 f"{r['test']['macro_f1']:.3f} | "
                 f"{r['test']['mean_BER_regret_abs']:.2e} | "
                 f"{r['test']['frac_BER_regret_gt_10pct']:.1%} |")
lines += ["", "## Feature importance", ""]
lines += [f"- `{k}`: {v}" for k, v in imp_out.items()]
lines += ["", f"## Confusion matrix on unseen test (rows=oracle, cols=pred)",
          "", "| | " + " | ".join(labels) + " |",
          "|---|" + "---|" * len(labels)]
for i, lab in enumerate(labels):
    lines.append(f"| {lab} | " + " | ".join(str(v) for v in cm[i]) + " |")
lines += ["", "## Behaviour inside tie regions (no correct answer)",
          "", str(tie_pred)]

with open(os.path.join(REPORTS, "selector_v2_training.md"), "w") as fh:
    fh.write("\n".join(lines) + "\n")
print("\nsaved: models/waveform_selector_v2.joblib, training_meta.json, "
      "Reports/selector_v2_training.md")
