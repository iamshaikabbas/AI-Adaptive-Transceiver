function summary = run_experiment(scenario, varargin)
% =========================================================================
% RUN_EXPERIMENT   Canonical Digital-Twin experiment runner (spec sections
% 5, 14-17). One scenario/group -> four-strategy paired evaluation using
% the centralized primitives (dt_scenarios_lib / dt_state / dt_seeds /
% dt_channel_for_frame / dt_payload_for_frame / dt_exec_waveform /
% dt_ai_decide). This REPLACES digital_twin_runtime.m as the production
% entry point; the frozen runtime stays untouched for regression proof.
%
%   summary = run_experiment('A');                       % FULL, phase3
%   summary = run_experiment('all', 'mode','FAST');
%   summary = run_experiment('tune', 'policy','phase4');
%   summary = run_experiment('custom_test');
%
% scenario : 'A'..'R' | group ('all'|'tune'|'heldout'|'difficult') |
%            custom scenario name/file (dt_scenarios_lib)
% opts (name/value, all optional):
%   'mode'       'FULL' (60 frames, default) | 'FAST' (12)
%   'n_frames'   explicit override of both modes
%   'strategies' cell subset of {fixed_otfs,fixed_oddm,ai_adaptive,oracle}
%                (default all four)
%   'policy'     'phase3' (DEFAULT, adaptive_config_v2 + ai_engine_v2) |
%                'phase4' (EXPERIMENTAL, adaptive_config_v4 + ai_engine_v3)
%   'seed0'      master seed (default 20260823)
%   'out_root'   output root (default <here>/Results/DigitalTwin)
%   'frequency_offset' | 'phase_offset' | 'timing_offset'
%                optional receiver impairments [Hz|rad|samples]; applied to
%                every frame when nonzero (apply_rx_impairments.m).
%
% FAIRNESS CONTRACT (unchanged, spec section 21): per frame ONE channel +
% ONE payload + ONE noise seed shared by all strategies; BOTH waveforms
% executed on identical inputs; the AI never sees oracle/actual results.
%
% OUTPUT LAYOUT (spec section 16):
%   Results/DigitalTwin/<scenario_id>/<strategy>_trace.csv   (canonical
%   snake_case schema, sec. 17) + summary.csv + states.csv +
%   run_manifest.json. Legacy flat files are NEVER written here.
% =========================================================================
here = fileparts(mfilename('fullpath'));
o = local_parse(varargin);

scen = dt_scenarios_lib('resolve', scenario);

t_start = tic;
run_started = datestr(now,'yyyy-mm-dd HH:MM:SS');
summary = struct();
summary.scenario_spec = char(string(scenario));
summary.mode = o.mode;
summary.frames_requested = o.n_frames;
summary.policy = o.policy;
summary.seed0 = o.seed0;
summary.strategies = strjoin(o.strategies,',');
summary.objective = o.objective;
summary.elapsed_min = [];
summary.scenarios = struct([]);

