function outputPath = baseline_plot_from_cfg(cfgPath, caseName)
%PLOT_BASELINE_FROM_CFG Render one baseline case from the shared CFG.
%   OUTPUTPATH = PLOT_BASELINE_FROM_CFG(CFGPATH, CASENAME) reads the same
%   Analysis-compatible manifest, four-column network, labels, ticks, colors,
%   and typography used by the Python baseline workflow.

if nargin < 2
    caseName = '';
end
document = read_baseline_plot_cfg(cfgPath);
project = cfg_section(document, 'project', true);
if ~isfield(project, 'root') || isempty(strtrim(project.root))
    error('baseline:cfg:project', '[project] root is required.');
end
cfgDirectory = fileparts(document.path);
projectRoot = confined_path(cfgDirectory, project.root, '', 'project root');

defaults = builtin_defaults();
configuredDefaults = cfg_section(document, 'defaults', false);
defaults = merge_values(defaults, configuredDefaults);
[selectedName, selectedCase] = select_case(document, caseName);
values = merge_values(defaults, selectedCase);

required = {'baseline_manifest', 'matlab_output'};
for index = 1:numel(required)
    key = required{index};
    if ~isfield(values, key) || isempty(strtrim(values.(key)))
        error('baseline:cfg:required', '[case:%s] requires %s.', selectedName, key);
    end
end

manifestPath = confined_path(projectRoot, values.baseline_manifest, ...
    projectRoot, 'baseline_manifest');
outputPath = confined_path(projectRoot, values.matlab_output, ...
    projectRoot, 'matlab_output');
if ~isfile(manifestPath)
    error('baseline:manifest:missing', 'Manifest not found: %s', manifestPath);
end
manifest = jsondecode(fileread(manifestPath));
if ~isfield(manifest, 'status') || ~strcmp(char(manifest.status), 'complete')
    error('baseline:manifest:status', 'Manifest status must be complete.');
end
if ~isfield(manifest, 'reference_date') || ~isfield(manifest, 'network_path')
    error('baseline:manifest:fields', ...
        'Manifest requires reference_date and network_path.');
end
referenceDate = str2double(char(manifest.reference_date));
networkPath = confined_path(fileparts(manifestPath), ...
    char(manifest.network_path), fileparts(manifestPath), 'network_path');
if ~isfile(networkPath)
    error('baseline:network:missing', 'Network not found: %s', networkPath);
end
baseline = readmatrix(networkPath, 'FileType', 'text');
if isempty(baseline) || size(baseline, 2) ~= 4
    error('baseline:network:shape', ...
        'Network must contain at least one row and exactly four columns.');
end

[dates, perpendicular] = solve_baselines(baseline, referenceDate);
dateNumbers = datenum(arrayfun(@(value) sprintf('%08d', value), dates, ...
    'UniformOutput', false), 'yyyymmdd');

fontFamily = char(values.matlab_font_family);
fontWeight = lower(char(values.font_weight));
if ~any(strcmp(fontWeight, {'normal', 'bold'}))
    error('baseline:cfg:fontWeight', 'font_weight must be normal or bold.');
end

figureSize = number_pair(values.figsize, 'figsize');
dpi = positive_number(values.dpi, 'dpi');
titleLabelSize = positive_number(values.title_label_font_size, ...
    'title_label_font_size');
tickSize = positive_number(values.tick_font_size, 'tick_font_size');
legendSize = positive_number(values.legend_font_size, 'legend_font_size');
yTopExtra = nonnegative_number(values.y_top_extra, 'y_top_extra');
yBottomExtra = nonnegative_number(values.y_bottom_extra, 'y_bottom_extra');
yTickInterval = positive_number(values.y_tick_interval, 'y_tick_interval');
dateTickInterval = positive_integer(values.date_tick_interval, ...
    'date_tick_interval');
dateRotation = finite_number(values.date_tick_rotation, 'date_tick_rotation');
if dateRotation < -360 || dateRotation > 360
    error('baseline:cfg:rotation', ...
        'date_tick_rotation must be between -360 and 360.');
end
showGrid = boolean_value(values.show_grid, 'show_grid');
lineColor = hex_color(values.line_color, 'line_color');
slaveColor = hex_color(values.slave_color, 'slave_color');
referenceColor = hex_color(values.reference_color, 'reference_color');
gridColor = hex_color(values.grid_color, 'grid_color');

