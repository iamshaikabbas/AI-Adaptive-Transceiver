function fd = dt_derive_doppler(speed_kmph, carrier_hz, doppler_scale)
% =========================================================================
% DT_DERIVE_DOPPLER   Maximum Doppler shift [Hz] derived from velocity and
% carrier frequency -- the ONLY way Doppler enters the Digital Twin:
%
%     f_d = (v / 3.6) * fc / c * doppler_scale
%
% Identical to the formula twin_run_frame.m logs and to what
% Generate_delay_Doppler_channel_parameters.m applies physically.
% Doppler is never an independent knob: it follows speed x carrier.
% =========================================================================
if nargin < 3 || isempty(doppler_scale), doppler_scale = 1; end
c_light = 299792458;
fd = (speed_kmph*(1000/3600)/c_light) * carrier_hz * doppler_scale;
end
