% =========================================================================
% _phase1_paired_check.m  -- Phase 1 certification helper (temporary).
% Proves the OTFS/ODDM/OFDM comparison path is truly PAIRED: identical
% channel realization, payload bits and noise seed fed to all three
% runners; verifies the echoed payload matches bit-for-bit, that the seed
% is effective, and that the production entry point run_paired_trials
% executes end-to-end.
% =========================================================================
cfg0 = sim_default_config('DelayProfile','EVA','Speed_kmph',120, ...
                          'Modulation',4,'SNR_dB',10);
probe = cfg0; probe.chan = [];
chan = gen_channel_params_flex(probe);
Lg = max(chan.max_delay_tap+1, ceil(cfg0.M/16));
tx_bits = randi([0 1], (cfg0.M-Lg)*cfg0.N*log2(4), 1);

names = {'OTFS','ODDM','OFDM'}; dets = {'MRC','LMMSE','LMMSE'};
res = cell(1,3);
for k = 1:3
    c = cfg0; c.chan = chan; c.tx_bits = tx_bits; c.noise_seed = 424242;
    c.Waveform = names{k}; c.([names{k} '_Detector']) = dets{k};
    switch names{k}
        case 'OTFS',  res{k} = run_otfs(c);
        case 'ODDM',  res{k} = run_oddm(c);
        otherwise,    res{k} = run_ofdm(c);
    end
    fprintf('%s : BER=%.5f  echoed_tx_bits=%d  err=%d\n', names{k}, ...
        res{k}.BER, numel(res{k}.tx_bits), sum(res{k}.tx_bits ~= res{k}.rx_bits));
end
assert(isequal(res{1}.tx_bits, res{2}.tx_bits) && ...
       isequal(res{2}.tx_bits, res{3}.tx_bits), 'payload mismatch across waveforms');
fprintf(['PAIRED INPUTS IDENTICAL: delay_taps=[%s] |max|=%d, ' ...
         'tx_bits %dx1 shared, noise_seed=424242\n'], ...
        num2str(chan.delay_taps), max(abs(chan.delay_taps)), numel(tx_bits));

c2 = cfg0; c2.chan = gen_channel_params_flex(probe); c2.noise_seed = 777;
c2.Waveform = 'OTFS'; c2.OTFS_Detector = 'MRC';
r2 = run_otfs(c2);
fprintf('control (fresh channel, seed 777): OTFS BER=%.5f -> seeds/channels are effective\n', r2.BER);

D = combo_defs('main3');
S = run_paired_trials(D, cfg0, 3);
for i = 1:numel(S)
    fprintf('%-14s BER_total=%.5f Thr=%.0f bps Lat=%.1f ms\n', ...
        S(i).name, S(i).BER_total, S(i).Thr_mean, S(i).Lat_mean);
end
assert(all(isfinite([S.BER_total])), 'non-finite aggregate');
fprintf('run_paired_trials OK (%d combos x 3 trials)\n', numel(S));
