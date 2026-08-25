clc;
clear;
close all;

disp('==================================================');
disp('  AI-Assisted OTFS Communication System');
disp('  MATLAB-Centric Architecture with Scenario Gen  ');
disp('  + Detector Sweep + Modulation Sweep + CQI      ');
disp('==================================================');

% ==========================================================================
% CHANGE LOG (this version adds, relative to the original script):
%   1. Detector sweep      : MRC (your existing detector) + LMMSE + MPA
%   2. Modulation sweep     : QPSK (4-QAM), 16-QAM, 64-QAM
%   3. Expanded dataset schema : Modulation, Detector, EVM, SINR_est_dB, CQI
%   4. CQI calculation      : approximate 3GPP-style SINR->CQI mapping
%   5. 12-panel dashboard   : BER/SER/PER/Throughput/SE/Iterations/Runtime/
%                             BER-vs-Speed/PER-distribution + Detector
%                             comparison + Modulation comparison + CQI
%   6. Results folder        : all CSV/PNG outputs now auto-saved under
%                             ./Results/ with a run timestamp
%
% IMPORTANT: LMMSE and MPA are implemented as self-contained local
% functions at the bottom of this file. They do NOT call your existing
% MRC_delay_time_detector.m (which is left untouched and still used for
% the 'MRC' case). Instead they rebuild the equivalent time-domain
% channel matrix directly from `gs` and `L_set` -- the SAME variables
% your original per-sample loop already used to build `r` -- so they
% are consistent with your channel model without depending on the
% internal conventions of MRC_delay_time_detector.m. MPA below is a
% simplified/damped Gaussian message-passing (soft interference
% cancellation) detector in the spirit of low-complexity MP OTFS
% detectors; it is NOT a verbatim reproduction of any single paper's
% algorithm. This file has not been executed against your helper
% functions (Generate_delay_Doppler_channel_parameters.m,
% Gen_discrete_time_channel.m, etc.) since MATLAB is not available in
% this environment -- please sanity-check on a small QUICK_TEST_MODE
% run before doing a full sweep.
% ==========================================================================

rng(1);   % Reproducible; comment out for true randomness

%% ========================================================================
%  MODULE 0 : Master Configuration
%  ========================================================================

%  --- Quick smoke-test toggle --------------------------------------------
%  Flip this on first to confirm the whole pipeline (scenario gen -> sweep
%  -> dataset -> dashboard -> Results export) runs end-to-end quickly,
%  before committing to a full multi-hour sweep.
QUICK_TEST_MODE = false;

%  --- Scenario Generator --------------------------------------------------
USE_SCENARIO_GENERATOR = true;      % TRUE = hundreds of rows (RECOMMENDED)
N_SCENARIOS_PER_ENV    = 20;        % scenarios per env in full-sweep mode
N_SCENARIOS_FOCUSED    = 100;       % scenarios when Python mic focuses on one env
N_FRAM_PER_SCENARIO    = 10;        % Monte-Carlo frames per (scenario,mod,detector,SNR)

%  --- Optional Python Mic Detection (Focus Mode) -------------------------
USE_PYTHON_DETECTION   = false;     % true = use mic (see MODULE 1)
PYTHON_EXE             = 'python';  % or 'python3', or full path
PYTHON_RECORD          = 'record_audio.py';
PYTHON_CLASSIFY        = 'environment_classifier.py';
PYTHON_MAPPER          = 'parameter_mapper.py';
PYTHON_JSON_OUT        = 'detected_environment.json';

%  --- Optional Python AI (runs AFTER dataset is built) -------------------
USE_PYTHON_AI          = false;     % true = call predict.py / dashboard.py
PYTHON_PREDICT         = 'predict.py';
PYTHON_DASHBOARD       = 'dashboard.py';

%  --- Detector sweep -------------------------------------------------------
ENABLE_DETECTOR_SWEEP  = true;
DETECTOR_LIST          = {'MRC', 'LMMSE', 'MPA'};   % detectors to compare
DEFAULT_DETECTOR       = 'MRC';                       % used when sweep is off,
                                                        % and as dashboard baseline
n_ite_MRC              = 50;      % MRC internal iteration budget
MPA_ITERATIONS         = 10;      % message-passing iterations
MPA_DAMPING            = 0.5;     % damping factor (0-1) for MPA convergence

%  --- Modulation sweep -----------------------------------------------------
ENABLE_MOD_SWEEP       = true;
MOD_LIST               = [4, 16, 64];                 % QPSK, 16-QAM, 64-QAM
MOD_NAMES               = containers.Map({4, 16, 64}, {'QPSK', '16QAM', '64QAM'});
DEFAULT_MOD            = 4;                            % used when sweep is off,
                                                        % and as dashboard baseline

%  --- Files / Results folder ------------------------------------------------
ENV_PROFILE_FILE       = 'environment_profiles.csv';
RESULTS_DIR            = 'Results';
if exist(RESULTS_DIR, 'dir') ~= 7
    mkdir(RESULTS_DIR);
end
run_stamp    = char(string(datetime('now', 'Format', 'yyyyMMdd_HHmmss')));
DATASET_FILE = fullfile(RESULTS_DIR, 'OTFS_Dataset.csv');

%  --- OTFS Core Parameters (modulation-independent) -----------------------
N       = 64;               % time symbols
M       = 64;               % subcarriers

car_fre  = 4e9;             % 4 GHz carrier
delta_f  = 15e3;            % 15 kHz subcarrier spacing
T        = 1/delta_f;       % symbol duration
BW       = M * delta_f;     % total bandwidth (Hz)
frame_duration = N * T;     % seconds per OTFS frame

