function S = run_paired_trials(wf_defs, cfg_base, n_trials)
% [PHASE-5 NOTE] LEGACY paired-trial harness (own seed scheme, kept for provenance). Canonical runner: run_experiment.m.
% =========================================================================
% RUN_PAIRED_TRIALS   Fair-comparison engine for OTFS / ODDM / OFDM.
%
% For every trial t:
%   1. ONE channel realization      chan  <- gen_channel_params_flex(cfg_base)
%   2. ONE payload                  bits  (identical for every waveform)
%   3. ONE noise seed               seed  = 100000 + t
% are generated ONCE and handed to EVERY waveform/detector combination,
% so all combos see identical physical conditions (paired design).
%
% Inputs:
%   wf_defs  : struct array, fields .name (legend label), .wf ('OTFS'|
%              'ODDM'|'OFDM'), .det (detector string for that waveform)
%   cfg_base : sim_default_config(...) struct with the operating point
%   n_trials : number of paired trials (frames per operating point)
%
% Output:
%   S(i)     : per-trial metric vectors (.BER .SER .PER .Throughput_bps
%              .SpectralEfficiency .CQI .SINR_est_dB .EVM_percent
%              .Latency_ms .Runtime_sec) plus aggregated means
%              (.BER_total bit-weighted, .PER_mean .CQI_mean .Thr_mean
%              .SE_mean .SINR_mean .Lat_mean .Run_mean).
% =========================================================================

ncomb   = numel(wf_defs);
metrics = {'BER','SER','PER','Throughput_bps','SpectralEfficiency', ...
           'CQI','SINR_est_dB','EVM_percent','Latency_ms','Runtime_sec'};
nmet    = numel(metrics);

for i = 1:ncomb
    for m = 1:nmet
        S(i).(metrics{m}) = nan(1, n_trials);
    end
    S(i).name = wf_defs(i).name;
    S(i).wf   = wf_defs(i).wf;
    S(i).det  = wf_defs(i).det;
end

% ---- payload sizing: identical guard-row rule for all waveforms ----------
probe     = cfg_base;
probe.chan= [];
chan0     = gen_channel_params_flex(probe);
Lg        = max(chan0.max_delay_tap+1, ceil(cfg_base.M/16));
M_bits    = log2(cfg_base.Modulation);
N_syms    = (cfg_base.M - Lg) * cfg_base.N;

rng(20260822);                                   % reproducible draws
tx_bits_master = randi([0 1], N_syms*M_bits, 1);

for t = 1:n_trials
    chan = gen_channel_params_flex(cfg_base);    % ONE realization per trial
    seed = 100000 + t;
    for i = 1:ncomb
        c = cfg_base;
        c.chan       = chan;
        c.tx_bits    = tx_bits_master;
        c.noise_seed = seed;
        c.Waveform   = wf_defs(i).wf;
        c.([wf_defs(i).wf '_Detector']) = wf_defs(i).det;
        switch wf_defs(i).wf
            case 'OTFS', res = run_otfs(c);
            case 'ODDM', res = run_oddm(c);
            case 'OFDM', res = run_ofdm(c);
            otherwise, error('run_paired_trials: unknown waveform %s', wf_defs(i).wf);
        end
        for m = 1:nmet
            S(i).(metrics{m})(t) = res.(metrics{m});
        end
    end
    if mod(t,10) == 0
        fprintf('    ...trial %d/%d done\n', t, n_trials);
    end
end

% ---- aggregation -----------------------------------------------------------
for i = 1:ncomb
    tot_bits = N_syms*M_bits*n_trials;
    S(i).BER_total = round(sum(S(i).BER)*N_syms*M_bits) / tot_bits;  % bit-weighted
    S(i).SER_total = round(sum(S(i).SER)*N_syms)        / (N_syms*n_trials);
    S(i).PER_mean  = mean(S(i).PER);
    S(i).CQI_mean  = mean(S(i).CQI);
    S(i).Thr_mean  = mean(S(i).Throughput_bps);
    S(i).SE_mean   = mean(S(i).SpectralEfficiency);
    S(i).SINR_mean = mean(S(i).SINR_est_dB);
    S(i).Lat_mean  = mean(S(i).Latency_ms);
    S(i).Run_mean  = mean(S(i).Runtime_sec);
end
end
