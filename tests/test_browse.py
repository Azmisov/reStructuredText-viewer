"""Directory browsing and pasted-path resolution for the file dialog."""
import os

import pytest

from rstview.library import DocumentError, Library


@pytest.fixture
def library(tmp_path):
    (tmp_path / "index.rst").write_text("Index\n=====\n")
    (tmp_path / "notes.md").write_text("not rest")
    (tmp_path / ".hidden.rst").write_text("Hidden\n======\n")
    (tmp_path / ".config").mkdir()
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "deep.rst").write_text("Deep\n====\n")
    return Library(str(tmp_path))


def names(result):
    return [e["name"] for e in result["entries"]]


def test_browse_lists_directories_and_documents(library):
    assert names(library.browse("")) == ["sub", "index.rst"]


def test_hidden_entries_are_excluded_by_default(library):
    assert ".hidden.rst" not in names(library.browse(""))
    assert ".config" not in names(library.browse(""))


def test_hidden_entries_can_be_shown(library):
    listed = names(library.browse("", show_hidden=True))
    assert ".config" in listed and ".hidden.rst" in listed


def test_non_rest_files_are_excluded_by_default(library):
    assert "notes.md" not in names(library.browse(""))


def test_non_rest_files_can_be_shown(library):
    assert "notes.md" in names(library.browse("", show_all=True))


def test_directories_sort_before_documents(library):
    kinds = [e["kind"] for e in library.browse("", show_all=True)["entries"]]
    assert kinds == sorted(kinds, key=lambda k: {"dir": 0, "doc": 1, "file": 2}[k])


def test_browse_reports_the_parent(library):
    assert library.browse("")["parent"] is None
    assert library.browse("sub")["parent"] == ""


def test_entries_carry_a_library_relative_path(library):
    entry = next(e for e in library.browse("sub")["entries"] if e["name"] == "deep.rst")
    assert entry["path"] == "sub/deep.rst"


@pytest.mark.parametrize("attack", ["..", "../..", "/etc", "sub/../..", "/"])
def test_browse_refuses_paths_outside_the_root(library, attack):
    with pytest.raises(DocumentError):
        library.browse(attack)


def test_browse_refuses_a_file(library):
    with pytest.raises(DocumentError):
        library.browse("index.rst")


def test_locate_accepts_a_relative_path(library):
    assert library.locate("sub/deep.rst") == {"path": "sub/deep.rst", "kind": "doc"}


def test_locate_accepts_an_absolute_path_inside_the_root(library, tmp_path):
    result = library.locate(str(tmp_path / "sub" / "deep.rst"))
    assert result == {"path": "sub/deep.rst", "kind": "doc"}


def test_locate_reports_directories_so_the_dialog_can_navigate(library):
    assert library.locate("sub") == {"path": "sub", "kind": "dir"}


def test_locate_refuses_a_path_outside_the_root(library):
    with pytest.raises(DocumentError) as excinfo:
        library.locate("/etc/passwd")
    # The message must say why, and how to widen the boundary.
    assert "--root" in str(excinfo.value)


def test_locate_refuses_a_missing_path(library):
    with pytest.raises(DocumentError):
        library.locate("nowhere.rst")


def test_locate_rejects_an_empty_path(library):
    with pytest.raises(DocumentError):
        library.locate("   ")


def test_symlinked_entry_out_of_the_tree_is_omitted(library, tmp_path):
    outside = tmp_path.parent / "elsewhere.rst"
    outside.write_text("Elsewhere\n=========\n")
    try:
        os.symlink(outside, tmp_path / "escape.rst")
    except OSError:
        pytest.skip("symlinks unavailable")
    assert "escape.rst" not in names(library.browse(""))
