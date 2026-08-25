function tx_bits = dt_payload_for_frame(cfg, chan, payload_seed)
% =========================================================================
% DT_PAYLOAD_FOR_FRAME   Deterministic payload bits for one frame.
%
%   tx_bits = dt_payload_for_frame(cfg_f, chan, payload_seed)
%
% Payload size is derived from THIS frame's realized channel:
%       Lg      = max(chan.max_delay_tap+1, ceil(M/16))   % guard symbols
%       N_syms  = (M - Lg) * N
%       n_bits  = N_syms * log2(modulation)
% then  rng(payload_seed); tx_bits = randi([0 1], n_bits, 1);
%
% This replicates the Phase-3/4 runtime exactly (for the A-D scenarios the
% per-frame sizing provably equals the older probe-based sizing -- their
% runs never errored, see digital_twin_runtime.m note).
% =========================================================================
mod_bits = log2(double(cfg.Modulation));
Lg       = max(double(chan.max_delay_tap)+1, ceil(double(cfg.M)/16));
N_syms   = (double(cfg.M) - Lg) * double(cfg.N);
rng(double(payload_seed));
tx_bits  = randi([0 1], N_syms*mod_bits, 1);
end
