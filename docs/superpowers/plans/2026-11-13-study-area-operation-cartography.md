# Study-Area Operation Cartography Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a configuration-driven PyGMT operation framework and use it to reproduce the Jishishan LT-1 study-area and image-footprint figure with a compact publication layout.

**Architecture:** Ordered `figure.<pygmt_method>.<semantic_id>` CFG sections compile into a nested `FigurePlan`; a small executor dispatches registered direct or composite operations against one `pygmt.Figure`. The public CFG follows PyGMT names, while compatibility adapters isolate the installed PyGMT v0.10 API and composite footprint, fault, and inset preparation.

**Tech Stack:** Python 3.10+, `configparser`, PyGMT, GMT/GDAL command-line tools, NumPy, standard-library XML/JSON parsing, `unittest`.

**Spec:** `docs/superpowers/specs/2026-11-13-study-area-operation-cartography-design.md`

## Global Constraints

- Preserve the existing dirty changes in `src/geodesy_visualization/cli.py`, `src/geodesy_visualization/workflows/insar/deformation_map.py`, untracked example data, and CPT files.
- Do not move or reorganize any Gansu project directory or source dataset.
- `footprint` is canonical; reject `coverage` as a section alias.
- Use lowercase `snake_case` identifiers and full PyGMT parameter names, never GMT one-letter aliases.
- Resolve relative input paths from the CFG directory and reject unknown sections and keys.
- Keep current workflows and `PyGMTPlotter` public behavior compatible.
- Use the existing `envPlot` environment; do not install or upgrade PyGMT for this feature.
- Every new production module requires the repository's structured module docstring and every function requires a docstring.
- Large LT-1 inputs and generated images remain outside the Geodesy-Visualization Git repository.

## Review Focus

- A misspelled dotted section or deprecated `figure.plot.coverage.*` must fail with the offending section, not be ignored; Task 1 pins this.
- A missing or incompatible `source` reference must fail before PyGMT rendering; Tasks 1 and 3 pin this.
- PyGMT v0.10 lacks current `Figure.scalebar` and `Figure.directional_rose`; Task 3 pins the compatibility fallback without changing CFG names.
- KML `MultiGeometry`, empty coordinates, or malformed coordinate tokens must be deterministic and section-qualified; Task 2 pins this.
- A fault dataset with no configured kinematic field, `MultiLineString` geometry, or an unknown kinematic value must validate or use the documented fallback; Tasks 2 and 4 pin this.

---

### Task 1: Ordered figure-plan configuration

**Files:**
- Create: `src/geodesy_visualization/figure_ops/__init__.py`
- Create: `src/geodesy_visualization/figure_ops/model.py`
- Create: `src/geodesy_visualization/figure_ops/registry.py`
- Create: `src/geodesy_visualization/figure_ops/config.py`
- Create: `tests/test_figure_operation_config.py`

**Interfaces:**
- Produces: `FigureOperation(section: str, method: str, semantics: tuple[str, ...], options: Mapping[str, object], order: int)`.
- Produces: `FigurePlan(config_path: Path, project: Mapping[str, str], figure: Mapping[str, str], operations: tuple[FigureOperation, ...])`.
- Produces: `OperationSpec(pattern, required_keys, allowed_keys, path_keys, bool_keys, int_keys, float_keys, handler)` and `OperationRegistry.resolve(section: str) -> OperationSpec`.
- Produces: `load_figure_plan(config_file: str | Path, registry: OperationRegistry = DEFAULT_REGISTRY) -> FigurePlan`.

- [ ] **Step 1: Write failing parser and validation tests**

Add tests that assert section order is preserved; `figure.plot.footprint.reference` exposes method `plot` and semantics `("footprint", "reference")`; relative `grid`/`data` paths resolve from the CFG directory; typed booleans, integers, and floats normalize; duplicate sections fail; unknown keys fail; `figure.plot.coverage.reference` fails; and missing/unknown `source` identifiers fail before rendering.

- [ ] **Step 2: Run the Task 1 test to verify failure**

Run: `/home/yilun/miniconda3/envs/envPlot/bin/python -m unittest tests.test_figure_operation_config -v`  
Expected: FAIL because `geodesy_visualization.figure_ops` does not exist.

- [ ] **Step 3: Implement the immutable model, operation schemas, and ordered INI loader**

Use `ConfigParser(interpolation=None, strict=True)` without inline comment stripping; preserve section insertion order; validate lowercase dotted names; normalize only schema-declared values; and validate references after every section has been parsed so forward references are supported.

