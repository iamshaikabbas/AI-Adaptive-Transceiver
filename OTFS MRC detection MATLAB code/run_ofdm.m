function res = run_ofdm(cfg)
% =========================================================================
% RUN_OFDM   Conventional CP-OFDM baseline on the SAME time-frequency
% lattice (M subcarriers x N OFDM symbols), the same shared channel
% realization and the same payload/mask policy as run_otfs/run_oddm.
% Provided because the repository had no standalone OFDM chain; it gives
% the AI layer a classical multicarrier reference point.
%
% TX: per OFDM symbol n: unitary M-point IDFT across subcarriers + CP of
%     length L_cp per symbol.
% CH: same path realization applied linearly over the CP-extended frame
%     (absolute-index phase convention -> identical Doppler evolution).
% RX: strip CPs -> per-symbol FFT -> single-tap MMSE ('MMSETAP', ICI
%     treated as noise) or per-symbol LMMSE including adjacent-carrier ICI.
% =========================================================================
t_all = tic;

N = cfg.N; M = cfg.M;
M_mod  = cfg.Modulation;
M_bits = log2(M_mod);
eng_sqrt = sqrt((M_mod-1)/6*4);
sigma2   = (abs(eng_sqrt)^2) / 10^(cfg.SNR_dB/10);
FM = dftmtx(M); FM = FM./norm(FM);      % unitary M-point DFT

if isempty(cfg.chan)
    chan = gen_channel_params_flex(cfg);
else
    chan = cfg.chan;
end

L_cp    = max(chan.max_delay_tap+1, 2);
M_data  = M - max(chan.max_delay_tap+1, ceil(M/16));
data_grid = zeros(M,N); data_grid(1:M_data,1:N) = 1;
data_mask = logical(data_grid);
N_syms  = sum(data_grid(:));
N_bits  = N_syms*M_bits;

if isempty(cfg.tx_bits)
    tx_bits = randi([0 1], N_bits, 1);
else
    tx_bits = cfg.tx_bits(:);
end

% ---- TX -------------------------------------------------------------------
tx_sym = qammod(reshape(tx_bits,M_bits,N_syms), M_mod,'gray','InputType','bit');
X_tf   = Generate_2D_data_grid(N, M, tx_sym, data_grid);   % M x N grid

frame = zeros(M+L_cp, N);
for n = 1:N
    t_blk = FM' * X_tf(:,n);              % unitary IDFT (subcarriers -> time)
    frame(:,n) = [t_blk(end-L_cp+1:end); t_blk];
end
s_ext = frame(:);                          % symbol blocks stacked in time

% ---- channel + noise ---------------------------------------------------------
H_lin = build_stream_channel(chan, N*M, 'linear', numel(s_ext));
if isempty(cfg.noise_seed), rng('shuffle'); else rng(cfg.noise_seed); end
r_ext = H_lin*s_ext + sqrt(sigma2/2)*(randn(numel(s_ext),1)+1i*randn(numel(s_ext),1));
[r_ext, imp_info] = apply_rx_impairments(r_ext, cfg);

% ---- RX: strip per-symbol CPs --------------------------------------------------
r_mat = reshape(r_ext, M+L_cp, N);
Y_tf  = zeros(M, N);
for n = 1:N
    Y_tf(:,n) = FM * r_mat(L_cp+1:end, n);
end

% ---- EXACT TF-domain channel ------------------------------------------------
% Projecting the delay-Doppler channel onto the per-block DFT basis gives,
% for output tone k and input tone kappa of OFDM symbol n (0-based):
%   H_n(k,kappa) = sum_i g_i * z^(nu_i*(q0(n)-l_i))
%                       * exp(-j*2*pi*l_i*kappa/M)
%                       * D_M(kappa - k + nu_i/N),
% with z = exp(j2pi/(N*M)), q0(n) = n*(M+L_cp)+L_cp (absolute index of the
% first data sample of block n) and the Dirichlet kernel
%   D_M(x) = (1/M)*sum_{m=0}^{M-1} exp(j2pi*m*x/M)
%          = exp(j*pi*x*(M-1)/M) * sin(pi*x) ./ (M*sin(pi*x/M)).
% D_M collapses to Kronecker delta when the fractional Doppler nu_i/N -> 0
% (static channel), reproducing the classical diagonal frequency response.
NM = N*M;
z  = exp(1i*2*pi/NM);
Pn = chan.taps;
kk = (0:M-1).';
dInt = kk.' - kk;                          % kappa - k  (rows k, cols kappa)

