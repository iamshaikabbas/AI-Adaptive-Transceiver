function [Y_dd, H_dd] = ODDM_demodulate(r_full, L_cp, N, M, Fn, chan, want_H)
% =========================================================================
% ODDM_DEMODULATE   ODDM receiver front-end: CP removal, de-staggering and
% row-wise FFT back to the delay-Doppler domain.
%
% Receiver chain ([P1]-[P3]):
%   r_full (NM+L_cp x 1) --strip CP--> r (NM x 1)
%     --de-stagger-->  R[m,nq] = r[m + nq*M]          (delay-time grid)
%     --row-wise N-point FFT-->  Y_dd = R * Fn        (DD-domain grid)
%
% Optionally returns the exact sparse MN x MN DD-domain channel matrix
%   y_vec = H_dd * x_vec + n_vec,
%   x_vec = vec(X_dd), y_vec = vec(Y_dd)   (column-major stacking),
% built as  H_dd = kron(Fn,I_M) * C * kron(conj(Fn),I_M),  where C is the
% exact effective time-domain channel of the CP-extended frame (wrapped
% input index, Doppler phase keyed on the unwrapped absolute input index,
% SAME z = exp(j*2*pi/(N*M)) convention as Gen_discrete_time_channel.m).
%
% Inputs:
%   r_full : received extended frame
%   L_cp   : cyclic prefix length used at the transmitter
%   N,M    : DD grid dimensions
%   Fn     : unitary DFT matrix ([] to build internally)
%   chan   : struct with fields .chan_coef (1xP), .delay_taps (1xP ints),
%            .Doppler_taps (1xP real)   [] to skip H_dd
%   want_H : true/false
% Outputs:
%   Y_dd   : M x N received DD-domain grid
%   H_dd   : sparse MN x MN channel matrix ([] if not requested)
% =========================================================================

if isempty(Fn)
    Fn = dftmtx(N); Fn = Fn ./ norm(Fn);
end

NM = N*M;
r = r_full(L_cp+1 : L_cp+NM);           % strip frame CP

R = reshape(r, M, N);                   % de-stagger: R(m,nq) = r(m+nq*M)
Y_dd = R * Fn;                          % row-wise FFT: back to DD domain

H_dd = [];
if want_H && ~isempty(chan)
    % ---- exact effective DD-domain channel matrix ---------------------
    % The CP-extended frame makes the channel circular over the data
    % region. For stripped output q' the wrapped input is
    %   p_w = mod(q'-l, NM)
    % while the Doppler phase is keyed on the UNWRAPPED absolute input
    % index q'+L_cp-l (same convention as Gen_discrete_time_channel.m,
    % eq.(16) in [R1], continued through the CP region):
    %   C(q',p) = sum_i g_i * z^(k_i*(q'+L_cp-l_i)) * delta(p == p_w)
    % with z = exp(j*2*pi/(N*M)). The full DD-domain matrix is then
    %   H_dd = kron(Fn, I_M) * C * kron(conj(Fn), I_M)
    % (the composite column-major index j = m + n*M has m fastest, so the
    %  DOPPLER transform is the SLOW/left Kronecker factor; identity check
    %  kron(Fn,I)*kron(conj(Fn),I) = (Fn*conj(Fn)) (x) I_M = I.)
    z  = exp(1i*2*pi/(N*M));
    Pn = length(chan.chan_coef);
    rows=[]; cols=[]; vals=[];
    qv = (0:NM-1);
    for i = 1:Pn
        l     = chan.delay_taps(i);
        p_idx = mod(qv - l, NM);                        % wrapped input idx
        w     = chan.chan_coef(i) * z.^(chan.Doppler_taps(i)*(qv + L_cp - l));
        rows  = [rows, qv + 1];                          %#ok<AGROW>
        cols  = [cols, p_idx + 1];                       %#ok<AGROW>
        vals  = [vals, w];                               %#ok<AGROW>
    end
    C = sparse(rows, cols, vals, NM, NM);

    Km = speye(M);
    H_dd = kron(Fn, Km) * C * kron(conj(Fn), Km);
end
end
