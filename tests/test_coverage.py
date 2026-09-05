"""Guards the client registry against docutils node types it cannot render.

The AST is only useful if the client knows what to do with it. This walks a
document exercising most of reST and fails when a type reaches the client with
no mapping - which would otherwise show up as an Unknown fallback in the page.
"""
import pathlib
import re

import pytest

from rstview.directives import register
from rstview.parse import parse

REGISTRY = pathlib.Path(__file__).resolve().parents[1] / "client" / "src" / "registry.js"

RICH = """\
=========
 Heading
=========

:Author: Someone
:Version: 1.0

Subsection
==========

Paragraph with *emphasis*, **strong**, ``literal``, `title ref`, a
`link <https://example.com>`_, an anonymous `link`__, and a footnote [#f]_
plus a citation [CIT]_.

__ https://example.org

- bullet
- list

1. enumerated
2. list

term
    definition

.. note::

   An admonition.

.. warning::

   Another one.

..

   A block quote.

   -- Attribution

| line block
| second line

+----------+---------+
| Header   | Cells   |
+==========+=========+
| a        | b       |
+----------+---------+

.. code-block:: python

   x = 1

.. image:: pic.png
   :alt: alt text

.. figure:: fig.png

   A caption.

.. |sub| replace:: substituted

Text with |sub|.

.. This is a comment.

----

.. [#f] A footnote.
.. [CIT] A citation.

.. compound::

   Compound first.

   Compound second.

.. topic:: A topic

   Topic body.

.. sidebar:: A sidebar

   Sidebar body.

.. rubric:: A rubric

.. epigraph::

   An epigraph.

.. parsed-literal::

   parsed *literal*

.. list-table:: A list table
   :header-rows: 1

   * - a
     - b
   * - 1
     - 2

.. csv-table:: A csv table
   :header: "x", "y"

   1, 2

.. container:: custom

   Contained.

.. admonition:: Custom title

   Custom admonition body.

.. header:: A page header

.. footer:: A page footer
"""


def _declared():
    source = REGISTRY.read_text()
    names = set()
    for block in ("SIMPLE", "COMPONENTS"):
        body = re.search(rf"export const {block} = \{{(.*?)\n\}};", source, re.S)
        names |= set(re.findall(r"^\s*([a-z_]+)\s*:", body.group(1), re.M))
    for block in ("TRANSPARENT", "HIDDEN"):
        body = re.search(rf"{block} = new Set\(\[?(.*?)\]?\);", source, re.S)
        names |= set(re.findall(r"'([a-z_]+)'", body.group(1)))
    return names | {"text"}


def _types(node, out=None):
    out = set() if out is None else out
    out.add(node["type"])
    for child in node.get("children", []):
        _types(child, out)
    return out


def test_registry_file_is_parseable():
    assert len(_declared()) > 30


def test_rich_document_has_no_unhandled_types():
    register({"chart": {"options": {"series": "json"}}})
    unhandled = _types(parse(RICH, "t.rst")) - _declared()
    assert not unhandled, f"client registry has no mapping for: {sorted(unhandled)}"


@pytest.mark.parametrize(
    "snippet, expected",
    [
        (".. note::\n\n   x\n", "note"),
        (".. image:: a.png\n", "image"),
        (".. figure:: a.png\n\n   cap\n", "figure"),
        ("a\n\nb\n", "paragraph"),
        ("- a\n", "bullet_list"),
        ("term\n    def\n", "definition_list"),
    ],
)
def test_expected_types_are_produced(snippet, expected):
    assert expected in _types(parse(snippet, "t.rst"))


APP_CSS = REGISTRY.parent / "app.css"


def test_plain_stylesheet_has_no_svelte_global_syntax():
    """`:global()` is Svelte <style> syntax. In a plain stylesheet the selectors
    are already global, and the browser discards `:global(...)` as invalid -
    silently, so the rules simply stop applying with no error anywhere."""
    source = APP_CSS.read_text()
    assert ":global(" not in source, (
        "app.css is a plain stylesheet; :global() selectors are dropped by the browser"
    )