- [ ] **Step 4: Run the Task 1 test to verify it passes**

Run: `/home/yilun/miniconda3/envs/envPlot/bin/python -m unittest tests.test_figure_operation_config -v`  
Expected: PASS.

- [ ] **Step 5: Commit Task 1 files if they can be staged without pre-existing user changes**

```bash
git add src/geodesy_visualization/figure_ops tests/test_figure_operation_config.py docs/superpowers/specs/2026-11-13-study-area-operation-cartography-design.md docs/superpowers/plans/2026-11-13-study-area-operation-cartography.md
git commit -m "feat: add ordered PyGMT figure plans"
```

### Task 2: Footprint and fault input preparation

**Files:**
- Create: `src/geodesy_visualization/figure_ops/cartography_inputs.py`
- Create: `tests/test_cartography_inputs.py`
- Create: `tests/fixtures/study_area/reference_footprint.kml`
- Create: `tests/fixtures/study_area/slave_footprints.kml`
- Create: `tests/fixtures/study_area/faults.geojson`

**Interfaces:**
- Consumes: CFG-resolved `Path` values from Task 1.
- Produces: `parse_kml_footprints(path: str | Path) -> tuple[np.ndarray, ...]`, each array shaped `(n, 2)` and explicitly closed.
- Produces: `FaultFeature(coordinates: np.ndarray, kinematics: str)`.
- Produces: `read_fault_features(path: str | Path, kinematic_field: str) -> tuple[FaultFeature, ...]` using `ogr2ogr -f GeoJSON /vsistdout/` and standard-library JSON parsing.
- Produces: `classify_fault_kinematics(value: str) -> Literal["strike_slip", "reverse", "normal", "other"]` with strike-slip precedence over reverse and normal.

- [ ] **Step 1: Write failing KML and fault preparation tests**

Test one `Polygon`, multiple polygons inside `MultiGeometry`, automatic polygon closure, malformed/empty coordinate errors, `LineString` and `MultiLineString` GeoJSON flattening, missing `kinematic_field`, classification precedence for `left lateral reverse fault`, and `other` fallback.

- [ ] **Step 2: Run the Task 2 test to verify failure**

Run: `/home/yilun/miniconda3/envs/envPlot/bin/python -m unittest tests.test_cartography_inputs -v`  
Expected: FAIL because the parser functions do not exist.

- [ ] **Step 3: Implement XML footprint parsing and GDAL-CLI vector extraction**

Parse KML with namespace wildcards and never require the optional GDAL KML driver. Run `ogr2ogr` with argument lists, capture GeoJSON, validate the requested property, and accept only line geometries for faults.

- [ ] **Step 4: Run the Task 2 test to verify it passes**

Run: `/home/yilun/miniconda3/envs/envPlot/bin/python -m unittest tests.test_cartography_inputs -v`  
Expected: PASS.

- [ ] **Step 5: Commit Task 2 files**

```bash
git add src/geodesy_visualization/figure_ops/cartography_inputs.py tests/test_cartography_inputs.py tests/fixtures/study_area
git commit -m "feat: parse map footprints and faults"
```

### Task 3: Fluent operation executor and PyGMT compatibility adapters

**Files:**
- Create: `src/geodesy_visualization/figure_ops/executor.py`
- Create: `src/geodesy_visualization/figure_ops/direct_operations.py`
- Create: `tests/test_figure_operation_executor.py`

**Interfaces:**
- Consumes: `FigurePlan`, `FigureOperation`, and `OperationSpec.handler` from Task 1.
- Produces: `RenderContext(figure, config_path, project, figure_options, resources, legend_items, warnings)`.
- Produces: `FigureExecutor(plan: FigurePlan, figure_factory: Callable[[], object] | None = None)`.
- Produces: `FigureExecutor.apply(operation: FigureOperation) -> FigureExecutor` and `FigureExecutor.execute() -> FigureExecutor`.
- Produces: direct handlers with signature `render_<name>(context: RenderContext, operation: FigureOperation) -> None`.

- [ ] **Step 1: Write failing fake-Figure executor tests**

Use a fake Figure to assert ordered dispatch, fluent `apply` identity, shared region/projection state, resource publication for `figure.grdimage.dem`, missing-source failure before colorbar rendering, and savefig-last enforcement. Assert `figure.scalebar` and `figure.directional_rose` call the dedicated methods when present and fall back to `basemap(map_scale=...)`/`basemap(rose=...)` for a v0.10-like fake.

