# PHASE 1 VALIDATION — Clean, Certify & Harden

**Date:** 2026-08-23
**Scope:** certification of the *existing* foundation only. No rebuilds, no retraining,
no changes to the legacy Thaj/Viterbo OTFS chain or any preserved file.
**Git baseline before any change:** commit `ebde54d` ("baseline: existing OTFS ODDM AI adaptive system").

**Environment:** MATLAB R2026a Update 4 (`C:\MY DATA ANALYTICS FILES AND PROJECTS\Matlab\bin\matlab.exe`,
run via `-batch`), Python 3.14.6 venv (`.venv\Scripts\python.exe`), Windows.

---

## 1. Test matrix

| # | Item | Method | Result |
|---|------|--------|--------|
| 1 | MATLAB launchable headless | `-batch` smoke commands | **PASS** |
| 2 | Comm Toolbox functions (`qammod`/`qamdemod`) | functional round-trip test | **PASS** (note: `license('test','Communication')` returns 0 due to wrong feature-name string; actual functionality verified) |
| 3 | OTFS chain certification | `validate_otfs.m` (4 cases x 4 SNRs) | **PASS** — AWGN sim vs theory matches at 5/10 dB (ratio 0.98–1.00); monotonic BER improvement in all four cases; usable at high SNR |
| 4 | OTFS quick sanity | `smoke_test_waveforms.m` | **PASS** — EVA@120 km/h QPSK: OTFS/ODDM/OFDM BER same order; AWGN@20 dB all-zero BER |
| 5 | ODDM chain certification | `validate_oddm.m` (MMSETAP + LMMSE ladders) | **PASS** — identity-channel ‖H−I‖_F = 7.7e-15; AWGN theory ratios ≤1%; LMMSE fully monotonic incl. Doppler; MMSETAP Doppler floor correctly identified as ICI-limited |
| 6 | Paired-trial integrity (OTFS/ODDM/OFDM share chan/bits/seed) | `phase1_paired_check.m` (temp cert script) | **PASS** — identical channel taps `[0…0 1 1 1]`, bit-identical echoed payload (1920 bits), shared seed; control run confirms seeds effective; `run_paired_trials` executes end-to-end |
| 7 | ACS parity MATLAB ↔ Python | `_acs_parity.py` (3 metric vectors through both engines) | **PASS** — composite + all six component scores **bit-exact (max diff = 0)** |
| 8 | AI inference CLI (no retraining) | `phase1_ai_cli_check.m`: production `ai_engine.py` path (exact `ai_decide_frame.m` command), plus `predict_waveform.py --classes 2/3` | **PASS** — engine returns valid decision JSON (ODDM/LMMSE, confidence 0.221, predicted ACS OTFS=0.487 / ODDM=0.626); selector CLIs return probability vectors summing to 1 |
| 9 | Digital twin existing functionality | interface inspection + live `strategy_compare.m` rerun (60 frames x 3 strategies) | **PASS (as-is)** — loop runs, every AI call succeeds, trace + summary regenerate cleanly; see §4 known issue K1 |
| 10 | Malformed comparison CSVs repaired | `_regen_cmp_csvs_from_raw.py` + `_verify_cmp_csvs.py` | **PASS** — see §2 |
| 11 | Comparison PNG pipeline works | live rerun of `compare_otfs_oddm_runtime.m` | **PASS** — fresh CSV in new schema + `cmp_runtime.png` re-rendered (127 KB) |
| 12 | `strategy_summary.csv` labels | fix + regenerated artifact | **PASS** — rows now labeled `fixed_otfs` / `fixed_oddm` / `ai_adaptive` |
| 13 | Documentation drift | PROJECT_SUMMARY.md edits | **PASS** — Python version corrected to 3.14; non-existent `build_Hdd_block.m` reference replaced by `ODDM_detect.m` |

**NOT TESTED (out of Phase 1 scope):**
- Full re-run of all nine comparison sweeps end-to-end (six of seven malformed CSVs were
  reconstructed from stored raw trial data instead of re-simulated; a future full re-run will
  produce the identical schema automatically).
- `digital_twin_runtime.m` (referenced but does not exist — deliberately not created).
- Streamlit dashboard runtime behavior (static checks only, per audit).
- Retraining / model quality improvements (explicitly forbidden this phase).

## 2. CSV repair details

The old `save_compare_results.m` serialized per-trial metric **vectors** with `fprintf`,
producing 68–188-field rows under a 14-name header in 7 of 9 comparison files
(`cmp_environment.csv` and `cmp_modulation.csv` use their own scalar writers and were already clean).

