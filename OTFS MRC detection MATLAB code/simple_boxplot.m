function simple_boxplot(y, g)
% SIMPLE_BOXPLOT  Toolbox-free stand-in for boxplot(y, g).
%
%   simple_boxplot(y, g) draws one box (25th-75th percentile), a median
%   line, and min/max whiskers for each group in g, using only base
%   MATLAB graphics (patch/plot) — no Statistics and Machine Learning
%   Toolbox required.
%
%   Usage: wherever your code currently calls
%       boxplot(T.Runtime, T.Environment);
%   just call
%       simple_boxplot(T.Runtime, T.Environment);
%   instead. Same two input arguments, same kind of grouped plot.

g = categorical(string(g));
cats = categories(g);
nCats = numel(cats);

hold on;
for i = 1:nCats
    vals = y(g == cats{i});
    vals = sort(vals(~isnan(vals)));
    if isempty(vals)
        continue;
    end

    q1 = local_prctile(vals, 25);
    q2 = local_prctile(vals, 50);
    q3 = local_prctile(vals, 75);
    lo = min(vals);
    hi = max(vals);

    x = i;
    w = 0.3; % half box width

    % box (25th-75th percentile)
    patch([x-w x+w x+w x-w], [q1 q1 q3 q3], [0.7 0.85 1], 'EdgeColor', 'k');
    % median line
    plot([x-w x+w], [q2 q2], 'k-', 'LineWidth', 1.5);
    % whiskers
    plot([x x], [q3 hi], 'k--');
    plot([x x], [q1 lo], 'k--');
    plot([x-w/2 x+w/2], [hi hi], 'k-');
    plot([x-w/2 x+w/2], [lo lo], 'k-');
end
hold off;

set(gca, 'XTick', 1:nCats, 'XTickLabel', cats);
xlim([0.5, nCats + 0.5]);
end

function p = local_prctile(sorted_vals, pct)
% Linear-interpolation percentile on an already-sorted vector.
% (Avoids depending on Statistics Toolbox's prctile/quantile.)
n = numel(sorted_vals);
if n == 1
    p = sorted_vals(1);
    return;
end
rank = (pct/100)*(n-1) + 1;
lo_idx = floor(rank);
hi_idx = ceil(rank);
frac = rank - lo_idx;
p = sorted_vals(lo_idx) + frac*(sorted_vals(hi_idx) - sorted_vals(lo_idx));
end