# User-authored components — implementation plan

Status: design settled, load-bearing spikes run, nothing implemented.

The ranking that produced this, and the five options it beat, are in
[COMPONENTS.md](COMPONENTS.md). This document is only what to build.

## Decision: a mount contract, compiled down to vanilla JS

A component is an ES module the author builds however they like — Svelte, Lit,
or nothing — that default-exports lifecycle functions:

```js
export default {
  ABI: 1,
  mount(target, props, ctx) {
    // build DOM in `target`; place `ctx.children` if the body was parsed
    return {
      update(props) {},   // props changed - same instance
      destroy() {}        // going away
    };
  }
};
```

The client imports it, calls `mount`, and calls `update` when the server sends
new props. Nothing about Svelte crosses the boundary.

Rejected alternatives and why:

| Option | Why not |
|---|---|
| Custom elements | The host can deliver a prop but cannot guarantee a re-render: Svelte assigns a property only where a real setter exists, so a plain class field silently degrades to a stringified attribute. `customElements.define` is also irreversible, so component code cannot hot-reload. Wraps into this contract in five lines if it is ever wanted. |
| Svelte modules sharing the host runtime | Best authoring experience, but couples every user's prebuilt bundle to `svelte/internal/client`, which is not a public API. Buys nothing this does not, now that a host-owned children node is proven to replace snippets. |
| Declarative templates in config | Too limited, with no path to expand — the first request for a control makes it a programming language by accident. |
| In-browser Svelte compiler | Needs `blob:` in `script-src`, downgrading the webview's CSP for a convenience feature, and adds ~1 MB to a bundle that loads Shiki and KaTeX lazily. |
| Sandboxed iframes | Solves running *document*-supplied code, which the trust boundary below says is not our problem. |

## The trust boundary

A component is named by `rstview.config.json`, which is chosen by whoever
started the process — the same authority that already decides which directives
parse at all. Loading code it points at is the same class of act as `pytest`
importing `conftest.py`.

A **document** may never introduce code. It references a name the config has
already blessed; there is no directive option, and no inline body, that can
name a module. This is what keeps the decision in
[DECISIONS.md](DECISIONS.md) about dropping `raw` markup intact — that is about
document-supplied code, and this is not.

Three rules follow, and they are not negotiable:

- **The config's module list is an allowlist, not a filter.** `resolve_module`
  serves a path only if the loaded config names it. Suffix checking is a second
  line, not the first.
- **Containment applies unchanged.** Paths resolve relative to the config file,
  through the same `realpath`-then-check that `resolve_asset` uses.
- **VS Code gates on workspace trust.** An untrusted folder gets the manifest
  with `blocked: true` and a distinct box in the document, never a module load.

## Config

One new key per component, optional:

```json
{"components": {
  "chart": {"options": {"series": "json", "height": "int"},
            "required": ["series"], "parse_body": false,
            "module": "./components/chart.js"}
}}
```

No `module` means the name resolves to a component compiled into the client
(the two that exist today), and failing that to the unregistered box. The rest
of the entry keeps its current meaning, so every existing config still parses.

## Wire protocol

`ready` gains a `components` manifest, and a new outbound `components` message
pushes a replacement when the config or a module file changes:

```json
{"type": "components",
 "components": {"chart": {"url": "/components/chart.js?v=1757030400", "abi": 1}},
 "blocked": false}
```

The `v=` is the module's mtime. That is the entire hot-reload mechanism: a
changed file is a changed URL, the client re-imports, and the loader tears the
old instance down. The client never learns what an mtime is.

This stays a message rather than an HTTP route for the same reason the file
dialog's lookups are — it is the only way the webview and the fixture-backed
demo can have the feature at all. See ARCHITECTURE.md.

## Changes to this codebase

**`src/rstview/directives.py`** — `load_config` returns the `module` values
alongside the rest; a helper builds the manifest (resolved paths + mtimes).

**`src/rstview/library.py`** — `resolve_module(path)`, next to `resolve_asset`:
allowlist membership first, then the existing containment check, then a
`.js`/`.mjs` suffix rule. It does *not* inherit `resolve_asset`'s widening —
that one drops the reST-suffix requirement because an image is not a document;
this one replaces it with a narrower rule, not no rule.

**`src/rstview/app.py`** — a `/components/{path:path}` route returning
`FileResponse(..., media_type="text/javascript")`, and the module paths added to
the watcher's `extra` beside `config`.

**`src/rstview/session.py`** — the manifest in `Session.start`'s `ready`, and
`broadcast` pushing `components` when the config *or* a module changes. The
config-change branch already exists; a module change is the same branch with a
different trigger and no re-render.

**`client/src/nodes/Component.svelte`** — three-way: a manifest entry loads
externally, otherwise the built-in map, otherwise the existing dashed box.

**`client/src/components/External.svelte`** *(new)* — the loader. Spiked; see
below for the two things about it that are not obvious.

