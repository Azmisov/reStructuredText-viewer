# Architecture

```
.rst file ──watchdog──> docutils ──> JSON AST ──WebSocket/stdio──> Svelte 5
```

The server describes the document; the client decides how it looks. Everything
below is a consequence of that split.

## Why an AST and not HTML

Presentation features — theming, collapsible sections, custom components, an
outline — become client changes rather than docutils translator subclasses. The
server never learns about CSS.

Partial updates fall out for free: every node carries a stable `id`, the client
renders with keyed `{#each}`, and Svelte leaves unchanged subtrees — along with
their scroll position, focus and component state — untouched.

## AST contract

```json
{"type": "paragraph", "id": "81a5ca73", "props": {}, "line": 4, "children": [...]}
{"type": "text", "id": "6e50b857", "value": "Hello "}
```

`type` is the docutils tagname and `props` are its attributes. A type the client
has no mapping for renders through `Unknown.svelte` rather than disappearing,
and `tests/test_coverage.py` parses `client/src/registry.js` to fail the build
when docutils can emit something unmapped.

## Node identity

This is the load-bearing part; `tests/test_identity.py` pins it.

- **Containers** (`section`, `bullet_list`, `table`, …) are keyed
  *structurally*: by their docutils anchor where they have one, otherwise by
  position among same-type siblings. Content-addressing them instead would
  rehash the entire root-to-edit spine on every keystroke, remounting a whole
  section to change one paragraph inside it.
- **Leaves** are content-addressed (blake2b, 8-byte digest), **excluding source
  line numbers** — including them would invalidate every id below an inserted
  line.
- **Components** are keyed by name or explicit `:key:`, so changing a prop
  updates the component rather than remounting it.

Verified empirically across edit, insert, append and reorder before it was
trusted: reordering list items changes nothing, and editing a paragraph
disturbs no ancestor.

## Watching

Watches follow documents, not the root: one non-recursive watch per directory,
added as each document is first opened (`Library.on_load`). Watching the root
recursively is wrong as soon as the root is broad — the default root on a
loopback bind is the whole filesystem — and it takes the server down before it
finishes starting. See [DECISIONS.md](DECISIONS.md).

Under `--stdio` there is no watcher at all: the editor sends buffer text, so
the preview follows what is on screen rather than what is on disk.

## Transports

The client talks to a transport of `{send, onMessage, onStatus}` and does not
know which one it has. `import.meta.env.VITE_TARGET` selects it at build time,
so the unused one is tree-shaken out.

- `transports/websocket.js` — the standalone app, with exponential backoff and
  reopen-on-reconnect.
- `transports/vscode.js` — `acquireVsCodeApi()` / `postMessage`; the extension
  host relays to the Python child.
- `transports/static.js` — the published demo, replaying fixtures recorded from
  `samples/` by `scripts/fixtures.py`. No server exists behind the Pages site,
  so what it cannot have is the half a static host cannot serve: the watcher
  pushing a new `doc` when a file changes. It reports its status as `demo`
  rather than claiming to be live.

### Message vocabulary

Inbound `open`, `list`, `source`, `browse`, `locate`; outbound `ready`, `doc`,
`error`, `list`, `browse`, `locate`. It is identical over the WebSocket and
over `--stdio`.

`browse` and `locate` are the only request/response pairs in an otherwise
push-only protocol, so they carry an `id` the reply echoes. That is what keeps
a refused lookup addressed to the dialog that asked for it instead of surfacing
as the document pane's error, and it is why the file dialog works over any
transport — including a webview and the fixture-backed demo, neither of which
can reach an HTTP route.

`source` renders supplied buffer text without reading disk, which is how an
editor previews unsaved changes. Containment applies to it exactly as to `open`
— it goes through the same `library.get`, which also means the path must exist
on disk, so a never-saved buffer is not yet renderable.

Under `--stdio`, stdout carries protocol only. It is claimed at the file
descriptor level (`dup`/`dup2`), so a stray `print` or a C-level write to fd 1
from any dependency is diverted to stderr rather than corrupting the stream.

## Containment

Path containment is a security boundary, not a detail. `--root` defaults to the
whole filesystem when bound to loopback and narrows to the starting document's
directory otherwise. Absolute paths, `..` traversal, symlinks pointing out of
the tree, and non-reST files are all rejected server-side — after `realpath`,
never before — and `/api/browse`, `/api/locate` and `/media` apply the same
check as document loading. Entries symlinked out of the tree are omitted from
listings rather than listed and then refused.

The HTTP routes are a parallel read-only surface rather than what the client
uses: `/api/doc`, `/api/browse` and the rest exist for scripting and debugging,
while the page itself speaks the message vocabulary over its transport.

`/media` is the one widening: `resolve_asset` drops the reST suffix
requirement, since an `.. image::` target is not a document, and keeps every
other rule including the directory refusal. Widening *what* may be read must
not widen *where*.

## Layout of the repo

| | |
|---|---|
| `src/rstview/` | parser, library, watcher, Starlette app, stdio loop, CLI |
| `client/src/` | Svelte 5 client; `registry.js` maps node types to components |
| `extension/` | VS Code extension over `--stdio`, with docutils vendored in |
| `samples/` | sample documents; `directives.rst` exercises every docutils built-in |
| `scripts/` | build tooling; `fixtures.py` records `samples/` for the demo |
| `docs/` | these notes |
| `tests/` | pytest suite |
