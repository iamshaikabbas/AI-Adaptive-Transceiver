function summary = digital_twin_runtime(scenario, mode, opts)
% [PHASE-5 NOTE] LEGACY but FROZEN: this validated reproducer produced the
% Phase-3/4 results and baseline_phase3/. The CANONICAL production runner
% is now run_experiment.m (same seeds/logic, standardized outputs).
% Kept UNCHANGED for regression proof -- do not extend.
% =========================================================================
% DIGITAL_TWIN_RUNTIME   Phase-3/4 closed-loop AI adaptive transceiver.
%
%   summary = digital_twin_runtime('all','FULL')            % A-D canonical
%   summary = digital_twin_runtime('A','FAST')
%   summary = digital_twin_runtime('tune','FAST')           % scenarios E-H
%   summary = digital_twin_runtime('heldout',struct('n_frames',24))
%   summary = digital_twin_runtime('difficult', ...)
%
% scenario: 'all'={A,B,C,D} (final-eval set) | 'tune'={E,F,G,H} |
%   'heldout'={I,J,K,L} | 'difficult'={M,N,O,P,Q,R} | any existing letter.
% mode: 'FULL' (60) | 'FAST' (12); opts.n_frames overrides both.
%
% opts (all optional):
%   .strategies  cell subset of {fixed_otfs,fixed_oddm,ai_adaptive,oracle}
%                (default all four; AI python call only if ai_adaptive used)
%   .tag         suffix for output files, e.g. '_p4' -> ai_adaptive_trace_a_p4.csv;
%                default '' reproduces Phase-3 filenames exactly
%   .config_file policy JSON read from this folder (default adaptive_config_v2.json)
%   .engine_py   engine script inside otfs_ai_pipeline (default ai_engine_v2.py)
%   .seed0       master seed (default 20260823)
%
% Paired fairness per frame: ONE channel realization + ONE payload + ONE
% noise seed shared by EVERY strategy; BOTH waveforms executed on identical
% inputs so oracle = best actual objective and any policy can be replayed
% offline against recorded paired actuals.
% =========================================================================
if nargin < 1, scenario = 'all'; end
if nargin < 2 || isempty(mode), mode = 'FULL'; end
if isstruct(mode)               % convenience: opts passed as 2nd argument
    opts = mode; mode = 'FULL';
elseif nargin < 3 || isempty(opts)
    opts = struct();
end
if ~isfield(opts,'strategies') || isempty(opts.strategies)
    opts.strategies = {'fixed_otfs','fixed_oddm','ai_adaptive','oracle'};
end
if ~isfield(opts,'tag'),             opts.tag = ''; end
if ~isfield(opts,'config_file'),     opts.config_file = 'adaptive_config_v2.json'; end
if ~isfield(opts,'engine_py'),       opts.engine_py = 'ai_engine_v2.py'; end
if ~isfield(opts,'seed0'),           opts.seed0 = 20260823; end
mode = upper(mode);
switch mode
    case 'FULL', n_frames = 60;
    case 'FAST', n_frames = 12;
    otherwise, error('mode must be FAST or FULL');
end
if isfield(opts,'n_frames') && ~isempty(opts.n_frames)
    n_frames = double(opts.n_frames);
end

here = fileparts(mfilename('fullpath'));
outdir = fullfile(here,'Results','DigitalTwin');
if ~exist(outdir,'dir'), mkdir(outdir); end

pyexe = 'C:\MY DATA ANALYTICS FILES AND PROJECTS\MAJOR\AI-Adaptive-Transceiver\.venv\Scripts\python.exe';
if exist(pyexe,'file') ~= 2, pyexe = 'python'; end

cfgpol = jsondecode(fileread(fullfile(here,opts.config_file)));
if isfield(cfgpol,'objective'),           objkey = 'objective';
elseif isfield(cfgpol,'decision_objective'), objkey = 'decision_objective';
else, error('config %s has no objective key', opts.config_file);
end
objective = upper(cfgpol.(objkey));
if ~any(strcmp(objective,{'ACS','BER'})), objective = 'ACS'; end

seed0 = double(opts.seed0);
c_light = 299792458;
need_ai = any(strcmp(opts.strategies,'ai_adaptive'));

