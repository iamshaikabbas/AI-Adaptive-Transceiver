function cfg = sim_default_config(varargin)
% =========================================================================
% SIM_DEFAULT_CONFIG   Shared simulation configuration for ALL waveforms
% (OTFS / ODDM / OFDM). Every comparison script must pass THIS struct (with
% documented overrides) to run_otfs / run_oddm / run_ofdm so that both
% waveforms always operate under identical conditions.
%
% cfg = sim_default_config();                          % defaults
% cfg = sim_default_config('SNR_dB',10,'Speed_kmph',120);
%
% Fields (see also run_otfs.m header for semantics):
%   N, M          : DD grid dimensions (time symbols x subcarriers)
%   car_fre       : carrier frequency [Hz]
%   delta_f       : subcarrier spacing [Hz]
%   Modulation    : 4 | 16 | 64   (QPSK / 16-QAM / 64-QAM)
%   Detector      : waveform-specific; see run_*.m
%   SNR_dB        : per-symbol SNR Es/N0 in dB
%   Speed_kmph    : vehicle speed [km/h]
%   DelayProfile  : 'EPA' | 'EVA' | 'ETU' | 'RayleighFlat' | 'AWGN'
%   DopplerScale  : extra multiplier on the physical speed-derived Doppler
%   NumPaths      : [] = use profile path count; integer = synthetic
%                   channel with exactly that many paths (controlled
%                   multipath experiments; delays spread over the profile
%                   span, exponential power decay, Jake's Doppler)
%   chan          : optional pre-generated channel struct (chan_coef,
%                   delay_taps, Doppler_taps) to force identical realizations
%   tx_bits       : optional pre-generated bit vector (paired trials)
%   noise_seed    : rng seed applied right before noise generation so all
%                   waveforms see identical noise realizations
%   n_ite_MRC     : MRC iteration budget (OTFS only)
% =========================================================================

cfg = struct();

% --- Grid & radio (defaults chosen for a balanced compute/accuracy point;
%     identical values are used by every waveform) -----------------------
cfg.N        = 32;
cfg.M        = 32;
cfg.car_fre  = 4e9;
cfg.delta_f  = 15e3;

% --- Link -------------------------------------------------------------
cfg.Modulation   = 4;           % QPSK
cfg.SNR_dB       = 10;

% --- Channel / mobility -----------------------------------------------
cfg.Speed_kmph   = 30;
cfg.DelayProfile = 'EVA';
cfg.DopplerScale = 1;
cfg.NumPaths     = [];

% --- Waveform-specific defaults ----------------------------------------
cfg.OTFS_Detector = 'MRC';      % 'MRC' | 'LMMSE'
cfg.ODDM_Detector = 'LMMSE';    % 'MMSETAP' | 'LMMSE'
cfg.OFDM_Detector = 'MMSETAP';  % 'MMSETAP' | 'LMMSE'
cfg.n_ite_MRC     = 50;

% --- Optional software-RF impairments (applied identically to all
%     waveforms by apply_rx_impairments.m; 0 = off) ------------------------
cfg.cfo_hz                = 0;   % carrier frequency offset [Hz]
cfg.phase_offset_rad      = 0;   % static phase offset [rad]
cfg.timing_offset_samples = 0;   % integer late-timing offset [samples]

% --- Paired-trial plumbing ----------------------------------------------
cfg.chan       = [];
cfg.tx_bits    = [];
cfg.noise_seed = [];

% --- Apply overrides -----------------------------------------------------
if ~isempty(varargin)
    overrides = varargin;
    if numel(overrides) == 1 && isstruct(overrides{1})
        fns = fieldnames(overrides{1});
        for k = 1:numel(fns)
            cfg.(fns{k}) = overrides{1}.(fns{k});
        end
    else
        if mod(numel(overrides),2) ~= 0
            error('sim_default_config: name-value overrides must come in pairs.');
        end
        for k = 1:2:numel(overrides)
            name = overrides{k};
            if ~(ischar(name) || isstring(name))
                error('sim_default_config: override names must be strings.');
            end
            cfg.(char(name)) = overrides{k+1};
        end
    end
end

% --- Derived quantities ---------------------------------------------------
cfg.T        = 1/cfg.delta_f;             % base symbol duration
cfg.BW       = cfg.M * cfg.delta_f;       % system bandwidth
cfg.fs       = cfg.M * cfg.delta_f;       % sample rate
cfg.frame_T  = cfg.N * cfg.T;             % OTFS/ZP frame duration (no CP)
end
