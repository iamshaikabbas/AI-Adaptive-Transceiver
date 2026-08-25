# Phase 4 offline policy sweep

## Stage 1: margin x dwell sweep (confidence off) - TUNING set E-H, 96 frames

```
 margin  dwell  mean_ACS  mean_BER  switches  agreement  acs_regret_mean  bad_switches
 0.0000      1    0.4011    0.0551         1     0.7083           0.0190             1
 0.0000      3    0.4011    0.0551         1     0.7083           0.0190             1
 0.0000      5    0.4011    0.0551         1     0.7083           0.0190             1
 0.0000      8    0.4011    0.0551         1     0.7083           0.0190             1
 0.0100      1    0.4011    0.0551         1     0.7083           0.0190             1
 0.0100      3    0.4011    0.0551         1     0.7083           0.0190             1
 0.0100      5    0.4011    0.0551         1     0.7083           0.0190             1
 0.0100      8    0.4011    0.0551         1     0.7083           0.0190             1
 0.0200      1    0.4011    0.0551         1     0.7083           0.0190             1
 0.0200      3    0.4011    0.0551         1     0.7083           0.0190             1
 0.0200      5    0.4011    0.0551         1     0.7083           0.0190             1
 0.0200      8    0.4011    0.0551         1     0.7083           0.0190             1
 0.0300      1    0.4011    0.0551         1     0.7083           0.0190             1
 0.0300      3    0.4011    0.0551         1     0.7083           0.0190             1
 0.0300      5    0.4011    0.0551         1     0.7083           0.0190             1
 0.0300      8    0.4011    0.0551         1     0.7083           0.0190             1
 0.0500      1    0.4011    0.0551         1     0.7083           0.0190             1
 0.0500      3    0.4011    0.0551         1     0.7083           0.0190             1
 0.0500      5    0.4011    0.0551         1     0.7083           0.0190             1
 0.0500      8    0.4011    0.0551         1     0.7083           0.0190             1
 0.0700      1    0.4011    0.0551         1     0.7083           0.0190             1
 0.0700      3    0.4011    0.0551         1     0.7083           0.0190             1
 0.0700      5    0.4011    0.0551         1     0.7083           0.0190             1
 0.0700      8    0.4011    0.0551         1     0.7083           0.0190             1
 0.1000      1    0.4130    0.0547         0     0.9062           0.0072             0
 0.1000      3    0.4130    0.0547         0     0.9062           0.0072             0
 0.1000      5    0.4130    0.0547         0     0.9062           0.0072             0
 0.1000      8    0.4130    0.0547         0     0.9062           0.0072             0
```

**Selection objective (documented):** primary = highest mean actual ACS; ties within 1e-3 broken by lower ACS regret, then fewer switches. Communication performance first, accuracy second.

Top-5 by objective:

```
 margin  dwell  mean_ACS  mean_BER  switches  agreement  acs_regret_mean  bad_switches
 0.1000      1    0.4130    0.0547         0     0.9062           0.0072             0
 0.1000      3    0.4130    0.0547         0     0.9062           0.0072             0
 0.1000      5    0.4130    0.0547         0     0.9062           0.0072             0
 0.1000      8    0.4130    0.0547         0     0.9062           0.0072             0
 0.0000      1    0.4011    0.0551         1     0.7083           0.0190             1
```

## Stage 2: uncertainty-aware confidence banding (TUNING set)

Agreement-score tertiles on tuning frames: tau_low=0.305, tau_high=0.585 (empirical quantiles, documented, not per-metric tuned)

```
 margin  dwell conf  mean_ACS  mean_BER  switches  agreement  acs_regret_mean  bad_switches
 0.1000      1 band    0.4130    0.0547         0     0.9062           0.0072             0
 0.1000      1 none    0.4130    0.0547         0     0.9062           0.0072             0
 0.1000      3 band    0.4130    0.0547         0     0.9062           0.0072             0
 0.1000      3 none    0.4130    0.0547         0     0.9062           0.0072             0
 0.1000      5 band    0.4130    0.0547         0     0.9062           0.0072             0
 0.1000      5 none    0.4130    0.0547         0     0.9062           0.0072             0
 0.1000      8 band    0.4130    0.0547         0     0.9062           0.0072             0
 0.1000      8 none    0.4130    0.0547         0     0.9062           0.0072             0
 0.0000      1 band    0.4130    0.0547         0     0.9062           0.0072             0
 0.0000      1 none    0.4011    0.0551         1     0.7083           0.0190             1
```


## Stage 3: candidate evaluation on HELD-OUT set I-L (96 frames, untouched so far)

```
 margin  dwell conf  mean_ACS  mean_BER     mean_TP  switches  agreement  order_acc  acs_regret_mean  bad_switches
 0.1000      1 none    0.2803    0.1122 103125.0000         0     0.9479     0.7812           0.0007             0
 0.1000      3 none    0.2803    0.1122 103125.0000         0     0.9479     0.7812           0.0007             0
 0.1000      5 none    0.2803    0.1122 103125.0000         0     0.9479     0.7812           0.0007             0
 0.1000      8 none    0.2803    0.1122 103125.0000         0     0.9479     0.7812           0.0007             0
 0.0000      1 none    0.2753    0.1129 103051.9006         1     0.7500     0.7812           0.0057             1
 0.1000      1 band    0.2803    0.1122 103125.0000         0     0.9479     0.7812           0.0007             0
 0.1000      1 none    0.2803    0.1122 103125.0000         0     0.9479     0.7812           0.0007             0
 0.1000      3 band    0.2803    0.1122 103125.0000         0     0.9479     0.7812           0.0007             0
 0.1000      3 none    0.2803    0.1122 103125.0000         0     0.9479     0.7812           0.0007             0
 0.1000      5 band    0.2803    0.1122 103125.0000         0     0.9479     0.7812           0.0007             0
 0.1000      5 none    0.2803    0.1122 103125.0000         0     0.9479     0.7812           0.0007             0
 0.1000      8 band    0.2803    0.1122 103125.0000         0     0.9479     0.7812           0.0007             0
 0.1000      8 none    0.2803    0.1122 103125.0000         0     0.9479     0.7812           0.0007             0
 0.0000      1 band    0.2803    0.1122 103125.0000         0     0.9479     0.7812           0.0007             0
 0.0000      1 none    0.2753    0.1129 103051.9006         1     0.7500     0.7812           0.0057             1
 0.0100      3 none    0.2753    0.1129 103051.9006         1     0.7500     0.7812           0.0057             1
```


**SELECTED POLICY (held-out):** margin=0.1, dwell=1, confidence=none


## Stage 4: temporal-feature feasibility (sec 10/11)

Lag-1 autocorrelation of per-frame ACS prediction error by scenario:

```
scenario
E   -0.116361
F   -0.094691
G   -0.156576
H    0.056112
I    0.570009
J   -0.122219
K   -0.178643
L    0.153423
```

Median |autocorr| = 0.138

**Interpretation:** frame-only features already carry the full condition state (speed/SNR/profile are measured, not estimated); if residual lag-1 autocorrelation is weak there is little temporal signal for a feature-based model to add. A temporal model is adopted ONLY on clear evidence.
