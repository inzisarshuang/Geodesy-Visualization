# Baseline Dual-Backend Plot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a FreeSans, MATLAB-reference baseline plot workflow whose Python and optional MATLAB renderers consume one documented CFG and whose runnable LT-1 example lives under `config_examples/baseline_plot/`.

**Architecture:** Preserve the Analysis manifest/four-column-network boundary and the existing Python CLI. Extend its immutable config model with validated publication controls, pass a focused render-style value into Matplotlib, and add a standalone MATLAB CFG adapter that reads the same case. Flatten `config_examples/visualization/` while updating packaging and documentation references.

**Tech Stack:** Python 3.10+, `configparser`, Matplotlib, `unittest`, MATLAB R2022b, INI CFG, JSON manifest

**Spec:** `docs/superpowers/specs/2026-11-13-baseline-dual-backend-design.md`

## Global Constraints

- `FreeSans` is the default and missing explicitly configured fonts fail instead of silently substituting.
- `title_label_font_size` controls title/xlabel/ylabel; `tick_font_size` and `legend_font_size` remain independent.
- Shared colors use `#RRGGBB`; `font_weight` is `normal|bold`; date units are `day|month|year`.
- Python-only CFGs remain compatible: `output` may still be derived and `matlab_output` is ignored unless MATLAB runs.
- MATLAB and Python solve the same connected, signed baseline graph.
- Preserve unrelated dirty and untracked files, including current study-area work, timeseries data, CPTs, and `deformation_map.py` changes.
- Do not commit, push, or modify the Gansu project layout in this implementation.

## Review Focus

- A multi-case CFG without `--case` must fail identically before either renderer writes output.
- A configured font that is absent must fail with the requested family name in the error.
- Date-format tokens or separators outside the shared grammar must fail before plotting.
- A valid indirect SBAS graph must give identical signed node baselines in Python and MATLAB.
- Moving example directories must preserve tracked and untracked example assets and leave no active `config_examples/visualization/` references.

---

### Task 1: Flatten the Example Configuration Layout

**Files:**
- Move: `config_examples/visualization/deformation_map/` -> `config_examples/deformation_map/`
- Move: `config_examples/visualization/deformation_profile/` -> `config_examples/deformation_profile/`
- Move: `config_examples/visualization/study_area/` -> `config_examples/study_area/`
- Move: `config_examples/visualization/timeseries_aux/` -> `config_examples/timeseries_aux/`
- Move: `config_examples/visualization/timeseries_map/` -> `config_examples/timeseries_map/`
- Move: `config_examples/visualization/baseline_plot.cfg` -> `config_examples/baseline_plot/baseline_plot.cfg`
- Modify: `pyproject.toml`
- Modify: `README.md`
- Modify: `docs/development/python_rules.md`
- Modify: `docs/development/engineering_rules.md`
- Modify: active cfg usage comments beneath `config_examples/`
- Test: `tests/test_baseline_plot.py`
- Test: `tests/test_study_area_workflow.py`

**Interfaces:**
- Consumes: the current example files without changing their workflow semantics.
- Produces: `config_examples/<workflow>/` as the only active example hierarchy and installed resource path.

- [ ] **Step 1: Change path-assertion tests to require the flattened locations and reject the old directory.**

Update the baseline and study-area packaging tests to assert
`config_examples/baseline_plot/baseline_plot.cfg`,
`config_examples/study_area/footprint.cfg`, and
`not (repository / "config_examples/visualization").exists()`.

- [ ] **Step 2: Run the focused tests and verify RED.**

Run: `python -m unittest discover -s tests -p 'test_baseline_plot.py' -v`

Run: `python -m unittest discover -s tests -p 'test_study_area_workflow.py' -v`

Expected: FAIL because examples and package data still use the old hierarchy.

- [ ] **Step 3: Move every example workflow, including untracked assets, and update package/documentation paths.**

Use mechanical directory moves so binary GeoTIFFs and user-owned untracked data are preserved. Update active README, engineering rules, cfg usage comments, and `pyproject.toml` data-file destinations/sources. Historical specs/plans remain historical records and are not rewritten.

- [ ] **Step 4: Run focused tests and path search.**

Run: `python -m unittest discover -s tests -p 'test_baseline_plot.py' -v`

Run: `python -m unittest discover -s tests -p 'test_study_area_workflow.py' -v`

Run: `rg -n "config_examples/visualization" README.md pyproject.toml docs/development config_examples src tests`

Expected: tests PASS; search returns no active references.

### Task 2: Extend and Validate the Shared Baseline CFG Model

**Files:**
- Modify: `src/geodesy_visualization/workflows/insar/baseline_plot_config.py`
- Modify: `tests/test_baseline_plot.py`

