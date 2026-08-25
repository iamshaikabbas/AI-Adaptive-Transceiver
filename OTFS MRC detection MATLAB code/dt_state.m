function state = dt_state(varargin)
% =========================================================================
% DT_STATE   Canonical Digital-Twin wireless STATE (what conditions exist).
% This is the ONE state schema every frame uses (spec sections 3/4).
%
%   state = dt_state();                                  % documented defaults
%   state = dt_state('speed_kmph',30,'snr_db',12, ...);  % name/value pairs
%   state = dt_state(pt, cfg);                           % from a scenario point
%                                                            + sim config
%
% A state describes CONDITIONS ONLY. It never contains results (BER, ACS,
% ...) and never contains oracle information -- the AI may consume states
% safely (spec section 8: oracle is evaluation-only).
%
% Fields (spec section 3):
%   timestamp              wall-clock string when the state was created
%   frame                  1-based frame index within the scenario
%   scenario_id            scenario name/letter
%   environment            Pedestrian|Urban|Highway|HighSpeedRail|custom
%   speed_kmph             mobility (simulation choice, not measured)
%   snr_db                 receive SNR
%   doppler_hz             DERIVED = (speed/3.6)*carrier/c * doppler_scale
%                          (never set independently; dt_derive_doppler rule)
%   carrier_frequency_hz   default 4e9 (repo convention)
%   bandwidth_hz           M*delta_f (repo default 480 kHz)
%   channel_profile        EPA|EVA|ETU
%   delay_spread_taps      realized channel max-delay tap index
%   num_paths              realized number of channel paths
%   modulation             QPSK=4 | 16-QAM | 64-QAM
%   detector               deployment detector for the current waveform
%   waveform               currently selected waveform ('OTFS'|'ODDM')
%   doppler_scale          profile scaling used by the generator
%   t_sim_s                SIMULATION time of the frame start (seconds);
%                          distinct from wall-clock time (spec section 23)
%
% Seeds (dt_seeds.m contract):
%   scenario_seed payload_seed channel_seed noise_seed
%
% Optional impairments -- applied by apply_rx_impairments.m only when the
% simulation supports them; zero means "not in use" (never forced):
%   frequency_offset [Hz]  phase_offset [rad]  timing_offset [samples]
%
% Adaptive-loop context consumed by the AI policy:
%   current_waveform       waveform selected on the previous frame
%   frames_since_switch    frames since the last waveform switch
% =========================================================================
c_light = 299792458;

state = struct( ...
    'timestamp',          string(datestr(now,'yyyy-mm-dd HH:MM:SS')), ...
    'frame',              int64(0), ...
    'scenario_id',        string(""), ...
    'environment',        string("Urban"), ...
    'speed_kmph',         30.0, ...
    'snr_db',             15.0, ...
    'doppler_hz',         NaN, ...          % derived below when speed given
    'doppler_scale',      1.0, ...
    'carrier_frequency_hz', 4e9, ...
    'bandwidth_hz',       480e3, ...
    'channel_profile',    string("EVA"), ...
    'delay_spread_taps',  NaN, ...          % realized by the generator
    'num_paths',          NaN, ...          % realized by the generator
    'modulation',         int64(4), ...
    'detector',           string(""), ...
    'waveform',           string("OTFS"), ...
    't_sim_s',            NaN, ...
    'scenario_seed',      20260823, ...
    'payload_seed',       NaN, ...
    'channel_seed',       NaN, ...
    'noise_seed',         NaN, ...
    'frequency_offset',   0.0, ...
    'phase_offset',       0.0, ...
    'timing_offset',      0.0, ...
    'current_waveform',   string("OTFS"), ...
    'frames_since_switch', int64(99));

% ---- form: dt_state(pt, cfg [, 'name',value ...]) -----------------------
% Optional trailing pairs override fields BEFORE seed derivation -- always
% pass the FINAL 1-based frame here (scenario files store 0-based indices;
% the runner renumbers and passes 'frame',f explicitly).
if nargin >= 2 && isstruct(varargin{1}) && isstruct(varargin{2})
    pt = varargin{1};  cfg = varargin{2};
    map = {'environment','environment'; 'speed_kmph','speed_kmph'; ...
           'snr_db','snr_db'; 'delay_profile','channel_profile'; ...
           'doppler_scale','doppler_scale'; 'modulation','modulation'; ...
           't_s','t_sim_s'; 'frame','frame'};
    for k = 1:size(map,1)
        if isfield(pt,map{k,1})
            state.(map{k,2}) = cast_like(state.(map{k,2}), pt.(map{k,1}));
        end
    end
    if isfield(cfg,'car_fre'), state.carrier_frequency_hz = cfg.car_fre; end
    if isfield(cfg,'BW'),      state.bandwidth_hz = cfg.BW; end
    extra = varargin(3:end);
else
    extra = varargin;
end

% ---- name/value overrides ----------------------------------------------
i = 1;
while i <= numel(extra)
    if i+1 > numel(extra), error('dt_state: missing value for %s', ...
                                 extra{i}); end
    key = lower(char(extra{i}));
    name = key;
    if strcmp(key,'frequency_offset'), name = 'cfo_hz'; end
    if strcmp(key,'phase_offset'),     name = 'phase_offset_rad'; end
    if strcmp(key,'timing_offset'),    name = 'timing_offset_samples'; end
    if ~isfield(state, name)
        error('dt_state: unknown field ''%s''', extra{i});
    end
    state.(name) = cast_like(state.(name), extra{i+1});
    i = i + 2;
end

state = dt_state_finalize(state);
end

function state = dt_state_finalize(state)
% ---- derived quantities -------------------------------------------------
c_light = 299792458;
if isnan(double(state.doppler_hz))
    v = double(state.speed_kmph)*(1000/3600);
    state.doppler_hz = v / c_light * double(state.carrier_frequency_hz) ...
                         * double(state.doppler_scale);
end
[ps, cs, ns] = dt_seeds(double(state.frame), ...
                        double(state.scenario_seed));
state.payload_seed = double(ps);
state.channel_seed = double(cs);
state.noise_seed   = double(ns);
if isempty(char(state.detector)) || strlength(string(state.detector))==0
    state.detector = string(twin_default_detector(char(state.waveform)));
end
end

function val = cast_like(existing, new)
% preserve int64/string types of the template while accepting plain numbers
if isstring(existing)
    val = string(new);
elseif isinteger(existing)
    val = int64(double(new));
else
    val = double(new);
end
end
