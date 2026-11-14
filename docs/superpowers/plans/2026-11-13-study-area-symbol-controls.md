# Study-Area Symbol Controls Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose study-area scale-bar height and legend-symbol geometry through CFG, then document every LT-1 study-area CFG parameter and its run command.

**Architecture:** Keep scientific layers responsible for structured legend metadata and format GMT legend records only in `render_legend`, where one set of geometry controls can align fault and footprint entries. Translate `map_scale_height` to GMT's local `MAP_SCALE_HEIGHT` configuration so it works with the installed PyGMT v0.10 fallback.

**Tech Stack:** Python, `configparser`, PyGMT/GMT, `unittest`, INI CFG.

**Spec:** `docs/superpowers/specs/2026-11-13-study-area-operation-cartography-design.md`

## Global Constraints

- Preserve unrelated dirty files and untracked visualization data.
- Use `envPlot`; do not alter the environment.
- Keep existing CFGs compatible when the new keys are absent.
- Use lowercase descriptive CFG names; do not expose GMT one-letter aliases.
- Do not commit or push unless requested separately.

## Review Focus

- `map_scale_height` must affect GMT configuration and must not leak into `Figure.scalebar` or legacy `basemap` keyword arguments.
- Legend geometry must affect both fault-front and footprint-line records while preserving scientific entry order.
- `box = no` must render without a frame and must ignore frame padding safely.
- Existing CFGs without the new geometry keys must retain their current defaults.
- The distributable example and LT-1 CFG must remain strictly loadable after comments are added.

---

### Task 1: Typed symbol controls and rendering

**Files:**
- Modify: `tests/test_figure_operation_config.py`
- Modify: `tests/test_figure_operation_executor.py`
- Modify: `src/geodesy_visualization/figure_ops/registry.py`
- Modify: `src/geodesy_visualization/figure_ops/direct_operations.py`
- Modify: `src/geodesy_visualization/figure_ops/cartography_operations.py`

**Interfaces:**
- Consumes: `[figure.scalebar] map_scale_height` and `[figure.legend] symbol_offset`, `line_length`, `front_spacing`, `front_size`, `text_offset`.
- Produces: local GMT scale-height configuration and automatic legend records using the configured geometry.

- [ ] Write parser and executor tests for the new keys, including frame-free legend output.
- [ ] Run focused tests and confirm they fail because the keys/behavior are not implemented.
- [ ] Add strict registry keys and late legend-record formatting; consume `map_scale_height` locally.
- [ ] Run focused tests and confirm they pass.

### Task 2: Fully annotated configurations and real LT-1 render

**Files:**
- Modify: `config_examples/visualization/study_area/footprint.cfg`
- Modify outside repository: `/mnt/beegfs/procesados/yiluntan/Gansu_Jishishan_LT1/config/4visualization/study_area_lt1.cfg`
- Generate outside repository: `/mnt/beegfs/procesados/yiluntan/Gansu_Jishishan_LT1/result_visual/study_area/refactored/jishishan_lt1.png`

**Interfaces:**
- Consumes: Task 1 CFG keys.
- Produces: runnable, parameter-by-parameter documented generic and LT-1 configurations.

- [ ] Add top-level `envPlot` dry-run/render commands and detailed comments for every configured key.
- [ ] Configure the approved LT-1 values: no legend frame, `3c` lines, `1c` front spacing, `0.25c` front size, and `20p` scale height.
- [ ] Load both CFGs, run the focused/full test suites, render LT-1, and inspect the resulting image.
- [ ] Review the final diff without touching unrelated changes.
