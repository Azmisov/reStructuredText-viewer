<script>
  import { setContext } from 'svelte';
  import { resolveDocumentLink } from './links.js';
  import { buildOutline } from './outline.js';
  import { createReading } from './reading.svelte.js';
  import {
    createSettings,
    WIDTH_MIN, WIDTH_MAX, WIDTH_FULL, widthLabel,
    SIDEBAR_MIN, SIDEBAR_MAX, SIDEBAR_SHARE
  } from './settings.svelte.js';
  import { createHostTheme } from './hostTheme.svelte.js';
  import Settings from './Settings.svelte';
  import FilePicker from './FilePicker.svelte';
  import Outline from './Outline.svelte';
  import ResizeHandle from './ResizeHandle.svelte';
  import Node from './Node.svelte';

  // The connection is built in main.js, where the transport is chosen.
  let { doc } = $props();

  const settings = createSettings();
  // Inert outside a webview: nothing ever posts a `host-theme` message there.
  const hostTheme = createHostTheme();

  // In VS Code the webview has no address bar and no session history; browser
  // navigation is a no-op there.
  // TODO(milestone 7): post navigation to the extension host instead.
  const browser = import.meta.env.VITE_TARGET !== 'vscode';

  // LiteralBlock needs the chosen syntax themes; passing them down through
  // every node would thread props through the whole recursive render.
  setContext('rst-settings', settings);
  setContext('rst-host-theme', hostTheme);

  // Outline data and reading position live here so the sidebar and the
  // document headings agree on which section is active.
  const outline = $derived(buildOutline(doc.ast));
  const reading = createReading(() => outline);
  setContext('rst-reading', reading);

  // Cross-document navigation: swap the document over the open socket and
  // record it in history, so Back works and no page reload occurs.
  function navigate(refuri, { push = true } = {}) {
    const { path, hash } = resolveDocumentLink(refuri, doc.path);
    if (!path) return;
    doc.open(path);
    if (push && browser) history.pushState({ path }, '', `?doc=${encodeURIComponent(path)}${hash ? '#' + hash : ''}`);
    pendingHash = hash;
  }
  setContext('rst-navigate', navigate);

  // Where images resolve from. The base is a message from the host in VS Code,
  // which has no server to fetch from; in a browser it is the media route,
  // under whatever base the bundle was built for - `/` for the server, a
  // project subpath for the Pages demo.
  let mediaBase = $state(import.meta.env.BASE_URL + 'media/');
  if (!browser) {
    window.addEventListener('message', (event) => {
      if (event.data?.type === 'media-base' && event.data.base) mediaBase = event.data.base;
    });
  }
  setContext('rst-media', {
    get path() { return doc.path; },
    get base() { return mediaBase; }
  });

  /** Open a library-relative path directly, as the picker supplies it. */
  function openDocument(path) {
    picked = path;
    startDir = null;
    doc.open(path);
    if (browser) history.pushState({ path }, '', `?doc=${encodeURIComponent(path)}`);
    pendingHash = '';
    showPicker = false;
  }

  // With nothing open there is nothing behind the dialog to go back to, so it
  // is open and cannot be dismissed until a document arrives. A pick that
  // fails lands back here, which is why its error is shown in the dialog.
  const mustPick = $derived(browser && doc.idle);
  // Where a remounted dialog starts: the last pick, if it failed to open, so
  // the reader is not thrown back to the root to find their place again.
  let picked = $state(null);
  // A folder the page was opened on (`?dir=`), as `rstview FOLDER` does.
  let startDir = $state(null);

  let pendingHash = $state('');

  // Live updates must not move the reader. Content that grows above the
  // viewport would otherwise push the page down under them - measured at 27px
  // drift for a single edited paragraph. $effect.pre runs before the DOM is
  // patched, so the anchor is captured against the old layout.
  let anchor = null;

  function anchorElements() {
    return [...document.querySelectorAll('main [id]')];
  }

  $effect.pre(() => {
    doc.version;
    anchor = null;
    if (!doc.ast) return;
    // The last anchor at or above the viewport top is the thing being read.
    for (const element of anchorElements()) {
      const top = element.getBoundingClientRect().top;
      if (top <= 0) anchor = { id: element.id, top };
      else break;
    }
  });

  $effect(() => {
    doc.version;
    const captured = anchor;
    anchor = null;
    // A fragment jump or a document switch is a deliberate move; don't undo it.
    if (!captured || pendingHash || doc.path !== anchoredPath) {
      anchoredPath = doc.path;
      return;
    }
    const element = document.getElementById(captured.id);
    if (!element) return;
    const delta = element.getBoundingClientRect().top - captured.top;
    if (delta) window.scrollBy(0, delta);
  });

  let anchoredPath = null;

  // Scroll to a link's fragment once the new document has actually rendered.
  $effect(() => {
    if (!doc.ast || !pendingHash) return;
    const target = document.getElementById(pendingHash);
    if (target) target.scrollIntoView();
    else window.scrollTo(0, 0);
    pendingHash = '';
  });

  $effect(() => {
    if (!browser) return;
    function onkeydown(event) {
      if ((event.ctrlKey || event.metaKey) && event.key === 'o') {
        event.preventDefault();
        showPicker = true;
      }
    }
    window.addEventListener('keydown', onkeydown);
    return () => window.removeEventListener('keydown', onkeydown);
  });

  $effect(() => {
    if (!browser) return;

    function onpopstate(event) {
      const path = event.state?.path ?? new URLSearchParams(location.search).get('doc');
      if (path) doc.open(path);
    }
    // Deep links: honour ?doc= on first load, and ?dir= by opening the
    // dialog in that folder.
    const params = new URLSearchParams(location.search);
    const initial = params.get('doc');
    if (initial) {
      picked = initial;
      doc.open(initial);
    } else if (params.has('dir')) {
      startDir = params.get('dir');
      showPicker = true;
    }

    window.addEventListener('popstate', onpopstate);
    return () => window.removeEventListener('popstate', onpopstate);
  });

  let showOutline = $state(true);
  let showSettings = $state(false);
  let showPicker = $state(false);

  // --- Drag-to-resize ------------------------------------------------------
  // Both bars write the same settings the panel's sliders do, in rem, so a
  // dragged width survives a reload and scales with the font size like a
  // chosen one.
  let layout = $state(), sidebar = $state(), column = $state(), page = $state();
  // Geometry measured when a drag starts; each move is applied to it.
  let start = null;

  // Fractional rem, so the edge follows the pointer instead of stepping.
  const quarter = (value) => Math.round(value * 4) / 4;
  const clamp = (value, low, high) => Math.min(high, Math.max(low, value));
  const remPx = () => parseFloat(getComputedStyle(document.documentElement).fontSize);

  function sidebarStart() {
    start = {
      width: sidebar.getBoundingClientRect().width,
      // The CSS caps the column at this share; dragging past it would store
      // a width the page never shows.
      limit: layout.clientWidth * SIDEBAR_SHARE
    };
  }

  function sidebarMove(dx) {
    const px = Math.min(start.width + dx, start.limit);
    settings.set('sidebarWidth', clamp(quarter(px / remPx()), SIDEBAR_MIN, SIDEBAR_MAX));
  }

  // Within this many rem of the column's edge, a dragged page width snaps to
  // full. Without it, "as wide as the window" is a target a pixel wide, and
  // missing it leaves a margin that reappears whenever the window grows.
  const SNAP = 3;

  // The bar sits on the edge that moves: a right-aligned column grows
  // leftward.
  const align = $derived(settings.values.align);

  function pageStart() {
    start = { width: page.getBoundingClientRect().width, room: column.clientWidth };
  }

  function pageMove(dx, { keyboard = false } = {}) {
    // A centred column moves both edges, so the dragged one tracks the
    // pointer only if the width changes twice as fast.
    const growth = align === 'center' ? 2 * dx : align === 'right' ? -dx : dx;
    const px = start.width + growth;
    const rem = remPx();
    // A key press moves a fixed step that the snap zone would swallow, so
    // the keyboard only reaches full at the edge itself.
    const zone = keyboard ? 0 : SNAP * rem * (align === 'center' ? 2 : 1);
    const full = px >= start.room - zone || px / rem >= WIDTH_FULL;
    settings.set('maxWidth', full ? WIDTH_FULL : Math.max(WIDTH_MIN, quarter(px / rem)));
  }
