function [dec, feat] = ai_decide_frame(pt, chan, cfg_base, current_wf, frames_since_switch, rt_dir)
% [PHASE-5 NOTE] LEGACY v1 AI interface (Phase-1 vocabulary). Canonical interface: dt_ai_decide.m.
% =========================================================================
% AI_DECIDE_FRAME   Ask the Python AI engine for the adaptive waveform
% decision at one Digital-Twin frame. Writes the state JSON (same feature
% names the regressors were trained on), invokes otfs_ai_pipeline/
% ai_engine.py and parses the decision JSON.
%
% Falls back to "keep current waveform" on ANY failure -- a broken AI call
% must never fabricate a recommendation (spec section 37).
%
% Environment label mapping to the TRAINING dataset vocabulary:
%   Pedestrian->Pedestrian  Urban->Urban  Highway/HighSpeedRail->Vehicular
% (the physical DelayProfile/DopplerSpread features carry the physics).
% =========================================================================
if nargin < 6
    rt_dir = fullfile('Results','DigitalTwin');
end

envmap = containers.Map({'Pedestrian','Urban','Highway','HighSpeedRail'}, ...
                        {'Pedestrian','Urban','Vehicular','Vehicular'});
if isKey(envmap, char(pt.environment))
    env_lab = envmap(char(pt.environment));
else
    env_lab = char(pt.environment);
end

feat = struct( ...
    'Environment',   env_lab, ...
    'Speed_kmph',    pt.speed_kmph, ...
    'DelayProfile',  char(pt.delay_profile), ...
    'DelaySpread',   double(chan.max_delay_tap), ...
    'NumPaths',      numel(chan.delay_taps), ...
    'DopplerSpread', double(max(abs(chan.Doppler_taps))), ...
    'Modulation',    pt.modulation, ...
    'SNR_dB',        pt.snr_db, ...
    'N',             cfg_base.N, 'M', cfg_base.M, ...
    'delta_f',       cfg_base.delta_f, ...
    'bandwidth_hz',  cfg_base.BW, ...
    'current_waveform', char(current_wf), ...
    'frames_since_switch', frames_since_switch);

fin = fullfile(rt_dir,'_ai_state.json');
fout = fullfile(rt_dir,'_ai_decision.json');
fid = fopen(fin,'w'); fwrite(fid, jsonencode(feat)); fclose(fid);

here = fileparts(mfilename('fullpath'));
pyexe = 'C:\MY DATA ANALYTICS FILES AND PROJECTS\MAJOR\AI-Adaptive-Transceiver\.venv\Scripts\python.exe';
if exist(pyexe,'file') ~= 2, pyexe = 'python'; end
cmd = sprintf('cd /d "%s" && "%s" ai_engine.py --infile "%s" --out "%s"', ...
              fullfile(here,'otfs_ai_pipeline'), pyexe, fin, fout);
[st,msg] = system(cmd);
if st == 0 && exist(fout,'file') == 2
    dec = jsondecode(fileread(fout));
else
    warning('ai_decide_frame: python call failed (%s)', strtrim(msg));
    dec = struct('recommendation', char(current_wf), ...
                 'detector', '', 'switched', false, ...
                 'reason', 'AI call failed -> kept current waveform', ...
                 'confidence', NaN);
end
end
