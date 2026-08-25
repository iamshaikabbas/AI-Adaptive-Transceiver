% =========================================================================
% dt_scenarios_v4.m   [Phase 4 / section 2 + 12]
%
% Builds the PHASE-4 scenario tiers. The final-evaluation scenarios A-D
% (dt_scenarios.m) are NEVER regenerated or modified here.
%
%   TUNING      E-H : threshold/margin/dwell/confidence sweeps ONLY.
%   HELDOUT     I-L : policy & model SELECTION (never used for sweeps).
%   DIFFICULT   M-R : robustness probes with known transition frames.
%
% All operating points stay inside environment_profiles_v2.csv ranges and
% inside the phase-2 dataset lattice (no extrapolation). Seeds documented:
%   tune rng(20260823+4), heldout rng(20260823+5), difficult rng(20260823+6)
%
% Difficult scenarios carry a 'transitions' meta field listing the frame on
% which each condition step begins (robustness delay measurement).
% Outputs: Results/DigitalTwin/scenario_<x>.json/.csv  (x = e..r)
% =========================================================================
clearvars; clc;
outdir = fullfile('Results','DigitalTwin');
if ~exist(outdir,'dir'), mkdir(outdir); end
prof = readtable(fullfile('otfs_ai_pipeline','environment_profiles_v2.csv'));

% ------------------------- TUNING (E-H) ----------------------------------
% NOTE: baseline A-D traces were used ONLY to LOCATE which condition
% regions the current models treat as decision-boundary (Urban 10-25 km/h
% QPSK EVA 1-tap pocket; low-SNR fast segments). Thresholds are never fit
% on A-D. The tuning scenarios COVER those regions with new trajectories.
rng(20260823+4);
u8 = {'Urban','Urban','Urban','Urban','Urban','Urban','Urban','Urban'};
E = build_steps(prof,'urban_boundary', u8, ...
    [11 11 15 15 19 19 23 23], 3, 4, [13 9 13 9 13 9 13 9]);
F = build_drive(prof,'urban_fast_mix',{{'UrbanFast',10},{'Urban',8},{'UrbanFast',6}}, {4 16 4});
G = build_drive(prof,'hsr_night',    {{'HighSpeedRail',14},{'HighSpeedRail',10}}, {4 4});
H = [build_steps(prof,'ped_lowsnr', ...
     {'Pedestrian','Pedestrian','Pedestrian'}, [3 6 9], 6, 4, [16 9 4]), ...
     build_steps(prof,'hwy_lowsnr', ...
     {'Highway','Highway'}, [90 130], 6, 4, [8 5])];

% ------------------------- HELD-OUT (I-L) --------------------------------
rng(20260823+5);
I = build_drive(prof,'urban_evening',{{'Urban',12},{'Urban',12}}, {16 16});
J = build_steps(prof,'urban_boundary_h', u8, ...
    [12 12 16 16 21 21 24 24], 3, 4, [14 10 12 8 11 8 14 8]);
K = build_drive(prof,'hsr_express',  {{'HighSpeedRail',8},{'HighSpeedRail',8},{'HighSpeedRail',8}}, {4 16 4});
L = [build_steps(prof,'qam64_fade', ...
     {'Urban','Urban','Urban'}, [25 40 55], 6, 64, [15 10 6]), ...
     build_steps(prof,'ped_m16', {'Pedestrian','Pedestrian'}, [4 8], 3, 16, [20 10])];

% ------------------------- DIFFICULT (M-R) -------------------------------
rng(20260823+6);   % only used for wobble; steps are deterministic
M = build_steps(prof,'rapid_accel', ...
    {'Pedestrian','Urban','Highway','HighSpeedRail'}, [5 30 100 250], 6, 4);
N = build_steps(prof,'rapid_decel', ...
    {'HighSpeedRail','Highway','Urban','Pedestrian'}, [250 100 30 5], 6, 4);
O = build_steps(prof,'snr_drop', ...
    {'Urban','Urban','Urban','Urban','Urban'}, 40*ones(1,5), 5, 4, ...
    [20 15 10 5 0]);
P = build_steps(prof,'snr_recover', ...
    {'Urban','Urban','Urban','Urban','Urban'}, 40*ones(1,5), 5, 4, ...
    [0 5 10 15 20]);
Q = build_drive(prof,'high_doppler_hsr', {{'HighSpeedRail',24}}, {4});
R = build_steps(prof,'profile_transition', ...
    {'Pedestrian','Urban','UrbanFast'}, [8 35 55], 8, 4);

