# Metric regressors v2 - training report

Data: 1158 rows / 579 conditions (Phase-2 paired dataset, no synthetic rows).
Split: train/val/test by condition (unseen-axis test).

| target | model | val R2 | test R2 | test MAE | test RMSE |
|---|---|---|---|---|---|
| Log10BER | RandomForest | 0.920 | 0.755 | 0.6704 | 1.887 |
| Throughput | RandomForest | 0.851 | 0.810 | 8.18e+04 | 1.879e+05 |
| CQI | RandomForest | 0.983 | 0.940 | 0.811 | 1.08 |
| ACS | RandomForest | 0.951 | 0.884 | 0.05431 | 0.1016 |
| PER | RandomForest | 0.914 | 0.842 | 0.06828 | 0.1496 |
| SE | RandomForest | 0.853 | 0.809 | 0.1712 | 0.3923 |
