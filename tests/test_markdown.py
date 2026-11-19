"""Markdown through MyST: the same AST contract as reST, plus what MyST and
the client disagree about - raw HTML and links to files."""
import json
import pathlib

import pytest
from starlette.testclient import TestClient

from rstview.app import create_app
from rstview.directives import register
from rstview.library import Library
from rstview.parse import parse, syntax_of

SAMPLES = pathlib.Path(__file__).resolve().parents[1] / "samples"


def md(source, **kwargs):
    return parse(source, "t.md", **kwargs)


def text(node):
    if node["type"] == "text":
        return node["value"]
    return "".join(text(child) for child in node.get("children", []))


def messages(ast, find_all):
    return [text(m) for m in find_all(ast, "system_message")]


# --- Choosing the parser ---------------------------------------------------

@pytest.mark.parametrize("name, expected", [
    ("a.md", "markdown"), ("A.MARKDOWN", "markdown"), ("a.rst", "rst"),
    ("a.txt", "rst"), (None, "rst"),
])
def test_syntax_follows_the_suffix(name, expected):
    assert syntax_of(name) == expected


def test_the_document_says_which_syntax_it_was(find):
    assert md("# Hi\n")["props"]["syntax"] == "markdown"
    assert parse("Hi\n==\n", "t.rst")["props"]["syntax"] == "rst"


def test_syntax_can_be_forced_regardless_of_name(find):
    ast = parse("# Hi\n", "t.rst", syntax="markdown")
    assert find(ast, "section") is not None


def test_markdown_headings_are_sections_like_rest(find):
    ast = md("# Top\n\n## Sub\n\nBody.\n")
    top = find(ast, "section")
    assert top["props"]["ids"][0] == "top"
    assert find(top["children"][1], "title") is not None


# --- Links -----------------------------------------------------------------

def test_a_link_to_a_file_is_a_uri_not_a_missing_name(find_all):
    ast = md("[a](other.md) [b](sub/x.md#intro) [c](guide.rst)\n")
    uris = [r["props"].get("refuri") for r in find_all(ast, "reference")]
    assert uris == ["other.md", "sub/x.md#intro", "guide.rst"]
    assert not find_all(ast, "problematic")
    assert not find_all(ast, "system_message")


def test_a_link_to_a_myst_label_still_resolves(find_all):
    ast = md("(here)=\n# Heading\n\n[go](here)\n")
    reference = find_all(ast, "reference")[0]
    assert reference["props"].get("refid") == "here"


def test_a_dangling_rest_reference_inside_markdown_still_fails_as_rest(find_all):
    ast = md("```{eval-rst}\nSee `nowhere`_.\n```\n")
    assert find_all(ast, "problematic")


def test_github_slugs_and_docutils_ids_both_reach_a_heading(find, find_all):
    ast = md("# What's new?\n\n[a](#whats-new) [b](#what-s-new)\n")
    section = find(ast, "section")
    assert {"what-s-new", "whats-new"} <= set(section["props"]["ids"])
    targets = [r["props"].get("refid") for r in find_all(ast, "reference")]
    assert targets == ["whats-new", "what-s-new"]
    assert not find_all(ast, "system_message")


def test_a_missing_anchor_is_reported(find_all):
    assert messages(md("[x](#nope)\n"), find_all)


# --- What MyST leaves as raw HTML ------------------------------------------

def test_no_raw_html_reaches_the_client_from_common_markdown(find_all):
    source = (
        "~~gone~~ and a hard break  \nnext\\\nlast\n\n"
        "- [ ] open\n- [x] done\n\n"
        "<kbd>K</kbd> <b>b</b> <sub>2</sub>\n"
    )
    ast = md(source)
    assert not find_all(ast, "raw")
    assert len(find_all(ast, "hardbreak")) == 2
    assert [c["props"]["checked"] for c in find_all(ast, "checkbox")] == [False, True]
    assert [h["props"]["tag"] for h in find_all(ast, "html_inline")] == ["s", "kbd"]
    assert find_all(ast, "strong") and find_all(ast, "subscript")
    assert not find_all(ast, "system_message")


def test_html_wrapped_around_markdown_contains_it(find):
    ast = md("<details>\n<summary>More</summary>\n\nInside *here*.\n\n</details>\n\nAfter.\n")
    details = find(ast, "details")
    assert details["children"][0]["type"] == "summary"
    assert text(details["children"][0]) == "More"
    assert "Inside here." in text(details)
    assert "After." not in text(details)


def test_html_attributes_are_allowlisted(find):
    ast = md('<p align="center" onclick="x()" class="lead"><img src="a.png" width="9" onerror="x()"></p>\n')
    paragraph = find(ast, "paragraph")
    assert set(paragraph["props"]["classes"]) == {"lead", "align-center"}
    assert "onclick" not in json.dumps(ast) and "onerror" not in json.dumps(ast)
    image = find(ast, "image")
    assert image["props"]["uri"] == "a.png" and image["props"]["width"] == "9"


def test_scripts_and_their_content_are_dropped(find_all):
    ast = md("Before <script>alert(1)</script> after.\n\n<script>\nevil()\n</script>\n")
    assert "alert" not in json.dumps(ast) and "evil" not in json.dumps(ast)
    assert "Before" in text(ast) and "after." in text(ast)