for si = 1:numel(scen)
    s = scen(si);
    sdir = fullfile(o.out_root, lower(char(s.name)));
    if ~exist(sdir,'dir'), mkdir(sdir); end
    pts = s.points;
    nF  = min(o.n_frames, numel(pts));
    fprintf('\n=== RUN_EXPERIMENT %s [%s] %s policy=%s: %d/%d frames ===\n', ...
        char(s.name), s.tier, o.mode, o.policy, nF, numel(pts));

    cfg_base = sim_default_config();
    cfg_base.TwinStrategy = 'pair';

    prev_wf = 'OTFS';  dwell = 99;
    row_buf = {};         state_buf = {};
    need_ai = any(strcmp(o.strategies,'ai_adaptive'));

    for f = 1:nF
        p = pts(f);
        st = dt_state(p, cfg_base, 'frame', f, ...
            'scenario_id', char(s.name), 'scenario_seed', o.seed0, ...
            'current_waveform', prev_wf, 'frames_since_switch', dwell);
        % payload/channel/noise seeds were derived inside dt_state via
        % dt_seeds(f, seed0) -- identical contract for every strategy.
        st.frequency_offset = double(o.cfo_hz);
        st.phase_offset     = double(o.phase_rad);
        st.timing_offset    = double(o.timing_samp);
        st.current_waveform = string(prev_wf);
        st.frames_since_switch = int64(dwell);

        cfg_f = cfg_base;
        cfg_f.DelayProfile = char(p.delay_profile);
        cfg_f.Speed_kmph   = double(p.speed_kmph);
        cfg_f.SNR_dB       = double(p.snr_db);
        cfg_f.DopplerScale = double(p.doppler_scale);
        cfg_f.Modulation   = double(p.modulation);
        if abs(o.cfo_hz)>0 || abs(o.phase_rad)>0 || abs(o.timing_samp)>0
            cfg_f.cfo_hz = o.cfo_hz;
            cfg_f.phase_offset_rad = o.phase_rad;
            cfg_f.timing_offset_samples = o.timing_samp;
        end

        % shared physical conditions for ALL strategies (sec. 21)
        chan = dt_channel_for_frame(cfg_f, st.channel_seed);
        tx_bits = dt_payload_for_frame(cfg_f, chan, st.payload_seed);
        pay_sum = sum(double(tx_bits));
        chan_sum = sum(abs(chan.chan_coef(:)));
        st.delay_spread_taps = int64(chan.max_delay_tap);
        st.num_paths = int64(chan.taps);

        [rO,~] = dt_exec_waveform(cfg_f,chan,tx_bits,st.noise_seed,'OTFS');
        rD = dt_exec_waveform(cfg_f,chan,tx_bits,st.noise_seed,'ODDM');

        % oracle (evaluation-only, sec. 8): best ACTUAL objective
        if strcmp(o.objective,'BER')
            if rO.BER <= rD.BER, orc_wf='OTFS'; else, orc_wf='ODDM'; end
        else
            if rO.ACS >= rD.ACS, orc_wf='OTFS'; else, orc_wf='ODDM'; end
        end
        orc_ber = min(rO.BER, rD.BER);
        orc_acs = max(rO.ACS, rD.ACS);

        % AI decision (closed loop; state-only features)
        ai_st = struct( ...
            'environment', char(st.environment), ...
            'speed_kmph', double(st.speed_kmph), ...
            'snr_db', double(st.snr_db), ...
            'doppler_hz', double(st.doppler_hz), ...
            'carrier_frequency_hz', double(st.carrier_frequency_hz), ...
            'bandwidth_hz', double(st.bandwidth_hz), ...
            'channel_profile', char(chan.profile), ...
            'delay_spread_taps', double(chan.max_delay_tap), ...
            'num_paths', double(chan.taps), ...
            'doppler_spread_hz', double(chan.doppler_spread_hz), ...
            'modulation', double(st.modulation), ...
            'current_waveform', prev_wf, ...
            'frames_since_switch', dwell);
        if need_ai
            wdir = fullfile(tempdir,'dt5_ai',lower(char(s.name)));
            [dec, ai_err, fb_used] = dt_ai_decide(ai_st, o.policy, ...
                                                  struct('here',here, ...
                                                         'workdir',wdir));
        else
            dec = struct('recommendation',prev_wf,'best_by_objective','', ...
                'detector','','confidence',NaN,'reason','not requested', ...
                'predicted_metrics',struct());
            ai_err = 'ai not requested';  fb_used = false;
        end

        sel_wf = dec.recommendation;
        if ~any(strcmp({'OTFS','ODDM'}, char(sel_wf))), sel_wf = prev_wf; end
        if strcmp(sel_wf,'OTFS'), rs=rO; else, rs=rD; end
        switched = ~strcmpi(sel_wf, prev_wf);

        % ---------------- canonical trace rows --------------------------
        for k = 1:numel(o.strategies)
            strat = o.strategies{k};
            row = local_row_template();
            row = local_fill_state(row, st, s.name, o);
            row.payload_sum = pay_sum;
            row.chan_checksum = chan_sum;
            row.strategy = string(strat);
            row.previous_waveform = string(prev_wf);
            row.oracle_waveform = string(orc_wf);
            row.oracle_BER = orc_ber;
            row.oracle_ACS = orc_acs;
            row.actual_BER_OTFS = rO.BER;  row.actual_ACS_OTFS = rO.ACS;
            row.actual_BER_ODDM = rD.BER;  row.actual_ACS_ODDM = rD.ACS;
            row.actual_TP_OTFS  = rO.throughput_bps;
            row.actual_TP_ODDM  = rD.throughput_bps;
            switch strat
                case 'fixed_otfs'
                    row.waveform='OTFS'; row.detector='MRC';
                    row = local_fill_result(row, rO);
                case 'fixed_oddm'
                    row.waveform='ODDM'; row.detector='LMMSE';
                    row = local_fill_result(row, rD);
                case 'oracle'
                    row.waveform = string(orc_wf);
                    if strcmp(orc_wf,'OTFS')
                        row.detector='MRC'; row=local_fill_result(row,rO);
                    else
                        row.detector='LMMSE'; row=local_fill_result(row,rD);
                    end
                case 'ai_adaptive'
                    row.predicted_waveform = string(dec.best_by_objective);
                    row.confidence = double(dec.confidence);
                    if isfield(dec,'confidence_band') && ...
                            ~isempty(dec.confidence_band)
                        row.confidence_band = string(char(dec.confidence_band));
                    end
                    pm = dec.predicted_metrics;
                    row.predicted_OTFS_BER = local_pmf(pm,'OTFS','BER');
                    row.predicted_ODDM_BER = local_pmf(pm,'ODDM','BER');
                    row.predicted_OTFS_ACS = local_pmf(pm,'OTFS','ACS');
                    row.predicted_ODDM_ACS = local_pmf(pm,'ODDM','ACS');
                    row.predicted_OTFS_TP  = local_pmf(pm,'OTFS','Throughput_bps');
                    row.predicted_ODDM_TP  = local_pmf(pm,'ODDM','Throughput_bps');
                    row.predicted_OTFS_CQI = local_pmf(pm,'OTFS','CQI');
                    row.predicted_ODDM_CQI = local_pmf(pm,'ODDM','CQI');
                    row.uncertainty_ACS_OTFS = local_unc(dec,'OTFS','ACS');
                    row.uncertainty_ACS_ODDM = local_unc(dec,'ODDM','ACS');
                    row.selected_waveform = string(sel_wf);
                    row.switched = switched;
                    row.switch_reason = string(dec.reason);
                    row.ai_error = string(ai_err);
                    row.fallback_used = logical(fb_used);
                    row.fallback_reason = string(local_fb_reason(dec,fb_used));
                    row.waveform = string(sel_wf);
                    if strcmp(sel_wf,'OTFS'), row.detector='MRC';
                    else,                     row.detector='LMMSE'; end
                    row = local_fill_result(row, rs);
                    row.decision_correct = double(strcmpi(sel_wf, orc_wf));
            end
            row = local_fill_regret(row);
            row_buf{end+1} = row; %#ok<AGROW>
        end

        strow = ai_st;
        strow.scenario_id = char(s.name);  strow.frame = f;
        strow.timestamp = char(st.timestamp);
        strow.t_sim_s = double(st.t_sim_s);
        state_buf{end+1} = strow; %#ok<AGROW>

        if switched, dwell = 0; else, dwell = dwell + 1; end
        if ~fb_used, prev_wf = sel_wf; end

        fprintf(['f%02d %5.1fkm/h %5.1fdB M%d | pred %-4s conf%.2f | sel %s' ...
                 ' %s | oracle %s | BER %.2e ACS %.3f%s\n'], f, ...
            double(st.speed_kmph), double(st.snr_db), ...
            double(st.modulation), dec.best_by_objective, ...
            double(dec.confidence), sel_wf, ...
            local_tern(switched,'SWITCH','      '), orc_wf, ...
            rs.BER, rs.ACS, local_tern(fb_used,' [FB]',''));
    end

    % ---- write canonical outputs (sec. 16) -----------------------------
    rows = [row_buf{:}];      states = [state_buf{:}];
    T = struct2table(rows);
    for k = 1:numel(o.strategies)
        strat = o.strategies{k};
        Tk = T(strcmp(string(T.strategy), string(strat)), :);
        writetable(Tk, fullfile(sdir, sprintf('%s_trace.csv',strat)));
        agg = local_aggregate(Tk, strat);
        writetable(agg, fullfile(sdir, sprintf('%s_summary.csv',strat)));
    end
    writetable(struct2table(states), fullfile(sdir,'states.csv'));
    manifest = struct( ...
        'scenario', char(s.name), 'tier', char(s.tier), ...
        'mode', o.mode, 'frames_run', nF, 'points_available', numel(pts), ...
        'policy', o.policy, 'seed0', o.seed0, ...
        'objective', o.objective, 'strategies', {o.strategies}, ...
        'matlab_version', version, ...
        'started', run_started, ...
        'finished', char(datestr(now,'yyyy-mm-dd HH:MM:SS')), ...
        'generator', 'run_experiment.m (phase5 canonical)', ...
        'impairments', struct('cfo_hz',o.cfo_hz, ...
            'phase_rad',o.phase_rad,'timing_samples',o.timing_samp), ...
        'note', ['software digital twin; wall_clock_ms is measured ' ...
                 'detector compute time; latency_ms_modeled is not ' ...
                 'modeled (always NaN)']);
    fid = fopen(fullfile(sdir,'run_manifest.json'),'w');
    fwrite(fid,jsonencode(manifest,'PrettyPrint',true)); fclose(fid);

    fprintf('--> outputs in %s\n', sdir);
    newsc = struct('name',char(s.name),'dir',sdir,'frames',nF);
    if isempty(summary.scenarios)
        summary.scenarios = newsc;
    else
        summary.scenarios(end+1) = newsc; %#ok<AGROW>
    end
