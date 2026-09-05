# VS Code extension — implementation plan

Status: planning complete, milestones 1–3 ready to implement.

## Decision: stdio, not a socket

The extension spawns `rstview --stdio` and speaks the **existing JSON message
vocabulary** over stdin/stdout. The extension host relays to the webview with
`postMessage`. The webview never opens a socket.

Rejected alternatives and why:

| Option | Why not |
|---|---|
| Webview → `ws://localhost:PORT` | Breaks under SSH/Codespaces (webview's `localhost` is the *user's* machine, not the remote). Needs `asExternalUri` port forwarding, a relaxed `connect-src`, and relaxing the Origin check in `app.py:94-98`. Whether webviews reliably permit localhost WebSockets is genuinely uncertain. |
| Webview → host `postMessage` → host owns a WebSocket to Python | Correct transport, but the socket adds port allocation, firewall prompts and orphaned uvicorn for no benefit once the host is already in the middle. |

Stdio wins because it removes: port allocation, firewall/AV prompts, the
`allowed_origins` machinery, port forwarding for remote, and orphaned
processes. It also drops starlette/uvicorn/websockets to optional — leaving
**docutils as the only hard runtime dependency**, which materially shrinks the
Python-environment problem.

The HTTP/WebSocket server stays exactly as it is for the standalone CLI. Both
front ends sit on one shared core.

## The gap that matters most

`watch.py` only sees **saved** files. The point of an in-editor preview is
previewing *as you type*. This needs a new inbound message:

```json
{"type": "source", "path": "docs/guide.rst", "text": "...buffer contents..."}
```

rendering that text as if it were the file at `path`, without touching disk.
`Document.render()` (`library.py`) already reads its source in one place, so an
optional override leaves the id scheme, directive config and `message()`
untouched. The host debounces `workspace.onDidChangeTextDocument` at ~150ms
(slower than watchdog's 30ms — keystrokes are more frequent than saves).

In stdio mode the watchdog watcher is disabled for open documents; VS Code's
own events cover them. Watchdog stays for *included* files and
`rstview.config.json`, which VS Code won't report unless they happen to be open.

## Python runtime

Resolve an interpreter in order: `rstview.pythonPath` setting →
`ms-python.python` extension API (`environments.getActiveEnvironmentPath`,
subscribing to `onDidChangeActiveEnvironmentPath`) → `python3`/`python` on PATH.

Probe once per interpreter: `python -c "import docutils, rstview"`. If
`rstview` is absent but docutils is present, run a **vendored copy shipped in
the extension** via `PYTHONPATH`. So the extension needs docutils and nothing
else — and docutils is pure Python with no build step.

Do **not** bundle a venv (platform matrix, VSIX size, wrong-platform binaries on
remote). Do **not** use Pyodide (~10MB WASM, loses filesystem access, forces a
second implementation of the parse path).

Failure paths, all first-class in the panel, never silent:
- No docutils → "Install docutils into <env>" (a `vscode.Task` so the terminal
  is visible) and "Select interpreter".
- No Python → message plus the `rstview.pythonPath` setting.
- Child crashed → last ~20 lines of stderr, an Output channel link, restart with
  capped exponential backoff.
- Untrusted workspace → don't spawn; show the trust command.

## Integration points

- **`WebviewPanel`, not `CustomTextEditorProvider`** — the latter *replaces* the
  text editor, which would remove the reST source view entirely.
- `rstview.showPreview` (side-by-side) + `showPreviewToCurrentColumn`;
  `ctrl+shift+v` / `ctrl+k v` scoped to `editorLangId == restructuredtext`;
  editor title button in `navigation` group.
- `Map<docUri, WebviewPanel>` so re-invoking focuses rather than duplicates.
  `WebviewPanelSerializer` so previews survive window reload.
- Start with `retainContextWhenHidden: true` (one line, ships), but design for
  `getState`/`setState` from day one. Settings moving to VS Code config removes
  most of the state problem; the residual is Shiki's loaded grammars. Measure a
  cold highlight — under ~150ms, drop `retainContextWhenHidden`.
- **Theme**: map `app.css` tokens onto `--vscode-*` in a separate `vscode.css`
  gated on `body.vscode-light, body.vscode-dark`, every mapping written with a
  fallback (`var(--vscode-x, <default>)`). Add `mode: 'vscode'` to `MODES`,
  default in the extension build, driven by relaying
  `onDidChangeActiveColorTheme` from the host. Shiki's dual-theme output already
  makes the switch free.
- **Settings** move to `workspace.getConfiguration('rstview')`. Webview
  `localStorage` has unstable origins across restarts, so it is unreliable there
  regardless. Keep the gear panel UI; it writes through to VS Code settings.
- **Scroll sync** depends on `data-line` from the AST's `line` field, which
  `Node.svelte` currently drops. Interpolate between adjacent `[data-line]`
  elements — snapping to element tops feels jerky with tall reST blocks. Guard
  both directions with a "last scroll source + timestamp" (~300ms) or it
  oscillates. **Caveat:** docutils' `node.line` is unreliable (often `None`,
  sometimes off by one for compound bodies). Spike S3 before promising this.

