"""Tests for fluent execution of validated PyGMT Figure operations."""

from __future__ import annotations

import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from types import MappingProxyType
from unittest.mock import patch

from geodesy_visualization.figure_ops.executor import FigureExecutor
from geodesy_visualization.figure_ops.model import (
    FigureOperation,
    FigurePlan,
    LayerOperation,
    PanelPlan,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
STUDY_FIXTURES = REPOSITORY_ROOT / "tests" / "fixtures" / "study_area"


class RecordingFigure:
    """Record current PyGMT-like method calls for deterministic tests."""

    def __init__(self) -> None:
        """Initialize an empty ordered call list."""
        self.calls: list[tuple[str, dict]] = []

    @contextmanager
    def set_panel(self, panel) -> None:
        """Record entry and exit around one subplot panel scope."""
        self.calls.append(("panel_enter", {"panel": panel}))
        yield
        self.calls.append(("panel_exit", {"panel": panel}))

    @contextmanager
    def subplot(self, **kwargs) -> None:
        """Record entry and exit around one multi-panel figure scope."""
        self.calls.append(("subplot_enter", kwargs))
        yield
        self.calls.append(("subplot_exit", {}))

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
        """Record one output call and publish a small valid test artifact."""
        self.calls.append(("savefig", {"fname": fname, **kwargs}))
        Path(fname).write_bytes(b"test-figure")


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
            self.assertIs(figure.calls[2][1]["cmap"], True)

    def test_executes_panel_layers_inside_their_named_scopes(self) -> None:
        """Catch layers rendered outside their configured subplot panel."""
        first = operation(
            "figure.plot.first",
            "record_panel",
            {},
            0,
        )
        second = operation(
            "figure.plot.second",
            "record_panel",
            {},
            1,
        )
        figure = RecordingFigure()
        observed: list[tuple[str, object, object]] = []

        def record_panel(context, layer) -> None:
            """Record the active panel identity, region, and projection."""
            observed.append((layer.section, context.region, context.projection))

        configured = FigurePlan(
            config_path=Path("/tmp/panels.cfg"),
            project=MappingProxyType({}),
            figure=MappingProxyType({"layout": "subplot"}),
            operations=(),
            panels=(
                PanelPlan("upper", (0.0, 1.0, 2.0, 3.0), "M8c", (first,)),
                PanelPlan("lower", (4.0, 5.0, 6.0, 7.0), "M6c", (second,)),
            ),
        )

        executor = FigureExecutor(
            configured,
            figure_factory=lambda: figure,
            handlers={"record_panel": record_panel},
        ).execute_plan()

        self.assertIsInstance(first, LayerOperation)
        self.assertEqual(
            [name for name, _ in figure.calls],
            ["panel_enter", "panel_exit", "panel_enter", "panel_exit"],
        )
        self.assertEqual(
            observed,
            [
                ("figure.plot.first", (0.0, 1.0, 2.0, 3.0), "M8c"),
                ("figure.plot.second", (4.0, 5.0, 6.0, 7.0), "M6c"),
            ],
        )
        self.assertIs(executor.execute_plan(), executor)

    def test_panel_resources_do_not_leak_into_the_next_panel(self) -> None:
        """Catch one panel accidentally consuming another panel's prepared raster."""
        figure = RecordingFigure()
        observed: list[set[str]] = []

        def publish(context, layer) -> None:
            """Publish a resource in the active panel only."""
            context.resources[layer.section] = {"value": "panel-only"}

        def inspect(context, layer) -> None:
            """Capture the resources visible to the next panel."""
            observed.append(set(context.resources))

        configured = FigurePlan(
            config_path=Path("/tmp/resources.cfg"),
            project=MappingProxyType({}),
            figure=MappingProxyType({"layout": "subplot"}),
            operations=(),
            panels=(
                PanelPlan(
                    0,
                    None,
                    None,
                    (operation("figure.plot.source", "publish", {}, 0),),
                ),
                PanelPlan(
                    1,
                    None,
                    None,
                    (operation("figure.plot.consumer", "inspect", {}, 1),),
                ),
            ),
        )

        FigureExecutor(
            configured,
            figure_factory=lambda: figure,
            handlers={"publish": publish, "inspect": inspect},
        ).execute_plan()

        self.assertEqual(observed, [set()])

    def test_subplot_scope_wraps_all_panel_scopes_once(self) -> None:
        """Catch panel selection occurring outside the owning subplot context."""
        figure = RecordingFigure()
        configured = FigurePlan(
            config_path=Path("/tmp/subplot.cfg"),
            project=MappingProxyType({}),
            figure=MappingProxyType(
                {
                    "layout": "subplot",
                    "subplot": {"nrows": 1, "ncols": 2, "subsize": ("4c", "3c")},
                }
            ),
            panels=(
                PanelPlan(0, None, None, ()),
                PanelPlan(1, None, None, ()),
            ),
        )

        FigureExecutor(configured, figure_factory=lambda: figure).execute_plan()

        self.assertEqual(
            [name for name, _ in figure.calls],
            [
                "subplot_enter",
                "panel_enter",
                "panel_exit",
                "panel_enter",
                "panel_exit",
                "subplot_exit",
            ],
        )
        self.assertEqual(
            figure.calls[0][1],
            {"nrows": 1, "ncols": 2, "subsize": ("4c", "3c")},
        )

    def test_single_cartesian_panel_executes_without_subplot_selection(self) -> None:
        """Catch a direct Cartesian figure incorrectly requiring Figure.set_panel."""
        figure = RecordingFigure()
        observed: list[str] = []

        def record(context, layer) -> None:
            """Record the direct panel layer without drawing."""
            observed.append(layer.section)

        configured = FigurePlan(
            config_path=Path("/tmp/cartesian.cfg"),
            project=MappingProxyType({}),
            figure=MappingProxyType({"layout": "cartesian"}),
            panels=(
                PanelPlan(
                    "main",
                    None,
                    "X16c/5c",
                    (operation("figure.plot.series", "record", {}, 0),),
                ),
            ),
        )

        FigureExecutor(
            configured,
            figure_factory=lambda: figure,
            handlers={"record": record},
        ).execute_plan()

        self.assertEqual(observed, ["figure.plot.series"])
        self.assertEqual(figure.calls, [])

    def test_failed_atomic_save_preserves_existing_output_and_removes_temporary(self) -> None:
        """Catch a failed PyGMT export replacing a valid existing figure."""
        class FailingFigure(RecordingFigure):
            """Write a partial temporary artifact and fail during publication."""

            def savefig(self, fname, **kwargs) -> None:
                """Simulate a renderer failure after creating partial output."""
                Path(fname).write_bytes(b"partial")
                raise RuntimeError("simulated export failure")

        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "figure.png"
            output.write_bytes(b"previous-valid-figure")
            configured = plan(
                operation(
                    "figure.savefig",
                    "savefig",
                    {"fname": str(output), "dpi": 300},
                    0,
                )
            )

            with self.assertRaisesRegex(RuntimeError, "simulated export failure"):
                FigureExecutor(
                    configured,
                    figure_factory=FailingFigure,
                ).execute_plan()

            self.assertEqual(output.read_bytes(), b"previous-valid-figure")
            self.assertEqual(list(output.parent.glob(".figure.*.png")), [])

    def test_grdimage_series_builds_one_shared_cpt(self) -> None:
        """Use one explicit CPT range for both raster colors and its colorbar."""
        figure = RecordingFigure()
        executor = FigureExecutor(plan(), figure_factory=lambda: figure)
        with patch("pygmt.makecpt") as makecpt:
            executor.apply(
                operation(
                    "figure.grdimage.dem",
                    "grdimage",
                    {
                        "grid": "/tmp/dem.grd",
                        "cmap": "gray",
                        "series": "0/5000/1000",
                        "continuous": True,
                    },
                    0,
                )
            )
        makecpt.assert_called_once_with(
            cmap="gray", series="0/5000/1000", continuous=True
        )
        self.assertIs(figure.calls[0][1]["cmap"], True)
        self.assertNotIn("series", figure.calls[0][1])
        self.assertNotIn("continuous", figure.calls[0][1])

    def test_basemap_applies_configured_coordinate_and_title_fonts(self) -> None:
        """Apply bold map title, coordinate annotation, and axis-label fonts locally."""
        figure = RecordingFigure()
        executor = FigureExecutor(plan(), figure_factory=lambda: figure)
        with patch("pygmt.config") as config:
            config.return_value.__enter__.return_value = None
            executor.apply(
                operation(
                    "figure.basemap",
                    "basemap",
                    {
                        "region": (102.0, 103.6, 35.2, 36.5),
                        "projection": "M15c",
                        "title": "Study Area Jishishan",
                        "font_title": "28p,Helvetica-Bold",
                        "font_annot_primary": "14p,Helvetica-Bold",
                        "font_label": "20p,Helvetica-Bold",
                    },
                    0,
                )
            )
        config.assert_called_once_with(
            FONT_TITLE="28p,Helvetica-Bold",
            FONT_ANNOT_PRIMARY="14p,Helvetica-Bold",
            FONT_LABEL="20p,Helvetica-Bold",
        )
        basemap = figure.calls[-1][1]
        self.assertNotIn("font_title", basemap)
        self.assertNotIn("font_annot_primary", basemap)
        self.assertNotIn("font_label", basemap)

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

    def test_scalebar_applies_configured_fonts_and_body_height(self) -> None:
        """Match scale typography and bar-body height to publication settings."""
        figure = RecordingFigure()
        executor = FigureExecutor(plan(), figure_factory=lambda: figure)
        with patch("pygmt.config") as config:
            config.return_value.__enter__.return_value = None
            executor.apply(
                operation(
                    "figure.scalebar",
                    "scalebar",
                    {
                        "position": "x17.2c/13.4c",
                        "length": "50k",
                        "font_annot_primary": "14p,Helvetica-Bold",
                        "font_label": "14p,Helvetica-Bold",
                        "map_scale_height": "20p",
                    },
                    0,
                )
            )
        config.assert_called_once_with(
            FONT_ANNOT_PRIMARY="14p,Helvetica-Bold",
            FONT_LABEL="14p,Helvetica-Bold",
            MAP_SCALE_HEIGHT="20p",
        )
        scale = figure.calls[-1][1]
        self.assertNotIn("font_annot_primary", scale)
        self.assertNotIn("font_label", scale)
        self.assertNotIn("map_scale_height", scale)

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

    def test_v010_fallback_rejects_untranslatable_embellishment_keys(self) -> None:
        """Fail clearly instead of silently ignoring current-only CFG options."""
        figure = LegacyRecordingFigure()
        executor = FigureExecutor(plan(), figure_factory=lambda: figure)
        with self.assertRaisesRegex(ValueError, r"figure\.scalebar.*height.*PyGMT v0\.10"):
            executor.apply(
                operation(
                    "figure.scalebar",
                    "scalebar",
                    {"position": "BR", "length": "50k", "height": "0.3c"},
                    0,
                )
            )
        with self.assertRaisesRegex(
            ValueError, r"figure\.directional_rose.*labels.*PyGMT v0\.10"
        ):
            executor.apply(
                operation(
                    "figure.directional_rose",
                    "directional_rose",
                    {"position": "TR", "width": "2c", "labels": "W,E,S,N"},
                    1,
                )
            )

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

    def test_enabled_option_is_not_forwarded_to_composite_figure_call(self) -> None:
        """Consume workflow control keys before invoking a PyGMT method."""
        figure = RecordingFigure()
        executor = FigureExecutor(plan(), figure_factory=lambda: figure)
        executor.apply(
            operation(
                "figure.plot.footprint.reference",
                "footprint",
                {
                    "data": str(STUDY_FIXTURES / "reference_footprint.kml"),
                    "pen": "2p,red",
                    "enabled": True,
                },
                0,
            )
        )
        plot = next(kwargs for name, kwargs in figure.calls if name == "plot")
        self.assertNotIn("enabled", plot)

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
        self.assertIn(" 1.5c Reverse fault", content)
        self.assertIn(" 1.5c LT-1 reference image", content)
        self.assertEqual(len(executor.context.legend_items), 5)

    def test_automatic_legend_applies_configured_font(self) -> None:
        """Apply the legend font through a local PyGMT configuration context."""
        figure = RecordingFigure()
        executor = FigureExecutor(plan(), figure_factory=lambda: figure)
        executor.context.legend_items.append(
            {
                "section": "figure.plot.footprint.reference",
                "spec": "S 0.3c - 1c - 2p,red 1c Reference",
            }
        )
        with patch("pygmt.config") as config:
            config.return_value.__enter__.return_value = None
            executor.apply(
                operation(
                    "figure.legend",
                    "legend",
                    {
                        "position": "x16c/0c",
                        "font": "10p,Helvetica",
                        "enabled": True,
                    },
                    0,
                )
            )
        config.assert_called_once_with(FONT_ANNOT_PRIMARY="10p,Helvetica")
        self.assertEqual(figure.calls[-1][0], "legend")
        self.assertNotIn("enabled", figure.calls[-1][1])

    def test_automatic_legend_applies_row_gap_and_box_padding(self) -> None:
        """Keep adjacent legend symbols and labels visually separated."""
        figure = RecordingFigure()
        executor = FigureExecutor(plan(), figure_factory=lambda: figure)
        executor.context.legend_items.extend(
            [
                {"section": "a", "spec": "S 0.3c - 1c - 2p,red 1c First"},
                {"section": "b", "spec": "S 0.3c - 1c - 2p,blue 1c Second"},
            ]
        )
        executor.apply(
            operation(
                "figure.legend",
                "legend",
                {
                    "position": "x16c/0c",
                    "box": True,
                    "row_gap": "0.1c",
                    "padding": "0.25c",
                },
                0,
            )
        )
        legend = figure.calls[-1][1]
        self.assertEqual(legend["spec_content"].count("G 0.1c"), 1)
        self.assertEqual(legend["box"], "+gwhite+p1p+c0.25c")

    def test_automatic_legend_applies_configured_symbol_geometry_without_box(self) -> None:
        """Format fault fronts and footprint lines from one frame-free legend schema."""
        figure = RecordingFigure()
        executor = FigureExecutor(plan(), figure_factory=lambda: figure)
        executor.apply(
            operation(
                "figure.plot.faults",
                "faults",
                {
                    "data": str(STUDY_FIXTURES / "faults.geojson"),
                    "kinematic_field": "Fea_En",
                },
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
                {
                    "position": "x16c/0c",
                    "box": False,
                    "symbol_offset": "1.8c",
                    "line_length": "3c",
                    "front_spacing": "1c",
                    "front_size": "0.25c",
                    "text_offset": "4c",
                },
                2,
            )
        )

        legend = figure.calls[-1][1]
        content = legend["spec_content"]
        self.assertIn(
            "S 1.8c f+l+t 3c/1c/0.25c white 1.5p,black 4c Reverse fault",
            content,
        )
        self.assertIn(
            "S 1.8c f+l+s 3c/1c/0.25c black 1.5p,black 4c Strike-slip fault",
            content,
        )
        self.assertIn(
            "S 1.8c - 3c - 4p,red 4c LT-1 reference image",
            content,
        )
        self.assertIs(legend["box"], False)
        self.assertNotIn("front_size", legend)

    def test_colorbar_applies_intervals_and_fonts(self) -> None:
        """Keep colorbar tick and typography controls aligned with legacy output."""
        figure = RecordingFigure()
        executor = FigureExecutor(plan(), figure_factory=lambda: figure)
        executor.context.resources["figure.grdimage.dem"] = {
            "grid": "/tmp/dem.grd",
            "cmap": "gray",
        }
        executor.context.active_cpt_source = "figure.grdimage.dem"
        with patch("pygmt.config") as config:
            config.return_value.__enter__.return_value = None
            executor.apply(
                operation(
                    "figure.colorbar.dem",
                    "colorbar",
                    {
                        "source": "figure.grdimage.dem",
                        "position": "BC",
                        "annot": 1000.0,
                        "tick": 1000.0,
                        "label": "Elevation",
                        "unit": "m",
                        "font_annot_primary": "10p,Helvetica",
                        "font_label": "12p,Helvetica-Bold",
                    },
                    0,
                )
            )
        config.assert_called_once_with(
            FONT_ANNOT_PRIMARY="10p,Helvetica",
            FONT_LABEL="12p,Helvetica-Bold",
        )
        colorbar = figure.calls[-1][1]
        self.assertEqual(colorbar["frame"], ["xa1000f1000+lElevation", "y+lm"])
        self.assertNotIn("annot", colorbar)
        self.assertNotIn("tick", colorbar)

    def test_colorbar_rejects_a_source_whose_cpt_is_no_longer_active(self) -> None:
        """Avoid silently labelling one raster with a later raster's active CPT."""
        figure = RecordingFigure()
        executor = FigureExecutor(plan(), figure_factory=lambda: figure)
        executor.apply(
            operation(
                "figure.grdimage.dem",
                "grdimage",
                {"grid": "/tmp/dem.grd", "cmap": "gray"},
                0,
            )
        ).apply(
            operation(
                "figure.grdimage.optic",
                "grdimage",
                {"grid": "/tmp/optic.grd", "cmap": "geo"},
                1,
            )
        )
        with self.assertRaisesRegex(ValueError, r"figure\.colorbar\.dem.*active CPT"):
            executor.apply(
                operation(
                    "figure.colorbar.dem",
                    "colorbar",
                    {"source": "figure.grdimage.dem", "position": "BC"},
                    2,
                )
            )

    def test_disabled_operation_may_follow_savefig(self) -> None:
        """Treat savefig as terminal among enabled operations only."""
        figure = RecordingFigure()
        operations = (
            operation("figure.savefig", "savefig", {"fname": "/tmp/a.png"}, 0),
            operation(
                "figure.colorbar.dem",
                "colorbar",
                {"source": "figure.grdimage.dem", "position": "BC", "enabled": False},
                1,
            ),
        )
        FigureExecutor(plan(*operations), figure_factory=lambda: figure).execute()
        self.assertEqual([name for name, _ in figure.calls], ["savefig"])


if __name__ == "__main__":
    unittest.main()
