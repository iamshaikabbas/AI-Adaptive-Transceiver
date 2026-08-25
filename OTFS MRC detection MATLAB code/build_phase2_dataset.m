% =========================================================================
% build_phase2_dataset.m   [Phase 2 / STEPS 3+4]
%
% Generates the EXPANDED paired OTFS/ODDM dataset and the condition-level
% performance map, using a leak-free-by-construction split:
%
%   TRAIN : SNR {-10 -5 0 5 10 15 20} x speed {0 20 60 100 150 200 300}
%           x profile {EPA EVA ETU} x mod {QPSK,16QAM}          (294 conds)
%   TEST  : UNSEEN axis values SNR {-3 2 7 12 17 22}
%           x speed {10 40 80 120 250 350} x same profiles/mods (216 conds)
%   VAL   : deterministic ~20 % holdout of TRAIN conditions
%   slices: 64-QAM (train+test subsets) and carrier sensitivity
%           fc in {2, 5.9} GHz (train+test subsets), FULL mode only
%
% Every condition runs nTrials PAIRED trials per waveform (identical
% channel realization / payload / noise seed per trial; only the waveform
% differs -- guaranteed by run_paired_trials.m).
%
% Outputs (Results/WaveformComparison/):
%   phase2_dataset.csv          one row per (condition x waveform)
%   phase2_performance_map.csv  one row per condition incl. best_waveform
%   phase2_dataset_meta.json    axes, rules, counts, reproducibility info
%
% Label rules (documented, nothing forced):
%   best_waveform = argmax ACS (default objective) or argmin BER;
%   ties: |dACS| < tie_tol_acs OR relative BER gap < tie_tol_ber_rel => 'tie'
%   best_by_BER and best_by_ACS are BOTH recorded so the objective can be
%   reconfigured later without re-simulating.
% =========================================================================
clearvars; clc;
C = dt_config('full');
if ~exist(C.outdir,'dir'), mkdir(C.outdir); end
rng(C.rng_seed);

D  = C.combos;
nT = C.nTrials;

% ---- assemble the condition list -----------------------------------------
conds = struct('profile',{},'speed',{},'snr',{},'mod',{},'fc',{},'split',{});
for ip = 1:numel(C.profiles)
  for v = C.speed_train
    for s = C.snr_train
      conds = add_cond(conds, C.profiles{ip}, v, s, 4,  C.carrier_hz, 'train');
      conds = add_cond(conds, C.profiles{ip}, v, s, 16, C.carrier_hz, 'train');
    end
  end
end
for ip = 1:numel(C.profiles)
  for v = C.speed_test
    for s = C.snr_test
      conds = add_cond(conds, C.profiles{ip}, v, s, 4,  C.carrier_hz, 'test');
      conds = add_cond(conds, C.profiles{ip}, v, s, 16, C.carrier_hz, 'test');
    end
  end
end

if C.include_64qam_slice
  for ip = 1:numel(C.profiles)
    for v = C.qam64_speeds
      for s = C.qam64_snrs
        conds = add_cond(conds, C.profiles{ip}, v, s, 64, C.carrier_hz, 'train');
      end
    end
    for s = [7 17]                          % unseen SNR values
      for v = [40 120 250]                  % unseen/test speeds
        conds = add_cond(conds, C.profiles{ip}, v, s, 64, C.carrier_hz, 'test');
      end
    end
  end
end

if C.carrier_slice
  fcs = setdiff(C.carrier_alts, C.carrier_hz);          % 2 GHz and 5.9 GHz
  for fc = fcs
    for v = [150 350], s_list = [5 15];                 % train-lattice values
      for s = s_list
        conds = add_cond(conds, 'EVA', v, s, 4, fc, 'train');
      end
    end
    for v = [40 250], s_list = [2 17];                  % test-lattice values
      for s = s_list
        conds = add_cond(conds, 'EVA', v, s, 4, fc, 'test');
      end
    end
  end
end

nCond = numel(conds);

% ---- validation holdout: deterministic 20 % of TRAIN conditions ------------
tr_ids  = find(strcmp({conds.split},'train'));
perm    = randperm(numel(tr_ids));
n_val   = round(0.2*numel(tr_ids));
val_ids = tr_ids(perm(1:n_val));

