"""Markdown, through MyST, into the same doctree reST produces.

MyST parses Markdown straight to docutils nodes, so everything downstream -
the AST builder, node identity, the client registry, custom directives - is
shared with reST rather than duplicated. What this module adds is the part
where Markdown and docutils disagree:

- **HTML.** Markdown leans on inline HTML, and MyST keeps it as `raw` nodes,
  which the client drops by design (see `Raw.svelte`). Hard breaks, task-list
  checkboxes and strikethrough arrive the same way. `HtmlToNodes` rebuilds an
  allowlisted subset as real nodes; everything else loses its tags and keeps
  its text, and nothing is ever handed to the client as markup.
- **Links.** A Markdown link to `other.md` is a path, as on GitHub. MyST under
  plain docutils treats it as a reference *name* and reports it missing.
  `RelativeLinks` turns those back into URIs before docutils gives up on them.
"""
import re
from html.parser import HTMLParser

from docutils import nodes
from docutils.transforms import Transform
from docutils.transforms.references import DanglingReferences

try:
    from myst_parser.parsers.docutils_ import Parser as _MystParser
except ImportError as exc:  # pragma: no cover - a broken install, not a state
    raise ImportError(
        "Markdown support needs myst-docutils: pip install myst-docutils"
    ) from exc


# GitHub-flavoured where GitHub has an answer, MyST where it does not and the
# syntax cannot be mistaken for ordinary prose. Left out on purpose:
# `fieldlist` (a paragraph opening with an emoji shortcode like `:tada:`
# becomes a field list), `substitution` (any `{{ }}` in prose, common in docs
# about templating, is evaluated as Jinja), `smartquotes`/`replacements`
# (rewrite text the author typed), `linkify` (needs another dependency, and
# `gfm_autolink` covers it), and `html_image` (`HtmlToNodes` handles every
# image, not only those alone in their block).
EXTENSIONS = (
    "alert",
    "amsmath",
    "attrs_block",
    "attrs_inline",
    "colon_fence",
    "deflist",
    "dollarmath",
    "gfm_autolink",
    "html_admonition",
    "strikethrough",
    "tasklist",
)

DEFAULTS = {
    "myst_enable_extensions": list(EXTENSIONS),
    # GitHub-style slugs, so `[see](#some-heading)` finds the heading.
    "myst_heading_anchors": 6,
    # Highlighting is the client's job, exactly as for reST.
    "myst_highlight_code_blocks": False,
    # HtmlToNodes gives strikethrough a real node; the warning is moot.
    "myst_suppress_warnings": ["myst.strikethrough"],
}


def settings(options=None):
    """docutils settings for a Markdown parse.

    `options` is the `markdown` object from the component config: MyST's own
    option names without the `myst_` prefix, with `extensions` replacing the
    default extension list outright.
    """
    out = {key: list(value) if isinstance(value, list) else value
           for key, value in DEFAULTS.items()}
    for key, value in (options or {}).items():
        if key == "extensions":
            out["myst_enable_extensions"] = list(value)
        else:
            out[f"myst_{key}"] = value
    return out


# --- Nodes with no docutils equivalent ------------------------------------

class hardbreak(nodes.Inline, nodes.Element):
    """A forced line break: two trailing spaces, a trailing backslash, `<br>`."""


class checkbox(nodes.Inline, nodes.Element):
    """A task list item's box. `checked` is a bool."""


class html_inline(nodes.Inline, nodes.TextElement):
    """An allowlisted inline HTML element docutils has no node for; `tag`
    names it. The client checks the tag against its own list again."""


class details(nodes.General, nodes.Element):
    """`<details>`, with its `summary` as first child when it has one."""


class summary(nodes.Part, nodes.TextElement):
    """`<summary>`."""


# --- HTML to nodes ---------------------------------------------------------

def _inline(cls):
    return lambda tag, attrs: cls()


def _tagged(tag, attrs):
    node = html_inline(tag={"strike": "s"}.get(tag, tag))
    if attrs.get("title"):
        node["title"] = attrs["title"]
    return node


def _enumerated(tag, attrs):
    node = nodes.enumerated_list(enumtype="arabic", prefix="", suffix=".")
    if (attrs.get("start") or "").isdigit():
        node["start"] = int(attrs["start"])
    return node


SAFE_SCHEME = re.compile(r"^(?:https?:|mailto:|ftp:|#|[^:]*$)", re.I)


def _anchor(tag, attrs):
    href = (attrs.get("href") or "").strip()
    if href and SAFE_SCHEME.match(href):
        node = nodes.reference()
        if href.startswith("#"):
            node["refid"] = href[1:]
        else:
            node["refuri"] = href
        return node
    # `<a name="x"></a>`: an anchor to jump to, not a link. Or a link to a
    # scheme that can run script, which keeps its text and loses the link.
    return nodes.inline()


def _image(tag, attrs):
    if not attrs.get("src"):
        return None
    node = nodes.image(uri=attrs["src"])
    for key in ("alt", "width", "height", "title"):
        if attrs.get(key):
            node[key] = attrs[key]
    if attrs.get("align") in ("left", "center", "right"):
        node["align"] = attrs["align"]
    return node


