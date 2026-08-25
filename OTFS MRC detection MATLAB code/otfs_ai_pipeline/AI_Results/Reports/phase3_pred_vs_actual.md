# Phase 3 - predicted vs actual (adaptive frames)

waveform   n  BER_log10_MAE  BER_log10_RMSE  ACS_MAE  ACS_RMSE
    OTFS 240       2.124397        3.908137 0.157347  0.243057
    ODDM 240       2.524310        4.253801 0.159179  0.246869

Frames where predicted better-waveform (by ACS) disagrees with actually-better waveform: **31/240 (12.9%)**

These prediction flips explain most AI/oracle disagreements:
the decision chain follows its regression model faithfully;
where the model's ACS ordering is wrong, the selection is wrong.