## Changes to this codebase

**Reusable unchanged:** `parse.py`, `directives.py`, `watch.py`, all of
`library.py`'s containment logic, the whole node component tree
(`registry.js`, `Node.svelte`, `nodes/*`), `outline.js`, `Outline.svelte`,
`reading.svelte.js`, `highlight.svelte.js`, `themes.js`, `links.js`.

**Transport abstraction** — `connection.svelte.js` is the only place that knows
about WebSockets. Refactor to `createConnection(transport)` where transport is
`{ send, onMessage, onStatus }`. The state machine, the `wanted` stale-push
guard and the public accessors stay identical. Two implementations:
`websocketTransport()` (lifts the current code verbatim, including reconnect
backoff) and `vscodeTransport()` (`acquireVsCodeApi`, status permanently
`'live'` — the host reports child death as an explicit error, so there is no
reconnect loop). Selected by `import.meta.env.VITE_TARGET`.

Also conditionalise the browser-only globals in `App.svelte`: `history.pushState`,
`popstate`, `location.search`. In VS Code, navigation posts to the host instead.

**File dialog** — `FilePicker.svelte` exists only because a browser cannot
supply a real path. VS Code can. In the extension build, replace with
`showQuickPick` over `workspace.findFiles`. Exclude the picker from that bundle.

(Since written, `browse` and `locate` moved off the HTTP routes and onto the
transport, so the dialog *would* now work unchanged in a webview. That does not
change the plan — a quick-pick is the native thing — it only means the picker is
excluded because it is the wrong UI there, not because it is broken there.)

**Root** — in VS Code the natural root is the workspace folder, not the
document's directory. `library.resolve`'s containment stays as the backstop for
`..` in link targets inside untrusted documents.

**New Python surface** — `src/rstview/stdio.py` (JSON-lines loop) plus a
transport-agnostic `Session` extracted from `create_app`'s `subscribe`/
`on_change`. `on_change` is already parameterised over a send function, so this
is mechanical. `cli.py` gains `--stdio` (mutually exclusive with
`--dev`/`--port`/`--listen`).

## Packaging

```
extension/
  package.json         # vsce generates .vsixmanifest; never hand-write it
  src/extension.ts     # activation, panels, process supervision
  src/pythonEnv.ts     # interpreter resolution + probe
  src/session.ts       # stdio JSON-lines client
  media/               # built Svelte bundle
  python/rstview/      # vendored server (build step copies src/rstview)
```

Client build gains a `vscode` target: `base: './'`, `outDir: '../extension/media'`,
`define` for `VITE_TARGET`. Bundle the host code with esbuild into a single
`out/extension.js`.

Manifest must declare `capabilities.untrustedWorkspaces: "limited"` with
`restrictedConfigurations: ["rstview.pythonPath"]` — a workspace
`.vscode/settings.json` could otherwise point it at an arbitrary executable —
and `virtualWorkspaces: false`, since `library.py` is entirely `os.path`-based.

**Dev loop**: the existing Vite HMR `--dev` path cannot work through a webview
CSP (it needs `connect-src ws://localhost:5173`). Use `vite build --watch` into
`extension/media/` plus a `rstview.reloadPreview` command that reassigns
`panel.webview.html` — a ~1s loop with no CSP changes. A dev-only relaxed CSP
pointing at the Vite server is a natural follow-up, kept out of the shipped path.

## Spikes — do these first

