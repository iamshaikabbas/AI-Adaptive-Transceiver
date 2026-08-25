# Phase 4 -- final analysis

## 1. Final evaluation on untouched scenarios A-D (section 18)

Fairness evidence: seed/payload/channel checksums of the P4 run equal the frozen baseline frame-by-frame: {'seed_match': True, 'payload_match': True, 'channel_match': True}

Measurement-noise caveat: Latency_ms is wall-clock detector time and varies between processes. Effect on this comparison:```json
{
 "mean_latency_ms": {
  "fixed_otfs": 31.601159999999997,
  "fixed_oddm": 78.56494083333334,
  "AI_phase3": 35.84597833333334,
  "AI_phase4": 34.84719583333334,
  "oracle": 36.04538124999999
 },
 "frames_with_oracle_flip": 4,
 "max_abs_dACS_on_flips": 0.015931540249190967,
 "spearman_abs_dACS_vs_abs_dLat": 0.8126338998940953
}
```
Waveform choices are bit-identical; the small agreement delta comes only from these near-tie oracle flips.

```
  strategy  mean_ACS  mean_BER      mean_TP  mean_CQI  switches  agreement  acs_regret_mean  abs_ber_regret
fixed_otfs   0.47782   0.05713 296250.00000  10.86250         0    0.88750          0.01632         0.00604
fixed_oddm   0.45167   0.07995 303157.89474  10.17500         0    0.11250          0.04246         0.02885
 AI_phase3   0.48071   0.05723 303654.97076  10.83750        10    0.82500          0.01342         0.00614
 AI_phase4   0.47630   0.05713 296250.00000  10.86250         0    0.87917          0.01618         0.00604
    oracle   0.49413   0.05465 318698.83041  11.01667         0    1.00000              NaN         0.00356
```

**Section 19 criteria verdict:**

```json
{
 "P4_beats_fixed_OTFS_on_ACS": false,
 "P4_beats_fixed_ODDM_on_ACS": true,
 "P4_beats_P3_on_ACS": false,
 "P4_vs_P3_dACS": -0.004413248150734295,
 "P4_vs_P3_agreement": 0.054166666666666696,
 "action": "PHASE 3 REMAINS THE PREFERRED BASELINE (section 19 honesty rule); the P4 policy is reported as a conservatism/robustness variant, not an improvement."
}
```


## 2. Prediction accuracy, all collected frames E-R (section 20)

```
waveform metric   n         MAE        RMSE     R2
    OTFS    BER 336      0.0419      0.0660 0.4563
    OTFS     TP 336 213186.7920 344219.9233 0.2856
    OTFS    CQI 336      2.3656      3.0667 0.4886
    OTFS    ACS 336      0.1687      0.2511 0.4475
    ODDM    BER 336      0.0414      0.0681 0.6424
    ODDM     TP 336 207336.1514 338367.0325 0.2339
    ODDM    CQI 336      2.4353      3.1953 0.4180
    ODDM    ACS 336      0.1760      0.2595 0.3467
```

(BER floor note: 89/336 frames contain at least one exactly-zero measured BER; predictions are clipped at log10(1e-12) by design -- documented, never fabricated.)


## 3. Order-accuracy breakdowns (section 21)

```
          group         value  order_acc   n
    environment HighSpeedRail      0.798  84
    environment       Highway      0.889  18
    environment    Pedestrian      1.000  44
    environment         Urban      0.747 166
    environment     UrbanFast      1.000  24
channel_profile           EPA      1.000  44
channel_profile           ETU      1.000  24
channel_profile           EVA      0.772 268
        snr_bin        <=10dB      0.699 166
        snr_bin       10-15dB      0.904 114
        snr_bin         >15dB      1.000  56
      speed_bin       <30km/h      0.779 131
      speed_bin    30-120km/h      0.876 121
      speed_bin      >120km/h      0.798  84
```


## 4. Robustness on difficult scenarios M-R (section 13)

Policy comparison over M-R (identical channels; P3 via exact offline replay, P4 via its live tagged run):

```
   policy  mean_ACS  mean_BER  switches  agreement  acs_regret_mean  bad_switches
P3_replay    0.5024    0.0479         2     0.7431           0.0135             2
P4_replay    0.5112    0.0490         0     0.9236           0.0047             0
```

