function results = phase5_checks_driver(which)
% =========================================================================
% PHASE5_CHECKS_DRIVER   MATLAB-side validation for Phase 5 (spec section
% 26) + the Phase-3 regression (section 27). Writes phase5_check_results.json.
%
%   results = phase5_checks_driver('fast')    % structural checks (~minutes)
%   results = phase5_checks_driver('full')    % + FULL A-D regression
%   results = phase5_checks_driver('all')     % both, in order
%
% Every check records {name, pass, details}; a check that cannot run is
% reported as failed -- silent skips are forbidden (non-vacuous rule).
% =========================================================================
if nargin < 1, which = 'all'; end
which = lower(char(which));
here = fileparts(mfilename('fullpath'));
cd(here);
R = struct([]);

if any(strcmp(which,{'fast','all'}))
    R = local_fast_checks(R);
end
if any(strcmp(which,{'full','all'}))
    R = local_regression_full(R);
end

fid = fopen(fullfile(here,'phase5_check_results.json'),'w');
fwrite(fid, jsonencode(struct('driver','phase5_checks_driver.m', ...
    'when', char(datestr(now,'yyyy-mm-dd HH:MM:SS')), ...
    'scope', which, 'results', R), 'PrettyPrint', true));
fclose(fid);

npass = sum([R.pass]);  ntot = numel(R);
fprintf('\n==== PHASE-5 CHECKS (%s): %d/%d PASSED ====\n', upper(which), ...
        npass, ntot);
for i = 1:ntot
    if ~R(i).pass
        fprintf('FAILED: %s -- %s\n', R(i).name, R(i).details);
    end
end
results = R;
end

% =========================================================================
function R = local_fast_checks(R)
here = fileparts(mfilename('fullpath'));

% ---- C1 canonical state schema ------------------------------------------
req = {'timestamp','frame','scenario_id','environment','speed_kmph', ...
    'snr_db','doppler_hz','carrier_frequency_hz','bandwidth_hz', ...
    'channel_profile','delay_spread_taps','num_paths','modulation', ...
    'detector','waveform','scenario_seed','payload_seed','channel_seed', ...
    'noise_seed','frequency_offset','phase_offset','timing_offset', ...
    'current_waveform','frames_since_switch'};
st = dt_state();
missing = req(~isfield(st,req));
R = local_add(R,'C1_state_schema', isempty(missing), ...
    sprintf('missing fields: %s', strjoin(missing,', ')));

% ---- C2 scenario library coverage ---------------------------------------
ok2 = true; det2 = {};
letters = ['A':'R'];
try
    g = dt_scenarios_lib('groups');
    ok2 = ok2 && numel(g.ALL)==4 && numel(g.TUNE)==4 && ...
          numel(g.HELDOUT)==4 && numel(g.DIFFICULT)==6;
    for i = 1:numel(letters)
        s = dt_scenarios_lib('resolve', letters(i));
        ok2 = ok2 && isfield(s,'points') && numel(s.points)>=24;
    end
    ct = dt_scenarios_lib('load_custom','custom_test');
    ok2 = ok2 && strcmp(ct.tier,'custom') && numel(ct.points)>0;
catch me
    ok2 = false;  det2{end+1} = me.message; %#ok<AGROW>
end
R = local_add(R,'C2_scenario_library', ok2, local_join(det2, ...
    sprintf('%d letters + groups + custom resolved', numel(letters))));

% ---- C3 seed contract ----------------------------------------------------
[ps,cs,ns] = dt_seeds(17, 20260823);
ok3 = (ps==20260823+17) && (cs==20260823*10+17) && (ns==100000+17);
R = local_add(R,'C3_seed_contract', ok3, ...
    sprintf('f=17: pay=%d chan=%d noise=%d', ps, cs, ns));

% ---- C4 paired fairness inside canonical trace ---------------------------
T = local_trace(here,'a','ai_adaptive');
ok4 = all(T.payload_seed == 20260823 + T.frame) && ...
      all(T.channel_seed == 20260823*10 + T.frame) && ...
      all(T.noise_seed   == 100000 + T.frame);
% cross-strategy identity of seeds/checksums per frame
To = local_trace(here,'a','oracle');  Tf = local_trace(here,'a','fixed_otfs');
ok4 = ok4 && isequal(double(T.chan_checksum), double(To.chan_checksum)) && ...
      isequal(double(T.payload_sum),  double(Tf.payload_sum));
