"""Regression test for the processing/visualization environment boundary."""

from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class EnvironmentBoundaryTests(unittest.TestCase):
    """Keep the plotting package installable without the processing adapter."""

    def test_visualization_has_no_data_adapter_dependency_or_import(self) -> None:
        """Require exchange files, not a cross-environment Python dependency."""
        pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8")
        self.assertNotIn("insar-data-adapter", pyproject)
        self.assertNotIn("insar-data-adapter", requirements)

        offenders = []
        for source in (ROOT / "src").rglob("*.py"):
            if "insar_data_adapter" in source.read_text(encoding="utf-8"):
                offenders.append(source.relative_to(ROOT).as_posix())
        self.assertEqual(offenders, [])


if __name__ == "__main__":
    unittest.main()
