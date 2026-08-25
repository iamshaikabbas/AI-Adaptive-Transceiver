function [payload_seed, channel_seed, noise_seed, scenario_seed] = dt_seeds(frame, seed0)
% =========================================================================
% DT_SEEDS   Canonical deterministic seed derivation for one Digital-Twin
% frame (spec section 9). THE single source of the fairness contract.
%
%   payload_seed  = seed0 +  frame      (tx bit generation)
%   channel_seed  = seed0*10 + frame    (channel realization draw)
%   noise_seed    = 100000 + frame      (receiver noise / detection seed)
%   scenario_seed = seed0               (scenario trajectory generation)
%
% The SAME three per-frame seeds are used by EVERY strategy (fixed_otfs,
% fixed_oddm, ai_adaptive, oracle), so all strategies see identical bits,
% identical channel coefficients and identical noise. Strategies are NEVER
% reseeded independently.
%
% These formulas replicate the validated Phase-3/4 runtime byte-for-byte;
% they must never change without a new regression run against
% Results/DigitalTwin/baseline_phase3/ (spec section 27).
%
% Default master seed: 20260823 (dt_config.m C.rng_seed).
% =========================================================================
if nargin < 2 || isempty(seed0), seed0 = 20260823; end
frame  = double(frame);
seed0  = double(seed0);
payload_seed  = seed0 + frame;
channel_seed  = seed0*10 + frame;
noise_seed    = 100000 + frame;
scenario_seed = seed0;
end
