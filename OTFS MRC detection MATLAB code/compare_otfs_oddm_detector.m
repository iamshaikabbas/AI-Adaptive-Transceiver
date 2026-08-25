% =========================================================================
% compare_otfs_oddm_detector.m   [Comparison 8/9]
% Detector impact: all six waveform x detector combinations at two
% operating points (static EVA and high-mobility EVA), SNR = 15 dB, QPSK.
% Grouped bars for BER, latency and CQI.
% =========================================================================
clearvars; clc;
outdir = fullfile('Results','WaveformComparison');
if ~exist(outdir,'dir'), mkdir(outdir); end

D       = combo_defs('det6');
conds   = struct('name',{'EVA static (0 km/h)','EVA 120 km/h'}, ...
                 'speed',{0,120});
nTrials = 25;

% (S is created by the first paired-trial assignment -- do not pre-init)
fprintf('=== Detector comparison (SNR=15 dB) ===\n');
for j = 1:numel(conds)
    cfg = sim_default_config('DelayProfile','EVA','Speed_kmph',conds(j).speed, ...
                             'Modulation',4,'SNR_dB',15);
    if conds(j).speed == 0, cfg.DopplerScale = 0; end
    Sj = run_paired_trials(D, cfg, nTrials);
    for i = 1:numel(D), S(i,j) = Sj(i); end
    fprintf('Condition "%s" done\n', conds(j).name);
end

save_compare_results(outdir, 'cmp_detector', 'CondIdx', 1:numel(conds), S);

nC = numel(D);
cols = lines(max(nC,7));
x = 1:numel(conds);

figure('Position',[60 60 1280 720],'Color','w');
subplot(2,2,1); hold on; grid on; box on;
bermat = zeros(nC,numel(conds));
for i=1:nC, for j=1:numel(conds), bermat(i,j)=S(i,j).BER_total; end, end
b = bar(x, max(bermat.',1e-6)', 'grouped','EdgeColor','none');
for i=1:nC, b(i).FaceColor = cols(i,:); end
set(gca,'YScale','log','XTickLabel',{conds.name},'XTick',x,'FontName','DejaVu Sans');
ylabel('BER'); title('BER by operating point (15 dB)');
legend({D.name},'Location','eastoutside','Interpreter','none');

subplot(2,2,2); hold on; grid on; box on;
latmat = zeros(nC,numel(conds));
for i=1:nC, for j=1:numel(conds), latmat(i,j)=S(i,j).Lat_mean; end, end
b = bar(x, latmat.', 'grouped','EdgeColor','none');
for i=1:nC, b(i).FaceColor = cols(i,:); end
set(gca,'XTickLabel',{conds.name},'XTick',x,'FontName','DejaVu Sans');
ylabel('Detection latency [ms]'); title('Detector latency');

subplot(2,2,3); hold on; grid on; box on;
cqimat = zeros(nC,numel(conds));
for i=1:nC, for j=1:numel(conds), cqimat(i,j)=S(i,j).CQI_mean; end, end
b = bar(x, cqimat.', 'grouped','EdgeColor','none');
for i=1:nC, b(i).FaceColor = cols(i,:); end
set(gca,'XTickLabel',{conds.name},'XTick',x,'FontName','DejaVu Sans');
ylabel('CQI (0-15)'); title('Reported CQI');

subplot(2,2,4); hold on; grid on; box on;
semat = zeros(nC,numel(conds));
for i=1:nC, for j=1:numel(conds), semat(i,j)=max(S(i,j).SER_total,1e-6); end, end
b = bar(x, semat.', 'grouped','EdgeColor','none');
for i=1:nC, b(i).FaceColor = cols(i,:); end
set(gca,'YScale','log','XTickLabel',{conds.name},'XTick',x,'FontName','DejaVu Sans');
ylabel('SER'); title('Symbol error rate');

exportgraphics(gcf, fullfile(outdir,'cmp_detector.png'), 'Resolution',150);
fprintf('Saved %s\n', fullfile(outdir,'cmp_detector.png'));
