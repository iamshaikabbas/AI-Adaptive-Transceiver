function [acs, parts] = compute_acs(BER, TP_bps, SE_bpsHz, CQI, LAT_ms, REC, tp_cap, se_cap)
% =========================================================================
% COMPUTE_ACS   Adaptive Communication Score -- canonical MATLAB definition.
%
% ACS = w_ber*BER_score + w_tp*Throughput_score + w_se*SE_score
%     + w_cqi*CQI_score + w_lat*Latency_score + w_rec*Recovery_score
%
% All scores are normalized to [0,1]; weights come from acs_weights.json
% (next to this file) and are re-normalized to sum 1 at load time. The
% Python module otfs_ai_pipeline/acs.py implements EXACTLY the same formula
% and reads the SAME json file -- edit the json, never the two code paths.
%
% Inputs:
%   BER, TP_bps, SE_bpsHz, CQI, LAT_ms, REC : one frame's common metrics
%   tp_cap : noiseless throughput cap = N_bits/frame_T      [bps]
%   se_cap : modulation upper bound   = log2(M_mod)         [bps/Hz]
% Output:
%   acs   : scalar in [0,1]
%   parts : struct with every normalized score (for logging/debugging)
% =========================================================================

w = local_load_weights();

s_ber = min(1, max(0, -log10(max(BER, 1e-6)) / 6));
s_tp  = min(1, max(0, TP_bps)    / max(tp_cap, eps));
s_se  = min(1, max(0, SE_bpsHz)  / max(se_cap, eps));
s_cqi = min(1, max(0, CQI / 15));
s_lat = exp(-max(LAT_ms, 0) / 200);            % 200 ms reference latency
s_rec = min(1, max(0, REC));

parts = struct('BER', s_ber, 'Throughput', s_tp, 'SE', s_se, ...
               'CQI', s_cqi, 'Latency', s_lat, 'Recovery', s_rec);

acs = w.w_ber*s_ber + w.w_throughput*s_tp + w.w_se*s_se + ...
      w.w_cqi*s_cqi + w.w_latency*s_lat + w.w_recovery*s_rec;
acs = min(1, max(0, acs));
end

function w = local_load_weights()
persistent cached
if ~isempty(cached), w = cached; return; end
defaults = struct('w_ber',0.25,'w_throughput',0.20,'w_se',0.10, ...
                  'w_cqi',0.15,'w_latency',0.10,'w_recovery',0.20);
jfile = fullfile(fileparts(mfilename('fullpath')), 'acs_weights.json');
w = defaults;
if exist(jfile,'file') == 2
    try
        j = jsondecode(fileread(jfile));
        fns = fieldnames(defaults);
        for k = 1:numel(fns)
            if isfield(j,fns{k}) && isscalar(j.(fns{k}))
                w.(fns{k}) = j.(fns{k});
            end
        end
    catch
        warning('compute_acs: could not parse %s -> defaults.', jfile);
    end
end
tot = w.w_ber + w.w_throughput + w.w_se + w.w_cqi + w.w_latency + w.w_recovery;
if tot <= 0, tot = 1; end
w.w_ber = w.w_ber/tot;       w.w_throughput = w.w_throughput/tot;
w.w_se  = w.w_se/tot;        w.w_cqi        = w.w_cqi/tot;
w.w_latency = w.w_latency/tot; w.w_recovery = w.w_recovery/tot;
cached = w;
end
