% =========================================================================
% dt_scenarios.m   [Phase 2 / STEP 8]
%
% Digital-Twin scenario generator v2. Produces four deterministic drive
% scenarios (A-D) as JSON + CSV, using environment_profiles_v2.csv ranges
% (Highway/HSR now physically map to EVA; SNRBase per environment).
%
% Point schema matches ScenarioPoint (scenario.py) and the pt struct that
% twin_run_frame.m / ai_decide_frame.m consume:
%   t_s, frame, environment, speed_kmph, snr_db,
%   delay_profile, doppler_scale, modulation
%
% Presets:
%   A commute        : Urban -> Highway -> Urban, QPSK with one 16-QAM stretch
%   B high_speed_rail: HSR -> Urban -> HSR, QPSK
%   C pedestrian_day : Pedestrian -> Urban mixed, QPSK/16-QAM alternation
%   D stress         : rapid env switches, deep fades, mod flips
%
% Outputs: Results/DigitalTwin/scenario_<x>.json/.csv (+ smoke frame row)
% =========================================================================
clearvars; clc;
rng(20260823);
outdir = fullfile('Results','DigitalTwin');
if ~exist(outdir,'dir'), mkdir(outdir); end

prof = readtable(fullfile('otfs_ai_pipeline','environment_profiles_v2.csv'));

scenA = build_drive(prof,'commute',         {{'Urban',20},{'Highway',25},{'Urban',15}}, {4 4 16});
scenB = build_drive(prof,'high_speed_rail', {{'HighSpeedRail',40},{'Urban',10},{'HighSpeedRail',10}}, {4 16 4});
scenC = build_drive(prof,'pedestrian_day',  {{'Pedestrian',30},{'Urban',20},{'Pedestrian',10}}, {4 16 4});
scenD = build_drive(prof,'stress',          {{'Urban',8},{'Highway',6},{'Pedestrian',5},{'HighSpeedRail',9},{'Urban',7},{'Highway',5},{'Pedestrian',6},{'Urban',14}}, {4 16 4 64 16 64 4 4});

names = {'A','B','C','D'};
S = {scenA, scenB, scenC, scenD};
for i = 1:4
  write_scenario(S{i}, names{i}, outdir);
end

% ---- compatibility smoke frame: scenario A point 1 through twin_run_frame --
cfg_base = sim_default_config();
cfg_base.TwinStrategy = 'smoke';
pt1 = scenA(1);
[row, res] = twin_run_frame(pt1, cfg_base, 'OTFS', ...
                            twin_default_detector('OTFS'), 20260823, struct());
fprintf(['SMOKE: frame BER=%.4g PER=%.4g throughput=%.0f bps ' ...
         '(error_flag=%d)\n'], row.BER, row.PER, ...
         row.Throughput_bps, row.error_flag);
writetable(struct2table(row), fullfile(outdir,'_smoke_frame_row.csv'));

fprintf('DONE: 4 scenarios written to Results\\DigitalTwin\n');

% -------------------------------------------------------------------------
function pts = build_drive(prof, name, segments, mods)
% [PHASE-5 NOTE] LEGACY generator for A-D scenario files (provenance). The canonical scenario engine is dt_scenarios_lib.m; existing JSON/CSV outputs remain the single source of truth.
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

  base   = v_lo + rand*(v_hi-v_lo);          % smooth random-walk speed
  target = v_lo + rand*(v_hi-v_lo);
  steps  = linspace(0,1,n);
  wob = 0.15*(v_hi-v_lo)*sin(2*pi*steps*randi([1 3]));
  speeds = min(max(base + (target-base)*steps + wob, v_lo), v_hi);
  mod = mods(min(s,numel(mods)));
  for k = 1:n
    snr = snr_base + 3*sin(2*pi*t/25) - 3*max(0,sin(2*pi*t/17+1));
    if strcmp(name,'stress') && rand < 0.08
      snr = snr - 6*rand;                    % deep dips in stress drive
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
function write_scenario(pts, name, outdir)
meta = struct('name',sprintf('scenario_%s',lower(name)), ...
              'generator','dt_scenarios.m (phase2)', ...
              'seed',20260823,'dt_s',1.0,'n_points',numel(pts), ...
              'profiles_file','otfs_ai_pipeline/environment_profiles_v2.csv');
fid = fopen(fullfile(outdir,sprintf('scenario_%s.json',lower(name))),'w');
fwrite(fid, jsonencode(struct('meta',meta,'points',pts), ...
                       'PrettyPrint', true));
fclose(fid);

T = struct2table(pts);
writetable(T, fullfile(outdir,sprintf('scenario_%s.csv',lower(name))));
fprintf('scenario_%s: %d points (%s)\n', lower(name), numel(pts), ...
        strjoin(unique({pts.environment}), ','));
end