oldAxesFont = get(groot, 'defaultAxesFontName');
oldTextFont = get(groot, 'defaultTextFontName');
restoreDefaults = onCleanup(@() restore_fonts(oldAxesFont, oldTextFont)); %#ok<NASGU>
set(groot, 'defaultAxesFontName', fontFamily);
set(groot, 'defaultTextFontName', fontFamily);

fig = figure('Visible', 'off', 'Color', 'white', 'Units', 'inches', ...
    'Position', [1, 1, figureSize(1), figureSize(2)]);
closeFigure = onCleanup(@() close(fig)); %#ok<NASGU>
axisHandle = axes(fig);
hold(axisHandle, 'on');
box(axisHandle, 'on');

master = baseline(:, 1);
slave = baseline(:, 2);
[~, masterIndex] = ismember(master, dates);
[~, slaveIndex] = ismember(slave, dates);
for row = 1:size(baseline, 1)
    plot(axisHandle, ...
        [dateNumbers(masterIndex(row)), dateNumbers(slaveIndex(row))], ...
        [perpendicular(masterIndex(row)), perpendicular(slaveIndex(row))], ...
        '-', 'Color', lineColor, 'LineWidth', 2.0, ...
        'HandleVisibility', 'off');
end
hLine = plot(axisHandle, nan, nan, '-', 'Color', lineColor, 'LineWidth', 2.0);
referenceIndex = find(dates == referenceDate, 1);
slaveIndices = setdiff(1:numel(dates), referenceIndex);
hSlave = plot(axisHandle, dateNumbers(slaveIndices), perpendicular(slaveIndices), ...
    'o', 'MarkerSize', 10, 'MarkerFaceColor', slaveColor, ...
    'MarkerEdgeColor', slaveColor, 'LineWidth', 1.5, 'LineStyle', 'none');
hReference = plot(axisHandle, dateNumbers(referenceIndex), ...
    perpendicular(referenceIndex), 'o', 'MarkerSize', 10, ...
    'MarkerFaceColor', referenceColor, 'MarkerEdgeColor', referenceColor, ...
    'LineWidth', 1.5, 'LineStyle', 'none');

xPaddingDays = 30;
ySpan = max(perpendicular) - min(perpendicular);
yPadding = max(40, ySpan * 0.12);
xlim(axisHandle, [min(dateNumbers) - xPaddingDays, ...
    max(dateNumbers) + xPaddingDays]);
ylim(axisHandle, [min(perpendicular) - yPadding - yBottomExtra, ...
    max(perpendicular) + yPadding + yTopExtra]);

set(axisHandle, 'LineWidth', 2.0, 'FontName', fontFamily, ...
    'FontSize', tickSize, 'FontWeight', fontWeight, ...
    'TickDir', 'in', 'XAxisLocation', 'bottom', 'YAxisLocation', 'left', ...
    'XColor', [0, 0, 0], 'YColor', [0, 0, 0], 'Layer', 'bottom');
axisHandle.XAxis.TickDirection = 'in';
axisHandle.YAxis.TickDirection = 'in';
axisHandle.XAxis.MinorTick = 'off';
axisHandle.YAxis.MinorTick = 'off';

ticks = date_ticks(min(dateNumbers) - xPaddingDays, ...
    max(dateNumbers) + xPaddingDays, values.date_tick_unit, dateTickInterval);
set(axisHandle, 'XTick', ticks);
datetick(axisHandle, 'x', matlab_date_format(values.date_format), ...
    'keepticks', 'keeplimits');
xtickangle(axisHandle, dateRotation);
yLimits = ylim(axisHandle);
set(axisHandle, 'YTick', ...
    ceil(yLimits(1) / yTickInterval) * yTickInterval:yTickInterval: ...
    floor(yLimits(2) / yTickInterval) * yTickInterval);

if showGrid
    grid(axisHandle, 'on');
    axisHandle.GridColor = gridColor;
    axisHandle.GridAlpha = 1.0;
else
    grid(axisHandle, 'off');
end

title(axisHandle, char(values.title), 'FontName', fontFamily, ...
    'FontSize', titleLabelSize, 'FontWeight', fontWeight);
xlabel(axisHandle, char(values.xlabel), 'FontName', fontFamily, ...
    'FontSize', titleLabelSize, 'FontWeight', fontWeight);
ylabel(axisHandle, char(values.ylabel), 'FontName', fontFamily, ...
    'FontSize', titleLabelSize, 'FontWeight', fontWeight);
legend(axisHandle, [hLine, hSlave, hReference], ...
    {char(values.line_label), char(values.slave_label), ...
    char(values.reference_label)}, 'Location', 'northeastoutside', ...
    'FontName', fontFamily, 'FontSize', legendSize, ...
    'FontWeight', fontWeight, 'Box', 'on', 'LineWidth', 1.5);

