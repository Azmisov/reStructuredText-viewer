# User-authored components

Notes towards closing the one item [TODO.md](TODO.md) calls "the big one".
Nothing here is built. This is the design space, what each point in it costs,
and which one to reach for first.

**The recommendation that came out of it is specified in
[COMPONENT_PLAN.md](COMPONENT_PLAN.md)** — a `mount`/`update`/`destroy` contract
over a user-built ES module. This document is the reasoning and the rejected
alternatives; that one is what to build.

## What exists, exactly

The server half is finished. `rstview.config.json` declares a directive with
typed options; `directives.py` builds a docutils `Directive` per entry, coerces
the options, and emits a `component` node carrying them as props. The config is
re-read on every render and the watcher treats a change to it as a change to
every document, so adding a block needs no restart.

The client half is a hard-coded map. `client/src/components/index.js` names two
Svelte components compiled into the bundle, and `nodes/Component.svelte` looks
the directive name up in it. A name with no entry renders a dashed "unregistered
component" box. Deployed, that box is the whole feature: a user can declare
`.. chart::` and get told to edit a source file they do not have.

The **prop contract is already fixed** and none of the options below change it:

| arrives as | from |
|---|---|
| coerced options | `:series:`, `:height:` — typed by `options` in config |
| `argument` | the directive's one optional positional argument |
| `content` | the raw body, when `parse_body` is false |
| `children` | a snippet of host-rendered nodes, when `parse_body` is true |
| identity | `name`, or `:key:` — see ARCHITECTURE.md on node identity |

So the question is narrow: **how does foreign code get into the page, and under
whose authority.**

## The trust boundary is the config, not the document

[DECISIONS.md](DECISIONS.md) refuses to render `raw` markup because doing so
hands any file you open authority over the page displaying it. That decision is
about **document-supplied** code and it does not extend to this.

A component is named by `rstview.config.json`, which is chosen by the person who
started the process — the same authority that decided which directives parse at
all. Loading code it points at is the same class of act as `pytest` importing
`conftest.py` or VS Code running `tasks.json`. The line to hold is that a
*document* can never introduce code, only reference a component the config
already blessed.

Three consequences, and they are non-negotiable for every option below:

- **A document may never supply source.** No `.. component::` with an inline
  body of JavaScript, no path in a directive option. The name is a lookup key
  into config, nothing more.
- **The module path resolves relative to the config and stays inside `--root`,**
  through the same resolver `/media` uses. Widening *what* may be read must not
  widen *where*.
- **VS Code gates on workspace trust.** An untrusted folder gets the declarative
  tier and the missing-component box, never a module load. This is the milestone
  9 item in TODO.md arriving with something to actually decide.

## What any answer has to survive

**Four hosts, not one.** Standalone (a real server, can serve files), the VS
Code webview (`script-src 'nonce-…'`, `localResourceRoots` = the extension's
`media` plus the workspace root), `--stdio` embedders generally, and the Pages
demo (no server at all). An answer that only works standalone is half a feature.

**Runtime coupling, but narrower than it looks.** Two copies of
`svelte/internal/client` are two reactivity contexts, and it is tempting to
conclude that the host's runtime must be shared. It does not: those contexts are
module-level variables in separate module instances, so they cannot interfere.
What is fatal is *snippets or reactive state crossing the boundary* — a
`children` snippet is a host-runtime construct and cannot be rendered by another
copy. **DOM is a safe boundary; snippets are not.** An option that hands over a
DOM node instead of a snippet lets the user pin their own Svelte, or use no
framework at all.