scen_names = local_scenario_list(scenario);
all_traces = struct();          % dynamic fields per strategy (cell arrays)
t_start = tic;

for si = 1:numel(scen_names)
    sn = scen_names{si};
    jf = fullfile(outdir,sprintf('scenario_%s.json',lower(sn)));
    assert(exist(jf,'file')==2, 'missing %s', jf);
    js = jsondecode(fileread(jf));
    pts = js.points;
    nF = min(n_frames, numel(pts));
    fprintf('\n=== SCENARIO %s (%s): %d frames ===\n', upper(sn), mode, nF);

    cfg_base = sim_default_config();
    cfg_base.TwinStrategy = 'pair';

    prev_wf  = 'OTFS';                  % deployment default at startup
    dwell    = 99;
    rows     = struct();                % filled per requested strategy
    states   = [];                      % AI feature vectors (offline replay)

    for f = 1:nF
        p  = pts(f);
        pt = struct('environment',char(p.environment), ...
            'speed_kmph',p.speed_kmph,'snr_db',p.snr_db, ...
            'delay_profile',char(p.delay_profile), ...
            'doppler_scale',p.doppler_scale,'modulation',double(p.modulation), ...
            't_s',p.t_s,'frame',double(f));
        mod_bits = log2(double(pt.modulation));

        cfg_f = cfg_base;
        cfg_f.DelayProfile = pt.delay_profile;
        cfg_f.Speed_kmph   = pt.speed_kmph;
        cfg_f.SNR_dB       = pt.snr_db;
        cfg_f.DopplerScale = pt.doppler_scale;
        cfg_f.Modulation   = double(pt.modulation);

        % ---- shared physical conditions for ALL strategies (sec. 21) ---
        rng(seed0*10 + f);
        chan = gen_channel_params_flex(cfg_f);
        % payload sized to THIS frame's channel (identical for every
        % strategy; A-D frames are unaffected because their probe-sized
        % Phase-3 runs never errored => Lg_f equals the old probe value)
        Lg_f     = max(chan.max_delay_tap+1, ceil(cfg_f.M/16));
        N_syms_f = (cfg_f.M - Lg_f) * cfg_f.N;
        rng(seed0 + f);                 % deterministic payload
        tx_bits = randi([0 1], N_syms_f*mod_bits, 1);
        seed_frame = 100000 + f;
        doppler_hz = (pt.speed_kmph*(1000/3600)/c_light) * cfg_f.car_fre ...
                     * pt.doppler_scale;
        pay_sum = sum(double(tx_bits)); chan_sum = sum(abs(chan.chan_coef(:)));

        % ---- execute BOTH waveforms on identical inputs -----------------
        [res_o, err_o] = local_run(cfg_f,chan,tx_bits,seed_frame,'OTFS');
        [res_d, err_d] = local_run(cfg_f,chan,tx_bits,seed_frame,'ODDM');

        N_bits_f = N_syms_f * mod_bits;
        frame_T_o = cfg_f.frame_T;
        L_cp      = max(chan.max_delay_tap+1, 2);
        frame_T_d = cfg_f.frame_T + L_cp/cfg_f.fs;
        se_cap    = mod_bits;
        [acs_o] = local_acs(res_o, N_bits_f/frame_T_o, se_cap, err_o);
        [acs_d] = local_acs(res_d, N_bits_f/frame_T_d, se_cap, err_d);

        if strcmp(objective,'BER')
            if res_o.BER <= res_d.BER, orc_wf='OTFS'; else, orc_wf='ODDM'; end
        else
            if acs_o >= acs_d, orc_wf='OTFS'; else, orc_wf='ODDM'; end
        end
        orc_ber = min(local_val(res_o,'BER',err_o), local_val(res_d,'BER',err_d));
        orc_acs = max(acs_o, acs_d);

        % ---- AI decision (closed loop; never sees oracle results) ------
        % field names EXACTLY match the v2 training feature columns
        state = struct( ...
            'environment', pt.environment, ...
            'speed_kmph', pt.speed_kmph, ...
            'snr_db', pt.snr_db, ...
            'doppler_hz', doppler_hz, ...
            'carrier_frequency_hz', cfg_f.car_fre, ...
            'bandwidth_hz', cfg_f.BW, ...
            'channel_profile', char(chan.profile), ...
            'delay_spread_taps', double(chan.max_delay_tap), ...
            'num_paths', double(chan.taps), ...
            'doppler_spread_hz', double(chan.doppler_spread_hz), ...
            'modulation', double(pt.modulation), ...
            'current_waveform', prev_wf, ...
            'frames_since_switch', dwell);
        if need_ai
            [dec, ai_err, fb_used] = local_ai(state, here, pyexe, ...
                                              opts.engine_py, opts.config_file);
        else
            % collection run: paired actuals only, no policy in the loop
            dec = struct('recommendation',prev_wf,'best_by_objective','', ...
                'detector','','confidence',NaN,'reason','not requested', ...
                'predicted_metrics',struct());
            ai_err = 'ai not requested'; fb_used = false;
        end
        st_row = state;  st_row.scenario = string(sn);  st_row.frame = f;
        if isempty(states), states = st_row;
        else,               states(end+1) = st_row; end %#ok<AGROW>

        sel_wf = dec.recommendation;
        if ~any(strcmp({'OTFS','ODDM'}, char(sel_wf)))
            sel_wf = prev_wf;           % defensive: keep current
        end

        % ---- ACTUALLY EXECUTE the selected waveform (sec. 6) ------------
        switch sel_wf
            case 'OTFS'      % identical inputs -> identical deterministic result
                res_sel = res_o; err_sel = err_o;  acs_sel = acs_o;
            otherwise
                res_sel = res_d; err_sel = err_d;  acs_sel = acs_d;
        end

        % ---- rows --------------------------------------------------------
        base = dt3_empty_row();
        base.timestamp = string(datestr(now,'yyyy-mm-dd HH:MM:SS'));
        base.scenario  = string(sn);  base.mode = string(mode);
        base.frame = f;  base.t_s = pt.t_s;
        base.environment = string(pt.environment);
        base.speed_kmph = pt.speed_kmph;  base.snr_db = pt.snr_db;
        base.doppler_hz = doppler_hz;
        base.carrier_frequency_hz = cfg_f.car_fre;
        base.bandwidth_hz = cfg_f.BW;
        base.channel_profile = string(pt.delay_profile);
        base.modulation = int64(pt.modulation);
        base.seed_frame = seed_frame;
        base.payload_sum = pay_sum;  base.chan_checksum = chan_sum;
        base.num_paths = chan.taps;
        base.delay_spread_taps = chan.max_delay_tap;
        base.actual_TP_OTFS  = local_val(res_o,'Throughput_bps',err_o);
        base.actual_TP_ODDM  = local_val(res_d,'Throughput_bps',err_d);
        base.actual_CQI_OTFS = local_val(res_o,'CQI',err_o);
        base.actual_CQI_ODDM = local_val(res_d,'CQI',err_d);

        r_fix_o = base;  r_fix_o.strategy = string('fixed_otfs');
        r_fix_o.waveform = string('OTFS');
        r_fix_o.detector = string('MRC');
        r_fix_o = local_fill_actual(r_fix_o,res_o,err_o,acs_o);
        r_fix_o.oracle_waveform = string(orc_wf);
        r_fix_o.oracle_BER = orc_ber;  r_fix_o.oracle_ACS = orc_acs;
        r_fix_o.actual_BER_OTFS = local_val(res_o,'BER',err_o);
        r_fix_o.actual_ACS_OTFS = acs_o;
        r_fix_o.actual_BER_ODDM = local_val(res_d,'BER',err_d);
        r_fix_o.actual_ACS_ODDM = acs_d;
        [r_fix_o] = local_regret(r_fix_o, r_fix_o.BER, r_fix_o.ACS);

        r_fix_d = base;  r_fix_d.strategy = string('fixed_oddm');
        r_fix_d.waveform = string('ODDM');  r_fix_d.detector = string('LMMSE');
        r_fix_d = local_fill_actual(r_fix_d,res_d,err_d,acs_d);
        r_fix_d.oracle_waveform = string(orc_wf);
        r_fix_d.oracle_BER = orc_ber;  r_fix_d.oracle_ACS = orc_acs;
        r_fix_d.actual_BER_OTFS = r_fix_o.actual_BER_OTFS;
        r_fix_d.actual_ACS_OTFS = acs_o;
        r_fix_d.actual_BER_ODDM = local_val(res_d,'BER',err_d);
        r_fix_d.actual_ACS_ODDM = acs_d;
        [r_fix_d] = local_regret(r_fix_d, r_fix_d.BER, r_fix_d.ACS);

        r_orc = base;  r_orc.strategy = string('oracle');
        r_orc.waveform = string(orc_wf);
        if strcmp(orc_wf,'OTFS'), r_orc.detector = string('MRC');
        else,                     r_orc.detector = string('LMMSE'); end
        if strcmp(orc_wf,'OTFS'), r_orc = local_fill_actual(r_orc,res_o,err_o,acs_o);
        else,                     r_orc = local_fill_actual(r_orc,res_d,err_d,acs_d); end
        r_orc.oracle_waveform = string(orc_wf);
        r_orc.oracle_BER = orc_ber;  r_orc.oracle_ACS = orc_acs;
        r_orc.actual_BER_OTFS = r_fix_o.actual_BER_OTFS;
        r_orc.actual_ACS_OTFS = acs_o;
        r_orc.actual_BER_ODDM = r_fix_o.actual_BER_ODDM;
        r_orc.actual_ACS_ODDM = acs_d;

        r_ai = base;  r_ai.strategy = string('ai_adaptive');
        r_ai.predicted_waveform = string(dec.best_by_objective);
        r_ai.confidence = dec.confidence;
        pm = dec.predicted_metrics;
        r_ai.pred_BER_OTFS = local_pmf(pm,'OTFS','BER');
        r_ai.pred_BER_ODDM = local_pmf(pm,'ODDM','BER');
        r_ai.pred_TP_OTFS  = local_pmf(pm,'OTFS','Throughput_bps');
        r_ai.pred_TP_ODDM  = local_pmf(pm,'ODDM','Throughput_bps');
        r_ai.pred_CQI_OTFS = local_pmf(pm,'OTFS','CQI');
        r_ai.pred_CQI_ODDM = local_pmf(pm,'ODDM','CQI');
        r_ai.pred_ACS_OTFS = local_pmf(pm,'OTFS','ACS');
        r_ai.pred_ACS_ODDM = local_pmf(pm,'ODDM','ACS');
        r_ai.unc_ACS_OTFS  = local_unc(dec,'OTFS','ACS');
        r_ai.unc_ACS_ODDM  = local_unc(dec,'ODDM','ACS');
        r_ai.unc_LogBER_OTFS = local_unc(dec,'OTFS','Log10BER');
        r_ai.unc_LogBER_ODDM = local_unc(dec,'ODDM','Log10BER');
        if isfield(dec,'confidence_band')
            r_ai.confidence_band = string(char(dec.confidence_band));
        end
        switched = ~strcmpi(sel_wf, prev_wf);
        r_ai.previous_waveform = string(prev_wf);
        r_ai.switched = switched;
        r_ai.switch_reason = string(dec.reason);
        fb_flag = fb_used || (isfield(dec,'fallback') && ~isempty(dec.fallback) ...
                              && logical(dec.fallback));
        r_ai.fallback_used = logical(fb_flag);
        if isfield(dec,'confidence_band')
            r_ai.confidence_band = string(char(dec.confidence_band));
        end
        r_ai.error_message = string(ai_err);
        r_ai.waveform = string(sel_wf);
        r_ai.detector = string(dec.detector);
        r_ai = local_fill_actual(r_ai,res_sel,err_sel,acs_sel);
        r_ai.oracle_waveform = string(orc_wf);
        r_ai.oracle_BER = orc_ber;  r_ai.oracle_ACS = orc_acs;
        r_ai.actual_BER_OTFS = r_fix_o.actual_BER_OTFS;
        r_ai.actual_ACS_OTFS = acs_o;
        r_ai.actual_BER_ODDM = r_fix_o.actual_BER_ODDM;
        r_ai.actual_ACS_ODDM = acs_d;
        [r_ai] = local_regret(r_ai, r_ai.BER, r_ai.ACS);
        r_ai.decision_correct = strcmpi(sel_wf, orc_wf);

        newrows = {'fixed_otfs',r_fix_o;'fixed_oddm',r_fix_d; ...
                   'ai_adaptive',r_ai;'oracle',r_orc};
        for k = 1:size(newrows,1)
            fn = newrows{k,1};
            if ~any(strcmp(opts.strategies, fn)), continue; end
            if ~isfield(rows, fn)
                rows.(fn) = newrows{k,2};
            else
                tmp = rows.(fn);
                tmp(end+1) = newrows{k,2};  %#ok<AGROW>
                rows.(fn) = tmp;
            end
        end
        if switched, dwell = 0;
        else,        dwell = dwell + 1; end
        if ~fb_used, prev_wf = sel_wf; end

        fprintf(['f%02d %5.1fkm/h %5.1fdB M%d | pred %s conf%.2f | sel %s ' ...
                 '%s | oracle %s | BER %.2e ACS %.3f%s\n'], ...
            f, pt.speed_kmph, pt.snr_db, pt.modulation, ...
            dec.best_by_objective, dec.confidence, sel_wf, ...
            tern(switched,'SWITCH','      '), orc_wf, ...
            r_ai.BER, r_ai.ACS, tern(fb_used,' [FB]',''));
    end

    fns = fieldnames(rows);
    for i = 1:numel(fns)
        if ~isfield(all_traces, fns{i}), all_traces.(fns{i}) = {}; end
        all_traces.(fns{i}){end+1} = rows.(fns{i});   %#ok<AGROW>
    end

    local_write(rows, outdir, sn, opts.tag);
    writetable(struct2table(states), fullfile(outdir, ...
        sprintf('states_%s%s.csv', lower(sn), opts.tag)));
