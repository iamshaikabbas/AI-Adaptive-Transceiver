function res = run_oddm(cfg)
% =========================================================================
% RUN_ODDM   Common-interface ODDM transceiver (genuine separate waveform).
%
% TX: bits -> QAM -> DD grid (rows 1:M_data active, identical payload to
%     OTFS) -> row-wise N-point IDFT along the Doppler axis -> staggered
%     delay-division sample placement -> frame-level cyclic prefix.
%     See ODDM_modulate.m for references [P1]-[P3].
% CH: shared path realization (cfg.chan / gen_channel_params_flex), applied
%     linearly over the CP-prepended frame with the same z = exp(j2pi/(NM))
%     phase convention as ZP-OTFS, so both waveforms see an identical
%     physical channel process at identical SNR definition (Es/N0).
% RX: strip CP -> de-stagger -> row-wise FFT -> DD-domain detection via
%     'MMSETAP' or 'LMMSE' on the exact sparse DD-domain channel matrix
%     H_dd = kron(I_M,Fn) * C * kron(I_M,Fn')  (ODDM_demodulate.m /
%     ODDM_detect.m). No OTFS-specific detector is reused.
% =========================================================================
t_all = tic;

N = cfg.N; M = cfg.M; NM = N*M;
Fn = dftmtx(N); Fn = Fn./norm(Fn);
M_mod  = cfg.Modulation;
M_bits = log2(M_mod);
eng_sqrt = sqrt((M_mod-1)/6*4);
sigma2   = (abs(eng_sqrt)^2) / 10^(cfg.SNR_dB/10);

% ---- shared channel -------------------------------------------------------
if isempty(cfg.chan)
    chan = gen_channel_params_flex(cfg);
else
    chan = cfg.chan;
end

% ---- guard / data mask (identical rule & payload as run_otfs) --------------
L_cp     = max(chan.max_delay_tap+1, 2);      % frame-level cyclic prefix
M_data   = M - max(chan.max_delay_tap+1, ceil(M/16));
data_grid= zeros(M,N); data_grid(1:M_data,1:N) = 1;
data_mask= logical(data_grid);
N_syms   = sum(data_grid(:));
N_bits   = N_syms*M_bits;

% ---- bits --------------------------------------------------------------------
if isempty(cfg.tx_bits)
    tx_bits = randi([0 1], N_bits, 1);
else
    tx_bits = cfg.tx_bits(:);
end

% ---- TX -----------------------------------------------------------------------
tx_sym = qammod(reshape(tx_bits,M_bits,N_syms), M_mod,'gray','InputType','bit');
X_dd   = Generate_2D_data_grid(N, M, tx_sym, data_grid);   % same placement policy
s_ext  = ODDM_modulate(X_dd, L_cp, Fn);

% ---- channel + noise -------------------------------------------------------------
H_lin = build_stream_channel(chan, NM, 'linear', NM+L_cp);
if isempty(cfg.noise_seed), rng('shuffle'); else rng(cfg.noise_seed); end
r_ext = H_lin*s_ext + sqrt(sigma2/2)*(randn(NM+L_cp,1)+1i*randn(NM+L_cp,1));
[r_ext, imp_info] = apply_rx_impairments(r_ext, cfg);

% ---- RX ---------------------------------------------------------------------------
[Y_dd, H_dd] = ODDM_demodulate(r_ext, L_cp, N, M, Fn, chan, true);

t_det = tic;
[rx_bits, ~, ~] = ODDM_detect(Y_dd, H_dd, data_mask, M_mod, sigma2, cfg.ODDM_Detector);
det_time = toc(t_det);

% ---- metrics -------------------------------------------------------------------------
rx_sym = qammod(reshape(rx_bits,M_bits,N_syms), M_mod,'gray','InputType','bit');
cfg.Waveform = 'ODDM';
cfg.L_cp = L_cp;
res = compute_common_metrics(tx_bits, rx_bits, tx_sym, rx_sym, M_mod, cfg, det_time, toc(t_all));

res.rx_bits = rx_bits; res.tx_bits = tx_bits;
res.tx_sym = tx_sym;   res.rx_sym = rx_sym;
res.M_data = M_data;   res.N_syms = N_syms;
res.L_cp   = L_cp;
res.chan   = chan;
res.tx_iq  = s_ext;     % TX complex baseband samples incl. CP (NM+L_cp x 1)
res.rx_iq  = r_ext;     % RX complex baseband samples (post-channel+impairments)
res.imp    = imp_info;
end
