"""
build_dashboard.py
==================
Builds a single consolidated dashboard (30 panels) covering every layer of
the project:

  A. Dataset overview      - winner distribution by condition (5 panels)
  B. Link metrics vs SNR   - BER/PER/CQI/throughput/SE (5 panels)
  C. Robustness sweeps     - speed/profile/modulation/EVM/latency (5)
  D. Paired-trial analysis - ODDM-vs-OTFS advantage structure (5)
  E. AI selector           - models, confusion matrix, importances (6)
  F. Real-time trace       - adaptive decisions vs oracle (4)

Inputs (relative to repo MATLAB dir):
  Results/WaveformComparison/waveform_dataset.csv
  Results/WaveformComparison/adaptive_trace.csv
  otfs_ai_pipeline/models/waveform_selector_2c.joblib (+ meta)
  otfs_ai_pipeline/AI_Results/Reports/*

Outputs:
  AI_Results/Dashboard/dashboard.png
  AI_Results/Dashboard/dashboard.html

Usage:  python build_dashboard.py
"""

import json
import os
import warnings

import joblib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.model_selection import GroupShuffleSplit

from train_waveform_selector import (FEATURE_COLS, RANDOM_STATE,
                                     build_group_table)

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)                      # .../OTFS MRC detection MATLAB code
RES  = os.path.join(ROOT, "Results", "WaveformComparison")
OUTD = os.path.join(HERE, "AI_Results", "Dashboard")
os.makedirs(OUTD, exist_ok=True)

CLASSES = ["ODDM", "OFDM", "OTFS"]
DEF_DET = {"OTFS": "MRC", "ODDM": "LMMSE", "OFDM": "LMMSE"}
WFCOL   = {"OTFS": "tab:blue", "ODDM": "tab:red", "OFDM": "tab:green"}
FLOOR   = 1e-7

plt.rcParams.update({"font.size": 8.5, "axes.titlesize": 9,
                     "axes.titleweight": "bold", "axes.grid": True,
                     "grid.alpha": 0.3})


def deployed_rows(ds):
    """Rows corresponding to the deployable default detector of each wf."""
    parts = [ds[(ds.Waveform == w) & (ds.Detector == det)]
             for w, det in DEF_DET.items()]
    return pd.concat(parts)


def winner_labels(sub):
    """Per-pair winner using the deployment rule min-BER (ties->first)."""
    wide = sub.pivot_table(index=["CondID", "TrialIdx"], columns="Waveform",
                           values="BER", aggfunc="min")
    feats = sub.groupby(["CondID", "TrialIdx"]).first()
    ber = wide[CLASSES].to_numpy()
    win = [CLASSES[i] for i in ber.argmin(axis=1)]
    out = feats[FEATURE_COLS].copy()
    out["winner"] = win
    return out.reset_index()


def mean_curve(df, col):
    g = df.groupby(["SNR_dB", "Waveform"])[col].mean().reset_index()
    return g