**Interfaces:**
- Consumes: `[project]`, `[defaults]`, `[case:name]` and the existing output derivation contract.
- Produces: immutable `BaselinePlotCase` fields for labels, font sizes/weight, tick policy, colors, grid, legend labels, and optional `matlab_output`.

- [ ] **Step 1: Add failing config tests for exact defaults, case overrides, and backward compatibility.**

Tests assert that a legacy Python-only case without `matlab_output` still loads, while the LT-style case resolves `matlab_output` and all configured publication fields.

- [ ] **Step 2: Add failing validation-table tests.**

Cover invalid positive sizes/intervals, rotation, `font_weight`, color, Boolean, date unit, date format, unsafe `matlab_output`, and unknown keys. Include all Review Focus grammar cases.

- [ ] **Step 3: Run config tests and verify RED.**

Run: `python tests/test_baseline_plot.py BaselinePlotConfigTests -v`

Expected: FAIL because the new keys and fields do not exist.

- [ ] **Step 4: Implement the minimal immutable config model and parsing helpers.**

Add exact fields to `BaselinePlotCase`; add focused parsers for positive floats, bounded finite rotation, colors, Boolean, enum values, and supported date-format grammar. Preserve `output` derivation and resolve optional `matlab_output` inside the project root.

- [ ] **Step 5: Run config tests and verify GREEN.**

Run: `python tests/test_baseline_plot.py BaselinePlotConfigTests -v`

Expected: PASS.

### Task 3: Reproduce the MATLAB Publication Style in Python

**Files:**
- Modify: `src/geodesy_visualization/workflows/insar/baseline_plot_core.py`
- Modify: `src/geodesy_visualization/workflows/insar/baseline_plot.py`
- Modify: `src/geodesy_visualization/backends/matplotlib.py`
- Modify: `tests/test_baseline_plot_core.py`
- Modify: `tests/test_baseline_plot.py`

**Interfaces:**
- Consumes: `BaselineNetwork` and the fully validated fields of `BaselinePlotCase`.
- Produces: `render_baseline_plot(...) -> Path` with white axes, boxed/two-sided ticks, configured grid/ticks/colors/text, right-side legend, and atomic PNG publication.

- [ ] **Step 1: Write failing renderer tests against real Matplotlib objects.**

Add `_build_baseline_plot(network: BaselineNetwork, **validated_style) -> tuple[Figure, Axes]` as the internal seam the tests exercise; `render_baseline_plot` remains the only exported publisher. Assert exact title/x/y text, all three font sizes, FreeSans family, font weight, colors, grid visibility, y ticks, date formatter/locator, rotation, top/right ticks, and outside-right legend labels.

- [ ] **Step 2: Write the missing-font regression test.**

Request a deliberately absent family and assert an actionable `ValueError` naming it; verify that no output replaces an existing destination.

- [ ] **Step 3: Run renderer tests and verify RED.**

Run: `python tests/test_baseline_plot_core.py BaselineNetworkRenderTests -v`

Expected: FAIL against the current hard-coded gray Matplotlib style and silent font fallback.

- [ ] **Step 4: Implement strict font selection and the configured MATLAB-reference renderer.**

Keep scientific graph code unchanged. Use `MonthLocator`/`YearLocator`/`DayLocator`, `DateFormatter`, `MultipleLocator`, configured labels/colors/sizes, white backgrounds, `tick_params(top=True, right=True, direction="in")`, major grid only, and an outside-right legend. Keep the 30-day x padding and existing y auto-padding plus extras.

- [ ] **Step 5: Pass every new case field through `baseline_plot.main`.**

Do not add a second Python entry point or positional input mode.

- [ ] **Step 6: Run renderer and CLI tests and verify GREEN.**

Run: `python -m unittest discover -s tests -p 'test_baseline_plot_core.py' -v`

Run: `python -m unittest discover -s tests -p 'test_baseline_plot.py' -v`

Expected: PASS.

### Task 4: Add the Runnable LT-1 Python Example

**Files:**
- Modify: `config_examples/baseline_plot/baseline_plot.cfg`
- Create: `config_examples/baseline_plot/data/shortbaseline_3`
- Create: `config_examples/baseline_plot/data/baseline_manifest.json`
- Modify: `tests/test_baseline_plot.py`

**Interfaces:**
- Consumes: the historical LT network values and the new shared CFG contract.
- Produces: a self-contained single-case example with reference `20231222`, pair count `3`, and separate Python/MATLAB output paths.

- [ ] **Step 1: Add a failing packaged-example test.**