def test_a_link_to_a_scriptable_scheme_keeps_its_text_only(find_all):
    ast = md('<a href="javascript:alert(1)">click</a>\n')
    assert not find_all(ast, "reference")
    assert "click" in text(ast)
    assert "javascript" not in json.dumps(ast)


def test_unknown_tags_lose_the_tag_and_keep_the_text(find_all):
    ast = md("<table><tr><td>cell</td></tr></table>\n")
    assert not find_all(ast, "raw")
    assert "cell" in text(ast)


def test_a_rule_inside_html_is_dropped_rather_than_warned_about(find_all):
    ast = md("<div><hr></div>\n\n<hr>\n\nAfter.\n")
    assert len(find_all(ast, "transition")) == 1
    assert not find_all(ast, "system_message")


def test_an_html_anchor_is_a_link_target(find, find_all):
    ast = md('<a name="spot"></a>\n\n[jump](#spot)\n')
    assert find_all(ast, "reference")[-1]["props"].get("refid") == "spot"
    assert not find_all(ast, "system_message")


def test_a_style_block_is_left_for_the_client_to_honour(find):
    ast = md("<style>.x { color: red }</style>\n")
    raw = find(ast, "raw")
    assert raw is not None and "color: red" in text(raw)


# --- docutils machinery that has to carry over -----------------------------

def test_code_blocks_are_not_highlighted_server_side(find):
    block = find(md("```python\nx = 1\n```\n"), "literal_block")
    assert [c["type"] for c in block["children"]] == ["text"]


def test_custom_components_work_from_markdown(find):
    register({
        "chart": {"options": {"series": "json"}},
        "callout": {"options": {"kind": "string"}, "parse_body": True},
    })
    ast = md("```{chart}\n:series: [1, 2]\n```\n\n:::{callout}\n:kind: tip\n\n*Body*\n:::\n")
    chart, callout = [n for n in ast["children"] if n["type"] == "component"]
    assert chart["props"]["series"] == [1, 2]
    assert find(callout, "emphasis") is not None


def test_front_matter_becomes_docinfo(find):
    ast = md("---\nauthor: Someone\nproject: x\n---\n\n# T\n")
    docinfo = find(ast, "docinfo")
    assert [c["type"] for c in docinfo["children"]] == ["author", "field"]


def test_config_can_replace_the_extension_list(find):
    assert find(md("$x$\n"), "math") is not None
    assert find(md("$x$\n", markdown={"extensions": []}), "math") is None


def test_config_passes_other_myst_options_through(find):
    ast = md("# A\n\n## B\n", markdown={"heading_anchors": 1})
    sub = find(ast, "section")["children"][1]
    assert "slug" not in sub["props"]


def test_editing_a_paragraph_leaves_its_section_alone(ids, find):
    base = "# One\n\nHello *world*.\n\n# Two\n\nOther.\n"
    before = md(base)
    after = md(base.replace("world", "there"))
    sections = lambda ast: [n["id"] for n in ast["children"] if n["type"] == "section"]
    assert sections(before) == sections(after)
    assert len(ids(before) - ids(after)) <= 3


def test_every_prefix_of_the_sample_renders_without_a_fatal():
    """What a live preview sees while someone types."""
    source = (SAMPLES / "markdown.md").read_text()
    for end in range(0, len(source), 11):
        ast = md(source[:end])
        assert all(child["id"] != "fatal" for child in ast["children"]), source[:end]


# --- Library and server ----------------------------------------------------

def test_the_library_opens_and_lists_markdown(tmp_path):
    (tmp_path / "a.md").write_text("# A\n")
    (tmp_path / "b.rst").write_text("B\n=\n")
    library = Library(str(tmp_path))
    assert library.listing() == ["a.md", "b.rst"]
    assert library.get("a.md").ast["props"]["syntax"] == "markdown"
    kinds = {e["name"]: e["kind"] for e in library.browse("")["entries"]}
    assert kinds == {"a.md": "doc", "b.rst": "doc"}


def test_markdown_options_come_from_the_config_file(tmp_path, find):
    (tmp_path / "a.md").write_text("$x$\n")
    config = tmp_path / "rstview.config.json"
    config.write_text(json.dumps({"markdown": {"extensions": []}}))
    library = Library(str(tmp_path), config=str(config))
    assert find(library.get("a.md").ast, "math") is None


def test_an_unreadable_markdown_file_reports_in_markdown(tmp_path, find):
    path = tmp_path / "a.md"
    path.write_text("# A\n")
    document = Library(str(tmp_path)).get("a.md")
    path.unlink()
    document.render()
    assert find(document.ast, "error") is not None


def test_editing_a_markdown_file_pushes_a_new_version(tmp_path):
    path = tmp_path / "doc.md"
    path.write_text("# Title\n\nOriginal.\n")
    with TestClient(create_app(str(path))) as client:
        with client.websocket_connect("/ws") as ws:
            assert ws.receive_json()["type"] == "ready"
            first = ws.receive_json()
            path.write_text("# Title\n\nEdited.\n")
            second = ws.receive_json()
    assert second["version"] > first["version"]
    assert "Edited" in json.dumps(second["ast"])
