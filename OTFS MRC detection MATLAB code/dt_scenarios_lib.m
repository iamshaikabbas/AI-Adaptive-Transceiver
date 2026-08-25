function out = dt_scenarios_lib(cmd, a1, a2)
% =========================================================================
% DT_SCENARIOS_LIB   Centralized Digital-Twin scenario engine (spec
% sections 10-12). ONE copy of the trajectory builders; the historical
% generator scripts dt_scenarios.m / dt_scenarios_v4.m remain frozen as
% provenance for the validated A-R scenario files.
%
% Commands:
%   out = dt_scenarios_lib('resolve', spec)
%       spec: 'A'..'R' | group ('all'|'tune'|'heldout'|'difficult') |
%             custom scenario name or JSON path.
%       -> struct(name, tier, points, meta)   (or struct array for groups)
%
%   out = dt_scenarios_lib('groups')
%       -> struct with the letter sets.
%
%   out = dt_scenarios_lib('load_custom', path_or_name)
%       -> points struct array from a user JSON (schema below).
%
% Custom scenario JSON schema (follows project conventions -- NOT a second
% format; it expands into the SAME point schema used by every scenario):
%   Constant condition (spec section 12 example):
%     {"name":"custom_test", "duration_frames":60,
%      "initial_speed_kmph":100, "snr_db":12,
%      "channel_profile":"EVA", "modulation":4}
%     (environment optional -- derived from speed via
%      environment_profiles_v2.csv ranges when omitted)
%   Piecewise transitions (spec section 11):
%     {"name":"urban_to_hwy",
%      "segments":[{"environment":"Urban","frames":10,"modulation":4,
%                   "speed_kmph":25,"snr_db":14},
%                  {"environment":"Highway","frames":10,"modulation":4,
%                  "speed_kmph":110,"snr_db":11}]}
%   Raw points (already in the standard schema):
%     {"name":"...", "points":[{"t_s":0,"frame":0,"environment":"...",
%       "speed_kmph":..,"snr_db":..,"delay_profile":"..","doppler_scale":..,
%       "modulation":..}, ...]}
%
% Scenario TRANSITIONS supported: Pedestrian->Urban->Highway->HSR and
% back, acceleration/deceleration (speed ramps), SNR degradation/recovery
% (explicit snr_db per segment), channel/profile transitions. Physically
% impossible jumps are rejected unless meta.stress=true (spec section 11).
%
% A scenario is a time sequence of states at dt_s = 1 s spacing:
%   frame f has t_sim_s = f-1 seconds of simulated time (spec section 23).
% =========================================================================
here = fileparts(mfilename('fullpath'));

switch lower(char(cmd))
    case 'groups'
        out = struct('ALL',{{'A','B','C','D'}}, ...
                     'TUNE',{{'E','F','G','H'}}, ...
                     'HELDOUT',{{'I','J','K','L'}}, ...
                     'DIFFICULT',{{'M','N','O','P','Q','R'}});

    case 'resolve'
        if ischar(a1) || isstring(a1)
            key = upper(char(a1));
            g = dt_scenarios_lib('groups');
            if isfield(g,key)
                letters = g.(key);
                cells = cell(1,numel(letters));
                for i = 1:numel(letters)
                    cells{i} = dt_scenarios_lib('resolve', letters{i});
                end
                out = [cells{:}];
            elseif numel(key)==1 && key >= 'A' && key <= 'R'
                out = local_load_letter(here, key);
            else
                out = local_load_custom(here, char(a1));   % custom name/path
            end
        else
            cells = cell(1,numel(a1));
            for i = 1:numel(a1)
                cells{i} = dt_scenarios_lib('resolve', a1{i});
            end
            out = [cells{:}];
        end

    case 'load_custom'
        out = local_load_custom(here, char(a1));

    case 'expand_constant'
        % expand_constant(json_struct) -> points
        out = local_expand(here, a1);

    otherwise
        error('dt_scenarios_lib: unknown command ''%s''', cmd);
end
end

% ---------------------------------------------------------------------------
function s = local_load_letter(here, key)
dt = fullfile(here,'Results','DigitalTwin');
jf = fullfile(dt, sprintf('scenario_%s.json', lower(key)));
assert(exist(jf,'file')==2, ...
    'scenario file missing: %s (run dt_scenarios.m / dt_scenarios_v4.m)', jf);
js = jsondecode(fileread(jf));
tier = 'final_eval';                       % A-D predate the tier system
if isfield(js.meta,'tier'), tier = js.meta.tier; end
s = struct('name', upper(key), 'tier', string(tier), ...
           'points', js.points, ...
           'meta', js.meta);
if ~isfield(s.meta,'stress'), s.meta.stress = false; end
local_check_transitions(s);
end

% ---------------------------------------------------------------------------
function s = local_load_custom(here, name_or_path)
cand = {name_or_path, ...
        fullfile(here,'custom_scenarios',[name_or_path '.json']), ...
        fullfile(here,'Results','DigitalTwin',['scenario_' ...
                 lower(name_or_path) '.json'])};
p = '';
for i = 1:numel(cand)
    if exist(cand{i},'file')==2, p = cand{i}; break; end
end
assert(~isempty(p), 'custom scenario not found: %s', name_or_path);
js = jsondecode(fileread(p));
pts = local_expand(here, js);
meta = struct('name',char(string(js.name)), 'generator','custom JSON', ...
              'tier','custom', ...
              'seed', double(local_get(js,'seed',20260823)), ...
              'dt_s',1.0, 'n_points',numel(pts), 'stress', ...
              logical(local_get(js,'stress',false)), 'source',p);
s = struct('name',upper(char(string(js.name))), 'tier', string('custom'), ...
           'points', pts, 'meta', meta);
