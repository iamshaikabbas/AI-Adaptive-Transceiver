function [dec, err_msg, fb_used] = dt_ai_decide(state, policy, opts)
% =========================================================================
% DT_AI_DECIDE   Canonical MATLAB <-> Python AI interface (spec sections
% 6-7): ONE mechanism for every policy generation.
%
%   [dec, err_msg, fb_used] = dt_ai_decide(state, 'phase3')
%   [dec, err_msg, fb_used] = dt_ai_decide(state, 'phase4', opts)
%
% POLICY SELECTION IS EXPLICIT (spec section 13):
%   phase3 -> adaptive_config_v2.json + ai_engine_v2.py   (CANONICAL,
%             default everywhere)
%   phase4 -> adaptive_config_v4.json + ai_engine_v3.py   (EXPERIMENTAL:
%             banded confidence policy; retained for robustness studies)
% Any other value raises an error -- silent defaults are forbidden.
%
% Mechanism (identical for both policies):
%   1. state struct -> JSON file (feature names EXACTLY match training
%      vocabulary: lowercase environment strings, doppler_hz, ...);
%   2. engine invoked as a subprocess writing a decision JSON;
%   3. on ANY failure (nonzero exit, missing file, exception) the caller
%      receives fb_used=true and a SAFE FALLBACK decision: keep current
%      waveform, reason records the error. The system NEVER crashes and
%      NEVER silently substitutes a different policy.
%
% opts (optional):
%   .here     project MATLAB-code dir (default: this file's folder)
%   .workdir  scratch dir for JSON exchange (default: <tempdir>/dt5_ai)
%   .pyexe    explicit python executable (default: repo .venv, else PATH)
%
% The oracle / actual frame results are NEVER part of the AI input state
% (spec section 8).
% =========================================================================
if nargin < 3, opts = struct(); end
here = local_opt(opts,'here', fileparts(mfilename('fullpath')));
workdir = local_opt(opts,'workdir', fullfile(tempdir,'dt5_ai'));
policy = lower(char(policy));
[cfg_name, engine_py] = dt_policy_config(policy);   % single mapping source

if ~exist(workdir,'dir'), mkdir(workdir); end
fin  = fullfile(workdir,'_ai_state.json');
fout = fullfile(workdir,'_ai_decision.json');

pyexe = char(local_opt(opts,'pyexe',''));
if isempty(pyexe)
    cand = fullfile(fileparts(here),'.venv','Scripts','python.exe');
    if exist(cand,'file')==2, pyexe = cand; else, pyexe = 'python'; end
end

dec = struct('recommendation','','best_by_objective','','detector','', ...
             'confidence',NaN,'reason','ai call failed', ...
             'predicted_metrics',struct());
err_msg = '';  fb_used = false;

fid = fopen(fin,'w'); fwrite(fid,jsonencode(state)); fclose(fid);
cmd = sprintf(['cd /d "%s" && "%s" %s --infile "%s" --out "%s" ' ...
               '--config "%s"'], ...
              fullfile(here,'otfs_ai_pipeline'), pyexe, engine_py, ...
              fin, fout, fullfile(here,cfg_name));
try
    [st,msg] = system(cmd);
    if st == 0 && exist(fout,'file')==2
        dec = jsondecode(fileread(fout));
        dec.recommendation    = char(dec.recommendation);
        dec.best_by_objective = char(dec.best_by_objective);
        dec.detector          = char(dec.detector);
        dec.reason            = char(dec.reason);
        if ~isfield(dec,'predicted_metrics'), dec.predicted_metrics = struct(); end
    else
        err_msg = ['python failed: ' strtrim(msg)];
        fb_used = true;
    end
catch me
    err_msg = ['python exception: ' me.message];
    fb_used = true;
end

if fb_used
    cur = char(state.current_waveform);
    if isempty(cur), cur = 'OTFS'; end
    dec.recommendation    = cur;
    dec.best_by_objective = cur;
    dec.detector          = twin_default_detector(cur);
    dec.reason            = ['fallback keep current: ' err_msg];
    dec.confidence        = NaN;
    dec.predicted_metrics = struct( ...
        'OTFS', struct('BER',NaN,'Throughput_bps',NaN,'CQI',NaN,'ACS',NaN), ...
        'ODDM', struct('BER',NaN,'Throughput_bps',NaN,'CQI',NaN,'ACS',NaN));
end
dec.policy = string(policy);
dec.config_file = string(cfg_name);
dec.engine_py = string(engine_py);
end

function v = local_opt(s, f, dflt)
if isfield(s,f) && ~isempty(s.(f)), v = s.(f); else, v = dflt; end
end
