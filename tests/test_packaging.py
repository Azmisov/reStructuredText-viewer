"""What the two manifests have to agree on.

The extension and the Python package are cut from one tag by one workflow, so
a version that differs between them names a release that does not exist.
"""
import json
import pathlib
import tomllib

REPO = pathlib.Path(__file__).resolve().parents[1]


def pyproject():
    return tomllib.loads((REPO / "pyproject.toml").read_text(encoding="utf-8"))


def test_the_extension_and_the_package_share_a_version():
    manifest = json.loads((REPO / "extension" / "package.json").read_text(encoding="utf-8"))
    assert manifest["version"] == pyproject()["project"]["version"]


def test_the_client_bundle_is_packaged_despite_being_gitignored():
    """Hatchling honours .gitignore, and the built client lives there.

    Without this the sdist - and the wheel `uv build` derives from it - carry
    a server whose only answer is "Client bundle not built".
    """
    artifacts = pyproject()["tool"]["hatch"]["build"]["artifacts"]
    assert any(pattern.startswith("src/rstview/client") for pattern in artifacts)
