# Phase 4 model studies

## STUDY A: zero-BER handling

**Zero-BER fraction by modulation**

```
                mean  sum  count
modulation                      
4           0.188172  105    558
16          0.021569   11    510
64          0.000000    0     90
```

**Zero-BER fraction by SNR band**

```
snr_band
(-30, 0]    0.000000
(0, 5]      0.000000
(5, 10]     0.000000
(10, 15]    0.071429
(15, 20]    0.299020
(20, 40]    0.597222
```

**Zero-BER fraction by speed band**

```
spd_band
(0, 10]       0.166667
(10, 60]      0.113475
(60, 140]     0.100000
(140, 360]    0.087500
```

Overall zero-BER fraction: **0.100**

### v2-style single log10(BER-clipped) regressor (test)
- overall MAE 0.667 decades
- MAE on zero-BER rows 3.384 (68 rows)
- MAE on positive-BER rows 0.231 (424 rows)

### Two-part model (P(BER=0) classifier x positive-magnitude regressor), threshold 0.5 (test)
- overall MAE 0.695 decades
- zero-row MAE 3.454, positive-row MAE 0.253
- zero/nonzero confusion: {'true_zero_pred_zero': 42, 'true_zero_pred_pos': 26, 'true_pos_pred_zero': 2, 'true_pos_pred_pos': 422}

**Decision (documented):** the two-part model fixes the dominant zero/nonzero confusion but only by hard-thresholding at 12 decades below the floor; its positive-row accuracy equals the single model's. Since runtime decisions key off ACS (not BER) and BER only enters via the BER-objective mode and reporting, we adopt the two-part model ONLY if it clearly wins; otherwise keep v2 clipping at 1e-12 unchanged.


## STUDY B: RF estimator disagreement as uncertainty

**Log10BER**: Spearman(spread, abs err) = 0.766 (p=6.0e-96); mean |err| by spread decile:

```
(-0.001, 0.0104]    0.023930
(0.0104, 0.0174]    0.039468
(0.0174, 0.027]     0.092463
(0.027, 0.0387]     0.115079
(0.0387, 0.0654]    0.152963
(0.0654, 0.105]     0.225593
(0.105, 0.211]      0.486056
(0.211, 0.788]      1.328560
(0.788, 1.994]      1.432464
(1.994, 4.46]       2.740634
```

**ACS**: Spearman(spread, abs err) = 0.743 (p=1.5e-87); mean |err| by spread decile:

```
(-0.0005909999999999999, 0.00173]    0.003403
(0.00173, 0.00248]                   0.006268
(0.00248, 0.00346]                   0.009862
(0.00346, 0.0051]                    0.018977
(0.0051, 0.00687]                    0.029018
(0.00687, 0.0138]                    0.035490
(0.0138, 0.0407]                     0.067057
(0.0407, 0.0731]                     0.108503
(0.0731, 0.106]                      0.114793
(0.106, 0.206]                       0.148051
```


## Decision-order check (ACS, test conditions)

(paired OTFS/ODDM actuals exist in dataset; engine uses predicted ACS ordering)
