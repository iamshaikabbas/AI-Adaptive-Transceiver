% =========================================================================
% _phase1_ai_cli_check.m -- Phase 1 certification helper (temporary).
% Exercises the real MATLAB<->Python integration surfaces WITHOUT
% retraining anything:
%   1) ai_engine.py via system(), byte-for-byte the command construction
%      used by ai_decide_frame.m (production digital-twin path)
%   2) predict_waveform.py --classes 2 and --classes 3 (documented CLI)
% Asserts: exit status 0, parseable decision JSON, valid recommendation,
% probabilities in [0,1], predicted_ACS present.
% =========================================================================
rt = fullfile(tempdir, 'phase1_ai_cli');
if ~exist(rt, 'dir'), mkdir(rt); end

feat = struct( ...
    'Environment', 'Vehicular', 'Speed_kmph', 120, ...
    'DelayProfile', 'EVA', 'DelaySpread', 1, 'NumPaths', 9, ...
    'DopplerSpread', 0.0127, 'Modulation', 4, 'SNR_dB', 12, ...
    'N', 32, 'M', 32, 'delta_f', 15000, 'bandwidth_hz', 480000, ...
    'current_waveform', 'OTFS', 'frames_since_switch', 14);
fin  = fullfile(rt, '_phase1_scenario.json');
fout = fullfile(rt, '_phase1_decision.json');
fid = fopen(fin, 'w'); fwrite(fid, jsonencode(feat)); fclose(fid);

here = fileparts(mfilename('fullpath'));
pyexe = 'C:\MY DATA ANALYTICS FILES AND PROJECTS\MAJOR\AI-Adaptive-Transceiver\.venv\Scripts\python.exe';
assert(exist(pyexe,'file') == 2, 'venv python not found');

% ---- 1) production path: ai_engine.py -----------------------------------
cmd = sprintf('cd /d "%s" && "%s" ai_engine.py --infile "%s" --out "%s"', ...
              fullfile(here, 'otfs_ai_pipeline'), pyexe, fin, fout);
[st, msg] = system(cmd);
fprintf('--- ai_engine.py (exit %d) ---\n%s\n', st, strtrim(msg));
assert(st == 0 && exist(fout, 'file') == 2, 'ai_engine.py call failed');
dec = jsondecode(fileread(fout));
assert(isfield(dec, 'recommendation') && any(strcmp(dec.recommendation, {'OTFS','ODDM'})), ...
       'bad recommendation');
probs = dec.predicted_ACS;
assert(isfield(probs, 'OTFS') && isfield(probs, 'ODDM'), 'missing predicted_ACS');
fprintf(['DECISION: %s (%s) switched=%d confidence=%.3f | predicted_ACS ' ...
         'OTFS=%.4f ODDM=%.4f\n'], dec.recommendation, dec.detector, ...
        dec.switched, dec.confidence, probs.OTFS, probs.ODDM);

% ---- 2) documented selector CLI -----------------------------------------
for nc = [2 3]
    dout = fullfile(rt, sprintf('_phase1_sel_%dc.json', nc));
    cmd2 = sprintf('cd /d "%s" && "%s" predict_waveform.py --infile "%s" --out "%s" --classes %d', ...
                   fullfile(here, 'otfs_ai_pipeline'), pyexe, fin, dout, nc);
    [st2, msg2] = system(cmd2);
    fprintf('--- predict_waveform.py %dc (exit %d): %s\n', nc, st2, strtrim(msg2));
    assert(st2 == 0 && exist(dout, 'file') == 2, 'selector CLI failed');
    sel = jsondecode(fileread(dout));
    pv = cellfun(@double, struct2cell(sel.probabilities));
    assert(all(pv >= 0 & pv <= 1) && abs(sum(pv) - 1) < 1e-6, 'bad probabilities');
    fprintf('    selector -> %s (%s), probs sum=%.6f\n', ...
            sel.waveform, sel.detector, sum(pv));
end

fprintf('PHASE1 AI INFERENCE: PASS\n');