tiers = { ...
 'E','tune',E;  'F','tune',F;  'G','tune',G;  'H','tune',H; ...
 'I','heldout',I;'J','heldout',J;'K','heldout',K;'L','heldout',L; ...
 'M','difficult',M;'N','difficult',N;'O','difficult',O; ...
 'P','difficult',P;'Q','difficult',Q;'R','difficult',R};
for i = 1:size(tiers,1)
    write_scenario(tiers{i,3}, tiers{i,1}, tiers{i,2}, outdir);
end
fprintf('DONE: %d phase-4 scenarios written\n', size(tiers,1));

% -------------------------------------------------------------------------
function pts = build_drive(prof, name, segments, mods)
% [PHASE-5 NOTE] LEGACY generator for E-R tier files (provenance). The canonical scenario engine is dt_scenarios_lib.m; existing outputs remain the single source of truth.
env_names = strtrim(string(prof.Environment));
pts = struct('t_s',{},'frame',{},'environment',{},'speed_kmph',{}, ...
             'snr_db',{},'delay_profile',{},'doppler_scale',{}, ...
             'modulation',{});
t = 0; frame = 0;
for s = 1:numel(segments)
  env = segments{s}{1};
  n   = segments{s}{2};
  r   = find(env_names == string(env), 1);
  assert(~isempty(r), 'unknown environment %s', env);
  v_lo = prof.SpeedMin(r); v_hi = prof.SpeedMax(r);
  dscale = prof.DopplerScale(r); snr_base = prof.SNRBase(r);
  dprof = char(string(prof.DelayProfile(r)));
  base   = v_lo + rand*(v_hi-v_lo);
  target = v_lo + rand*(v_hi-v_lo);
  steps  = linspace(0,1,n);
  wob = 0.15*(v_hi-v_lo)*sin(2*pi*steps*randi([1 3]));
  speeds = min(max(base + (target-base)*steps + wob, v_lo), v_hi);
  mod = mods(min(s,numel(mods)));
  for k = 1:n
    snr = snr_base + 3*sin(2*pi*t/25) - 3*max(0,sin(2*pi*t/17+1));
    if contains(name,'storm') && rand < 0.10
      snr = snr - 7*rand;
    end
    pts(end+1) = struct('t_s',round(t,3),'frame',frame, ...
        'environment',char(env),'speed_kmph',round(speeds(k),1), ...
        'snr_db',round(snr,2),'delay_profile',dprof, ...
        'doppler_scale',dscale,'modulation',mod); %#ok<AGROW>
    t = t + 1.0; frame = frame + 1;
  end
end
end

% -------------------------------------------------------------------------
function pts = build_steps(prof, name, envs, speeds, n_per, mod, varargin)
% deterministic piecewise-condition scenarios with known transition frames;
% optional varargin{1} = explicit SNR per segment (else profile SNRBase)
env_names = strtrim(string(prof.Environment));
explicit_snr = ~isempty(varargin);
pts = struct('t_s',{},'frame',{},'environment',{},'speed_kmph',{}, ...
             'snr_db',{},'delay_profile',{},'doppler_scale',{}, ...
             'modulation',{});
t = 0; frame = 0;
for s = 1:numel(envs)
  r = find(env_names == string(envs(s)), 1);
  assert(~isempty(r), 'unknown environment %s', envs(s));
  dscale = prof.DopplerScale(r); dprof = char(string(prof.DelayProfile(r)));
  v = speeds(s);
  if explicit_snr, snr = varargin{1}(s); else, snr = prof.SNRBase(r); end
  for k = 1:n_per
    pts(end+1) = struct('t_s',round(t,3),'frame',frame, ...
        'environment',char(envs(s)),'speed_kmph',round(v,1), ...
        'snr_db',round(snr,2),'delay_profile',dprof, ...
        'doppler_scale',dscale,'modulation',mod); %#ok<AGROW>
    t = t + 1.0; frame = frame + 1;
  end
end
end

% -------------------------------------------------------------------------
function write_scenario(pts, name, tier, outdir)
meta = struct('name',sprintf('scenario_%s',lower(name)), ...
              'generator','dt_scenarios_v4.m (phase4)', ...
              'tier',tier,'seed',20260823,'dt_s',1.0, ...
              'n_points',numel(pts), ...
              'profiles_file','otfs_ai_pipeline/environment_profiles_v2.csv');
fid = fopen(fullfile(outdir,sprintf('scenario_%s.json',lower(name))),'w');
fwrite(fid, jsonencode(struct('meta',meta,'points',pts), ...
                       'PrettyPrint', true));
fclose(fid);
T = struct2table(pts);
writetable(T, fullfile(outdir,sprintf('scenario_%s.csv',lower(name))));
fprintf('scenario_%s [%s]: %d points (%s)\n', lower(name), tier, ...
        numel(pts), strjoin(unique({pts.environment}), ','));
end
