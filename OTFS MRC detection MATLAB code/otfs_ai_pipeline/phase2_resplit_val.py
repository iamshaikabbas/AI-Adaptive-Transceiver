"""phase2_resplit_val.py -- Phase 2 / STEP 5b (one-off, deterministic).

The initial validation holdout (random 20 % of train conditions) happened to
contain ZERO ODDM-decisive conditions (they are rare: 16 of 579), which made
validation blind to minority-class detection. This utility re-assigns ONLY
the 'val' membership within the TRAIN split, stratified by best_waveform
class so val contains every class. The unseen-axis TEST split is NOT touched.

Deterministic (seed 20260823). Updates the split column in
phase2_dataset.csv and phase2_performance_map.csv in place.
"""

import os
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "Results", "WaveformComparison")
SEED = 20260823

mp_path = os.path.join(OUT, "phase2_performance_map.csv")
ds_path = os.path.join(OUT, "phase2_dataset.csv")
mp = pd.read_csv(mp_path)
ds = pd.read_csv(ds_path)

tr = mp.split == "train"
classes = mp.loc[tr, "best_waveform"].fillna("nan")

rng = None
groups = {}
for c in classes.unique():
    groups[c] = sorted(classes[classes == c].index.to_numpy())

# deterministic positional rule: every 5th condition (sorted) of each class
# goes to val -> ~20 % per class, independent of any prior run state
val_ids = []
for c, idx in sorted(groups.items()):
    val_ids.extend(idx[::5])

new_split = mp.split.copy()
new_split.loc[val_ids] = "val"
# any previous val rows not selected revert to train
was_val_but_not_now = (mp.split == "val") & ~mp.index.isin(val_ids)
new_split.loc[was_val_but_not_now] = "train"
mp["split"] = new_split

# dataset CSV follows the map authoritatively (idempotent)
smap = dict(zip(mp.scenario_id, mp.split))
ds["split"] = ds.scenario_id.map(smap)

mp.to_csv(mp_path, index=False)
ds.to_csv(ds_path, index=False)

d = mp[mp.best_waveform.isin(["OTFS", "ODDM"])]
print("re-split done. decisive counts:\n",
      pd.crosstab(d.split, d.best_waveform))
print("total rows per split:\n", mp.split.value_counts())
