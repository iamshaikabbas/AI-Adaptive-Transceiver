# PHASE 3 VALIDATION RECORD

Date: 2026-08-23
Scope: closed-loop AI adaptive transceiver — decision engine v2, metric
regressors v2, digital-twin runtime, scenario runs A–D, traces, analyses.

## Test matrix (spec section 20)

| # | What is proven | Where | Result |
|---|----------------|-------|--------|
| T1 | Python AI inference round-trip works from MATLAB (`ai_engine_v2.py --infile/--out`) | `phase3_tests.m` | PASS |
| T2 | Engine returns a valid waveform (OTFS/ODDM) + detector | `phase3_tests.m` | PASS (OTFS/MRC) |
| T3 | Recommended waveform actually executes through the twin (`twin_run_frame`) and yields finite BER | `phase3_tests.m` | PASS (BER=0.0292 @ EVA/150/10dB QPSK) |
| T4/T5 | Fixed-OTFS / fixed-ODDM baselines: exactly one executed row per frame (240 each), correct waveform every frame, zero sim errors | `phase3_validation_tests.py` | PASS |
| T6 | Oracle trace: 240 rows; oracle waveform = argmax actual ACS on ≥99% of frames | `phase3_validation_tests.py` | PASS |
| T7 | AI-adaptive trace: 240 rows, all frames executed, zero sim errors | `phase3_validation_tests.py` | PASS |
| T8 | One row per (scenario, frame); scenarios A–D × frames 1–60 complete, no duplicates/gaps | `phase3_validation_tests.py` | PASS |
| T9 | No NaN in BER/SER/PER/Throughput/CQI/ACS on any error-free row of any strategy | `phase3_validation_tests.py` | PASS (0 NaN cells) |
| T10 | **Fairness:** per-frame noise seed, payload checksum, channel checksum identical across all four strategies (paired evaluation) | `phase3_validation_tests.py` | PASS (240/240 frames) |
| T11 | AI predictions AND actual metrics recorded for both waveforms + oracle fields present | `phase3_validation_tests.py` | PASS |
| T12 | Regret columns recompute independently from actual/oracle columns to machine precision | `phase3_validation_tests.py` | PASS |
| T13a–h | Decision policy unit tests with injected predictions: small margin keeps; big margin switches; min-dwell blocks; confidence gate blocks/passes when enabled; BER objective keeps lower-BER current; BER objective switches to lower-BER alt | `phase3_validation_tests.py` | ALL PASS |

## Success criteria (spec section 24)

| Criterion | Target | Measured |
|---|---|---|
| Closed loop executes selected waveform | yes, every frame | 240/240 frames, 0 fallbacks, 0 errors |
| Genuine switching driven by predictions only | no fabricated switches | 10 real switches (A@1,5,16,21 D@1,5,47,51,56,60), all with predicted ACS gain +4…10% rel; dwell ≥ 3 respected (min gap 4) |
| Fair paired comparison | identical chan/payload/seeds per frame across strategies | proven by checksums (T10) |
| AI ≥ fixed baselines overall | honest report either way | AI mean ACS 0.4807 > fixed OTFS 0.4778 > fixed ODDM 0.4517; throughput 303.7 kbps > 296.3 kbps (OTFS) / 303.2 kbps (ODDM) |
| Regret vs oracle quantified | reported | mean abs BER regret 6.1e-3, mean ACS regret 0.0134 (max BER regret 0.126) |
| Predictions vs actual audited | reported | ACS MAE ≈ 0.157; log10-BER MAE 2.1–2.5 decades (dominated by BER=0 frames clipped at 1e-12 — bursty single-frame BER, see limitations); ACS-order flips 31/240 (12.9%) |

## Issues found & fixed during validation

1. **min_confidence default made switching impossible** — normalized-margin
   confidence can only reach high values when the alternative objective is
   ~1.5× better, so the initial 0.5 default blocked all 240 switches.
   Fixed: margins (+rel OR abs) + dwell are the primary anti-chatter gates;
   `min_confidence` kept as an optional gate, default 0.0, documented in
   `adaptive_config_v2.json`. Traces regenerated after the fix.
2. `pt.modulation` passed as int64 into `twin_run_frame` broke the sim
   ("Invalid data type") — simulation entry points now keep modulation as
   double; integer casting happens only in trace rows.
3. Validation harness initially parsed MATLAB logicals written as 0/1 as
   strings → vacuous passes. `bcol()` now handles both encodings; all
   boolean checks re-run non-vacuously.

## Limitations (honest)

- Single-frame BER is bursty (often exactly 0), so per-frame log10-BER
  prediction error is inflated by clipping artifacts; ACS/CQI/throughput
  regressions are the reliable signals.
- The selector-v2 ODDM recall remains low (2/8 unseen); the runtime relies
  on direct metric regression rather than the classifier for decisions.
- Policy thresholds inherited from phase 1; not tuned or claimed optimal.
- Wall-clock decoupled from simulated time (~12 s/frame dominated by the
  Python subprocess spawn).