outputDirectory = fileparts(outputPath);
if ~isfolder(outputDirectory)
    mkdir(outputDirectory);
end
set(fig, 'PaperPositionMode', 'auto');
print(fig, outputPath, '-dpng', sprintf('-r%d', round(dpi)));
fprintf('[baseline_plot] MATLAB FontName=%s\n', get(axisHandle, 'FontName'));
fprintf('[baseline_plot] wrote %s\n', outputPath);
end


function defaults = builtin_defaults()
%BUILTIN_DEFAULTS Mirror the Python publication defaults.

defaults = struct( ...
    'title', 'Baselines Distribution', ...
    'dpi', '300', 'figsize', '10.5, 6.2', ...
    'y_top_extra', '50', 'y_bottom_extra', '0', ...
    'matlab_font_family', 'FreeSans', ...
    'title_label_font_size', '18', 'tick_font_size', '16', ...
    'legend_font_size', '14', 'font_weight', 'bold', ...
    'xlabel', 'SLC Images Acquire Date', ...
    'ylabel', 'Perpendicular Baselines (m)', ...
    'date_format', '%Y-%m', 'date_tick_unit', 'month', ...
    'date_tick_interval', '1', 'date_tick_rotation', '45', ...
    'y_tick_interval', '100', 'line_color', '#333333', ...
    'slave_color', '#0000FF', 'reference_color', '#FF0000', ...
    'grid_color', '#D9D9D9', 'show_grid', 'true', ...
    'line_label', 'perpendicular baselines', ...
    'slave_label', 'slave SLC images', ...
    'reference_label', 'reference SLC image');
end


function section = cfg_section(document, name, required)
%CFG_SECTION Return one named CFG section.

field = matlab.lang.makeValidName(name, 'ReplacementStyle', 'hex');
if ~isfield(document.sections, field)
    if required
        error('baseline:cfg:section', 'Missing [%s] section.', name);
    end
    section = struct();
    return;
end
section = document.sections.(field);
end


function [name, section] = select_case(document, requested)
%SELECT_CASE Apply the same single/multi-case rule as Python.

caseNames = document.order(startsWith(document.order, 'case:'));
if isempty(caseNames)
    error('baseline:cfg:case', 'At least one [case:name] section is required.');
end
requested = char(requested);
if isempty(requested)
    if numel(caseNames) ~= 1
        error('baseline:cfg:case', 'caseName is required for multiple cases.');
    end
    fullName = caseNames{1};
else
    fullName = ['case:' requested];
    if ~any(strcmp(caseNames, fullName))
        error('baseline:cfg:case', 'Unknown case: %s', requested);
    end
end
name = extractAfter(fullName, 'case:');
section = cfg_section(document, fullName, true);
end


function merged = merge_values(base, override)
%MERGE_VALUES Apply one CFG section over defaults.

merged = base;
keys = fieldnames(override);
for index = 1:numel(keys)
    merged.(keys{index}) = override.(keys{index});
end
end


function path = confined_path(base, value, root, label)
%CONFINED_PATH Resolve a path and optionally confine it to ROOT.

value = char(value);
candidate = java.io.File(value);
if candidate.isAbsolute()
    path = char(candidate.getCanonicalPath());
else
    path = char(java.io.File(base, value).getCanonicalPath());
end
if ~isempty(root)
    root = char(java.io.File(root).getCanonicalPath());
    prefix = [root filesep];
    if ~strcmp(path, root) && ~startsWith(path, prefix)
        error('baseline:cfg:path', '%s must stay inside project root.', label);
    end
end
end


function [dates, solved] = solve_baselines(baseline, referenceDate)
%SOLVE_BASELINES Solve signed node baselines over a connected pair graph.

dates = sort(unique([baseline(:, 1); baseline(:, 2)]));
referenceIndex = find(dates == referenceDate, 1);
if isempty(referenceIndex)
    error('baseline:network:reference', 'Reference date is absent from network.');
end
solved = nan(size(dates));
solved(referenceIndex) = 0;
changed = true;
while changed
    changed = false;
    for row = 1:size(baseline, 1)
        masterIndex = find(dates == baseline(row, 1), 1);
        slaveIndex = find(dates == baseline(row, 2), 1);
        if ~isnan(solved(masterIndex)) && isnan(solved(slaveIndex))
            solved(slaveIndex) = solved(masterIndex) + baseline(row, 3);
            changed = true;
        elseif isnan(solved(masterIndex)) && ~isnan(solved(slaveIndex))
            solved(masterIndex) = solved(slaveIndex) - baseline(row, 3);
            changed = true;
        end
    end
