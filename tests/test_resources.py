from pathlib import Path

from geodesy_visualization.resources import resource_path, resource_root


def test_checkout_resources_resolve_from_repository_root() -> None:
    root = resource_root()
    assert root == Path(__file__).resolve().parents[1]
    assert resource_path("cpt").is_dir()
    assert resource_path(
        "config_examples", "visualization", "deformation_map", "deformation_map.cfg"
    ).is_file()
