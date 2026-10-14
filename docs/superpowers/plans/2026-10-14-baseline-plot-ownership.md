# Baseline Plot Ownership Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `Geodesy-Visualization` the sole owner of InSAR baseline plotting and leave `Geodesy-Analysis` responsible only for baseline calculation and network publication.

**Architecture:** Analysis continues to publish schema-1 `baseline_manifest.json` plus its source-neutral four-column network table. Visualization validates that boundary, resolves the network beside the manifest, computes only the display coordinates needed by the figure, and atomically publishes the PNG; neither Python package imports the other.

**Tech Stack:** Python 3.10+, standard-library `argparse`/`configparser`/`dataclasses`/`json`, NumPy, Matplotlib, `unittest`, envPlot, envInSAR, Git worktrees.

**Spec:** `docs/superpowers/specs/2026-10-14-baseline-plot-ownership-design.md`

## Global Constraints

- Work in dedicated branches and worktrees for both repositories; do not edit the two main checkouts during implementation.
- Preserve `/mnt/beegfs/procesados/yiluntan/Geodesy-Visualization/cpt/gamma_*` and `cpt/seismic_continuous.*`; they are untracked user-owned files.
- Use test-first development for every production-code behavior change and observe the intended failure before implementation.
- Keep `baseline_manifest.json` at schema version 1 and tolerate unrelated extra fields from already published results.
- Do not retain the Analysis plot command, a positional-file compatibility CLI, duplicate production plotters, or a Python dependency between the repositories.
- Resolve cfg-relative paths from the configured project root, reject traversal, and publish the PNG atomically.
- Do not rerun GAMMA during real validation; reuse the existing Jishishan Analysis products.
- New Visualization production modules must follow `AGENTS.md` structured module and function docstring rules.

## Review Focus

- A manifest whose `network_path` is absolute or traverses with `..` must fail before the network is opened; Task 1 tests both forms.
- A network with duplicate, reversed, self, malformed-date, non-finite, or pair-count-mismatched rows must fail explicitly; Task 1 tests each input class.
- A plotting exception must preserve an existing destination and remove the temporary sibling; Task 1 tests failure publication.
- An old Analysis manifest containing `plot_path` and `warnings` must remain skippable even if the old PNG is absent; Task 3 pins this restart behavior.
- Configuration with multiple cases, an unknown key, duplicate key, unsafe case name, or output outside the project must fail before plotting; Task 2 tests these boundaries.

---

### Task 1: Build the Visualization manifest consumer and renderer

**Files:**
- Create: `geodesy_visualization/workflows/insar/baseline_network.py`
- Create: `tests/test_baseline_network_workflow.py`

**Interfaces:**
- Consumes: schema-1 Analysis `baseline_manifest.json`; referenced rows `master slave perpendicular_baseline_m temporal_baseline_days`; `geodesy_visualization.io.atomic_output_path`; `geodesy_visualization.backends.matplotlib.configure_plot_font`.
- Produces: immutable `BaselineManifest`, `BaselinePair`, and `BaselineNetwork` values; `read_baseline_manifest(path: Path, *, project_root: Path) -> BaselineManifest`; `read_baseline_network(manifest: BaselineManifest) -> BaselineNetwork`; `plot_baseline_network(network: BaselineNetwork, output: Path, *, title: str, dpi: int, figsize: tuple[float, float], y_top_extra: float, y_bottom_extra: float, font_family: str) -> Path`.

- [ ] **Step 1: Write failing manifest and network contract tests**

Add tests that create a complete manifest and three connected rows, then assert preserved pair order, the manifest reference date, solved signed perpendicular baselines and exact pair count. Add separate assertions for wrong schema/status, unsafe absolute/traversing network paths, missing/empty network, malformed dates, self/duplicate/reversed pairs, non-finite baseline values, absent reference date and pair-count mismatch.

- [ ] **Step 2: Run the new contract tests and verify RED**

Run:

```bash
/home/yilun/miniconda3/envs/envPlot/bin/python -m unittest tests.test_baseline_network_workflow -v
```

Expected: import failure because `geodesy_visualization.workflows.insar.baseline_network` does not exist.

- [ ] **Step 3: Implement the minimal manifest and network consumer**

