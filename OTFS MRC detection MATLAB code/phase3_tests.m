% =========================================================================
% PHASE3_TESTS   Live closed-loop component tests (spec section 20).
%   TEST 1: AI inference works            (python engine v2 round trip)
%   TEST 2: AI selects one valid waveform
%   TEST 3: selected waveform actually executes
% Run: matlab -batch "phase3_tests"
% =========================================================================
clearvars; clc;
here = fileparts(mfilename('fullpath'));
pyexe = 'C:\MY DATA ANALYTICS FILES AND PROJECTS\MAJOR\AI-Adaptive-Transceiver\.venv\Scripts\python.exe';
if exist(pyexe,'file') ~= 2, pyexe = 'python'; end
pass = true;

% ---- realistic state drawn from the digital twin ---------------------------
cfg = sim_default_config('DelayProfile','EVA','Speed_kmph',150, ...
                         'Modulation',4,'SNR_dB',10);
chan = gen_channel_params_flex(cfg);
state = struct('environment','Urban', 'speed_kmph',150, 'snr_db',10, ...
    'doppler_hz',(150*(1000/3600)/299792458)*cfg.car_fre, ...
    'carrier_frequency_hz',cfg.car_fre, 'bandwidth_hz',cfg.BW, ...
    'channel_profile',char(chan.profile), ...
    'delay_spread_taps',double(chan.max_delay_tap), ...
    'num_paths',double(chan.taps), ...
    'doppler_spread_hz',double(chan.doppler_spread_hz), ...
    'modulation',4, 'current_waveform','OTFS', 'frames_since_switch',99);

fin = fullfile(here,'_t_state.json');  fout = fullfile(here,'_t_dec.json');
fid=fopen(fin,'w'); fwrite(fid,jsonencode(state)); fclose(fid);
cmd = sprintf('cd /d "%s" && "%s" ai_engine_v2.py --infile "%s" --out "%s"', ...
              fullfile(here,'otfs_ai_pipeline'), pyexe, fin, fout);
[st,~] = system(cmd);
ok1 = (st == 0) && exist(fout,'file')==2;
fprintf('TEST 1 AI inference works              : %s\n', tern(ok1,'PASS','FAIL'));
pass = pass && ok1;

dec = struct();
if ok1
    dec = jsondecode(fileread(fout));
    wf = char(dec.recommendation);
    ok2 = any(strcmp(wf,{'OTFS','ODDM'}));
else
    wf = 'OTFS'; ok2 = false;
end
fprintf('TEST 2 selects valid waveform (%s)     : %s\n', wf, tern(ok2,'PASS','FAIL'));
pass = pass && ok2;

% ---- TEST 3: execute the selected waveform for real ------------------------
cfg.TwinStrategy = 'test';
pt = struct('environment','Urban','speed_kmph',150,'snr_db',10, ...
    'delay_profile','EVA','doppler_scale',1,'modulation',4, ...
    't_s',0,'frame',1);
[row,res] = twin_run_frame(pt, cfg, wf, char(dec.detector), 100001, struct());
ok3 = ~row.error_flag && isfinite(row.BER) && ~isempty(res);
fprintf('TEST 3 selected waveform executes      : %s (BER=%.3g)\n', ...
        tern(ok3,'PASS','FAIL'), row.BER);
pass = pass && ok3;

if pass, disp('PHASE3 COMPONENT TESTS: ALL PASS');
else,    error('PHASE3 COMPONENT TESTS FAILED'); end

function out = tern(c,a,b)
if c, out=a; else, out=b; end
end
