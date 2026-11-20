# Visualization Workflow Completion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete the internal Figure/Panel/Layer migration for every PyGMT workflow while preserving compact workflow CFGs and unrestricted atomic reruns.

**Architecture:** Workflow loaders retain domain-specific configuration, compile typed FigurePlans, and delegate drawing to the shared executor. Panel scopes and workflow handlers extend the existing operation registry without putting scientific data preparation into the renderer.

**Tech Stack:** Python 3.10+, PyGMT 0.10, GMT, Rasterio, Pandas, NumPy, unittest

**Spec:** `../specs/2026-11-20-visualization-workflow-completion-design.md`

## Global Constraints

- Work only in `Geodesy-Visualization`; do not modify Gansu project files.
- Preserve existing workflow CLI names and existing example CFG keys.
- Use `envPlot` for rendering verification and writable `/tmp` GMT/cache roots.
- A valid rerun always replaces output atomically; no parameter-signature gate and no `--force` requirement.
- Keep DataAdapter and Analysis imports out of Visualization.
- Keep baseline_plot as its existing specialized dual backend.

## Review Focus

- Output outside `processing_root` must remain valid and atomically replaceable.
- A batch list with comments, relative CFG paths, and one failing job must still run later jobs and return failure summary.
- Subplot panel transitions must not leak region, projection, frame, or CPT state.
- Dry-run must not import PyGMT or create temporary outputs.
- Existing flat CFG examples must compile to the same scientific inputs, scales, units, and output names.

---

### Task 1: Common Figure, Panel, Layer, and atomic-output foundation

**Files:**
- Modify: `src/geodesy_visualization/figure_ops/model.py`
- Modify: `src/geodesy_visualization/figure_ops/config.py`
- Modify: `src/geodesy_visualization/figure_ops/executor.py`
- Modify: `src/geodesy_visualization/figure_ops/direct_operations.py`
- Modify: `tests/test_figure_operation_config.py`
- Modify: `tests/test_figure_operation_executor.py`

**Interfaces:**
- Produces: `PanelPlan(identifier, region, projection, layers)`
- Produces: `LayerOperation` with compatibility alias `FigureOperation`
- Produces: `FigureExecutor.execute_plan(plan) -> FigureExecutor`
- Produces: atomic `savefig` behavior for any explicit output path

- [ ] Add failing tests for panel scopes, resource isolation, output paths outside `processing_root`, and failed-save rollback.
- [ ] Run the two figure-operation test modules and confirm the new assertions fail.
- [ ] Implement the typed model, executor panel scope, and atomic save adapter; remove output containment enforcement.
- [ ] Run the focused tests and confirm they pass.
- [ ] Commit as `refactor: add shared panel and layer execution`.

### Task 2: Re-runnable single-CFG workflow interface

**Files:**
- Modify: `src/geodesy_visualization/cli.py`
- Modify: `README.md`

**Interfaces:**
- CLI: every workflow accepts one required `--config`
- Existing outputs may be safely replaced after a successful render

- [ ] Keep the installed CLI lazy and require one explicit cfg.
- [ ] Verify repeated execution does not require a run identifier or force flag.
- [ ] Document atomic replacement and workflow-owned cfg parameters.

### Task 3: Deformation-map plan compiler and layer migration

**Files:**
- Create: `src/geodesy_visualization/workflows/insar/deformation_map_plan.py`
- Create: `src/geodesy_visualization/figure_ops/deformation_layers.py`
- Modify: `src/geodesy_visualization/workflows/insar/deformation_map.py`
- Modify: `tests/test_deformation_map_workflow.py`
- Modify: `config_examples/deformation_map/deformation_map.cfg`

**Interfaces:**
- Produces: `compile_deformation_maps(cfg) -> tuple[FigurePlan, ...]`
- Produces handlers for prepared raster/scatter, target region, scale, rose, and map colorbar layers

- [ ] Add failing compiler tests asserting SBAS/PSI plan count, layer order, paths, scales, CPTs, units, and outputs from the existing example.
- [ ] Run the workflow test and confirm it still calls legacy monolithic rendering.
- [ ] Implement plan compilation and focused layer handlers; retain scientific grid preparation in the workflow.
- [ ] Replace monolithic drawing with executor dispatch and atomic output.
- [ ] Run deformation-map and figure-operation tests.
- [ ] Commit as `refactor: compose deformation maps from layers`.

### Task 4: Deformation-profile map and Cartesian-panel migration

