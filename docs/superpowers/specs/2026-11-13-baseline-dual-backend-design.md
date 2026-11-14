# Baseline Dual-Backend Plot Design

## Intent

Build a self-contained baseline-plot example in `Geodesy-Visualization` using
the Jishishan LT-1 temporal/perpendicular baseline network as the reference.
The existing MATLAB result is the visual target. Python/Matplotlib remains the
repository's primary implementation, while MATLAB is retained as a reference
and comparison backend. Both backends consume one documented INI-style CFG so
that labels and appearance do not drift.

The same configuration-driven pattern may later be applied to other Python
figure workflows. A MATLAB backend is optional and is added only where a
MATLAB reference implementation is useful; PyGMT-only cartography is not
required to duplicate a MATLAB renderer.

## Goals

- Reproduce the accepted MATLAB LT-1 baseline figure closely in Matplotlib.
- Use the Analysis baseline manifest and four-column network as the scientific
  input contract; Visualization never recalculates or selects baselines.
- Keep one human-editable CFG for Python and MATLAB.
- Expose the small set of controls needed for scientific publication figures.
- Keep separate Python and MATLAB output paths so results can be compared.
- Make `config_examples/baseline_plot/` a runnable LT-1 reference example.
- Remove the redundant `config_examples/visualization/` directory layer.

## Non-goals

- Do not create a global theme or preset system.
- Do not expose every Matplotlib or MATLAB graphics property.
- Do not make MATLAB a runtime dependency of the Python package.
- Do not invoke GAMMA or modify Analysis products.
- Do not require every future visualization workflow to implement MATLAB.

## Approaches Considered

1. **One INI CFG with two renderers (selected).** Python uses
   `configparser`; MATLAB uses a small repository-owned reader for the same
   sections and keys. This adds a small MATLAB helper but prevents parameter
   drift and preserves comments.
2. **Separate MATLAB structure and Python CFG.** Simpler per backend, but every
   label and style change must be duplicated and the reference figures can
   silently diverge.
3. **One JSON configuration.** MATLAB can use `jsondecode`, but JSON is awkward
   for heavily commented, frequently edited project configurations and does
   not match the repository's established CFG interface.

## Example Layout

The redundant `visualization` level is removed from all example paths. The
baseline example is organized as:

```text
config_examples/
├── baseline/
│   ├── baseline_plot.cfg
│   ├── data/
│   │   ├── baseline_manifest.json
│   │   └── shortbaseline_3
│   └── matlab/
│       ├── baseline_plot_from_cfg.m
│       └── read_baseline_plot_cfg.m
├── deformation_map/
├── deformation_profile/
├── study_area/
├── timeseries_aux/
└── timeseries_map/
```

Generated example images are not package source data. Python and MATLAB write
to separate configured destinations, normally beneath a user project or a
temporary comparison directory.

## Shared Configuration Contract

The existing `[project]`, `[defaults]`, and `[case:name]` structure is kept.
A case overrides defaults. Paths resolve from `[project] root`, remain confined
to that root, and work independently of the current working directory.

Required scientific and output fields:

- `baseline_manifest`: completed Analysis manifest;
- `output`: optional final Matplotlib PNG, preserving the existing public CFG
  contract and its current `project`/`processing_root` derived default;
- `matlab_output`: required only when the optional MATLAB command is run.

Existing Python-only CFG files therefore remain valid. The packaged LT example
sets both output paths so the two backends can be compared.

Exposed figure fields:

- `dpi`, `figsize`;
- `python_font_dir` (optional explicit single-family TTF/OTF directory; the
  packaged example resolves to `fonts/TeXGyreHeros`, and Python reads the
  family name from the font metadata);
- `matlab_font_family` (default `FreeSans`，与 Python 字体独立，不回退);
- `title_label_font_size`: one size shared by title, x label and y label;
- `tick_font_size`;
- `legend_font_size`;
- `font_weight`;
- `title`, `xlabel`, `ylabel`;
- `date_format`, `date_tick_unit`, `date_tick_interval`,
  `date_tick_rotation`;
