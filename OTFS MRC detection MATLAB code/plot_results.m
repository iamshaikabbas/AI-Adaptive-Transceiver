%% plot_results.m
% ------------------------------------------------------------------------
% Reads OTFS_Dataset.csv (produced by AI_OTFS_MRC_system.m) and generates
% a full set of graphs covering BER, Throughput, Runtime, and Iterations
% across the simulated Environments (traffic/mobility scenarios) and SNR
% sweep, plus how performance relates to Speed, Delay spread, number of
% Paths, and Doppler spread.
%
% Can be run standalone (e.g. after loading a previously saved dataset)
% as long as OTFS_Dataset.csv is on the MATLAB path / current folder.
% ------------------------------------------------------------------------

if ~exist('ResultsTable','var')
    ResultsTable = readtable('OTFS_Dataset.csv');
end
T = ResultsTable;

envs = unique(T.Environment,'stable');
n_envs = numel(envs);
colors = lines(n_envs);
max_snr = max(T.SNR);

%% ---------------------------------------------------------------------
% Figure 1 : BER vs SNR (per Environment)
figure('Name','BER vs SNR');
hold on;
for e = 1:n_envs
    idx = strcmp(T.Environment, envs{e});
    semilogy(T.SNR(idx), T.BER(idx), '-o', 'LineWidth', 2, 'Color', colors(e,:));
end
hold off; grid on; set(gca,'YScale','log');
xlabel('SNR (dB)'); ylabel('BER');
title('BER vs SNR across Environments');
legend(envs, 'Interpreter','none', 'Location','southwest');

%% Figure 2 : Throughput vs SNR (per Environment)
figure('Name','Throughput vs SNR');
hold on;
for e = 1:n_envs
    idx = strcmp(T.Environment, envs{e});
    plot(T.SNR(idx), T.Throughput(idx)/1e3, '-o', 'LineWidth', 2, 'Color', colors(e,:));
end
hold off; grid on;
xlabel('SNR (dB)'); ylabel('Throughput (kbps)');
title('Throughput vs SNR across Environments');
legend(envs, 'Interpreter','none', 'Location','northwest');

%% Figure 3 : Runtime vs SNR (per Environment)
figure('Name','Runtime vs SNR');
hold on;
for e = 1:n_envs
    idx = strcmp(T.Environment, envs{e});
    plot(T.SNR(idx), T.Runtime(idx), '-o', 'LineWidth', 2, 'Color', colors(e,:));
end
hold off; grid on;
xlabel('SNR (dB)'); ylabel('Runtime (s)');
title('Runtime vs SNR across Environments');
legend(envs, 'Interpreter','none', 'Location','northeast');

%% Figure 4 : Detector Iterations vs SNR (per Environment)
figure('Name','Iterations vs SNR');
hold on;
for e = 1:n_envs
    idx = strcmp(T.Environment, envs{e});
    plot(T.SNR(idx), T.Iterations(idx), '-s', 'LineWidth', 2, 'Color', colors(e,:));
end
hold off; grid on;
xlabel('SNR (dB)'); ylabel('Average detector iterations');
title('MRC Detector Iterations vs SNR across Environments');
legend(envs, 'Interpreter','none', 'Location','northeast');

%% ---------------------------------------------------------------------
% From here on, compare Environments at the highest simulated SNR point
Thigh = T(T.SNR == max_snr, :);

%% Figure 5 : BER vs Speed (at max SNR)
figure('Name','BER vs Speed');
[speed_sorted, sidx] = sort(Thigh.Speed);
semilogy(speed_sorted, Thigh.BER(sidx), '-o', 'LineWidth', 2, 'MarkerSize', 8);
grid on;
xlabel('Vehicle Speed (km/hr)'); ylabel('BER');
title(sprintf('BER vs Speed (at SNR = %d dB)', max_snr));
text(speed_sorted, Thigh.BER(sidx), Thigh.Environment(sidx), ...
    'Interpreter','none','VerticalAlignment','bottom','FontSize',8);

%% Figure 6 : Throughput vs Speed (at max SNR)
figure('Name','Throughput vs Speed');
plot(speed_sorted, Thigh.Throughput(sidx)/1e3, '-o', 'LineWidth', 2, 'MarkerSize', 8);
grid on;
xlabel('Vehicle Speed (km/hr)'); ylabel('Throughput (kbps)');
title(sprintf('Throughput vs Speed (at SNR = %d dB)', max_snr));
text(speed_sorted, Thigh.Throughput(sidx)/1e3, Thigh.Environment(sidx), ...
    'Interpreter','none','VerticalAlignment','bottom','FontSize',8);

