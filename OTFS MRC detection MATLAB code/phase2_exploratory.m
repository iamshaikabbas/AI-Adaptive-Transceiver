% =========================================================================
% phase2_exploratory.m   [Phase 2 / STEP 1]
%
% Small paired exploratory grid to find where OTFS and ODDM actually
% differ under the CURRENT implementation -- before any dataset is
% generated or any model retrained.
%
%   SNR    : -5 0 5 10 15 20 dB          (dt_config 'snr_fast')
%   Speed  : 0 50 150 250 350 km/h       (section-15 example values)
%   Channel: EPA, EVA, ETU               (existing generator only)
%   Mod    : QPSK, 16-QAM
%
% For every condition BOTH waveforms run as true PAIRED trials (identical
% channel realization, payload bits and noise seed per trial; only the
% waveform changes). Nothing is assumed about which waveform wins.
%
% Output: Results/WaveformComparison/phase2_exploratory.csv
% =========================================================================
clearvars; clc;
C  = dt_config('fast');
if ~exist(C.outdir,'dir'), mkdir(C.outdir); end

SNRs    = C.snr_fast;
speeds  = [0 50 150 250 350];
profiles= C.profiles;
mods    = C.mods_fast;
D       = C.combos;
nT      = C.nTrials;

nCond = numel(SNRs)*numel(speeds)*numel(profiles)*numel(mods);
fprintf(['EXPLORATORY GRID: %d conditions x %d waveforms x %d paired ' ...
         'trials\n'], nCond, numel(D), nT);
t0 = tic;

cols = {'cond_id','profile','speed_kmph','snr_db','modulation','carrier_hz', ...
        'doppler_hz','num_paths','delay_spread_taps','doppler_spread_hz', ...
        'nTrials','label','BER_total','SER_total','PER_mean','Thr_mean', ...
        'SE_mean','EVM_mean','CQI_mean','SINR_mean','Lat_mean','Run_mean'};
fid = fopen(fullfile(C.outdir,'phase2_exploratory.csv'),'w');
fprintf(fid,'%s\n', strjoin(cols,','));
fclose(fid);

cid = 0;
for ip = 1:numel(profiles)
for sp = speeds
for is = 1:numel(SNRs)
for m = mods
    cid = cid + 1;
    cfg = sim_default_config('DelayProfile',profiles{ip}, ...
                             'Speed_kmph',sp,'Modulation',m, ...
                             'SNR_dB',SNRs(is));
    cfg.car_fre = C.carrier_hz;              % explicit carrier (4 GHz default)
    cfg.cfo_hz = C.impairments.cfo_hz;       % zeros: impairment-free matrix
    cfg.phase_offset_rad = C.impairments.phase_offset_rad;
    cfg.timing_offset_samples = C.impairments.timing_offset_samples;

    probe = cfg; probe.chan = [];
    pchan = gen_channel_params_flex(probe);  % feature source (probe draw)

    S = run_paired_trials(D, cfg, nT);

    fid = fopen(fullfile(C.outdir,'phase2_exploratory.csv'),'a');
    for i = 1:numel(D)
        fprintf(fid,'%d,%s,%g,%g,%d,%g,%g,%d,%d,%.6g,%d,%s,%.10g,%.10g,%.10g,%.10g,%.10g,%.10g,%.10g,%.10g,%.10g,%.10g\n', ...
            cid, profiles{ip}, sp, SNRs(is), m, C.carrier_hz, ...
            dt_derive_doppler(sp, C.carrier_hz, 1), ...
            pchan.taps, pchan.max_delay_tap, pchan.doppler_spread_hz, nT, ...
            S(i).name, S(i).BER_total, S(i).SER_total, S(i).PER_mean, ...
            S(i).Thr_mean, S(i).SE_mean, mean(S(i).EVM_percent), ...
            S(i).CQI_mean, S(i).SINR_mean, S(i).Lat_mean, S(i).Run_mean);
    end
    fclose(fid);

    fprintf('[%3d/%3d] %s %3dkmh %5.1fdB M%d : OTFS %.4g vs ODDM %.4g (%.1fs)\n', ...
        cid, nCond, upper(profiles{ip}), sp, SNRs(is), m, ...
        S(1).BER_total, S(2).BER_total, toc(t0));
end
end
end
end

fprintf('DONE: %d conditions in %.1f min -> %s\n', cid, toc(t0)/60, ...
    fullfile(C.outdir,'phase2_exploratory.csv'));
