% Smoke test: one frame per waveform, shared channel/bits/seed
cfg = sim_default_config('SNR_dB', 12);
rng(7);
cfg.chan = gen_channel_params_flex(cfg);
cfg.tx_bits = randi([0 1], 1, 1);   % placeholder; run_* sizes it if empty
N_bits = (cfg.M - max(cfg.chan.max_delay_tap+1, ceil(cfg.M/16)))*cfg.N*log2(cfg.Modulation);
cfg.tx_bits = randi([0 1], N_bits, 1);

r1 = run_otfs(cfg);
r2 = run_oddm(cfg);
r3 = run_ofdm(cfg);

fprintf('OTFS : BER=%.4f SER=%.4f PER=%d TP=%.3e SE=%.3f CQI=%d lat=%.2fms rt=%.3fs\n', r1.BER,r1.SER,r1.PER,r1.Throughput_bps,r1.SpectralEfficiency,r1.CQI,r1.Latency_ms,r1.Runtime_sec);
fprintf('ODDM : BER=%.4f SER=%.4f PER=%d TP=%.3e SE=%.3f CQI=%d lat=%.2fms rt=%.3fs\n', r2.BER,r2.SER,r2.PER,r2.Throughput_bps,r2.SpectralEfficiency,r2.CQI,r2.Latency_ms,r2.Runtime_sec);
fprintf('OFDM : BER=%.4f SER=%.4f PER=%d TP=%.3e SE=%.3f CQI=%d lat=%.2fms rt=%.3fs\n', r3.BER,r3.SER,r3.PER,r3.Throughput_bps,r3.SpectralEfficiency,r3.CQI,r3.Latency_ms,r3.Runtime_sec);

% AWGN identity check: BER should be ~0 at 20 dB for all
c2 = sim_default_config('SNR_dB',20,'DelayProfile','AWGN','noise_seed',3);
q1 = run_otfs(c2); q2 = run_oddm(c2); q3 = run_ofdm(c2);
fprintf('AWGN@20dB: OTFS BER=%.2e | ODDM BER=%.2e | OFDM BER=%.2e\n', q1.BER,q2.BER,q3.BER);
