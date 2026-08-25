function result_json = dt_step_frame(scenario_json, frame, strategy, policy, seed0)
% =========================================================================
% DT_STEP_FRAME   Single-frame MATLAB executor for the Phase 8 backend.
%
%   result_json = dt_step_frame(scenario_json, frame, strategy, policy, seed0)
%
% Inputs (JSON strings):
%   scenario_json : JSON with {name, points[{t_s, frame, environment,
%                   speed_kmph, snr_db, delay_profile, doppler_scale,
%                   modulation}]}
%   frame         : 1-based frame index
%   strategy      : 'fixed_otfs' | 'fixed_oddm' | 'ai_adaptive' | 'oracle'
%   policy        : 'phase3' | 'phase4'
%   seed0         : master seed (default 20260823)
%
% Output:
%   result_json   : JSON string with the frame result
% =========================================================================
if nargin < 5 || isempty(seed0), seed0 = 20260823; end
if nargin < 4 || isempty(policy), policy = 'phase3'; end
if nargin < 3 || isempty(strategy), strategy = 'ai_adaptive'; end

scen = jsondecode(scenario_json);
if frame < 1 || frame > numel(scen.points)
    result_json = jsonencode(struct('error', true, ...
        'error_message', sprintf('frame %d out of range [1, %d]', ...
        frame, numel(scen.points))));
    return;
end

pt = scen.points(frame);
cfg_base = sim_default_config();
cfg_base.TwinStrategy = 'pair';
prev_wf = 'OTFS';
dwell = 99;

st = dt_state(pt, cfg_base, 'frame', frame, ...
    'scenario_id', scen.name, 'scenario_seed', seed0, ...
    'current_waveform', prev_wf, 'frames_since_switch', dwell);

cfg_f = cfg_base;
cfg_f.DelayProfile = char(pt.delay_profile);
cfg_f.Speed_kmph = pt.speed_kmph;
cfg_f.SNR_dB = pt.snr_db;
cfg_f.DopplerScale = pt.doppler_scale;
cfg_f.Modulation = pt.modulation;

chan = dt_channel_for_frame(cfg_f, st.channel_seed);
tx_bits = dt_payload_for_frame(cfg_f, chan, st.payload_seed);
st.delay_spread_taps = int64(chan.max_delay_tap);
st.num_paths = int64(chan.taps);

[rO, ~] = dt_exec_waveform(cfg_f, chan, tx_bits, st.noise_seed, 'OTFS');
rD = dt_exec_waveform(cfg_f, chan, tx_bits, st.noise_seed, 'ODDM');

if rO.ACS >= rD.ACS
    orc_wf = 'OTFS'; orc_ber = rO.BER; orc_acs = rO.ACS;
else
    orc_wf = 'ODDM'; orc_ber = rD.BER; orc_acs = rD.ACS;
end

dec = struct('recommendation', prev_wf, 'best_by_objective', '', ...
    'detector', '', 'confidence', NaN, 'reason', 'not requested', ...
    'predicted_metrics', struct());
ai_st = struct( ...
    'environment', char(st.environment), ...
    'speed_kmph', st.speed_kmph, 'snr_db', st.snr_db, ...
    'doppler_hz', st.doppler_hz, ...
    'carrier_frequency_hz', st.carrier_frequency_hz, ...
    'bandwidth_hz', st.bandwidth_hz, ...
    'channel_profile', char(chan.profile), ...
    'delay_spread_taps', chan.max_delay_tap, ...
    'num_paths', chan.taps, ...
    'doppler_spread_hz', chan.doppler_spread_hz, ...
    'modulation', st.modulation, ...
    'current_waveform', prev_wf, ...
    'frames_since_switch', dwell);

switch strategy
    case 'fixed_otfs'
        sel_wf = 'OTFS';
        row_result = rO;
    case 'fixed_oddm'
        sel_wf = 'ODDM';
        row_result = rD;
    case 'oracle'
        sel_wf = orc_wf;
        if strcmp(orc_wf, 'OTFS'), row_result = rO;
        else, row_result = rD; end
    case 'ai_adaptive'
        wdir = fullfile(tempdir, 'dt8_ai');
        if ~exist(wdir, 'dir'), mkdir(wdir); end
        [dec, ai_err, fb_used] = dt_ai_decide(ai_st, policy, ...
            struct('here', fileparts(mfilename('fullpath')), ...
                   'workdir', wdir));
        sel_wf = dec.recommendation;
        if ~any(strcmp({'OTFS', 'ODDM'}, sel_wf)), sel_wf = prev_wf; end
        if strcmp(sel_wf, 'OTFS'), row_result = rO;
        else, row_result = rD; end
    otherwise
        sel_wf = prev_wf;
        row_result = rO;
end

switched = ~strcmp(sel_wf, prev_wf);
[ps, cs, ns] = dt_seeds(frame, seed0);

out = struct();
out.scenario_id = scen.name;
out.frame = frame;
out.timestamp = char(st.timestamp);
out.t_sim_s = st.t_sim_s;
out.environment = char(st.environment);
out.speed_kmph = st.speed_kmph;
out.snr_db = st.snr_db;
out.doppler_hz = st.doppler_hz;
out.carrier_frequency_hz = st.carrier_frequency_hz;
out.bandwidth_hz = st.bandwidth_hz;
out.channel_profile = char(chan.profile);
out.delay_spread_taps = st.delay_spread_taps;
out.num_paths = st.num_paths;
out.modulation = st.modulation;
out.doppler_scale = st.doppler_scale;
out.seed0 = seed0;
out.payload_seed = ps;
out.channel_seed = cs;
out.noise_seed = ns;

out.strategy = strategy;
out.policy = policy;
out.waveform = sel_wf;
out.previous_waveform = prev_wf;
out.switched = switched;
out.oracle_waveform = orc_wf;
out.oracle_BER = orc_ber;
out.oracle_ACS = orc_acs;

out.BER = row_result.BER;
out.SER = row_result.SER;
out.PER = row_result.PER;
out.throughput_bps = row_result.throughput_bps;
out.spectral_efficiency = row_result.spectral_efficiency;
out.CQI = row_result.CQI;
out.ACS = row_result.ACS;
out.wall_clock_ms = row_result.wall_clock_ms;
out.detector_time_ms = row_result.detector_time_ms;
out.latency_ms_modeled = NaN;
out.packet_loss = row_result.packet_loss;
out.recovery_rate = row_result.recovery_rate;
out.tp_cap_bps = row_result.tp_cap_bps;
out.se_cap = row_result.se_cap;
out.error_flag = row_result.error_flag;
out.error_message = char(row_result.error_message);

if strcmp(strategy, 'ai_adaptive')
    out.ai = struct();
    out.ai.recommendation = dec.recommendation;
    out.ai.best_by_objective = dec.best_by_objective;
    out.ai.confidence = dec.confidence;
    out.ai.reason = dec.reason;
    out.ai.predicted_metrics = dec.predicted_metrics;
    if isfield(dec, 'switched'), out.ai.switched = dec.switched; end
end

out.actual_BER_OTFS = rO.BER;
out.actual_ACS_OTFS = rO.ACS;
out.actual_BER_ODDM = rD.BER;
out.actual_ACS_ODDM = rD.ACS;
out.actual_TP_OTFS = rO.throughput_bps;
out.actual_TP_ODDM = rD.throughput_bps;
out.ACS_regret = max(orc_acs - row_result.ACS, 0);
out.BER_regret = row_result.BER - orc_ber;
out.decision_correct = double(strcmp(sel_wf, orc_wf));

result_json = jsonencode(out);
end