H_tf = zeros(M, M, N);                     % exact TF matrices per symbol
for i = 1:Pn
    li = chan.delay_taps(i);
    ni = chan.Doppler_taps(i);
    x  = dInt + ni/N;                      % Dirichlet argument
    Dm = exp(1i*pi*x.*(M-1)./M) .* sin(pi*x) ./ (M*sin(pi*x./M));
    % Only x == 0 (mod M) is singular (rho==1, 0/0): the true limit there
    % is 1. Other integer offsets are NOT singular -- the sin form already
    % yields exactly 0 for them and must be left untouched.
    sing = abs(sin(pi*x./M)) < 1e-12;
    Dm(sing) = 1;
    kap = 0:M-1;
    eDelay = exp(-1i*2*pi*li*kap/M);       % delay phase vs input tone kappa
    for n = 1:N
        q0n   = (n-1)*(M+L_cp) + L_cp;     % absolute first data sample (0-based)
        a_in  = chan.chan_coef(i) * z.^(ni*(q0n - li));
        H_tf(:,:,n) = H_tf(:,:,n) + a_in .* (Dm .* eDelay);   % eDelay scales cols (input tone kappa)
    end
end

t_det = tic;
switch upper(cfg.OFDM_Detector)
    case 'MMSETAP'
        % single-tap MMSE on the exact diagonal; residual ICI treated as noise
        h_diag = zeros(M, N);
        for n = 1:N
            h_diag(:,n) = diag(H_tf(:,:,n));
        end
        W     = conj(h_diag) ./ (abs(h_diag).^2 + sigma2 + eps);
        X_eq  = W .* Y_tf;
        x_eq  = X_eq(data_mask);

    case 'LMMSE'
        % per-symbol Wiener filter on the EXACT M_data x M_data TF matrix
        % (includes the full Dirichlet ICI structure, not just neighbors)
        x_eq = zeros(N_syms,1);
        ka   = 1:M_data;                       % active tones (contiguous)
        for n = 1:N
            Hn  = H_tf(ka, ka, n);
            y_n = Y_tf(ka,n);
            xn  = (Hn'*Hn + sigma2*eye(numel(ka))) \ (Hn'*y_n);
            x_eq((n-1)*M_data + (1:M_data)) = xn;
        end

    otherwise
        error('run_ofdm: unknown OFDM_Detector "%s".', cfg.OFDM_Detector);
end
det_time = toc(t_det);

rx_bits = reshape(qamdemod(x_eq(:), M_mod,'gray','OutputType','bit'),[],1);

rx_sym = qammod(reshape(rx_bits,M_bits,N_syms), M_mod,'gray','InputType','bit');
cfg.Waveform = 'OFDM';
cfg.L_cp = L_cp;
res = compute_common_metrics(tx_bits, rx_bits, tx_sym, rx_sym, M_mod, cfg, det_time, toc(t_all));

res.rx_bits = rx_bits; res.tx_bits = tx_bits;
res.tx_sym = tx_sym;   res.rx_sym = rx_sym;
res.M_data = M_data;   res.N_syms = N_syms;
res.L_cp   = L_cp;
res.chan   = chan;
res.tx_iq  = s_ext;     % TX complex baseband samples incl. CPs (N*(M+L_cp) x 1)
res.rx_iq  = r_ext;     % RX complex baseband samples (post-channel+impairments)
res.imp    = imp_info;
end