Both halves of that are now measured rather than argued — see
[Spike results](#spike-results). Two runtimes coexist and update independently;
a host snippet handed across kills the guest mount outright.

**Reactivity has a last hop the host does not own.** Delivering an updated prop
and the component re-rendering are two different things, and only some of the
options below guarantee the second. See the next section — it decides the
ranking.

**Node identity.** Components are keyed so that editing an option updates the
instance. Code changes are the opposite case: a new module is a new component
identity and every instance remounts. That is correct — but it means "hot reload
of component code" and "state survives" cannot both be promised.

**Degradation.** Missing module, version mismatch, a constructor that throws.
The dashed box already exists for the first; a `<svelte:boundary>` around each
instance should cover the rest, so one bad component cannot blank a document.

**The manifest is a message, not a route.** Which components exist and where
they load from belongs in `ready`/`doc`, the way the file dialog's lookups are
messages rather than HTTP. That is the only reason the webview and the demo can
have the feature at all.

## How a prop actually reaches a loaded component

This is the mechanical question the ranking turns on, so it is worth settling
before comparing options. Verified against the installed Svelte (5.57.0).

The **delivery** path already works and needs nothing new. `ast` is `$state`
(`client/src/connection.svelte.js:12`), so it is a deep proxy; a new `doc`
replaces it wholesale; the keyed `{#each}` matches a component by its stable
`name`/`key` id and therefore *updates* the `node` prop rather than remounting;
a `$derived` recomputes the props. A watched file changing `:height: 90` gets
that number to a mounted instance without a remount. That is the identity design
in ARCHITECTURE.md doing exactly what it was built for.

The **last hop** — the component noticing — is where the options differ.

For a custom element there is no single channel. `set_custom_element_data`
(`client/node_modules/svelte/src/internal/client/dom/elements/attributes.js:212`)
branches on whether the element is registered yet:

- **Registered:** `get_setters()` (`:590`) walks the prototype chain collecting
  keys whose descriptor has a `set`. A prop with a real setter is assigned as a
  property; anything else goes through `setAttribute` stringified.
- **Not yet registered:** a heuristic stands in — `value && typeof value ===
  'object'` becomes a property, everything else a stringified attribute.

Two things fall out of that, and both are design constraints rather than
curiosities:

- **Do not render the element before its module resolves.** A `json` option
  survives either branch, because objects always take the property path, but a
  `string` or `int` prop set during the import lands as an attribute and then
  switches to a property after upgrade. Same prop, two channels, decided by
  network timing. Awaiting the import before rendering removes the whole class
  of problem, and gives the dashed box and the error boundary a natural home.
- **Props must be accessors, and that is the author's job.** A public class
  field is not a setter, so Svelte will never assign it as a property — the
  value gets stringified onto an attribute the component is not observing, and
  nothing happens, silently. Svelte-compiled elements (`customElement: true`)
  and Lit's `@property()` both generate accessors and work; a hand-written class
  works only if its author knew to write `set series(v)`.

So with custom elements the host can *deliver* an update but cannot *guarantee*
a re-render. That is a weaker promise than the two components compiled into the
bundle today make, and weakening it silently — no error, just a stale block — is
the worst shape a failure can take.

An explicit `update(props)` call has no such gap. That is the single largest
difference between the two loading ABIs below.

## The options

Ranked by what to do. The ordering criterion is value delivered per unit of new
risk and new user obligation.

### 1. A mount contract — recommended

The module exports lifecycle functions rather than a component or an element:

```js
export default {
  mount(target, props, ctx) {
    // …build DOM in `target`; ctx.children is a host-owned node to place
    return {
      update(next) { /* props changed */ },
      destroy() { /* going away */ }
    };
  }
};
```

The client renders a container, awaits the module, calls `mount`, and calls
`update` from the same `$effect` that would otherwise be assigning properties.

- **For:**
  - **Reactivity is contractual.** `update(props)` is a call that either happens
    or throws. There is no arrangement of author mistakes that produces a
    silently stale block.
  - **Hot reload is possible** — destroy the instance, mount the new module.
    Component-local state is lost, which is correct for a code change, but the
    document does not remount and neither do the children. No other loading
    option can say this; see the note under option 2.
  - **The user pins their own Svelte** (or Lit, or nothing). DOM is the only
    thing crossing the boundary, and the two runtimes' module-level state cannot
    interact. This is the coupling in option 3 dissolved rather than managed.
  - **`parse_body: true` needs no shadow DOM and no slots.** The host renders
    children into a detached node it owns and keeps updating, and passes that
    node in `ctx` for the guest to place. Children updates stay entirely
    host-side, keyed and remount-free, and document CSS reaches them normally.
    Critically, the *host* never runs inside guest control flow — the guest
    receives a node, not a callback that re-enters our renderer.
  - Authoring in Svelte is a published preset away: a build that wraps a
    `.svelte` file's default export in `mount`/`unmount` is a few lines. The
    generated adapter is the whole of it:

    ```js
    // entry.svelte.js - what the preset emits
    import { mount, unmount } from 'svelte';
    import Chart from './Chart.svelte';
    export default {
      ABI: 1,
      mount(target, props, ctx) {
        const bag = $state({ ...props, childrenNode: ctx?.children ?? null });
        const app = mount(Chart, { target, props: bag });
        return { update: (next) => Object.assign(bag, next),
                 destroy: () => unmount(app) };
      }
    };
    ```
- **Against:**
  - **A bespoke ABI.** An off-the-shelf web component needs a five-line adapter,
    and we own the contract's versioning forever. Declare an ABI version in the
    manifest and refuse a mismatch into the existing dashed box.
  - **No style isolation.** A component's CSS and the document's can reach each
    other. Mitigable with a scoping class on the container, but it is a
    convention, not a boundary — shadow DOM would have made it one.
  - Slightly more for the author to write than a `.svelte` file alone.
  - **The guest carries its own runtime: 18.8 kB gzip measured**, on top of the
    component itself. Per bundle, not per instance, and only for authors who
    choose a framework — but it is the price of not sharing, and option 3 does
    not pay it.

### 2. Custom elements

Config names a module and a tag; the client imports it and renders
`<svelte:element this={tag}>`, letting props flow as described above.

- **For:**
  - **The ABI is a web standard.** Ecosystem components work as-is, and the
    contract is documented by someone other than us.
  - **Optional toolchain.** One file with `customElements.define` needs no build
    at all.
  - **Shadow DOM gives real style isolation**, and theming still works because
    custom properties (`--link`, `--muted`, `--code-bg`) inherit through the
    boundary. Slotted children stay in the light DOM, so document CSS reaches
    them too.
- **Against:**
  - **The reactivity gap above.** The host cannot guarantee a re-render, and the
    failure is silent.
  - **`customElements.define` is irreversible**, so component code cannot be
    hot-reloaded. The usual workaround — versioned tag names — remounts every
    instance *and* leaks a definition per reload, and Svelte's `setters_cache`
    is keyed by `nodeName` and never evicted, so it accumulates an entry per
    version too. The honest position is: config changes live, code changes want
    a page reload.
  - Prop delivery must wait on the import, per above.
- **Verdict:** the right answer if reuse of existing web components turns out to
  matter more than hot reload and a guaranteed update path. Nothing stops both
  from existing — a custom-element module is trivially wrappable in the option 1
  contract, which is a reason to make option 1 the primitive.

### 3. Svelte modules against a shared runtime

The user builds real `.svelte` files with a preset that marks `svelte` external
and aliases it to a shim reading the host's runtime off a global the client
publishes.

- **For:** the best authoring experience — real components, `$props()`, the
  `children` snippet passed straight through, compiler-scoped styles, identical
  to the two components in the repo today.
- **Against:** it couples every user's prebuilt bundle to
  `svelte/internal/client`, which is not a public API, so every Svelte minor is
  a potential break with a cryptic runtime error. Option 1 delivers most of the
  same authoring experience through a preset while letting the user pin their
  own Svelte, which makes this coupling a cost with no remaining benefit except
  passing snippets — and the spike shows a host-owned children node covers what
  snippets were needed for, with keyed updates intact.
- **Verdict:** superseded by option 1 unless someone produces a case that needs
  a real snippet rather than a rendered node.

### 4. Server-side expansion into ordinary nodes

The component never reaches the client: a config entry or Python entry point
expands the directive into standard doctree nodes carrying classes, styled by
the `raw` stylesheet support that already exists.

- **For:** zero client work, zero loading surface, works everywhere, and
  identity and partial updates keep working because the output is nodes the
  client already renders.
- **Against:** no interactivity, and the entry-point form reopens a decision
  DECISIONS.md closed deliberately — "custom directives are declared in
  `rstview.config.json`, config not Python plugins, so there is no user code to
  import" is load-bearing for the extension's bundling story. Importing user
  code into the vendored interpreter is the Esbonio failure mode that was
  designed away.
- **Verdict:** acceptable for the standalone tool, unacceptable for the
  extension, which makes it a fork in behaviour between hosts. Skip.

### 5. Declarative templates in config — rejected

An element tree with interpolation in `rstview.config.json`, walked by a
`Template.svelte` using `<svelte:element>`.

Cheap, safe, and it needed no trust gate, which is why the first draft of this
document led with it. **Rejected: too limited, with no path to expand.** It buys
a styled box and then dead-ends — the first person who wants a control or a
loop is asking for a template language, and growing one incrementally is how
you arrive at a bad programming language by accident. The untrusted-workspace
fallback it would have provided is served by the existing dashed box instead.

### 6. Ship the Svelte compiler to the browser

- **For:** no build step while still writing real Svelte.
- **Against:** blob-URL module imports need `script-src` widened with `blob:`,
  a direct downgrade of the webview's CSP for a convenience feature. Adds
  roughly a megabyte to a bundle that loads Shiki and KaTeX lazily and is proud
  of it. Compiler output imports `svelte/internal/client` anyway, so option 3's
  coupling comes along for the ride. Compiling server-side instead trades it for
  a Node runtime requirement the extension went to real lengths to avoid.
- **Verdict:** no.

### 7. Sandboxed iframes

- **For:** the only option that could safely run *document*-supplied code.
- **Against:** sizing, theming, printing, selection and accessibility all break
  or need rebuilding; host-rendered children cannot be projected, so
  `parse_body: true` has no meaning; cost is per instance.
- **Verdict:** keep in the drawer against a goal we do not have.

## Summary

| | update guaranteed | hot reload | user build | couples user to |
|---|---|---|---|---|
| 1 Mount contract | yes, by call | yes | preset or ~10 lines | our ABI version |
| 2 Custom elements | no, silent gap | no | optional | nothing |
| 3 Shared-runtime Svelte | yes | no | required | `svelte/internal` |
| 4 Server expansion | n/a, not interactive | yes | none | reopens a decision |
| 5 Templates | n/a | yes | none | nothing — but dead-ends |
| 6 Browser compiler | yes | yes | none | CSP, bundle size |
| 7 Iframes | yes, by message | yes | required | the wrong problem |

## What to do

Build **1**, and make it the primitive rather than one of two peers. The spikes
below were run before writing this line: the contract works, hot reload works,
the failure modes are contained, and the one thing that would have sunk it — a
CSP that refuses a cross-origin module — does not. A custom
element wraps into the mount contract in five lines, so shipping option 2 later
as a convenience adapter costs nothing and keeps the standard-ABI door open;
shipping it *first* would mean living with a silent staleness failure in the
core path.

Two things the spikes add to the build list, neither obvious from the design:
the update effect must skip the run in which the instance appears, and
`<svelte:boundary>` belongs around each instance for `update`, since only
`mount` is covered by the import's promise chain.

The server-side work is the same either way and is what to start on: a
`/components/{path}` route mirroring `resolve_asset` with a `.js` suffix rule, a
manifest in the `ready` message rather than an HTTP route, module paths resolved
relative to the config and contained within `--root`, the component files added
to the watcher's `extra`, and the workspace-trust gate in the extension.

All of that is specified, with milestones and failure modes, in
[COMPONENT_PLAN.md](COMPONENT_PLAN.md).

Presentation-only blocks stay `.. class::` plus a `raw` stylesheet. A component
that renders a coloured box is a component that did not need to exist.

## Spike results

Run 2026-09-05 against Svelte 5.57.0 and Chromium (Playwright). A host bundle
and a guest bundle were built separately, each with its own copy of Svelte, and
driven in a real browser. Harness in the session scratchpad (`spike/`), not
checked in.

**10/10 passed.** What each one settles:

| | result |
|---|---|
| Two Svelte runtimes in one page | both mount, update and tear down independently; `mount()` identities distinct |
| Host-owned children node, placed by the guest | host's second root renders into a detached node the guest appends |
| `update(props)` re-renders without remounting | guest element identity survived; 1 update call per change |
| Host keyed child updates after adoption | text changed in place, DOM identity preserved inside guest DOM |
| Inserting a child | untouched siblings reused, new one built, guest untouched |
| Hot reload by changing the module URL | destroy + remount, children node survived intact |
| ABI mismatch | refused into the dashed box, guest never mounted |
| Throwing `mount` | contained, rest of the document rendered |
| Throwing `update` | caught by `<svelte:boundary>` |
| Host snippet across the boundary | **guest fails to mount** |

Four findings that change the design rather than merely confirm it:

- **The snippet boundary is real, and it fails harder than predicted.** Handing
  a host snippet to a guest built against its own Svelte does not degrade to
  "the snippet does not render" — it throws inside the guest runtime
  (`TypeError: Cannot read properties of null (reading 'nodes')`) and takes the
  whole component down. A host-owned DOM node in the same position works
  perfectly. This is the strongest available argument for the mount contract
  over option 3, and it is now evidence rather than reasoning.

- **The update effect must skip its first run.** An effect that reads both
  `props` and `instance` fires the moment the instance lands, so every component
  takes a redundant `update()` before it is on screen — measured as 2 update
  calls for 1 prop change. Harmless for a pure component, wasteful for an
  expensive one, and wrong for anything that treats `update` as a delta. The
  loader tracks the last delivered props object and skips the run where the
  instance appears. Cheap to fix, easy to ship without noticing.

- **The children node survives a hot reload.** Because the host owns it and only
  the guest is destroyed and rebuilt, editing component code loses the
  component's own state but not the rendered document inside it. Better than
  expected.

- **`<svelte:boundary>` is load-bearing for `update`, not for `mount`.** A
  throwing `mount` is already contained by the promise chain around the dynamic
  import. A throwing `update` runs inside an effect and needs the boundary.

### S-A: the webview CSP

Tested separately against the exact policy from `extension/src/html.ts`
(`default-src 'none'; script-src 'nonce-…'`), with the module served from a
second origin to model `asWebviewUri`:

| | |
|---|---|
| same-origin dynamic `import()` | **loaded** |
| cross-origin, CORS allowed | **loaded**, no CSP violation reported |
| cross-origin, no CORS header | blocked |

So nonce inheritance does carry a dynamic import across origins, as spike S2
implied — **the constraint is CORS, not CSP.** That matters because it moves the
remaining risk somewhere much narrower: the extension already lists the
workspace root in `localResourceRoots` (`extension/src/preview.ts:24`), and
Shiki's lazy chunks prove VS Code serves *its* webview resources with headers a
module import accepts. What is still unverified is whether a file under the
**workspace root** is served the same way as one under `media`. Same mechanism
and same roots list, so it should be — but it has not been run inside a real
extension host, and that is the one thing left that could force module source
to be relayed over stdio instead.

Standalone is unaffected either way: the module is same-origin there, so the
`/components/` route needs no CORS header at all.

## What is left to verify

- **A file under the workspace root, imported inside a real extension host.**
  The narrowed remainder of S-A above. Everything else about option 1 is
  settled; this decides only *how the bytes arrive*, not the contract.
- **Two runtimes under the webview's CSP specifically.** The runtime spike ran
  in plain Chromium. Nothing in it touches `eval` or `blob:`, so there is no
  reason for the CSP to care, but the pair has not been run together.
- **A component that is not Svelte.** The contract is framework-agnostic by
  construction and the hand-written variants used in the failure-mode tests are
  proof it needs no framework at all, but a Lit component has not been tried.
