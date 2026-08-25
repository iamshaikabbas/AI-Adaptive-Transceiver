"""phase2_dataset_check.py -- Phase 2 / STEPS 4-5 gate.

Integrity checks on phase2_dataset.csv / phase2_performance_map.csv before
any training happens. Fails loudly (exit 1) if anything is off.
"""

import os
import sys
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "Results", "WaveformComparison")

ds = pd.read_csv(os.path.join(OUT, "phase2_dataset.csv"))
mp = pd.read_csv(os.path.join(OUT, "phase2_performance_map.csv"))
fails = []

def chk(name, cond):
    print(f"[{'PASS' if cond else 'FAIL'}] {name}")
    if not cond:
        fails.append(name)

chk("dataset rows == 1158", len(ds) == 1158)
chk("map rows == 579", len(mp) == 579)
chk("no NaN in BER", ds.BER.notna().all())
chk("no NaN in ACS", ds.ACS.notna().all())
chk("waveforms exact", set(ds.waveform) == {"OTFS", "ODDM"})
per_sid = ds.groupby("scenario_id").size()
chk("2 rows per condition", (per_sid == 2).all())
sp = ds.groupby("split")["scenario_id"].nunique().to_dict()
chk("split counts 278/55/246",
    sp.get("train") == 278 and sp.get("val") == 55 and sp.get("test") == 246)

# leak-free-by-design: for the MAIN grid (mod in {4,16}, default carrier),
# train and test must not share any (SNR, speed) lattice point
main = mp[(mp.modulation.isin([4, 16])) &
          (mp.carrier_frequency_hz == mp.carrier_frequency_hz.mode()[0])]
tr = set(zip(main[main.split == "train"].snr_db,
             main[main.split == "train"].speed_kmph))
te = set(zip(main[main.split == "test"].snr_db,
             main[main.split == "test"].speed_kmph))
chk("main-grid train/test lattice disjoint", len(tr & te) == 0)
print(f"      train pts={len(tr)}  test pts={len(te)}  overlap={len(tr & te)}")

# label honesty
lab = mp.best_waveform.value_counts(dropna=False)
print("\nbest_waveform distribution:\n" + lab.to_string())
chk("labels never empty", mp.best_waveform.notna().all())

# cross-check vs exploratory finding: 16-QAM should favour OTFS strongly
q = mp[mp.modulation == 64] if (mp.modulation == 64).any() else None
m16 = mp[mp.modulation == 16]
otfs_16 = (m16.best_by_BER == "OTFS").mean()
print(f"\n16-QAM best_by_BER -> OTFS share: {otfs_16:.1%} "
      f"(exploratory predicted strong OTFS dominance)")

# modulation=4 fast+EVA region should favour ODDM
eva_fast_q = m16 if False else mp[(mp.modulation == 4) &
                                  (mp.channel_profile == "EVA") &
                                  (mp.speed_kmph >= 100) & (mp.snr_db >= 10)]
oddm_share = (eva_fast_q.best_by_BER == "ODDM").mean() if len(eva_fast_q) else float('nan')
print(f"EVA fast high-SNR QPSK -> ODDM share: {oddm_share:.1%} "
      f"({len(eva_fast_q)} conds; exploratory predicted ODDM lean)")

print(f"\n{'ALL CHECKS PASSED' if not fails else 'FAILURES: ' + str(fails)}")
sys.exit(0 if not fails else 1)