end

% ---- canonical combined traces ---------------------------------------------
if numel(scen_names)>1
    local_write_all(all_traces, outdir, opts.tag);
end

summary = struct();
summary.scenarios = strjoin(scen_names,',');
summary.mode = mode;
summary.frames_per_scenario = n_frames;
summary.objective = objective;
summary.strategies = strjoin(opts.strategies,',');
summary.config_file = opts.config_file;
summary.engine_py = opts.engine_py;
summary.output_tag = opts.tag;
summary.elapsed_min = toc(t_start)/60;
fprintf('\nRUNTIME DONE (%s, %s) in %.1f min\n', scenario, mode, ...
        summary.elapsed_min);
end

% =========================================================================
function names = local_scenario_list(s)
groups = struct('ALL',{{'A','B','C','D'}}, ...
                'TUNE',{{'E','F','G','H'}}, ...
                'HELDOUT',{{'I','J','K','L'}}, ...
                'DIFFICULT',{{'M','N','O','P','Q','R'}});
if ischar(s) || isstring(s)
    key = upper(char(s));
    if isfield(groups,key), names = groups.(key);
    else,                   names = {key};
    end
else
    names = arrayfun(@(x) upper(char(x)), s, 'UniformOutput', false);
end
end

function [res, err] = local_run(cfg, chan, bits, seed, wf)
c = cfg; c.chan = chan; c.tx_bits = bits; c.noise_seed = seed;
c.Waveform = wf; c.([wf '_Detector']) = twin_default_detector(wf);
err = '';
try
    switch wf
        case 'OTFS', res = run_otfs(c);
        case 'ODDM', res = run_oddm(c);
        otherwise, error('bad waveform');
    end
