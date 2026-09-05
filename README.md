# reStructuredText-viewer

Live-reloading reStructuredText previewer. Edit a `.rst` file, see it update in
the browser — without losing your scroll position, your settings, or the state
of anything on the page.

**[Try it](https://azmisov.github.io/reStructuredText-viewer/)** — the sample
corpus, rendered by the real client against recorded server responses. Reading,
navigation, settings and the file dialog all work; only live reloading is
missing, since nothing is watching a file.

```sh
uv venv && uv pip install -e .
pnpm --dir client install && pnpm --dir client build
rstview samples/index.rst
```

## Using it

```sh
rstview                      # start with nothing open; pick a file in the browser
rstview samples/index.rst    # open a document
rstview --port 0             # random free port instead of the default 5686
rstview --root ~/notes       # restrict reachable documents to a directory
rstview --dev samples/index.rst   # also run Vite, for working on the client
```

The port defaults to **5686** so a pinned browser tab survives a restart.

**Open…** in the top bar (or `Ctrl/Cmd+O`) browses the filesystem server-side —
the browser cannot hand over a real path, so the dialog is served rather than
native. It filters hidden and non-reST entries, switches between list and icon
views, and accepts a pasted path.

A link pointing at another local `.rst` file loads that document into the page
instead of navigating away, so scroll, settings and loaded syntax grammars all
survive. Back works.

Images are served from beside the document they appear in, under the same
containment rules. Maths — `.. math::` and the `:math:` role — renders with
KaTeX, loaded only when a document actually contains a formula.

By default `--root` is the whole filesystem, which is safe because the server
binds loopback only. Bind it anywhere else and the root narrows to the starting
document's directory; everything outside is refused.

### Settings

The gear icon opens a panel persisted to `localStorage`: light/dark/system,
spacing, font size, content width and position, code line numbers, line
wrapping, and separate light and dark syntax themes (all 65 Shiki themes).

### Styling from inside a document

A `.. raw:: html` block's **stylesheet** is honoured — somewhere to define the
classes that `.. class::` and custom roles attach — while raw markup stays
dropped. The rules are scoped to the document body, so a stylesheet cannot
reach the viewer's own chrome, and `@import` is stripped.

### Custom blocks

Directives are declared in `rstview.config.json`, not in code, and map to Svelte
components:

```json
{"components": {
  "chart": {"options": {"series": "json", "height": "int"},
            "required": ["series"], "parse_body": false}
}}
```

That makes `.. chart::` available in documents; `client/src/components/index.js`
maps the name to a component. The config is re-read on each render, so adding
one needs no restart.

### VS Code

`extension/` is a VS Code extension wrapping the same renderer. **Open Preview
to the Side** (`Ctrl/Cmd+Shift+V`) spawns `python -m rstview --stdio` and pipes
it into a webview, with the workspace folder as the root.

```sh
pnpm --dir extension install
pnpm --dir extension build      # vendors Python, builds the client, compiles TS
pnpm --dir extension package    # -> extension/*.vsix
```

The extension bundles docutils and the renderer, so it needs only a Python
3.10+ interpreter — nothing to install into it. `pnpm run vendor` builds
`extension/python/` from `pyproject.toml`.

The preview follows the editor as you type, unsaved changes included, and
matches your colour theme — including syntax highlighting, which is driven by
your actual theme JSON rather than an approximation of it. Scroll sync between
source and preview is still to come; see
[docs/VSCODE_PLAN.md](docs/VSCODE_PLAN.md).

### Embedding

`rstview --stdio` runs no server and speaks the same JSON messages over
stdin/stdout, one object per line. That is how the extension talks to it, and
anything else can too.

## Tech stack

| | |
|---|---|
| **Parsing** | docutils — the reference implementation, and reST has no formal grammar to generate a parser from |
| **Server** | Starlette + uvicorn, watchdog for file events |
| **Wire format** | a JSON AST over a WebSocket, not HTML |
| **Client** | Svelte 5 (runes), built with Vite |
| **Highlighting** | Shiki, in the browser — themes load lazily, so switching one costs no rebuild |
| **Maths** | KaTeX, lazily loaded with its own fonts, so a formula looks the same everywhere |

The server describes the document and the client decides how it looks. That is
the single decision the rest follows from: theming, custom components and the
outline are client changes rather than docutils translator subclasses, and
partial updates fall out for free because every node carries a stable id.

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the AST contract and how
those ids are assigned, [docs/DECISIONS.md](docs/DECISIONS.md) for why the
less obvious parts are the way they are, and [docs/TODO.md](docs/TODO.md) for
what is left.

## Samples

`samples/` is a small multi-document set — cross-document links, custom blocks,
and a right-to-left document. `samples/directives.rst` exercises every
directive docutils ships with, which is also what `tests/test_coverage.py`
checks the renderer against.

It is also what the published demo shows. `scripts/fixtures.py` records what a
real session would answer for these documents, and the demo's transport replays
that, so the demo renders through the same code the app does and cannot drift
from it.

## Develop

```sh
uv pip install -e ".[test]" && pytest
pnpm --dir client build              # the bundle the server serves
pnpm --dir extension run package     # vendored docutils + webview bundle + .vsix
python scripts/fixtures.py --out demo/data && \
  DEMO_BASE=/ pnpm --dir client build:demo   # the static demo, in demo/dist
```

`rstview --dev` additionally starts Vite on `--port + 1` and opens that, so
editing a `.svelte` file hot-reloads without losing the open document.

### Releasing

Pushing to `main` runs the tests and republishes the demo. It also cuts a
release — tag, wheel, sdist and `.vsix` — but only when the version in
`pyproject.toml` has no tag yet, so bumping it is the act that ships. Bump
`extension/package.json` to match; a test fails if they disagree.

## License

LGPL-3.0-or-later. See [COPYING.LESSER](COPYING.LESSER).