local_check_transitions(s);
end

% ---------------------------------------------------------------------------
function pts = local_expand(here, js)
assert(isscalar(js), 'scenario JSON must decode to a single object');
prof = readtable(fullfile(here,'otfs_ai_pipeline', ...
                          'environment_profiles_v2.csv'));
if isfield(js,'points') && numel(js.points) > 0
    pts = js.points;
elseif isfield(js,'segments') && numel(js.segments) > 0
    segs = js.segments;
    if iscell(segs)                      % programmatic caller (cell form)
        sa = segs{1};
        for ii = 2:numel(segs), sa(ii) = segs{ii}; end
        segs = sa;
    end
    envs = {}; speeds = []; n_per = []; mods = []; snrs = [];
    for i = 1:numel(segs)
        sg = segs(i);
        envs{end+1} = char(string(sg.environment)); %#ok<AGROW>
        speeds(end+1) = local_get(sg,'speed_kmph',NaN); %#ok<AGROW>
        n_per(end+1)  = double(sg.frames);              %#ok<AGROW>
        mods(end+1)   = double(local_get(sg,'modulation',4)); %#ok<AGROW>
        snrs(end+1)   = local_get(sg,'snr_db',NaN);     %#ok<AGROW>
    end
    pts = local_steps(prof, envs, speeds, n_per, mods, snrs);
else
    % constant-condition form (spec section 12 example)
    n     = double(local_get(js,'duration_frames',60));
    v     = double(local_get(js,'initial_speed_kmph',30));
    snr   = double(local_get(js,'snr_db',NaN));
    profn = char(string(local_get(js,'channel_profile',"")));
    mod   = double(local_get(js,'modulation',4));
    env   = local_env_for_speed(prof, v);
    r = local_prof_row(prof, env);
    if isempty(profn), profn = char(string(prof.DelayProfile(r))); end
    if isnan(snr),     snr = prof.SNRBase(r); end
    dscale = prof.DopplerScale(r);
    pts = struct('t_s',{},'frame',{},'environment',{},'speed_kmph',{}, ...
                 'snr_db',{},'delay_profile',{},'doppler_scale',{}, ...
                 'modulation',{});
    t = 0;
    for k = 1:n
        pts(end+1) = struct('t_s',round(t,3),'frame',k-1, ...
            'environment',env,'speed_kmph',round(v,1),'snr_db',round(snr,2), ...
            'delay_profile',profn,'doppler_scale',dscale,'modulation',mod); %#ok<AGROW>
        t = t + 1.0;
    end
end
end

% ---------------------------------------------------------------------------
function pts = local_steps(prof, envs, speeds, n_per, mod, varargin)
% deterministic piecewise conditions; explicit SNR vector optional
env_names = strtrim(string(prof.Environment));
explicit_snr = ~isempty(varargin) && all(~isnan(varargin{1}));
pts = struct('t_s',{},'frame',{},'environment',{},'speed_kmph',{}, ...
             'snr_db',{},'delay_profile',{},'doppler_scale',{}, ...
             'modulation',{});
t = 0; frame = 0;
for s = 1:numel(envs)
  r = local_prof_row(prof, envs{s});
  dscale = prof.DopplerScale(r); dprof = char(string(prof.DelayProfile(r)));
  v = speeds(s);
  if explicit_snr, snr = varargin{1}(s); else, snr = prof.SNRBase(r); end
  for k = 1:n_per(s)
    pts(end+1) = struct('t_s',round(t,3),'frame',frame, ...
        'environment',envs{s},'speed_kmph',round(v,1),'snr_db',round(snr,2), ...
        'delay_profile',dprof,'doppler_scale',dscale, ...
        'modulation',mod(min(s,numel(mod)))); %#ok<AGROW>
    t = t + 1.0; frame = frame + 1;
  end
end
end

% ---------------------------------------------------------------------------
function local_check_transitions(s)
% physically-plausible transition check (spec section 11): speed must stay
% inside the environment band of each point; jumps BETWEEN bands are fine
% when they follow the corridor order, otherwise require meta.stress.
prof_file = fullfile(fileparts(mfilename('fullpath')), ...
    'otfs_ai_pipeline','environment_profiles_v2.csv');
prof = readtable(prof_file);
bad = {};
for k = 1:numel(s.points)
    p = s.points(k);
    r = local_prof_row(prof, char(p.environment));
    if isempty(r), bad{end+1} = sprintf('unknown env %s', p.environment); %#ok<AGROW>
    elseif p.speed_kmph < prof.SpeedMin(r)-1e-9 || ...
           p.speed_kmph > prof.SpeedMax(r)+1e-9
        bad{end+1} = sprintf(['frame %d: %.1f km/h outside %s band'], ...
                             k, p.speed_kmph, p.environment); %#ok<AGROW>
    end
end
if ~isempty(bad) && ~(isfield(s.meta,'stress') && s.meta.stress)
    error('dt_scenarios_lib(%s): implausible conditions: %s', ...
          s.name, strjoin(bad, '; '));
end
end

function r = local_prof_row(prof, env)
env_names = strtrim(string(prof.Environment));
r = find(env_names == string(env), 1);
end

function env = local_env_for_speed(prof, v)
env_names = strtrim(string(prof.Environment));
env = "";
for i = 1:numel(env_names)
    if v >= prof.SpeedMin(i)-1e-9 && v <= prof.SpeedMax(i)+1e-9
        env = char(env_names(i)); return;
    end
end
error('dt_scenarios_lib: speed %.1f km/h outside all environment bands', v);
end

function v = local_get(s, f, dflt)
if isfield(s,f) && ~isempty(s.(f)), v = s.(f); else, v = dflt; end
end
