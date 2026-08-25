function plot_compare_metric(xvals, S, yfield, opts)
% =========================================================================
% PLOT_COMPARE_METRIC   Standard styled curve plot for one metric over a
% sweep. S is numel(combos) x numel(xvals) from run_paired_trials.
%
% opts (all optional name-value):
%   'Yscale'  'log' (default) | 'linear'
%   'Ylabel'  string
%   'Title'   string
%   'Floor'   value clamps the y data from below (e.g. 1e-6 for BER)
% =========================================================================
p = struct('Yscale','log','Ylabel',yfield,'Title','','Floor',[]);
fn = fieldnames(p);
for k = 1:2:numel(opts)
    p.(opts{k}) = opts{k+1}; %#ok<STRNU>
end

nC = size(S,1); nX = numel(xvals);
markers = {'o','s','d','p','^','v'};
cols = lines(max(nC,7));

hold on; grid on; box on;
for i = 1:nC
    y = zeros(1,nX);
    for j = 1:nX, y(j) = S(i,j).(yfield); end
    if ~isempty(p.Floor), y = max(y, p.Floor); end
    if strcmpi(p.Yscale,'log')
        semilogy(xvals, y, ['-' markers{mod(i-1,6)+1}], ...
            'Color',cols(i,:), 'LineWidth',1.6, 'MarkerSize',6, ...
            'MarkerFaceColor',cols(i,:));
    else
        plot(xvals, y, ['-' markers{mod(i-1,6)+1}], ...
            'Color',cols(i,:), 'LineWidth',1.6, 'MarkerSize',6, ...
            'MarkerFaceColor',cols(i,:));
    end
end
xlabel('x'); ylabel(p.Ylabel); title(p.Title);
legend({S(:,1).name}, 'Location','best', 'Interpreter','none');
set(gca,'FontName','DejaVu Sans');
end