- [ ] **Step 2: Run the Task 3 test to verify failure**

Run: `/home/yilun/miniconda3/envs/envPlot/bin/python -m unittest tests.test_figure_operation_executor -v`  
Expected: FAIL because the executor does not exist.

- [ ] **Step 3: Implement the executor and direct adapters**

Create the PyGMT Figure lazily, dispatch through the registry handler name, return `self` from `apply`, keep version compatibility inside adapters, and convert current-style CFG parameters into the raw v0.10 arguments only at the adapter boundary.

- [ ] **Step 4: Run the Task 3 test to verify it passes**

Run: `/home/yilun/miniconda3/envs/envPlot/bin/python -m unittest tests.test_figure_operation_executor -v`  
Expected: PASS.

- [ ] **Step 5: Commit Task 3 files**

```bash
git add src/geodesy_visualization/figure_ops/executor.py src/geodesy_visualization/figure_ops/direct_operations.py tests/test_figure_operation_executor.py
git commit -m "feat: execute configured PyGMT operations"
```

### Task 4: Composite study-area operations

**Files:**
- Create: `src/geodesy_visualization/figure_ops/cartography_operations.py`
- Modify: `src/geodesy_visualization/figure_ops/registry.py`
- Modify: `tests/test_figure_operation_executor.py`

**Interfaces:**
- Consumes: `RenderContext`, `FigureOperation`, KML polygons, and fault features from Tasks 2 and 3.
- Produces: `render_footprint`, `render_faults`, `render_meca`, `render_globe_inset`, `render_regional_inset`, and `render_legend` handlers registered by section pattern.
- Publishes: automatic legend items from fault and footprint operations.

- [ ] **Step 1: Add failing composite-operation tests**

Assert every KML polygon produces one plot call; footprint labels contribute one legend entry per operation, not per polygon; kinematic faults use deterministic front/pen/fill styles; unknown kinematics use the fallback pen; meca receives the configured Aki strike/dip/rake values; inset context managers contain their coast and study-location calls; and automatic legend order follows operation order.

- [ ] **Step 2: Run the focused executor tests to verify failure**

Run: `/home/yilun/miniconda3/envs/envPlot/bin/python -m unittest tests.test_figure_operation_executor -v`  
Expected: FAIL on unimplemented composite handlers.

- [ ] **Step 3: Implement composite handlers and registry bindings**

Keep scientific preparation out of direct adapters. Preserve the legacy visual semantics for reverse, normal, strike-slip, reference footprint, slave footprints, focal mechanism, globe locator, Gansu-Qinghai locator, and explicit/automatic legend while accepting configurable PyGMT-style parameters.

- [ ] **Step 4: Run Task 2 and Task 4 tests**

Run: `/home/yilun/miniconda3/envs/envPlot/bin/python -m unittest tests.test_cartography_inputs tests.test_figure_operation_executor -v`  
Expected: PASS.

- [ ] **Step 5: Commit Task 4 files**

```bash
git add src/geodesy_visualization/figure_ops/registry.py src/geodesy_visualization/figure_ops/cartography_operations.py tests/test_figure_operation_executor.py
git commit -m "feat: add study-area cartography operations"
```

### Task 5: Study-area workflow, CLI, and distributable example

**Files:**
- Create: `src/geodesy_visualization/workflows/cartography/__init__.py`
- Create: `src/geodesy_visualization/workflows/cartography/study_area.py`
- Modify: `src/geodesy_visualization/cli.py`
- Create: `tests/test_study_area_workflow.py`
- Create: `config_examples/visualization/study_area/study_area.cfg`
- Create: `config_examples/visualization/study_area/data/reference_footprint.kml`
- Create: `config_examples/visualization/study_area/data/slave_footprints.kml`
- Create: `config_examples/visualization/study_area/data/faults.geojson`
- Modify: `pyproject.toml`

**Interfaces:**
- Consumes: `load_figure_plan` and `FigureExecutor`.
- Produces: `build_parser() -> argparse.ArgumentParser`, `load_plan(config_file: str) -> FigurePlan`, and `main(arguments: Sequence[str] | None = None) -> int`.
- Produces: unified CLI command `geodesy-visualization study-area --config <cfg> [--dry-run]`.

- [ ] **Step 1: Write failing workflow and CLI tests**

