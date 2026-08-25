% =========================================================================
% compare_otfs_oddm_snr.m   [Comparison 1/9]
% BER / throughput / spectral efficiency / CQI vs SNR (0..25 dB) under the
% reference condition: EVA profile, 120 km/h, QPSK, N=M=32.
% Paired trials: identical channel realization, payload and noise seed for
% every waveform at every SNR point.
% =========================================================================
clearvars; clc;
outdir = fullfile('Results','WaveformComparison');
if ~exist(outdir,'dir'), mkdir(outdir); end

D      = combo_defs('full5');
SNRs   = 0:2.5:25;
nTrials = 30;

% (S is created by the first paired-trial assignment -- do not pre-init)
fprintf('=== SNR sweep (%s km/h EVA, QPSK) ===\n', '120');
for j = 1:numel(SNRs)
    cfg = sim_default_config('DelayProfile','EVA','Speed_kmph',120, ...
                             'Modulation',4,'SNR_dB',SNRs(j));
    Sj = run_paired_trials(D, cfg, nTrials);
    for i = 1:numel(D), S(i,j) = Sj(i); end
    fprintf('SNR %5.1f dB done\n', SNRs(j));
end

save_compare_results(outdir, 'cmp_snr', 'SNR_dB', SNRs, S);

figure('Position',[60 60 1280 720],'Color','w');
subplot(2,2,1);
plot_compare_metric(SNRs, S, 'BER_total', {'Yscale','log','Ylabel','BER', ...
    'Title','BER vs SNR (EVA, 120 km/h, QPSK)','Floor',0.5/(32*28*30*nTrials)});
subplot(2,2,2);
plot_compare_metric(SNRs, S, 'Thr_mean', {'Yscale','linear','Ylabel','Throughput [bps]', ...
    'Title','Throughput vs SNR'});
subplot(2,2,3);
plot_compare_metric(SNRs, S, 'SE_mean', {'Yscale','linear','Ylabel','Spectral eff. [bps/Hz]', ...
    'Title','Spectral efficiency vs SNR'});
subplot(2,2,4);
plot_compare_metric(SNRs, S, 'CQI_mean', {'Yscale','linear','Ylabel','CQI (0-15)', ...
    'Title','CQI vs SNR'});
exportgraphics(gcf, fullfile(outdir,'cmp_snr.png'), 'Resolution',150);
fprintf('Saved %s\n', fullfile(outdir,'cmp_snr.png'));
