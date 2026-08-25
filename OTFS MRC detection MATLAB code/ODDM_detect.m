function [rx_bits, iters, x_eq] = ODDM_detect(Y_dd, H_dd, data_mask, M_mod, sigma2, detector)
% =========================================================================
% ODDM_DETECT   Detection / equalization for ODDM in the delay-Doppler
% domain. Two detectors are provided (deliberately NOT reusing the OTFS
% MRC/MPA machinery -- their mathematical assumptions differ):
%
%   'MMSETAP' : per-symbol MMSE single-tap equalizer on the DD grid.
%               Weight w_j = conj(h_jj) / (sum_{k active} |H_jk|^2 + sigma2).
%               The denominator includes the whole active-row energy, so
%               residual ISI/ICI is treated as additional noise -- the same
%               unit-variance-symbol Wiener convention used by the LMMSE
%               detector inside ZP_OTFS_MRC_system.m. Complexity O(nnz H).
%   'LMMSE'   : block linear MMSE Wiener filter over the active data
%               symbols:  x_a = (Ha' Ha + sigma2 I)^-1 Ha' y.
%               Complexity O(|A|^3) dense solve.
%
% Inputs:
%   Y_dd       : M x N received DD-domain grid
%   H_dd       : sparse MN x MN DD-domain channel matrix ([] -> pure
%                1-tap slice; intended only for AWGN sanity tests)
%   data_mask  : M x N logical mask of active data positions
%   M_mod      : QAM order (4 / 16 / 64)
%   sigma2     : noise variance per DD sample
%   detector   : 'MMSETAP' | 'LMMSE'
% Outputs:
%   rx_bits    : recovered bit column vector (gray-mapped QAM demod)
%   iters      : effective iteration count (1; reported for interface
%                parity with the iterative OTFS detectors)
%   x_eq       : equalized DD symbols at the active positions
% =========================================================================

x_idx  = find(data_mask);          % column-major active indices of the grid
y_vec  = Y_dd(:);

switch upper(detector)
    case 'MMSETAP'
        if isempty(H_dd)
            h_diag = ones(numel(y_vec),1);
            prow   = zeros(numel(y_vec),1);
        else
            h_diag = full(diag(H_dd));
            Ha   = H_dd(:, x_idx);                    % active columns only
            prow = zeros(size(h_diag));
            for j = x_idx.'                            % rows of interest only
                prow(j) = real(full(Ha(j,:)) * conj(full(Ha(j,:))).');
            end
        end
        w = conj(h_diag) ./ (prow + sigma2 + eps);
        x_eq_full = w .* y_vec;
        x_eq = x_eq_full(x_idx);

    case 'LMMSE'
        if isempty(H_dd)
            x_eq = y_vec(x_idx);
        else
            Ha = full(H_dd(:, x_idx));
            Wa = Ha'*Ha + sigma2*eye(size(Ha,2));
            x_eq = Wa \ (Ha'*y_vec);
        end

    otherwise
        error('ODDM_detect: unknown detector "%s" (use MMSETAP or LMMSE).', detector);
end

rx_bits = reshape(qamdemod(x_eq(:), M_mod, 'gray', 'OutputType','bit'), [], 1);
iters   = 1;
end