catch me
    res = []; err = me.message;
end
end

function v = local_val(res, field, err)
if isempty(err) && ~isempty(res) && isfield(res,field)
    v = double(res.(field));
else
    v = NaN;
end
end

function acs_v = local_acs(res, tp_cap, se_cap, err)
if isempty(err) && ~isempty(res)
    acs_v = compute_acs(res.BER, res.Throughput_bps, res.SpectralEfficiency, ...
                        res.CQI, res.Latency_ms, res.RecoveryRate, ...
                        tp_cap, se_cap);
else
    acs_v = NaN;
end
end

function r = local_fill_actual(r, res, err, acs_override)
r.BER = local_val(res,'BER',err);
r.SER = local_val(res,'SER',err);
r.PER = local_val(res,'PER',err);
r.Throughput_bps = local_val(res,'Throughput_bps',err);
r.SpectralEfficiency_bps_per_Hz = local_val(res,'SpectralEfficiency',err);
r.CQI = local_val(res,'CQI',err);
r.Latency_ms = local_val(res,'Latency_ms',err);
r.PacketLoss = local_val(res,'PacketLoss',err);
r.RecoveryRate = local_val(res,'RecoveryRate',err);
if ~isempty(err) || isempty(res)
    r.error_flag = true; r.error_message = string(err);
