"""Custom block directives and prop coercion."""
import json

import pytest

from rstview.directives import load_config, register
from rstview.parse import parse

CONFIG = {
    "chart": {
        "options": {"series": "json", "title": "string", "height": "int", "live": "bool"},
        "required": ["series"],
    },
    "callout": {"options": {"kind": "string"}, "parse_body": True},
}


@pytest.fixture(autouse=True)
def registered():
    register(CONFIG)


def test_directive_becomes_a_component_node(find):
    ast = parse(".. chart::\n   :series: [1, 2]\n", "t.rst")
    node = find(ast, "component")
    assert node is not None
    assert node["props"]["name"] == "chart"


def test_options_are_coerced_to_their_declared_types(find):
    ast = parse(
        ".. chart::\n   :series: [1, 2, 3]\n   :height: 60\n   :live:\n   :title: Speed\n",
        "t.rst",
    )
    props = find(ast, "component")["props"]
    assert props["series"] == [1, 2, 3]
    assert props["height"] == 60
    assert props["live"] is True
    assert props["title"] == "Speed"


def test_positional_argument_is_passed_through(find):
    ast = parse(".. callout:: A title\n\n   Body.\n", "t.rst")
    assert find(ast, "component")["props"]["argument"] == "A title"


def test_parsed_body_yields_child_nodes(find):
    ast = parse(".. callout::\n   :kind: warning\n\n   Body with *emphasis*.\n", "t.rst")
    node = find(ast, "component")
    assert [c["type"] for c in node["children"]] == ["paragraph"]
    assert find(node, "emphasis") is not None


def test_unparsed_body_is_kept_verbatim(find):
    ast = parse(".. chart::\n   :series: []\n\n   *not* reST\n", "t.rst")
    node = find(ast, "component")
    assert node["children"] == []
    assert node["props"]["content"] == "*not* reST"


def test_missing_required_option_is_an_error_node_not_a_crash(find, find_all):
    ast = parse(".. chart::\n   :height: 10\n", "t.rst")
    assert find_all(ast, "system_message")
    assert find(ast, "component") is None


def test_malformed_json_option_degrades_locally(find_all):
    ast = parse("Before.\n\n.. chart::\n   :series: {not json}\n\nAfter.\n", "t.rst")
    assert find_all(ast, "system_message")
    # Surrounding content must still render.
    assert len(find_all(ast, "paragraph")) >= 2


def test_component_identity_survives_a_prop_change():
    """A stateful component should update, not remount, when props change."""
    a = parse(".. chart::\n   :series: [1]\n", "t.rst")
    b = parse(".. chart::\n   :series: [1, 2, 3]\n", "t.rst")

    def component_id(ast):
        node = ast
        while node["type"] != "component":
            node = node["children"][0]
        return node["id"]

    assert component_id(a) == component_id(b)


def test_explicit_key_distinguishes_two_instances(find_all):
    ast = parse(
        ".. chart::\n   :series: [1]\n   :key: left\n\n.. chart::\n   :series: [2]\n   :key: right\n",
        "t.rst",
    )
    ids = [n["id"] for n in find_all(ast, "component")]
    assert len(set(ids)) == 2


def test_load_config_tolerates_a_missing_file():
    assert load_config("does-not-exist.json") == {}


def test_load_config_reads_the_components_block(tmp_path):
    path = tmp_path / "c.json"
    path.write_text(json.dumps({"components": CONFIG}))
    assert set(load_config(str(path))) == {"chart", "callout"}


def test_parsed_literal_keeps_its_inline_markup():
    """The whole point of `parsed-literal` is that the markup survives.

    It arrives as a `literal_block` with element children rather than one text
    node, which is what the client keys off to skip highlighting - flattening
    it to a string for the highlighter would throw the markup away.
    """
    ast = parse(".. parsed-literal::\n\n   plain **bold** and *italic*\n")
    block = ast["children"][0]
    assert block["type"] == "literal_block"
    kinds = [child["type"] for child in block["children"]]
    assert "strong" in kinds and "emphasis" in kinds
    # A highlighted code block, by contrast, is a single run of text.
    code = parse(".. code-block:: python\n\n   x = 1\n")["children"][0]
    assert [child["type"] for child in code["children"]] == ["text"]
    assert "code" in code["props"]["classes"]
