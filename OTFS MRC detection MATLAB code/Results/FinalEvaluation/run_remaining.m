% run_remaining.m -- Run remaining scenarios F-R
clearvars; clc;

here = fileparts(mfilename('fullpath'));
matlabRoot = fullfile(here, '..', '..');
addpath(matlabRoot);

fprintf('=== PHASE 6: REMAINING SCENARIOS F-R ===\n');

scenarios = {'F','G','H','I','J','K','L','M','N','O','P','Q','R'};
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

fprintf('\n=== REMAINING SCENARIOS COMPLETE in %.1f min ===\n', ...
    toc(t_total)/60);
