<script>
  import { setContext } from 'svelte';
  import { resolveDocumentLink } from './links.js';
  import { buildOutline } from './outline.js';
  import { createReading } from './reading.svelte.js';
  import { createSettings } from './settings.svelte.js';
  import { createHostTheme } from './hostTheme.svelte.js';
  import Settings from './Settings.svelte';
  import FilePicker from './FilePicker.svelte';
  import Outline from './Outline.svelte';
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
  // which has no server to fetch from; in a browser it is the media route.
  let mediaBase = $state('/media/');
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
    doc.open(path);
    if (browser) history.pushState({ path }, '', `?doc=${encodeURIComponent(path)}`);
    pendingHash = '';
    showPicker = false;
  }

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
    // Deep links: honour ?doc= on first load.
    const initial = new URLSearchParams(location.search).get('doc');
    if (initial) doc.open(initial);

    window.addEventListener('popstate', onpopstate);
    return () => window.removeEventListener('popstate', onpopstate);
  });

  let showOutline = $state(true);
  let showSettings = $state(false);
  let showPicker = $state(false);
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
    <span class="source">{doc.path ?? (doc.ready ? 'no document' : 'loading…')}</span>
  </span>
  <span class="right">
    <span class="status" data-status={doc.status}>{doc.status}</span>
  </span>
</header>

{#if showSettings}
  <Settings {settings} onclose={() => (showSettings = false)} />
{/if}

{#if showPicker && browser}
  <FilePicker
    current={doc.path}
    onpick={openDocument}
    onclose={() => (showPicker = false)}
  />
{/if}

<div class="layout" class:with-outline={showOutline}>
  {#if showOutline}
    <Outline entries={outline} active={reading.active} visible={reading.visible} />
  {/if}
  <main>
    {#if doc.error}
      <p class="failure">{doc.error}</p>
    {:else if doc.ast}
      <Node node={doc.ast} />
    {:else if doc.ready}
      <div class="welcome">
        <p>No document open.</p>
        {#if browser}
          <button onclick={() => (showPicker = true)}>
            Open a document…
          </button>
        {/if}
        <p class="hint">Root: <code>{doc.root ?? '…'}</code></p>
      </div>
    {:else}
      <p class="empty">Connecting…</p>
    {/if}
  </main>
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
    grid-template-columns: 15rem minmax(0, 1fr);
  }
  main {
    /* width:100% is load-bearing. `main` is a grid item, and auto margins
       disable the default `stretch`, which makes the item size to max-content
       instead of filling the column - so the rendered width tracked the
       content rather than the setting. */
    width: 100%;
    box-sizing: border-box;
    max-width: var(--content-width, 46rem);
    margin: var(--content-margin, 0 auto);
    /* The horizontal padding is what keeps prose off the edge of a narrow
       pane, where the max-width never binds and there are no auto margins to
       do it instead. */
    padding: calc(2rem * var(--gap-scale)) 1.75rem 6rem;
    min-width: 0;
  }
  .empty { color: var(--muted); }
  .welcome { color: var(--muted); padding: 3rem 0; text-align: center; }
  .welcome button {
    background: var(--link);
    color: #fff;
    border: none;
    border-radius: 5px;
    padding: 0.4rem 0.9rem;
    cursor: pointer;
    font-size: 0.9rem;
  }
  .hint { font-size: 0.8rem; }
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
     The column narrows first, and only disappears when it genuinely would
     squeeze the prose. */
  @media (max-width: 62rem) {
    .layout.with-outline { grid-template-columns: 12rem minmax(0, 1fr); }
  }
  @media (max-width: 40rem) {
    .layout.with-outline { display: block; }
    .layout.with-outline :global(.outline) { display: none; }
  }
</style>
