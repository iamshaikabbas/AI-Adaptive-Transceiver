% =========================================================================
% compare_otfs_oddm_environment.m   [Comparison 5/9]
% Environment x mobility matrix: {EPA, EVA, ETU} x {3, 30, 120, 350 km/h}
% at SNR = 15 dB, QPSK. Produces BER heatmaps for OTFS (MRC) and
% ODDM (LMMSE) plus a per-cell winner table.
% =========================================================================
clearvars; clc;
outdir = fullfile('Results','WaveformComparison');
if ~exist(outdir,'dir'), mkdir(outdir); end

profiles = {'EPA','EVA','ETU'};
speeds   = [3 30 120 350];
nTrials  = 15;

nR = numel(profiles); nCcol = numel(speeds);
berO = zeros(nR,nCcol); berD = zeros(nR,nCcol); berF = zeros(nR,nCcol);
cqiO = zeros(nR,nCcol); cqiD = zeros(nR,nCcol); cqiF = zeros(nR,nCcol);
winner = cell(nR,nCcol);

D = combo_defs('main3');
fprintf('=== Environment x speed matrix (SNR=15 dB) ===\n');
for r = 1:nR
    for c = 1:nCcol
        cfg = sim_default_config('DelayProfile',profiles{r}, ...
                                 'Speed_kmph',speeds(c),'Modulation',4,'SNR_dB',15);
        S = run_paired_trials(D, cfg, nTrials);
        berO(r,c) = S(1).BER_total; cqiO(r,c) = S(1).CQI_mean;
        berD(r,c) = S(2).BER_total; cqiD(r,c) = S(2).CQI_mean;
        berF(r,c) = S(3).BER_total; cqiF(r,c) = S(3).CQI_mean;
        bers = [berO(r,c), berD(r,c), berF(r,c)];
        [~,w] = min(bers);
        winner{r,c} = sprintf('%s (%.1e)', D(w).name, bers(w));
        fprintf('%s @%d km/h: OTFS %.2e | ODDM %.2e | OFDM %.2e -> %s\n', ...
            profiles{r}, speeds(c), berO(r,c), berD(r,c), berF(r,c), D(w).name);
    end
end

% ---- CSV: full grid --------------------------------------------------------
fid = fopen(fullfile(outdir,'cmp_environment.csv'),'w');
fprintf(fid,'profile,speed_kmph,BER_OTFS_MRC,CQI_OTFS,BER_ODDM_LMMSE,CQI_ODDM,BER_OFDM_LMMSE,CQI_OFDM,winner\n');
for r=1:nR, for c=1:nCcol
    [~,w] = min([berO(r,c) berD(r,c) berF(r,c)]);
    fprintf(fid,'%s,%d,%.8g,%.4f,%.8g,%.4f,%.8g,%.4f,%s\n', profiles{r}, speeds(c), ...
        berO(r,c), cqiO(r,c), berD(r,c), cqiD(r,c), berF(r,c), cqiF(r,c), D(w).name);
end, end
fclose(fid);

% ---- heatmaps ----------------------------------------------------------------
figure('Position',[60 60 1280 720],'Color','w');
subplot(2,2,1);
imagesc(min(log10(max(berO,1e-6)),0)); colorbar; axis image;
set(gca,'XTick',1:nCcol,'XTickLabel',compose('%d',speeds),'YTick',1:nR,'YTickLabel',profiles,'FontName','DejaVu Sans');
title('log_{10} BER -- OTFS (MRC)'); xlabel('speed [km/h]');
subplot(2,2,2);
imagesc(min(log10(max(berD,1e-6)),0)); colorbar; axis image;
set(gca,'XTick',1:nCcol,'XTickLabel',compose('%d',speeds),'YTick',1:nR,'YTickLabel',profiles,'FontName','DejaVu Sans');
title('log_{10} BER -- ODDM (LMMSE)'); xlabel('speed [km/h]');
subplot(2,2,3);
imagesc(cqiO); colorbar; axis image;
set(gca,'XTick',1:nCcol,'XTickLabel',compose('%d',speeds),'YTick',1:nR,'YTickLabel',profiles,'FontName','DejaVu Sans');
title('CQI -- OTFS (MRC)');
subplot(2,2,4); axis off;
text(0.02, 0.95, 'Per-cell winner (lowest BER):', 'FontSize',11,'FontWeight','bold');
for r=1:nR, for c=1:nCcol
    text(0.02+ (c-1)*0.25, 0.80 - (r-1)*0.12, sprintf('%s %4d km/h: %s', profiles{r}, speeds(c), winner{r,c}), 'FontSize',8, 'Interpreter','none');
end, end
exportgraphics(gcf, fullfile(outdir,'cmp_environment.png'), 'Resolution',150);
fprintf('Saved %s\n', fullfile(outdir,'cmp_environment.png'));
