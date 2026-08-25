function run_all_comparisons()
% =========================================================================
% RUN_ALL_COMPARISONS   Master runner for the 9 waveform comparisons.
%
% Implemented as a FUNCTION so its loop state survives the per-script
% `clearvars` (each compare_* script runs via evalin('base',...) and thus
% only touches the base workspace, never this function's variables).
% A failure in one script is reported and does not abort the rest.
% All artifacts are written to Results\WaveformComparison\.
% =========================================================================
outdir = fullfile('Results','WaveformComparison');
if ~exist(outdir,'dir'), mkdir(outdir); end

scripts = {'compare_otfs_oddm_snr', ...
           'compare_otfs_oddm_velocity', ...
           'compare_otfs_oddm_doppler', ...
           'compare_otfs_oddm_channel', ...
           'compare_otfs_oddm_environment', ...
           'compare_otfs_oddm_multipath', ...
           'compare_otfs_oddm_modulation', ...
           'compare_otfs_oddm_detector', ...
           'compare_otfs_oddm_runtime'};

nOK = 0; nFail = 0; failures = {};
t_all = tic;
for k = 1:numel(scripts)
    fprintf('\n########## [%d/%d] %s ##########\n', k, numel(scripts), scripts{k});
    t_k = tic;
    try
        evalin('base', ['clearvars; clc; ' scripts{k}]);
        nOK = nOK + 1;
        fprintf('--> %s OK (%.1f s)\n', scripts{k}, toc(t_k));
    catch err
        nFail = nFail + 1;
        failures{end+1} = sprintf('%s: %s', scripts{k}, err.message);
        fprintf(2, '--> %s FAILED: %s\n', scripts{k}, err.message);
    end
    savefig_progress(outdir, nOK + nFail);
end
fprintf('\n=== COMPARISONS COMPLETE: %d OK, %d failed (%.1f min) ===\n', ...
    nOK, nFail, toc(t_all)/60);
if nFail > 0
    for k = 1:numel(failures), fprintf('  FAIL %s\n', failures{k}); end
end
close all force;
end

function savefig_progress(outdir, k)
try
    savefig(fullfile(outdir, sprintf('_progress_%02d.fig', k)));
catch
    % progress snapshot is best-effort only
end
end
