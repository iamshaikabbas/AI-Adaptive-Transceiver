# AI-Adaptive Transceiver — Project Summary

End-to-end study comparing **ZP-OTFS (MRC / LMMSE)**, a **newly implemented genuine ODDM chain**, and an **OFDM baseline**, then training an **AI waveform selector** that adapts the waveform in real time as channel conditions change.

---

## 1. Repository layout (this effort)

```
AI-Adaptive-Transceiver/
├─ PROJECT_SUMMARY.md                  ← this file
├─ .venv/                              ← Python 3.14 env (sklearn, pandas, joblib, matplotlib)
└─ OTFS MRC detection MATLAB code/
   ├─ sim_default_config.m             shared cfg for ALL waveforms (paired trials)
   ├─ gen_channel_params_flex.m        shared channel generator (EPA/EVA/ETU/flat/AWGN/synthetic-N)
   ├─ build_stream_channel.m           linear time-varying stream channel r = H s
   ├─ ODDM_modulate.m / ODDM_demodulate.m / ODDM_detect.m      ← new ODDM core
   ├─ run_otfs.m / run_oddm.m / run_ofdm.m          common-interface simulators
   ├─ compute_common_metrics.m         identical metric block for all waveforms
   ├─ validate_oddm.m                  ODDM validation ladder (A–D × detectors)
   ├─ run_paired_trials.m              paired-trial engine (shared chan/bits/noise seed)
   ├─ combo_defs.m / save_compare_results.m / plot_compare_metric.m
   ├─ compare_otfs_oddm_{snr,velocity,doppler,channel,environment,multipath,
   │                    modulation,detector,runtime}.m     (9 experiments)
   ├─ run_all_comparisons.m            master runner
   ├─ build_waveform_dataset.m         merged dataset writer (9720 rows)
   ├─ realtime_adaptive.m              real-time adaptive drive (MATLAB ↔ Python)
   ├─ Results/WaveformComparison/      CSVs + PNGs of every experiment + adaptive trace
   └─ otfs_ai_pipeline/
      ├─ train_waveform_selector.py    trains selector (2-class & 3-class), group-aware eval
      ├─ predict_waveform.py           per-frame inference CLI used by MATLAB
      ├─ build_dashboard.py            consolidated 30-panel dashboard
      ├─ models/waveform_selector_2c.joblib (+3c, meta JSONs)
      └─ AI_Results/{Reports,Graphs,Dashboard}/
```

## 2. Simulation core

- **Grid**: N=32 × M=32, Δf=15 kHz, fc=4 GHz; ZP-OTFS per the original repo chain (untouched); ODDM with L_cp=8; OFDM N-blocks with CP.
- **Shared plumbing**: `sim_default_config` → `gen_channel_params_flex` → identical `chan`, `tx_bits`, and noise seed fed to all three `run_*` functions ⇒ strictly paired comparisons.
- **ODDM math**: input symbols live on the delay axis; modulation spreads each tap across time via IDFT. The exact discrete channel is

  `H_dd = (F_N ⊗ I_M) · C · (conj(F_N) ⊗ I_M)`,

  with phase keys evaluated at the **unwrapped absolute sample index** q'+L_cp−l. Two early bugs (Kronecker factor order on the TX side, wrapped-vs-unwrapped phase keys) were found by consistency testing (`debug_oddm2.m`: ‖H_dd·x − y_noiseless‖ ≈ 5e-16) and fixed.
- **Detectors**: ODDM-MMSETAP (per-delay-row one-tap MMSE, ignores ICI off-diagonals) and ODDM-LMMSE (full dense MMSE on H_dd). OTFS: repo MRC (50 iter) + LMMSE. OFDM: exact TF-domain kernel with Dirichlet-decay ICI + MMSETAP/LMMSE.

### Validation results (`validate_oddm.m`)
| Ladder | Result |
|---|---|
| A_AWGN | BER→0, theory ratio ≈ 0.98–1.00 ✔ |
| B_RayleighFlat | monotone, matches flat-Rayleigh QPSK curve ✔ |
| C_DopplerFlat (ν≈0.09) | MMSETAP shows expected ICI floor (~0.31); LMMSE recovers full waterfall ✔ |
| D_DopplerEVA | same physics: single-tap equalizer is ICI-limited, dense LMMSE fine ✔ |