fprintf(['PHASE2 DATASET: %d conditions (%d train / %d val / %d test) ' ...
         'x %d waveforms x %d paired trials\n'], nCond, ...
         numel(tr_ids)-n_val, n_val, nCond-numel(tr_ids), numel(D), nT);
t0 = tic;

rows = cell(0, 27);
map  = cell(0, 28);
env_names = {C.environments.name};
env_vmax  = [C.environments.vmax];

for k = 1:nCond
  cd_   = conds(k);
  if any(val_ids == k), split = 'val'; else, split = cd_.split; end

  cfg = sim_default_config('DelayProfile',cd_.profile,'Speed_kmph',cd_.speed, ...
                           'Modulation',cd_.mod,'SNR_dB',cd_.snr);
  cfg.car_fre = cd_.fc;
  cfg.cfo_hz                = C.impairments.cfo_hz;
  cfg.phase_offset_rad      = C.impairments.phase_offset_rad;
  cfg.timing_offset_samples = C.impairments.timing_offset_samples;

  probe = cfg; probe.chan = [];
  pchan = gen_channel_params_flex(probe);     % feature source (probe draw)
  Lg     = max(pchan.max_delay_tap+1, ceil(cfg.M/16));
  N_bits = (cfg.M-Lg)*cfg.N*log2(cd_.mod);
  L_cp   = max(pchan.max_delay_tap+1, 2);     % mirrors run_oddm.m

  S = run_paired_trials(D, cfg, nT);

  env_i = find(cd_.speed <= env_vmax, 1);
  if isempty(env_i), env_i = numel(env_vmax); end
  dop_hz = dt_derive_doppler(cd_.speed, cd_.fc, 1);

  acs_vals = zeros(1, numel(D));
  for i = 1:numel(D)
    wf = S(i).wf;
    if strcmpi(wf,'OTFS'), frame_T = cfg.frame_T;
    else,                  frame_T = cfg.frame_T + L_cp/cfg.fs; end
    tp_cap   = N_bits/frame_T;
    se_cap   = log2(cd_.mod);
    rec_rate = 1 - S(i).PER_mean;
    [acs_vals(i),~] = compute_acs(S(i).BER_total, S(i).Thr_mean, ...
        S(i).SE_mean, S(i).CQI_mean, S(i).Lat_mean, rec_rate, tp_cap, se_cap);

    rows(end+1,:) = {k, datestr(now,'yyyy-mm-dd HH:MM:SS'), split, ...
        env_names{env_i}, cd_.speed, cd_.snr, dop_hz, cd_.fc, ...
        C.bandwidth_hz, cd_.profile, pchan.max_delay_tap, pchan.taps, ...
        pchan.doppler_spread_hz, cd_.mod, S(i).det, S(i).wf, nT, ...
        S(i).BER_total, S(i).SER_total, S(i).PER_mean, S(i).Thr_mean, ...
        S(i).SE_mean, S(i).Lat_mean, S(i).PER_mean, rec_rate, ...
        S(i).CQI_mean, acs_vals(i)};                    %#ok<AGROW>
  end

  % ---- performance-map row -------------------------------------------------
  ber_o   = [S.BER_total];
  [~, b_ber] = min(ber_o);
  [~, b_acs] = max(acs_vals);
  gap_ber = abs(ber_o(1)-ber_o(2)) / max(min(ber_o), 1e-12);
  gap_acs = abs(acs_vals(1)-acs_vals(2));
  if gap_acs < C.tie_tol_acs || gap_ber < C.tie_tol_ber_rel, tie = true; else, tie = false; end
  switch C.objective
    case 'ACS', best_wf = S(b_acs).wf;
    case 'BER', best_wf = S(b_ber).wf;
    otherwise, error('unknown objective %s', C.objective);
  end
  if tie && ~strcmpi(S(b_acs).wf, S(b_ber).wf)
    best_wf = 'tie';    % objectives disagree within tolerance -> no label
  elseif tie
    best_wf = ['tie_' lower(best_wf)];  % both agree but margin is tiny
  end

  map(end+1,:) = {k, env_names{env_i}, cd_.speed, cd_.snr, cd_.profile, ...
      cd_.mod, cd_.fc, split, dop_hz, pchan.max_delay_tap, pchan.taps, ...
      S(1).name, ber_o(1), S(1).Thr_mean, S(1).CQI_mean, S(1).SE_mean, ...
      acs_vals(1), ...
      S(2).name, ber_o(2), S(2).Thr_mean, S(2).CQI_mean, S(2).SE_mean, ...
      acs_vals(2), ...
      S(b_ber).wf, S(b_acs).wf, best_wf, gap_ber, gap_acs};   %#ok<AGROW>

  if mod(k,25)==0 || k==nCond
    fprintf('[%3d/%3d] elapsed %.1f min\n', k, nCond, toc(t0)/60);
  end
