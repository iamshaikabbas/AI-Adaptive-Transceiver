% =========================================================================
% build_waveform_dataset.m   [Dataset stage]
%
% Builds the combined OTFS/ODDM/OFDM training dataset for the AI waveform
% selector. Long format, one row per (condition x trial x waveform):
%
%   Waveform, Environment, Speed_kmh, DelayProfile, DelaySpread, NumPaths,
%   DopplerSpread, Modulation, Detector, SNR_dB, BER, SER, PER, EVM_percent,
%   SINR_est_dB, CQI, Throughput_bps, SpectralEfficiency_bps_per_Hz,
%   Runtime_sec, AvgIterations, ScenarioID, Category, FocusMode,
%   CondID, TrialIdx, Timestamp
%
% Rows sharing (CondID, TrialIdx) were simulated under IDENTICAL channel
% realization, payload bits and noise seed -> valid paired-selection labels
% (winner = argmin BER within a pair).
%
% Column semantics follow Results\OTFS_Dataset.csv (repo convention):
%   DelaySpread   = max integer delay tap          [taps]
%   DopplerSpread = max |Doppler tap|              [normalized taps]
%   Category      = Low (<30) / Mid (<120) / High mobility bucket
% =========================================================================
clearvars; clc;
outdir = fullfile('Results','WaveformComparison');
if ~exist(outdir,'dir'), mkdir(outdir); end

profiles = {'EPA','EVA','ETU'};
envNames = {'Pedestrian','Vehicular','Urban'};
speeds   = [3 30 60 120 200 350];
SNRs     = 0:5:25;
mods     = [4 16 64];
nTrials  = 5;

combos = struct('wf',{'OTFS','OTFS','ODDM','ODDM','OFDM','OFDM'}, ...
                'det',{'MRC','LMMSE','MMSETAP','LMMSE','MMSETAP','LMMSE'});
nC = numel(combos);

rng(20260822);
fid = fopen(fullfile(outdir,'waveform_dataset.csv'),'w');
fprintf(fid,['Waveform,Environment,Speed_kmh,DelayProfile,DelaySpread,NumPaths,' ...
             'DopplerSpread,Modulation,Detector,SNR_dB,BER,SER,PER,EVM_percent,' ...
             'SINR_est_dB,CQI,Throughput_bps,SpectralEfficiency_bps_per_Hz,' ...
             'Runtime_sec,AvgIterations,ScenarioID,Category,FocusMode,' ...
             'CondID,TrialIdx,Timestamp\n']);

condID = 0; scenarioID = 0; nRows = 0;
t_all = tic;

for ip = 1:numel(profiles)
for sp = speeds
for im = 1:numel(mods)
for isn = 1:numel(SNRs)
    condID = condID + 1;
    cfg = sim_default_config('DelayProfile',profiles{ip},'Speed_kmph',sp, ...
                             'Modulation',mods(im),'SNR_dB',SNRs(isn));
    probe = cfg; probe.chan = [];
    probe_chan = gen_channel_params_flex(probe);
    Lg     = max(probe_chan.max_delay_tap+1, ceil(cfg.M/16));
    M_bits = log2(mods(im));
    N_syms = (cfg.M - Lg)*cfg.N;
    tx_bits_master = randi([0 1], N_syms*M_bits, 1);

    if sp < 30, cat = 'LowMobility'; elseif sp < 120, cat = 'MidMobility';
    else, cat = 'HighMobility'; end

    for t = 1:nTrials
        scenarioID = scenarioID + 1;
        chan = gen_channel_params_flex(cfg);      % shared realization
        seed = 500000 + condID*100 + t;
        for ic = 1:nC
            c = cfg;
            c.chan = chan; c.tx_bits = tx_bits_master; c.noise_seed = seed;
            c.Waveform = combos(ic).wf;
            c.([combos(ic).wf '_Detector']) = combos(ic).det;
            switch combos(ic).wf
                case 'OTFS', res = run_otfs(c);
                case 'ODDM', res = run_oddm(c);
                case 'OFDM', res = run_ofdm(c);
            end
            switch combos(ic).det
                case 'MRC',   avg_it = cfg.n_ite_MRC;
                otherwise,    avg_it = 1;
            end
            fprintf(fid, '%s,%s,%d,%s,%d,%d,%.10g,%d,%s,%g,%.10g,%.10g,%d,%.6g,%.6g,%d,%.6g,%.6g,%.6g,%d,%d,%s,0,%d,%d,%s\n', ...
                combos(ic).wf, envNames{ip}, sp, profiles{ip}, ...
                chan.max_delay_tap, numel(chan.delay_taps), max(abs(chan.Doppler_taps)), ...
                mods(im), combos(ic).det, SNRs(isn), ...
                res.BER, res.SER, res.PER, res.EVM_percent, res.SINR_est_dB, ...
                res.CQI, res.Throughput_bps, res.SpectralEfficiency, ...
                res.Runtime_sec, avg_it, scenarioID, cat, condID, t, datestr(now,'yyyy-mm-dd HH:MM:SS'));
            nRows = nRows + 1;
        end
    end
    if mod(condID,20)==0
        fprintf('cond %d/%d (%s %dkmh %dQAM %.0fdB) rows=%d elapsed=%.1f min\n', ...
            condID, numel(profiles)*numel(speeds)*numel(mods)*numel(SNRs), ...
            profiles{ip}, sp, mods(im), SNRs(isn), nRows, toc(t_all)/60);
    end
end
end
end
end

fclose(fid);
fprintf('DONE: %d rows written to %s (%.1f min)\n', nRows, ...
    fullfile(outdir,'waveform_dataset.csv'), toc(t_all)/60);
