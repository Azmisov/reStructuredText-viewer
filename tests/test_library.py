"""Document library, and the path containment boundary.

Serving a directory instead of one file makes containment a security boundary:
a client supplies the path, so `resolve` is the only thing standing between a
link in a document and the rest of the filesystem.
"""
import os

import pytest

from rstview.library import DocumentError, Library


@pytest.fixture
def library(tmp_path):
    (tmp_path / "index.rst").write_text("Index\n=====\n\nsee `other <other.rst>`_\n")
    (tmp_path / "other.rst").write_text("Other\n=====\n\nbody\n")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "deep.rst").write_text("Deep\n====\n")
    (tmp_path / "secret.txt.bak").write_text("nope")
    (tmp_path / "notes.md").write_text("nope")
    return Library(str(tmp_path))


def test_resolves_a_document_in_the_root(library, tmp_path):
    assert library.resolve("index.rst") == str(tmp_path / "index.rst")


def test_resolves_a_nested_document(library, tmp_path):
    assert library.resolve("sub/deep.rst") == str(tmp_path / "sub" / "deep.rst")


@pytest.mark.parametrize(
    "attack",
    [
        "../outside.rst",
        "../../etc/passwd",
        "sub/../../outside.rst",
        "/etc/passwd",
        "/etc/hosts",
        "sub/./../../outside.rst",
    ],
)
def test_traversal_is_rejected(library, attack):
    with pytest.raises(DocumentError):
        library.resolve(attack)


def test_symlink_out_of_the_tree_is_rejected(library, tmp_path):
    """realpath is resolved before the containment check, so a symlink cannot
    be used to step outside the root."""
    outside = tmp_path.parent / "outside.rst"
    outside.write_text("Outside\n=======\n")
    link = tmp_path / "escape.rst"
    try:
        os.symlink(outside, link)
    except OSError:
        pytest.skip("symlinks unavailable")
    with pytest.raises(DocumentError):
        library.resolve("escape.rst")


def test_non_rest_files_are_rejected(library):
    for name in ("notes.md", "secret.txt.bak"):
        with pytest.raises(DocumentError):
            library.resolve(name)


def test_missing_document_is_rejected(library):
    with pytest.raises(DocumentError):
        library.resolve("absent.rst")


def test_empty_path_is_rejected(library):
    with pytest.raises(DocumentError):
        library.resolve("")


def test_documents_are_cached_and_reused(library):
    assert library.get("index.rst") is library.get("index.rst")


def test_relative_maps_a_path_back_to_the_library(library, tmp_path):
    assert library.relative(str(tmp_path / "sub" / "deep.rst")) == "sub/deep.rst"


def test_relative_returns_none_outside_the_root(library, tmp_path):
    assert library.relative(str(tmp_path.parent / "elsewhere.rst")) is None


def test_filesystem_root_contains_everything(tmp_path):
    """A loopback server defaults to root "/", where naive prefix matching
    against root + os.sep yields "//" and rejects every real path."""
    doc = tmp_path / "a.rst"
    doc.write_text("A\n=\n")
    library = Library("/")
    assert library.resolve(str(doc)) == str(doc.resolve())
    assert library.relative(str(doc)) == str(doc.resolve()).lstrip("/")


def test_filesystem_root_still_rejects_non_rest_files(tmp_path):
    other = tmp_path / "a.md"
    other.write_text("x")
    with pytest.raises(DocumentError):
        Library("/").resolve(str(other))


def test_assets_are_contained_like_documents(tmp_path):
    """Images are read through `resolve_asset`, which drops the suffix check.

    Widening *what* may be read must not widen *where*: the same realpath and
    containment rules still apply, or an `.. image:: ../../../etc/passwd` in
    someone else's document would read it.
    """
    root = tmp_path / "root"
    (root / "sub").mkdir(parents=True)
    (root / "sub" / "pic.png").write_bytes(b"\x89PNG")
    (tmp_path / "outside.png").write_bytes(b"\x89PNG")
    (root / "escape.png").symlink_to(tmp_path / "outside.png")

    library = Library(str(root))

    assert library.resolve_asset("sub/pic.png") == str((root / "sub" / "pic.png").resolve())

    for bad in ("../outside.png", "/etc/passwd", "escape.png", "sub", ""):
        with pytest.raises(DocumentError):
            library.resolve_asset(bad)
