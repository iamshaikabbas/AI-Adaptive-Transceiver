function out = run_system(cmd, varargin)
% =========================================================================
% RUN_SYSTEM   Master command-line dispatcher for the consolidated Digital
% Twin (spec sections 14-15). ONE entry point; defaults come from
% system_config.json when present.
%
%   run_system('help')
%   run_system('validate')                    % FAST smoke test on scenario A
%   run_system('fast', 'A')                   % 12-frame run
%   run_system('full', 'all')                 % 60-frame canonical A-D
%   run_system('full', 'custom_test')         % user scenarios (JSON)
%   run_system('experiment','tune', 'policy','phase4')
%
% Policy is EXPLICIT everywhere (phase3 = default/canonical,
% phase4 = experimental); run_experiment enforces this.
%
% Returns the summary struct of the underlying run_experiment call
% (or prints help and returns nothing for 'help').
% =========================================================================
here = fileparts(mfilename('fullpath'));
cfgf = fullfile(here,'system_config.json');
dflt = struct('default_mode','FAST','default_scenario','A', ...
              'policy','phase3','seed0',20260823);
if exist(cfgf,'file')==2
    j = jsondecode(fileread(cfgf));
    if isfield(j,'default_mode'),    dflt.default_mode = j.default_mode; end
    if isfield(j,'default_scenario'),dflt.default_scenario = j.default_scenario; end
    if isfield(j,'policy'),          dflt.policy = j.policy; end
    if isfield(j,'seed0'),           dflt.seed0 = double(j.seed0); end
end

if nargin < 1, cmd = 'help'; end
switch lower(char(cmd))
    case 'help'
        fprintf(['RUN_SYSTEM commands:\n' ...
            '  help                          this text\n' ...
            '  validate                      FAST smoke run on %s\n' ...
            '  fast   <scenario|group>       12 frames/scenario\n' ...
            '  full   <scenario|group>       60 frames/scenario\n' ...
            '  experiment <spec> [opts...]   full control, e.g.\n' ...
            '      run_system(''experiment'',''difficult'', ''policy'',''phase4'', ...\n' ...
            '                  ''strategies'',{''ai_adaptive''})\n' ...
            'Scenarios: A-R letters | groups all/tune/heldout/difficult |\n' ...
            'custom names from custom_scenarios/*.json\n'], ...
            dflt.default_scenario);
        out = [];
    case 'validate'
        out = run_experiment(dflt.default_scenario, 'mode','FAST', ...
                             'seed0',dflt.seed0);
    case {'fast','full'}
        assert(nargin>=2,'run_system(%s) needs a scenario argument',cmd);
        out = run_experiment(varargin{1}, 'mode',upper(cmd), ...
                             'seed0',dflt.seed0);
    case 'experiment'
        assert(nargin>=2,'run_system(experiment) needs a spec');
        opts = varargin(2:end);
        if ~any(strcmp(lower(opts(1:2:end)),'seed0')) && numel(opts)>=2
            opts = [{'seed0',dflt.seed0}, opts];
        end
        out = run_experiment(varargin{1}, opts{:});
    otherwise
        error('run_system: unknown command ''%s'' (try help)', cmd);
end
end