%  --- SNR Sweep ----------------------------------------------------------
SNR_dB = 0:5:30;

%  --- Normalized DFT matrix ----------------------------------------------
Fn = dftmtx(N);
Fn = Fn ./ norm(Fn);

%  --- Apply quick-test overrides -------------------------------------------
if QUICK_TEST_MODE
    fprintf('\n*** QUICK_TEST_MODE is ON: using small scenario/frame/SNR counts ***\n');
    N_SCENARIOS_PER_ENV = 2;
    N_SCENARIOS_FOCUSED = 4;
    N_FRAM_PER_SCENARIO = 2;
    SNR_dB = [0 15 30];
end

%  --- Resolve which detectors / modulations actually run ------------------
if ENABLE_DETECTOR_SWEEP
    detectors_to_run = DETECTOR_LIST;
else
    detectors_to_run = {DEFAULT_DETECTOR};
end

if ENABLE_MOD_SWEEP
    mods_to_run = MOD_LIST;
else
    mods_to_run = DEFAULT_MOD;
end

if isempty(detectors_to_run) || isempty(mods_to_run)
    error('detectors_to_run / mods_to_run resolved to empty -- check DETECTOR_LIST / MOD_LIST.');
end

fprintf('\nDetectors this run   : %s\n', strjoin(detectors_to_run, ', '));
mod_name_list = cellfun(@(m) MOD_NAMES(m), num2cell(mods_to_run), 'UniformOutput', false);
fprintf('Modulations this run : %s\n', strjoin(mod_name_list, ', '));

%% ========================================================================
%  MODULE 1 : Load Environment Profiles + Optional Python Focus
%  ========================================================================
if exist(ENV_PROFILE_FILE, 'file') ~= 2
    error(['Environment profile file not found: %s\n' ...
           'Create it with columns: Environment,SpeedMin,SpeedMax,' ...
           'DelayProfile,DopplerScale,Category'], ENV_PROFILE_FILE);
end

EnvProfiles = readtable(ENV_PROFILE_FILE);
N_profiles  = height(EnvProfiles);

% --- GUARDRAIL #1: fail loudly and clearly if the CSV has no data rows ---
if N_profiles == 0
    error(['%s was found but contains no data rows.\n' ...
           'It must have a header row plus at least one data row with columns:\n' ...
           'Environment,SpeedMin,SpeedMax,DelayProfile,DopplerScale,Category\n' ...
           'Example row: Urban,10,50,EVA,1,MediumMobility'], ENV_PROFILE_FILE);
end

required_cols = {'Environment','SpeedMin','SpeedMax','DelayProfile','DopplerScale','Category'};
missing_cols = setdiff(required_cols, EnvProfiles.Properties.VariableNames);
if ~isempty(missing_cols)
    error(['%s is missing required column(s): %s\n' ...
           'Expected columns: %s'], ENV_PROFILE_FILE, ...
           strjoin(missing_cols, ', '), strjoin(required_cols, ', '));
end

fprintf('\nLoaded %d environment profiles from %s:\n', N_profiles, ENV_PROFILE_FILE);
disp(EnvProfiles);