end

summary.elapsed_min = toc(t_start)/60;
fprintf('\nRUN_EXPERIMENT DONE (%s, %s) in %.1f min\n', ...
    summary.scenario_spec, summary.mode, summary.elapsed_min);
end

% =========================================================================
function o = local_parse(opts)
o = struct('mode','FULL','n_frames',[], 'strategies', ...
    {{'fixed_otfs','fixed_oddm','ai_adaptive','oracle'}}, ...
    'policy','phase3', 'seed0',20260823, ...
    'out_root', fullfile(fileparts(mfilename('fullpath')), ...
                         'Results','DigitalTwin'), ...
    'cfo_hz',0, 'phase_rad',0, 'timing_samp',0);
i = 1;
while i <= numel(opts)
    switch lower(char(opts{i}))
        case 'mode',       o.mode = upper(char(opts{i+1}));
        case 'n_frames',   o.n_frames = double(opts{i+1});
        case 'strategies', o.strategies = opts{i+1};
        case 'policy',     o.policy = lower(char(opts{i+1}));
        case 'seed0',      o.seed0 = double(opts{i+1});
        case 'out_root',   o.out_root = char(opts{i+1});
        case 'frequency_offset', o.cfo_hz = double(opts{i+1});
        case 'phase_offset',     o.phase_rad = double(opts{i+1});
        case 'timing_offset',    o.timing_samp = double(opts{i+1});
        otherwise, error('run_experiment: unknown option ''%s''',opts{i});
    end
    i = i + 2;