Load the example through the public config/manifest/network readers and assert exact pairs `20231222-20230629`, `20231222-20230731`, `20231222-20231218` and baselines `-603.5297`, `-808.2997`, `-742.2232`.

- [ ] **Step 2: Run the example test and verify RED.**

Run: `python tests/test_baseline_plot.py BaselineExampleTests -v`

Expected: FAIL because the example data/manifest do not exist.

- [ ] **Step 3: Add the copied network, synthetic manifest, and fully commented CFG.**

The CFG documents both run commands, every exposed key, default behavior, input/output paths, completion criteria, and FreeSans verification.

- [ ] **Step 4: Run the example test and real Python CLI.**

Run: `python tests/test_baseline_plot.py BaselineExampleTests -v`

Run: `python -m geodesy_visualization.cli baseline_plot --config config_examples/baseline_plot/baseline_plot.cfg`

Expected: test PASS and a non-empty LT Python PNG at the configured comparison output; do not commit the generated PNG.

### Task 5: Add the Optional MATLAB CFG Adapter and Renderer

**Files:**
- Create: `config_examples/baseline_plot/matlab/read_baseline_plot_cfg.m`
- Create: `config_examples/baseline_plot/matlab/baseline_plot_from_cfg.m`
- Create: `tests/test_baseline_matlab_example.py`
- Modify: `README.md`

**Interfaces:**
- Consumes: `baseline_plot_from_cfg(cfgPath, caseName)` and the same manifest/network/style values as Python.
- Produces: the configured `matlab_output` PNG without importing or invoking MATLAB from Python.

- [ ] **Step 1: Write failing static-contract tests for the MATLAB example.**

Assert both `.m` files exist, the entry point accepts cfg/case, reads `matlab_output`, manifest and supported style keys, and contains no hard-coded LT data path.

- [ ] **Step 2: Run the MATLAB example test and verify RED.**

Run: `python -m unittest discover -s tests -p 'test_baseline_matlab_example.py' -v`

Expected: FAIL because the MATLAB adapter does not exist.

- [ ] **Step 3: Implement the minimal INI reader.**

Support blank lines, full-line `#`/`;` comments, `[section]`, one `key=value` per line, duplicate/invalid section and key errors, case selection identical to Python, and values containing `#RRGGBB` without treating inline `#` as a comment.

- [ ] **Step 4: Implement the MATLAB renderer.**

Read the manifest with `jsondecode`, resolve its relative network, solve signed node baselines over a connected graph, translate the supported date format, apply every shared field, and save only `matlab_output`. Restore any changed MATLAB root graphics defaults with `onCleanup`.

- [ ] **Step 5: Run static tests and a real licensed MATLAB smoke render.**

Run: `python -m unittest discover -s tests -p 'test_baseline_matlab_example.py' -v`

Run: `matlab -batch "addpath('config_examples/baseline_plot/matlab'); baseline_plot_from_cfg('config_examples/baseline_plot/baseline_plot.cfg','lt1')"`

Expected: tests PASS; MATLAB reports FreeSans and writes a non-empty configured PNG. If the sandbox blocks the license host, rerun the same command with the approved external MATLAB permission.

### Task 6: Document, Compare, and Verify the Complete Workflow

**Files:**
- Modify: `README.md`
- Modify: `fonts/README.md` if required for FreeSans installation guidance
- Modify: tests named above only when verification exposes a missed documented contract

**Interfaces:**
- Consumes: both renderers and the LT example.
- Produces: documented Python/MATLAB commands and evidence that both implement the same scientific/config contract.

- [ ] **Step 1: Document ownership, shared CFG behavior, optional MATLAB use, font installation, and output comparison.**

State that Python is canonical, MATLAB is optional, and other workflows may reuse the CFG-driven pattern without requiring a MATLAB duplicate or global theme.

- [ ] **Step 2: Compare generated artifacts.**

Verify both PNGs are non-empty; inspect them visually against the accepted Gansu FreeSans preview; confirm identical node dates, node baselines, edge count, labels, configured colors, ticks, and grid state. Record unavoidable engine layout differences rather than tuning hidden constants.

- [ ] **Step 3: Run the complete repository suite.**

Run: `python -m unittest discover -s tests -v`

Expected: all tests PASS.

- [ ] **Step 4: Run repository hygiene checks.**

Run: `git diff --check`

Run: `rg -n "config_examples/visualization" README.md pyproject.toml docs/development config_examples src tests`

Expected: no whitespace errors and no active obsolete example paths.

- [ ] **Step 5: Inspect the final worktree without committing.**

Run: `git status --short`

Expected: requested baseline/config-layout changes are distinguishable from preserved pre-existing user changes; generated PNGs are excluded or removed from the repository worktree.
