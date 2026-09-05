# reStructuredText Viewer

Live preview for reStructuredText, rendered from a docutils AST rather than
generated HTML — so theming, custom directive components and the outline are
all decided on the client side.

**Open Preview to the Side** — `Ctrl+Shift+V` (`Cmd+Shift+V` on macOS), or the
button in the editor title bar of any reStructuredText file.

## Requirements

**Python 3.10 or newer. Nothing to pip install** — docutils and the renderer
ship inside the extension.

It uses the Python extension's active interpreter if there is one, otherwise
`python3` on PATH. Set `rstview.pythonPath` to point somewhere specific; it
accepts `${workspaceFolder}`.

With several folders open, set it in that folder's own `.vscode/settings.json`
or in the `.code-workspace` file — whichever folder the document belongs to
wins.

## Status

Early. The preview follows the editor as you type, including unsaved changes,
and matches your colour theme - including syntax highlighting, which is driven
by your actual theme rather than an approximation of it. Scroll sync is not
implemented yet.

## License

LGPL-3.0-or-later.