Use strict `YYYYMMDD` parsing, finite floating-point checks and an undirected-pair identity set. Resolve the manifest and network beneath `project_root`, additionally require the network to remain inside the manifest directory, and solve node perpendicular baselines from the declared reference date without importing Analysis.

- [ ] **Step 4: Run the contract tests and verify GREEN**

Run the Step 2 command. Expected: all manifest and network tests pass without importing Matplotlib.

- [ ] **Step 5: Write failing renderer publication tests**

Assert a two-node network produces a non-empty PNG and returns its resolved path. Patch the final figure write to raise after a previous destination is created, then assert the previous bytes remain and no `.baseline_network.*.png` temporary sibling remains.

- [ ] **Step 6: Run renderer tests and verify RED**

Run the Step 2 command. Expected: failure because `plot_baseline_network` is missing.

- [ ] **Step 7: Implement the Matplotlib renderer**

Move the single canonical visual composition from Analysis, use the bundled font configurator, preserve node/pair/master styling and axis semantics, save through `atomic_output_path`, and always close the figure in `finally`.

- [ ] **Step 8: Run Task 1 tests and the Visualization suite**

Run:

```bash
/home/yilun/miniconda3/envs/envPlot/bin/python -m unittest tests.test_baseline_network_workflow -v
/home/yilun/miniconda3/envs/envPlot/bin/python -m unittest discover -s tests -v
```

Expected: both commands pass.

- [ ] **Step 9: Commit Task 1 in Geodesy-Visualization**

```bash
git add geodesy_visualization/workflows/insar/baseline_network.py tests/test_baseline_network_workflow.py
git commit -m "Add source-neutral baseline network visualization"
```

### Task 2: Expose the Visualization CFG and installed command

**Files:**
- Create: `geodesy_visualization/workflows/insar/baseline_config.py`
- Create: `geodesy_visualization/workflows/insar/baseline_cli.py`
- Create: `tests/test_baseline_cli.py`
- Create: `config_examples/baseline_plot.cfg`
- Modify: `pyproject.toml`
- Modify: `README.md`

**Interfaces:**
- Consumes: Task 1 `read_baseline_manifest`, `read_baseline_network`, and `plot_baseline_network`.
- Produces: `BaselinePlotCase`; `load_baseline_plot_config(path: Path) -> tuple[BaselinePlotCase, ...]`; `select_baseline_plot_case(cases, name) -> BaselinePlotCase`; `main(arguments: Sequence[str] | None = None) -> int`; installed command `geodesy-visualization-insar-baseline`.

- [ ] **Step 1: Write failing configuration tests**

Test one and multiple `[case:name]` sections, defaults overridden by a case, path resolution from `[project] root`, and exact parsed style values. Test duplicate/unknown keys, unsupported sections, unsafe case names, missing manifest/output, non-positive DPI/figsize, negative margins, an output outside the project and omitted `--case` with multiple cases.

- [ ] **Step 2: Run configuration tests and verify RED**

Run:

```bash
/home/yilun/miniconda3/envs/envPlot/bin/python -m unittest tests.test_baseline_cli -v
```

Expected: import failure because `baseline_config` and `baseline_cli` do not exist.

- [ ] **Step 3: Implement strict case configuration**

Use `configparser.ConfigParser(interpolation=None, strict=True)`, require `[project] root`, allow only `[defaults]` and `[case:name]`, and produce fully resolved immutable cases. Keep Matplotlib imports outside configuration loading.

- [ ] **Step 4: Run configuration tests and verify GREEN**

Run the Step 2 command. Expected: configuration tests pass.

- [ ] **Step 5: Write failing CLI and packaging tests**

Assert `--config` is required, `--case` selects exactly one case, a successful call publishes through Task 1 and prints the final path, validation errors return `2`, and no GAMMA executable is invoked. Assert `pyproject.toml` exposes only `geodesy-visualization-insar-baseline` for this workflow and that the example cfg documents purpose, absolute command usage, outputs, every parameter and completion judgment.

- [ ] **Step 6: Run CLI tests and verify RED**

Run the Step 2 command. Expected: failures for missing CLI behavior and packaging metadata.

- [ ] **Step 7: Implement the CLI, package entry and documentation**

