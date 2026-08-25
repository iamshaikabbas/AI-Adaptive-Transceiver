# PHASE 2 — VALIDATION RECORD

Generated: 2026-08-23 · Mode: FULL · No git operations performed (per spec).

## Checklist

1. **No git commits** — none made in Phase 2. Working tree only.
2. **Paired trials verified** — all dataset conditions ran through
   `run_paired_trials` (identical channel realization, payload bits, noise
   seed per trial across waveforms; only waveform differs). nTrials = 3.
3. **No fabricated labels / honest ties** — `best_waveform` derived from
   measured metrics only. Strict dual tie rule (|ΔACS| < 0.005 OR relative
   BER gap < 10% ⇒ tie). Tie variants: 115 `tie`, 104 `tie_otfs`,
   3 `tie_oddm` out of 579 conditions. Ties excluded from training,
   reported separately.
4. **Leak-free split by construction** — main grid TRAIN lattice
   (SNR {-10,-5,0,5,10,15,20} × speed {0,20,60,100,150,200,300}) vs TEST
   lattice (SNR {-3,2,7,12,17,22} × speed {10,40,80,120,250,350}):
   intersection = ∅ (checked programmatically). VAL = deterministic
   positional stratified holdout of train (every 5th sorted condition per
   class), re-assigned AFTER simulation, contains both classes
   (2 ODDM + 29 OTFS decisive). TEST untouched by re-split.
   Final counts: 278 train / 55 val / 246 test conditions.
5. **Axes as designed** — 579 conditions = 294 main-train + 216 main-test +
   45 64-QAM slice (27 train / 18 test) + 24 carrier slice
   ({2 GHz, 5.9 GHz} × EVA × QPSK, 16 train / 8 test).
6. **Artifacts saved** — `models/waveform_selector_v2.joblib` (RF bundle:
   model, feature list, categorical encodings, classes),
   `models/training_meta.json`, reports under
   `otfs_ai_pipeline/AI_Results/Reports/`.
7. **Unseen-condition evaluation reported honestly incl. weaknesses** —
   test accuracy on decisive labels 94.5% (156/165); ODDM recall only 2/8
   (ODDM-decisive conditions are rare project-wide: 16/579 — stated, not
   hidden). Mean |ΔBER| regret vs BER-oracle 4.5e-3, max 6.3e-2; mean ACS
   regret 0.0073. Relative-BER regret blows up at the BER floor where both
   waveforms are error-free; absolute deltas are the operational numbers.
   Confidence buckets: all predictions ≥0.9 confidence (trees are
   overconfident at this sample size — noted).
8. **Scenario JSONs loadable & schema-compatible** — scenarios A–D
   (`Results/DigitalTwin/scenario_{a,b,c,d}.json/.csv`, 60 points each):
   field-for-field match with ScenarioPoint (scenario.py) and the `pt`
   struct consumed by `twin_run_frame.m`/`ai_decide_frame.m`
   (`phase2_scenario_check.py`: schema/speed bounds/profiles/frame order
   ALL PASS for all four).
9. **Compat smoke frame passes** — scenario A point 1 through
   `twin_run_frame('OTFS','MRC')`: BER=0, PER=0, throughput=900000 bps,
   error_flag=0 (`Results/DigitalTwin/_smoke_frame_row.csv`).
10. **Compute within FULL budget** — exploration 180 conds in 38 s;
    full matrix 579 conds × 2 wf × 3 trials in ~2.8 min single MATLAB
    session. Training+eval < 1 min Python.
11. **Environment mapping corrected** — v2 profiles map Highway→EVA and
    HSR→EVA (physical), replacing v1's Highway/HSR→ETU which biased the
    twin toward OTFS. Documented in `environment_profiles_v2.csv`.

## Known limitations (honest)

- ODDM-decisive regions exist but are narrow (EPA/EVA × QPSK × SNR ≥ 10 dB,
  speed ≳ 100 km/h). Under strict tie rules only 16/579 conditions are
  decisive-ODDM → minority-class learning is data-limited; RF finds 25% of
  them on unseen axes vs 0% for always-OTFS dummy.
- The selector's practical value concentrates in avoiding OTFS-side regret
  inside fast-QPSK regions and confirming OTFS on 16-QAM/ETU regions;
  tie-region behaviour is conservative (mostly OTFS).
- v1 metric-regressor chain (`ai_engine.py`) was NOT retrained (out of
  scope); K1 (adaptive never switches) remains open until a future phase
  retrains it on this expanded dataset.
