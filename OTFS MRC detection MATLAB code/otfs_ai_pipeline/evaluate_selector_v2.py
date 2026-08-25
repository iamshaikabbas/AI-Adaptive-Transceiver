"""evaluate_selector_v2.py -- Phase 2 / STEP 7.

Deep-dive evaluation of waveform_selector_v2 on the UNSEEN-AXIS test split:

  * overall + per-class metrics, confusion matrix
  * confidence buckets (does confidence correlate with correctness?)
  * AI-vs-oracle regret against BOTH oracles (BER / ACS), absolute + relative
  * behaviour inside tie regions (no correct answer exists)
  * tie-tolerance sensitivity: how do labels/regret shift if the tie rule is
    loosened (analysis only -- training labels stay strict)

Writes Reports/selector_v2_unseen_eval.md. Read-only w.r.t. datasets/models.
"""

import os
import json
import numpy as np
import pandas as pd
import joblib

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "Results", "WaveformComparison")
MODELS = os.path.join(HERE, "models")
REPORTS = os.path.join(HERE, "AI_Results", "Reports")

FEATURE_COLS = ["environment", "speed_kmph", "snr_db", "doppler_hz",
                "carrier_frequency_hz", "bandwidth_hz", "channel_profile",
                "delay_spread_taps", "num_paths", "doppler_spread_hz",
                "modulation"]

bundle = joblib.load(os.path.join(MODELS, "waveform_selector_v2.joblib"))
model = bundle["model"]
env_vocab = bundle["cat_encodings"]["environment"]
prof_vocab = bundle["cat_encodings"]["channel_profile"]

mp = pd.read_csv(os.path.join(OUT, "phase2_performance_map.csv"))
ds = pd.read_csv(os.path.join(OUT, "phase2_dataset.csv"))
_extra = (ds.groupby("scenario_id")[["bandwidth_hz", "doppler_spread_hz"]]
            .first().reset_index())
mp = mp.merge(_extra, on="scenario_id", how="left")
mrow = ds.set_index(["scenario_id", "waveform"])

te = mp[mp.split == "test"].copy()


def featurize(df):
    X = df[FEATURE_COLS].copy()
    X["environment"] = X.environment.map({v: i for i, v in enumerate(env_vocab)})
    X["channel_profile"] = X.channel_profile.map(
        {v: i for i, v in enumerate(prof_vocab)})
    return X


teX = featurize(te)
te["pred"] = model.predict(teX)
te["conf"] = model.predict_proba(teX).max(axis=1)

L = ["OTFS", "ODDM"]
dec_mask = te.best_waveform.isin(L)
dec = te[dec_mask]
acc = float((dec.pred == dec.best_waveform).mean())

# ---- regret ------------------------------------------------------------------
reg_abs_b, reg_rel_b, reg_a = [], [], []
for _, r in te.iterrows():
    bp = mrow.loc[(r.scenario_id, r.pred)]
    if r.best_waveform in L and r.pred != r.best_by_BER:
        bo = mrow.loc[(r.scenario_id, r.best_by_BER)]
        reg_abs_b.append(bp.BER - bo.BER)
        reg_rel_b.append((bp.BER - bo.BER) / max(bo.BER, 1e-12))
    else:
        reg_abs_b.append(0.0)
        reg_rel_b.append(0.0)
    if r.best_waveform in L and r.pred != r.best_by_ACS:
        ao = mrow.loc[(r.scenario_id, r.best_by_ACS)]
        reg_a.append(max(ao.ACS - bp.ACS, 0.0))
    else:
        reg_a.append(0.0)
te["reg_abs_BER"] = reg_abs_b
te["reg_rel_BER"] = reg_rel_b
te["reg_abs_ACS"] = reg_a

# ---- confidence buckets --------------------------------------------------------
bins = [0.5, 0.75, 0.9, 1.01]
labs = ["0.5-0.75", "0.75-0.9", ">=0.9"]
dec2 = dec.copy()
dec2["cbucket"] = pd.cut(dec.conf, bins, labels=labs, right=False)
conf_tbl = (dec2.groupby("cbucket", observed=True)
              .apply(lambda g: pd.Series({
                  "n": len(g),
                  "accuracy": (g.pred == g.best_waveform).mean()}))
              .reset_index())

# ---- tie-tolerance sensitivity (analysis only) ----------------------------------
def labels_at_tol(tol):
    """best_waveform if ties need only >tol relative BER gap."""
    def f(r):
        g = r.rel_gap_BER
        if g < tol:
            return "tie"
        return "OTFS" if r.best_by_BER == "OTFS" else "ODDM"
    return te.apply(f, axis=1)

sens_rows = []
for tol in (0.05, 0.10, 0.25, 0.50):
    lab = labels_at_tol(tol)
    d2 = te[lab.isin(L)]
    a2 = float((d2.pred == lab[d2.index]).mean()) if len(d2) else float("nan")
    sens_rows.append({"tol": tol,
                      "decisive": int(len(d2)),
                      "ODDM_decisive": int((lab == "ODDM").sum()),
                      "acc_on_decisive": round(a2, 3),
                      "mean_abs_regret": round(float(
                          te.loc[lab.isin(L)].reg_abs_BER.mean()), 6)})
sens = pd.DataFrame(sens_rows)

# ---- markdown -------------------------------------------------------------------
cm = pd.crosstab(dec.best_waveform, dec.pred, dropna=False)
tie_behaviour = te.loc[~dec_mask, "pred"].value_counts().to_dict()

lines = [
    "# Selector v2 - evaluation on UNSEEN-axis test conditions",
    "",
    f"Test conditions: {len(te)} "
    f"(decisive {len(dec)}, ties {len(te) - len(dec)}); "
    f"accuracy on decisive: **{acc:.1%}**.",
    "",
    "## Confusion matrix (rows=oracle, cols=predicted)",
    "",
    cm.to_string(),
    "",
    "## Regret vs oracle",
    "",
    f"- mean |dB| BER regret: {te.reg_abs_BER.mean():.3e}",
    f"- p90 |dB| BER regret: {te.reg_abs_BER.quantile(0.9):.3e}",
    f"- max  |dB| BER regret: {te.reg_abs_BER.max():.3e}",
    f"- mean ACS regret: {te.reg_abs_ACS.mean():.4f}",
    f"- frac conditions with >10% relative BER regret: "
    f"{(te.reg_rel_BER > 0.10).mean():.1%} (relative values blow up at the "
    "BER floor where both waveforms are error-free; absolute deltas above "
    "are the honest operational number)",
    "",
    "## Confidence calibration",
    "",
    conf_tbl.to_string(index=False),
    "",
    "## Behaviour inside tie regions",
    "",
    f"predictions: {tie_behaviour}",
    "",
    "## Tie-tolerance sensitivity (ANALYSIS ONLY - training kept strict 10%)",
    "",
    "NOTE: this table re-labels with a BER-only oracle (best_by_BER plus a",
    "single relative-gap tie rule). Primary training labels use the stricter",
    "dual rule (ACS objective, |dACS| or rel-BER ties), so counts differ.",
    "",
    sens.to_string(index=False),
]

os.makedirs(REPORTS, exist_ok=True)
path = os.path.join(REPORTS, "selector_v2_unseen_eval.md")
with open(path, "w") as fh:
    fh.write("\n".join(lines) + "\n")
print("\n".join(lines))
print(f"\nsaved -> {path}")
