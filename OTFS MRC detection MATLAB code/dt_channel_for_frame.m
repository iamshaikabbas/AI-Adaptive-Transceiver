function chan = dt_channel_for_frame(cfg, channel_seed)
% =========================================================================
% DT_CHANNEL_FOR_FRAME   Deterministic channel realization for one frame.
%
%   chan = dt_channel_for_frame(cfg_f, channel_seed)
%
% Draws exactly like the validated Phase-3/4 runtime:
%       rng(channel_seed);  chan = gen_channel_params_flex(cfg_f);
% with channel_seed = seed0*10 + frame (dt_seeds.m). Callers must NOT draw
% anything else from the global RNG between seeding and this call.
% =========================================================================
rng(double(channel_seed));
chan = gen_channel_params_flex(cfg);
end