end
if isempty(o.n_frames)
    switch o.mode
        case 'FULL', o.n_frames = 60;
        case 'FAST', o.n_frames = 12;
        otherwise, error('mode must be FAST or FULL');
    end
end
assert(any(strcmp(o.policy,{'phase3','phase4'})), ...
    'policy must be phase3 (default/canonical) or phase4 (experimental)');
[cfg_name,~] = dt_policy_config(o.policy);
cfgpol = jsondecode(fileread(fullfile( ...
    fileparts(mfilename('fullpath')), cfg_name)));
if isfield(cfgpol,'objective'),           ok='objective';
elseif isfield(cfgpol,'decision_objective'), ok='decision_objective';
else, error('policy config has no objective key');
end
obj = upper(cfgpol.(ok));
if ~any(strcmp(obj,{'ACS','BER'})), obj = 'ACS'; end
o.objective = obj;
end

function r = local_row_template()
r = struct();
f = {'frame',int64(0); 'timestamp',string(""); 't_sim_s',NaN; ...
     'scenario_id',string(""); 'environment',string(""); ...
     'speed_kmph',NaN; 'snr_db',NaN; 'doppler_hz',NaN; ...
     'carrier_frequency_hz',NaN; 'bandwidth_hz',NaN; ...
     'channel_profile',string(""); 'delay_spread_taps',int64(0); ...
     'num_paths',int64(0); 'modulation',int64(0); 'doppler_scale',1.0; ...
     'detector',string(""); 'waveform',string(""); 'strategy',string(""); ...
     'mode',string(""); 'policy',string(""); ...
     'scenario_seed',double(NaN); 'payload_seed',NaN; ...
     'channel_seed',NaN; 'noise_seed',NaN; 'payload_sum',NaN; ...
     'chan_checksum',NaN; ...
     'frequency_offset_hz',0.0; 'phase_offset_rad',0.0; ...
     'timing_offset_samples',0.0; ...
     'predicted_waveform',string(""); 'confidence',NaN; ...
     'confidence_band',string(""); ...
     'predicted_OTFS_BER',NaN; 'predicted_ODDM_BER',NaN; ...
     'predicted_OTFS_ACS',NaN; 'predicted_ODDM_ACS',NaN; ...
     'predicted_OTFS_TP',NaN; 'predicted_ODDM_TP',NaN; ...
     'predicted_OTFS_CQI',NaN; 'predicted_ODDM_CQI',NaN; ...
     'uncertainty_ACS_OTFS',NaN; 'uncertainty_ACS_ODDM',NaN; ...
     'selected_waveform',string(""); 'previous_waveform',string(""); ...
     'switched',false; 'switch_reason',string(""); ...
     'ai_error',string(""); 'fallback_used',false; ...
     'fallback_reason',string(""); ...
      'BER',NaN; 'SER',NaN; 'PER',NaN; 'throughput_bps',NaN; ...
      'spectral_efficiency',NaN; 'CQI',NaN; 'wall_clock_ms',NaN; ...
      'detector_time_ms',NaN; 'latency_ms_modeled',NaN; ...
      'packet_loss',NaN; 'recovery_rate',NaN; ...
      'ACS',NaN; 'tp_cap_bps',NaN; 'se_cap',NaN; ...
     'actual_BER_OTFS',NaN; 'actual_ACS_OTFS',NaN; ...
     'actual_BER_ODDM',NaN; 'actual_ACS_ODDM',NaN; ...
     'actual_TP_OTFS',NaN; 'actual_TP_ODDM',NaN; ...
     'oracle_waveform',string(""); 'oracle_BER',NaN; 'oracle_ACS',NaN; ...
     'ACS_regret',NaN; 'BER_regret',NaN; 'relative_BER_regret',NaN; ...
     'decision_correct',NaN; ...
     'error_flag',false; 'error_message',string("")};
