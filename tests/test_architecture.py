"""Regression checks for documented module ownership and production imports."""

from __future__ import annotations

import ast
import re
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
GEO_MODULE = REPOSITORY_ROOT / "lib" / "pygmt_geo.py"
OWNERSHIP_MAP = REPOSITORY_ROOT / "docs" / "development" / "pygmt_geo_ownership.md"

EXPECTED_PRODUCTION_IMPORTS = {
    "plot_defo_dem_optic/plot_defo_dem_optic.py": {
        "prepare_dataset_grid",
        "region_from_grd",
    },
    "plot_defo_profile/plot_defo_dem_profile.py": {
        "extract_profile",
        "generate_tracks",
        "prepare_dataset_grid",
        "region_from_grd",
    },
}


def public_functions(path: Path) -> set[str]:
    """Return public top-level function names declared by one Python module."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return {
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and not node.name.startswith("_")
    }


def documented_functions(path: Path) -> set[str]:
    """Read function names from the first column of the ownership table."""
    text = path.read_text(encoding="utf-8")
    return set(re.findall(r"^\| `([a-z][a-z0-9_]*)` \|", text, flags=re.MULTILINE))


def production_imports() -> dict[str, set[str]]:
    """Find every direct production import from the legacy geo module."""
    imports: dict[str, set[str]] = {}
    excluded_roots = {".git", "tests", "lib", "geodesy_visualization"}
    for path in REPOSITORY_ROOT.rglob("*.py"):
        relative = path.relative_to(REPOSITORY_ROOT)
        if relative.parts[0] in excluded_roots:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        names = {
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module == "pygmt_geo"
            for alias in node.names
        }
        if names:
            imports[relative.as_posix()] = names
    return imports


class OwnershipMapTests(unittest.TestCase):
    def test_documents_every_public_geo_function(self) -> None:
        """Require the migration map to change whenever the public API changes."""
        self.assertEqual(documented_functions(OWNERSHIP_MAP), public_functions(GEO_MODULE))

    def test_tracks_every_production_geo_import(self) -> None:
        """Require new production callers to be reviewed before entering the tree."""
        self.assertEqual(production_imports(), EXPECTED_PRODUCTION_IMPORTS)


if __name__ == "__main__":
    unittest.main()