end
if ~isempty(acs_override), r.ACS = acs_override; end
end

function [r] = local_regret(r, ber, acs)
r.BER_regret = ber - r.oracle_BER;
if isfinite(r.oracle_BER) && r.oracle_BER > 0
    r.relative_BER_regret = r.BER_regret / r.oracle_BER;
else
    r.relative_BER_regret = NaN;    % meaningless near zero-BER floor
end
r.ACS_regret = max(r.oracle_ACS - acs, 0);
end

function [dec, err, fb] = local_ai(state, here, pyexe, engine_py, cfg_name)
dec = struct('recommendation','','best_by_objective','','detector','', ...
             'confidence',NaN,'reason','ai call failed', ...
             'predicted_metrics',struct());
err = ''; fb = false;
fin = fullfile(here,'_ai_state.json');  fout = fullfile(here,'_ai_decision.json');
fid = fopen(fin,'w'); fwrite(fid,jsonencode(state)); fclose(fid);
cmd = sprintf(['cd /d "%s" && "%s" %s --infile "%s" --out "%s" ' ...
               '--config "%s"'], ...
              fullfile(here,'otfs_ai_pipeline'), pyexe, engine_py, fin, fout, ...
              fullfile(here, cfg_name));
try
    [st,msg] = system(cmd);
    if st == 0 && exist(fout,'file')==2
        dec = jsondecode(fileread(fout));
        % ensure plain char fields survive jsondecode scalars
        dec.recommendation = char(dec.recommendation);
        dec.best_by_objective = char(dec.best_by_objective);
        dec.detector = char(dec.detector);
        dec.reason = char(dec.reason);
    else
        err = ['python failed: ' strtrim(msg)];
        fb = true;
    end