def main():
    ds = pd.read_csv(os.path.join(RES, "waveform_dataset.csv"))
    tr = pd.read_csv(os.path.join(RES, "adaptive_trace.csv"))
    dep = deployed_rows(ds)
    wins = winner_labels(dep)

    # ---- selector holdout reproduction -----------------------------------
    sel = {}
    try:
        tab = build_group_table(pd.read_csv(
            os.path.join(RES, "waveform_dataset.csv")), ["ODDM", "OTFS"])
        splitter = GroupShuffleSplit(n_splits=1, test_size=0.25,
                                     random_state=RANDOM_STATE)
        _, te = next(splitter.split(tab[FEATURE_COLS], tab["label"],
                                    tab["CondID"]))
        te_tab = tab.iloc[te].reset_index(drop=True)
        pipe = joblib.load(os.path.join(
            HERE, "models", "waveform_selector_2c.joblib"))
        pred = pipe.predict(te_tab[FEATURE_COLS])
        proba = pipe.predict_proba(te_tab[FEATURE_COLS]).max(axis=1)
        sel = {"te": te_tab, "pred": pred, "proba": proba}
        with open(os.path.join(HERE, "models",
                               "waveform_selector_meta_2c.json")) as fh:
            sel["meta"] = json.load(fh)
    except Exception as exc:                                   # noqa: BLE001
        print(f"selector overlay unavailable: {exc}")

    cmp2 = pd.read_csv(os.path.join(
        HERE, "AI_Results", "Reports", "waveform_model_comparison_2c.csv"))
    try:
        rep_txt = open(os.path.join(HERE, "AI_Results", "Reports",
                                    "waveform_selector_report_2c.txt")).read()
    except OSError:
        rep_txt = ""

    fig, axes = plt.subplots(6, 5, figsize=(25, 31))
    fig.suptitle("AI-Adaptive Transceiver - Consolidated Dashboard\n"
                 "OTFS (ZP-MRC) vs ODDM vs OFDM | paired trials N=32 M=32 | "
                 "selector: RandomForestBal (OTFS/ODDM)",
                 fontsize=14, fontweight="bold")

    # =================== ROW A : winner distribution ======================
    ax = axes[0, 0]
    cnt = wins["winner"].value_counts().reindex(CLASSES).fillna(0)
    ax.bar(cnt.index, cnt.values, color=[WFCOL[c] for c in CLASSES])
    for i, v in enumerate(cnt.values):
        ax.text(i, v, f"{int(v)}\n({100*v/cnt.sum():.0f}%)",
                ha="center", va="bottom")
    ax.set_title("A1 Winner distribution (paired)")
    ax.set_ylabel("pair groups"); ax.set_ylim(0, cnt.max()*1.22)

    ax = axes[0, 1]
    ct = pd.crosstab(wins["Environment"], wins["winner"], normalize="index")
    ct = ct.reindex(columns=CLASSES).fillna(0)
    ct.plot.bar(ax=ax, color=[WFCOL[c] for c in CLASSES], legend=False)
    ax.set_title("A2 Winner share by environment"); ax.set_ylabel("share")
    ax.tick_params(axis="x", rotation=15); ax.set_ylim(0, 1.05)

    ax = axes[0, 2]
    ct = pd.crosstab(wins["DelayProfile"], wins["winner"], normalize="index")
    ct = ct.reindex(columns=CLASSES).fillna(0)
    ct.plot.bar(ax=ax, color=[WFCOL[c] for c in CLASSES], legend=False)
    ax.set_title("A3 Winner share by delay profile"); ax.set_ylabel("share")
    ax.tick_params(axis="x", rotation=0); ax.set_ylim(0, 1.05)

    ax = axes[0, 3]
    wb = pd.cut(wins.SNR_dB, [-1, 2.5, 7.5, 12.5, 17.5, 22.5, 30],
                labels=["0-2", "3-7", "8-12", "13-17", "18-22", "23+"])
    ct = pd.crosstab(wb, wins["winner"], normalize="index")
    ct = ct.reindex(columns=CLASSES).fillna(0)
    ct.plot.bar(ax=ax, color=[WFCOL[c] for c in CLASSES],
                legend=False, stacked=True)
    ax.set_title("A4 Winner share vs SNR bin"); ax.set_ylabel("share")
    ax.set_xlabel("SNR bin [dB]"); ax.set_ylim(0, 1.05)

    ax = axes[0, 4]
    wb = pd.cut(wins.Speed_kmh, [0, 10, 60, 130, 260, 400],
                labels=["<=10", "11-60", "61-130", "131-260", ">260"])
    ct = pd.crosstab(wb, wins["winner"], normalize="index")
    ct = ct.reindex(columns=CLASSES).fillna(0)
    ct.plot.bar(ax=ax, color=[WFCOL[c] for c in CLASSES],
                legend=False, stacked=True)
    ax.set_title("A5 Winner share vs speed bin"); ax.set_ylabel("share")
    ax.set_xlabel("speed [km/h]"); ax.set_ylim(0, 1.05)
    handles = [plt.Rectangle((0, 0), 1, 1, color=WFCOL[c]) for c in CLASSES]
    ax.legend(handles, CLASSES, fontsize=7, loc="lower right")

    # =================== ROW B : metrics vs SNR ===========================
    for k, (col, ttl, logy) in enumerate([
            ("BER", "B1 Mean BER vs SNR", True),
            ("PER", "B2 Packet-error rate vs SNR", False),
            ("CQI", "B3 Reported CQI vs SNR", False),
            ("Throughput_bps", "B4 Throughput vs SNR [kbps]", False),
            ("SpectralEfficiency_bps_per_Hz", "B5 Spectral eff. [bps/Hz]", False)]):
        ax = axes[1, k]
        g = mean_curve(dep, col)
        for w in CLASSES:
            s = g[g.Waveform == w]
            y = s[col].to_numpy(dtype=float)
            if logy:
                y = np.maximum(y, FLOOR)
            ax.plot(s.SNR_dB, y, "-o", ms=3, color=WFCOL[w], label=w)
        if logy:
            ax.set_yscale("log")
        elif col == "CQI":
            ax.set_ylim(0, 15.5)
        ax.set_title(ttl); ax.set_xlabel("SNR [dB]")
        if k == 0:
            ax.set_ylabel("BER" if logy else col); ax.legend(fontsize=7)
        else:
            ax.set_ylabel(col.split("_")[0])

    # =================== ROW C : robustness sweeps ========================
    ax = axes[2, 0]
    dep2 = dep.copy()
    dep2["spd_bin"] = pd.cut(dep2.Speed_kmh, [0, 10, 60, 130, 260, 400],
                             labels=["<=10", "11-60", "61-130",
                                     "131-260", ">260"])
    g = dep2.groupby(["spd_bin", "Waveform"])["BER"].mean().reset_index()
    for w in CLASSES:
        s = g[g.Waveform == w]
        ax.plot(range(len(s)), np.maximum(s.BER, FLOOR), "-o", ms=3,
                color=WFCOL[w], label=w)
    ax.set_yscale("log"); ax.set_xticks(range(5),
                                        ["<=10", "11-60", "61-130",
                                         "131-260", ">260"])
    ax.set_title("C1 Mean BER vs speed"); ax.set_xlabel("speed [km/h]")
    ax.set_ylabel("BER")

    ax = axes[2, 1]
    piv = dep.pivot_table(index="DelayProfile", columns="Waveform",
                          values="BER", aggfunc="mean").reindex(
                              index=["EPA", "EVA", "ETU"], columns=CLASSES)
    piv.plot.bar(ax=ax, color=[WFCOL[c] for c in CLASSES])
    ax.set_yscale("log"); ax.set_ylim(FLOOR, 1)
    ax.set_title("C2 Mean BER by delay profile"); ax.set_ylabel("BER")
    ax.tick_params(axis="x", rotation=0)
    ax.get_legend().remove()

    ax = axes[2, 2]
    mods = sorted(dep.Modulation.unique())
    x = np.arange(len(mods)); wd = 0.26
    for i, w in enumerate(CLASSES):
        vals = [dep[(dep.Modulation == m) & (dep.Waveform == w)].BER.mean()
                for m in mods]
        ax.bar(x + (i-1)*wd, np.maximum(vals, FLOOR), wd, color=WFCOL[w],
               label=w)
    ax.set_yscale("log"); ax.set_xticks(x, [f"{m}-QAM" if m > 4 else "QPSK"
                                            for m in mods])
    ax.set_title("C3 Mean BER by modulation"); ax.set_ylabel("BER")

    ax = axes[2, 3]
    g = mean_curve(dep, "EVM_percent")
    for w in CLASSES:
        s = g[g.Waveform == w]
        ax.plot(s.SNR_dB, s.EVM_percent, "-o", ms=3, color=WFCOL[w], label=w)
    ax.set_title("C4 EVM vs SNR [%]"); ax.set_xlabel("SNR [dB]")
    ax.set_ylabel("EVM %")

    ax = axes[2, 4]
    g = dep.groupby(["SNR_dB", "Waveform"])["Runtime_sec"].median().reset_index()
    for w in CLASSES:
        s = g[g.Waveform == w]
        ax.plot(s.SNR_dB, s.Runtime_sec*1000, "-o", ms=3, color=WFCOL[w],
                label=w)
    ax.set_yscale("log")
    ax.set_title("C5 Detector latency (median)"); ax.set_xlabel("SNR [dB]")
    ax.set_ylabel("ms / frame")

    # =================== ROW D : paired analysis ==========================
    pair = dep.pivot_table(index=["CondID", "TrialIdx"], columns="Waveform",
                           values="BER", aggfunc="min")[["OTFS", "ODDM"]]
    delta = np.log10(np.maximum(pair.ODDM, FLOOR)) - \
        np.log10(np.maximum(pair.OTFS, FLOOR))
    ax = axes[3, 0]
    ax.hist(delta, bins=40, color="slateblue", edgecolor="k", lw=.2)
    ax.axvline(0, color="k", lw=1.2)
    ax.axvline(delta.median(), color="crimson", ls="--",
               label=f"median {delta.median():+.2f} dec")
    ax.set_title("D1 Paired log10(BER_ODDM/BER_OTFS)")
    ax.set_xlabel("decades"); ax.legend(fontsize=7)

    ax = axes[3, 1]
    db = pd.cut(wins.DopplerSpread, [-.001, .02, .05, .1, .2, .35, 1],
                labels=["<.02", ".02-.05", ".05-.1", ".1-.2", ".2-.35", ">.35"])
    piv = pd.crosstab(db, wins.SNR_dB, values=(wins.winner == "ODDM"),
                      aggfunc="mean")
    im = ax.imshow(piv.to_numpy(dtype=float), aspect="auto", cmap="RdYlGn_r",
                   vmin=0, vmax=1, origin="lower")
    ax.set_xticks(range(piv.shape[1]), piv.columns)
    ax.set_yticks(range(piv.shape[0]), piv.index.astype(str))
    ax.set_title("D2 P(ODDM optimal) heat: Doppler x SNR")
    ax.set_xlabel("SNR [dB]"); ax.set_ylabel("norm. Doppler spread")
    fig.colorbar(im, ax=ax, fraction=.046)

    ax = axes[3, 2]
    rt = dep.groupby("Waveform").Runtime_sec.apply(list)
    bp = ax.boxplot([rt[w] for w in CLASSES], tick_labels=CLASSES, showfliers=False)
    for patch, w in zip(bp["boxes"], CLASSES):
        patch.set_color(WFCOL[w]); patch.set_alpha(.6)
    ax.set_yscale("log"); ax.set_title("D3 Runtime per waveform (full chain)")
    ax.set_ylabel("s / frame")

    ax = axes[3, 3]
    g = mean_curve(dep, "SINR_est_dB")
    for w in CLASSES:
        s = g[g.Waveform == w]
        ax.plot(s.SNR_dB, s.SNR_dB, "k:", lw=.8)
        ax.plot(s.SNR_dB, s.SINR_est_dB, "-o", ms=3, color=WFCOL[w], label=w)
    ax.set_title("D4 Effective SINR (EVM-based) vs SNR")
    ax.set_xlabel("SNR [dB]"); ax.set_ylabel("SINR est [dB]")

    ax = axes[3, 4]
    dd = pd.DataFrame({"snr": wins.SNR_dB.to_numpy(),
                       "oddm_adv": (delta.to_numpy() < 0)})
    g = dd.groupby("snr").oddm_adv.mean()
    ax.plot(g.index, 100*g, "-o", color="tab:red", label="ODDM wins")
    ax.axhline(50, color="k", ls=":")
    ax.set_title("D5 % frames where ODDM beats OTFS")
    ax.set_xlabel("SNR [dB]"); ax.set_ylabel("% of pairs"); ax.set_ylim(0, 100)

    # =================== ROW E : selector =================================
    ax = axes[4, 0]
    x = np.arange(len(cmp2)); wd = .27
    for i, (c, cc) in enumerate([("Accuracy", "tab:blue"),
                                 ("MacroF1", "tab:orange"),
                                 ("Regret_log10", "tab:red")]):
        ax.bar(x + (i-1)*wd, cmp2[c], wd, label=c, color=cc)
    ax.set_xticks(x, cmp2.Model, rotation=20, ha="right", fontsize=6.5)
    ax.set_title("E1 Candidate models (2-class, group-split)")
    ax.legend(fontsize=7)

    ax = axes[4, 1]
    if sel:
        from sklearn.metrics import confusion_matrix
        cm = confusion_matrix(sel["te"]["label"], sel["pred"],
                              labels=["ODDM", "OTFS"])
        im = ax.imshow(cm, cmap="Blues")
        for i in range(2):
            for j in range(2):
                ax.text(j, i, cm[i, j], ha="center", va="center",
                        color="white" if cm[i, j] > cm.max()/2 else "black")
        ax.set_xticks([0, 1], ["ODDM", "OTFS"])
        ax.set_yticks([0, 1], ["ODDM", "OTFS"])
        acc = float((sel["te"]["label"].to_numpy() == sel["pred"]).mean())
        ax.set_title(f"E2 Confusion (holdout, acc={acc:.2f})")
        fig.colorbar(im, ax=ax, fraction=.046)
    else:
        ax.text(.5, .5, "model unavailable", ha="center"); ax.axis("off")

    ax = axes[4, 2]
    if rep_txt:
        ax.text(0, 1, "\n".join(rep_txt.splitlines()[14:24]), family="monospace",
                fontsize=6, va="top")
    ax.set_title("E3 Classification report (holdout)"); ax.axis("off")

    ax = axes[4, 3]
    try:
        imp = pipe.named_steps["clf"].feature_importances_
        names = (list(pipe.named_steps["pre"]
                      .named_transformers_["cat"].get_feature_names_out(
                          ["Environment", "DelayProfile"]))
                 + [c for c in FEATURE_COLS
                    if c not in ("Environment", "DelayProfile")])
        o = np.argsort(imp)[::-1][:12]
        ax.barh(range(len(o)), imp[o][::-1],
                color=plt.cm.viridis(np.linspace(.3, .9, len(o))))
        ax.set_yticks(range(len(o)), [names[i] for i in o][::-1], fontsize=6)
        ax.set_title("E4 Top feature importances")
    except Exception:
        ax.text(.5, .5, "n/a", ha="center"); ax.axis("off")

    ax = axes[4, 4]
    if sel:
        ev = sel["te"][["SNR_dB"]].copy()
        ev["ok"] = (ev.index.to_series().notna()) & \
                   (sel["pred"] == sel["te"]["label"].to_numpy())
        g = ev.groupby("SNR_dB").ok.mean()
        base = float((sel["te"]["label"] == "OTFS").mean())
        ax.plot(g.index, g.values, "-o", color="darkred", label="selector")
        ax.axhline(base, ls="--", color="gray", label=f"always-OTFS {base:.2f}")
        ax.set_ylim(0, 1.05); ax.legend(fontsize=7)
        ax.set_title("E5 Selection accuracy vs SNR")
        ax.set_xlabel("SNR [dB]")
    else:
        ax.axis("off")

    # =================== ROW F : real-time trace ==========================
    fr = tr.frame
    ax = axes[5, 0]
    code = tr.chosen_waveform.map({"ODDM": 1, "OFDM": 2, "OTFS": 3})
    ax.step(fr, code, where="post", color="navy", lw=1.6)
    ax.set_yticks([1, 2, 3], ["ODDM", "OFDM", "OTFS"]); ax.set_ylim(.5, 3.5)
    ax.set_title("F1 Adaptive decisions (60-frame drive)")
    ax.set_xlabel("frame")

    ax = axes[5, 1]
    ax.semilogy(fr, np.maximum(tr.BER_OTFS, FLOOR), "-o", ms=2.5,
                color=WFCOL["OTFS"], label="OTFS")
    ax.semilogy(fr, np.maximum(tr.BER_ODDM, FLOOR), "-s", ms=2.5,
                color=WFCOL["ODDM"], label="ODDM")
    ax.semilogy(fr, np.maximum(tr.BER_OFDM, FLOOR), "-^", ms=2.5,
                color=WFCOL["OFDM"], label="OFDM")
    ax.semilogy(fr, np.maximum(tr.BER_oracle, FLOOR), "k--", lw=1,
                label="oracle")
    ax.set_title("F2 Frame BER: candidates vs oracle"); ax.set_xlabel("frame")
    ax.set_ylabel("BER"); ax.legend(fontsize=6, ncol=2)

    ax = axes[5, 2]
    ax.plot(fr, np.cumsum(~tr.optimal_choice.astype(bool)), color="crimson")
    opt = 100*tr.optimal_choice.mean()
    ax.set_title(f"F3 Cumulative sub-optimal frames ({opt:.0f}% optimal)")
    ax.set_xlabel("frame")

    ax = axes[5, 3]
    reg = np.log10(np.maximum(tr.BER_chosen, FLOOR) /
                   np.maximum(tr.BER_oracle, FLOOR))
    ax.hist(reg, bins=15, color="teal", edgecolor="k", lw=.3)
    ax.set_title("F4 Adaptation regret histogram")
    ax.set_xlabel("log10(BER_chosen/BER_oracle)")

    ax = axes[5, 4]
    txt = (f"drive summary\n{'-'*26}\n"
           f"frames             : {len(tr)}\n"
           f"optimal choices    : {int(tr.optimal_choice.sum())}"
           f" ({opt:.1f}%)\n"
           f"mean chosen CQI    : {tr.CQI_chosen.mean():.2f}\n"
           f"switches           : "
           f"{int((tr.chosen_waveform != tr.chosen_waveform.shift()).sum()-1)}\n"
           f"median regret      : {np.median(reg):+.3f} dec\n"
           f"profiles           : EPA->EVA->ETU\n"
           f"speed              : {tr.speed_kmph.min():.0f}->"
           f"{tr.speed_kmph.max():.0f} km/h\n"
           f"SNR range          : {tr.SNR_dB.min():.1f}-"
           f"{tr.SNR_dB.max():.1f} dB")
    ax.text(0, .95, txt, family="monospace", fontsize=7.5, va="top")
    ax.set_title("F5 Drive statistics"); ax.axis("off")

    png = os.path.join(OUTD, "dashboard.png")
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    fig.savefig(png, dpi=120)
    plt.close(fig)

    html = f"""<!DOCTYPE html>
<html><head><title>AI-Adaptive Transceiver Dashboard</title>
<style>body{{font-family:Segoe UI,Arial;margin:24px;background:#111;color:#eee}}
img{{max-width:100%;border:1px solid #444}}
a{{color:#6cf}} table{{border-collapse:collapse}} td,th{{border:1px solid #555;padding:4px 10px}}</style>
</head><body>
<h1>AI-Adaptive Transceiver - Dashboard</h1>
<p>Paired-trial dataset: {len(ds)} rows | pair groups: {len(wins)} |
real-time drive: {len(tr)} frames</p>
<img src="dashboard.png" alt="dashboard">
<h2>Artifacts</h2>
<table><tr><th>Layer</th><th>File</th></tr>
<tr><td>Dataset</td><td><a href="../../Results/WaveformComparison/waveform_dataset.csv">waveform_dataset.csv</a></td></tr>
<tr><td>Real-time trace</td><td><a href="../../Results/WaveformComparison/adaptive_trace.csv">adaptive_trace.csv</a></td></tr>
<tr><td>Model comparison</td><td><a href="../Reports/waveform_model_comparison_2c.csv">waveform_model_comparison_2c.csv</a></td></tr>
<tr><td>Training report</td><td><a href="../Reports/waveform_selector_report_2c.txt">waveform_selector_report_2c.txt</a></td></tr>
<tr><td>Trained model</td><td>models/waveform_selector_2c.joblib</td></tr>
</table>
</body></html>"""
    with open(os.path.join(OUTD, "dashboard.html"), "w") as fh:
        fh.write(html)
    print(f"dashboard -> {png}")
    print(f"dashboard -> {os.path.join(OUTD, 'dashboard.html')}")


if __name__ == "__main__":
    warnings.filterwarnings("ignore")
    main()