def _checkbox(tag, attrs):
    if (attrs.get("type") or "").lower() != "checkbox":
        return None
    return checkbox(checked="checked" in attrs)


def _rubric(tag, attrs):
    # A heading inside HTML cannot open a section - sections come from the
    # Markdown structure - so it is a heading in appearance only.
    return nodes.rubric(classes=[tag])


# Tag -> factory(tag, attrs) returning a node, or None to drop the element.
ELEMENTS = {
    "b": _inline(nodes.strong),
    "strong": _inline(nodes.strong),
    "i": _inline(nodes.emphasis),
    "em": _inline(nodes.emphasis),
    "code": _inline(nodes.literal),
    "tt": _inline(nodes.literal),
    "sub": _inline(nodes.subscript),
    "sup": _inline(nodes.superscript),
    "a": _anchor,
    "span": _inline(nodes.inline),
    **{tag: _tagged for tag in (
        "abbr", "cite", "del", "dfn", "ins", "kbd", "mark", "q", "s", "samp",
        "small", "strike", "u", "var",
    )},
    "p": lambda tag, attrs: nodes.paragraph(),
    "div": lambda tag, attrs: nodes.container(),
    "center": lambda tag, attrs: nodes.container(classes=["align-center"]),
    "blockquote": lambda tag, attrs: nodes.block_quote(),
    "pre": lambda tag, attrs: nodes.literal_block(),
    "ul": lambda tag, attrs: nodes.bullet_list(),
    "ol": _enumerated,
    "li": lambda tag, attrs: nodes.list_item(),
    "details": lambda tag, attrs: details(),
    "summary": lambda tag, attrs: summary(),
    **{f"h{level}": _rubric for level in range(1, 7)},
    # Void elements.
    "br": lambda tag, attrs: hardbreak(),
    "hr": lambda tag, attrs: nodes.transition(),
    "img": _image,
    "input": _checkbox,
}

VOID = frozenset({"br", "hr", "img", "input", "wbr", "source", "meta", "link",
                  "area", "base", "col", "embed", "param", "track"})

# Elements whose *content* goes too, not only their tags.
DROPPED = frozenset({"script", "style", "iframe", "object", "embed", "noscript",
                     "template", "textarea", "select", "button", "svg", "math",
                     "head", "title"})

CLASS_NAME = re.compile(r"^[A-Za-z_][\w-]*$")


