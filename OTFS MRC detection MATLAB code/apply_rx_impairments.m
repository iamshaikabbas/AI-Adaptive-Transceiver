function [r_out, info] = apply_rx_impairments(r, cfg)
% =========================================================================
% APPLY_RX_IMPAIRMENTS   Optional receiver-side RF impairments shared by
% run_otfs / run_oddm / run_ofdm so every waveform sees identical hardware
% non-idealities. All default to ZERO (pure simulation, no behavior change
% for existing experiments/datasets).
%
%   cfg.cfo_hz                 carrier frequency offset        [Hz]
%   cfg.phase_offset_rad       static phase offset             [rad]
%   cfg.timing_offset_samples  integer late-timing offset      [samples]
%
% Timing model: the frame arrives 'timing_offset_samples' late; samples are
% shifted down and the head is zero-padded (idealized -- no equalizer
% compensation is attempted; detectors simply see a worse channel).
% =========================================================================
r_out = r;
info = struct('cfo_hz',0,'phase_offset_rad',0,'timing_offset_samples',0);

cfo = 0; ph = 0; toff = 0;
if isfield(cfg,'cfo_hz')                && ~isempty(cfg.cfo_hz),                cfo  = cfg.cfo_hz;                end
if isfield(cfg,'phase_offset_rad')      && ~isempty(cfg.phase_offset_rad),      ph   = cfg.phase_offset_rad;      end
if isfield(cfg,'timing_offset_samples') && ~isempty(cfg.timing_offset_samples), toff = round(cfg.timing_offset_samples); end

if toff > 0
    r_out = [zeros(toff,1); r_out(1:end-toff)]; %#ok<AGROW>
elseif toff < 0
    r_out = [r_out(-toff+1:end); zeros(-toff,1)]; %#ok<AGROW>
end

n = (0:numel(r_out)-1).';
fs = cfg.fs;
if cfo ~= 0
    r_out = r_out .* exp(1i*2*pi*cfo*n/fs);
end
if ph ~= 0
    r_out = r_out * exp(1i*ph);
end

info.cfo_hz = cfo; info.phase_offset_rad = ph; info.timing_offset_samples = toff;
end