% --- Optional Python microphone pipeline ----------------------------------
detected_env_name = '';
if USE_PYTHON_DETECTION
    try
        fprintf('\n[Python Focus Mode] Invoking Python mic pipeline...\n');
        cmds = {
            sprintf('%s "%s"', PYTHON_EXE, PYTHON_RECORD);
            sprintf('%s "%s"', PYTHON_EXE, PYTHON_CLASSIFY);
            sprintf('%s "%s"', PYTHON_EXE, PYTHON_MAPPER)
        };
        for k = 1:numel(cmds)
            [st, out] = system(cmds{k});
            if st ~= 0
                error('%s failed (exit %d): %s', cmds{k}, st, strtrim(out));
            end
        end

        fid = fopen(PYTHON_JSON_OUT, 'r');
        raw = fread(fid, inf); fclose(fid);
        py = jsondecode(char(raw'));

        required = {'environment','speed_kmh','delay_profile','doppler_scale'};
        for k = 1:numel(required)
            if ~isfield(py, required{k})
                error('JSON missing field: %s', required{k});
            end
        end

        detected_env_name = py.environment;
        fprintf('    -> Python detected: %s (speed ~%d km/hr)\n', ...
            detected_env_name, py.speed_kmh);
    catch ME
        warning('Python detection failed (%s). Running full sweep.', ME.message);
        detected_env_name = '';
    end
end

%% ========================================================================
%  MODULE 2 : Scenario Generator
%  ========================================================================
Scenarios = struct([]);
scen_count = 0;

if ~isempty(detected_env_name)
    % FOCUS MODE: only the detected environment, many scenarios
    focus_idx = find(strcmp(EnvProfiles.Environment, detected_env_name), 1);
    if isempty(focus_idx)
        warning('Detected env "%s" not in CSV. Reverting to full sweep.', detected_env_name);
        detected_env_name = '';
    else
        n_scen = N_SCENARIOS_FOCUSED;
        prof = EnvProfiles(focus_idx, :);
        fprintf('\n[Scenario Gen] FOCUS mode: %d scenarios for %s\n', n_scen, prof.Environment{1});
        for s = 1:n_scen
            scen_count = scen_count + 1;
            speed = sample_speed_cdf(prof.SpeedMin, prof.SpeedMax);
            Scenarios(scen_count).EnvName      = prof.Environment{1};
            Scenarios(scen_count).Speed        = round(speed);
            Scenarios(scen_count).DelayProfile = prof.DelayProfile{1};
            Scenarios(scen_count).DopplerScale = prof.DopplerScale;
            Scenarios(scen_count).Category     = prof.Category{1};
            Scenarios(scen_count).ScenarioID   = s;
            Scenarios(scen_count).FocusMode    = true;
        end
    end
end

if isempty(detected_env_name)
    % FULL SWEEP: all profiles, standard scenario count
    fprintf('\n[Scenario Gen] FULL mode: %d scenarios per environment\n', N_SCENARIOS_PER_ENV);
    for p = 1:N_profiles
        prof = EnvProfiles(p, :);
        for s = 1:N_SCENARIOS_PER_ENV
            scen_count = scen_count + 1;
            speed = sample_speed_cdf(prof.SpeedMin, prof.SpeedMax);
            Scenarios(scen_count).EnvName      = prof.Environment{1};
            Scenarios(scen_count).Speed        = round(speed);
            Scenarios(scen_count).DelayProfile = prof.DelayProfile{1};
            Scenarios(scen_count).DopplerScale = prof.DopplerScale;
            Scenarios(scen_count).Category     = prof.Category{1};
            Scenarios(scen_count).ScenarioID   = s;
            Scenarios(scen_count).FocusMode    = false;
        end
    end
end

N_scenarios = length(Scenarios);

% --- GUARDRAIL #2: fail loudly if no scenarios were generated ---
if N_scenarios == 0
    error(['No scenarios were generated. This usually means EnvProfiles ' ...
           'was empty, or SpeedMin/SpeedMax values were invalid. ' ...
           'Check %s.'], ENV_PROFILE_FILE);
end

expected_rows = N_scenarios * numel(mods_to_run) * numel(detectors_to_run) * length(SNR_dB);
fprintf('Total scenarios       : %d\n', N_scenarios);
fprintf('Modulations x Detectors: %d x %d\n', numel(mods_to_run), numel(detectors_to_run));
fprintf('Expected dataset rows  : %d\n', expected_rows);
fprintf('Frames per (scen,mod,det,SNR): %d  ->  total frames: %d\n', ...
    N_FRAM_PER_SCENARIO, expected_rows * N_FRAM_PER_SCENARIO);
fprintf(['NOTE: LMMSE/MPA build and solve an %d x %d sparse system per frame.\n' ...
         '      If this run count is too slow, reduce N_SCENARIOS_PER_ENV,\n' ...
         '      N_FRAM_PER_SCENARIO, DETECTOR_LIST or MOD_LIST, or use\n' ...
         '      QUICK_TEST_MODE = true first.\n'], N*M, N*M);

%% ========================================================================
%  MODULE 3 : OTFS Simulation over Scenarios x Modulations x Detectors x SNR
%  ========================================================================
Results = {};
row = 0;
sweep_start_tic = tic;   % cumulative timer for the whole sweep (progress/ETA below)

for iscen = 1:N_scenarios

    env_name      = Scenarios(iscen).EnvName;
    veh_speed     = Scenarios(iscen).Speed;
    delay_prof    = Scenarios(iscen).DelayProfile;
    doppler_scale = Scenarios(iscen).DopplerScale;
    scen_id       = Scenarios(iscen).ScenarioID;

    fprintf('\n>>> Scen %d/%d | %s | Speed=%d km/h | Profile=%s\n', ...
        iscen, N_scenarios, env_name, veh_speed, delay_prof);

    % Probe channel once to size guard interval for THIS scenario
    % (guard interval / data grid do not depend on modulation or detector)
    [~, probe_delay_taps, ~, ~] = Generate_delay_Doppler_channel_parameters(...
        N, M, car_fre, delta_f, T, veh_speed, delay_prof, doppler_scale);

    length_ZP = max(max(probe_delay_taps) + 1, ceil(M/16));
    if length_ZP >= M
        error('Guard %d consumes whole frame (M=%d).', length_ZP, M);
    end

    M_data = M - length_ZP;
    data_grid = zeros(M, N);
    data_grid(1:M_data, 1:N) = 1;
    data_mask = logical(data_grid);
    N_syms_perfram = sum(sum(data_grid));

    % ---- Modulation loop -------------------------------------------------
    for im = 1:numel(mods_to_run)
        M_mod    = mods_to_run(im);
        M_bits   = log2(M_mod);
        mod_name = MOD_NAMES(M_mod);

        eng_sqrt = (M_mod==2) + (M_mod~=2)*sqrt((M_mod-1)/6*(2^2));
        SNR      = 10.^(SNR_dB/10);
        sigma_2  = (abs(eng_sqrt)^2) ./ SNR;

        N_bits_perfram = N_syms_perfram * M_bits;

        omega = 1;
        if M_mod == 64, omega = 0.25; end

        % ---- Detector loop -------------------------------------------------
        for idet = 1:numel(detectors_to_run)
            detector_name = detectors_to_run{idet};

            fprintf('    [Mod=%-5s | Det=%-6s]\n', mod_name, detector_name);

            % ---- SNR loop ---------------------------------------------------
            for iesn0 = 1:length(SNR_dB)
                tic;

                bit_errors_acc    = 0;
                sym_errors_acc    = 0;
                packet_errors_acc = 0;
                iter_acc          = 0;
                evm_acc           = 0;

                for ifram = 1:N_FRAM_PER_SCENARIO
                    %% TX: bits -> QAM -> 2D grid
                    tx_bits = randi([0,1], N_bits_perfram, 1);
                    tx_sym  = qammod(reshape(tx_bits, M_bits, N_syms_perfram), ...
                                     M_mod, 'gray', 'InputType', 'bit');
                    X = Generate_2D_data_grid(N, M, tx_sym, data_grid);

                    %% OTFS Modulation
                    X_tilda = X * Fn';
                    s = reshape(X_tilda, N*M, 1);

                    %% Channel (3GPP profile + speed driven)
                    [chan_coef, delay_taps, Doppler_taps, taps] = ...
                        Generate_delay_Doppler_channel_parameters(...
                        N, M, car_fre, delta_f, T, veh_speed, delay_prof, doppler_scale);

                    delay_spread   = max(delay_taps);
                    num_paths      = taps;
                    doppler_spread = max(abs(Doppler_taps));
                    L_set = unique(delay_taps);
                    gs = Gen_discrete_time_channel(N, M, taps, delay_taps, Doppler_taps, chan_coef);

                    %% Channel output + noise
                    % Vectorized: build the sparse NM x NM time-domain
                    % channel matrix once, then r = H*s. This replaces the
                    % old element-by-element double loop (O(N*M*num_taps)
                    % scalar MATLAB operations per frame), which dominated
                    % the runtime of every sweep. H is reused below by
                    % LMMSE/MPA too, so it is only built ONCE per frame
                    % instead of once per detector.
                    l_max = max(delay_taps);
                    H_time = build_time_domain_channel(gs, L_set, N*M);
                    r = H_time * s;
                    noise = sqrt(sigma_2(iesn0)/2) * (randn(size(s)) + 1i*randn(size(s)));
                    r = r + noise;

                    %% ---- Detector dispatch --------------------------------
                    % nu_ml_tilda / H_tf are only needed by MRC, so they are
                    % now computed only inside that branch instead of on
                    % every single frame regardless of which detector is
                    % actually running.
                    switch detector_name
                        case 'MRC'
                            [nu_ml_tilda] = Gen_delay_time_channel_vectors(N, M, l_max, gs);
                            [H_tf] = Generate_time_frequency_channel_ZP(N, M, gs, L_set);
                            [rx_bits, det_iters, ~] = MRC_delay_time_detector(...
                                N, M, M_data, M_mod, sigma_2(iesn0), data_grid, r, ...
                                H_tf, nu_ml_tilda, L_set, omega, 1, 1, n_ite_MRC);

                        case 'LMMSE'
                            [rx_bits, det_iters] = LMMSE_OTFS_detector(...
                                N, M, M_mod, sigma_2(iesn0), data_mask, r, H_time, Fn);

                        case 'MPA'
                            [rx_bits, det_iters] = MPA_OTFS_detector(...
                                N, M, M_mod, sigma_2(iesn0), data_mask, r, H_time, Fn, ...
                                MPA_ITERATIONS, MPA_DAMPING);

                        otherwise
                            error('Unknown detector: %s', detector_name);
                    end

                    %% Metrics
                    frame_bit_err = sum(xor(rx_bits, tx_bits));
                    bit_errors_acc = bit_errors_acc + frame_bit_err;

                    % SER + EVM: re-modulate detected bits -> compare symbols
                    rx_sym = qammod(reshape(rx_bits, M_bits, N_syms_perfram), ...
                                    M_mod, 'gray', 'InputType', 'bit');
                    sym_errors_acc = sym_errors_acc + sum(rx_sym ~= tx_sym);
                    evm_acc = evm_acc + sqrt(mean(abs(rx_sym - tx_sym).^2) / mean(abs(tx_sym).^2));

                    % PER: packet is lost if ANY bit is wrong
                    if frame_bit_err > 0
                        packet_errors_acc = packet_errors_acc + 1;
                    end

                    iter_acc = iter_acc + det_iters;
                end  % frame loop

                runtime = toc;

                % Averages
                avg_ber = bit_errors_acc / (N_bits_perfram * N_FRAM_PER_SCENARIO);
                avg_ser = sym_errors_acc / (N_syms_perfram * N_FRAM_PER_SCENARIO);
                avg_per = packet_errors_acc / N_FRAM_PER_SCENARIO;
                avg_iter = iter_acc / N_FRAM_PER_SCENARIO;
                avg_evm_pct = 100 * (evm_acc / N_FRAM_PER_SCENARIO);

                % Effective SINR estimate from EVM, and CQI lookup
                sinr_est_dB = -20*log10(max(avg_evm_pct, 1e-6)/100);
                cqi = compute_CQI(sinr_est_dB);

                % Throughput (correct bits per sec, packet-level)
                throughput_bps = N_bits_perfram * (1 - avg_per) / frame_duration;

                % Spectral Efficiency (bps/Hz)
                spectral_eff = throughput_bps / BW;

                % Store
                row = row + 1;
                Results(row, :) = {...
                    env_name, veh_speed, delay_prof, delay_spread, num_paths, ...
                    doppler_spread, mod_name, detector_name, SNR_dB(iesn0), ...
                    avg_ber, avg_ser, avg_per, avg_evm_pct, sinr_est_dB, cqi, ...
                    throughput_bps, spectral_eff, runtime, avg_iter, scen_id, ...
                    Scenarios(iscen).Category, Scenarios(iscen).FocusMode, ...
                    string(datetime('now','Format','yyyy-MM-dd HH:mm:ss'))};

                % --- Cumulative progress / ETA -------------------------------
                % row/expected_rows is a running (cumulative) fraction of
                % all work done so far; elapsed/row gives the running
                % average pace, which is used to project the remaining
                % time. This turns "how long is this taking" into a
                % running percentage instead of only a per-row number.
                elapsed_sweep = toc(sweep_start_tic);
                pct_done      = 100 * row / expected_rows;
                eta_sec       = (elapsed_sweep / row) * (expected_rows - row);

                fprintf('      SNR=%2d dB | BER=%.2e | SER=%.2e | PER=%.3f | EVM=%.1f%% | CQI=%2d | TP=%.2e bps | SE=%.3f | It=%.1f | [%5.1f%% done, elapsed %s, ETA %s]\n',...
                    SNR_dB(iesn0), avg_ber, avg_ser, avg_per, avg_evm_pct, cqi, throughput_bps, spectral_eff, avg_iter, ...
                    pct_done, format_hms(elapsed_sweep), format_hms(eta_sec));
            end  % SNR loop
        end  % detector loop
    end  % modulation loop
end  % scenario loop

%% ========================================================================
%  MODULE 4 : Dataset Assembler
%  ========================================================================

% --- GUARDRAIL #3: sanity check before cell2table ---
if isempty(Results)
    error(['Results is empty - the simulation loop produced no rows. ' ...
           'Check N_scenarios, mods_to_run and detectors_to_run above.']);
end

VarNames = {...
    'Environment','Speed_kmh','DelayProfile','DelaySpread','NumPaths',...
    'DopplerSpread','Modulation','Detector','SNR_dB','BER','SER','PER',...
    'EVM_percent','SINR_est_dB','CQI','Throughput_bps',...
    'SpectralEfficiency_bps_per_Hz','Runtime_sec','AvgIterations',...
    'ScenarioID','Category','FocusMode','Timestamp'};

ResultsTable = cell2table(Results, 'VariableNames', VarNames);

% Append if schema matches an existing dataset in the Results folder
if exist(DATASET_FILE, 'file') == 2
    try
        old = readtable(DATASET_FILE);
        if isequal(sort(string(old.Properties.VariableNames)), ...
                   sort(string(ResultsTable.Properties.VariableNames)))
            ResultsTable = [old; ResultsTable(:, old.Properties.VariableNames)];
            fprintf('\nAppended to existing %s. ', DATASET_FILE);
        else
            DATASET_FILE = fullfile(RESULTS_DIR, 'OTFS_Dataset_new.csv');
            fprintf('\nSchema mismatch (old dataset used the pre-expansion schema). Saving to %s. ', DATASET_FILE);
        end
    catch
    end
end

writetable(ResultsTable, DATASET_FILE);
% Also keep a timestamped snapshot of exactly this run
snapshot_file = fullfile(RESULTS_DIR, sprintf('OTFS_Dataset_%s.csv', run_stamp));
writetable(cell2table(Results, 'VariableNames', VarNames), snapshot_file);
fprintf('Dataset saved: %s (%d rows)\n', DATASET_FILE, height(ResultsTable));
fprintf('Run snapshot saved: %s\n', snapshot_file);

%% ========================================================================
%  MODULE 5 : Graph Generator (12-panel Dashboard + comparison figures)
%  ========================================================================
fprintf('\n[Graph Generator] Building dashboard...\n');

env_list = unique(ResultsTable.Environment);
n_env    = length(env_list);
colors   = lines(max([n_env, numel(DETECTOR_LIST), numel(mod_name_list)]));
markers  = {'o','s','^','d','v','>','p','h','x'};

% Baseline slice (one detector, one modulation) used for the "classic"
% per-environment panels 1-9, so those curves reflect one consistent
% radio configuration rather than an average across mixed configs.
baseline_mod = MOD_NAMES(DEFAULT_MOD);
baseline_det = DEFAULT_DETECTOR;
baseline_idx = strcmp(ResultsTable.Detector, baseline_det) & strcmp(ResultsTable.Modulation, baseline_mod);
BaselineTable = ResultsTable(baseline_idx, :);
if isempty(BaselineTable)
    warning('Baseline (Detector=%s, Modulation=%s) not present in results; using full table for panels 1-9.', baseline_det, baseline_mod);
    BaselineTable = ResultsTable;
end

figure('Name','OTFS Performance Dashboard','Position',[50 50 1700 1150]);

% --- 1. BER vs SNR ---
subplot(4,3,1); hold on; grid on; set(gca,'YScale','log');
for i = 1:n_env
    [u, v] = avg_by_filter(BaselineTable, 'Environment', env_list{i}, 'BER');
    plot(u, v, [markers{mod(i-1,9)+1},'-'], 'Color',colors(i,:), 'LineWidth',1.5, 'DisplayName',env_list{i});
end
xlabel('SNR (dB)'); ylabel('BER'); title(sprintf('Bit Error Rate (%s/%s)', baseline_det, baseline_mod));
legend('Location','southwest');

% --- 2. SER vs SNR ---
subplot(4,3,2); hold on; grid on; set(gca,'YScale','log');
for i = 1:n_env
    [u, v] = avg_by_filter(BaselineTable, 'Environment', env_list{i}, 'SER');
    plot(u, v, [markers{mod(i-1,9)+1},'-'], 'Color',colors(i,:), 'LineWidth',1.5, 'DisplayName',env_list{i});
end
xlabel('SNR (dB)'); ylabel('SER'); title('Symbol Error Rate');
legend('Location','southwest');

% --- 3. PER vs SNR ---
subplot(4,3,3); hold on; grid on;
for i = 1:n_env
    [u, v] = avg_by_filter(BaselineTable, 'Environment', env_list{i}, 'PER');
    plot(u, v, [markers{mod(i-1,9)+1},'-'], 'Color',colors(i,:), 'LineWidth',1.5, 'DisplayName',env_list{i});
end
xlabel('SNR (dB)'); ylabel('PER'); title('Packet Error Rate');
legend('Location','southwest');

% --- 4. Throughput vs SNR ---
subplot(4,3,4); hold on; grid on;
for i = 1:n_env
    [u, v] = avg_by_filter(BaselineTable, 'Environment', env_list{i}, 'Throughput_bps');
    plot(u, v/1e3, [markers{mod(i-1,9)+1},'-'], 'Color',colors(i,:), 'LineWidth',1.5, 'DisplayName',env_list{i});
end
xlabel('SNR (dB)'); ylabel('Throughput (kbps)'); title('Throughput');
legend('Location','southeast');

% --- 5. Spectral Efficiency vs SNR ---
subplot(4,3,5); hold on; grid on;
for i = 1:n_env
    [u, v] = avg_by_filter(BaselineTable, 'Environment', env_list{i}, 'SpectralEfficiency_bps_per_Hz');
    plot(u, v, [markers{mod(i-1,9)+1},'-'], 'Color',colors(i,:), 'LineWidth',1.5, 'DisplayName',env_list{i});
end
xlabel('SNR (dB)'); ylabel('SE (bps/Hz)'); title('Spectral Efficiency');
legend('Location','southeast');

% --- 6. Detector Iterations vs SNR ---
subplot(4,3,6); hold on; grid on;
for i = 1:n_env
    [u, v] = avg_by_filter(BaselineTable, 'Environment', env_list{i}, 'AvgIterations');
    plot(u, v, [markers{mod(i-1,9)+1},'-'], 'Color',colors(i,:), 'LineWidth',1.5, 'DisplayName',env_list{i});
end
xlabel('SNR (dB)'); ylabel('Iterations'); title('Detector Iterations');
legend('Location','northeast');

% --- 7. Runtime vs SNR ---
subplot(4,3,7); hold on; grid on;
for i = 1:n_env
    [u, v] = avg_by_filter(BaselineTable, 'Environment', env_list{i}, 'Runtime_sec');
    plot(u, v, [markers{mod(i-1,9)+1},'-'], 'Color',colors(i,:), 'LineWidth',1.5, 'DisplayName',env_list{i});
end
xlabel('SNR (dB)'); ylabel('Runtime (s)'); title('Simulation Runtime');
legend('Location','northwest');

% --- 8. BER vs Speed (scatter, color = SNR) ---
subplot(4,3,8); hold on; grid on; set(gca,'YScale','log');
scatter(BaselineTable.Speed_kmh, BaselineTable.BER, 25, BaselineTable.SNR_dB, 'filled');
colormap(gca, jet); colorbar('Label','SNR (dB)');
xlabel('Speed (km/h)'); ylabel('BER'); title('BER vs Speed');

% --- 9. PER Distribution by Environment ---
subplot(4,3,9);
boxplot(BaselineTable.PER, BaselineTable.Environment);
ylabel('PER'); title('PER Distribution'); xtickangle(30);

% --- 10. BER vs SNR by Detector (fixed env + modulation) ---
subplot(4,3,10); hold on; grid on; set(gca,'YScale','log');
det_env  = env_list{1};
det_slice = ResultsTable(strcmp(ResultsTable.Environment, det_env) & strcmp(ResultsTable.Modulation, baseline_mod), :);
for i = 1:numel(DETECTOR_LIST)
    [u, v] = avg_by_filter(det_slice, 'Detector', DETECTOR_LIST{i}, 'BER');
    if ~isempty(u)
        plot(u, v, [markers{mod(i-1,9)+1},'-'], 'Color',colors(i,:), 'LineWidth',1.5, 'DisplayName',DETECTOR_LIST{i});
    end
end
xlabel('SNR (dB)'); ylabel('BER'); title(sprintf('Detector Comparison (%s, %s)', det_env, baseline_mod));
legend('Location','southwest');

% --- 11. BER vs SNR by Modulation (fixed env + detector) ---
subplot(4,3,11); hold on; grid on; set(gca,'YScale','log');
mod_slice = ResultsTable(strcmp(ResultsTable.Environment, det_env) & strcmp(ResultsTable.Detector, baseline_det), :);
for i = 1:numel(mod_name_list)
    [u, v] = avg_by_filter(mod_slice, 'Modulation', mod_name_list{i}, 'BER');
    if ~isempty(u)
        plot(u, v, [markers{mod(i-1,9)+1},'-'], 'Color',colors(i,:), 'LineWidth',1.5, 'DisplayName',mod_name_list{i});
    end
end
xlabel('SNR (dB)'); ylabel('BER'); title(sprintf('Modulation Comparison (%s, %s)', det_env, baseline_det));
legend('Location','southwest');

% --- 12. CQI vs SNR by Environment ---
subplot(4,3,12); hold on; grid on;
for i = 1:n_env
    [u, v] = avg_by_filter(BaselineTable, 'Environment', env_list{i}, 'CQI');
    plot(u, v, [markers{mod(i-1,9)+1},'-'], 'Color',colors(i,:), 'LineWidth',1.5, 'DisplayName',env_list{i});
end
xlabel('SNR (dB)'); ylabel('CQI (0-15)'); ylim([0 15]); title('CQI vs SNR');
legend('Location','southeast');

sgtitle(sprintf('OTFS Dashboard | %d Scenarios | %s', N_scenarios, run_stamp));

dashboard_file = fullfile(RESULTS_DIR, sprintf('OTFS_Dashboard_%s.png', run_stamp));
saveas(gcf, dashboard_file);
saveas(gcf, fullfile(RESULTS_DIR, 'OTFS_Dashboard_latest.png'));
fprintf('Dashboard saved: %s\n', dashboard_file);

% --- Standalone Detector comparison figure (BER/SER/PER/Throughput) ---
figure('Name','Detector Comparison','Position',[100 100 1100 800]);
metrics = {'BER','SER','PER','Throughput_bps'};
titles  = {'BER','SER','PER','Throughput (bps)'};
for mi = 1:4
    subplot(2,2,mi); hold on; grid on;
    if mi <= 3, set(gca,'YScale','log'); end
    for i = 1:numel(DETECTOR_LIST)
        [u, v] = avg_by_filter(det_slice, 'Detector', DETECTOR_LIST{i}, metrics{mi});
        if ~isempty(u)
            plot(u, v, [markers{mod(i-1,9)+1},'-'], 'Color',colors(i,:), 'LineWidth',1.5, 'DisplayName',DETECTOR_LIST{i});
        end
    end
    xlabel('SNR (dB)'); ylabel(titles{mi}); title(titles{mi}); legend('Location','best');
end
sgtitle(sprintf('Detector Comparison | %s | %s', det_env, baseline_mod));
saveas(gcf, fullfile(RESULTS_DIR, sprintf('OTFS_DetectorComparison_%s.png', run_stamp)));
saveas(gcf, fullfile(RESULTS_DIR, 'OTFS_DetectorComparison_latest.png'));

% --- Standalone Modulation comparison figure (BER/SER/PER/Throughput) ---
figure('Name','Modulation Comparison','Position',[150 150 1100 800]);
for mi = 1:4
    subplot(2,2,mi); hold on; grid on;
    if mi <= 3, set(gca,'YScale','log'); end
    for i = 1:numel(mod_name_list)
        [u, v] = avg_by_filter(mod_slice, 'Modulation', mod_name_list{i}, metrics{mi});
        if ~isempty(u)
            plot(u, v, [markers{mod(i-1,9)+1},'-'], 'Color',colors(i,:), 'LineWidth',1.5, 'DisplayName',mod_name_list{i});
        end
    end
    xlabel('SNR (dB)'); ylabel(titles{mi}); title(titles{mi}); legend('Location','best');
end
sgtitle(sprintf('Modulation Comparison | %s | %s', det_env, baseline_det));
saveas(gcf, fullfile(RESULTS_DIR, sprintf('OTFS_ModulationComparison_%s.png', run_stamp)));
saveas(gcf, fullfile(RESULTS_DIR, 'OTFS_ModulationComparison_latest.png'));

fprintf('All figures saved under: %s\n', RESULTS_DIR);

%% ========================================================================
%  MODULE 6 : Optional Python AI (Prediction + Dashboard)
%  ========================================================================
if USE_PYTHON_AI
    fprintf('\n[Python AI] Calling prediction pipeline...\n');
    temp_csv = fullfile(RESULTS_DIR, 'temp_for_python.csv');
    writetable(ResultsTable, temp_csv);

    cmd = sprintf('%s "%s" --input "%s"', PYTHON_EXE, PYTHON_PREDICT, temp_csv);
    [st, out] = system(cmd);
    if st == 0
        fprintf('Python prediction OK.\n%s\n', strtrim(out));
        system(sprintf('%s "%s" &', PYTHON_EXE, PYTHON_DASHBOARD));  % non-blocking
    else
        try
            logfn = fullfile(RESULTS_DIR, 'python_ai_error.txt');
            fid = fopen(logfn, 'w');
            if fid ~= -1
                fprintf(fid, 'Command: %s\n\n', cmd);
                fprintf(fid, 'ExitStatus: %d\n\n', st);
                fprintf(fid, 'Output:\n%s\n', out);
                fclose(fid);
                fprintf('Wrote Python AI stderr/stdout to %s\n', logfn);
            end
        catch
        end

        try
            if isempty(ResultsTable) || width(ResultsTable)==0 || height(ResultsTable)==0
                warning(['ResultsTable appears empty or malformed. ', ...
                    'Ensure environment profiles loaded and ResultsTable was constructed with matching VariableNames.']);
            end
        catch
        end
        warning('Python AI failed (exit %d): %s', st, strtrim(out));
    end
else
    fprintf('\n[Python AI] Skipped. Set USE_PYTHON_AI = true to enable.\n');
end

fprintf('\n=== ALL MODULES COMPLETE ===\n');
fprintf('Dataset : %s\n', DATASET_FILE);
fprintf('Figures : %s\n', RESULTS_DIR);
return

%% ========================================================================
%  LOCAL FUNCTIONS  (must appear after all script-level code in MATLAB)
%  ========================================================================

function [u_snr, avg_val] = avg_by_filter(tbl, filterCol, filterVal, colname)
% Average `colname` over SNR_dB for rows where tbl.(filterCol) == filterVal.
% filterCol may hold char/string/cellstr data (Environment, Detector,
% Modulation are all stored this way).
    idx = strcmp(string(tbl.(filterCol)), string(filterVal));
    snr = tbl.SNR_dB(idx);
    val = tbl.(colname)(idx);
    if isempty(snr)
        u_snr = []; avg_val = [];
        return;
    end
    [u_snr, ~, ic] = unique(snr);
    avg_val = accumarray(ic, val, [], @mean);
end

function cqi = compute_CQI(sinr_dB)
% Approximate 3GPP-style SINR -> CQI (0-15) mapping. CQI 0 means the
% link cannot reliably sustain even the most robust MCS (CQI 1).
% Thresholds are commonly-cited approximate values, not the verbatim
% 3GPP 36.213 table -- adjust to your target spec if needed.
    thresholds = [-6.7 -4.7 -2.3 0.2 2.4 4.3 5.9 8.1 10.3 11.7 14.1 16.3 18.7 21.0 22.7];
    cqi = 0;
    for k = 1:numel(thresholds)
        if sinr_dB >= thresholds(k)
            cqi = k;
        end
    end
end

function speed = sample_speed_cdf(speed_min, speed_max)
% Sample a per-scenario vehicle speed using inverse-CDF (cumulative
% frequency) sampling instead of a flat uniform draw.
%
% The old code did speed = SpeedMin + rand()*(SpeedMax-SpeedMin), which
% spreads speeds FLAT across the whole range -- e.g. for a "Highway"
% profile of 60-120 km/h it is just as likely to generate 61 km/h as
% 90 km/h, which does not match how real traffic speeds cluster around
% a typical/cruising value. Here a triangular distribution peaked at
% the midpoint of [SpeedMin, SpeedMax] is used instead: its CDF is
% inverted analytically (piecewise-quadratic inverse) so that a single
% rand() draw maps to a speed that is far more likely to land near the
% middle of the range than at either extreme, while still respecting
% the exact SpeedMin/SpeedMax bounds from environment_profiles.csv.
    if speed_max <= speed_min
        speed = speed_min;
        return;
    end
    mode = (speed_min + speed_max) / 2;             % peak of the distribution
    Fc   = (mode - speed_min) / (speed_max - speed_min);  % CDF value at the mode

    u = rand();
    if u < Fc
        speed = speed_min + sqrt(u * (speed_max - speed_min) * (mode - speed_min));
    else
        speed = speed_max - sqrt((1 - u) * (speed_max - speed_min) * (speed_max - mode));
    end
end

function str = format_hms(total_seconds)
% Format a duration in seconds as HH:MM:SS for progress/ETA printing.
    total_seconds = max(total_seconds, 0);
    h = floor(total_seconds / 3600);
    m = floor(mod(total_seconds, 3600) / 60);
    s = floor(mod(total_seconds, 60));
    str = sprintf('%02d:%02d:%02d', h, m, s);
end

function H = build_time_domain_channel(gs, L_set, NM)
% Rebuild the sparse NM x NM time-domain channel matrix H such that
% r = H*s (+ noise), using EXACTLY the same (gs, L_set) convention as
% the per-sample loop:  r(q) = r(q) + gs(l,q) * s(q-l+1)  for l in L_set+1.
    rows = []; cols = []; vals = [];
    for l = (L_set(:)' + 1)
        q_idx = l:NM;
        rows = [rows, q_idx]; %#ok<AGROW>
        cols = [cols, q_idx - l + 1]; %#ok<AGROW>
        vals = [vals, gs(l, q_idx)]; %#ok<AGROW>
    end
    H = sparse(rows, cols, vals, NM, NM);
end

function [rx_bits, iters] = LMMSE_OTFS_detector(N, M, M_mod, sigma2, data_mask, r, H, Fn)
% Linear MMSE detector operating directly on the time-domain equivalent
% channel H (built once by the caller and reused across detectors),
% then mapped back to the delay-Doppler domain via the inverse OTFS
% transform to read off the data symbols.
    NM = N*M;

    A = H'*H + sigma2*speye(NM);
    b = H'*r;
    s_hat = A \ b;

    X_tilda_hat = reshape(s_hat, M, N);
    X_hat = X_tilda_hat * Fn;              % inverse of X_tilda = X*Fn' (Fn unitary)

    rx_sym = X_hat(data_mask);
    M_bits = log2(M_mod);
    rx_bits_mat = qamdemod(rx_sym, M_mod, 'gray', 'OutputType', 'bit');
    rx_bits = reshape(rx_bits_mat, [], 1);
    iters = 1;  % closed-form solve
end

function [rx_bits, iters] = MPA_OTFS_detector(N, M, M_mod, sigma2, data_mask, r, H, Fn, max_iter, damping)
% Simplified / damped Gaussian message-passing (soft interference
% cancellation) detector. Iteratively refines a time-domain symbol
% estimate using gradient steps towards the LS/LMMSE solution, then
% "slices" each sample towards the nearest constellation points using a
% soft (belief-weighted) expectation that sharpens each iteration. This
% approximates the behaviour of low-complexity MP OTFS detectors without
% reproducing a specific paper's exact factor-graph update equations.
% H is built once by the caller (per frame) and passed in, rather than
% being rebuilt here from gs/L_set a second time.
    NM = N*M;

    const = qammod((0:M_mod-1)', M_mod, 'gray');
    const = const / sqrt(mean(abs(const).^2));    % unit average energy

    % Lipschitz-ish step size from an operator-norm estimate of H
    Hn = normest(H, 1e-2);
    step = 1 / (Hn^2 + sigma2 + eps);

    s_est = zeros(NM, 1);
    T0 = mean(abs(const).^2) * 2;   % initial "temperature" (belief spread)

    for it = 1:max_iter
        residual = r - H*s_est;
        grad = H' * residual;
        s_grad = s_est + step*grad;

        % Soft slicing: belief-weighted expectation over the constellation,
        % with temperature annealed down each iteration (sharper beliefs
        % as we iterate -> approaches hard decision at convergence).
        Tk = max(T0 / it, sigma2/4 + 1e-6);
        diffs = abs(s_grad - const.');            % NM x M_mod
        weights = exp(-(diffs.^2) / Tk);
        weights = weights ./ max(sum(weights, 2), eps);
        s_soft = weights * const;

        s_est = damping*s_soft + (1-damping)*s_est;
    end

    X_tilda_hat = reshape(s_est, M, N);
    X_hat = X_tilda_hat * Fn;

    rx_sym = X_hat(data_mask);
    M_bits = log2(M_mod); %#ok<NASGU>
    rx_bits_mat = qamdemod(rx_sym, M_mod, 'gray', 'OutputType', 'bit');
    rx_bits = reshape(rx_bits_mat, [], 1);
    iters = max_iter;
end