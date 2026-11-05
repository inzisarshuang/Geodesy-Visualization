# Method-Centric Visualization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finish the `src` package migration and publish reproducible figures under `FIGURES/PUBLICATION/<WORKFLOW>` with atomic replacement.

**Architecture:** Python code lives only in `src/geodesy_visualization`; installed assets are resolved with package-resource APIs rather than source-tree parent traversal. Workflow CFGs accept project/case/method context, derive publication defaults, and continue to permit explicit output paths.

**Tech Stack:** Python 3.10+, setuptools, importlib.resources, PyGMT, Matplotlib, Rasterio, pytest

**Spec:** `../Geodesy-2Analysis/docs/superpowers/specs/2026-11-04-method-centric-project-layout-design.md`

## Global Constraints

- Visualization consumes public Adapter APIs only.
- Publication output is atomically replaced after successful rendering.
- Fonts, CPTs, and CFG examples must work from an installed wheel.
- Do not commit Python caches or generated egg-info.
- Do not push until the new Visualization remote is explicitly configured.

## Review Focus

- Installed-wheel resource lookup must not depend on repository parents.
- Nested example CFGs and required small assets must be included in the wheel.
- Explicit output paths must override method-root defaults.
- A failed render must preserve the previous publication figure.
- Legacy import paths and executable entry points must not silently point at deleted source.

---

### Task 1: Complete the src-layout move

**Files:**
- Move/retain: `src/geodesy_visualization/**`
- Remove after parity check: tracked `geodesy_visualization/**`
- Modify: `pyproject.toml`
- Modify: `tests/test_architecture.py`
- Modify: `tests/test_docstrings.py`
- Modify: `.gitignore`

**Interfaces:**
- Retains: package name `geodesy_visualization`
- Retains: console scripts `geodesy-visualization` and `geodesy-visualization-insar-baseline`

- [ ] **Step 1:** Add failing architecture tests requiring imports to resolve from `src` and forbidding a second root package.
- [ ] **Step 2:** Run architecture/import tests and record failures caused by the incomplete move.
- [ ] **Step 3:** Verify moved Python files against their tracked predecessors, finish missing moves, and remove generated `egg-info`/cache artifacts from the candidate file set.
- [ ] **Step 4:** Update setuptools discovery and entry-point tests.
- [ ] **Step 5:** Run architecture, docstring, and CLI-help tests.
- [ ] **Step 6:** Commit as `refactor: finish visualization src layout`.

### Task 2: Package fonts, CPTs, and nested examples

**Files:**
- Create: `src/geodesy_visualization/resources.py`
- Modify: `pyproject.toml`
- Move/package: `fonts/**`, `cpt/**`, `config_examples/visualization/**`
- Create: `tests/test_packaged_resources.py`

**Interfaces:**
- Produces: `resource_path(group, name)` context manager or equivalent importlib-resources interface
- Produces: workflow-specific default CFG/CPT/font lookup independent of checkout location

- [ ] **Step 1:** Add failing source-tree and built-wheel tests for representative font, CPT, top-level baseline CFG, and nested deformation-map CFG.
- [ ] **Step 2:** Run the resource test and confirm current data-files rules omit nested assets/CPTs.
- [ ] **Step 3:** Implement package resources and replace `Path(__file__).parents[...]` resource discovery.
- [ ] **Step 4:** Build a wheel locally and run the installed-resource assertions in an isolated temporary target.
- [ ] **Step 5:** Commit as `build: package visualization resources`.

### Task 3: Method-root publication outputs

**Files:**
- Create: `src/geodesy_visualization/project_layout.py`
- Modify: `src/geodesy_visualization/io.py`
- Modify: workflow config/load functions under `src/geodesy_visualization/workflows/insar/`
- Modify: `config_examples/visualization/**.cfg`
- Create: `tests/test_project_layout.py`
- Modify: workflow tests

**Interfaces:**
- Produces: `VisualizationProjectLayout.bind(project_root, project, processing_root)`
- Produces default: `<processing_root>/FIGURES/PUBLICATION/<WORKFLOW>`
- Explicit workflow output remains authoritative

- [ ] **Step 1:** Add failing tests for default publication directories, containment, explicit overrides, and cfg-relative inputs.
- [ ] **Step 2:** Run focused config/workflow tests.
- [ ] **Step 3:** Implement layout-aware resolution and add bilingual CFG path-contract headers.
- [ ] **Step 4:** Run the focused tests.
- [ ] **Step 5:** Commit as `feat: add method-root publication defaults`.

### Task 4: Atomic output parity and legacy cleanup

**Files:**
- Modify: workflow render functions under `src/geodesy_visualization/workflows/insar/`
- Modify: backend output helpers as necessary
- Modify: `README.md`, `CONTRIBUTING.md`, and development docs
- Remove after parity: legacy `plot_defo_*` wrappers/data locations replaced by examples
- Modify: relevant workflow/backend tests

**Interfaces:**
- Retains: one validated atomic replace for every final figure
- Produces: dry-run output that prints resolved inputs and publication targets

- [ ] **Step 1:** Add failing tests that a renderer failure preserves an existing image and success replaces it.
- [ ] **Step 2:** Run affected workflow tests.
- [ ] **Step 3:** Route all final saves through the atomic output helper and finish documented legacy-path removal.
- [ ] **Step 4:** Run focused tests plus one representative visual inspection using the established plotting environment.
- [ ] **Step 5:** Run `compileall`, wheel build, and `git diff --check`.
- [ ] **Step 6:** Commit as `refactor: finalize publication workflows`.
