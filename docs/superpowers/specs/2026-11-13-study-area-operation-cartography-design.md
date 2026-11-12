# Study-Area Operation Cartography Design

**Date:** 2026-11-13  
**Repository:** Geodesy-Visualization  
**First production case:** Gansu Jishishan LT-1 study-area and image-footprint map

## 1. Purpose

The Jishishan LT-1 figure is the first production case for a reusable PyGMT
cartography framework. The implementation must reproduce all scientific
content from the legacy figure while replacing its hard-coded script and
oversized canvas with a configuration-driven, publication-ready layout.

The public model follows PyGMT's `Figure` vocabulary. A CFG describes an
ordered sequence of figure operations; the application validates that
sequence, prepares the data, executes it against one `pygmt.Figure`, and
saves the result.

## 2. Design goals

- Make the CFG read like a serialized sequence of `pygmt.Figure` calls.
- Reuse PyGMT public method and parameter names whenever semantics match.
- Keep project paths and scientific concepts explicit and readable.
- Support repeated operations such as multiple image footprints or events.
- Support nested operations for insets and, later, subplots.
- Preserve strict configuration validation and CFG-relative paths.
- Preserve a Python fluent interface for programmatic use without creating a
  monolithic builder class.
- Keep existing visualization workflows compatible during incremental
  migration.

## 3. Non-goals for the first implementation

- Do not migrate all existing workflows at once.
- Do not expose internal registry, context, or operation classes to CFG users.
- Do not build a backend-neutral plotting language; this repository is
  intentionally PyGMT-oriented.
- Do not reproduce the legacy figure's excessive whitespace pixel for pixel.
- Do not move or reorganize the Gansu project data during framework
  implementation.
- Do not place study-area behavior inside `deformation_map.py`.

## 4. Execution model

```text
CFG
  -> Config Parser and Validator
  -> nested Figure Operation Plan
  -> Operation Registry
  -> Figure Executor
  -> pygmt.Figure
  -> PNG/PDF
```

This is a drawing composition model, not a data-processing chain. Data
validation and preparation occur before rendering. During rendering, ordered
operations add content to the same Figure object.

The executor is fluent for Python callers:

```python
executor.apply(operation_a).apply(operation_b).save(output)
```

`apply` returns the executor, but each operation lives in a focused module.
The executor must not acquire one method for every future scientific feature.

## 5. Configuration naming contract

### 5.1 Section names

Figure operations use:

```text
figure.<pygmt_method>.<optional_scientific_semantics>.<optional_instance_id>
```

Examples:

```ini
[figure.basemap]
[figure.grdimage.dem]
[figure.plot.faults]
[figure.plot.footprint.reference]
[figure.plot.footprint.slaves]
[figure.meca.mainshock]
[figure.scalebar]
[figure.directional_rose]
[figure.colorbar.dem]
[figure.inset.globe]
[figure.legend]
[figure.savefig]
```

`footprint` is the canonical scientific term for satellite or product spatial
coverage. `coverage` is not accepted as an alias.

All identifiers use lowercase `snake_case`. Repeated objects use semantic and
instance suffixes, such as `figure.plot.footprint.saocom`.

### 5.2 Key names

Use PyGMT's complete public parameter names when the meaning is one-to-one,
including `region`, `projection`, `frame`, `grid`, `cmap`, `shading`, `data`,
`pen`, `fill`, `label`, `position`, `width`, `height`, `length`, `unit`,
`box`, and `transparency`.

Do not expose GMT single-letter aliases such as `R`, `J`, `B`, `W`, or `G`.

The project defines only a small stable set of additional keys:

- `enabled`: enable or disable an optional operation;
- `source`: reference another operation's prepared resource;
- `layout`: choose a named page layout;
- `processing_root`: resolve the project output policy;
- `kinematic_field`: classify fault styles;
- `highlight` and `regions`: configure location insets.

Unknown sections and keys are rejected. Relative file paths are resolved
against the CFG directory.

### 5.3 Ordering

The order of figure operation sections is the default rendering order. Moving
a section changes its stacking order. Structural sections such as `project`
and `figure` are not render operations.

Nested prefixes define a scope. For example, operations nested under an inset
execute inside the corresponding PyGMT inset context. The first production
CFG may use high-level globe and regional inset operations; the plan remains
capable of later expanding them into nested child operations.

## 6. Proposed implementation structure

```text
src/geodesy_visualization/
├── backends/
│   └── pygmt.py
├── figure_ops/
│   ├── model.py
│   ├── config.py
│   ├── registry.py
│   ├── executor.py
│   ├── raster.py
│   ├── vector.py
│   ├── seismic.py
│   └── embellishment.py
└── workflows/
    └── cartography/
        └── study_area.py
```

- `model.py` defines immutable operation and plan records.
- `config.py` parses ordered CFG sections into a validated operation plan.
- `registry.py` maps section patterns to schemas and render functions.
- `executor.py` owns one `pygmt.Figure`, shared render context, and fluent
  `apply`/`execute` behavior.
- focused operation modules implement direct and composite PyGMT operations.
- `study_area.py` applies the project output policy and exposes CLI/dry-run.

The exact number of operation modules may be reduced if a file would contain
only trivial code. Responsibility boundaries must remain intact.

## 7. Operation behavior

An operation has four phases:

1. parse its section name and typed parameters;
2. validate required values and referenced resources;
3. prepare scientific data when direct PyGMT input is insufficient;
4. render against the shared Figure and context.

Direct operations adapt PyGMT methods such as `basemap`, `grdimage`, `meca`,
`scalebar`, `directional_rose`, `colorbar`, `legend`, and `savefig`.

Composite operations retain a PyGMT-oriented section name but may perform
multiple internal calls:

- `figure.plot.faults` reads a shapefile, classifies `kinematic_field`, and
  issues one or more `Figure.plot` calls;
- `figure.plot.footprint.*` parses KML `Polygon` and `MultiGeometry` content
  independently of optional GDAL KML driver availability, then calls
  `Figure.plot` for every polygon;
- `figure.inset.globe` and `figure.inset.regional` enter an inset context and
  combine coast, boundary, and location-marker calls.

The operation registry is extensible. Adding a new operation must not require
editing the central executor.

## 8. Shared render context

The executor context stores only resources that later operations must
reference, such as:

- the active Figure;
- current region and projection;
- prepared raster/CPT resources keyed by operation identifier;
- legend contributions;
- warnings and output metadata.

For example:

```ini
[figure.colorbar.dem]
source = figure.grdimage.dem
```

The colorbar resolves the CPT prepared by the named raster operation. Missing
or incompatible references fail before rendering where possible.

## 9. LT-1 production CFG

The first case follows this shape:

```ini
[project]
processing_root = /path/to/Gansu_Jishishan_LT1

[figure]
layout = publication_sidecar

[figure.basemap]
region = 102, 103.6, 35.2, 36.5
projection = M8i
title = Study Area Jishishan

[figure.grdimage.dem]
grid = data/dem.grd
cmap = gray
shading = +d

[figure.plot.faults]
data = data/faults_jishishan.shp
kinematic_field = Fea_En
pen = 1.5p,black

[figure.plot.footprint.reference]
data = data/reference_image.kml
pen = 4p,red
label = LT-1 reference image

[figure.plot.footprint.slaves]
data = data/slave_images.kml
pen = 4p,blue
label = LT-1 slave images

[figure.meca.mainshock]
longitude = 102.79
latitude = 35.758
strike = 353
dip = 78
rake = -124
magnitude = 5.9
depth_km = 18.281
scale = 0.6c

[figure.scalebar]
position = BR
length = 50k

[figure.directional_rose]
position = MR
width = 2c

[figure.colorbar.dem]
source = figure.grdimage.dem
position = BC
label = Elevation
unit = m

[figure.inset.globe]
position = TR
width = 4c
highlight = CN

[figure.inset.regional]
position = MR
width = 6c
regions = CN.62, CN.63

[figure.legend]
position = BC

[figure.savefig]
fname = FIGURES/PUBLICATION/STUDY_AREA/jishishan_lt1.png
dpi = 300
crop = yes
```

The delivered example documents every supported key. Users normally copy the
example and edit paths, region, labels, and optional element parameters.

## 10. Layout

The selected default is `publication_sidecar`:

- main map on the left and occupying most of the figure;
- globe locator, Gansu-Qinghai locator, directional rose, scale bar, and
  colorbar in a coordinated right-side information column;
- legend across the bottom;
- all legacy scientific elements retained;
- no excessive external whitespace.

Layout controls geometry only. Scientific data remains in the corresponding
operation sections.

## 11. Error handling and dry run

The workflow fails with a section-qualified error when:

- a section or key is unknown;
- a required file is missing or unreadable;
- an operation identifier is duplicated;
- a source reference is missing or incompatible;
- region, projection, focal-mechanism, or layout values are invalid;
- a shapefile lacks its configured kinematic field;
- an output path violates project policy.

`--dry-run` parses paths, operations, ordering, references, and output without
creating a PyGMT Figure or output file.

## 12. Compatibility and migration

- Existing commands keep their current public behavior.
- Current experimental coverage behavior in `deformation_map.py` is not
  expanded during this feature and is not overwritten.
- `backends/pygmt.py` may gain reusable primitives while retaining existing
  callers.
- PyGMT version differences are isolated in operation adapters so published
  CFG identifiers remain stable.
- Later workflow migrations translate their current drawing steps into
  operation plans one workflow at a time.

Suggested later order:

1. deformation map;
2. deformation profile map panel;
3. time-series geographic map panel;
4. baseline and Cartesian panels;
5. time-series and auxiliary Cartesian panels.

## 13. Repository and project scope

The repository receives the operation framework, `study-area` CLI, generic
example CFG, bilingual README updates, and small test fixtures where needed.

The Gansu project receives a project-specific LT-1 CFG only after repository
implementation is verified. Large region-specific datasets and generated
products remain outside the code repository. No Gansu directories are moved
as part of this feature.

## 14. Verification

- operation-plan ordering and nested-prefix tests;
- strict section/key and typed-value validation tests;
- path and source-reference resolution tests;
- KML `Polygon` and `MultiGeometry` parsing tests;
- fault-field validation and deterministic classification tests;
- dry-run CLI test;
- executor dispatch tests using a fake Figure;
- Python compilation and the full repository unit-test suite;
- one real render in `envPlot` using existing LT-1 data;
- visual comparison with the legacy figure for scientific-content parity and
  compact layout.

The real render is a verification product only; it does not reorganize the
Gansu project.