Transition response (delays in frames; degradation = summed ACS regret until first switch onto the new regime):

```
   policy scenario  frame    kind  det_delay  switch_delay  degraded_ACS_sum  recovery           note
  P4_live        M      7     env        NaN           NaN               NaN       NaN already-on-new
  P4_live        M     13     env        NaN           NaN               NaN       NaN already-on-new
  P4_live        M     19     env        NaN           NaN              0.01       NaN            NaN
  P4_live        N      7     env        NaN           NaN               NaN       NaN already-on-new
  P4_live        N     13     env        NaN           NaN               NaN       NaN already-on-new
  P4_live        N     19     env        NaN           NaN               NaN       NaN already-on-new
  P4_live        O      6     snr        NaN           NaN               NaN       NaN already-on-new
  P4_live        O     11     snr        NaN           NaN               NaN       NaN already-on-new
  P4_live        O     16     snr        NaN           NaN               NaN       NaN already-on-new
  P4_live        O     21     snr        NaN           NaN               NaN       NaN already-on-new
  P4_live        P      6     snr        NaN           NaN               NaN       NaN already-on-new
  P4_live        P     11     snr        NaN           NaN               NaN       NaN already-on-new
  P4_live        P     16     snr        NaN           NaN               NaN       NaN already-on-new
  P4_live        P     21     snr        NaN           NaN               NaN       NaN already-on-new
  P4_live        R      9 profile        NaN           NaN               NaN       NaN already-on-new
  P4_live        R     17 profile        NaN           NaN               NaN       NaN already-on-new
P3_replay        M      7     env        NaN           NaN               NaN       NaN already-on-new
P3_replay        M     13     env        NaN           NaN               NaN       NaN already-on-new
P3_replay        M     19     env        NaN           NaN              0.01       NaN            NaN
P3_replay        N      7     env        NaN           NaN               NaN       NaN already-on-new
P3_replay        N     13     env        NaN           NaN               NaN       NaN already-on-new
P3_replay        N     19     env        NaN           NaN               NaN       NaN already-on-new
P3_replay        O      6     snr        NaN           NaN               NaN       NaN already-on-new
P3_replay        O     11     snr        NaN           NaN               NaN       NaN already-on-new
P3_replay        O     16     snr       0.00           NaN              0.11       NaN            NaN
P3_replay        O     21     snr       0.00           NaN              0.04       NaN            NaN
P3_replay        P      6     snr        NaN           NaN               NaN       NaN already-on-new
P3_replay        P     11     snr        NaN           NaN               NaN       NaN already-on-new
P3_replay        P     16     snr       0.00           NaN              1.53       NaN            NaN
P3_replay        P     21     snr       0.00           NaN              0.74       NaN            NaN
P3_replay        R      9 profile        NaN           NaN               NaN       NaN already-on-new
P3_replay        R     17 profile        NaN           NaN               NaN       NaN already-on-new
```

Mean response by policy:

```
           det_delay  switch_delay  degraded_ACS_sum  recovery
policy                                                        
P3_replay       0.00           NaN              0.49       NaN
P4_live          NaN           NaN              0.01       NaN
```

Offline-replay vs live-execution identity check on M-R: decision mismatches=0/144, band mismatches=0/144 (0 expected; nonzero would invalidate the replay method).


## 5. Oscillation diagnostics (section 14)

Alternating switch pairs within <=3 frames:```json
{"P3_replay_difficult": 0, "P4_replay_difficult": 0, "P4_live_difficult": 0, "P3_baseline_AD": 0}
```

Confidence-band usage:

```json
{
 "AD_P4_live": {
  "HIGH": 94,
  "MEDIUM": 88,
  "LOW": 58
 },
 "MR_P4_live": {
  "MEDIUM": 72,
  "HIGH": 41,
  "LOW": 31
 },
 "EH_replay": {
  "LOW": 39,
  "HIGH": 38,
  "MEDIUM": 19
 },
 "IL_replay": {
  "HIGH": 64,
  "LOW": 21,
  "MEDIUM": 11
 }
}
```
