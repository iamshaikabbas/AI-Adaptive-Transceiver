function chan = gen_channel_params_flex(cfg)
% =========================================================================
% GEN_CHANNEL_PARAMS_FLEX   Channel parameter generator shared by ALL
% waveforms so every run_* function sees the same physical channel.
%
%  * 'EPA' | 'EVA' | 'ETU' : delegates to the EXISTING (untouched) repo
%    generator Generate_delay_Doppler_channel_parameters.m, which draws
%    Jake's-spectrum Doppler taps and complex path gains from the 3GPP
%    power delay profiles.
%  * 'RayleighFlat'        : single zero-delay path, CN(0,1) gain, no Doppler.
%  * 'AWGN'                : identity channel (unit gain, zero delay/Doppler).
%  * NumPaths override     : synthetic P-path channel -- integer delays
%    spread over the selected profile's span, exponentially decaying PDP,
%    Jake's Doppler. Used for the controlled "BER vs number of paths"
%    experiment where path count must be independent of the profile table.
%
% Output struct fields: .chan_coef (1xP), .delay_taps (1xP int),
%                       .Doppler_taps (1xP), .taps (P), .profile (string),
%                       .max_delay_tap, .doppler_spread_hz
% =========================================================================

N = cfg.N; M = cfg.M; car_fre = cfg.car_fre; delta_f = cfg.delta_f;
T = cfg.T;
prof = upper(string(cfg.DelayProfile));

one_doppler_tap = 1/(N*T);

switch prof
    case {'EPA','EVA','ETU'}
        if isempty(cfg.NumPaths)
            [coef, dt, kt, P] = Generate_delay_Doppler_channel_parameters(...
                N, M, car_fre, delta_f, T, cfg.Speed_kmph, char(prof), cfg.DopplerScale);
        else
            % ---- synthetic NumPaths-controlled variant -------------------
            P = cfg.NumPaths;
            switch prof
                case 'EPA', l_span = round(410e-9 *M*delta_f);
                case 'EVA', l_span = round(2510e-9 *M*delta_f);
                case 'ETU', l_span = round(5000e-9 *M*delta_f);
            end
            l_span = max(l_span, P-1);
            dt = unique(round(linspace(0, l_span, P)));
            P  = numel(dt);
            pdp_db = -3*(0:P-1);                    % 3 dB per tap decay
            pow = 10.^(pdp_db/10); pow = pow/sum(pow);
            coef = sqrt(pow).*(sqrt(1/2)*(randn(1,P)+1i*randn(1,P)));
            max_speed = cfg.Speed_kmph*(1000/3600);
            dv  = (max_speed*car_fre)/299792458;
            mdt = cfg.DopplerScale*dv/one_doppler_tap;
            kt  = mdt*cos(2*pi*rand(1,P));
        end

    case 'RAYLEIGHFLAT'
        P = 1; dt = 0; kt = 0;
        coef = sqrt(1/2)*(randn(1,1)+1i*randn(1,1));

    case 'AWGN'
        P = 1; dt = 0; kt = 0; coef = 1;

    otherwise
        error('gen_channel_params_flex: unknown DelayProfile "%s".', char(prof));
end

chan.chan_coef      = coef;
chan.delay_taps     = dt(:).';
chan.Doppler_taps   = kt(:).';
chan.taps           = P;
chan.profile        = char(prof);
chan.max_delay_tap  = max(chan.delay_taps);
chan.doppler_spread_hz = max(abs(kt))*one_doppler_tap;
end