end
if any(isnan(solved))
    error('baseline:network:disconnected', ...
        'Network is disconnected from the reference date.');
end
end


function ticks = date_ticks(lowerLimit, upperLimit, unit, interval)
%DATE_TICKS Build fixed day/month/year ticks inside display limits.

startDate = datetime(lowerLimit, 'ConvertFrom', 'datenum');
endDate = datetime(upperLimit, 'ConvertFrom', 'datenum');
unit = lower(char(unit));
switch unit
    case 'day'
        startDate = dateshift(startDate, 'start', 'day');
        values = startDate:caldays(interval):endDate;
    case 'month'
        monthSerial = year(startDate) * 12 + month(startDate) - 1;
        firstSerial = ceil(monthSerial / interval) * interval;
        firstYear = floor(firstSerial / 12);
        firstMonth = mod(firstSerial, 12) + 1;
        firstDate = datetime(firstYear, firstMonth, 1);
        if firstDate < startDate
            firstDate = firstDate + calmonths(interval);
        end
        values = firstDate:calmonths(interval):endDate;
    case 'year'
        startDate = dateshift(startDate, 'start', 'year');
        values = startDate:calyears(interval):endDate;
    otherwise
        error('baseline:cfg:dateUnit', ...
            'date_tick_unit must be day, month, or year.');
end
ticks = datenum(values);
end


function format = matlab_date_format(value)
%MATLAB_DATE_FORMAT Translate the supported shared strftime subset.

value = char(value);
if isempty(regexp(value, '^(%[Ymd]|[ ./-])+$', 'once'))
    error('baseline:cfg:dateFormat', ...
        'date_format supports %%Y, %%m, %%d and simple separators.');
end
format = strrep(value, '%Y', 'yyyy');
format = strrep(format, '%m', 'mm');
format = strrep(format, '%d', 'dd');
end


function value = finite_number(text, key)
%FINITE_NUMBER Parse one finite scalar.

value = str2double(char(text));
if ~isscalar(value) || ~isfinite(value)
    error('baseline:cfg:number', '%s must be a finite number.', key);
end
end


function value = positive_number(text, key)
%POSITIVE_NUMBER Parse one positive finite scalar.

value = finite_number(text, key);
if value <= 0
    error('baseline:cfg:number', '%s must be positive.', key);
end
end


function value = nonnegative_number(text, key)
%NONNEGATIVE_NUMBER Parse one non-negative finite scalar.

value = finite_number(text, key);
if value < 0
    error('baseline:cfg:number', '%s must be non-negative.', key);
end
end


function value = positive_integer(text, key)
%POSITIVE_INTEGER Parse one positive integer.

value = positive_number(text, key);
if value ~= round(value)
    error('baseline:cfg:integer', '%s must be a positive integer.', key);
end
value = round(value);
end


function values = number_pair(text, key)
%NUMBER_PAIR Parse one comma/space separated positive pair.

fields = regexp(strtrim(char(text)), '[, ]+', 'split');
if numel(fields) ~= 2
    error('baseline:cfg:pair', '%s must contain two positive numbers.', key);
end
values = [positive_number(fields{1}, key), positive_number(fields{2}, key)];
end


function value = boolean_value(text, key)
%BOOLEAN_VALUE Parse the shared Boolean spellings.

text = lower(strtrim(char(text)));
if any(strcmp(text, {'1', 'true', 'yes', 'on'}))
    value = true;
elseif any(strcmp(text, {'0', 'false', 'no', 'off'}))
    value = false;
else
    error('baseline:cfg:boolean', '%s must be a Boolean value.', key);
end
end


function rgb = hex_color(text, key)
%HEX_COLOR Convert #RRGGBB to a MATLAB RGB triplet.

text = char(text);
if isempty(regexp(text, '^#[0-9A-Fa-f]{6}$', 'once'))
    error('baseline:cfg:color', '%s must use #RRGGBB.', key);
end
rgb = [hex2dec(text(2:3)), hex2dec(text(4:5)), hex2dec(text(6:7))] / 255;
end


function restore_fonts(axesFont, textFont)
%RESTORE_FONTS Restore MATLAB root graphics defaults.

set(groot, 'defaultAxesFontName', axesFont);
set(groot, 'defaultTextFontName', textFont);
end
