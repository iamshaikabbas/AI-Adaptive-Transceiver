% =========================================================================
% realtime_adaptive.m   [Real-time stage]
%
% Time-varying link simulation driven by the TRAINED AI WAVEFORM SELECTOR:
%
%   for each frame t:
%     1. evolve the scenario   (speed ramp, profile switch, SNR drift)
%     2. draw the channel realization and estimate its features
%     3. ask Python (predict_waveform.py) which waveform to transmit
%     4. run the CHOSEN waveform AND every candidate under IDENTICAL
%        conditions (paired channel/bits/noise) -> oracle comparison
%
% The gap between the chosen waveform's BER and the per-frame oracle is the
% adaptation regret; the trace shows when the selector switches waveforms
% as the channel environment changes.
%
% Outputs (Results\WaveformComparison\):
%   adaptive_trace.csv    one row per frame (decisions + all BERs)
%   adaptive_timeline.png six-panel timeline figure
% =========================================================================
clearvars; clc;
here    = fileparts(mfilename('fullpath'));
outdir  = fullfile(here,'Results','WaveformComparison');
if ~exist(outdir,'dir'), mkdir(outdir); end

PYEXE = 'C:\MY DATA ANALYTICS FILES AND PROJECTS\MAJOR\AI-Adaptive-Transceiver\.venv\Scripts\python.exe';
if exist(PYEXE,'file') ~= 2, PYEXE = 'python'; end
PYDIR     = fullfile(here,'otfs_ai_pipeline');
SCEN_JSON = fullfile(outdir,'_rt_scenario.json');
DEC_JSON  = fullfile(outdir,'_rt_decision.json');

Nf    = 60;
M_mod = 4;
frames = (1:Nf).';

