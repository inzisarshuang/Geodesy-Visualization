# Visualization Workflow Completion Design

**Date:** 2026-11-20
**Repository:** Geodesy-Visualization
**Status:** Approved direction consolidated from the existing Figure-operation design

## Intent

Complete the repository-wide visualization refactor without making users learn
the internal plotting language for routine workflows. All PyGMT workflows use
one internal `Figure -> Panel -> Layer -> variant` composition model. Study-area
CFGs may expose ordered `figure.*` operations directly; deformation and time
series workflows keep their purpose-specific CFG vocabulary and compile it into
the same internal model.

## Goals

- Migrate deformation map, deformation profile, spatial time-series map, and
  auxiliary time-series rendering onto shared Figure/Panel/Layer execution.
- Keep existing public CLI workflow names and current example CFG keys working.
- Make every output path explicit and user-overridable; do not require outputs
  to remain under `processing_root`.
- Allow every valid rerun to replace the previous figure atomically. Parameter
  changes never block execution.
- Add simple list-controlled batch execution: one CFG path per line, resolved
  relative to the list file, continuing through independent failures and
  reporting a final summary.
- Preserve workflow-specific scientific preparation and parameter defaults.
- Remove duplicated PyGMT drawing sequences once their workflow is migrated.

## Non-goals

- Do not move data conversion, reprojection, scientific unit conversion, or
  canonical HDF5 reading back into Visualization.
- Do not force the Matplotlib/MATLAB baseline network workflow into the PyGMT
  operation registry; it remains a specialized dual-backend figure.
- Do not force users to add `run_id`, `main`, or `test` directory levels.
- Do not modify Gansu project CFGs or products in this repository-only phase.
- Do not reject a rerun because a prior figure or different prior parameters
  exist.

## Public Configuration Strategy

Advanced cartography continues to support ordered sections such as:

```ini
[figure.grdimage.dem]
[figure.plot.footprint.reference]
[figure.colorbar.dem]
```

Routine workflow CFGs remain compact and domain-oriented. Their loaders produce
typed workflow settings, then a compiler creates internal Figure, Panel, and
Layer records. This preserves existing examples and avoids exposing registry or
context details to normal users.

Unknown keys remain errors because they indicate spelling mistakes. Valid
parameter changes, alternate paths, different output names, and repeated runs
are always accepted.

## Internal Model

- `FigurePlan`: one output figure plus ordered panels and figure-level layers.
- `PanelPlan`: one map, Cartesian axis, or subplot panel with region/projection
  and ordered layers.
- `LayerOperation`: one registered drawing action and a variant identifier.
- `RenderContext`: active PyGMT Figure, current panel, prepared resources,
  legends, CPTs, and warnings.

Existing `FigureOperation` remains a compatibility name during migration and
maps to `LayerOperation`. The executor supports a single panel, `subplot`, and
multiple independent figures compiled by one workflow.

## Workflow Mapping

### Deformation map

Each configured dataset compiles to one figure: basemap raster, deformation
grid/scatter, optional target regions, colorbar, scale, rose, and save layer.
Multiple datasets are a workflow batch of independent FigurePlans.

### Deformation profile

Each dataset map compiles as above with track and marker layers. Profile output
uses one Cartesian panel per configured track and registered line/scatter/
legend layers. Scientific profile sampling remains in the workflow preparation
module, not in layer handlers.

### Spatial time-series map

One FigurePlan owns a subplot specification. Every epoch is a PanelPlan with
the same map-layer variants and panel-specific title/number/coordinate frame.
The shared CPT and final colorbar remain figure-level resources.

### Auxiliary time series

One Cartesian PanelPlan contains deformation points, fitted line, precipitation
bars, temperature line, primary/secondary time axes, legends, and save layer.
The existing three Y-axis scientific meaning is preserved.

## Configuration Interface

All repository workflows accept one explicit cfg:

```bash
geodesy-visualization <workflow> --config workflow.cfg
```

The cfg remains the visible parameter record. Visualization does not impose a
second list-control interface; external processing scripts may choose their own
batch organization without changing the plotting workflow contract.

## Output And Rerun Behavior

Every figure is first saved to a unique sibling temporary file and validated as
non-empty. Success atomically replaces the requested output. Failure removes
the temporary file and leaves the previous output unchanged. Existing output
and changed parameters never require `--force` and never produce a conflict.

`--dry-run` validates configuration and input availability, prints resolved
figures/panels/layers and output paths, but does not create PyGMT figures.

## Compatibility And Cleanup

- Keep legacy flat workflow CFG keys as the public compatibility contract.
- Keep `lib/pygmt_io.py`, `lib/pygmt_visual.py`, and `lib/pygmt_geo.py` only as
  installed-package re-exports; they must not modify `sys.path`.
- Keep deprecated `add_tifs` only through this compatibility cycle, with no
  production caller; removal is a separate announced breaking change.
- Update README and examples to describe the internal common architecture and
  the workflow-specific user interfaces.

## Verification

- Unit tests verify plan compilation without importing PyGMT.
- Executor tests use fake figures for layer order, panel scope, resources, and
  output replacement.
- Existing workflow tests pin configuration compatibility and scientific data
  preparation.
- Each migrated workflow has a dry-run contract test and one focused rendering
  test in `envPlot`.
- The complete repository suite and installed CLI help must pass before commit.
