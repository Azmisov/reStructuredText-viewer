# Decisions

Why the less obvious parts are the way they are. Most of these were bugs first.

## Cross-document links are ordinary hyperlinks

Plain reST has no cross-reference role — that is Sphinx's `:doc:`. So a link
whose target happens to be a local `.rst`/`.txt`/`.rest` file is intercepted by
the client, resolved relative to the current document, and swapped over the open
connection. Scroll, settings and the highlighter's already-loaded grammars all
survive; a history entry is pushed so Back works. Modified clicks
(ctrl/cmd/shift) fall through to the browser untouched.

## The file dialog is served, not native

The browser cannot supply a real path. `<input type="file">` deliberately hides
it, the File System Access API is Chromium-only and still path-less, and OPFS is
a sandbox with no relation to the user's files. So the server browses and the
client draws the dialog.

## Text direction has no setting

The Unicode bidirectional algorithm already orders characters within a line, and
every block-level text container is rendered with `dir="auto"`, which resolves
base direction from the block's first strong character. An Arabic paragraph lays
out right-to-left and an English one beside it does not, with no configuration.

`dir="auto"` is doing what bidi alone cannot: punctuation placement at line
boundaries, list marker side, table column order. Code blocks are pinned LTR
regardless, since source is not prose.

## Reading position is measured, not observed

The outline highlights the first heading clipped by neither the sticky bar nor
the bottom of the viewport; when no heading is fully visible, it is whichever
section occupies the top of the scroll.

It is measured from the **heading** elements rather than the sections — a
section spans the rest of the document, so "unclipped" would never be true of
one — and computed directly from scroll position on a throttled rAF rather than
with an `IntersectionObserver`, which only reports sections whose intersection
*changed* and so left the highlight stuck when scrolling back up.

## Highlighting runs in the browser

Shiki emits both palettes in one pass as CSS variables, so switching light/dark
is a variable swap with no re-highlight. Switching a *syntax theme* does re-run
highlighting, which is why themes and grammars load lazily at runtime instead of
being fixed at build time — 65 themes, ~77 lazy chunks.

Two things this cost:

- Vite cannot statically analyse `` import(`@shikijs/langs/${lang}`) ``. It
  emitted a bundle with **no grammars at all** and only a warning. There is an
  explicit `LANGS` map for that reason; do not "simplify" it back.
- The highlighter cache must hold *promises*, not resolved values. Caching
  resolved values let two concurrent code blocks each build their own
  highlighter while sharing module-global loaded-sets, producing "Theme not
  found" at random.

## Line numbers are CSS counters on a grid

Shiki emits one `.line` span per line separated by literal `\n` text nodes,
which `<pre>` renders. Any per-line box would then add a *second* break and
double-space the code, so `<code>` is `display: grid` — grid discards
whitespace-only text nodes, giving exactly one row per line.

Wrapping with numbers uses a hanging indent (`padding-left` plus negative
`text-indent`), **not** a two-column grid: grid makes every token `<span>` its
own cell, which shatters each line into one fragment per token.

Shiki themes carry no gutter colour, so one is derived from the theme's own
background with `color-mix`, nudged toward the text colour — direction depending
on light or dark.

## `client/src/app.css` may not contain `:global()`

`:global()` is Svelte `<style>` syntax. In a plain stylesheet browsers silently
discard the whole rule — which killed syntax colours, table cell margins and
code padding at once, with no error anywhere. A test enforces its absence.

## The watcher ignores read events

inotify reports `opened` and `closed_no_write` for the server's *own* reads
during `render()`, which produced roughly 16 renders per second forever, with
the version counter climbing while nothing touched the file.
`test_server.py::test_reading_the_file_does_not_retrigger_a_render` guards it.

## Font size is pinned inside the settings panel

The font-size slider lives in the panel it resizes. Letting the panel grow moves
the slider out from under the cursor mid-drag, so the panel is sized in `px`
while everything outside it previews live. Its top offset is snapshotted once
for the same reason.

`html`, not `body`, carries `--base-font-size`: `rem` is root-relative, so
setting it on `body` scales the prose but leaves the nav and sidebars behind.

## The extension bundles docutils rather than asking for an install

The nearest comparable extension is widely disliked for exactly one reason:
it makes users install and correctly locate a Python package before anything
renders. That failure has many shapes - wrong venv, wrong interpreter selected,
multi-root settings silently not applying - and every one of them looks like
the extension being broken.

Bundling is also the *correct* answer here, not merely the kind one. Esbonio
genuinely needs the user's environment: it loads `conf.py`, Sphinx extensions
and project code. Parsing reST with docutils is hermetic, and custom directives
are declared in `rstview.config.json` - config, not Python plugins - so there
is no user code to import. The interpreter is a runtime, not a project context.

`pnpm run vendor` builds `extension/python/` from `pyproject.toml`, the child is
spawned with `PYTHONPATH` prepended to it, and the requirement drops to "a
Python 3.10 or newer exists". docutils is pure Python with no compiled
extensions, so one copy serves every OS and every interpreter version - no
per-platform `.vsix`, no wheel matrix. Cost: 550 KB to 1.2 MB.

The tree is *not* checked in. Vendored dependencies in git rot silently and
land in every diff; this one is reproducible build output, like `out/` and
`media/`.

What this does not fix: a machine with no Python at all. Closing that needs
frozen per-platform binaries, which is a much larger packaging commitment -
deferred until someone reports it.

## The server stack is imported lazily

`--stdio` needs docutils and nothing else; the WebSocket server needs Starlette,
uvicorn and watchdog. Importing those at the top of `cli.py` would make an
editor host require the whole stack for a preview pane it never uses. They are
imported at the point the server actually starts, and
`test_stdio_does_not_import_the_server_stack` fails if anyone hoists them back.

