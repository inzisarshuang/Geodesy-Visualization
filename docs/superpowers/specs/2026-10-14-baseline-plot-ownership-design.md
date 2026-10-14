# Baseline Plot Ownership Design

## 1. Goal

Move the complete InSAR temporal–perpendicular baseline plotting workflow from
`Geodesy-Analysis` to `Geodesy-Visualization`. Baseline calculation and pair
selection remain Analysis responsibilities; figure construction and image
publication become Visualization responsibilities.

This change removes the current plotting dependency from the GAMMA baseline
runner without changing its scientific baseline network or the downstream
interferogram pair selection.

## 2. Repository Boundary

`Geodesy-Analysis` owns:

- reading `registered_stack.json`;
- invoking GAMMA `base_calc`;
- validating and publishing the selected pair network;
- publishing `baseline_manifest.json`, `baseline_select_*`, `image_pairs_*`,
  provenance and command logs;
- scientific network calculations used elsewhere in Analysis.

`Geodesy-Visualization` owns:

- reading and validating the completed `baseline_manifest.json`;
- resolving the manifest's relative `network_path` beside the manifest;
- reconstructing display coordinates for the temporal–perpendicular network;
- applying fonts, figure dimensions, title and axis-margin settings;
- atomically publishing the requested PNG figure.

Neither repository imports the other repository's Python package. Their only
integration boundary is the versioned Analysis manifest and its referenced
network text file.

## 3. Public Visualization Workflow

The canonical module is:

```text
geodesy_visualization/workflows/insar/baseline_network.py
```

The installed command is:

```bash
geodesy-visualization-insar-baseline \
  --config /absolute/path/to/baseline_plot.cfg \
  --case ascending
```

The command supports configuration-driven execution only. It does not retain a
second positional-file compatibility mode. This keeps one documented interface
and ensures the plot always carries the reference date and network identity
published by Analysis.

The example configuration uses the existing multi-case pattern:

```ini
[project]
root = /absolute/or/relative/project/root

[defaults]
dpi = 300
figsize = 10.5, 6.2
y_top_extra = 50
y_bottom_extra = 0
font_family = TeX Gyre Heros

[case:ascending]
baseline_manifest = S1/ANALYSIS/GAMMA/ascending/BASELINE/baseline_manifest.json
output = S1/VISUALIZATION/ascending/baseline_network.png
title = Sentinel-1 ascending SBAS baseline network
```

Paths are resolved from the configured project root, confined to that root and
valid from any shell working directory. Unknown sections, duplicate keys,
unknown keys, invalid numeric values, unsafe case names and paths outside the
project fail before Matplotlib is loaded.

## 4. Input Contract

Visualization accepts a completed Analysis baseline manifest with:

- `schema_version = 1`;
- `status = "complete"`;
- a valid `reference_date` in `YYYYMMDD` form;
- a positive integer `pair_count`;
- a non-empty relative `network_path` that cannot traverse outside the
  manifest directory.

The referenced network must exist, remain inside the project and manifest
directory, and contain exactly `pair_count` non-comment records. Each record
uses the Analysis output contract:

```text
master_yyyymmdd slave_yyyymmdd perpendicular_baseline_m temporal_baseline_days
```

Malformed dates, non-finite values, duplicate or reversed pairs, self-pairs,
and a reference date absent from the network are rejected with actionable
errors. Extra manifest fields are ignored, so already generated schema-1
manifests containing `plot_path` remain readable without carrying compatibility
branches in the public CLI.

## 5. Analysis Changes

The GAMMA baseline runner publishes scientific outputs in two progress stages:
baseline calculation and publication. It no longer imports a plotter, accepts a
`plotter` callback, emits a plot progress item, stores `plot_path`, or records
plot warnings. Existing completed outputs remain restart-safe: an old optional
`plot_path` is ignored rather than required when checking whether a schema-1
result can be skipped.

The Analysis package removes:

- `geodesy-analysis-baseline-plot`;
- `config_examples/baseline_plot.cfg`;
- the standalone plot CLI and plot configuration modules;
- Matplotlib and `geodesy_visualization` imports;
- plotting-only functions and documentation from
  `geodesy_analysis.insar.baseline`;
- the `plot` optional dependency and Matplotlib from the `all` dependency set.

Network parsing and scientific functions still used by Analysis remain in
`geodesy_analysis.insar.baseline`.

## 6. Output And Failure Behavior

Visualization writes one PNG through a temporary sibling path and atomically
replaces the requested destination only after Matplotlib completes. A plotting
failure leaves any previous final image unchanged and removes the temporary
file.

The command returns:

- `0` after publishing the figure;
- `2` for configuration, manifest, network or plotting errors.

It prints one concise success line containing the final path. It never invokes
GAMMA and never modifies Analysis products.

## 7. Documentation And Project Configuration

The Visualization README gains the baseline-network workflow, installed command,
input/output description and example cfg. The Analysis README and GAMMA workflow
describe the baseline manifest as the hand-off to Visualization and no longer
claim that baseline selection produces a figure.

The existing Jishishan project cfg moves from
`config/analysis/baseline_plot.cfg` to
`config/visualization/baseline_plot.cfg`, references the existing Analysis
manifest, and writes its figure beneath the project's Visualization output
area. The old project cfg is removed after the new command succeeds.

## 8. Verification

Implementation follows test-first development in both repositories.

Visualization tests cover manifest validation, network validation, cfg path
confinement, case selection, atomic PNG publication, CLI exit codes, package
entry-point exposure and the documented example configuration. A real check
uses the existing Jishishan ascending baseline manifest and confirms that the
new command produces a non-empty image without invoking GAMMA.

Analysis tests prove that baseline selection publishes the same dates, pair
order and perpendicular/temporal values without creating a PNG or importing
Matplotlib/Geodesy-Visualization. Existing completed Jishishan baseline and
interferogram products must still return `skipped` after the change.

Both complete repository test suites and `git diff --check` must pass. Existing
untracked CPT assets in `Geodesy-Visualization` are user-owned and remain
untouched.
