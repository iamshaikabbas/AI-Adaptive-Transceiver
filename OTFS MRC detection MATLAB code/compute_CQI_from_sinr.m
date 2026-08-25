function cqi = compute_CQI_from_sinr(sinr_dB)
% Approximate 3GPP-style SINR -> CQI (0-15) mapping. Identical thresholds
% to compute_CQI() inside ZP_OTFS_MRC_system.m so the OTFS dataset and the
% new waveform-comparison dataset share one definition.
    thresholds = [-6.7 -4.7 -2.3 0.2 2.4 4.3 5.9 8.1 10.3 11.7 14.1 16.3 18.7 21.0 22.7];
    cqi = 0;
    for k = 1:numel(thresholds)
        if sinr_dB >= thresholds(k)
            cqi = k;
        end
    end
end