Keep the CLI thin: load/select one case, read the manifest/network, call the renderer and map expected input/plot exceptions to exit code `2`. Add `[project.scripts]`, package the cfg example, and add a numbered bilingual baseline-network section to the Visualization README.

- [ ] **Step 8: Run Task 2 tests and the Visualization suite**

Run:

```bash
/home/yilun/miniconda3/envs/envPlot/bin/python -m unittest tests.test_baseline_cli tests.test_baseline_network_workflow -v
/home/yilun/miniconda3/envs/envPlot/bin/python -m unittest discover -s tests -v
git diff --check
```

Expected: all checks pass; the user-owned untracked CPT files remain unchanged.

- [ ] **Step 9: Commit Task 2 in Geodesy-Visualization**

```bash
git add geodesy_visualization/workflows/insar/baseline_config.py geodesy_visualization/workflows/insar/baseline_cli.py tests/test_baseline_cli.py config_examples/baseline_plot.cfg pyproject.toml README.md
git commit -m "Expose baseline network visualization workflow"
```

### Task 3: Remove plotting ownership from Geodesy-Analysis

**Files:**
- Modify: `src/geodesy_analysis/insar/baseline_selection/gamma/runner.py`
- Modify: `src/geodesy_analysis/insar/baseline.py`
- Delete: `src/geodesy_analysis/insar/baseline_selection/common/plot_config.py`
- Delete: `src/geodesy_analysis/insar/baseline_selection/common/plot_cli.py`
- Delete: `tests/test_baseline_plot_cli.py`
- Delete: `config_examples/baseline_plot.cfg`
- Modify: `tests/test_gamma_baseline_runner.py`
- Modify: `tests/test_baseline.py`
- Modify: `tests/test_architecture.py`
- Modify: `tests/test_gamma_interferogram_cli.py`
- Modify: `pyproject.toml`
- Modify: `README.md`
- Modify: `docs/workflows/gamma_insar.md`
- Modify: `MIGRATION_PROVENANCE.md`

**Interfaces:**
- Consumes: unchanged GAMMA baseline plan and command runner contracts.
- Produces: `run_gamma_baseline(plan, *, command_runner=None, progress_sink=print) -> BaselineRunSummary`; schema-1 manifest without `plot_path` or plotting `warnings`; no Analysis plotting command or plotting dependency.

- [ ] **Step 1: Rewrite runner tests for the new boundary and verify RED**

Replace plot-callback assertions with exact two-stage progress, unchanged network/pair/provenance values, absence of PNG/`plot_path`/plot warnings, and a runner signature without `plotter`. Add a restart fixture containing legacy `plot_path` and `warnings`, omit its PNG, and assert the completed output still returns `skipped`.

Run:

```bash
PYTHONPATH=src /home/yilun/miniconda3/envs/envInSAR/bin/python -m unittest tests.test_gamma_baseline_runner -v
```

Expected: failures because the runner still plots and requires the old PNG.

- [ ] **Step 2: Remove plot execution from the GAMMA runner and verify GREEN**

Delete the plotter import/argument/callback, plotting progress item, plotting warnings and manifest `plot_path`. Make restart validation ignore unrelated legacy fields and require only scientific assets. Preserve network file bytes, pair order, logs, provenance, atomic output and failure behavior.

Run the Step 1 command. Expected: all runner tests pass.

- [ ] **Step 3: Add failing repository-boundary tests**

Assert Analysis production sources contain no `matplotlib` or `geodesy_visualization` import, `pyproject.toml` has no baseline-plot script or plot extra, and no plot CLI/config production files remain. Update baseline unit tests so only scientific functions still owned by Analysis are exercised.

Run:

```bash
PYTHONPATH=src /home/yilun/miniconda3/envs/envInSAR/bin/python -m unittest tests.test_architecture tests.test_baseline tests.test_gamma_interferogram_cli -v
```

Expected: failures while the old command, modules, dependencies and documentation references remain.

- [ ] **Step 4: Delete the old Analysis plotting surface and update documentation**

Remove plotting-only code from `baseline.py`, the common plot modules/test/cfg, console entry and Matplotlib optional dependency. Keep network-analysis functions required by `select_interferogram_network`. Rewrite the README and GAMMA workflow so the hand-off is the manifest and the next command belongs to Visualization; record the ownership migration in provenance.

