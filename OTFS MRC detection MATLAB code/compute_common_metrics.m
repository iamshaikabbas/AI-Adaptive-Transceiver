function res = compute_common_metrics(tx_bits, rx_bits, tx_sym, rx_sym, M_mod, cfg, det_time_s, total_time_s)
% =========================================================================
% COMPUTE_COMMON_METRICS   Single-frame metric block shared by run_otfs /
% run_oddm / run_ofdm so every waveform reports identical quantities.
%
% Definitions (documented, actually computed):
%   BER  bit error rate of the frame
%   SER  symbol error rate (re-modulated bits vs transmitted symbols)
%   PER  frame-level packet error indicator (1 if any bit wrong)
%   Throughput_bps        payload bits * (1-PER) / frame duration
%                         (OTFS frame = N*T; ODDM/OFDM include CP overhead)
%   SpectralEfficiency    throughput / bandwidth [bps/Hz]
%   EVM_percent           rms constellation error in %
%   SINR_est_dB           -20*log10(EVM)  (EVM-based effective SINR)
%   CQI                   3GPP-style mapping of SINR_est_dB (0..15)
%   Latency_ms            detector wall-clock time per frame
%   PacketLoss            == PER (frame granularity)
%   RecoveryRate          1 - PER
% =========================================================================

M_bits = log2(M_mod);
bit_errs = sum(xor(rx_bits(:), tx_bits(:)));
N_bits   = numel(tx_bits);

res.BER  = bit_errs / N_bits;
res.SER  = sum(rx_sym ~= tx_sym) / numel(tx_sym);
res.PER  = double(bit_errs > 0);

evm = sqrt(mean(abs(rx_sym(:) - tx_sym(:)).^2) / mean(abs(tx_sym(:)).^2));
res.EVM_percent = 100*evm;
res.SINR_est_dB = -20*log10(max(res.EVM_percent,1e-6)/100);
res.CQI = compute_CQI_from_sinr(res.SINR_est_dB);

switch upper(cfg.Waveform)
    case 'OTFS'
        frame_T = cfg.frame_T;
    otherwise                       % ODDM / OFDM carry a cyclic prefix
        frame_T = cfg.frame_T + cfg.L_cp/cfg.fs;
end

res.Throughput_bps       = N_bits * (1-res.PER) / frame_T;
res.SpectralEfficiency   = res.Throughput_bps / cfg.BW;
res.Latency_ms           = 1000*det_time_s;
res.PacketLoss           = res.PER;
res.RecoveryRate         = 1 - res.PER;
res.Runtime_sec          = total_time_s;

% ---- Adaptive Communication Score (see compute_acs.m / acs_weights.json) ----
tp_cap = N_bits / frame_T;               % noiseless throughput for this frame
se_cap = log2(M_mod);                    % modulation upper bound [bps/Hz]
[res.ACS, res.ACS_parts] = compute_acs(res.BER, res.Throughput_bps, ...
    res.SpectralEfficiency, res.CQI, res.Latency_ms, res.RecoveryRate, ...
    tp_cap, se_cap);
end
