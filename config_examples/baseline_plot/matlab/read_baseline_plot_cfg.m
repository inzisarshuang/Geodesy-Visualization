function document = read_baseline_plot_cfg(cfgPath)
%READ_BASELINE_CFG Read the shared baseline INI-style configuration.
%   DOCUMENT = READ_BASELINE_CFG(CFGPATH) parses full-line #/; comments,
%   [section] headers, and key=value entries. Inline # characters are kept
%   so hexadecimal colors such as #FF0000 remain intact.

cfgPath = char(cfgPath);
if ~isfile(cfgPath)
    error('baseline:cfg:missing', 'Configuration not found: %s', cfgPath);
end

lines = regexp(fileread(cfgPath), '\r\n|\n|\r', 'split');
sections = struct();
sectionNames = struct();
order = {};
sectionField = '';

for lineNumber = 1:numel(lines)
    line = strtrim(lines{lineNumber});
    if isempty(line) || startsWith(line, '#') || startsWith(line, ';')
        continue;
    end
    if startsWith(line, '[')
        if ~endsWith(line, ']') || numel(line) < 3
            error('baseline:cfg:section', ...
                'Invalid section header at line %d.', lineNumber);
        end
        sectionName = strtrim(line(2:end-1));
        if isempty(regexp(sectionName, '^[A-Za-z0-9][A-Za-z0-9_.:-]*$', 'once'))
            error('baseline:cfg:section', ...
                'Unsafe or empty section at line %d.', lineNumber);
        end
        sectionField = matlab.lang.makeValidName( ...
            sectionName, 'ReplacementStyle', 'hex');
        if isfield(sections, sectionField)
            error('baseline:cfg:duplicateSection', ...
                'Duplicate section [%s].', sectionName);
        end
        sections.(sectionField) = struct();
        sectionNames.(sectionField) = sectionName;
        order{end + 1} = sectionName; %#ok<AGROW>
        continue;
    end
    if isempty(sectionField)
        error('baseline:cfg:entry', ...
            'Entry outside a section at line %d.', lineNumber);
    end
    separator = strfind(line, '=');
    if isempty(separator)
        error('baseline:cfg:entry', ...
            'Expected key=value at line %d.', lineNumber);
    end
    splitAt = separator(1);
    key = lower(strtrim(line(1:splitAt - 1)));
    value = strtrim(line(splitAt + 1:end));
    if isempty(regexp(key, '^[A-Za-z][A-Za-z0-9_]*$', 'once'))
        error('baseline:cfg:key', 'Invalid key at line %d.', lineNumber);
    end
    if isfield(sections.(sectionField), key)
        error('baseline:cfg:duplicateKey', ...
            'Duplicate key %s at line %d.', key, lineNumber);
    end
    sections.(sectionField).(key) = value;
end

document.path = canonical_path(cfgPath);
document.sections = sections;
document.section_names = sectionNames;
document.order = order;
end


function path = canonical_path(path)
%CANONICAL_PATH Return an absolute normalized filesystem path.

path = char(java.io.File(char(path)).getCanonicalPath());
end
