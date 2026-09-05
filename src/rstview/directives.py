"""Custom block directives that become client components.

A component is declared in config, not in code:

    {"components": {"chart": {"options": {"series": "json", "height": "int"}}}}

which makes ``.. chart::`` available in documents.  The directive puts a
``component`` node in the doctree carrying the coerced options as props; the
client's registry maps the name to a Svelte component.
"""
import json

from docutils import nodes
from docutils.parsers.rst import Directive, directives


class component(nodes.General, nodes.Element):
    """Doctree node for a custom block. `tagname` is 'component'."""


def _flag(argument):
    # Presence alone means true; ``:name: false`` still reads as false.
    if argument is None or argument.strip() == "":
        return True
    return argument.strip().lower() not in ("false", "no", "0", "off")


def _json(argument):
    try:
        return json.loads(argument)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"expected JSON: {exc}") from exc


COERCERS = {
    "string": directives.unchanged,
    "text": directives.unchanged,
    "int": int,
    "float": float,
    "bool": _flag,
    "flag": _flag,
    "json": _json,
}


def build_directive(name, spec):
    """Create a Directive class for one configured component."""
    options = spec.get("options", {})
    parse_body = spec.get("parse_body", False)
    required = set(spec.get("required", []))

    option_spec = {key: COERCERS.get(kind, directives.unchanged)
                   for key, kind in options.items()}
    # `key` lets an author pin a component's identity so that editing its
    # options updates the instance instead of remounting it.
    option_spec.setdefault("key", directives.unchanged)

    class ComponentDirective(Directive):
        has_content = True
        # One optional positional argument, conventionally a title or label.
        required_arguments = 0
        optional_arguments = 1
        final_argument_whitespace = True
        option_spec = None  # replaced below

        def run(self):
            missing = required - set(self.options)
            if missing:
                message = self.state_machine.reporter.error(
                    f"{name}: missing required option(s): {', '.join(sorted(missing))}",
                    nodes.literal_block(self.block_text, self.block_text),
                    line=self.lineno,
                )
                return [message]

            props = dict(self.options)
            props["name"] = name
            if self.arguments:
                props["argument"] = self.arguments[0]

            node = component("\n".join(self.content), **props)
            node.line = self.lineno

            if parse_body:
                # Body is reST: parse it into real child nodes.
                self.state.nested_parse(self.content, self.content_offset, node)
            elif self.content:
                # Body is opaque: hand it over verbatim.
                node["content"] = "\n".join(self.content)

            return [node]

    ComponentDirective.option_spec = option_spec
    ComponentDirective.__name__ = f"{name.title()}Directive"
    return ComponentDirective


def register(components):
    """Register configured components as reST directives.

    docutils' directive table is global, so this is idempotent by name.
    """
    for name, spec in (components or {}).items():
        directives.register_directive(name, build_directive(name, spec))


def load_config(path):
    """Read a component config file. Missing file means no components."""
    if not path:
        return {}
    try:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle).get("components", {})
    except FileNotFoundError:
        return {}