Assert the documented example loads, contains the expected operation sequence and resolved fixture paths, unified CLI dispatch remains lazy, `--dry-run` prints section order/output and creates no figure, and normal execution delegates once to `FigureExecutor`.

- [ ] **Step 2: Run the Task 5 test to verify failure**

Run: `/home/yilun/miniconda3/envs/envPlot/bin/python -m unittest tests.test_study_area_workflow -v`  
Expected: FAIL because the workflow and command do not exist.

- [ ] **Step 3: Implement the workflow and merge the CLI edit without discarding existing lazy-import changes**

Keep `study_area.py` limited to workflow orchestration. Add package-data entries for the CFG and small text fixtures; reference the existing tracked deformation-map DEM from the example rather than duplicating a large raster.

- [ ] **Step 4: Run workflow, architecture, and docstring tests**

Run: `/home/yilun/miniconda3/envs/envPlot/bin/python -m unittest tests.test_study_area_workflow tests.test_architecture tests.test_docstrings -v`  
Expected: PASS.

- [ ] **Step 5: Commit Task 5 files only if the shared `cli.py` diff has been reviewed and intentionally included**

```bash
git add src/geodesy_visualization/workflows/cartography src/geodesy_visualization/cli.py tests/test_study_area_workflow.py config_examples/visualization/study_area pyproject.toml
git commit -m "feat: add study-area visualization workflow"
```

### Task 6: Documentation, LT-1 configuration, and real render verification

**Files:**
- Modify: `README.md`
- Modify: `docs/development/style_cfg_contract.md`
- Create outside repository: `/mnt/beegfs/procesados/yiluntan/Gansu_Jishishan_LT1/config/4visualization/study_area_lt1.cfg`
- Generate outside repository: `/mnt/beegfs/procesados/yiluntan/Gansu_Jishishan_LT1/result_visual/study_area/refactored/jishishan_lt1.png`

**Interfaces:**
- Consumes: the completed `study-area` workflow and the legacy LT-1 DEM, fault shapefile, reference KML, and slave KML.
- Produces: bilingual usage and naming documentation plus one real project CFG and verification image.

- [ ] **Step 1: Add bilingual README and CFG naming-contract documentation**

Document the `figure.<pygmt_method>.<semantic_id>` rule, `footprint` terminology, execution order, PyGMT-native versus workflow keys, CLI command, publication layout, and extension examples for new footprints and events.

- [ ] **Step 2: Create the project CFG without moving source data**

Point to `data/dem.grd`, `faults_jishishan.shp`, `reference_image.kml`, and `slave_images.kml` under the legacy source folder; configure the legacy focal mechanism and `publication_sidecar` output under `result_visual/study_area/refactored/`.

- [ ] **Step 3: Run dry-run and real rendering in envPlot**

Run dry-run first, then render with writable GMT user/temp directories:

```bash
mkdir -p /tmp/geodesy-gmt-user /tmp/geodesy-gmt-tmp
GMT_USERDIR=/tmp/geodesy-gmt-user GMT_TMPDIR=/tmp/geodesy-gmt-tmp /home/yilun/miniconda3/envs/envPlot/bin/python -m geodesy_visualization.cli study-area --config /mnt/beegfs/procesados/yiluntan/Gansu_Jishishan_LT1/config/4visualization/study_area_lt1.cfg
```

Expected: one compact PNG containing DEM, three fault styles, red reference footprint, blue slave footprints, focal mechanism, scale bar, directional rose, elevation colorbar, globe locator, regional locator, and legend.

- [ ] **Step 4: Visually inspect the new PNG beside the legacy image**

Confirm scientific-content parity, readable labels, no clipped elements, correct red/blue footprint distinction, and no legacy-sized empty canvas. If a layout value changes, change only the CFG or documented layout preset unless a renderer defect is proven.

- [ ] **Step 5: Run proportionate final verification**

Run:

```bash
/home/yilun/miniconda3/envs/envPlot/bin/python -m compileall -q src/geodesy_visualization
/home/yilun/miniconda3/envs/envPlot/bin/python -m unittest discover -s tests -v
git diff --check
```

Expected: compilation succeeds, the full suite passes, and `git diff --check` prints nothing.

- [ ] **Step 6: Commit repository documentation if safe; do not commit generated LT-1 data or images to Geodesy-Visualization**

```bash
git add README.md docs/development/style_cfg_contract.md
git commit -m "docs: document operation-based study-area maps"
```

