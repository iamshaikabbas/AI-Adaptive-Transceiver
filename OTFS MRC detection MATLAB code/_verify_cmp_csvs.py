import os
import numpy as np
import pandas as pd

R = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                 "Results", "WaveformComparison")

snr = pd.read_csv(os.path.join(R, "cmp_snr.csv"))
o = snr[snr.label == "OTFS (MRC)"]
lat = np.round(o.BER_total.values * 1920 * 30)
assert np.allclose(lat, o.BER_total.values * 1920 * 30), "lattice violation"
print("lattice check (exact error-count grid): PASS")

wd = pd.read_csv(os.path.join(R, "waveform_dataset.csv"))
cell = wd[(wd.DelayProfile == "EVA") & (wd.Speed_kmh == 120)
          & (wd.Modulation == 4) & (wd.SNR_dB == 15)
          & (wd.Waveform == "OTFS") & (wd.Detector == "MRC")]
ref = cell.BER.mean()
ours = float(o[o.SNR_dB == 15].BER_total.iloc[0])
ratio = ours / ref if ref else float("nan")
print(f"cross-check OTFS-MRC EVA120 QPSK 15dB: dataset={ref:.6f} "
      f"cmp_snr={ours:.6f} ratio={ratio:.2f}")

rt = pd.read_csv(os.path.join(R, "cmp_runtime.csv"))
print("cmp_runtime Run_mean by NM:",
      dict(zip(rt.NM.astype(int), np.round(rt.Run_mean, 3))))

mp = pd.read_csv(os.path.join(R, "cmp_multipath.csv"))
print("multipath BER_total within [0,0.5]:",
      bool(mp.BER_total.between(0, 0.5).all()))

det = pd.read_csv(os.path.join(R, "cmp_detector.csv"))
print("detector labels:", sorted(det.label.unique()))

ch = pd.read_csv(os.path.join(R, "cmp_channel.csv"))
print("channel ProfileIdx xval counts:",
      ch.groupby("ProfileIdx").size().to_dict())
