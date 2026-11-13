"""Tests for fluent execution of validated PyGMT Figure operations."""

from __future__ import annotations

import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from types import MappingProxyType

from geodesy_visualization.figure_ops.executor import FigureExecutor
from geodesy_visualization.figure_ops.model import FigureOperation, FigurePlan


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
STUDY_FIXTURES = REPOSITORY_ROOT / "tests" / "fixtures" / "study_area"


class RecordingFigure:
    """Record current PyGMT-like method calls for deterministic tests."""

    def __init__(self) -> None:
        """Initialize an empty ordered call list."""
        self.calls: list[tuple[str, dict]] = []

    def basemap(self, **kwargs) -> None:
        """Record one basemap call."""
        self.calls.append(("basemap", kwargs))

    def grdimage(self, **kwargs) -> None:
        """Record one grdimage call."""
        self.calls.append(("grdimage", kwargs))

    def scalebar(self, **kwargs) -> None:
        """Record one current-API scalebar call."""
        self.calls.append(("scalebar", kwargs))

    def directional_rose(self, **kwargs) -> None:
        """Record one current-API directional-rose call."""
        self.calls.append(("directional_rose", kwargs))

    def colorbar(self, **kwargs) -> None:
        """Record one colorbar call."""
        self.calls.append(("colorbar", kwargs))

    def plot(self, **kwargs) -> None:
        """Record one vector, polygon, or marker call."""
        self.calls.append(("plot", kwargs))

    def meca(self, **kwargs) -> None:
        """Record one focal-mechanism call."""
        self.calls.append(("meca", kwargs))

    def coast(self, **kwargs) -> None:
        """Record one coast or administrative-boundary call."""
        self.calls.append(("coast", kwargs))

    @contextmanager
    def inset(self, **kwargs):
        """Record entry and exit around one inset operation scope."""
        self.calls.append(("inset_enter", kwargs))
        yield
        self.calls.append(("inset_exit", {}))

    def legend(self, spec=None, **kwargs) -> None:
        """Read and record the generated legend specification immediately."""
        content = Path(spec).read_text(encoding="utf-8") if spec else ""
        self.calls.append(("legend", {"spec_content": content, **kwargs}))

    def savefig(self, fname, **kwargs) -> None:
        """Record one output call without writing a file."""
        self.calls.append(("savefig", {"fname": fname, **kwargs}))


class LegacyRecordingFigure:
    """Record the subset available from a PyGMT v0.10-like Figure."""

    def __init__(self) -> None:
        """Initialize an empty call list without dedicated embellishment methods."""
        self.calls: list[tuple[str, dict]] = []

    def basemap(self, **kwargs) -> None:
        """Record legacy scale/rose calls made through basemap."""
        self.calls.append(("basemap", kwargs))


def operation(
    section: str,
    handler: str,
    options: dict[str, object],
    order: int,
) -> FigureOperation:
    """Build one immutable operation fixture from its dotted section."""
    tokens = section.split(".")
    return FigureOperation(
        section=section,
        method=tokens[1],
        semantics=tuple(tokens[2:]),
        options=MappingProxyType(options),
        order=order,
        handler=handler,
    )


def plan(*operations: FigureOperation) -> FigurePlan:
    """Build one minimal immutable plan for executor tests."""
    return FigurePlan(
        config_path=Path("/tmp/study_area.cfg"),
        project=MappingProxyType({}),
        figure=MappingProxyType({"layout": "publication_sidecar"}),
        operations=operations,
    )


