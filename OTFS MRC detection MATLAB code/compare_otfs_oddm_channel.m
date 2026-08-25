% =========================================================================
% compare_otfs_oddm_channel.m   [Comparison 4/9]
% Performance per delay profile {RayleighFlat, EPA, EVA, ETU} at SNR=15 dB,
% 120 km/h, QPSK. Grouped bars for BER and CQI.
% =========================================================================
clearvars; clc;
outdir = fullfile('Results','WaveformComparison');
if ~exist(outdir,'dir'), mkdir(outdir); end

D        = combo_defs('full5');
profiles = {'RayleighFlat','EPA','EVA','ETU'};
nTrials  = 25;

% (S is created by the first paired-trial assignment -- do not pre-init)
fprintf('=== Channel-profile comparison (SNR=15 dB, 120 km/h) ===\n');
for j = 1:numel(profiles)
    cfg = sim_default_config('DelayProfile',profiles{j},'Speed_kmph',120, ...
                             'Modulation',4,'SNR_dB',15);
    Sj = run_paired_trials(D, cfg, nTrials);
    for i = 1:numel(D), S(i,j) = Sj(i); end
    fprintf('Profile %s done\n', profiles{j});
end

save_compare_results(outdir, 'cmp_channel', 'ProfileIdx', 1:numel(profiles), S);

nC = numel(D);
cols = lines(max(nC,7));
x = 1:numel(profiles);

figure('Position',[60 60 1280 720],'Color','w');
subplot(2,2,1); hold on; grid on; box on;
bermat = zeros(nC,numel(profiles));
for i=1:nC, for j=1:numel(profiles), bermat(i,j)=S(i,j).BER_total; end, end
b = bar(x, max(bermat.',1e-6)', 'grouped','EdgeColor','none');
for i=1:nC, b(i).FaceColor = cols(i,:); end
set(gca,'YScale','log','XTickLabel',profiles,'XTick',x,'FontName','DejaVu Sans');
ylabel('BER'); title('BER by channel profile (15 dB)');
legend({D.name},'Location','best','Interpreter','none');

subplot(2,2,2); hold on; grid on; box on;
cqimat = zeros(nC,numel(profiles));
for i=1:nC, for j=1:numel(profiles), cqimat(i,j)=S(i,j).CQI_mean; end, end
b = bar(x, cqimat.', 'grouped','EdgeColor','none');
for i=1:nC, b(i).FaceColor = cols(i,:); end
set(gca,'XTickLabel',profiles,'XTick',x,'FontName','DejaVu Sans');
ylabel('CQI (0-15)'); title('CQI by channel profile');

subplot(2,2,3); hold on; grid on; box on;
permat = zeros(nC,numel(profiles));
for i=1:nC, for j=1:numel(profiles), permat(i,j)=S(i,j).PER_mean; end, end
b = bar(x, permat.', 'grouped','EdgeColor','none');
for i=1:nC, b(i).FaceColor = cols(i,:); end
set(gca,'XTickLabel',profiles,'XTick',x,'FontName','DejaVu Sans');
ylabel('PER'); title('Packet error rate by profile');

subplot(2,2,4); hold on; grid on; box on;
latmat = zeros(nC,numel(profiles));
for i=1:nC, for j=1:numel(profiles), latmat(i,j)=S(i,j).Lat_mean; end, end
b = bar(x, latmat.', 'grouped','EdgeColor','none');
for i=1:nC, b(i).FaceColor = cols(i,:); end
set(gca,'XTickLabel',profiles,'XTick',x,'FontName','DejaVu Sans');
ylabel('Detection latency [ms]'); title('Detector latency by profile');

exportgraphics(gcf, fullfile(outdir,'cmp_channel.png'), 'Resolution',150);
fprintf('Saved %s\n', fullfile(outdir,'cmp_channel.png'));