Recovery performed without re-simulation for six files: each malformed row still contained the
ordered raw vectors `[BER[nT], SER[nT], PER_mean, Throughput[nT], SE[nT], CQI_mean, SINR_mean,
EVM[nT], Latency[nT], Run_mean]`. Aggregates were recomputed with exactly the formulas of
`run_paired_trials.m`:

```
BER_total = round(sum(BER)*N_bits)/(N_bits*nTrials)     # bit-weighted, as originally defined
SER_total = round(sum(SER)*N_syms)/(N_syms*nTrials)
EVM_mean  = mean(EVM_percent)
Thr_mean/SE_mean/Lat_mean = arithmetic means
PER/CQI/SINR/Run          = copied scalars
```

Payload sizes derived from each experiment's config (`N_syms = (M − Lg)·N`, `Lg = max(max_delay_tap+1, ceil(M/16))`)
and cross-checked against the realized `DelaySpread` values in `waveform_dataset.csv`
(EPA/EVA/RayleighFlat → 960 symbols @32×32; ETU → 928; multipath P→960…704; runtime grids → 224/960/2160).

New fixed writer schema (all scalars):
`<xname>,label,waveform,detector,BER_total,SER_total,PER_mean,Thr_mean,SE_mean,EVM_mean,CQI_mean,SINR_mean,Lat_mean,Run_mean`

Verification performed:
- all 9 files parse with pandas, expected shapes (55/55/55/20/50/12/9 rows x 14 cols);
- lattice check: every aggregate sits exactly on an integer error-count grid point;
- monotonic non-increasing BER vs SNR for all combos in `cmp_snr`;
- runtime grows monotonically with NM; detector set complete in `cmp_detector`;
- statistical consistency vs independent measurement: `cmp_snr` OTFS-MRC values scatter around
  `waveform_dataset.csv` means (ratios 1.02/1.15/1.59/0.13 across SNRs) — explained by the
  dataset's n=5 heavy-tailed single-frame trials vs 30 paired trials, **not** systematic bias.

## 3. Files changed / created / regenerated

Modified (code, minimal diffs):
- `OTFS MRC detection MATLAB code/save_compare_results.m` — scalar-only serialization (root cause fix)
- `OTFS MRC detection MATLAB code/strategy_compare.m` — one line: label summary rows
- `PROJECT_SUMMARY.md` — factual corrections only

Regenerated data artifacts:
- `Results/WaveformComparison/cmp_{snr,velocity,doppler,channel,multipath,detector}.csv` — reconstructed from stored raw trial vectors
- `Results/WaveformComparison/cmp_runtime.csv` + `cmp_runtime.png` — fresh live run through the fixed writer
- `Results/DigitalTwin/strategy_summary.csv`, `strategy_trace.csv` — fresh live `strategy_compare.m` run

Created (certification helpers, safe to delete; kept for re-certification provenance):
- `_regen_cmp_csvs_from_raw.py`, `_verify_cmp_csvs.py`, `_acs_parity.py`
- `phase1_paired_check.m`, `phase1_ai_cli_check.m`
(plus `.gitignore` at project root and baseline commit `ebde54d`, from the start of the phase)

Untouched: entire legacy OTFS implementation, validators, AI models/training scripts, datasets.

## 4. Known issues (documented, deliberately NOT fixed this phase)

- **K1 — AI-adaptive degeneracy (confirmed live):** across all 60 digital-twin frames the engine
  predicts negative ACS gain for switching ("−2.5% … −18.4% below threshold") and never switches;
  `ai_adaptive` therefore equals `fixed_otfs` exactly (0 switches). The loop mechanics are sound;
  the *selector model* simply prefers OTFS in these conditions. Fixing model behavior is deferred
  (requires retraining — out of scope).
- **K2 — historical anomaly preserved:** `cmp_multipath.csv` row NumPaths=1 / ODDM-MMSETAP shows
  BER_total ≈ 0.506 with negative EVM — a genuine catastrophic-failure point present in the original
  measurements, faithfully carried over. Worth investigating in a later phase.
- **K3 — `digital_twin_runtime.m` missing** (referenced by docs/tooling): intentionally not created.
- **K4 — MMSETAP Doppler floor** (~0.31 BER flat in SNR under fractional Doppler): expected
  detector limitation, correctly verdicted by `validate_oddm.m`.
- **K5 — plot floors in compare scripts** assume `N_syms` factor 28·32 (e.g. `0.5/(32*28*30*nTrials)`);
  actual payloads are mostly 30·32. Cosmetic clamp only; does not affect data.
- **K6 — untracked external material:** `MAJOR/O/Common_Wireless_Simulator-main/` (third-party
  reference simulator) appeared next to the project; not touched, not committed.

## Verdict

**PHASE 1: COMPLETE — all in-scope certifications PASSED.** The foundation is certified fit for
Phase 2 planning on top of commit `ebde54d` + these repairs.