end

% ---- write CSVs --------------------------------------------------------------
ds_hdr = {'scenario_id','timestamp','split','environment','speed_kmph', ...
  'snr_db','doppler_hz','carrier_frequency_hz','bandwidth_hz', ...
  'channel_profile','delay_spread_taps','num_paths','doppler_spread_hz', ...
  'modulation','detector','waveform','n_trials','BER','SER','PER', ...
  'throughput_bps','spectral_efficiency','latency_ms','packet_loss', ...
  'recovery_rate','CQI','ACS'};
ds = cell2table(rows, 'VariableNames', ds_hdr);
writetable(ds, fullfile(C.outdir,'phase2_dataset.csv'));

map_hdr = {'scenario_id','environment','speed_kmph','snr_db', ...
  'channel_profile','modulation','carrier_frequency_hz','split','doppler_hz', ...
  'delay_spread_taps','num_paths', ...
  'OTFS_label','OTFS_BER','OTFS_throughput','OTFS_CQI','OTFS_SE','OTFS_ACS', ...
  'ODDM_label','ODDM_BER','ODDM_throughput','ODDM_CQI','ODDM_SE','ODDM_ACS', ...
  'best_by_BER','best_by_ACS','best_waveform','rel_gap_BER','gap_ACS'};
mp = cell2table(map, 'VariableNames', map_hdr);
writetable(mp, fullfile(C.outdir,'phase2_performance_map.csv'));

% ---- metadata ------------------------------------------------------------------
meta = struct( ...
  'generated_at', datestr(now), ...
  'mode', C.mode, 'rng_seed', C.rng_seed, ...
  'carrier_default_hz', C.carrier_hz, 'bandwidth_hz', C.bandwidth_hz, ...
  'objective', C.objective, ...
  'tie_rules', struct('acs_abs', C.tie_tol_acs, ...
                      'ber_relative', C.tie_tol_ber_rel), ...
  'nTrials_per_condition', nT, ...
  'combos', {C.combos.name}, ...
  'axes', struct('snr_train', C.snr_train, 'snr_test', C.snr_test, ...
    'speed_train', C.speed_train, 'speed_test', C.speed_test, ...
    'profiles', {C.profiles}, 'mods_main', [4 16], ...
    'qam64_slice', C.include_64qam_slice, 'carrier_slice', C.carrier_slice), ...
  'counts', struct('conditions', nCond, 'train', numel(tr_ids)-n_val, ...
                   'val', n_val, 'test', nCond-numel(tr_ids), ...
                   'rows', height(ds)), ...
  'pairing', ['per trial: identical channel realization, payload bits and ' ...
              'noise seed across waveforms; only the waveform differs'], ...
  'feature_source', ['delay/Doppler/path features come from one probe ' ...
                     'channel realization per condition (gen_channel_params_flex)'], ...
  'acs_rule', ['ACS recomputed from aggregated metrics via compute_acs(); ' ...
               'tp_cap=N_bits/frame_T (frame_T includes ODDM CP), se_cap=log2(M)'], ...
  'label_rule', ['best_waveform = argmax ACS (configurable) or argmin BER; ' ...
                 'ties recorded as tie/tie_<waveform>, never fabricated'], ...
  'files', struct('dataset','phase2_dataset.csv', ...
                  'performance_map','phase2_performance_map.csv'));
fid = fopen(fullfile(C.outdir,'phase2_dataset_meta.json'),'w');
fwrite(fid, jsonencode(meta, 'PrettyPrint', true)); fclose(fid);

fprintf(['DONE: %d conditions -> %d dataset rows, performance map %d rows\n'], ...
        nCond, height(ds), height(mp));

% -------------------------------------------------------------------------
function conds = add_cond(conds, p, v, s, m, fc, sp)
conds(end+1) = struct('profile',p,'speed',v,'snr',s,'mod',m,'fc',fc, ...
                      'split',sp); %#ok<AGROW>
end
