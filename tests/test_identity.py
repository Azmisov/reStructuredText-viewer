"""Node identity.

These are the load-bearing tests for partial updates. The client renders with
keyed {#each}, so an id that changes means a remounted DOM subtree and lost
scroll position, focus, and component state.
"""
import collections
import pathlib
import pytest

from rstview.parse import parse

DOC = """\
=========
 rstview
=========

Introduction
============

Hello *world*.

- first item
- second item

Second Section
==============

Another paragraph.
"""


@pytest.fixture
def churn(ids):
    """(kept, new, gone) node ids between the base doc and an edited one."""
    def measure(edited, base=DOC):
        before = ids(parse(base, "t.rst"))
        after = ids(parse(edited, "t.rst"))
        return len(before & after), len(after - before), len(before - after)
    return measure


def test_identical_input_is_stable(churn):
    kept, new, gone = churn(DOC)
    assert (new, gone) == (0, 0)


def test_editing_a_paragraph_does_not_disturb_its_ancestors(ids, find):
    """The regression this scheme exists to prevent: hashing containers over
    their children rehashed the whole root-to-edit spine on every keystroke."""
    before = parse(DOC, "t.rst")
    after = parse(DOC.replace("Hello *world*.", "Hello *there*."), "t.rst")

    assert before["id"] == after["id"], "document id must survive an edit"

    def section_ids(node, out=None):
        out = {} if out is None else out
        if node["type"] == "section":
            out[node["props"]["ids"][0]] = node["id"]
        for child in node.get("children", []):
            section_ids(child, out)
        return out

    assert section_ids(before) == section_ids(after)


def test_editing_a_paragraph_churns_only_that_paragraph(churn):
    kept, new, gone = churn(DOC.replace("Hello *world*.", "Hello *there*."))
    assert new <= 3 and gone <= 3


def test_reordering_list_items_keeps_every_id(churn):
    kept, new, gone = churn(
        DOC.replace("- first item\n- second item", "- second item\n- first item")
    )
    assert (new, gone) == (0, 0), "reordering must update in place, not remount"


def test_inserting_a_section_preserves_the_existing_ones(ids):
    before = ids(parse(DOC, "t.rst"))
    after = ids(parse(
        DOC.replace("Introduction\n============", "New\n===\n\nBody.\n\nIntroduction\n============"),
        "t.rst",
    ))
    assert len(before - after) <= 2, "inserting at the top must not invalidate the document"


def test_appending_does_not_invalidate_earlier_nodes(ids):
    before = ids(parse(DOC, "t.rst"))
    after = ids(parse(DOC + "\nTrailing paragraph.\n", "t.rst"))
    assert len(before - after) <= 3


def test_line_numbers_are_excluded_from_identity(ids):
    """Otherwise inserting one line at the top would invalidate everything."""
    shifted = ".. a comment\n\n" + DOC
    before = ids(parse(DOC, "t.rst"))
    after = ids(parse(shifted, "t.rst"))
    assert len(before & after) >= len(before) - 2


def test_identical_siblings_get_distinct_ids(ids):
    doc = "Same paragraph.\n\nSame paragraph.\n\nSame paragraph.\n"
    ast = parse(doc, "t.rst")
    paragraphs = [c for c in ast["children"] if c["type"] == "paragraph"]
    assert len(paragraphs) == 3
    assert len({p["id"] for p in paragraphs}) == 3, "duplicate keys break keyed each"


def _sibling_collisions(node):
    """Every id repeated among one node's direct children, recursively."""
    found = []
    children = node.get("children", [])
    counts = collections.Counter(child["id"] for child in children)
    found += [(node["type"], i) for i, n in counts.items() if n > 1]
    for child in children:
        found += _sibling_collisions(child)
    return found


def test_identical_text_siblings_get_distinct_ids():
    """A duplicate key is fatal to the whole `{#each}`, not just to one node.

    Text used to skip the occurrence counter, so a paragraph whose inline
    markup produced the same separator twice - `` `a`, `b`, `c` `` - crashed
    the entire render with `each_key_duplicate`.
    """
    ast = parse("Runs of :emphasis:`a`, :strong:`b`, and :literal:`c` here.\n")
    assert _sibling_collisions(ast) == []


def test_no_sample_has_colliding_sibling_ids():
    samples = pathlib.Path(__file__).resolve().parents[1] / "samples"
    for document in sorted(samples.glob("*.rst")):
        collisions = _sibling_collisions(parse(document.read_text(), document.name))
        assert collisions == [], f"{document.name}: {collisions}"
