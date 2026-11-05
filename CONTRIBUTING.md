# Contributing

Read [AGENTS.md](AGENTS.md) before changing code. It is the repository's coding baseline for both human and AI contributors.

## Environment

The recommended Conda environment is documented in [README.md](README.md). Confirm that both `gmt` and `gdal_translate` are available on `PATH` before running integration tests.

## Change Process

1. Reproduce the current behavior with an example cfg.
2. Keep scientific conventions and existing cfg keys compatible.
3. Put new reusable behavior in `src/geodesy_visualization/`; keep compatibility-only modules in `lib/` and task scripts focused on orchestration.
4. Add or update tests for parser, I/O, and numerical behavior.
5. Run syntax checks, unit tests, and affected example plots.
6. Inspect `git diff --check` and generated figures before committing.

Do not commit generated GRD files, figures, local environments, or machine-specific paths.
