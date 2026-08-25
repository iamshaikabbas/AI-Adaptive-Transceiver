function C = dt_config(mode)
% =========================================================================
% DT_CONFIG   Digital-Twin condition model + experiment configuration
% (Phase 2). Single source of truth for environments, sweep axes, split
% design and compute budget. FAST mode = small development grids;
% FULL mode = complete Phase 2 matrix.
%
% Everything here is a SIMULATION choice -- not a claim of measured
% real-world behaviour.
%
% Condition model (one wireless state):
%   t_s, frame, environment, speed_kmph, snr_db,
%   doppler_hz          DERIVED = (speed/3.6)*carrier/c * doppler_scale
%                       (never assigned independently; see dt_derive_doppler)
%   carrier_frequency_hz (default 4 GHz = repo default car_fre),
%   bandwidth_hz         (= M*delta_f = 480 kHz),
%   channel_profile      EPA | EVA | ETU   (existing generator only),
%   delay_spread_taps, num_paths   (from the profile's realized taps),
%   modulation           4 | 16 (| 64 FULL slice),
%   detector             deployment defaults only (twin_default_detector),
%   waveform             OTFS | ODDM,
%   optional impairments cfg.cfo_hz / cfg.phase_offset_rad /
%                        cfg.timing_offset_samples (default all ZERO;
%                        primary matrix runs impairment-free).
%
% Split design (leak-free by construction):
%   train : SNR in  [-10 -5 0 5 10 15 20], speed in [0 20 60 100 150 200 300]
%   val   : deterministic 20% holdout of TRAIN conditions (rng seeded)
%   test  : UNSEEN axis values SNR in [-3 2 7 12 17 22],
%                             speed in [10 40 80 120 250 350]
% =========================================================================

if nargin < 1 || isempty(mode), mode = 'fast'; end

C.mode = lower(mode);
assert(any(strcmp(C.mode, {'fast','full'})), 'mode must be fast|full');

% ---- radio ---------------------------------------------------------------
C.carrier_hz   = 4e9;                 % ONE default carrier for main experiments
C.carrier_alts = [2e9 3.5e9 5.9e9];   % configurable alternatives
C.delta_f      = 15e3;
C.N = 32;  C.M = 32;
C.bandwidth_hz = C.M * C.delta_f;     % 480 kHz

% ---- objectives ----------------------------------------------------------
C.objective      = 'ACS';    % 'ACS' (max) or 'BER' (min): best_waveform rule
C.tie_tol_acs    = 0.005;    % |dACS| below this -> 'tie'
C.tie_tol_ber_rel= 0.10;     % relative BER gap below this -> 'tie'

% ---- sweep axes ----------------------------------------------------------
C.snr_all   = -10:2:24;                                    % complete range
C.snr_fast  = [-5 0 5 10 15 20];                           % development set
C.speeds_all= [0 5 20 40 60 80 100 120 150 200 250 300 350];
C.profiles  = {'EPA','EVA','ETU'};
C.mods_fast = [4 16];

% ---- split lattices (disjoint axis values => no leakage) ------------------
C.snr_train   = [-10 -5 0 5 10 15 20];
C.snr_test    = [ -3  2 7 12 17 22];
C.speed_train = [0 20 60 100 150 200 300];
C.speed_test  = [10 40 80 120 250 350];

% ---- trials ----------------------------------------------------------------
if strcmp(C.mode, 'fast'), C.nTrials = 2; else, C.nTrials = 3; end

% ---- waveform/detector combos (deployment defaults, both validated) -------
C.combos = struct('name', {'OTFS (MRC)', 'ODDM (LMMSE)'}, ...
                  'wf',   {'OTFS', 'ODDM'}, ...
                  'det',  {'MRC',  'LMMSE'});

% ---- optional impairments (OFF for the primary matrix) ---------------------
C.impairments = struct('cfo_hz', 0, 'phase_offset_rad', 0, ...
                       'timing_offset_samples', 0);

% ---- environments (configurable simulation ranges) -------------------------
%   name, speed bounds, natural profile set, SNR baseline for scenarios.
env = struct('name', {}, 'vmin', {}, 'vmax', {}, 'profiles', {}, ...
             'snr_base', {});
env(1) = struct('name','Pedestrian',    'vmin',0, 'vmax',10, ...
                'profiles',{{'EPA'}},      'snr_base',20);
env(2) = struct('name','Urban',         'vmin',10,'vmax',60, ...
                'profiles',{{'ETU','EVA'}},'snr_base',15);
env(3) = struct('name','Highway',       'vmin',60,'vmax',140, ...
                'profiles',{{'EVA'}},      'snr_base',12);
env(4) = struct('name','HighSpeedRail', 'vmin',140,'vmax',350, ...
                'profiles',{{'EVA'}},      'snr_base',8);
C.environments = env;

% NOTE (documented assumption): v1 mapped Highway/HSR -> ETU. Measured
% Phase-1 data (cmp_channel) shows ETU favours OTFS while EVA at speed
% favours ODDM; assigning ETU to 300 km/h links is also physically odd.
% v2 therefore uses EVA for vehicular/rail bands (3GPP-consistent) while
% keeping every profile reachable through the explicit profile axis.

% ---- 64-QAM slice (FULL mode only, modest budget) ---------------------------
C.include_64qam_slice = strcmp(C.mode, 'full');
C.qam64_speeds = [60 150 300];
C.qam64_snrs   = [0 10 20];

% ---- carrier-sensitivity slice (FULL mode) ----------------------------------
C.carrier_slice = strcmp(C.mode, 'full');   % fc in {2,5.9} GHz mini-grid

% ---- seeds / reproducibility -------------------------------------------------
C.rng_seed = 20260823;

% ---- output locations ----------------------------------------------------------
C.outdir = fullfile('Results', 'WaveformComparison');
C.dt_dir = fullfile('Results', 'DigitalTwin');
end