class FigureOperationExecutorTests(unittest.TestCase):
    """Verify ordered dispatch, state sharing, and compatibility behavior."""

    def test_executes_in_order_and_publishes_raster_resource(self) -> None:
        """Apply operations to one Figure and share raster metadata with colorbar."""
        with tempfile.TemporaryDirectory() as tmp:
            output = str(Path(tmp) / "study_area.png")
            operations = (
                operation(
                    "figure.basemap",
                    "basemap",
                    {"region": (102.0, 103.6, 35.2, 36.5), "projection": "M8i"},
                    0,
                ),
                operation(
                    "figure.grdimage.dem",
                    "grdimage",
                    {"grid": "/tmp/dem.grd", "cmap": "gray", "shading": "+d"},
                    1,
                ),
                operation(
                    "figure.colorbar.dem",
                    "colorbar",
                    {
                        "source": "figure.grdimage.dem",
                        "position": "BC",
                        "label": "Elevation",
                        "unit": "m",
                    },
                    2,
                ),
                operation(
                    "figure.savefig",
                    "savefig",
                    {"fname": output, "dpi": 300, "crop": True},
                    3,
                ),
            )
            figure = RecordingFigure()
            executor = FigureExecutor(plan(*operations), figure_factory=lambda: figure)

            result = executor.execute()

            self.assertIs(result, executor)
            self.assertEqual(
                [name for name, _ in figure.calls],
                ["basemap", "grdimage", "colorbar", "savefig"],
            )
            self.assertEqual(executor.context.region, (102.0, 103.6, 35.2, 36.5))
            self.assertEqual(executor.context.projection, "M8i")
            self.assertEqual(
                executor.context.resources["figure.grdimage.dem"]["cmap"], "gray"
            )
            self.assertEqual(figure.calls[1][1]["region"], (102.0, 103.6, 35.2, 36.5))
            self.assertEqual(figure.calls[1][1]["projection"], "M8i")
            self.assertEqual(figure.calls[2][1]["cmap"], "gray")

    def test_apply_is_fluent_and_figure_creation_is_lazy(self) -> None:
        """Return the same executor while creating a Figure only on first use."""
        created: list[RecordingFigure] = []

        def factory() -> RecordingFigure:
            """Record lazy creation of a fake Figure."""
            created.append(RecordingFigure())
            return created[-1]

        executor = FigureExecutor(plan(), figure_factory=factory)
        self.assertEqual(created, [])
        result = executor.apply(
            operation(
                "figure.basemap",
                "basemap",
                {"region": (0.0, 1.0, 0.0, 1.0), "projection": "M8c"},
                0,
            )
        )
        self.assertIs(result, executor)
        self.assertEqual(len(created), 1)

    def test_rejects_unprepared_source_before_rendering(self) -> None:
        """Fail a dependent operation before calling the Figure method."""
        figure = RecordingFigure()
        executor = FigureExecutor(plan(), figure_factory=lambda: figure)
        colorbar = operation(
            "figure.colorbar.dem",
            "colorbar",
            {"source": "figure.grdimage.dem", "position": "BC"},
            0,
        )
        with self.assertRaisesRegex(ValueError, "figure.colorbar.dem.*source"):
            executor.apply(colorbar)
        self.assertEqual(figure.calls, [])

    def test_requires_savefig_to_be_the_last_operation(self) -> None:
        """Reject a plan whose output is followed by another drawing operation."""
        operations = (
            operation("figure.savefig", "savefig", {"fname": "/tmp/a.png"}, 0),
            operation(
                "figure.basemap",
                "basemap",
                {"region": (0.0, 1.0, 0.0, 1.0), "projection": "M8c"},
                1,
            ),
        )
        with self.assertRaisesRegex(ValueError, "figure.savefig.*last"):
            FigureExecutor(plan(*operations), figure_factory=RecordingFigure).execute()

    def test_uses_current_dedicated_embellishment_methods(self) -> None:
        """Call dedicated current PyGMT methods when the Figure provides them."""
        figure = RecordingFigure()
        executor = FigureExecutor(plan(), figure_factory=lambda: figure)
        executor.apply(
            operation(
                "figure.scalebar",
                "scalebar",
                {"position": "BR", "length": "50k", "fancy": True, "unit": True},
                0,
            )
        ).apply(
            operation(
                "figure.directional_rose",
                "directional_rose",
                {"position": "TR", "width": "2c"},
                1,
            )
        )
        self.assertEqual([name for name, _ in figure.calls], ["scalebar", "directional_rose"])
        self.assertEqual(figure.calls[0][1]["position"], "BR")
        self.assertEqual(figure.calls[1][1]["width"], "2c")

    def test_falls_back_to_v010_basemap_embellishments(self) -> None:
        """Translate current CFG names to legacy basemap raw option strings."""
        figure = LegacyRecordingFigure()
        executor = FigureExecutor(plan(), figure_factory=lambda: figure)
        executor.apply(
            operation(
                "figure.scalebar",
                "scalebar",
                {"position": "BR", "length": "50k", "fancy": True, "unit": True},
                0,
            )
        ).apply(
            operation(
                "figure.directional_rose",
                "directional_rose",
                {"position": "TR", "width": "2c"},
                1,
            )
        )
        self.assertEqual(len(figure.calls), 2)
        self.assertEqual(figure.calls[0][1]["map_scale"], "jBR+w50k+f+u")
        self.assertEqual(figure.calls[1][1]["rose"], "jTR+w2c")

    def test_footprint_draws_each_polygon_and_adds_one_legend_item(self) -> None:
        """Keep polygon count independent from the scientific legend entry count."""
        figure = RecordingFigure()
        executor = FigureExecutor(plan(), figure_factory=lambda: figure)
        executor.apply(
            operation(
                "figure.plot.footprint.slaves",
                "footprint",
                {
                    "data": str(STUDY_FIXTURES / "slave_footprints.kml"),
                    "pen": "4p,blue",
                    "label": "LT-1 slave images",
                },
                0,
            )
        )
        plot_calls = [kwargs for name, kwargs in figure.calls if name == "plot"]
        self.assertEqual(len(plot_calls), 2)
        self.assertTrue(all(len(call["x"]) == 5 for call in plot_calls))
        self.assertEqual(len(executor.context.legend_items), 1)
        self.assertEqual(executor.context.legend_items[0]["label"], "LT-1 slave images")

    def test_faults_use_kinematic_styles_and_other_fallback(self) -> None:
        """Map reverse, strike-slip, and unknown faults to deterministic styles."""
        figure = RecordingFigure()
        executor = FigureExecutor(plan(), figure_factory=lambda: figure)
        executor.apply(
            operation(
                "figure.plot.faults",
                "faults",
                {
                    "data": str(STUDY_FIXTURES / "faults.geojson"),
                    "kinematic_field": "Fea_En",
                    "pen": "1.5p,black",
                    "fallback_pen": "1p,gray50",
                },
                0,
            )
        )
        calls = [kwargs for name, kwargs in figure.calls if name == "plot"]
        self.assertEqual(len(calls), 4)
        self.assertEqual(calls[0]["style"], "f0.8c/0.3c+r+t")
        self.assertEqual(calls[0]["fill"], "white")
        self.assertEqual(calls[1]["style"], "f0.8c/0.3c+l+s")
        self.assertEqual(calls[2]["style"], "f0.8c/0.3c+l+s")
        self.assertEqual(calls[3]["pen"], "1p,gray50")
        self.assertNotIn("style", calls[3])

    def test_meca_uses_configured_aki_values(self) -> None:
        """Pass the configured strike, dip, rake, magnitude, and depth to meca."""
        figure = RecordingFigure()
        executor = FigureExecutor(plan(), figure_factory=lambda: figure)
        executor.apply(
            operation(
                "figure.meca.mainshock",
                "meca",
                {
                    "longitude": 102.79,
                    "latitude": 35.758,
                    "strike": 353.0,
                    "dip": 78.0,
                    "rake": -124.0,
                    "magnitude": 5.9,
                    "depth_km": 18.281,
                    "scale": "0.6c",
                },
                0,
            )
        )
        name, kwargs = figure.calls[0]
        self.assertEqual(name, "meca")
        self.assertEqual(
            kwargs["spec"],
            {"strike": 353.0, "dip": 78.0, "rake": -124.0, "magnitude": 5.9},
        )
        self.assertEqual(kwargs["depth"], 18.281)

    def test_insets_contain_coast_and_location_marker_calls(self) -> None:
        """Render globe and regional location content inside separate inset scopes."""
        figure = RecordingFigure()
        executor = FigureExecutor(plan(), figure_factory=lambda: figure)
        executor.apply(
            operation(
                "figure.basemap",
                "basemap",
                {"region": (102.0, 103.6, 35.2, 36.5), "projection": "M8i"},
                0,
            )
        ).apply(
            operation(
                "figure.inset.globe",
                "globe_inset",
                {"position": "TR", "width": "4c", "highlight": "CN"},
                1,
            )
        ).apply(
            operation(
                "figure.inset.regional",
                "regional_inset",
                {"position": "MR", "width": "6c", "regions": "CN.62,CN.63"},
                2,
            )
        )
        names = [name for name, _ in figure.calls]
        self.assertEqual(
            names,
            [
                "basemap",
                "inset_enter", "coast", "plot", "inset_exit",
                "inset_enter", "coast", "plot", "inset_exit",
            ],
        )
        self.assertIn("CN+g", figure.calls[2][1]["dcw"])
        self.assertIn("CN.62,CN.63", figure.calls[6][1]["dcw"])

    def test_automatic_legend_follows_operation_order(self) -> None:
        """Generate one legend after fault and footprint contributions in that order."""
        figure = RecordingFigure()
        executor = FigureExecutor(plan(), figure_factory=lambda: figure)
        executor.apply(
            operation(
                "figure.plot.faults",
                "faults",
                {"data": str(STUDY_FIXTURES / "faults.geojson"), "kinematic_field": "Fea_En"},
                0,
            )
        ).apply(
            operation(
                "figure.plot.footprint.reference",
                "footprint",
                {
                    "data": str(STUDY_FIXTURES / "reference_footprint.kml"),
                    "pen": "4p,red",
                    "label": "LT-1 reference image",
                },
                1,
            )
        ).apply(
            operation(
                "figure.legend",
                "legend",
                {"position": "BC", "box": True},
                2,
            )
        )
        legend = next(kwargs for name, kwargs in figure.calls if name == "legend")
        content = legend["spec_content"]
        self.assertLess(content.index("Reverse fault"), content.index("LT-1 reference image"))
        self.assertEqual(len(executor.context.legend_items), 5)


if __name__ == "__main__":
    unittest.main()
