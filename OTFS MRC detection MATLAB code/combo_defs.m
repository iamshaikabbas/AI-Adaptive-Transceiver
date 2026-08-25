function D = combo_defs(which)
% =========================================================================
% COMBO_DEFS   Standard waveform/detector combinations so every comparison
% script uses identical labels, order and pairing semantics.
%   'full5' : OTFS-MRC, OTFS-LMMSE, ODDM-MMSETAP, ODDM-LMMSE, OFDM-LMMSE
%   'main3' : OTFS-MRC, ODDM-LMMSE, OFDM-LMMSE
%   'det6'  : every waveform x its two detectors
% =========================================================================
switch lower(which)
    case 'full5'
        D = struct('name',{'OTFS (MRC)','OTFS (LMMSE)','ODDM (MMSETAP)', ...
                           'ODDM (LMMSE)','OFDM (LMMSE)'}, ...
                   'wf',  {'OTFS','OTFS','ODDM','ODDM','OFDM'}, ...
                   'det', {'MRC','LMMSE','MMSETAP','LMMSE','LMMSE'});
    case 'main3'
        D = struct('name',{'OTFS (MRC)','ODDM (LMMSE)','OFDM (LMMSE)'}, ...
                   'wf',  {'OTFS','ODDM','OFDM'}, ...
                   'det', {'MRC','LMMSE','LMMSE'});
    case 'det6'
        D = struct('name',{'OTFS (MRC)','OTFS (LMMSE)','ODDM (MMSETAP)', ...
                           'ODDM (LMMSE)','OFDM (MMSETAP)','OFDM (LMMSE)'}, ...
                   'wf',  {'OTFS','OTFS','ODDM','ODDM','OFDM','OFDM'}, ...
                   'det', {'MRC','LMMSE','MMSETAP','LMMSE','MMSETAP','LMMSE'});
    otherwise
        error('combo_defs: unknown set "%s" (full5|main3|det6).', which);
end
end