%% Figure 7 : BER vs Delay Spread (at max SNR)
figure('Name','BER vs Delay Spread');
[ds_sorted, didx] = sort(Thigh.DelaySpread);
semilogy(ds_sorted, Thigh.BER(didx), '-o', 'LineWidth', 2, 'MarkerSize', 8);
grid on;
xlabel('Delay Spread (samples)'); ylabel('BER');
title(sprintf('BER vs Delay Spread (at SNR = %d dB)', max_snr));
text(ds_sorted, Thigh.BER(didx), Thigh.Environment(didx), ...
    'Interpreter','none','VerticalAlignment','bottom','FontSize',8);

%% Figure 8 : BER vs Number of Paths (at max SNR)
figure('Name','BER vs Number of Paths');
bar(categorical(Thigh.Environment), Thigh.BER);
set(gca,'YScale','log'); grid on;
xlabel('Environment'); ylabel('BER');
title(sprintf('BER by Number of Multipaths (at SNR = %d dB)', max_snr));
for e = 1:height(Thigh)
    text(e, Thigh.BER(e), sprintf('Paths=%d', Thigh.NumPaths(e)), ...
        'HorizontalAlignment','center','VerticalAlignment','bottom','FontSize',8);
end

%% Figure 9 : BER vs Doppler Spread (at max SNR)
figure('Name','BER vs Doppler Spread');
[dop_sorted, dopidx] = sort(Thigh.Doppler);
semilogy(dop_sorted, Thigh.BER(dopidx), '-o', 'LineWidth', 2, 'MarkerSize', 8);
grid on;
xlabel('Doppler Spread (taps)'); ylabel('BER');
title(sprintf('BER vs Doppler Spread (at SNR = %d dB)', max_snr));
text(dop_sorted, Thigh.BER(dopidx), Thigh.Environment(dopidx), ...
    'Interpreter','none','VerticalAlignment','bottom','FontSize',8);

%% ---------------------------------------------------------------------
% Environment-level summaries (averaged across all simulated SNR points)
avg_ber = zeros(n_envs,1);
avg_thr = zeros(n_envs,1);
avg_run = zeros(n_envs,1);
for e = 1:n_envs
    idx = strcmp(T.Environment, envs{e});
    avg_ber(e) = mean(T.BER(idx));
    avg_thr(e) = mean(T.Throughput(idx));
    avg_run(e) = mean(T.Runtime(idx));
end

%% Figure 10 : Average BER per Environment
figure('Name','Average BER per Environment');
bar(categorical(envs), avg_ber);
set(gca,'YScale','log'); grid on;
xlabel('Environment'); ylabel('Average BER (all SNR)');
title('Average BER per Environment');

%% Figure 11 : Average Throughput per Environment
figure('Name','Average Throughput per Environment');
bar(categorical(envs), avg_thr/1e3);
grid on;
xlabel('Environment'); ylabel('Average Throughput (kbps)');
title('Average Throughput per Environment');

%% Figure 12 : Average Runtime per Environment
figure('Name','Average Runtime per Environment');
bar(categorical(envs), avg_run);
grid on;
xlabel('Environment'); ylabel('Average Runtime per SNR point (s)');
title('Average Simulation Runtime per Environment');

%% Figure 13 : Heatmap of BER across Environment x SNR
snr_list = unique(T.SNR);
ber_matrix = nan(n_envs, numel(snr_list));
for e = 1:n_envs
    for s = 1:numel(snr_list)
        idx = strcmp(T.Environment, envs{e}) & T.SNR == snr_list(s);
        if any(idx)
            ber_matrix(e,s) = T.BER(idx);
        end
    end
end
figure('Name','BER Heatmap');
imagesc(log10(ber_matrix));
colorbar;
set(gca,'YTick',1:n_envs,'YTickLabel',envs,'TickLabelInterpreter','none');
set(gca,'XTick',1:numel(snr_list),'XTickLabel',string(snr_list));
xlabel('SNR (dB)'); ylabel('Environment');
title('log_{10}(BER) Heatmap: Environment x SNR');

%% Figure 14 : Runtime distribution per Environment (boxplot across SNR points)
figure('Name','Runtime Distribution per Environment');
simple_boxplot(T.Runtime, T.Environment);
grid on;
xlabel('Environment'); ylabel('Runtime (s)');
title('Runtime Distribution per Environment (across SNR sweep)');

%% Figure 15 : Doppler vs Iterations (colored by Environment)
figure('Name','Doppler vs Iterations');
hold on;
for e = 1:n_envs
    idx = strcmp(T.Environment, envs{e});
    scatter(T.Doppler(idx), T.Iterations(idx), 60, colors(e,:), 'filled');
end
hold off; grid on;
xlabel('Doppler Spread (taps)'); ylabel('Average detector iterations');
title('Detector Iterations vs Doppler Spread');
legend(envs, 'Interpreter','none', 'Location','best');

disp('All 15 result graphs generated.');