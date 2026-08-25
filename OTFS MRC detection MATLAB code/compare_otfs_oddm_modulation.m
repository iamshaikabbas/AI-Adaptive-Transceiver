% =========================================================================
% compare_otfs_oddm_modulation.m   [Comparison 7/9]
% BER vs SNR for QPSK / 16-QAM / 64-QAM (EVA, 120 km/h), main three
% waveform+detector combos. One subplot per modulation order.
% =========================================================================
clearvars; clc;
outdir = fullfile('Results','WaveformComparison');
if ~exist(outdir,'dir'), mkdir(outdir); end

D      = combo_defs('main3');
mods   = [4 16 64];
SNRs   = [0 5 10 15 20];
nTrials = 15;

% (S is created by the first paired-trial assignment -- do not pre-init)
fprintf('=== Modulation comparison (EVA, 120 km/h) ===\n');
for m = 1:numel(mods)
    for j = 1:numel(SNRs)
        cfg = sim_default_config('DelayProfile','EVA','Speed_kmph',120, ...
                                 'Modulation',mods(m),'SNR_dB',SNRs(j));
        Sj = run_paired_trials(D, cfg, nTrials);
        for i = 1:numel(D), S(i,j,m) = Sj(i); end
    end
    fprintf('Modulation %d-QAM done\n', mods(m));
end

% CSV
fid = fopen(fullfile(outdir,'cmp_modulation.csv'),'w');
fprintf(fid,'modulation,SNR_dB,label,BER,SER,PER,CQI_mean,SE_mean\n');
for m=1:numel(mods), for j=1:numel(SNRs), for i=1:numel(D)
    fprintf(fid,'%d,%g,%s,%.8g,%.8g,%.6g,%.4f,%.6g\n', mods(m), SNRs(j), S(i,j,m).name, ...
        S(i,j,m).BER_total, S(i,j,m).SER_total, S(i,j,m).PER_mean, ...
        S(i,j,m).CQI_mean, S(i,j,m).SE_mean);
end, end, end
fclose(fid);

figure('Position',[60 60 1280 720],'Color','w');
for m = 1:numel(mods)
    subplot(1,3,m);
    plot_compare_metric(SNRs, S(:,:,m), 'BER_total', {'Yscale','log', ...
        'Ylabel','BER','Title',sprintf('%d-QAM (EVA, 120 km/h)',mods(m)), ...
        'Floor',0.5/(32*28*30*nTrials)});
end
exportgraphics(gcf, fullfile(outdir,'cmp_modulation.png'), 'Resolution',150);
fprintf('Saved %s\n', fullfile(outdir,'cmp_modulation.png'));