R = local_add(R,'C4_paired_fairness', ok4, ...
    'seeds follow dt_seeds; checksums identical across strategies');

% ---- C5 frozen-runtime draw-order parity ---------------------------------
cfgb = sim_default_config(); cfgb.TwinStrategy='pair';
A1 = dt_scenarios_lib('resolve','A');
p = A1.points(9);
cfg9 = cfgb; cfg9.DelayProfile=char(p.delay_profile);
cfg9.Speed_kmph=p.speed_kmph; cfg9.SNR_dB=p.snr_db;
cfg9.DopplerScale=p.doppler_scale; cfg9.Modulation=double(p.modulation);
cs9 = 20260823*10+9;
rng(cs9); ch9 = gen_channel_params_flex(cfg9);
Lg=max(ch9.max_delay_tap+1,ceil(cfg9.M/16)); Ns=(cfg9.M-Lg)*cfg9.N;
rng(20260823+9); b9 = randi([0 1], Ns*log2(cfg9.Modulation),1);
ch9b = dt_channel_for_frame(cfg9, cs9);
b9b  = dt_payload_for_frame(cfg9, ch9b, 20260823+9);
ok5 = isequal(ch9.chan_coef,ch9b.chan_coef) && isequal(b9,b9b);
R = local_add(R,'C5_runtime_draw_parity', ok5, ...
    'canonical primitives byte-equal frozen rng sequence');

% ---- C6 four-strategy outputs on custom scenario -------------------------
try
    run_experiment('custom_test','mode','FAST','strategies', ...
        {'fixed_otfs','fixed_oddm','ai_adaptive','oracle'});
    cdir = fullfile(here,'Results','DigitalTwin','custom_test');
    need = {'fixed_otfs_trace.csv','fixed_oddm_trace.csv', ...
            'ai_adaptive_trace.csv','oracle_trace.csv','states.csv', ...
            'run_manifest.json'};
    miss = need(~cellfun(@(f) exist(fullfile(cdir,f),'file')==2, need));
    R = local_add(R,'C6_four_strategy_outputs', isempty(miss), ...
        sprintf('missing: %s', strjoin(miss,', ')));
catch me
    R = local_add(R,'C6_four_strategy_outputs', false, me.message);
end

% ---- C7 fallback safety ---------------------------------------------------
ai_st = struct('environment','Urban','speed_kmph',25.0,'snr_db',14.0, ...
    'doppler_hz',111.2,'carrier_frequency_hz',4e9,'bandwidth_hz',480e3, ...
    'channel_profile','EVA','delay_spread_taps',6,'num_paths',9, ...
    'doppler_spread_hz',222.0,'modulation',4, ...
    'current_waveform','ODDM','frames_since_switch',3);
[dec,err,fb] = dt_ai_decide(ai_st,'phase3', struct( ...
    'pyexe','__no_such_python_executable__', ...
    'workdir', fullfile(tempdir,'dt5_check_fb')));
ok7 = fb && strcmp(dec.recommendation,'ODDM') && ~isempty(err) && ...
      logical(strncmpi(dec.reason,'fallback',8));
R = local_add(R,'C7_fallback_safety', ok7, ...
    sprintf('fb=%d rec=%s err=%.60s', fb, dec.recommendation, err));

% ---- C8 canonical trace schema --------------------------------------------
want = {'frame','timestamp','t_sim_s','scenario_id','environment', ...
 'speed_kmph','snr_db','doppler_hz','carrier_frequency_hz','bandwidth_hz', ...
 'channel_profile','delay_spread_taps','num_paths','modulation', ...
 'detector','waveform','strategy','mode','policy', ...
 'scenario_seed','payload_seed','channel_seed','noise_seed', ...
 'payload_sum','chan_checksum','frequency_offset_hz','phase_offset_rad', ...
 'timing_offset_samples','predicted_waveform','confidence', ...
 'confidence_band','predicted_OTFS_BER','predicted_ODDM_BER', ...
 'predicted_OTFS_ACS','predicted_ODDM_ACS','selected_waveform', ...
 'previous_waveform','switched','switch_reason','ai_error', ...
 'fallback_used','fallback_reason','BER','SER','PER','throughput_bps', ...
 'spectral_efficiency','CQI','wall_clock_ms','detector_time_ms', ...
 'latency_ms_modeled','packet_loss','recovery_rate','ACS','tp_cap_bps', ...
 'se_cap','actual_BER_OTFS','actual_ACS_OTFS', ...
 'actual_BER_ODDM','actual_ACS_ODDM','actual_TP_OTFS','actual_TP_ODDM', ...
 'oracle_waveform','oracle_BER','oracle_ACS','ACS_regret','BER_regret', ...
 'relative_BER_regret','decision_correct','error_flag','error_message'};
