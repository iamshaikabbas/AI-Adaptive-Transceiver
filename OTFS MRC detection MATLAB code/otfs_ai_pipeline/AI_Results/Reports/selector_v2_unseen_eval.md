# Selector v2 - evaluation on UNSEEN-axis test conditions

Test conditions: 246 (decisive 165, ties 81); accuracy on decisive: **94.5%**.

## Confusion matrix (rows=oracle, cols=predicted)

pred           ODDM  OTFS
best_waveform            
ODDM              2     6
OTFS              3   154

## Regret vs oracle

- mean |dB| BER regret: 4.527e-03
- p90 |dB| BER regret: 1.380e-02
- max  |dB| BER regret: 6.337e-02
- mean ACS regret: 0.0073
- frac conditions with >10% relative BER regret: 17.1% (relative values blow up at the BER floor where both waveforms are error-free; absolute deltas above are the honest operational number)

## Confidence calibration

 cbucket     n  accuracy
0.5-0.75   6.0  0.500000
0.75-0.9  10.0  0.600000
   >=0.9 149.0  0.986577

## Behaviour inside tie regions

predictions: {'OTFS': 73, 'ODDM': 8}

## Tie-tolerance sensitivity (ANALYSIS ONLY - training kept strict 10%)

NOTE: this table re-labels with a BER-only oracle (best_by_BER plus a
single relative-gap tie rule). Primary training labels use the stricter
dual rule (ACS objective, |dACS| or rel-BER ties), so counts differ.

 tol  decisive  ODDM_decisive  acc_on_decisive  mean_abs_regret
0.05       186             59            0.704         0.005987
0.10       169             49            0.734         0.006590
0.25       139             34            0.777         0.005271
0.50       107             17            0.869         0.001146