**Files:**
- Create: `src/geodesy_visualization/workflows/insar/deformation_profile_plan.py`
- Create: `src/geodesy_visualization/figure_ops/profile_layers.py`
- Modify: `src/geodesy_visualization/workflows/insar/deformation_profile.py`
- Modify: `tests/test_deformation_profile_workflow.py`
- Modify: `config_examples/deformation_profile/deformation_profile.cfg`

**Interfaces:**
- Produces: `compile_profile_figures(cfg, tracks, profiles) -> tuple[FigurePlan, ...]`
- Produces handlers for track, marker, profile line/scatter, Cartesian frame, and legend layers

- [ ] Add failing tests for dataset maps, track order, marker options, profile panels, padding, styles, and all output paths.
- [ ] Run the workflow test and confirm the compiler is absent.
- [ ] Implement map/profile plan compilation while leaving sampling and table export in preparation code.
- [ ] Replace direct drawing with executor dispatch.
- [ ] Run profile, map, and operation tests.
- [ ] Commit as `refactor: compose deformation profiles from layers`.

### Task 5: Spatial time-series subplot migration

**Files:**
- Create: `src/geodesy_visualization/workflows/insar/timeseries_map_plan.py`
- Create: `src/geodesy_visualization/figure_ops/timeseries_layers.py`
- Modify: `src/geodesy_visualization/workflows/insar/timeseries_map.py`
- Modify: `tests/test_timeseries_workflows.py`
- Modify: `config_examples/timeseries_map/timeseries_map.cfg`

**Interfaces:**
- Produces: `compile_timeseries_map(cfg, epochs) -> FigurePlan`
- Produces subplot/panel handlers for epoch raster/scatter, titles, numbers, coordinate frames, shared CPT, and colorbar

- [ ] Add failing tests for panel count/order, coordinate modes, font scaling, shared CPT, colorbar geometry, and explicit epoch range.
- [ ] Run time-series tests and confirm no panel plan exists.
- [ ] Implement compiler and panel-scoped handlers with no state leakage.
- [ ] Replace direct subplot rendering with executor dispatch.
- [ ] Run time-series and figure-operation tests.
- [ ] Commit as `refactor: compose time-series maps from panels`.

### Task 6: Auxiliary time-series Cartesian-layer migration

**Files:**
- Create: `src/geodesy_visualization/workflows/insar/timeseries_aux_plan.py`
- Modify: `src/geodesy_visualization/figure_ops/timeseries_layers.py`
- Modify: `src/geodesy_visualization/workflows/insar/timeseries_aux.py`
- Modify: `tests/test_timeseries_workflows.py`
- Modify: `config_examples/timeseries_aux/timeseries_aux.cfg`

**Interfaces:**
- Produces: `compile_aux_timeseries(cfg, series) -> FigurePlan`
- Produces handlers for deformation, fit, precipitation, temperature, multi-axis frame, and legend layers

- [ ] Add failing tests for series order, three Y ranges, dual time frames, styles, legend labels, and output path.
- [ ] Run focused tests and confirm the compiler is absent.
- [ ] Implement the compiler and reuse registered Cartesian handlers.
- [ ] Replace monolithic render calls with executor dispatch.
- [ ] Run all time-series and operation tests.
- [ ] Commit as `refactor: compose auxiliary time series from layers`.

### Task 7: Compatibility cleanup, documentation, and full verification

**Files:**
- Modify: `README.md`
- Modify: `docs/development/style_cfg_contract.md`
- Modify: `docs/development/python_rules.md`
- Modify: `lib/pygmt_geo.py`
- Modify: `lib/pygmt_io.py`
- Modify: `lib/pygmt_visual.py`
- Modify: `tests/test_architecture.py`
- Modify: `tests/test_environment_boundary.py`
- Modify: `tests/test_docstrings.py`

**Interfaces:**
- Documents routine CFG compilation versus advanced direct operations
- Enforces no `sys.path`, DataAdapter, or Analysis production dependency

- [ ] Add failing architecture assertions that every PyGMT workflow compiles plans and no production workflow imports the compatibility plotter.
- [ ] Remove obsolete duplicated rendering helpers and update compatibility/doc ownership maps.
- [ ] Verify all example CFGs with `--dry-run`.
- [ ] Run the complete unittest suite in `envPlot` with writable GMT and Matplotlib caches.
- [ ] Run `git diff --check` and installed CLI help.
- [ ] Commit as `docs: complete visualization workflow migration`.