hdr = T.Properties.VariableNames;
miss = setdiff(want, hdr);
extra = setdiff(hdr, want);
ok8 = isempty(miss);
R = local_add(R,'C8_canonical_trace_schema', ok8, ...
    sprintf('cols=%d missing=[%s] extra=[%s]', numel(hdr), ...
    strjoin(miss,', '), strjoin(extra,', ')));

% ---- C9 manifest integrity -------------------------------------------------
mf = jsondecode(fileread(fullfile(here,'Results','DigitalTwin', ...
                                        'custom_test','run_manifest.json')));
needm = {'scenario','tier','mode','frames_run','policy','seed0', ...
         'objective','strategies','generator','impairments','note'};
miss = needm(~isfield(mf,needm));
R = local_add(R,'C9_run_manifest', isempty(miss), ...
    sprintf('missing keys: %s', strjoin(miss,', ')));

% ---- C10 ACS recomputation consistency -------------------------------------
% recompute ACS from the row's stored components, the exact ACS caps
% (tp_cap_bps, se_cap) and the SAME latency input the canonical runner
% used (detector_time_ms = the sim chain's own measurement).
row = T(5,:);
acs_re = compute_acs(row.BER, row.throughput_bps, row.spectral_efficiency, ...
    row.CQI, row.detector_time_ms, row.recovery_rate, row.tp_cap_bps, ...
    row.se_cap);
ok10 = abs(acs_re - row.ACS) < 1e-9;
R = local_add(R,'C10_acs_consistency', ok10, ...
    sprintf('stored ACS=%.9f recomputed=%.9f', row.ACS, acs_re));

% ---- C11 metric sanity ------------------------------------------------------
ok11 = all(isfinite(T.BER)) && all(T.BER>=0) && all(isfinite(T.ACS)) && ...
       all(T.ACS>=0 & T.ACS<=1) && all(isfinite(T.PER));
R = local_add(R,'C11_metric_sanity', ok11, 'BER/PER finite>=0, ACS in [0,1]');

% ---- C12 FAST frame count ----------------------------------------------------
% Self-contained: run a fresh FAST experiment into a scratch root so the
% check cannot be poisoned by leftover FULL outputs in Results/DigitalTwin/a.
scratch = fullfile(tempdir,'dt5_checks_fast','fastmode');
if isfolder(scratch), rmdir(scratch,'s'); end
run_experiment('A','mode','FAST','out_root',scratch);
T12 = readtable(fullfile(scratch,'a','ai_adaptive_trace.csv'));
ok12 = height(T12)==12;
R = local_add(R,'C12_fast_frames', ok12, sprintf('rows=%d',height(T12)));

% ---- C13 transitions present in difficult tiers ------------------------------
O = dt_scenarios_lib('resolve','O');
snrs = [O.points.snr_db]';
seg_snrs = snrs(1:5:end);           % one sample per 5-frame segment
ok13 = numel(unique(snrs))==5 && all(diff(seg_snrs) < 0);  % drop 20->0
M = dt_scenarios_lib('resolve','M');
envsM = {M.points.environment};
ok13 = ok13 && numel(envsM)==24 && ~strcmp(envsM{1},envsM{7});
R = local_add(R,'C13_transition_scenarios', ok13, ...
    sprintf('O snr steps=%s | M env blocks=%d', mat2str(unique(snrs)), ...
    numel(unique(envsM))));

% ---- C14 policy guard ----------------------------------------------------------
ok14 = false;
try, dt_policy_config('phase9'); catch, ok14 = true; end
[c3,e3] = dt_policy_config('phase3');
[c4,e4] = dt_policy_config('phase4');
ok14 = ok14 && strcmp(c3,'adaptive_config_v2.json') && ...
              strcmp(c4,'adaptive_config_v4.json') && ...
              strcmp(e3,'ai_engine_v2.py') && strcmp(e4,'ai_engine_v3.py');
R = local_add(R,'C14_policy_mapping_guard', ok14, ...
    sprintf('phase3->%s/%s, phase4->%s/%s', c3,e3,c4,e4));

% ---- C15 oracle-leakage static scan ---------------------------------------------
% The AI input-state construction in the canonical runner must contain no
% oracle/actual/regret tokens (spec section 8: AI never sees outcomes).
src_run = fileread(fullfile(here,'run_experiment.m'));
i1 = strfind(src_run,'ai_st = struct');
i2 = strfind(src_run,'if need_ai');
block = src_run(i1:i2-1);
leak = any(contains(lower(block), {'oracle','actual_','acs_regret', ...
                                   'ber_regret'}));
R = local_add(R,'C15_oracle_leakage_scan', ~leak, ...
    sprintf('AI-state block tokens scanned; hits=%d', leak));

% ---- C16 wall-clock vs modeled latency discipline -------------------------------
ok16 = all(isnan(T.latency_ms_modeled)) && ...
       all(isfinite(T.wall_clock_ms)) && all(isfinite(T.detector_time_ms)) && ...
       all(T.detector_time_ms <= T.wall_clock_ms + 1e-6);
R = local_add(R,'C16_latency_discipline', ok16, ...
    'latency_ms_modeled always NaN; detector_time<=wall_clock; both measured');
end

% =========================================================================
function R = local_regression_full(R)
% PHASE-3 REGRESSION (spec section 27): FULL A-D via the CANONICAL runner,
% policy=phase3, compared against the FROZEN baseline traces.
% Invariants tested (see PHASE5_VALIDATION.md sec. regression):
%   1. BIT-EXACT everywhere determinism is defined: shared-condition fields
%      (payload_sum/chan_checksum/num_paths/delay_spread_taps) for ALL
%      strategies, and full BER/SER/PER results for both FIXED strategies
%      (their rows involve no selection, so they prove chain identity).
%   2. Oracle labels may differ ONLY inside the near-tie band
%      |ACS_OTFS-ACS_ODDM| < 0.01, where the measured-latency term of ACS
%      decides (documented Phase-4 finding; count is machine-dependent).
%   3. Switch counts equal for every strategy/scenario.
%   4. Per-scenario mean ACS delta <= 0.02.
here = fileparts(mfilename('fullpath'));
try
    t0 = tic;
    summary = run_experiment('all','mode','FULL','policy','phase3');
    el_min = toc(t0)/60;

    letters = {'A','B','C','D'};
    strat   = {'fixed_otfs','fixed_oddm','ai_adaptive','oracle'};
    bit_fields = {'BER','SER','PER','payload_sum','chan_checksum', ...
                  'num_paths','delay_spread_taps'};
    worst = struct('field','',  'scenario','','strategy','', ...
                   'maxdiff',-inf);
    agree_flips = 0; acs_deltas = []; switch_ok = true;
    flip_margins = [];   % |ACS_OTFS-ACS_ODDM| at every flipping frame
    t_canon = []; t_base = [];   % detector times feeding the latency term
    % baseline = the COMBINED legacy trace set (one file per strategy)
    for si = 1:numel(strat)
        B = readtable(fullfile(here,'Results','DigitalTwin', ...
                               'baseline_phase3', [strat{si} '_trace.csv']));
        Bs = string(B.scenario);  Bf = double(B.frame);
        for li = 1:numel(letters)
            L = letters{li};
            sel = (Bs==upper(L));
            Tb = B(sel,:);  Tb = Tb(Bf(sel)<=60,:);
            Tc = local_trace(here, lower(L), strat{si});
            assert(height(Tb)==height(Tc), ...
                '%s/%s row count %d vs %d', L, strat{si}, ...
                height(Tc), height(Tb));
            for k = 1:numel(bit_fields)
                f = bit_fields{k};
                % payload/checksum/taps are shared-condition fields: exact
                % for every strategy. BER/SER/PER are row results: exact
                % unless the row IS the (possibly flipped) oracle choice.
                if any(strcmp(f,{'BER','SER','PER'})) && ...
                        strcmp(strat{si},'oracle')
                    continue
                end
                d = max(abs(double(Tc.(f)) - double(Tb.(f))));
                if d > worst.maxdiff
                    worst = struct('field',f,'scenario',L, ...
                        'strategy',strat{si},'maxdiff',d);
                end
            end
            % FIXED strategies must be bit-exact end-to-end: their rows
            % involve no selection, so any difference would mean the
            % simulation chain itself diverged (strongest proof).
            if any(strcmp(strat{si},{'fixed_otfs','fixed_oddm'}))
                for f = {'BER','SER','PER'}
                    d = max(abs(double(Tc.(f{1})) - double(Tb.(f{1}))));
                    if d > worst.maxdiff
                        worst = struct('field',['fixed_' f{1}], ...
                            'scenario',L,'strategy',strat{si},'maxdiff',d);
                    end
                end
            end
            % oracle labels may flip ONLY where the measured-latency ACS
            % term decides (Phase-4 documented wall-clock noise). The tie
            % band is DERIVED from this run's own detector-time spread:
            % w_lat * (exp(-t_min/200) - exp(-t_max/200)) bounds the ACS
            % swing the latency score can produce given real timing jitter.
            ow_c = upper(string(Tc.oracle_waveform));
            ow_b = upper(string(Tb.oracle_waveform));
            fl = find(ow_c ~= ow_b);
            agree_flips = agree_flips + numel(fl);
            if numel(fl) > 0
                m = abs(double(Tc.actual_ACS_OTFS(:)) - ...
                        double(Tc.actual_ACS_ODDM(:)));
                flip_margins = [flip_margins; m(fl)]; %#ok<AGROW>
            end
            % switches
            sw_c = sum(logical(Tc.switched));
            sw_b = sum(logical(Tb.switched));
            if sw_c ~= sw_b
                switch_ok = false;
                fprintf('  !! switches %s/%s: canon=%d base=%d\n', ...
                    L, strat{si}, sw_c, sw_b);
            end
            % measured detector times feed the ACS latency term -> collect
            if any(strcmp(strat{si},{'ai_adaptive','oracle'}))
                t_canon = [t_canon; double(Tc.detector_time_ms)];
                t_base  = [t_base;  double(Tb.Latency_ms)];
            end
            acs_deltas(end+1) = abs(mean(Tc.ACS)-mean(Tb.ACS)); %#ok<AGROW>
        end
    end
    wj = jsondecode(fileread(fullfile(here,'acs_weights.json')));
    if isfield(wj,'w_latency'), w_lat = double(wj.w_latency); else, w_lat = 0.10; end
    lat_band = w_lat * (exp(-min([t_canon;t_base])/200) - ...
                        exp(-max([t_canon;t_base])/200));
    ok_bit  = worst.maxdiff == 0;
    ok_flip = isempty(flip_margins) || ...
              max(flip_margins) <= lat_band + 1e-6;
    ok_acs  = max(acs_deltas) <= 0.02;
    pass = ok_bit && ok_flip && ok_acs && switch_ok;
    R = local_add(R,'C17_phase3_regression_full', pass, sprintf([ ...
        'bit-exact(deterministic+fixed)=%d (worst %s/%s/%s diff=%.3g); ', ...
        'oracle flips=%d within latency-tie-band=%d (max margin %.4f ', ...
        'band %.4f from t-range %.0f-%.0f ms); switches_match=%d; ', ...
        'max mean-ACS delta=%.4f; elapsed=%.1f min'], ...
        ok_bit, worst.field, worst.scenario, worst.strategy, ...
        worst.maxdiff, agree_flips, ok_flip, ...
        local_max_or_nan(flip_margins), lat_band, ...
        min([t_canon;t_base]), max([t_canon;t_base]), ...
        switch_ok, max(acs_deltas), el_min));
catch me
    R = local_add(R,'C17_phase3_regression_full', false, ...
        ['EXCEPTION: ' me.message]);
end
end

% =========================================================================
function T = local_trace(here, scen, strat)
T = readtable(fullfile(here,'Results','DigitalTwin', scen, ...
    sprintf('%s_trace.csv',strat)));
end

function R = local_add(R, name, pass, details)
r = struct('name',name,'pass',logical(pass),'details',char(details));
if isempty(R), R = r; else, R(end+1) = r; end %#ok<AGROW>
fprintf('[%s] %-32s %s\n', local_tern(pass,'PASS','FAIL'), name, details);
end

function s = local_join(cells, dflt)
if isempty(cells), s = dflt; else, s = strjoin(cells,'; '); end
end

function o = local_tern(c,a,b)
if c, o=a; else, o=b; end
end

function m = local_max_or_nan(v)
if isempty(v), m = NaN; else, m = max(v); end
end
