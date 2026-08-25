% =========================================================================
% compare_otfs_oddm_multipath.m   [Comparison 6/9]
% Performance vs number of resolvable paths (synthetic channel: P paths
% spread over the EVA span, exponential power decay, Jake's Doppler) at
% SNR = 15 dB, 120 km/h, QPSK. Isolates delay-spread richness effects.
% =========================================================================
clearvars; clc;
outdir = fullfile('Results','WaveformComparison');
if ~exist(outdir,'dir'), mkdir(outdir); end

D       = combo_defs('full5');
Plist   = 1:10;
nTrials = 25;

% (S is created by the first paired-trial assignment -- do not pre-init)
fprintf('=== Multipath-count sweep (synthetic, SNR=15 dB, 120 km/h) ===\n');
for j = 1:numel(Plist)
    cfg = sim_default_config('DelayProfile','EVA','Speed_kmph',120, ...
                             'NumPaths',Plist(j),'Modulation',4,'SNR_dB',15);
    Sj = run_paired_trials(D, cfg, nTrials);
    for i = 1:numel(D), S(i,j) = Sj(i); end
    fprintf('NumPaths %d done\n', Plist(j));
end

save_compare_results(outdir, 'cmp_multipath', 'NumPaths', Plist, S);

figure('Position',[60 60 1280 720],'Color','w');
subplot(2,2,1);
plot_compare_metric(Plist, S, 'BER_total', {'Yscale','log','Ylabel','BER', ...
    'Title','BER vs number of paths','Floor',0.5/(32*28*30*nTrials)});
subplot(2,2,2);
plot_compare_metric(Plist, S, 'PER_mean', {'Yscale','linear','Ylabel','PER', ...
    'Title','Packet error rate vs paths'});
subplot(2,2,3);
plot_compare_metric(Plist, S, 'SINR_mean', {'Yscale','linear','Ylabel','SINR_{est} [dB]', ...
    'Title','Estimated SINR vs paths'});
subplot(2,2,4);
plot_compare_metric(Plist, S, 'Lat_mean', {'Yscale','linear','Ylabel','Detection latency [ms]', ...
    'Title','Detector latency vs paths'});
exportgraphics(gcf, fullfile(outdir,'cmp_multipath.png'), 'Resolution',150);
fprintf('Saved %s\n', fullfile(outdir,'cmp_multipath.png'));
