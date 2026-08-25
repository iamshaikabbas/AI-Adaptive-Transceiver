"""phase2_region_analysis.py -- Phase 2 / STEP 2.

Reads Results/WaveformComparison/phase2_exploratory.csv (paired OTFS-MRC
vs ODDM-LMMSE aggregates) and derives where each waveform actually wins.
No assumption is made up front; every statement below is computed from
the measurements. Writes AI_Results/Reports/phase2_region_analysis.md.
"""

import os
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
CSV = os.path.join(ROOT, "Results", "WaveformComparison",
                   "phase2_exploratory.csv")
REPORTS = os.path.join(HERE, "AI_Results", "Reports")
os.makedirs(REPORTS, exist_ok=True)

OTFS, ODDM = "OTFS (MRC)", "ODDM (LMMSE)"

df = pd.read_csv(CSV)
w = df.pivot_table(index=["cond_id", "profile", "speed_kmph", "snr_db",
                          "modulation"], columns="label", values="BER_total")
w = w.reset_index()
rel = (w[ODDM] - w[OTFS]) / w[OTFS].clip(lower=1e-9)
w["rel_gap"] = rel
# tie rule: relative BER gap < 10 % counts as no decisive winner
w["winner"] = np.where(rel > 0.10, "OTFS",
                       np.where(rel < -0.10, "ODDM", "tie"))


def vc_table(sub, by):
    t = sub.groupby(by)["winner"].value_counts().unstack(fill_value=0)
    for c in ("OTFS", "ODDM", "tie"):
        if c not in t.columns:
            t[c] = 0
        t[c] = t.get(c, 0)
    return t[["OTFS", "ODDM", "tie"]]


lines = ["# Phase 2 - OTFS/ODDM decision-region analysis (exploratory grid)",
         "",
         f"Conditions analysed: {len(w)} "
         f"(SNR {{{','.join(map(str, sorted(w.snr_db.unique())))}}} dB x "
         f"speed {{{','.join(map(str, sorted(w.speed_kmph.unique())))}}} km/h x "
         "profiles {EPA,EVA,ETU} x {QPSK,16QAM}, paired trials).",
         "",
         "Winner rule: lower mean BER over paired trials; relative gap <10% => tie.",
         "",
         "## Overall", "",
         w["winner"].value_counts(dropna=False).rename_axis("winner")
             .to_frame("conditions").to_string(), ""]

for by, title in [(["profile"], "By channel profile"),
                  (["modulation"], "By modulation"),
                  (["profile", "modulation"], "By profile x modulation")]:
    lines += [f"## {title}", "", vc_table(w, by).to_string(), ""]

t = w[w.modulation == 4].copy()
t["snr_band"] = pd.cut(t.snr_db, [-np.inf, 2.5, 7.5, 12.5, np.inf],
                       labels=["<=0", "5", "10", ">=15"])
lines += ["## By SNR band (QPSK only)", "", vc_table(t, ["snr_band"]).to_string(), ""]

t = w[w.modulation == 4].copy()
t["spd_band"] = pd.cut(t.speed_kmph, [-1, 25, 75, 175, np.inf],
                       labels=["static-low", "mid", "fast", "very-fast"])
lines += ["## By speed band (QPSK only)", "", vc_table(t, ["spd_band"]).to_string(), ""]

lines += ["## Median relative BER gap (positive => OTFS better)", "",
          w.groupby(["profile", "modulation"])["rel_gap"].median().to_string(), ""]

out = "\n".join(lines)
path = os.path.join(REPORTS, "phase2_region_analysis.md")
with open(path, "w") as fh:
    fh.write(out + "\n")
print(out)
print(f"\nsaved -> {path}")
