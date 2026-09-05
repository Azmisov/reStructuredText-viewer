"""The recorded transcript the published demo replays.

Nothing here is committed - the fixtures are build output - so these tests are
what stops the demo breaking unnoticed: the static transport reads exactly
these keys, and a corpus that grows a document or an image must still be
completely covered by what the generator writes.
"""
import importlib.util
import json
import pathlib

import pytest

REPO = pathlib.Path(__file__).resolve().parents[1]
SAMPLES = REPO / "samples"


@pytest.fixture(scope="module")
def fixtures():
    """`scripts/` is tooling, not a package, so it is loaded by path."""
    spec = importlib.util.spec_from_file_location("fixtures", REPO / "scripts" / "fixtures.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def recorded(fixtures, tmp_path_factory):
    out = tmp_path_factory.mktemp("demo")
    fixtures.main(["--out", str(out), "--samples", str(SAMPLES)])
    return out, json.loads((out / "fixtures.json").read_text(encoding="utf-8"))


def test_every_document_in_the_corpus_has_an_ast(recorded):
    out, manifest = recorded
    listed = sorted(p.name for p in SAMPLES.glob("*.rst"))
    assert sorted(manifest["documents"]) == listed
    for relpath in manifest["documents"]:
        message = json.loads((out / manifest["docs"][relpath]).read_text(encoding="utf-8"))
        assert message["type"] == "doc" and message["path"] == relpath
        assert message["ast"]


def test_the_entry_document_is_one_of_them(recorded):
    _, manifest = recorded
    assert manifest["entry"] in manifest["docs"]


def test_the_dialog_can_open_at_every_toggle_combination(recorded, fixtures):
    """The transport builds these keys; a missing one is a dialog that goes
    blank when someone ticks a checkbox."""
    _, manifest = recorded
    for hidden in (False, True):
        for all_files in (False, True):
            key = fixtures.browse_key("", hidden, all_files)
            assert manifest["browse"][key]["type"] == "browse"


def test_non_documents_appear_only_under_show_all(recorded, fixtures):
    _, manifest = recorded
    plain = manifest["browse"][fixtures.browse_key("", False, False)]
    everything = manifest["browse"][fixtures.browse_key("", False, True)]
    assert "chart.svg" not in {e["name"] for e in plain["entries"]}
    assert "chart.svg" in {e["name"] for e in everything["entries"]}


def test_paths_resolve_in_both_the_spellings_the_page_shows(recorded, fixtures):
    _, manifest = recorded
    assert manifest["locate"]["index.rst"]["kind"] == "doc"
    assert manifest["locate"][f"{fixtures.DEMO_ROOT}/index.rst"]["kind"] == "doc"


def test_the_build_machine_is_not_published(recorded):
    """The real root is wherever CI checked the repository out."""
    out, manifest = recorded
    assert manifest["root"] == "/samples"
    assert str(REPO) not in (out / "fixtures.json").read_text(encoding="utf-8")


def test_images_the_samples_point_at_are_copied(recorded):
    out, _ = recorded
    assert (out / "media" / "chart.svg").exists()
    assert not list((out / "media").glob("*.rst"))