- [ ] **Step 5: Run the complete Analysis suite**

Run:

```bash
PYTHONPATH=src /home/yilun/miniconda3/envs/envInSAR/bin/python -m unittest discover -s tests -v
git diff --check
```

Expected: all Analysis tests pass, and importing Analysis does not load or require Matplotlib/Visualization.

- [ ] **Step 6: Commit Task 3 in Geodesy-Analysis**

```bash
git add -A src/geodesy_analysis tests config_examples pyproject.toml README.md docs/workflows/gamma_insar.md MIGRATION_PROVENANCE.md
git commit -m "Move baseline plotting out of Analysis"
```

### Task 4: Migrate the project cfg and verify the integrated workflow

**Files:**
- Create: `/mnt/beegfs/procesados/yiluntan/Gansu_Jishishan_LT1/config/visualization/baseline_plot.cfg`
- Delete after successful validation: `/mnt/beegfs/procesados/yiluntan/Gansu_Jishishan_LT1/config/analysis/baseline_plot.cfg`
- Create: `/mnt/beegfs/procesados/yiluntan/Gansu_Jishishan_LT1/LOG/VISUALIZATION/BASELINE/validation.json`

**Interfaces:**
- Consumes: existing Jishishan ascending `baseline_manifest.json`; Task 2 installed command; Task 3 Analysis command.
- Produces: one non-empty project-local baseline PNG and a validation record containing command, manifest, output path, output size, timestamp and test results.

- [ ] **Step 1: Install both feature worktrees into their intended environments**

Run:

```bash
/home/yilun/miniconda3/envs/envPlot/bin/python -m pip install --no-deps -e /mnt/beegfs/procesados/yiluntan/Geodesy-Visualization/.worktrees/baseline-plot-ownership
/home/yilun/miniconda3/envs/envInSAR/bin/python -m pip install --no-deps -e /mnt/beegfs/procesados/yiluntan/Geodesy-Analysis/.worktrees/baseline-plot-ownership
```

Expected: both editable installations succeed and each package resolves from its own feature worktree.

- [ ] **Step 2: Create and dry-check the project Visualization cfg**

Create the approved manifest-based cfg with the existing ascending manifest and an output below `S1/VISUALIZATION/ascending/BASELINE`. Run the installed command's `--help`, then load the cfg through `load_baseline_plot_config` without creating a figure.

- [ ] **Step 3: Run one real Visualization-only baseline plot**

Run from `/mnt/beegfs/procesados/yiluntan`:

```bash
/home/yilun/miniconda3/envs/envPlot/bin/geodesy-visualization-insar-baseline \
  --config /mnt/beegfs/procesados/yiluntan/Gansu_Jishishan_LT1/config/visualization/baseline_plot.cfg \
  --case ascending
```

Expected: exit `0`, a non-empty PNG, and no GAMMA command/log changes. Inspect the generated image to confirm the master node, slave node and connecting pair are visible.

- [ ] **Step 4: Verify existing Analysis products still skip**

Run:

```bash
/home/yilun/miniconda3/envs/envInSAR/bin/geodesy-analysis-gamma-baseline --config /mnt/beegfs/procesados/yiluntan/Gansu_Jishishan_LT1/config/analysis/gamma_baseline.cfg --case ascending
/home/yilun/miniconda3/envs/envInSAR/bin/geodesy-analysis-gamma-interferogram --config /mnt/beegfs/procesados/yiluntan/Gansu_Jishishan_LT1/config/analysis/gamma_interferogram.cfg --case ascending
```

Expected: both report `status=skipped`; no GAMMA processing is executed.

- [ ] **Step 5: Run both full suites and write validation evidence**

Run the complete Visualization and Analysis unittest suites plus `git diff --check` in both worktrees. Write `validation.json` atomically only after all checks pass, then remove the old project Analysis plotting cfg.

- [ ] **Step 6: Final branch review and local integration decision**

Review both complete branch diffs against the spec, verify no user-owned CPT assets entered either commit, and use the finishing-development-branch workflow separately for each repository. Do not push unless the user explicitly asks.
