function res = run_otfs(cfg)
% =========================================================================
% RUN_OTFS   Common-interface wrapper around the EXISTING ZP-OTFS chain.
%
% Uses, unmodified:
%   Generate_2D_data_grid.m, Gen_discrete_time_channel.m,
%   Gen_delay_time_channel_vectors.m, Generate_time_frequency_channel_ZP.m,
%   MRC_delay_time_detector.m   (the repository's baseline detector)
% and an LMMSE detector identical to the local function inside
% ZP_OTFS_MRC_system.m (dense Wiener filter on the time-domain channel).
%
% Channel: cfg.chan (shared realization) or gen_channel_params_flex(cfg).
% The time-domain channel matrix is built with build_stream_channel(...,'linear')
% which is mathematically identical to the sparse matrix used inside
% ZP_OTFS_MRC_system.m for r = H*s.
%
% Output: common results struct -- see compute_common_metrics.m. Also
% returns .rx_bits/.tx_bits/.tx_sym/.rx_sym for dataset assembly.
% =========================================================================
t_all = tic;

% ---- derived parameters -------------------------------------------------
N = cfg.N; M = cfg.M;
NM = N*M;
Fn = dftmtx(N); Fn = Fn./norm(Fn);
M_mod  = cfg.Modulation;
M_bits = log2(M_mod);
eng_sqrt = sqrt((M_mod-1)/6*4);              % unit-grid QAM factor (repo convention)
sigma2   = (abs(eng_sqrt)^2) / 10^(cfg.SNR_dB/10);

% ---- shared channel ------------------------------------------------------
if isempty(cfg.chan)
    chan = gen_channel_params_flex(cfg);
else
    chan = cfg.chan;
end

% ---- guard / data mask (same policy as ZP_OTFS_MRC_system.m) -------------
length_ZP = max(chan.max_delay_tap+1, ceil(M/16));
M_data    = M - length_ZP;
data_grid = zeros(M,N); data_grid(1:M_data,1:N) = 1;
data_mask = logical(data_grid);
N_syms    = sum(data_grid(:));
N_bits    = N_syms*M_bits;

% ---- bits ------------------------------------------------------------------
if isempty(cfg.tx_bits)
    tx_bits = randi([0 1], N_bits, 1);
else
    tx_bits = cfg.tx_bits(:);
end

% ---- TX: QAM -> DD grid -> ISFFT -> time samples ---------------------------
tx_sym = qammod(reshape(tx_bits,M_bits,N_syms), M_mod,'gray','InputType','bit');
X      = Generate_2D_data_grid(N, M, tx_sym, data_grid);
s      = reshape(X*Fn', NM, 1);

% ---- linear time-domain channel + noise -------------------------------------
H_time = build_stream_channel(chan, NM, 'linear');
if isempty(cfg.noise_seed), rng('shuffle'); else rng(cfg.noise_seed); end
r = H_time*s + sqrt(sigma2/2)*(randn(NM,1)+1i*randn(NM,1));
[r, imp_info] = apply_rx_impairments(r, cfg);

% ---- detection ---------------------------------------------------------------
l_max = chan.max_delay_tap;
gs    = Gen_discrete_time_channel(N,M,chan.taps,chan.delay_taps,chan.Doppler_taps,chan.chan_coef);

t_det = tic;
switch upper(cfg.OTFS_Detector)
    case 'MRC'
        nu_ml_tilda = Gen_delay_time_channel_vectors(N,M,l_max,gs);
        H_tf        = Generate_time_frequency_channel_ZP(N,M,gs,unique(chan.delay_taps));
        omega = 1; if M_mod >= 64, omega = 0.25; end
        [rx_bits,~,~] = MRC_delay_time_detector(N,M,M_data,M_mod,sigma2,data_grid,...
            r,H_tf,nu_ml_tilda,unique(chan.delay_taps),omega,1,1,cfg.n_ite_MRC);
    case 'LMMSE'
        rx_bits = otfs_lmmse_local(N,M,M_mod,sigma2,data_mask,r,H_time,Fn);
    otherwise
        error('run_otfs: unknown OTFS_Detector "%s".', cfg.OTFS_Detector);
end
det_time = toc(t_det);

% ---- metrics -------------------------------------------------------------------
rx_sym = qammod(reshape(rx_bits,M_bits,N_syms), M_mod,'gray','InputType','bit');
cfg.Waveform = 'OTFS';
res = compute_common_metrics(tx_bits, rx_bits, tx_sym, rx_sym, M_mod, cfg, det_time, toc(t_all));

res.rx_bits = rx_bits; res.tx_bits = tx_bits;
res.tx_sym = tx_sym;   res.rx_sym = rx_sym;
res.M_data = M_data;   res.N_syms = N_syms;
res.chan   = chan;
res.tx_iq  = s;        % TX complex baseband samples (NM x 1)
res.rx_iq  = r;        % RX complex baseband samples (post-channel+impairments)
res.imp    = imp_info;
end

function bits = otfs_lmmse_local(N, M, M_mod, sigma2, data_mask, r, H, Fn)
% Identical in form to LMMSE_OTFS_detector() inside ZP_OTFS_MRC_system.m:
% dense Wiener solve on the time-domain channel, then SFFT back to DD.
    NM = N*M;
    A = H'*H + sigma2*speye(NM);
    b = H'*r;
    s_hat = A \ b;
    X_tilda_hat = reshape(s_hat, M, N);
    X_hat = X_tilda_hat * Fn;
    rx_sym = X_hat(data_mask);
    bits = reshape(qamdemod(rx_sym, M_mod,'gray','OutputType','bit'),[],1);
end
