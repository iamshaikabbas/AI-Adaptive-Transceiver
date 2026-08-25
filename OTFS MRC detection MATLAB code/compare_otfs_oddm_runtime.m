% =========================================================================
% compare_otfs_oddm_runtime.m   [Comparison 9/9]
% Computational cost vs grid size: mean per-frame runtime (TX+CH+RX) and
% detector latency for N=M in {16, 32, 48} at SNR = 15 dB, EVA 120 km/h.
% =========================================================================
clearvars; clc;
outdir = fullfile('Results','WaveformComparison');
if ~exist(outdir,'dir'), mkdir(outdir); end

D       = combo_defs('main3');
sizes   = [16 32 48];
nTrials = 10;

% (S is created by the first paired-trial assignment -- do not pre-init)
fprintf('=== Runtime scaling (EVA, 120 km/h, 15 dB) ===\n');
for j = 1:numel(sizes)
    cfg = sim_default_config('DelayProfile','EVA','Speed_kmph',120, ...
                             'Modulation',4,'SNR_dB',15, ...
                             'N',sizes(j),'M',sizes(j));
    Sj = run_paired_trials(D, cfg, nTrials);
    for i = 1:numel(D), S(i,j) = Sj(i); end
    fprintf('Grid %dx%d done\n', sizes(j), sizes(j));
end

save_compare_results(outdir, 'cmp_runtime', 'NM', sizes.^2, S);

figure('Position',[60 60 1280 720],'Color','w');
subplot(2,2,1);
plot_compare_metric(sizes.^2, S, 'Run_mean', {'Yscale','log','Ylabel','Runtime per frame [s]', ...
    'Title','Total per-frame runtime vs NM'});
xlabel('NM');
subplot(2,2,2);
plot_compare_metric(sizes.^2, S, 'Lat_mean', {'Yscale','log','Ylabel','Detector latency [ms]', ...
    'Title','Detector latency vs NM'});
xlabel('NM');
subplot(2,2,3);
plot_compare_metric(sizes.^2, S, 'BER_total', {'Yscale','log','Ylabel','BER', ...
    'Title','BER sanity check across grid sizes','Floor',0.5/(48*44*30*nTrials)});
xlabel('NM');
subplot(2,2,4);
plot_compare_metric(sizes.^2, S, 'SE_mean', {'Yscale','linear','Ylabel','Spectral eff. [bps/Hz]', ...
    'Title','Spectral efficiency across grid sizes'});
xlabel('NM');
exportgraphics(gcf, fullfile(outdir,'cmp_runtime.png'), 'Resolution',150);
fprintf('Saved %s\n', fullfile(outdir,'cmp_runtime.png'));