Verdict logic treats a *flat, high-floor* ladder as a pass-with-note only when it is genuinely ICI-limited (max/min < 1.6 and min > 1e-2) — the floor is channel physics, not a bug.

## 3. Comparison suite (9 experiments)

All experiments use paired trials (identical realization/payload/noise per trial across waveforms). Master runner:

```matlab
run_all_comparisons     % runs all 9, saves CSV+PNG per experiment
```

Outputs in `Results\WaveformComparison\`. Headline findings:
- **OTFS-MRC dominates most of the grid** (wins ~90% of pair groups) — robustness to high speed/delay spread is its strength; cost: detector latency.
- **ODDM-LMMSE** is competitive at high SNR and low Doppler (better spectral efficiency due to CP-only overhead vs ZP) but suffers under fractional Doppler with the tap detector.
- **OFDM** collapses once Doppler exceeds ~1 subcarrier spacing unless the full Dirichlet-kernel ICI model + dense equalizer is used (the earlier approximate kernel produced a fake 0.45 floor).

## 4. Dataset & AI waveform selector

`build_waveform_dataset.m` merges everything into `waveform_dataset.csv` — **9720 rows = 1620 pair groups × 6 waveform/detector combos**, features: Environment, Speed_kmh, DelayProfile, DelaySpread, NumPaths, DopplerSpread, Modulation, SNR_dB.

Label rule per group: `argmin BER` (ties → PER → runtime). Class imbalance is real (OTFS 1468 / ODDM 152 in 2-class view), so class-weighted model variants are trained and scored additionally by **regret** = mean log10(BER_chosen / BER_oracle).

Split is **group-aware** (GroupShuffleSplit over CondIDs — unseen test conditions).

| Variant | Best model | Test acc | Macro-F1 | Regret [dec] | Baseline regret |
|---|---|---|---|---|---|
| 2-class (OTFS/ODDM) | DecisionTreeBal | 0.852 | **0.618** | 0.018 | always-OTFS: 0.002 |
| 3-class (+OFDM) | RandomForestBal | 0.849 | 0.476 | 0.026 | always-OTFS: 0.020 |

Honest reading: because OTFS wins most cells in this grid, raw accuracy can't beat the trivial "always-OTFS" policy; macro-F1 (balanced-error) and regret are the meaningful scores, and the selector's value appears exactly where conditions favor ODDM/OFDM.

Retrain:
```powershell
python train_waveform_selector.py --classes 2
python train_waveform_selector.py --classes 3
```

## 5. Real-time adaptive loop (`realtime_adaptive.m`)

Per frame: evolve scenario (EPA→EVA→ETU profile switches, 3→350 km/h ramp, sinusoidal SNR 6–22 dB) → write scenario JSON → call `predict_waveform.py --classes 2` → run chosen **and** all candidates under identical conditions → log decision vs oracle.

Result (60 frames): **85% optimal choices**, mean chosen CQI 12.98, visible OTFS↔ODDM switching in the hard low-SNR EVA stretch (frames ~26–39), median instantaneous regret ≈ 0 dec. Artifacts: `adaptive_trace.csv`, `adaptive_timeline.png`.

Run:
```matlab
realtime_adaptive
```

## 6. Dashboard

`build_dashboard.py` renders **30 panels** in three layers (winner distributions, link metrics vs SNR, robustness sweeps, paired advantage structure, selector diagnostics incl. holdout confusion matrix/importances, real-time trace):

```powershell
python build_dashboard.py
# → otfs_ai_pipeline/AI_Results/Dashboard/dashboard.png (+ .html index)
```

## 7. Known limitations

- Small grid (N=M=32) keeps runtime sane but limits absolute BER floors; conclusions are about relative ordering, not link budgets.
- Selector trained on the current condition grid — retrain after extending the grid (e.g., add SNR<0 dB, more profiles, MIMO).
- MRC iteration count fixed at 50; latency numbers are wall-clock on the dev machine (relative comparisons only).
- OFDM uses the exact TF kernel derived here, not LTE-style pilots; no channel estimation error modeled anywhere (perfect CSI assumed).
