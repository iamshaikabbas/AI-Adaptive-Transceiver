function [row, res] = twin_run_frame(pt, cfg_base, waveform, detector, seed, extra)
% [PHASE-5 NOTE] LEGACY frame executor (schema drifted from the runtime; superseded by dt_exec_waveform.m + dt_frame_result.m).
% =========================================================================
% TWIN_RUN_FRAME   Run ONE Digital-Twin frame: one waveform, one scenario
% point, one paired seed. Shared by digital_twin_runtime.m and
% strategy_compare.m so every consumer logs an IDENTICAL row schema.
%
% pt       : scenario point struct (environment, speed_kmph, snr_db,
%            delay_profile, doppler_scale, modulation, t_s, frame)
% cfg_base : sim_default_config() output carrying N/M/car_fre/delta_f/fs/BW
% waveform : 'OTFS' | 'ODDM' | 'OFDM'
% detector : waveform-specific detector name
% seed     : noise seed for this frame (paired across strategies/waveforms)
% extra    : optional struct merged into the row (AI predictions, flags...)
%
% Channel realization is generated HERE (not cached) unless cfg_base.chan
% is preset -- callers that need cross-strategy pairing pre-set cfg.chan.
%
% Never fabricates results: on simulation failure the row carries
% error_flag=1 and NaN metrics (spec section 37).
% =========================================================================
if nargin < 6, extra = struct(); end

cfg = cfg_base;
cfg.DelayProfile = pt.delay_profile;
cfg.Speed_kmph   = pt.speed_kmph;
cfg.SNR_dB       = pt.snr_db;
cfg.DopplerScale = pt.doppler_scale;
cfg.Modulation   = pt.modulation;
cfg.noise_seed   = seed;
cfg.tx_bits      = [];
cfg.Waveform     = waveform;
if ~isempty(detector)
    cfg.([waveform '_Detector']) = detector;
end

row = twin_empty_row();
row.frame = pt.frame;  row.t_s = pt.t_s;
row.environment = string(pt.environment);
row.speed_kmph = pt.speed_kmph;  row.snr_db = pt.snr_db;
row.delay_profile = string(pt.delay_profile);
row.doppler_scale = pt.doppler_scale;
row.modulation = pt.modulation;
row.waveform = string(waveform);
row.detector = string(detector);
row.strategy = string(cfg_base.TwinStrategy);
c_light = 299792458;
row.doppler_hz = (pt.speed_kmph*(1000/3600)/c_light) * cfg.car_fre * pt.doppler_scale;

try
    switch upper(waveform)
        case 'OTFS', res = run_otfs(cfg);
        case 'ODDM', res = run_oddm(cfg);
        case 'OFDM', res = run_ofdm(cfg);
        otherwise, error('unknown waveform %s', waveform);
    end
    row.BER = res.BER;                    row.SER = res.SER;
    row.PER = res.PER;                    row.Throughput_bps = res.Throughput_bps;
    row.SpectralEfficiency_bps_per_Hz = res.SpectralEfficiency;
    row.CQI = res.CQI;                    row.Latency_ms = res.Latency_ms;
    row.PacketLoss = res.PacketLoss;      row.RecoveryRate = res.RecoveryRate;
    row.ACS = res.ACS;
    row.num_paths = numel(res.chan.delay_taps);
    row.delay_spread_taps = res.chan.max_delay_tap;
    row.error_flag = 0;
catch err
    warning('twin_run_frame: %s frame %d failed: %s', waveform, pt.frame, err.message);
    res = [];
    row.BER = NaN; row.SER = NaN; row.PER = NaN;
    row.Throughput_bps = NaN; row.SpectralEfficiency_bps_per_Hz = NaN;
    row.CQI = NaN; row.Latency_ms = NaN; row.PacketLoss = NaN;
    row.RecoveryRate = NaN; row.ACS = NaN;
    row.num_paths = NaN; row.delay_spread_taps = NaN;
    row.error_flag = 1;
end

if ~isempty(extra)
    fns = fieldnames(extra);
    for k = 1:numel(fns)
        row.(fns{k}) = extra.(fns{k});
    end
end
end