for i = 1:size(f,1), r.(f{i,1}) = f{i,2}; end
end

function row = local_fill_state(row, st, name, o)
row.frame = int64(st.frame);
row.timestamp = string(st.timestamp);
row.t_sim_s = double(st.t_sim_s);
row.scenario_id = string(name);
row.environment = string(st.environment);
row.speed_kmph = double(st.speed_kmph);
row.snr_db = double(st.snr_db);
row.doppler_hz = double(st.doppler_hz);
row.carrier_frequency_hz = double(st.carrier_frequency_hz);
row.bandwidth_hz = double(st.bandwidth_hz);
row.channel_profile = string(st.channel_profile);
row.delay_spread_taps = int64(st.delay_spread_taps);
row.num_paths = int64(st.num_paths);
row.modulation = int64(st.modulation);
row.doppler_scale = double(st.doppler_scale);
row.mode = string(o.mode);
row.policy = string(o.policy);
row.scenario_seed = double(st.scenario_seed);
row.payload_seed = double(st.payload_seed);
row.channel_seed = double(st.channel_seed);
row.noise_seed = double(st.noise_seed);
row.frequency_offset_hz = double(st.frequency_offset);
row.phase_offset_rad = double(st.phase_offset);
row.timing_offset_samples = double(st.timing_offset);
end

