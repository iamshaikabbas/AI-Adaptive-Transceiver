# Phase 5 — Digital Twin & Evaluation Engine Architecture

Consolidates Phases 1–4 into one canonical, reproducible pipeline. This
document describes what exists, why it is shaped this way, and where the
honest limits are. Companion evidence: `PHASE5_VALIDATION.md`.

## 1. Purpose and scope (honesty statement)

This is a **software Digital Twin**: MATLAB link/channel/waveform simulation
plus learned Python decision policies exchanging JSON per frame. There is no
hardware, SDR, RF chain, or over-the-air component anywhere in this project,
and none of the results should be read as hardware measurements. All latency
values reported are **measured software execution times** of the simulation
chain itself (`detector_time_ms`, `wall_clock_ms`); the modeled-latency slot
(`latency_ms_modeled`) is intentionally left NaN everywhere.

## 2. Layer map

```
run_system.m            dispatcher: help/validate/fast/full/experiment
  └─ run_experiment.m   canonical runner (per scenario, per strategy, per frame)
       ├─ dt_scenarios_lib.m     scenario resolution (letters, groups, custom)
       ├─ dt_state.m             canonical per-frame state (schema + seeds)
       ├─ dt_seeds.m             seed derivation contract
       ├─ dt_channel_for_frame.m rng(channel_seed) -> gen_channel_params_flex
       ├─ dt_payload_for_frame.m rng(payload_seed) -> bits (frozen sizing rule)
       ├─ dt_exec_waveform.m     run_otfs/run_oddm + metrics + ACS inputs
       ├─ dt_ai_decide.m         MATLAB <-> Python JSON exchange (+fallback)
       └─ dt_policy_config.m     THE policy->files map (phase3 | phase4)
Frozen backbone (unmodified): sim_default_config.m, gen_channel_params_flex.m,
run_otfs.m, run_oddm.m, compute_acs.m, apply_rx_impairments.m,
twin_default_detector.m, environment_profiles_v2.csv,
adaptive_config_v2/v4.json, otfs_ai_pipeline/ai_engine_v2.py, ai_engine_v3.py.
Legacy entry points (digital_twin_runtime.m, dt_scenarios*.m, strategy_compare.m,
ai_decide_frame.m, twin_run_frame.m, run_paired_trials.m) carry a header mark
and are superseded by the files above; they are kept only for provenance.
```

## 3. Reproducibility contract (seeds and state)

Master seed default `20260823` (`system_config.json`, overridable via
`run_experiment(...,'seed0',s)`). For frame `f` in a scenario with seed `s`:

| stream | seed | producer |
|---|---|---|
| payload bits | `s + f` → `randi` after frozen sizing `Lg=max(max_delay_tap+1,ceil(M/16))`, `N_syms=(M-Lg)*N` | `dt_seeds` / `dt_payload_for_frame` |
| channel params | `rng(s*10+f)` → `gen_channel_params_flex(cfg_f)` | `dt_channel_for_frame` |
| noise realization | passed as `noise_seed = 100000+f` into the frozen runtime | `dt_state` |

Everything downstream (channel taps, doppler, delays, payloads) is therefore a
pure function of `(scenario, frame, master_seed)`. Verified bit-exact against
the frozen Phase-3 runtime draw order (check C5).

`dt_state(pt,cfg,'frame',f,'scenario_id',id,'scenario_seed',s,...
'current_waveform',wf,'frames_since_switch',d)` builds the canonical state;
trailing name/value pairs let the runner set deployment fields *before* seed
derivation so ordering bugs cannot reappear.

## 4. Scenario library

`dt_scenarios_lib('resolve', X)` understands:
- letters `A`–`R`: `Results/DigitalTwin/scenario_<x>.json`
  (A–D baseline tiers, E–R exploration/difficult tiers; tier defaults to
  `final_eval` when absent from meta);
- groups: `'all'`, `'baseline'`, etc.;
- custom names: `custom_scenarios/<name>.json` or an explicit path.

Custom schema: `name`, `duration_frames`, then either a `constant` block or
`segments`/`points` lists (each point carries `environment`, `speed_kmph`,
`snr_db`, `modulation`, optional offsets). A transition plausibility check
rejects impossible jumps unless `meta.stress` opts out.

Difficult-tier structure: O/P = SNR staircase (20→0 and reverse), M/N =
environment corridor Pedestrian→Urban→Highway→HighSpeedRail (and reverse),
Q/R = channel-profile transitions. These exist to stress the switch logic,
never to tune against final A–D.

## 5. Frame execution pipeline

Per frame: state → channel → payload → **both** waveforms executed on the
*same realized channel/payload* (paired fairness, enforced by identical
`chan_checksum`/`payload_sum` across all four strategy traces) → metrics
(BER/SER/PER/TP/SE/CQI/recovery) → ACS inputs. Impairments
(frequency/phase/timing offsets) are applied through the frozen
`apply_rx_impairments` path only when nonzero. Timing columns:
- `wall_clock_ms`: outer tic/toc around the whole waveform execution;
- `detector_time_ms`: the detector's **internal** measurement
  (`res.Latency_ms`) — this is what `compute_acs` consumes, exactly as the
  legacy runtime did;
- `latency_ms_modeled`: always NaN (honesty placeholder).

ACS caps come from the frame itself: `tp_cap_bps = N_bits/frame_T`,
`se_cap = log2(mod)`; for ODDM `frame_T += L_cp/fs` with
`L_cp = max(max_delay_tap+1,2)`.

