"""docutils doctree -> JSON AST.

The AST is the contract between server and client.  It stays faithful to
docutils' own node vocabulary: `type` is the docutils tagname, `props` are the
node's attributes.  Presentation decisions belong to the client.
"""
import hashlib
import io
import json
from collections import Counter

import docutils.core
import docutils.nodes
import docutils.utils

# Attributes docutils puts on every node.  Emitting them when empty triples the
# size of the payload and changes nothing on the client.
_NOISE = ("ids", "classes", "names", "dupnames", "backrefs")

# Types whose identity must survive a props change, so that a component holding
# internal state is updated rather than remounted.
_STABLE = ("component",)

# Containers whose identity must NOT depend on their descendants.  Hashing a
# container over its children would rehash the whole root-to-edit spine on
# every keystroke, remounting an entire section to change one paragraph in it.
# These are keyed structurally instead: by explicit anchor where docutils gives
# one, else by position among siblings of the same type.
_CONTAINERS = (
    "document", "section", "bullet_list", "enumerated_list", "list_item",
    "definition_list", "definition_list_item", "definition", "block_quote",
    "table", "tgroup", "thead", "tbody", "row", "entry", "line_block",
    "field_list", "field", "field_body", "footnote", "citation", "topic",
    "sidebar", "admonition", "note", "warning", "tip", "important", "caution",
    "danger", "error", "hint", "attention", "figure", "container",
)


def _props(node):
    props = {}
    for key, value in node.attributes.items():
        if key in _NOISE and not value:
            continue
        if value == "" or value is None:
            continue
        props[key] = value
    return props


def _digest(type_, props, child_ids):
    # Source line numbers are deliberately excluded: including them would
    # invalidate every id in the document when a line is inserted at the top.
    payload = json.dumps([type_, props, child_ids], sort_keys=True, default=str)
    return hashlib.blake2b(payload.encode(), digest_size=8).hexdigest()


class AstBuilder(docutils.nodes.GenericNodeVisitor):
    """Walks a doctree and builds the JSON AST bottom-up."""

    def __init__(self, document):
        super().__init__(document)
        self.root = None

    @staticmethod
    def _unique(base, ordinals):
        """Disambiguate identical siblings by their occurrence in the parent.

        Two identical siblings hash identically, and a duplicate key is fatal
        to the whole `{#each}` block, not just to the node - so every node must
        go through here, text included.
        """
        seen = ordinals[base]
        ordinals[base] += 1
        return base if seen == 0 else f"{base}~{seen}"

    def build(self, node, ordinals):
        if isinstance(node, docutils.nodes.Text):
            text = node.astext()
            # Text takes the same occurrence counter as every other node. It
            # used to return early, which meant two identical text siblings -
            # the ", " between runs of inline markup, say - shared an id, and
            # Svelte rejects a duplicate key by tearing down the whole render.
            return {"type": "text", "id": self._unique(_digest("text", text, []), ordinals), "value": text}

        type_ = node.tagname
        props = _props(node)

        child_ordinals = Counter()
        children = [self.build(child, child_ordinals) for child in node.children]

        if type_ in _STABLE:
            # Keyed on identity, not content, so prop updates don't remount.
            key = props.get("key") or props.get("name", type_)
            base = f"{type_}:{key}"
        elif type_ in _CONTAINERS:
            anchor = props.get("ids") or props.get("names")
            if anchor:
                base = f"{type_}#{anchor[0]}"
            else:
                base = f"{type_}@{ordinals[type_]}"
                ordinals[type_] += 1
        else:
            base = _digest(type_, props, [c["id"] for c in children])

        out = {"type": type_, "id": self._unique(base, ordinals), "props": props, "children": children}
        if node.line is not None:
            out["line"] = node.line
        return out


def parse(source, filename=None, settings=None):
    """Render reST source to an AST dict.

    System messages are left in the tree as ordinary nodes so that one bad
    directive degrades a region instead of blanking the document.
    """
    overrides = {
        # Keep heading levels literal; don't hoist a lone title out of the body.
        "doctitle_xform": False,
        "sectsubtitle_xform": False,
        "initial_header_level": 1,
        # Report everything; the client decides what to show.
        "report_level": 1,
        "halt_level": 5,
        # Highlighting is a presentation decision and belongs to the client;
        # docutils would otherwise bake Pygments token spans into the tree.
        "syntax_highlight": "none",
        "embed_stylesheet": False,
        "output_encoding": "unicode",
        # Messages already appear in the tree as system_message nodes;
        # keep them off the terminal too.
        "warning_stream": io.StringIO(),
    }
    if settings:
        overrides.update(settings)

    try:
        doctree = docutils.core.publish_doctree(
            source, source_path=filename, settings_overrides=overrides
        )
    except Exception as exc:  # noqa: BLE001 - surfaced to the client as content
        return _fatal(exc, filename)

    builder = AstBuilder(doctree)
    ast = builder.build(doctree, Counter())
    ast["props"].setdefault("source", filename or "<string>")
    return ast


def _fatal(exc, filename):
    message = f"{exc.__class__.__name__}: {exc}"
    return {
        "type": "document",
        "id": "document",
        "props": {"source": filename or "<string>"},
        "children": [
            {
                "type": "system_message",
                "id": "fatal",
                "props": {"level": 4, "type": "SEVERE"},
                "children": [
                    {
                        "type": "paragraph",
                        "id": "fatal-text",
                        "props": {},
                        "children": [
                            {"type": "text", "id": "fatal-msg", "value": message}
                        ],
                    }
                ],
            }
        ],
    }
