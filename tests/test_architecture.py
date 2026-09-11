"""Regression checks for documented module ownership and production imports."""

from __future__ import annotations

import ast
import re
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
GEO_MODULE = REPOSITORY_ROOT / "lib" / "pygmt_geo.py"
OWNERSHIP_MAP = REPOSITORY_ROOT / "docs" / "development" / "pygmt_geo_ownership.md"

EXPECTED_LEGACY_GEO_IMPORTS = {}

EXPECTED_PACKAGE_GEO_IMPORTS = {
    "geodesy_visualization/workflows/insar/deformation_map.py": {
        "prepare_dataset_grid",
    },
    "geodesy_visualization/workflows/insar/deformation_profile.py": {
        "prepare_dataset_grid",
    },
}

EXPECTED_CANONICAL_GEO_IMPORTS = {
    "geodesy_visualization/workflows/insar/deformation_map.py": {
        "region_from_grd",
    },
    "geodesy_visualization/workflows/insar/deformation_profile.py": {
        "extract_profile",
        "generate_tracks",
        "region_from_grd",
    },
}


def public_api(path: Path) -> set[str]:
    """Return the string names declared by one module's explicit ``__all__``."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in tree.body:
        if (
            isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id == "__all__" for target in node.targets)
            and isinstance(node.value, (ast.List, ast.Tuple))
        ):
            return {
                element.value
                for element in node.value.elts
                if isinstance(element, ast.Constant) and isinstance(element.value, str)
            }
    raise AssertionError(f"module has no static __all__: {path}")


def documented_functions(path: Path) -> set[str]:
    """Read function names from the first column of the ownership table."""
    text = path.read_text(encoding="utf-8")
    return set(re.findall(r"^\| `([a-z][a-z0-9_]*)` \|", text, flags=re.MULTILINE))


def production_imports(module_name: str) -> dict[str, set[str]]:
    """Find every direct production import from one named geo module."""
    imports: dict[str, set[str]] = {}
    excluded_roots = {".git", "tests", "lib"}
    for path in REPOSITORY_ROOT.rglob("*.py"):
        relative = path.relative_to(REPOSITORY_ROOT)
        if relative.parts[0] in excluded_roots:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        names = {
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module == module_name
            for alias in node.names
        }
        if names:
            imports[relative.as_posix()] = names
    return imports


class OwnershipMapTests(unittest.TestCase):
    def test_documents_every_public_geo_function(self) -> None:
        """Require the migration map to change whenever the public API changes."""
        self.assertEqual(documented_functions(OWNERSHIP_MAP), public_api(GEO_MODULE))

    def test_tracks_every_production_geo_import(self) -> None:
        """Require new production callers to be reviewed before entering the tree."""
        self.assertEqual(production_imports("pygmt_geo"), EXPECTED_LEGACY_GEO_IMPORTS)
        self.assertEqual(
            production_imports("lib.pygmt_geo"), EXPECTED_PACKAGE_GEO_IMPORTS
        )
        self.assertEqual(
            production_imports("geodesy_visualization.geo"),
            EXPECTED_CANONICAL_GEO_IMPORTS,
        )


if __name__ == "__main__":
    unittest.main()
