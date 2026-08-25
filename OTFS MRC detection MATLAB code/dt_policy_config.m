function [cfg_file, engine_py] = dt_policy_config(policy)
% =========================================================================
% DT_POLICY_CONFIG   THE single policy -> files mapping (spec section 13).
% Used by run_experiment.m and dt_ai_decide.m so the pairing can never
% drift:
%   phase3 -> adaptive_config_v2.json + ai_engine_v2.py   CANONICAL/DEFAULT
%   phase4 -> adaptive_config_v4.json + ai_engine_v3.py   EXPERIMENTAL
% Any other value errors -- silent defaults are forbidden.
% =========================================================================
switch lower(char(policy))
    case 'phase3'
        cfg_file  = 'adaptive_config_v2.json';
        engine_py = 'ai_engine_v2.py';
    case 'phase4'
        cfg_file  = 'adaptive_config_v4.json';
        engine_py = 'ai_engine_v3.py';
    otherwise
        error(['dt_policy_config: unknown policy ''%s'' ' ...
               '(allowed: phase3|phase4)'], policy);
end
end
