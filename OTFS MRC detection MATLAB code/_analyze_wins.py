import pandas as pd

t = pd.read_csv(r"Results\DigitalTwin\strategy_trace.csv")
print("trace strategy values:", t.strategy.astype(str).unique()[:8])
print(t.groupby(t.strategy.astype(str)).size())
print()

d = pd.read_csv(r"Results\WaveformComparison\waveform_dataset.csv")
dep = d[((d.Waveform == "OTFS") & (d.Detector == "MRC"))
        | ((d.Waveform == "ODDM") & (d.Detector == "LMMSE"))]
w = dep.pivot_table(index=["CondID", "TrialIdx"], columns="Waveform",
                    values="BER", aggfunc="min")
f = dep.groupby(["CondID", "TrialIdx"]).first()[
    ["Environment", "Speed_kmh", "DelayProfile", "Modulation", "SNR_dB",
     "DopplerSpread"]]
win = w.idxmin(axis=1)
fa = f.assign(win=win)

print("ODDM win share by modulation:")
print(fa.groupby("Modulation").win.apply(lambda s: (s == "ODDM").mean()).round(3))
print("\nby (profile, modulation):")
print(fa.groupby(["DelayProfile", "Modulation"]).win.apply(
    lambda s: (s == "ODDM").mean()).round(3))
ow = fa[fa.win == "ODDM"]
if len(ow):
    print("\nODDM wins: SNR", ow.SNR_dB.min(), "-", ow.SNR_dB.max(),
          "| speed", ow.Speed_kmph.min(), "-", ow.Speed_kmph.max(),
          "| doppler", round(ow.DopplerSpread.min(), 3), "-",
          round(ow.DopplerSpread.max(), 3))