**`client/src/components/loader.svelte.js`** *(new)* — module cache keyed by
URL, de-duplicating concurrent imports of the same module.

**`extension/src/preview.ts`** — intercept `ready` and `components` on the way
to the webview and rewrite each `url` through `asWebviewUri`. The workspace root
is already in `localResourceRoots` (`preview.ts:24`), and containment already
guarantees the file is under it. Gate on `vscode.workspace.isTrusted`.

**`scripts/fixtures.py`** — record the manifest and copy the sample modules into
`demo/data`, so the published demo exercises real module loading rather than
only the built-in map.

## The loader, precisely

Two details the spike surfaced that are easy to get wrong:

- **The update effect must skip its first run.** An effect reading both `props`
  and `instance` fires the moment the instance lands, delivering a redundant
  `update()` before the component is on screen — measured as two calls for one
  change. Track the last delivered props object and skip the run in which the
  instance appears.
- **`<svelte:boundary>` goes around each instance for `update`, not `mount`.** A
  throwing `mount` is already contained by the dynamic import's promise chain; a
  throwing `update` runs inside an effect and needs the boundary.

Children, when `parse_body` is true, are rendered by the **host** into a
detached node the host owns and keeps updating, handed to the guest as
`ctx.children` for it to place. The guest never receives a snippet and never
calls back into our renderer.

## Failure modes

Every one degrades to the dashed box that already exists, with the reason in it:

| | |
|---|---|
| No `module`, no built-in | unregistered component (today's behaviour) |
| Module 404s or fails to parse | load error, with the URL |
| `ABI` mismatch | refused before `mount` is called |
| `mount` throws | caught by the import's promise chain |
| `update` throws | caught by `<svelte:boundary>` |
| Untrusted workspace | blocked, distinct wording — not an error |

## Spikes — done

Run 2026-09-05, Svelte 5.57.0 and Chromium. Full results and the four findings
that changed the design are in [COMPONENTS.md](COMPONENTS.md#spike-results).

- **Two Svelte runtimes in one page** — coexist and update independently.
- **Host-owned children node, adopted by the guest** — keyed updates keep
  reaching it, in place, no remount.
- **`update(props)`** — re-renders without remounting; hot reload by URL change
  destroys and remounts the guest while the children node survives.
- **Failure containment** — ABI refusal, throwing `mount`, throwing `update`.
- **A host snippet across the boundary** — kills the guest mount outright. This
  is why children are a DOM node and not a snippet.
- **The webview CSP** — a cross-origin dynamic `import()` loads under
  `default-src 'none'; script-src 'nonce-…'` with no violation. The constraint
  is CORS, not CSP; standalone is same-origin and needs no header.

One question is left, and it decides how the bytes arrive rather than the
contract: whether a file under the **workspace root** is served to a webview the
way one under `media` is. If it is not, the extension relays module source over
stdio and serves it from `media`; everything else here is unaffected. Answer it
in milestone 5, not before — the standalone path does not depend on it.

## Milestones

1. **`resolve_module` and the route.** Allowlist, containment, suffix rule,
   `/components/{path}`. Tests mirror the existing `resolve_asset` containment
   tests: absolute paths, `..`, a symlink pointing out, a file the config does
   not name, a non-`.js` file the config *does* name.
2. **Manifest in `ready`.** Server-side only; no client change. `--stdio` and
   HTTP produce the same manifest, which is one assertion in `tests/test_stdio.py`.
3. **The loader.** `External.svelte`, `loader.svelte.js`, and the three-way
   dispatch in `Component.svelte`. Port one of the two built-in samples to an
   external module and render it from `samples/`.
4. **Hot reload.** Module paths in the watcher's `extra`; `components` pushed on
   change; the client re-imports on a changed URL.
5. **The extension.** URL rewriting through `asWebviewUri`, the trust gate, and
   the open S-A question answered in a real extension host.
6. **The demo.** Fixtures record the manifest, sample modules ship in
   `demo/data`. The published demo then proves module loading end to end, which
   is the standing rule that the demo cannot drift from the app.
7. **The Svelte preset.** A documented Vite config plus the ten-line adapter
   that wraps a `.svelte` file's default export in `mount`/`destroy`. Ship it
   only once 1-6 are real; a preset for a contract nobody has used is a guess.

Milestones 1-4 are the whole feature for the standalone tool and depend on
nothing unresolved.

## Out of scope

- **Document-supplied component code**, permanently. The trust boundary above.
- **Custom elements as a second first-class ABI.** A five-line adapter over this
  contract if anyone wants one; not a parallel loading path.
- **A template language.** Rejected in COMPONENTS.md and not to be reintroduced
  incrementally as "just one conditional".
- **Sharing the host's Svelte runtime.** The guest brings its own — 18.8 kB gzip
  measured, and only for authors who choose a framework at all.
