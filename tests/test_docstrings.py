"""Enforce the repository rule that every production function states its purpose."""

from __future__ import annotations

import ast
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


class ProductionDocstringTests(unittest.TestCase):
    def production_files(self) -> list[Path]:
        """Return every library and workflow module governed by documentation rules."""
        source_files = list((REPOSITORY_ROOT / "lib").glob("*.py"))
        source_files.extend(
            (REPOSITORY_ROOT / "geodesy_visualization").rglob("*.py")
        )
        source_files.extend(REPOSITORY_ROOT.glob("plot_*/*.py"))
        return source_files

    def test_every_production_module_has_structured_overview(self) -> None:
        """Require standard sections and list every public top-level function or class."""
        problems = []
        for source_file in self.production_files():
            tree = ast.parse(source_file.read_text(encoding="utf-8"), filename=str(source_file))
            module_docstring = ast.get_docstring(tree) or ""
            for section in ("功能概述:", "函数说明:"):
                if section not in module_docstring:
                    problems.append(f"{source_file.relative_to(REPOSITORY_ROOT)}: missing {section}")
            for node in tree.body:
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    if not node.name.startswith("_") and f"``{node.name}``" not in module_docstring:
                        problems.append(
                            f"{source_file.relative_to(REPOSITORY_ROOT)}: "
                            f"public symbol {node.name} is not listed"
                        )
        self.assertEqual(problems, [], "module documentation problems:\n" + "\n".join(problems))

    def test_every_production_function_has_a_docstring(self) -> None:
        """Report every production function or method missing an opening docstring."""
        missing = []

        for source_file in self.production_files():
            tree = ast.parse(source_file.read_text(encoding="utf-8"), filename=str(source_file))
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if not ast.get_docstring(node):
                        missing.append(
                            f"{source_file.relative_to(REPOSITORY_ROOT)}:{node.lineno}:{node.name}"
                        )

        self.assertEqual(missing, [], "missing function docstrings:\n" + "\n".join(missing))


if __name__ == "__main__":
    unittest.main()
