"""Structure and error handling of the AST."""
from rstview.parse import parse

DOC = """\
Title
=====

Hello *world* and ``code``.

- one
- two
"""


def test_document_shape():
    ast = parse(DOC, "t.rst")
    assert ast["type"] == "document"
    assert ast["props"]["source"] == "t.rst"


def test_types_are_docutils_tagnames(find):
    ast = parse(DOC, "t.rst")
    assert find(ast, "emphasis") is not None
    assert find(ast, "literal") is not None
    assert find(ast, "bullet_list") is not None


def test_text_nodes_carry_value(find):
    node = find(parse(DOC, "t.rst"), "text")
    assert "value" in node and "children" not in node


def test_empty_docutils_attributes_are_dropped(find):
    para = find(parse(DOC, "t.rst"), "paragraph")
    assert "dupnames" not in para["props"]
    assert "backrefs" not in para["props"]


def test_source_lines_are_reported(find):
    para = find(parse(DOC, "t.rst"), "paragraph")
    assert para["line"] == 4


def test_bad_directive_becomes_a_node_not_an_exception(find_all):
    ast = parse(DOC + "\n.. nonexistent:: x\n", "t.rst")
    messages = find_all(ast, "system_message")
    assert messages, "unknown directive should surface as a system_message"
    # The rest of the document must survive.
    assert find_all(ast, "bullet_list")


def test_highlighting_is_left_to_the_client(find):
    """docutils must not bake Pygments token spans into the tree."""
    ast = parse(".. code-block:: python\n\n   def f(): pass\n", "t.rst")
    block = find(ast, "literal_block")
    assert [c["type"] for c in block["children"]] == ["text"]
    assert block["children"][0]["value"] == "def f(): pass"
    assert "python" in block["props"]["classes"]


def test_unreadable_source_still_produces_a_document(find):
    ast = parse("=====\nunterminated\n", "t.rst")
    assert ast["type"] == "document"


def test_sections_carry_anchors_for_the_outline(find_all):
    """The sidebar links to sections by fragment, so each needs an id."""
    ast = parse("A\n=\n\nx\n\nB\n-\n\ny\n", "t.rst")
    sections = find_all(ast, "section")
    assert sections
    assert all(s["props"].get("ids") for s in sections)


def test_section_anchors_are_stable_across_body_edits(find_all):
    """Otherwise the outline's links break on every keystroke."""
    def anchors(doc):
        return [s["props"]["ids"][0] for s in find_all(parse(doc, "t.rst"), "section")]

    before = anchors("A\n=\n\noriginal\n\nB\n-\n\ny\n")
    after = anchors("A\n=\n\nedited text\n\nB\n-\n\ny\n")
    assert before == after
