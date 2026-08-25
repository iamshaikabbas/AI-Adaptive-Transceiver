% Copyright (c) 2021, Tharaj Thaj, Emanuele Viterbo, and  Yi Hong, Monash University
% All rights reserved.
%
% Redistribution and use in source and binary forms, with or without
% modification, are permitted provided that the following conditions are met:
%
% 1. Redistributions of source code must retain the above copyright notice, this
%   list of conditions and the following disclaimer.
% 2. Redistributions in binary form must reproduce the above copyright notice,
%   this list of conditions and the following disclaimer in the documentation
%   and/or other materials provided with the distribution.
% 3. The reference listed below should be cited if the corresponding codes are used for
%   publication..
%
%THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
%ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
%WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
%DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR
%ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
%(INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
%LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
%ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
%(INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
%SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
%
%    - Latest version of this code may be downloaded from: https://ecse.monash.edu/staff/eviterbo/
%    - Freely distributed for educational and research purposes
%References

%  [R1]. T. Thaj and E. Viterbo, "Low Complexity Iterative Rake Decision Feedback Equalizer for Zero-Padded OTFS Systems," in IEEE Transactions on Vehicular Technology, vol. 69, no. 12, pp. 15606-15622, Dec. 2020, doi: 10.1109/TVT.2020.3044276.
%  [R2]. T. Thaj and E. Viterbo,``Low Complexity Iterative Rake Detector for Orthogonal Time Frequency Space Modulation'' 2020 IEEE Wireless Communications and Networking Conference (WCNC), 2020, pp. 1-6, doi: 10.1109/WCNC45663.2020.9120526.
%  [R3]. Y. Hong, T. Thaj, E. Viterbo, ``Delay-Doppler Communications: Principles and Applications'', Academic Press, 2022, ISBN:9780323850285
%
% ------------------------------------------------------------------------
% MODIFIED for AI-assisted OTFS project:
%   - max_speed is now supplied by the caller (per-"Environment" scenario)
%     instead of being fixed at 500 km/h.
%   - delay_profile selects which 3GPP delay/PDP table is used (this also
%     fixes how many multipaths ("Paths") the channel has, since delay
%     spread and path count are coupled in a real 3GPP profile - you can't
%     independently pick both without inventing a non-standard channel).
%   - doppler_scale is an extra multiplier on top of the physical
%     speed-derived Doppler shift, so "Doppler" can be tuned independently
%     of "Speed" if desired (e.g. to stress-test the detector).
%   - Backward compatible: calling with only the original 6 arguments
%     reproduces the exact original behaviour (EVA profile, scale = 1).
% ------------------------------------------------------------------------

function [chan_coef,delay_taps,Doppler_taps,taps] = Generate_delay_Doppler_channel_parameters(N,M,car_fre,delta_f,T,max_speed,delay_profile,doppler_scale)

if nargin < 7 || isempty(delay_profile)
    delay_profile = 'EVA';   % original default profile
end
if nargin < 8 || isempty(doppler_scale)
    doppler_scale = 1;       % original behaviour: no extra scaling
end

one_delay_tap = 1/(M*delta_f);
one_doppler_tap = 1/(N*T);

switch upper(delay_profile)
    case 'EPA'
        delays = [0 30 70 90 110 190 410]*10^(-9);                       % EPA model
        pdp    = [0 -1.0 -2.0 -3.0 -8.0 -17.2 -20.8];                    % EPA power delay profile
    case 'EVA'
        delays = [0 30 150 310 370 710 1090 1730 2510]*10^(-9);          % EVA model
        pdp    = [0 -1.5 -1.4 -3.6 -0.6 -9.1 -7.0 -12.0 -16.9];          % EVA power delay profile
    case 'ETU'
        delays = [0 50 120 200 230 500 1600 2300 5000]*10^(-9);          % ETU model
        pdp    = [-1 -1 -1 0 0 0  -3 -5 -7];                             % ETU power delay profile
    otherwise
        error('Generate_delay_Doppler_channel_parameters:UnknownProfile', ...
            'Unknown delay_profile "%s". Valid options are EPA, EVA, ETU.', delay_profile);
end

taps = length(delays);              % number of delay taps ("Paths"), set by the chosen profile
delay_taps = round(delays/one_delay_tap);   %assuming no fraction for the delay

pow_prof = 10.^(pdp/10);
pow_prof = pow_prof/sum(pow_prof);          %normalization of power delay profile
chan_coef = sqrt(pow_prof).*(sqrt(1/2) * (randn(1,taps)+1i*randn(1,taps)));  %channel coef. for each path

max_UE_speed = max_speed*(1000/3600);
Doppler_vel = (max_UE_speed*car_fre)/(299792458);
max_Doppler_tap = doppler_scale * Doppler_vel/one_doppler_tap;
Doppler_taps = (max_Doppler_tap*cos(2*pi*rand(1,taps)));   %Doppler taps using Jake's spectrum
end