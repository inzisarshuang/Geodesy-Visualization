"""Behavioral tests for the source-neutral InSAR baseline visualization."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from geodesy_visualization.workflows.insar.baseline_network import (
    plot_baseline_network,
    read_baseline_manifest,
    read_baseline_network,
)


class _ProductFactory:
    """Create complete local Analysis products shared by behavioral tests."""

    def _product(
        self,
        root: Path,
        *,
        rows: str | None = None,
        manifest_updates: dict[str, object] | None = None,
    ) -> Path:
        """Write one complete Analysis baseline product for a test."""

        product = root / "ANALYSIS/GAMMA/ascending/BASELINE"
        product.mkdir(parents=True)
        network = product / "baseline_select_SBAS"
        network.write_text(
            rows
            if rows is not None
            else (
                "20200101 20200113 10 12\n"
                "20200113 20200125 -3 12\n"
                "20200101 20200125 7 24\n"
            ),
            encoding="utf-8",
        )
        payload: dict[str, object] = {
            "schema_version": 1,
            "status": "complete",
            "reference_date": "20200101",
            "pair_count": 3,
            "network_path": "baseline_select_SBAS",
            "network_type": "SBAS",
            "plot_path": "legacy_plot_may_not_exist.png",
        }
        payload.update(manifest_updates or {})
        manifest = product / "baseline_manifest.json"
        manifest.write_text(json.dumps(payload), encoding="utf-8")
        return manifest


class BaselineNetworkContractTests(_ProductFactory, unittest.TestCase):
    """Reject unsafe products and preserve the scientific network values."""

    def test_preserves_pair_order_and_solves_signed_node_baselines(self) -> None:
        """Catch reordered pairs or a wrong sign while traversing the network."""

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = read_baseline_manifest(self._product(root), project_root=root)
            network = read_baseline_network(manifest)

        self.assertEqual(manifest.reference_date, "20200101")
        self.assertEqual(manifest.pair_count, 3)
        self.assertEqual(
            [(pair.master, pair.slave) for pair in network.pairs],
            [
                ("20200101", "20200113"),
                ("20200113", "20200125"),
                ("20200101", "20200125"),
            ],
        )
        self.assertEqual(network.dates, ("20200101", "20200113", "20200125"))
        self.assertEqual(
            dict(network.perpendicular_baselines_m),
            {"20200101": 0.0, "20200113": 10.0, "20200125": 7.0},
        )

    def test_rejects_invalid_manifest_identity_and_unsafe_network_paths(self) -> None:
        """Catch incomplete products and paths that escape their publication folder."""

        cases = (
            ({"schema_version": 3}, "schema_version"),
            ({"status": "failed"}, "status"),
            ({"reference_date": "2020-01-01"}, "reference_date"),
            ({"pair_count": 0}, "pair_count"),
            ({"network_path": "/tmp/network"}, "relative"),
            ({"network_path": "../network"}, "traverse"),
        )
        for updates, message in cases:
            with self.subTest(updates=updates):
                with tempfile.TemporaryDirectory() as directory:
                    root = Path(directory)
                    source = self._product(root, manifest_updates=updates)
                    with self.assertRaisesRegex(ValueError, message):
                        read_baseline_manifest(source, project_root=root)

    def test_rejects_manifest_outside_project(self) -> None:
        """Catch a valid-looking manifest selected from another project."""

        with tempfile.TemporaryDirectory() as project, tempfile.TemporaryDirectory() as other:
            source = self._product(Path(other))
            with self.assertRaisesRegex(ValueError, "project"):
                read_baseline_manifest(source, project_root=Path(project))

    def test_rejects_missing_or_empty_network(self) -> None:
        """Catch a manifest published without its declared scientific table."""

        for mode in ("missing", "empty"):
            with self.subTest(mode=mode):
                with tempfile.TemporaryDirectory() as directory:
                    root = Path(directory)
                    source = self._product(root)
                    manifest = read_baseline_manifest(source, project_root=root)
                    if mode == "missing":
                        manifest.network_path.unlink()
                    else:
                        manifest.network_path.write_text("", encoding="utf-8")
                    with self.assertRaisesRegex(
                        (FileNotFoundError, ValueError), "network"
                    ):
                        read_baseline_network(manifest)

    def test_rejects_malformed_or_inconsistent_network_rows(self) -> None:
        """Catch rows that would draw scientifically misleading topology."""

        cases = (
            ("2020010X 20200113 10 12\n", {}, "date"),
            ("20200101 20200101 0 0\n", {}, "self"),
            (
                "20200101 20200113 10 12\n20200101 20200113 10 12\n",
                {"pair_count": 2},
                "duplicate",
            ),
            (
                "20200101 20200113 10 12\n20200113 20200101 -10 -12\n",
                {"pair_count": 2},
                "reversed",
            ),
            ("20200101 20200113 nan 12\n", {}, "finite"),
            ("20200101 20200113 10 inf\n", {}, "finite"),
            ("20200101 20200113 10\n", {}, "four"),
            (
                "20200101 20200113 10 12\n",
                {"pair_count": 2},
                "pair_count",
            ),
            (
                "20200101 20200113 10 12\n",
                {"reference_date": "20200125", "pair_count": 1},
                "reference",
            ),
        )
        for rows, updates, message in cases:
            with self.subTest(message=message):
                with tempfile.TemporaryDirectory() as directory:
                    root = Path(directory)
                    source = self._product(
                        root, rows=rows, manifest_updates=updates
                    )
                    manifest = read_baseline_manifest(source, project_root=root)
                    with self.assertRaisesRegex(ValueError, message):
                        read_baseline_network(manifest)


class BaselineNetworkRenderTests(_ProductFactory, unittest.TestCase):
    """Publish a real PNG atomically from already validated network data."""

    def _network(self, root: Path):
        """Build the smallest connected network accepted by the renderer."""

        source = self._product(
            root,
            rows="20200101 20200113 10 12\n",
            manifest_updates={"pair_count": 1},
        )
        return read_baseline_network(
            read_baseline_manifest(source, project_root=root)
        )

    def test_publishes_a_nonempty_png_and_returns_resolved_path(self) -> None:
        """Catch a renderer that does not create the configured final figure."""

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            destination = root / "VISUALIZATION/baseline_network.png"
            result = plot_baseline_network(
                self._network(root),
                destination,
                title="Test baseline network",
                dpi=90,
                figsize=(6.0, 4.0),
                y_top_extra=20.0,
                y_bottom_extra=10.0,
                font_family="TeX Gyre Heros",
            )
            self.assertEqual(result, destination.resolve())
            self.assertGreater(destination.stat().st_size, 1000)
            self.assertEqual(destination.read_bytes()[:8], b"\x89PNG\r\n\x1a\n")

    def test_plot_failure_preserves_previous_destination_and_cleans_temporary(self) -> None:
        """Catch partial replacement of a valid pre-existing scientific figure."""

        import matplotlib.pyplot  # noqa: F401

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            destination = root / "baseline_network.png"
            destination.write_bytes(b"existing-figure")
            with patch("matplotlib.figure.Figure.savefig", side_effect=RuntimeError("stop")):
                with self.assertRaisesRegex(RuntimeError, "stop"):
                    plot_baseline_network(
                        self._network(root),
                        destination,
                        title="Test baseline network",
                        dpi=90,
                        figsize=(6.0, 4.0),
                        y_top_extra=20.0,
                        y_bottom_extra=10.0,
                        font_family="TeX Gyre Heros",
                    )
            self.assertEqual(destination.read_bytes(), b"existing-figure")
            self.assertEqual(list(root.glob(".baseline_network.*.png")), [])


if __name__ == "__main__":
    unittest.main()
