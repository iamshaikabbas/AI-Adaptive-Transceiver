function csvpath = save_compare_results(outdir, tag, xname, xvals, S)
% =========================================================================
% SAVE_COMPARE_RESULTS   Write one comparison sweep to CSV (and return the
% path). One row per (combo x sweep point), SCALAR AGGREGATES ONLY.
%
% REGRESSION NOTE (Phase 1 fix): an earlier version wrote raw per-trial
% metric VECTORS (S.BER, S.SER, S.Throughput_bps, ...) with fprintf, which
% silently expanded every row to hundreds of columns under a 14-name
% header and made all cmp_*.csv unreadable. Only aggregated struct fields
% may be serialized here; per-trial vectors stay in memory.
%
%   S : numel(combos) x numel(xvals) struct array from run_paired_trials
%
% Columns (all scalar):
%   <xname>,label,waveform,detector,
%   BER_total,SER_total,      bit-/symbol-weighted totals (run_paired_trials)
%   PER_mean,CQI_mean,SINR_mean,Run_mean,   trial means from run_paired_trials
%   Thr_mean,SE_mean,Lat_mean,             trial means from run_paired_trials
%   EVM_mean                  arithmetic mean of per-trial EVM_percent
% =========================================================================
if ~exist(outdir, 'dir'), mkdir(outdir); end

cols = {'BER_total','SER_total','PER_mean','Thr_mean','SE_mean', ...
        'CQI_mean','SINR_mean','Lat_mean','Run_mean'};
nC = size(S,1); nX = numel(xvals);

fid = fopen(fullfile(outdir, [tag '.csv']), 'w');
fprintf(fid, '%s,label,waveform,detector', xname);
for k = 1:numel(cols), fprintf(fid, ',%s', cols{k}); end
fprintf(fid, ',EVM_mean\n');
for i = 1:nC
    for j = 1:nX
        fprintf(fid, '%g,%s,%s,%s', xvals(j), S(i,j).name, S(i,j).wf, S(i,j).det);
        for k = 1:numel(cols)
            fprintf(fid, ',%.8g', S(i,j).(cols{k}));
        end
        fprintf(fid, ',%.8g', mean(S(i,j).EVM_percent));
        fprintf(fid, '\n');
    end
end
fclose(fid);
csvpath = fullfile(outdir, [tag '.csv']);
end
