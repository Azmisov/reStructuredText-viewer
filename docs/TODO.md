# Open work

What is left, why it is left, and what it would cost. Ordered roughly by how
much it would change if deferred, not by size.

Design rationale for what already exists lives in
[DECISIONS.md](DECISIONS.md); the VS Code plan and its milestone status are in
[VSCODE_PLAN.md](VSCODE_PLAN.md).

## The big one

### User-authored components for custom directives

Directives are already pluggable on the **server** side: `rstview.config.json`
declares a directive with typed options, the parser coerces them and emits a
`component` node, and nothing needs a restart. The gap is entirely on the
client, where `client/src/components/index.js` maps a name to a Svelte
component compiled into the bundle.

Loading a user's own component at runtime means one of:

- **Ship the Svelte compiler** to the browser and compile on demand. Largest
  bundle, no build step for the user, and a compiler is a lot of surface to
  hand document-supplied source.
- **Ask users to build**, and load the compiled output from a directory the
  server serves. Small runtime, but the user now needs a toolchain.
- **Neither** — offer a declarative escape hatch instead (templates plus the
  `raw` stylesheet support that already exists), which covers presentation but
  not interactivity.

Worth its own session. Nothing about the current architecture forecloses any
of the three. [COMPONENTS.md](COMPONENTS.md) is that session's homework: seven
options rather than three, ranked, with the trust boundary and the four hosts
that decide between them. It lands on a `mount`/`update`/`destroy` contract —
which keeps prop updates guaranteed rather than hopeful, makes hot reload
possible, and lets the user pin their own Svelte, because DOM is a safe
boundary between two runtimes and snippets are not. The escape hatch above is
rejected there, and the third option's toolchain cost turns out to be the
smallest of the problems.

The load-bearing claims are spiked, not assumed: two Svelte runtimes in one
page, a host-owned children node placed by the guest, hot reload, the failure
modes, and the webview's CSP against a cross-origin module. What is left is one
narrow question — whether a file under the workspace root is served to a webview
the way one under `media` is — and it decides how the bytes arrive, not the
contract.

[COMPONENT_PLAN.md](COMPONENT_PLAN.md) turns that into the build: the contract,
the config key, the `components` message, `resolve_module` as an allowlist, the
trust gate, and seven milestones of which the first four are the whole feature
for the standalone tool.

## Markdown

Parsed through MyST into the same doctree as reST; see the Markdown entries in
[DECISIONS.md](DECISIONS.md). Known gaps, roughly by how often they will bite:

- **HTML tables lose their structure.** `<table>` is outside the allowlist, so
  its cell text survives as loose paragraphs. Mapping it means building
  docutils' `table`/`tgroup`/`colspec` shape from rows of unknown width, and
  `colspan`/`rowspan` into `morecols`/`morerows`. `<dl>` has the same problem
  in miniature (`dt`/`dd` are not wrapped in an item).
- **Emoji shortcodes** (`:tada:`) stay as text. GitHub renders them; MyST has
  no extension for it, and a table of ~1800 names is a lot of data for one
  feature.
- **Line numbers are weaker than reST's.** MyST gives table internals line 0
  and inline raw HTML no reliable line at all (inline HTML nodes take their
  paragraph's). Messages still point at the right line; this matters for the
  scroll sync spike, which should run against a Markdown document too.
- **Sphinx-only roles and links** (`{ref}`, `{doc}`, `<project:...>`) warn,
  exactly as the Sphinx roles do in reST. GitHub-style `[text](#slug)` and
  `[text](file.md)` are the supported way to link.
- **An invalid directive option** is dropped with a warning and the directive
  still runs; reST rejects the whole directive. MyST's behaviour, not ours.

## VS Code

Milestones 1-6 are done and 9 is partly done; see
[VSCODE_PLAN.md](VSCODE_PLAN.md) for the full list.

- **Quick-pick navigation** (milestone 7). The served file dialog is excluded
  from the extension build already, so this is the replacement, not an
  addition: `showQuickPick` over `workspace.findFiles`, and cross-document
  links posted to the host rather than pushed onto browser history.
- **Scroll sync** (milestone 8), *gated on spike S3*: is docutils' `node.line`
  good enough? It is often `None` and sometimes off by one for compound
  bodies. The spike needs no extension - add `data-line` in the standalone
  viewer and look at the gaps. Do not promise this before running it.
- **Crashed child, untrusted workspace** (milestone 9). A dead child currently
  surfaces as an `error` frame with no way to restart short of reopening the
  panel.
- **`retainContextWhenHidden` measurement** (milestone 9). It is on
  unconditionally. Measure a cold Shiki highlight; under ~150ms, drop it.
- **A real SSH remote and a Codespace** (milestone 10). The plan is explicit
  that a transport-shaped problem is cheapest to fix while the transport work
  is fresh, and this has not been run anywhere but locally.
- **Unsaved buffers.** `source` renders buffer text but goes through
  `library.get`, so the path must exist on disk - File > New, paste reST,
  preview does not work. Needs either a synthetic path inside the root or a
  separate containment-free message.
- **Never opened in a real editor by the author of this code.** Everything is
  verified by driving the compiled host code and the built bundle outside VS
  Code. The plumbing is proven; "it looks right when you press the keybinding"
  is not.

## Packaging and distribution

- **Publish.** A version bump on `main` tags a release and attaches the wheel,
  the sdist and the `.vsix`, so installing means downloading one. Neither index
  is fed: PyPI wants trusted publishing configured against the project, and the
  marketplace wants an Azure DevOps token in the repository's secrets. Both are
  one job each on top of what `.github/workflows/ci.yml` already builds.
- **Machines with no Python at all.** Bundling docutils dropped the
  requirement to "a Python 3.11+ exists", which is the 90% win. Closing the
  rest means frozen per-platform binaries (~15MB each, a per-platform `.vsix`,
  a real build pipeline). Wait for someone to ask.
- **Trim the KaTeX fonts.** All three formats ship - woff2 296K, woff 336K,
  ttf 540K - and every browser that can run this takes woff2. Dropping the
  other two would halve the extension's payload. It needs a build step that
  removes the files *and* the `src` entries naming them, so it is not a
  one-liner.

## Smaller ideas

- **Runtime root switching** in the file dialog. Offered once and not taken;
  the root is fixed at startup by `--root`.
- **A flat "search all documents" mode** in the picker, alongside the current
  directory browsing. `Library.locate` already does the matching.
- **Server-side AST patches.** The whole tree is sent on every render. Node
  ids are stable, so a diff is possible - but this is a bandwidth
  optimisation, not a correctness one, and updates are already partial on the
  client.
- **`--pypi-strict`**, using the `strict` extra (`readme_renderer`) that is
  declared in `pyproject.toml` but unused: render the way PyPI would, so a
  README can be checked before upload.

## Known limitations, by choice

Not bugs, and not on the list above. Recorded so they are not rediscovered as
defects.

- **Raw markup is dropped** (stylesheets are not). Rendering it would hand any
  document you open authority over the page displaying it. See DECISIONS.md.
- **Semantic highlighting is not available** in the VS Code preview: it needs
  a language server's token classification, which a preview pane has no access
  to. `tokenColors` from the user's real theme are honoured; `semanticTokenColors`
  are not. VS Code's own Markdown preview has the same limitation.
- **`.. header::` and `.. footer::` are page furniture** rendered at the top
  and bottom of the document, not repeated per printed page. There are no
  pages here.
- **A bare custom role does nothing visible.** It attaches a class; something
  has to style it. Deriving the role from an existing one, or defining the
  class in a `raw` stylesheet, is the answer - both are shown in
  `samples/directives.rst`.