## 6. Four-strategy interface

Every experiment evaluates exactly these strategies over identical frames:

1. `fixed_otfs` — always OTFS;
2. `fixed_oddm` — always ODDM;
3. `ai_adaptive` — policy decision per frame (see §7);
4. `oracle` — picks `argmax(actual_ACS_OTFS, actual_ACS_ODDM)` with OTFS
   tie-break, using post-decision outcomes. Evaluation-only by construction.

Deployment mechanics (shared): dwell starts at `previous_waveform='OTFS'`,
`frames_since_switch=99`; a real switch resets the counter, otherwise it
increments; a fallback keeps the current waveform deployed and does **not**
reset dwell. Switch bookkeeping columns (`switched`, `switch_reason`,
`previous_waveform`, `decision_correct`) are recomputed-verified by tests.

## 7. AI interface and policies

`dt_policy_config(policy)` is the single mapping:

| policy | config | engine |
|---|---|---|
| `phase3` (canonical) | `adaptive_config_v2.json` | `ai_engine_v2.py` |
| `phase4` (experimental) | `adaptive_config_v4.json` | `ai_engine_v3.py` |

Anything else raises. Per AI frame, `dt_ai_decide` writes the feature state
JSON, invokes the venv python (repo `.venv\Scripts\python.exe`, else PATH),
reads back `{recommendation, confidence, predicted_metrics, uncertainty_*}`.
On ANY failure (missing python, bad JSON, crash) the fallback keeps the
currently deployed waveform and records `fallback_used=true`,
`ai_error=<reason>` — degradation, never divergence.

**Oracle-leakage guard:** the AI state contains only
`environment, speed_kmph, snr_db, doppler_hz, carrier_frequency_hz,
bandwidth_hz, channel_profile, delay_spread_taps, num_paths,
doppler_spread_hz, modulation, current_waveform, frames_since_switch`.
No oracle/outcome/regret field ever reaches decision time (static scan C15 +
artifact test T19).

Phase-4 remains the experimental branch; Phase-3 stays canonical per the
Phase-4 verdict (P4 ΔACS −0.0044 on untouched A–D).

## 8. Adaptive Communication Score

One definition, two mirrored implementations, one shared weight file
(`acs_weights.json`): MATLAB `compute_acs.m` and Python `otfs_ai_pipeline/acs.py`.
`ACS = w_ber·s_ber + w_tp·s_tp + w_se·s_se + w_cqi·s_cqi + w_lat·e^(-t/200)
+ w_rec·s_rec`, scores clamped to [0,1]. The objective used by the oracle and
all reporting is read from the policy config. Cross-checks: MATLAB-side C10
(exact to 9 decimals) and Python T10 (max err ~5e-15).

## 9. Output schema and layout

`Results/DigitalTwin/<scenario>/<strategy>_trace.csv` (one row per frame,
78 canonical columns), `<strategy>_summary.csv` (aggregates incl.
`mean_ACS`), `states.csv` (timeline, `t_sim_s=(frame-1)*1s`),
`run_manifest.json` (`frames_run`, `policy`, `mode`, seeds, generator note,
MATLAB version). Legacy→canonical column naming is documented inside the
trace header itself; the important renames are `Latency_ms→detector_time_ms`
(measured, detector-internal), plus new `tp_cap_bps`, `se_cap`,
`latency_ms_modeled`. Extra prediction columns
(`predicted_{OTFS,ODDM}_{TP,CQI}`, `uncertainty_ACS_*`, `doppler_scale`) ride
along for analysis; tests check the required superset, not exclusivity.

## 10. Modes

- `FAST`: first 12 frames of a scenario (~0.6–0.7 min/scenario).
- `FULL`: all frames (60 on A–D; ~12–13 min for all four scenarios).
- Custom scenarios run at their declared duration under either mode.

`run_system('experiment','scenarios',{'a'},'strategies',{'ai_adaptive'},...)`
forwards options; defaults come from `system_config.json`.

## 11. Validation entry points

- MATLAB: `phase5_checks_driver('fast'|'full'|'all')` → C1–C17, writes
  `phase5_check_results.json`. Current record: **17/17 PASSED**.
- Python: `python otfs_ai_pipeline/phase5_validation_tests.py` → T01–T20,
  regenerates `PHASE5_VALIDATION.md`. Current record: **20/20 PASSED**.

## 12. Reproducibility limitation: wall-clock in ACS (read this before comparing runs)

The ACS latency term uses measured detector time, which varies with machine
load. Everything deterministic (payload, channel, BER/SER/PER of fixed
deployments, predictions, switches) is bit-stable across sessions — proven by
bit-exact FULL A–D regression against the frozen baseline. What can differ
between sessions is the **oracle label on near-tie frames**, because
`w_lat·(e^(-t_otfs/200) − e^(-t_oddm/200))` can outweigh a metric tie. C17
therefore accepts label differences only inside a band derived from the run's
own measured time spread, `w_lat·(e^(-t_min/200) − e^(-t_max/200))`
(observed: band ≈0.038 vs max flip margin ≈0.017; every flipping frame had
identical deterministic components). This is a property of measuring real
software execution time, not of the pipeline; replacing it would require
either freezing timing (dishonest) or removing the latency term from ACS.

## 13. Known non-goals

No dashboards/graphs/hardware/SDR/RF/audio/webapp work is in scope. The AI
models themselves are frozen artifacts from earlier phases and are never
retrained here.