</script>

<header class="bar">
  <span class="left">
    <button
      onclick={() => (showSettings = !showSettings)}
      title="Settings"
      aria-label="Settings"
      aria-expanded={showSettings}>⚙</button
    >
    {#if browser}
      <!-- The served file dialog exists only because a browser cannot supply a
           real path. VS Code can, so milestone 7 replaces this with a quick-pick
           on the host side. -->
      <button class="open" onclick={() => (showPicker = true)} title="Open document (Ctrl+O)">
        Open…
      </button>
    {/if}
    <button
      onclick={() => (showOutline = !showOutline)}
      title="Toggle outline"
      aria-label="Toggle outline"
      aria-pressed={showOutline}>☰</button
    >
    <span class="source">{doc.path ?? (doc.ready ? '' : 'loading…')}</span>
  </span>
  <span class="right">
    <span class="status" data-status={doc.status}>{doc.status}</span>
  </span>
</header>

{#if showSettings}
  <Settings {settings} onclose={() => (showSettings = false)} />
{/if}

<!-- Not before `ready`: a dialog opened by `?dir=` would otherwise send its
     first lookup down a socket that is not open yet. -->
{#if browser && doc.ready && (showPicker || mustPick)}
  <FilePicker
    current={doc.path ?? picked}
    start={startDir}
    root={doc.root}
    notice={mustPick ? doc.error : null}
    dismissable={!mustPick}
    browse={doc.browse}
    locate={doc.locate}
    onpick={openDocument}
    onclose={() => { showPicker = false; startDir = null; }}
  />
{/if}

<div class="layout" class:with-outline={showOutline} bind:this={layout}>
  {#if showOutline}
    <div class="sidebar" bind:this={sidebar}>
      <Outline entries={outline} active={reading.active} visible={reading.visible} />
      {#if outline.length}
        <!-- Invisible at rest: the outline already reads as a column, and a
             permanent rule beside it would be one more line on the page. -->
        <ResizeHandle
          label="Outline width"
          value={settings.values.sidebarWidth}
          min={SIDEBAR_MIN}
          max={SIDEBAR_MAX}
          rest={0}
          onstart={sidebarStart}
          onmove={sidebarMove}
        />
      {/if}
    </div>
  {/if}
  <div class="column" bind:this={column}>
    <main bind:this={page}>
      {#if doc.error && !mustPick}
        <p class="failure">{doc.error}</p>
      {:else if doc.ast}
        <Node node={doc.ast} />
      {:else if !doc.ready}
        <p class="empty">Connecting…</p>
      {/if}
      <!-- Connected with nothing open: the page stays blank, and the dialog
           above it is the whole interface until something is picked. -->

    </main>
    <!-- Beside main rather than inside it: a document's own stylesheet is
         scoped to `main`, and must not be able to restyle or hide this. -->
    {#if doc.ast}
      <div class="page-edge {align}">
        <ResizeHandle
          label="Page width"
          value={settings.values.maxWidth}
          min={WIDTH_MIN}
          max={WIDTH_MAX}
          valuetext={widthLabel(settings.values.maxWidth)}
          onstart={pageStart}
          onmove={pageMove}
        />
      </div>
    {/if}
  </div>
</div>

<style>
  .bar {
    position: sticky;
    top: 0;
    z-index: 30;
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 1rem;
    padding: 0.5rem 1rem;
    min-height: var(--nav-height);
    box-sizing: border-box;
    background: var(--bar-bg);
    backdrop-filter: blur(6px);
    border-bottom: 1px solid var(--border);
    font-size: 0.8rem;
    color: var(--muted);
  }
  .left { display: flex; align-items: center; gap: 0.4rem; min-width: 0; }
  .source { font-family: var(--mono); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .open {
    background: none;
    border: 1px solid var(--border);
    color: var(--fg);
    border-radius: 4px;
    padding: 0.15rem 0.5rem;
    cursor: pointer;
    font-size: 0.78rem;
    flex: none;
  }
  .open:hover { background: var(--code-bg); }
  .right { display: flex; align-items: center; gap: 0.5rem; }
  .status[data-status='offline'] { color: var(--error); }
  .status[data-status='live'] { color: var(--ok); }
  /* The demo is served, not watched: honest about it rather than claiming live. */
  .status[data-status='demo'] { color: var(--muted); }
  .left button:not(.open) {
    background: none;
    border: 1px solid var(--border);
    color: var(--fg);
    border-radius: 4px;
    padding: 0.15rem 0.45rem;
    cursor: pointer;
    font-size: 0.9rem;
    line-height: 1.4;
  }
  .left button:not(.open):hover { background: var(--code-bg); }
  /* Toggles show their state: pressed reads as filled, not merely hovered. */
  .left button[aria-pressed='true'],
  .left button[aria-expanded='true'] {
    background: var(--link);
    border-color: var(--link);
    color: #fff;
  }
  .left button[aria-pressed='false'],
  .left button[aria-expanded='false'] {
    color: var(--muted);
  }

  .layout { display: block; }
  .layout.with-outline {
    display: grid;
    /* The share cap is what used to be a breakpoint that narrowed the column:
       a chosen width holds until the pane is too narrow to afford it, and
       then gives way to the prose rather than squeezing it. Keep the share in
       step with SIDEBAR_SHARE, which the drag clamps to. */
    grid-template-columns: min(var(--sidebar-width, 15rem), 35%) minmax(0, 1fr);
  }
  /* The outline and its drag bar side by side; both are sticky, and the
     column stretches to the page's height to give them room to stick. */
  .sidebar {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
  }
  .column {
    position: relative;
    min-width: 0;
  }
  main {
    /* width:100% is load-bearing. Auto margins on a grid item disable the
       default `stretch` and size it to max-content, so the rendered width
       tracked the content rather than the setting. `main` is no longer the
       grid item, but the width keeps it independent of which it is. */
    width: 100%;
    box-sizing: border-box;
    max-width: var(--content-width, 46rem);
    margin: var(--content-margin, 0 auto);
    /* The horizontal padding is what keeps prose off the edge of a narrow
       pane, where the max-width never binds and there are no auto margins to
       do it instead. */
    padding: calc(2rem * var(--gap-scale)) 1.75rem 6rem;
    min-width: 0;
    /* A long URL or inline literal is one unbreakable word, and on a phone
       one is enough to widen the whole page. Break it only where it would
       otherwise overflow; tables and code blocks scroll in place instead. */
    overflow-wrap: break-word;
  }
  /* Tracks main's moving edge in CSS rather than by measuring it: the gap
     beside a column of --content-width is all of the slack when aligned to
     one side, and half of it when centred. The bar's 12px land inside main's
     padding, so at full width it does not overhang the window. */
  .page-edge {
    position: absolute;
    top: 0;
    bottom: 0;
    --slack: calc(100% - min(100%, var(--content-width, 46rem)));
  }
  .page-edge.center { right: calc(var(--slack) / 2); }
  .page-edge.left { right: var(--slack); }
  .page-edge.right { left: var(--slack); }
  .empty { color: var(--muted); }
  .failure {
    color: var(--error);
    background: var(--error-bg);
    border-left: 3px solid var(--error);
    padding: 0.6rem 0.9rem;
    border-radius: 0 4px 4px 0;
    /* Server errors are one line, but setup failures arrive as a short
       numbered list of things to try; collapsing that into a paragraph is
       what makes an error unreadable. */
    white-space: pre-wrap;
    font-family: var(--mono);
    font-size: 0.85em;
    line-height: 1.5;
  }

  /* The outline needs room the page may not have; below this it would squeeze
     the prose column rather than help navigate it. */
  /* A VS Code preview beside an editor is roughly half a screen, which the old
     60rem cutoff hid the outline in - the place a document map is most useful.
     The column narrows first (the share cap above), and only disappears when
     it genuinely would squeeze the prose. */
  @media (max-width: 40rem) {
    .layout.with-outline { display: block; }
    .sidebar { display: none; }
  }
</style>