catch me
    err = ['python exception: ' me.message];
    fb = true;
end
if fb
    dec.recommendation = state.current_waveform;
    dec.best_by_objective = state.current_waveform;
    dec.detector = twin_default_detector(state.current_waveform);
    dec.reason = ['fallback keep current: ' err];
    dec.confidence = NaN;
    dec.predicted_metrics = struct( ...
        'OTFS', struct('BER',NaN,'Throughput_bps',NaN,'CQI',NaN,'ACS',NaN), ...
        'ODDM', struct('BER',NaN,'Throughput_bps',NaN,'CQI',NaN,'ACS',NaN));
end
end

function out = tern(c, a, b)
if c, out = a; else, out = b; end
end

function v = local_pmf(s, wf, fld)
% safe field extraction from decoded JSON structs; NaN when absent
v = NaN;
try
    if isfield(s,wf) && isfield(s.(wf),fld) && ~isempty(s.(wf).(fld))
        v = double(s.(wf).(fld));
    end
catch
end
end

function v = local_unc(dec, wf, fld)
% phase-4 engines may attach dec.uncertainty.<waveform>.<target>; NaN otherwise
v = NaN;
try
    if isfield(dec,'uncertainty') && isfield(dec.uncertainty, wf) && ...
            isfield(dec.uncertainty.(wf), fld) && ...
            ~isempty(dec.uncertainty.(wf).(fld))
        v = double(dec.uncertainty.(wf).(fld));
    end
catch
end
end

function local_write(rows, outdir, tag, suffix)
fns = fieldnames(rows);
for i = 1:numel(fns)
    T = struct2table(rows.(fns{i}));
    writetable(T, fullfile(outdir, ...
        sprintf('%s_trace_%s%s.csv', fns{i}, lower(tag), suffix)));
end
end

function local_write_all(all_traces, outdir, suffix)
fns = fieldnames(all_traces);
for i = 1:numel(fns)
    cells = all_traces.(fns{i});
    T = cell(numel(cells),1);
    for k = 1:numel(cells)
        T{k} = struct2table(cells{k});
    end
    writetable(vertcat(T{:}), fullfile(outdir, ...
        sprintf('%s_trace%s.csv', fns{i}, suffix)));
end
end