% ---- scenario schedule -----------------------------------------------------
prof   = cell(Nf,1); prof(1:20)={'EPA'}; prof(21:40)={'EVA'}; prof(41:end)={'ETU'};
env    = cell(Nf,1); env(1:20)={'Pedestrian'}; env(21:40)={'Vehicular'}; env(41:end)={'Urban'};
speed  = [linspace(3,30,20).' linspace(30,120,20).' linspace(120,350,20).'];
snrdb  = 14 + 8*sin(2*pi*frames(:)/40) - 0.05*(frames(:)-1)/Nf*10;

candidates = struct('wf',{'OTFS','ODDM','OFDM'}, ...
                    'det',{'MRC','LMMSE','LMMSE'}, ...
                    'name',{'OTFS-MRC','ODDM-LMMSE','OFDM-LMMSE'});
NC = numel(candidates);

rows = cell(Nf,1);
fprintf('=== REAL-TIME ADAPTIVE SIMULATION (%d frames) ===\n', Nf);
for t = 1:Nf
    cfg  = sim_default_config('DelayProfile',prof{t}, ...
                              'Speed_kmph',round(speed(t)), ...
                              'Modulation',M_mod,'SNR_dB',snrdb(t));
    chan = gen_channel_params_flex(cfg);
    cfg.chan = chan;
    seed = 900000 + t;

    % ---- 2. scenario features -> Python selector --------------------------
    scen = struct( ...
        'Environment',   env{t}, ...
        'Speed_kmh',     round(speed(t)), ...
        'DelayProfile',  prof{t}, ...
        'DelaySpread',   double(chan.max_delay_tap), ...
        'NumPaths',      numel(chan.delay_taps), ...
        'DopplerSpread', double(max(abs(chan.Doppler_taps))), ...
        'Modulation',    M_mod, ...
        'SNR_dB',        snrdb(t));
    fid = fopen(SCEN_JSON,'w'); fwrite(fid,jsonencode(scen)); fclose(fid);

    cmd = sprintf('cd /d "%s" && "%s" predict_waveform.py --infile "%s" --out "%s" --classes 2', ...
                  PYDIR, PYEXE, SCEN_JSON, DEC_JSON);
    [st,~] = system(cmd);
    if st == 0 && exist(DEC_JSON,'file') == 2
        dec       = jsondecode(fileread(DEC_JSON));
        wf_choice = char(dec.waveform);
        p_choice  = max(structfun(@double, dec.probabilities));
    else
        warning('selector call failed at frame %d -> fallback OTFS', t);
        wf_choice = 'OTFS'; p_choice = NaN;
    end

    % ---- 4. chosen + every candidate, identical conditions ----------------
    bers = zeros(NC,1); cqis = bers; lats = bers;
    for ic = 1:NC
        c = cfg;
        c.noise_seed = seed; c.tx_bits = [];
        c.Waveform = candidates(ic).wf;
        c.([candidates(ic).wf '_Detector']) = candidates(ic).det;
        switch candidates(ic).wf
            case 'OTFS', res = run_otfs(c);
            case 'ODDM', res = run_oddm(c);
            case 'OFDM', res = run_ofdm(c);
        end
        bers(ic) = res.BER; cqis(ic) = res.CQI; lats(ic) = res.Latency_ms;
    end
    ich = find(strcmpi({candidates.wf}, wf_choice), 1);
    if isempty(ich), ich = 1; wf_choice = candidates(1).wf; end
    ber_ch = bers(ich); cqi_ch = cqis(ich); lat_ch = lats(ich);
    det_ch = candidates(ich).det;
    [ber_best, iw] = min(bers);

    rows{t} = struct('frame',t, 'speed_kmph',round(speed(t)), 'SNR_dB',snrdb(t), ...
        'profile',string(prof{t}), 'chosen_waveform',string(wf_choice), ...
        'chosen_detector',string(det_ch), 'choice_prob',p_choice, ...
        'BER_chosen',ber_ch, 'CQI_chosen',cqi_ch, 'Latency_ms_chosen',lat_ch, ...
        'BER_oracle',ber_best, 'oracle_waveform',string(candidates(iw).wf), ...
        'BER_OTFS',bers(1),'BER_ODDM',bers(2),'BER_OFDM',bers(3), ...
        'CQI_OTFS',cqis(1),'CQI_ODDM',cqis(2),'CQI_OFDM',cqis(3), ...
        'optimal_choice',double(bers(ich)==ber_best));

    fprintf(['f%02d %5.0fkm/h %s %4.1fdB -> %-4s/%-6s (p=%.2f) BER %.2e | ' ...
             'oracle %-4s %.2e%s\n'], t, speed(t), prof{t}, snrdb(t), ...
             wf_choice, det_ch, p_choice, ber_ch, candidates(iw).wf, ...
             ber_best, ternary(bers(ich)==ber_best,'','  <-- sub-optimal'));
end

T = struct2table(vertcat(rows{:}));
csvpath = fullfile(outdir,'adaptive_trace.csv');
writetable(T, csvpath);
delete(SCEN_JSON); delete(DEC_JSON);
fprintf('\nOptimal-choice rate: %.1f%% (%d/%d) | mean CQI chosen: %.2f\n', ...
    100*mean(T.optimal_choice), sum(T.optimal_choice), Nf, mean(T.CQI_chosen));
fprintf('Trace written to %s\n', csvpath);

% ---- timeline figure --------------------------------------------------------
wfmap = containers.Map({'OTFS','ODDM','OFDM'},{3,1,2});
wfcode = cellfun(@(w) wfmap(char(w)), T.chosen_waveform);

fig = figure('Position',[40 40 1400 800],'Color','w');

subplot(2,3,1);
yyaxis left;  plot(frames, T.speed_kmph,'-','LineWidth',1.5); ylabel('speed [km/h]');
yyaxis right; plot(frames, T.SNR_dB,'-','LineWidth',1.5); ylabel('SNR [dB]');
grid on; title('(a) scenario schedule'); xlabel('frame');

subplot(2,3,2);
stairs(frames, wfcode,'LineWidth',2); grid on; ylim([0.5 3.5]);
set(gca,'YTick',[1 2 3],'YTickLabel',{'ODDM','OFDM','OTFS'});
title('(b) AI waveform decisions'); xlabel('frame');

subplot(2,3,3);
semilogy(frames, max(T.BER_OTFS,1e-7),'-o', frames, max(T.BER_ODDM,1e-7),'-s', ...
         frames, max(T.BER_OFDM,1e-7),'-^', frames, max(T.BER_oracle,1e-7),'k--');
grid on; legend({'OTFS','ODDM','OFDM','oracle'},'Location','best');
title('(c) frame BER vs oracle'); xlabel('frame'); ylabel('BER');

subplot(2,3,4);
plot(frames, T.CQI_chosen,'-o'); grid on; ylim([0 15]);
title('(d) reported CQI of chosen waveform'); xlabel('frame'); ylabel('CQI');

subplot(2,3,5);
plot(frames, cumsum(~T.optimal_choice),'-','LineWidth',1.8); grid on;
title('(e) cumulative sub-optimal choices'); xlabel('frame');

subplot(2,3,6);
histogram(log10(max(T.BER_chosen./max(T.BER_oracle,1e-12),1)),12); grid on;
xlabel('log_{10}(BER_{chosen}/BER_{oracle})'); ylabel('frames');
title('(f) instantaneous adaptation regret');

pngpath = fullfile(outdir,'adaptive_timeline.png');
exportgraphics(fig, pngpath,'Resolution',150);
fprintf('Saved %s\n', pngpath);

function s = ternary(c,a,b)
if c, s=a; else, s=b; end
end
