# Phase 3 - strategy comparison (same scenario/seeds/channels)

             mean_BER  median_BER  mean_Throughput_bps   mean_CQI  mean_SpectralEfficiency_bps_per_Hz  mean_ACS  mean_Latency_ms  mean_PacketLoss  mean_RecoveryRate
strategy                                                                                                                                                            
fixed_otfs   0.057133    0.007292        296250.000000  10.862500                            0.617188  0.477817        31.601160         0.679167           0.320833
fixed_oddm   0.079947    0.014323        303157.894737  10.175000                            0.631579  0.451668        78.564941         0.670833           0.329167
ai_adaptive  0.057233    0.007292        303654.970760  10.837500                            0.632615  0.480709        35.845978         0.670833           0.329167
oracle       0.054654    0.006771        318698.830409  11.016667                            0.663956  0.494132        36.045381         0.654167           0.345833


## Improvement vs fixed baselines (positive = better)

| strategy | dACS vs fixed OTFS | dACS vs fixed ODDM | dBER(abs) vs fixed OTFS | dBER(abs) vs fixed ODDM |
|---|---|---|---|---|
| ai_adaptive | +0.0029 | +0.0290 | +9.983e-05 | -2.271e-02 |
| oracle | +0.0163 | +0.0425 | -2.479e-03 | -2.529e-02 |
