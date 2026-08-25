function [result, n_bits, frame_T] = dt_exec_waveform(cfg, chan, tx_bits, ...
                                                      noise_seed, waveform)
% =========================================================================
% DT_EXEC_WAVEFORM   Execute ONE waveform on ONE frame's shared inputs.
%
%   [result, n_bits, frame_T] = dt_exec_waveform(cfg_f, chan, tx_bits, ...
%                                                noise_seed, 'OTFS'|'ODDM')
%
% This is THE single-frame execution primitive (spec section 5). It
% contains NO scenario logic and NO policy logic:
%   1. cfg is stamped with the shared channel / payload / noise seed
%      and the deployment detector for the requested waveform;
%   2. run_otfs.m or run_oddm.m (validated software communication chain);
%   3. metrics are collected into a dt_frame_result; wall-clock detector
%      time is measured and stored as wall_clock_ms (spec section 22).
%
% Never fabricates results: on failure the result carries error_flag=true,
% NaN metrics and the error message (NaN = explicitly unavailable).
%
% Frame-duration convention (identical to the validated runtime):
%   OTFS frame_T = cfg.frame_T
%   ODDM frame_T = cfg.frame_T + L_cp/fs, L_cp = max(max_delay_tap+1, 2)
% These feed the throughput cap used by ACS (compute_acs.m).
% =========================================================================
waveform = upper(char(waveform));
result = dt_frame_result(struct('scenario_id', "", 'frame', 0, ...
    'waveform', string(waveform), ...
    'detector', twin_default_detector(waveform)));
result.waveform  = string(waveform);
result.detector  = string(twin_default_detector(waveform));

c = cfg;
c.chan       = chan;
c.tx_bits    = tx_bits;
c.noise_seed = double(noise_seed);
c.Waveform   = waveform;
c.([waveform '_Detector']) = char(twin_default_detector(waveform));

t0 = tic;
try
    switch waveform
        case 'OTFS', res = run_otfs(c);
        case 'ODDM', res = run_oddm(c);
        otherwise, error('unsupported waveform ''%s''', waveform);
    end
    wc_ms = toc(t0)*1e3;

    mod_bits  = log2(double(c.Modulation));
    Lg        = max(double(chan.max_delay_tap)+1, ceil(double(c.M)/16));
    N_syms    = (double(c.M) - Lg) * double(c.N);
    n_bits    = N_syms * mod_bits;
    L_cp      = max(double(chan.max_delay_tap)+1, 2);
    if strcmp(waveform,'OTFS')
        frame_T = c.frame_T;
    else
        frame_T = c.frame_T + L_cp/c.fs;
    end

    result.BER = double(res.BER);
    result.SER = double(res.SER);
    result.PER = double(res.PER);
    result.throughput_bps = double(res.Throughput_bps);
    result.spectral_efficiency = double(res.SpectralEfficiency);
    result.CQI = double(res.CQI);
    result.wall_clock_ms = wc_ms;
    result.detector_time_ms = double(res.Latency_ms);  % inner, feeds ACS
    result.latency_ms_modeled = NaN;         % not modeled (see header)
    result.packet_loss = double(res.PacketLoss);
    result.recovery_rate = double(res.RecoveryRate);
    % Legacy column parity: Latency_ms in Phase-2/4 traces == detector
    % wall-clock time; ACS keeps consuming that value (documented).
    result.ACS = compute_acs(res.BER, res.Throughput_bps, ...
        res.SpectralEfficiency, res.CQI, res.Latency_ms, ...
        res.RecoveryRate, n_bits/frame_T, mod_bits);
    result.tp_cap_bps = n_bits/frame_T;
    result.se_cap     = mod_bits;
catch me
    result.error_flag = true;
    result.error_message = string(me.message);
end
end