class _Tokens(HTMLParser):
    """One raw fragment as a flat list of start/end/text events."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.events = []

    def handle_starttag(self, tag, attrs):
        self.events.append(("start", tag, dict(attrs)))
        if tag in VOID:
            self.events.append(("end", tag, None))

    def handle_startendtag(self, tag, attrs):
        self.events.append(("start", tag, dict(attrs)))
        self.events.append(("end", tag, None))

    def handle_endtag(self, tag):
        if tag not in VOID:
            self.events.append(("end", tag, None))

    def handle_data(self, data):
        self.events.append(("text", data, None))


def _takes_inline(node):
    return isinstance(node, (nodes.TextElement, nodes.Inline))


class _Builder:
    """Rebuilds one element's children, folding HTML tags into nodes.

    Tags and ordinary nodes interleave: Markdown between `<details>` and
    `</details>` arrives as sibling nodes between two raw fragments, so the
    open-element stack spans fragments rather than living inside one.
    """

    def __init__(self, document, parent):
        self.document = document
        self.parent = parent
        self.out = []
        self.stack = []  # (tag or None for an implicit paragraph, node)
        self.dropping = []  # tags whose content is being discarded
        self.line = None
        self.anchored = []  # nodes given an id from HTML

    def _top(self):
        return self.stack[-1][1] if self.stack else self.parent

    def _append(self, node):
        if self.stack:
            self.stack[-1][1].append(node)
        else:
            self.out.append(node)

    def add(self, node):
        if self.dropping:
            return
        if isinstance(node, (nodes.Text, nodes.Inline)):
            if not _takes_inline(self._top()):
                if isinstance(node, nodes.Text) and not node.strip():
                    return  # whitespace between blocks
                paragraph = nodes.paragraph()
                paragraph.line = self.line
                self.add(paragraph)
                self.stack.append((None, paragraph))
        else:
            # A block closes whatever inline context is open, as in HTML.
            while self.stack and _takes_inline(self.stack[-1][1]):
                self.stack.pop()
        self._append(node)

    def start(self, tag, attrs):
        if tag in DROPPED or self.dropping:
            if tag not in VOID:
                self.dropping.append(tag)
            return
        factory = ELEMENTS.get(tag)
        if factory is None:
            return  # unknown element: its content stays, its tag goes
        if tag == "code" and isinstance(self._top(), nodes.literal_block):
            return  # `<pre><code>` is one block, not a block holding a span
        if tag == "p" and self.stack and isinstance(self.stack[-1][1], nodes.paragraph):
            self.stack.pop()
        if tag == "hr" and (self.stack or not isinstance(self.parent, (nodes.section, nodes.document))):
            # docutils allows a transition only between sections' children,
            # and says so on the page; a rule inside a <div> is not worth that.
            return
        node = factory(tag, attrs)
        if node is None:
            return
        node.line = self.line
        self._attributes(node, tag, attrs)
        self.add(node)
        if tag not in VOID:
            self.stack.append((tag, node))

    def end(self, tag):
        if self.dropping:
            if self.dropping[-1] == tag:
                self.dropping.pop()
            return
        for depth in range(len(self.stack) - 1, -1, -1):
            if self.stack[depth][0] == tag:
                del self.stack[depth:]
                return
        # A close tag with nothing open to close: ignored, as browsers do.

    def text(self, data):
        self.add(nodes.Text(data))

    def _attributes(self, node, tag, attrs):
        classes = [c for c in (attrs.get("class") or "").split() if CLASS_NAME.match(c)]
        align = (attrs.get("align") or "").lower()
        if align in ("left", "center", "right") and tag != "img":
            classes.append(f"align-{align}")
        node["classes"].extend(classes)
        anchor = attrs.get("id") or (attrs.get("name") if tag == "a" else None)
        if anchor and anchor.strip():
            # Kept verbatim: `<a href="#my_anchor">` must still land on it.
            node["ids"].append(anchor.strip())
            node["names"].append(nodes.fully_normalize_name(anchor))
            self.anchored.append(node)

    def feed(self, raw):
        # MyST numbers block HTML reliably and inline HTML not at all (0, or
        # whatever line it last saw), so inline nodes take their paragraph's.
        self.line = self.parent.line if _takes_inline(self.parent) else raw.line
        parser = _Tokens()
        parser.feed(raw.astext())
        parser.close()
        for kind, value, attrs in parser.events:
            if kind == "start":
                self.start(value, attrs)
            elif kind == "end":
                self.end(value)
            else:
                self.text(value)


def _convertible(node):
    if not isinstance(node, nodes.raw):
        return False
    if node.get("format") == "latex":
        # Never shown, and MyST writes every hard break twice: once as HTML,
        # once as LaTeX. Dropped along with the HTML it shadows.
        return True
    # A style block is the one piece of raw HTML the client honours.
    return node.get("format") == "html" and "<style" not in node.astext().lower()


class HtmlToNodes(Transform):
    """Replace raw HTML fragments with the allowlisted nodes they spell."""

    # Early: before reference resolution (460+) so HTML anchors are targets,
    # and before MyST's anchor resolution (879) so `[x](#anchor)` finds them.
    default_priority = 205

    def apply(self):
        parents = [element for element in self.document.findall(nodes.Element)
                   if any(_convertible(child) for child in element.children)]
        for parent in parents:
            builder = _Builder(self.document, parent)
            for child in list(parent.children):
                if not _convertible(child):
                    builder.add(child)
                elif child.get("format") == "html":
                    builder.feed(child)
            for child in builder.out:
                child.parent = None
            parent.children = []
            parent.extend(builder.out)
            for node in builder.anchored:
                self.document.note_explicit_target(node, node)


class RelativeLinks(Transform):
    """`[text](other.md)` is a link to a file, not a reference by name.

    MyST hands any link without a recognised scheme to docutils as a
    `refname`, which would only resolve against a target of that name. One
    still unresolved just before docutils reports it dangling is a path, and
    becomes the URI it was written as - the client decides whether that is
    another document. References from reST (`{eval-rst}`) carry a `name` and
    are left to fail as reST would.
    """

    default_priority = DanglingReferences.default_priority - 5

    def apply(self):
        for node in self.document.findall(nodes.reference):
            if "refname" not in node or "name" in node or node.get("refuri") or node.get("refid"):
                continue
            refname = node["refname"]
            if self.document.nameids.get(nodes.fully_normalize_name(refname)):
                # A MyST `(label)=` by that name. DanglingReferences is what
                # resolves internal names, so it is left for that to do.
                continue
            del node["refname"]
            node["refuri"] = refname
            waiting = self.document.refnames.get(refname)
            if waiting and node in waiting:
                waiting.remove(node)


class Anchors(Transform):
    """Make both spellings of a heading's anchor work.

    docutils ids a heading `What's new?` as `what-s-new`; GitHub, and every
    Markdown link written against it, says `whats-new`. MyST resolves
    `[x](#whats-new)` within a document from the slug it records, but a
    fragment arriving from *another* document is matched by the browser
    against element ids - so the slug becomes an id as well. And the reverse:
    `[x](#what-s-new)` names the docutils id, which MyST alone would report
    missing.
    """

    # Just ahead of MyST's ResolveAnchorIds, which reports what it cannot find.
    default_priority = 878

    def apply(self):
        for section in self.document.findall(nodes.section):
            slug = section.get("slug")
            if slug and slug not in self.document.ids:
                section["ids"].append(slug)
                self.document.ids[slug] = section
        for node in self.document.findall(nodes.reference):
            target = (node.get("refuri") or "")[1:]
            if node.get("id_link") and target in self.document.ids:
                del node["refuri"], node["id_link"]
                node["refid"] = target


class Parser(_MystParser):
    def get_transforms(self):
        return super().get_transforms() + [HtmlToNodes, Anchors, RelativeLinks]
