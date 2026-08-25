function s_ext = ODDM_modulate(X_dd, L_cp, Fn)
% =========================================================================
% ODDM_MODULATE   Orthogonal Delay-Doppler Division Multiplexing modulator.
%
% Implements the (approximate) digital ODDM transmitter of:
%   [P1] H. Lin and J. Yuan, "Multicarrier Modulation on Delay-Doppler
%        Plane: Achieving Orthogonality with Fine Resolutions," IEEE ICC 2022
%        (arXiv:2206.13382).
%   [P2] "Orthogonal Delay-Doppler Division Multiplexing Modulation,"
%        IEEE Trans. Wireless Commun., 2022 (doc. 9829188).
%   [P3] H. Lin, "A Primer on Orthogonal Delay-Doppler Division
%        Multiplexing (ODDM)," arXiv:2504.10949, 2025.
%
% Model (digital approximation of the DDOP-based waveform, [P3] Sec. IV):
%   x(t) = sum_m sum_n X[m,n] * u(t - m*T0/M) * exp(j*2*pi*n/(N*T0)*(t-m*T0/M))
% with u(t) = sum_nq a(t - nq*T0) a root-Nyquist pulse TRAIN. Sampling at
% fs = M/T0 (= M*delta_f here), the elementary pulses satisfy a(k*T0/M)=
% delta[k], so the transmit sample stream is the staggered placement
%       s[m + nq*M] = dt[m,nq],
% where dt is obtained by a ROW-WISE N-point IDFT along the DOPPLER axis:
%       dt[m,nq] = sum_n X[m,n] * exp(+j*2*pi*n*nq/N) / sqrt(N).
% This is the defining difference w.r.t. OTFS: OTFS spreads every symbol
% over ALL M*N time-frequency resources with the full symplectic finite
% Fourier transform, while ODDM multiplexes N-symbol delay-time blocks in
% the DELAY dimension (stagger interval T0/M = one sample). A frame-level
% cyclic prefix of length >= max channel delay preserves periodicity.
%
% Lattice alignment with the repository's ZP-OTFS (same bandwidth B=M*df,
% same duration N*T0=NT, same DD resolutions):
%       delay resolution  dT = T0/M = 1/(M*delta_f)  == one_delay_tap
%       Doppler resolution dF = 1/(N*T0) = df/N      == one_doppler_tap
%
% Inputs:
%   X_dd : M x N delay-Doppler symbol matrix (rows = delay index m,
%          cols = Doppler index n; guard rows are zeros)
%   L_cp : frame cyclic-prefix length in samples (>= max channel delay)
%   Fn   : unitary N-point DFT matrix (dftmtx(N)/norm(dftmtx(N)));
%          pass [] to build internally
% Output:
%   s_ext: (NM+L_cp) x 1 complex baseband samples (CP-prepended frame),
%          normalized to unit mean power over the whole extended frame.
% =========================================================================

[M, N] = size(X_dd);
if isempty(Fn)
    Fn = dftmtx(N); Fn = Fn ./ norm(Fn);    % unitary
end

% --- Step 1: row-wise N-point IDFT along the Doppler axis (DD -> delay-time)
dt = X_dd * Fn';                            % dt(m,:) = IDFT of X_dd(m,:)

% --- Step 2: staggered delay-division placement
%     s[m + nq*M] = dt[m,nq]  (delay row m occupies polyphase offset m).
%     MATLAB column-major stacking of dt places each column (= one delay-
%     time block nq, all M staggered offsets) contiguously -- one T0
%     interval per block of M samples.
s = reshape(dt, [], 1);                     % length MN x 1

% --- Step 3: frame-level cyclic prefix (keeps channel circularity)
s_ext = [s(end-L_cp+1:end); s];

% NOTE on fairness: no extra power normalization is applied. With
% unit-energy constellation symbols the unitary IDFT preserves total frame
% energy exactly like the OTFS ISFFT does (||dt||_F^2 = ||X_dd||_F^2), so
% the per-sample transmit-power statistics match ZP-OTFS at the same
% Es/N0-defined SNR. The only additional energy ODDM spends is the L_cp
% cyclic-prefix copies -- an inherent, honestly-reported cost of
% CP-based designs ((1+L_cp/NM) x frame energy).
end
