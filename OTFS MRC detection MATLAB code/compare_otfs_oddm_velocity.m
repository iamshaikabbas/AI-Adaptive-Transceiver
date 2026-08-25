% =========================================================================
% compare_otfs_oddm_velocity.m   [Comparison 2/9]
% Performance vs vehicle speed (0..300 km/h) at fixed SNR = 15 dB, EVA,
% QPSK. Shows Doppler robustness of each waveform.
% =========================================================================
clearvars; clc;
outdir = fullfile('Results','WaveformComparison');
if ~exist(outdir,'dir'), mkdir(outdir); end

D       = combo_defs('full5');
speeds  = 0:30:300;
nTrials = 25;

% (S is created by the first paired-trial assignment -- do not pre-init)
fprintf('=== Velocity sweep (EVA, SNR=15 dB) ===\n');
for j = 1:numel(speeds)
    cfg = sim_default_config('DelayProfile','EVA','Speed_kmph',speeds(j), ...
                             'Modulation',4,'SNR_dB',15);
    Sj = run_paired_trials(D, cfg, nTrials);
    for i = 1:numel(D), S(i,j) = Sj(i); end
    fprintf('Speed %3d km/h done\n', speeds(j));
end

save_compare_results(outdir, 'cmp_velocity', 'Speed_kmph', speeds, S);

figure('Position',[60 60 1280 720],'Color','w');
subplot(2,2,1);
plot_compare_metric(speeds, S, 'BER_total', {'Yscale','log','Ylabel','BER', ...
    'Title','BER vs speed (EVA, 15 dB)','Floor',0.5/(32*28*30*nTrials)});
subplot(2,2,2);
plot_compare_metric(speeds, S, 'PER_mean', {'Yscale','linear','Ylabel','PER', ...
    'Title','Packet error rate vs speed'});
subplot(2,2,3);
plot_compare_metric(speeds, S, 'SINR_mean', {'Yscale','linear','Ylabel','SINR_{est} [dB]', ...
    'Title','Estimated SINR vs speed'});
subplot(2,2,4);
plot_compare_metric(speeds, S, 'Thr_mean', {'Yscale','linear','Ylabel','Throughput [bps]', ...
    'Title','Throughput vs speed'});
exportgraphics(gcf, fullfile(outdir,'cmp_velocity.png'), 'Resolution',150);
fprintf('Saved %s\n', fullfile(outdir,'cmp_velocity.png'));