function row = local_fill_result(row, res)
row.BER = res.BER;  row.SER = res.SER;  row.PER = res.PER;
row.throughput_bps = res.throughput_bps;
row.spectral_efficiency = res.spectral_efficiency;
row.CQI = res.CQI;
row.wall_clock_ms = res.wall_clock_ms;
row.detector_time_ms = res.detector_time_ms;  % legacy 'Latency_ms' value
row.latency_ms_modeled = NaN;              % not modeled (documented)
row.packet_loss = res.packet_loss;
row.recovery_rate = res.recovery_rate;
row.ACS = res.ACS;
row.tp_cap_bps = res.tp_cap_bps;   % ACS normalization caps (provenance)
row.se_cap = res.se_cap;
if res.error_flag
    row.error_flag = true;
    row.error_message = string(res.error_message);
end
end

function row = local_fill_regret(row)
row.BER_regret = row.BER - row.oracle_BER;
if isfinite(row.oracle_BER) && row.oracle_BER > 0
    row.relative_BER_regret = row.BER_regret / row.oracle_BER;
else
    row.relative_BER_regret = NaN;
end
row.ACS_regret = max(row.oracle_ACS - row.ACS, 0);
end

function fr = local_fb_reason(dec, fb_used)
fr = "";
if fb_used, fr = string(dec.reason); end
end

function v = local_pmf(s, wf, fld)
v = NaN;
try
    if isfield(s,wf) && isfield(s.(wf),fld) && ~isempty(s.(wf).(fld))
        v = double(s.(wf).(fld));
    end
catch
end
end

function v = local_unc(dec, wf, fld)
v = NaN;
try
    if isfield(dec,'uncertainty') && isfield(dec.uncertainty,wf) && ...
            isfield(dec.uncertainty.(wf),fld) && ...
            ~isempty(dec.uncertainty.(wf).(fld))
        v = double(dec.uncertainty.(wf).(fld));
    end
catch
end
end

function out = local_tern(c,a,b)
if c, out=a; else, out=b; end
end

function agg = local_aggregate(T, strat)
agg = table( ...
    repmat(string(strat),1,1)', ...
    numel(T.frame), ...
    mean(T.BER,'omitnan'), ...
    mean(T.SER,'omitnan'), ...
    mean(T.PER,'omitnan'), ...
    mean(T.throughput_bps,'omitnan'), ...
    mean(T.CQI,'omitnan'), ...
    mean(T.ACS,'omitnan'), ...
    max(T.ACS_regret,[],'omitnan'), ...
    sum(T.switched), ...
    mean(T.decision_correct,'omitnan'), ...
    sum(T.wall_clock_ms,'omitnan'), ...
    'VariableNames',{'strategy','frames','mean_BER','mean_SER','mean_PER', ...
    'mean_throughput_bps','mean_CQI','mean_ACS','max_ACS_regret', ...
    'switches','decision_correct_rate','total_wall_clock_ms'});
end
