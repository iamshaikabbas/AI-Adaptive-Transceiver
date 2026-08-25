% run_full_dataset.m -- Phase 6: Run all 18 scenarios (A-R) in FULL mode
% Uses run_experiment as the canonical runner.
% Script lives in Results/FinalEvaluation/ so we addpath up to MATLAB root.
clearvars; clc;

here = fileparts(mfilename('fullpath'));
matlabRoot = fullfile(here, '..', '..');
addpath(matlabRoot);

fprintf('=== PHASE 6: FULL DATASET GENERATION ===\n');
fprintf('MATLAB root: %s\n', matlabRoot);
fprintf('Policy: phase3 | Seed: 20260823 | Mode: FULL\n\n');

scenarios = {'A','B','C','D','E','F','G','H','I','J','K','L','M','N','O','P','Q','R'};
t_total = tic;

for i = 1:numel(scenarios)
    fprintf('\n--- [%d/%d] Scenario %s ---\n', i, numel(scenarios), scenarios{i});
    try
        s = tic;
        run_experiment(scenarios{i}, 'mode', 'FULL', 'policy', 'phase3', ...
                       'seed0', 20260823);
        fprintf('Scenario %s DONE in %.1f min\n', scenarios{i}, toc(s)/60);
    catch me
        fprintf('ERROR in scenario %s: %s\n', scenarios{i}, me.message);
    end
end

fprintf('\n=== PHASE 6 FULL DATASET GENERATION COMPLETE in %.1f min ===\n', ...
    toc(t_total)/60);
