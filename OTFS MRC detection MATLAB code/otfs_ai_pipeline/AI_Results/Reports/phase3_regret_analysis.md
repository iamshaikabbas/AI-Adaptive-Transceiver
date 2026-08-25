# Phase 3 - regret analysis (AI adaptive vs oracle)

Absolute BER difference is the primary operational measure;
relative values are recorded but meaningless at the BER floor.

| metric | value |
|---|---|
| mean BER regret (abs) | 0.00614005 |
| p90 BER regret (abs) | 0.0227083 |
| max BER regret (abs) | 0.125521 |
| mean ACS regret | 0.0134229 |
| p90 ACS regret | 0.0196707 |
| frac frames >10% rel-BER regret | 0.2375 |

## Fixed baselines' regret (reference)

| strategy | mean BER regret | max BER regret | mean ACS regret |
|---|---|---|---|
| fixed_otfs | 6.040e-03 | 1.255e-01 | 0.0163 |
| fixed_oddm | 2.885e-02 | 1.882e-01 | 0.0425 |