- `y_tick_interval`;
- `line_color`, `slave_color`, `reference_color`, `grid_color`;
- `show_grid`;
- `line_label`, `slave_label`, `reference_label`;
- existing y margin controls and fixed 30-day left/right date padding.

Only explicit, validated values are accepted. Boolean, positive number, color,
date unit and format errors fail before creating an output. Tick units in the
first version are `day`, `month`, or `year`. Date formatting follows strftime
tokens in Python; the MATLAB adapter translates the supported tokens to the
equivalent display format.

The shared value grammar is deliberately small:

- colors are `#RRGGBB` values;
- `font_weight` is `normal` or `bold`;
- booleans accept case-insensitive `true/false`, `yes/no`, `on/off`, or `1/0`;
- date formats contain `%Y`, `%m`, and/or `%d` with literal spaces, `-`, `/`,
  or `.` separators; the example default is `%Y-%m`.

## Rendering Contract

Both backends use the accepted MATLAB figure as their reference:

- white figure and axes background;
- dark pair lines;
- blue non-reference acquisitions and red reference acquisition;
- bold TeX Gyre Heros text in Python and bold FreeSans text in MATLAB by default;
- boxed axes with ticks on all sides;
- light-gray major grid when enabled;
- legend outside the axes on the right;
- reference baseline fixed at zero;
- the same date and perpendicular-baseline limits and tick intervals.

Pixel identity is not required because MATLAB and Matplotlib use different
layout and rasterization engines. Success means matching scientific points,
connections, labels, colors, tick policy and overall publication layout.

The authoritative reference inputs are:

- script: `Gansu_Jishishan_LT1/result_visual/study_area/shortbaseline_plot_tyl.m`;
- network: `Gansu_Jishishan_LT1/LT-1/project_total_backup/RESULT_mb_3_2/shortbaseline_3`;
- reference date: `20231222`;
- accepted preview: `Gansu_Jishishan_LT1/result_visual/study_area/refactored/perpendicular_baselines_distribution.png`, regenerated after MATLAB confirmed `AxesFontName=FreeSans` and `TitleFontName=FreeSans`.

The repository example synthesizes a schema-valid completed manifest for the
copied three-pair network (reference `20231222`); it does not
claim that this historical LT folder originally contained that manifest.

Python continues to validate the versioned manifest and atomically publishes
its PNG. MATLAB reads the same CFG, loads the same manifest with `jsondecode`,
loads its relative four-column network, and writes only `matlab_output`.
The MATLAB entry point accepts a CFG path plus an optional case name, matching
Python: the case may be omitted only when the CFG contains exactly one case.
It uses the same connected-graph, signed-baseline solution as Python rather
than the legacy script's direct-reference-only fallback, so general SBAS
networks produce the same node values in both backends.

## Generalization Rule

Future Python figure types use the same flow:

```text
CFG -> validated workflow-specific model -> scientific input -> renderer -> output
```

Common names such as font, label, tick, grid, color and output controls should
remain consistent, but each workflow owns only the parameters it actually
needs. There is no inheritance-heavy global theme and no requirement that all
figures expose identical settings.

## Error Handling and Verification

- Existing manifest/network validation remains authoritative.
- Unknown CFG keys remain errors so misspellings cannot silently change plots.
- A missing explicitly configured font is an actionable error rather than a
  silent substitution. The LT example points Python to the repository's
  `fonts/TeXGyreHeros` directory and documents MATLAB FreeSans verification.
- Python implementation follows test-first development for config parsing,
  tick selection, labels/colors/grid controls and CLI output routing.
- A real LT-1 comparison run verifies both PNGs are non-empty and that Python
  uses the configured font and the same node/pair values.
- The complete repository test suite and `git diff --check` must pass.

## Constraints

- Preserve unrelated dirty work already present in `Geodesy-Visualization`.
- Do not commit generated comparison PNGs unless explicitly requested.
- Do not modify the Gansu project layout as part of this repository feature;
  its existing LT data is read as the reference and copied only as a small
  self-contained example dataset.