- **S2 (critical, ~2h): does the built Svelte bundle load under a strict webview
  CSP?** Build with `base: './'`, load under
  `default-src 'none'; script-src ${cspSource} 'nonce-X'`. Watch: the nonce on
  Vite's module script, Shiki's dynamic `import()` chunks, whether anything
  needs `unsafe-eval`/`wasm-unsafe-eval`, and Svelte's scoped style injection
  against `style-src`. **If this fails, the plan changes.** Fallback: static
  Shiki imports, accepting a larger bundle.

  **RUN — PASSED.** The current bundle was served under a webview-style `<meta
  http-equiv>` CSP with a *nonce-only* `script-src` (no `'self'`, the strictest
  form VS Code recommends):

  ```
  default-src 'none'; script-src 'nonce-rstview'; style-src 'self' 'unsafe-inline';
  connect-src ws://127.0.0.1:8931 http://127.0.0.1:8931; img-src 'self' data:; font-src 'self'
  ```

  Headless Chromium reported `securitypolicyviolation` events: **none**. The app
  mounted, the outline populated (7 entries), both `.shiki` blocks rendered and
  a token span computed to `rgb(215, 58, 73)` — so the lazily `import()`ed
  grammar and theme chunks loaded and applied. Dynamic `import()` inherits the
  importing module's nonce, which is what makes 77 lazy chunks survive a
  nonce-only policy. No `unsafe-eval` was needed: Shiki runs on the JavaScript
  regex engine, not the WASM/oniguruma one.

  Caveat: this used Vite's default absolute `base`. Milestone 9 still has to
  switch to `base: './'` and route every asset through `asWebviewUri`; that
  changes URLs, not the CSP question settled here. The Shiki fallback is not
  needed.
- **S1 (~1h): webview → localhost WebSocket, desktop and SSH.** Retires the
  architecture question empirically. Irrelevant if stdio is chosen, which is
  part of why stdio is chosen.
- **S3 (~30min): is `node.line` good enough for scroll sync?** No extension
  needed — add `data-line` in the standalone viewer and eyeball the gaps.

## Milestones

**Status: 1-6 done.**

1. **Transport abstraction** (client only, no VS Code). Standalone behaves
   identically; unit-test `createConnection` with a fake transport.
2. **`--stdio` server mode** + `Session` extraction. `tests/test_stdio.py` pipes
   JSON lines in, asserts ASTs out. HTTP server untouched.
3. **`source` message** — render a buffer without touching disk; a path outside
   the root is still refused.
4. **Hello-world extension**: panel, spawn, render one document. *Done.*
   `extension/` holds `extension.ts` (commands), `preview.ts` (panel + child
   lifetime, one panel per document), `server.ts` (JSON-lines child), `html.ts`
   (CSP + `asWebviewUri` rewriting, kept free of `vscode` imports so it can be
   tested outside a host) and `pythonEnv.ts` (probes candidate interpreters for
   an importable `rstview` rather than trusting the first one that exists).
   Added `src/rstview/__main__.py`: the extension spawns `python -m rstview`,
   because the console script is not necessarily on PATH for the interpreter it
   resolved.
5. **Live update on typing** — `onDidChangeTextDocument` → debounce → `source`.
   *Done.* 150ms debounce, plus `onDidSaveTextDocument` undebounced (a save can
   rewrite the buffer, and it is when a user most expects the preview to be
   right), plus a `source` at startup when the editor is already dirty. The
   preview follows the buffer, not the file, so there is no watcher in the
   stdio path at all.
6. **Theme + settings integration.** *Theme done; settings still localStorage.*
   No message from the host is needed: VS Code maintains
   `vscode-light`/`vscode-dark`/`vscode-high-contrast` on `<body>` and rewrites
   it the moment the theme changes, so a `MutationObserver` on that class is a
   live feed. A `vscode` mode replaces `system` in that build and resolves to
   whichever way the host leans. `vscode.css` maps the chrome tokens onto
   `--vscode-*` with our own values as fallbacks, scoped entirely to those body
   classes so the file is inert in a browser. Syntax defaults to Light Plus and
   Dark Plus - VS Code's own themes - so code in the preview matches code in
   the editor without any theme parsing.

   The user's *actual* theme is now read too: `theme.ts` matches
   `workbench.colorTheme` against every extension's contributed themes, parses
   the JSONC, follows `include`, and posts the result to the webview, which
   hands it straight to Shiki. Defaults to matching the editor; a named Shiki
   theme can still be chosen instead.
7. **Navigation**: quick-pick open, cross-document links, root = workspace folder.
8. **Scroll sync**, gated on S3.
9. **Failure modes**: *partly done.* The serializer is in - a window reload was
   otherwise a permanently blank pane, and it needs an explicit
   `onWebviewPanel` activation event, which is not inferred the way command
   activation is. A missing interpreter reports every candidate it tried plus
   two buttons that fix it. Still open: crashed child, untrusted workspace,
   `retainContextWhenHidden` measurement.
10. **Package and test on a real SSH remote and a Codespace.** Do not defer past
    here — a transport-shaped problem is cheapest to fix while M1 is fresh.
