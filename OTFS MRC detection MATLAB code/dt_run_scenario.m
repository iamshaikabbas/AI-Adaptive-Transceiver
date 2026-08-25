function results_json = dt_run_scenario(scenario_json, strategy, policy, n_frames, seed0)
% =========================================================================
% DT_RUN_SCENARIO   Run all frames for a scenario via MATLAB and return
% results as JSON. Called by the Phase 8 backend for FAST/FULL runs.
%
%   results_json = dt_run_scenario(scenario_json, strategy, policy,
%                                  n_frames, seed0)
%
% Inputs:
%   scenario_json : JSON with {name, points[{...}]}
%   strategy      : 'fixed_otfs' | 'fixed_oddm' | 'ai_adaptive' | 'oracle'
%   policy        : 'phase3' | 'phase4'
%   n_frames      : number of frames to run
%   seed0         : master seed
%
% Output:
%   results_json  : JSON array of frame results
% =========================================================================
if nargin < 5 || isempty(seed0), seed0 = 20260823; end
if nargin < 4 || isempty(policy), policy = 'phase3'; end
if nargin < 3 || isempty(strategy), strategy = 'ai_adaptive'; end

scen = jsondecode(scenario_json);
nF = min(n_frames, numel(scen.points));
results = {};

cfg_base = sim_default_config();
cfg_base.TwinStrategy = 'pair';
prev_wf = 'OTFS';
dwell = 99;

for f = 1:nF
    pt = scen.points(f);
    st = dt_state(pt, cfg_base, 'frame', f, ...
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

    [rO,~] = dt_exec_waveform(cfg_f, chan, tx_bits, st.noise_seed, 'OTFS');
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
            sel_wf = 'OTFS'; row_result = rO;
        case 'fixed_oddm'
            sel_wf = 'ODDM'; row_result = rD;
        case 'oracle'
            sel_wf = orc_wf;
            if strcmp(orc_wf, 'OTFS'), row_result = rO;
            else, row_result = rD; end
        case 'ai_adaptive'
            wdir = fullfile(tempdir, 'dt8_ai');
            if ~exist(wdir, 'dir'), mkdir(wdir); end
            [dec, ~, ~] = dt_ai_decide(ai_st, policy, ...
                struct('here', fileparts(mfilename('fullpath')), ...
                       'workdir', wdir));
            sel_wf = dec.recommendation;
            if ~any(strcmp({'OTFS', 'ODDM'}, sel_wf)), sel_wf = prev_wf; end
            if strcmp(sel_wf, 'OTFS'), row_result = rO;
            else, row_result = rD; end
        otherwise
            sel_wf = prev_wf; row_result = rO;
    end

    switched = ~strcmp(sel_wf, prev_wf);
    [ps, cs, ns] = dt_seeds(f, seed0);

    out = struct();
    out.scenario_id = scen.name;
    out.frame = f;
    out.environment = char(st.environment);
    out.speed_kmph = st.speed_kmph;
    out.snr_db = st.snr_db;
    out.doppler_hz = st.doppler_hz;
    out.channel_profile = char(chan.profile);
    out.modulation = st.modulation;
    out.waveform = sel_wf;
    out.strategy = strategy;
    out.switched = switched;
    out.oracle_waveform = orc_wf;
    out.BER = row_result.BER;
    out.throughput_bps = row_result.throughput_bps;
    out.CQI = row_result.CQI;
    out.ACS = row_result.ACS;
    out.ACS_regret = max(orc_acs - row_result.ACS, 0);
    out.decision_correct = double(strcmp(sel_wf, orc_wf));

    if strcmp(strategy, 'ai_adaptive')
        out.ai_confidence = dec.confidence;
        out.ai_reason = dec.reason;
    end

    results{end+1} = out; %#ok<AGROW>

    if switched, dwell = 0; else, dwell = dwell + 1; end
    prev_wf = sel_wf;

    fprintf('f%02d %s | sel %s | oracle %s | BER %.2e ACS %.3f\n', ...
        f, strategy, sel_wf, orc_wf, row_result.BER, row_result.ACS);
end

results_json = jsonencode(results);
end
