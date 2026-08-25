# PHASE 4 VALIDATION REPORT

Generated: 2026-08-23 18:28:19   Duration: 255 s
Result: **20/20 tests PASS**

| # | Test | Status | Evidence |
|---|------|--------|----------|
| T1 | phase-3 baseline frozen & canonical traces untouched | PASS | hash-equal={'fixed_otfs': True, 'fixed_oddm': True, 'ai_adaptive': True, 'oracle': True} |
| T2 | 67-col extended trace schema with uncertainty/band/paired-TP-CQI | PASS | missing=[] ncols=67 |
| T3 | tuning E-H / held-out I-L / difficult M-R tiers exist and are disjoint from final A-D | PASS | scenarios=['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M', 'N', 'O', 'P', 'Q', 'R'] |
| T4 | tagged runs never touch canonical outputs; per-frame AI feature vectors recorded (states sidecar) | PASS | states_ok=True features=True canonical_oracle_untouched=True |
| T5 | every collected frame records BOTH waveforms' actual ACS/BER/TP/CQI (paired execution) | PASS |  |
| T6 | final A-D P4 run uses identical seeds/payload/channels as the frozen baseline | PASS |  |
| T7 | rapid accel/decel (M,N): complete error-free runs, no oscillation | PASS | osc=0 |
| T8 | SNR drop/recover (O,P): every transition answered and logged (switch or already-optimal) | PASS |  |
| T9 | high-doppler HSR (Q, 250 km/h): stable run, decisions logged, ACS in range | PASS |  |
| T10 | profile transition (R): both transitions logged | PASS |  |
| T11 | difficult-set outcome: P4 policy >= P3 policy on ACS with zero bad switches | PASS | P4=0.5112 P3=0.5024 |
| T12 | offline replay reproduces live execution EXACTLY (decisions and confidence bands) | PASS | decision_mismatch=0/144 band_mismatch=0/144 |
| T13 | zero-BER rows handled by documented log10 clipping; two-part model tested and NOT adopted (worse MAE); counts consistent | PASS | zero_ber=89 v2style_MAE=0.667 twopart_MAE=0.695 |
| T14 | RF estimator disagreement predicts prediction error (Spearman>0.5, p<1e-6, both metrics) | PASS | Log10BER rho=0.766 ACS rho=0.743 |
| T15 | tau_low/tau_high are empirical tertiles of tuning agreement scores; all three bands occur in practice | PASS | recomputed=(0.305,0.585) config=(0.305,0.585) bands_seen=['HIGH', 'LOW', 'MEDIUM'] |
| T16 | min-dwell blocks early switches (gap>=min_dwell+1); engine enforces it internally | PASS | observed_min_gap=4 dwell_blocked=True |
| T17 | strict-> margins (equal gain does NOT switch), LOW-confidence fallback holds current waveform and flags fallback | PASS | tie=True at_margin=True above=True low_fallback=True |
| T18 | runtime payload sizing now per-frame channel-derived; bit-identical A-D execution proves equivalence for these runs (see T6) | PASS |  |
| T19 | selection used only E-L (+M-R robustness); final A-D evaluated strictly after the config was frozen | PASS | no_AD_reference_in_stages_1-3=True config_before_eval=True |
| T20 | section-19 verdict matches raw data; P3 kept as preferred when P4 does not improve on it | PASS | dACS=-0.00441 action='PHASE 3 REMAINS THE PREFERRED BASELINE (sect…' |

## Notes

- Tests marked PASS were verified non-vacuously: each asserts a property that fails if the corresponding component regresses (checksums, exact replay equality, strict-inequality margins, tertile recomputation, dwell arithmetic, honesty consistency).
- Latency_ms is wall-clock detector time; cross-run ACS differences are dominated by bit-exact BER/TP/CQI (see analysis report latency-noise quantification).
- The Phase-4 policy did NOT beat Phase 3 on the untouched final scenarios; per the pre-registered improvement criteria, Phase 3 remains the preferred configuration.
