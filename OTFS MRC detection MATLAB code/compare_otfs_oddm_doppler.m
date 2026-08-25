% =========================================================================
% compare_otfs_oddm_doppler.m   [Comparison 3/9]
% Performance vs normalized Doppler multiplier (DopplerScale 0..1.5 applied
% on top of the 120 km/h physical Doppler) at SNR = 15 dB, EVA, QPSK.
% Isolates pure ICI sensitivity from the speed label.
% =========================================================================
clearvars; clc;
outdir = fullfile('Results','WaveformComparison');
if ~exist(outdir,'dir'), mkdir(outdir); end

D       = combo_defs('full5');
dscale  = 0:0.15:1.5;
nTrials = 25;

% (S is created by the first paired-trial assignment -- do not pre-init)
fprintf('=== Doppler-scale sweep (EVA, 120 km/h base, SNR=15 dB) ===\n');
for j = 1:numel(dscale)
    cfg = sim_default_config('DelayProfile','EVA','Speed_kmph',120, ...
                             'DopplerScale',dscale(j),'Modulation',4,'SNR_dB',15);
    Sj = run_paired_trials(D, cfg, nTrials);
    for i = 1:numel(D), S(i,j) = Sj(i); end
    fprintf('DopplerScale %.2f done\n', dscale(j));
end

save_compare_results(outdir, 'cmp_doppler', 'DopplerScale', dscale, S);

figure('Position',[60 60 1280 720],'Color','w');
subplot(2,2,1);
plot_compare_metric(dscale, S, 'BER_total', {'Yscale','log','Ylabel','BER', ...
    'Title','BER vs normalized-Doppler scale','Floor',0.5/(32*28*30*nTrials)});
subplot(2,2,2);
plot_compare_metric(dscale, S, 'SER_total', {'Yscale','log','Ylabel','SER', ...
    'Title','SER vs Doppler scale','Floor',0.5/(32*28*30*nTrials)});
subplot(2,2,3);
plot_compare_metric(dscale, S, 'SE_mean', {'Yscale','linear','Ylabel','Spectral eff. [bps/Hz]', ...
    'Title','Spectral efficiency vs Doppler scale'});
subplot(2,2,4);
plot_compare_metric(dscale, S, 'CQI_mean', {'Yscale','linear','Ylabel','CQI (0-15)', ...
    'Title','CQI vs Doppler scale'});
exportgraphics(gcf, fullfile(outdir,'cmp_doppler.png'), 'Resolution',150);
fprintf('Saved %s\n', fullfile(outdir,'cmp_doppler.png'));
