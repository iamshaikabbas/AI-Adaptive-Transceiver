function det = twin_default_detector(wf)
% TWIN_DEFAULT_DETECTOR   Deployment detector per waveform (must match
% ai_engine.py DEFAULT_DET and the dataset's default combos).
switch upper(wf)
    case 'OTFS', det = "MRC";
    case 'ODDM', det = "LMMSE";
    case 'OFDM', det = "LMMSE";
    otherwise,   det = "";
end
end