This is what keeps the editor's dependency floor at "an interpreter with
docutils", which matters for any future attempt to bundle rather than ask the
user to install.

## A title is only a heading inside a section

`table`, `topic`, `sidebar` and the generic `admonition` all carry a `title`
child, and routing it through the ordinary `title` mapping made it an
`<h1>`-`<h6>` sized by section depth. In a table that heading landed *inside*
the element and split it in two. Each of those types now renders its own
title: a `<caption>` for a table, a plain label for the rest.

The table caption is styled as a banner row above the column headers - same
fill and padding as `th`, no bottom border - because a caption floating above
a bordered table reads as a stray paragraph rather than as part of it.

## docutils hides some structure in nesting, not in attributes

Three cases where the obvious CSS target does not exist:

- **`decoration`** holds `.. header::` and `.. footer::` and sits *first* in
  the doctree, so rendering children in order puts the page footer above the
  title. `Document.svelte` splits it out and puts each end where it belongs.
- **A line block's indentation** is a nested `line_block`, not a property of
  the line - so the indent hangs on the nesting and compounds for free. A
  blank line is a `line` with no content, which needs `::before { "\00a0" }`
  or the stanza break collapses.
- **`legend` and `compound` carry no classes at all**, unlike `epigraph`,
  `pull-quote` and `highlights`, which are all `block_quote` and would be
  indistinguishable without one. `TYPE_CLASS` supplies a hook for the few
  types CSS targets; tagging every paragraph would be DOM weight for nothing.

## `raw` is parsed and then dropped

`.. raw:: html` is the one directive deliberately not rendered. The client
builds a component tree from an AST; honouring `raw` would mean `{@html}` on
document-supplied markup, which hands any document the viewer opens authority
over the page it is displayed in - script, styles, and anything else. A preview
of someone else's file should not be able to do that.

It stays in `HIDDEN` rather than being rejected at parse time, so a document
using it still renders everywhere else.

## Images are served through a separate resolver

`.. image::` targets are not documents, so `resolve` - which insists on a reST
suffix - cannot serve them. `resolve_asset` drops the suffix check and keeps
everything else: realpath before the containment check, no directories, no
escaping the root. Widening *what* may be read must not widen *where*.

In a webview there is no server to fetch from, so the host adds the root to
`localResourceRoots` and posts the `asWebviewUri` of it; the client rebases
relative URIs onto whichever base it has been given. Either way the URI is
resolved against the *document*, not the page URL - two different things as
soon as one document links to another in a subdirectory.

## Borders are derived, not taken from a theme variable

`--vscode-panel-border` is the obvious mapping and the wrong one. It separates
large workbench surfaces and is deliberately faint against the editor:

| theme | panel.border | on background | contrast |
|---|---|---|---|
| Dark Modern | `#2B2B2B` | `#1F1F1F` | 1.16 |
| Monokai | `#414339` | `#272822` | 1.48 |
| Abyss | `#2b2b4a` | `#000c18` | 1.45 |
| Dark (Visual Studio) | *not defined* | | |

Table and code-block rules are drawn *on* content and have to be seen. They mix
the background toward white or black - not toward the theme's foreground, since
a theme whose text is already low-contrast (Abyss is `#6688cc` on `#000c18`)
would hand that weakness down to every rule derived from it. The direction has
to be picked per theme kind, which is what the `body.vscode-*` classes are for.
Measured after: 2.60-2.71 on dark themes, 1.69 on light, where a faint rule is
the convention.

High-contrast themes define `contrastBorder` for exactly this purpose, so where
it exists it wins.

## The editor's own theme is read, not approximated

VS Code colour themes *are* TextMate themes with a `colors` block bolted on,
which is exactly what Shiki consumes - so the user's real theme can be handed
over as raw JSON with no translation layer. Verified against Dark+, Monokai,
Abyss, Quiet Light and HC Light before any of this was built.

Three things make it work that are not obvious:

- **`include` must be resolved.** VS Code's themes are layered (Dark+ is a
  handful of overrides on Dark), so a theme read without following `include`
  is mostly empty. The including theme's `tokenColors` go *last*, because
  TextMate resolution takes the final match.
- **Comment stripping must be string-aware.** Theme files are full of `//`
  inside colour values and scope selectors; a naive comment regex corrupts the
  document into something that will not parse. This is not hypothetical - it
  failed that way the first time.
- **Some themes define no editor background.** VS Code's high-contrast themes
  leave it to the workbench. Those resolved defaults are live in the webview as
  `--vscode-editor-background`, so the client reads them back rather than
  guessing a colour that would not match the editor.

There is no API for "the active theme's JSON", so it is found the way VS Code
finds it: match `workbench.colorTheme` against every extension's contributed
themes. A theme that cannot be read falls back to the bundled Shiki themes -
highlighting must never be what breaks.

## `rstview.pythonPath` is declared `scope: "resource"`

The default configuration scope is `window`, and VS Code **silently ignores
window-scoped settings in a folder's own `.vscode/settings.json` once more than
one folder is open**. The setting simply has no effect, with no warning
anywhere. Resource scope is what makes a per-folder interpreter work in a
multi-root workspace.

The failure it caused is also why `MissingRstview` carries an `advice` string
listing every interpreter that was tried and naming the multi-root case, rather
than a one-line message.

## VS Code integration uses stdio, not a socket

See [VSCODE_PLAN.md](VSCODE_PLAN.md). Briefly: a webview reaching a localhost
port is an extra listening socket, an origin check, and a story about remote and
SSH windows; the extension host already has a child process and a message
channel.
