<script>
  /** Mini file dialog over the server's rooted filesystem view.
   *
   *  The browser cannot give a real path (`<input type=file>` hides it, and
   *  OPFS is a sandbox with no relation to the user's files), so browsing
   *  happens server-side where the path and its containment rules already live.
   *
   *  `browse` and `locate` come in as props rather than being fetched here:
   *  they go over whichever transport the connection holds, so the dialog works
   *  the same against a socket, an editor host, or the demo's fixtures.
   */
  import { untrack } from 'svelte';

  let {
    current = null,
    // A folder to open in instead of the current document's.
    start = null,
    // The server's root as an absolute path, which bookmarks are kept against.
    root = null,
    // An error from outside the dialog - a document that failed to open while
    // nothing else was - shown here because nothing else is on screen.
    notice = null,
    // False while nothing is open: there is no page behind the dialog to
    // return to, so Escape and the backdrop do nothing.
    dismissable = true,
    browse,
    locate,
    onpick,
    onclose
  } = $props();

  // Opens in the current document's folder. Deliberately the initial value
  // only: the dialog is remounted each time it opens, and after that the user
  // navigates freely without being yanked back when the document changes.
  let dir = $state(untrack(() => start ?? parentOf(current)));
  let entries = $state([]);
  let parent = $state(null);
  let error = $state(null);
  let loading = $state(false);

  let filter = $state('');
  let pasted = $state('');
  let cursor = $state(0);

  // Persist the view preferences; they are per-viewer conveniences.
  let showHidden = $state(pref('rstview-fp-hidden', false));
  let showAll = $state(pref('rstview-fp-all', false));
  let view = $state(pref('rstview-fp-view', 'list'));

  function pref(key, fallback) {
    try {
      const raw = localStorage.getItem(key);
      return raw === null ? fallback : JSON.parse(raw);
    } catch {
      return fallback;
    }
  }

  function remember(key, value) {
    try {
      localStorage.setItem(key, JSON.stringify(value));
    } catch {
      // A stored preference is a convenience, not a requirement.
    }
  }

  // --- Bookmarks -----------------------------------------------------------
  // Kept as absolute paths, not library-relative ones. Every rstview on a port
  // shares one origin and so one localStorage, whatever root each was started
  // with; a relative path would point somewhere different under each. One
  // outside this server's root is still listed, but cannot be opened here.
  const BOOKMARKS = 'rstview-bookmarks';
  let bookmarks = $state(pref(BOOKMARKS, []).filter((b) => typeof b === 'string'));

  // The root is reported in the server's own spelling: backslashes on Windows.
  const sep = $derived(root && root.includes('\\') && !root.includes('/') ? '\\' : '/');
  const prefix = $derived(root ? (root.endsWith(sep) ? root : root + sep) : null);

  function absoluteOf(relpath) {
    if (!relpath) return root;
    return prefix + relpath.split('/').join(sep);
  }

  /** The library path of a bookmark, or null if this root cannot reach it. */
  function relativeOf(absolute) {
    if (absolute === root) return '';
    if (!prefix || !absolute.startsWith(prefix)) return null;
    return absolute.slice(prefix.length).split(sep).join('/');
  }

  function labelOf(absolute) {
    const trimmed = absolute.length > 1 && absolute.endsWith(sep) ? absolute.slice(0, -1) : absolute;
    return trimmed.slice(trimmed.lastIndexOf(sep) + 1) || trimmed;
  }

  const here = $derived(root ? absoluteOf(dir) : null);
  const marked = $derived(here !== null && bookmarks.includes(here));

  function toggleBookmark() {
    if (here === null) return;
    bookmarks = marked ? bookmarks.filter((b) => b !== here) : [...bookmarks, here];
    remember(BOOKMARKS, bookmarks);
  }

  function unbookmark(absolute) {
    bookmarks = bookmarks.filter((b) => b !== absolute);
    remember(BOOKMARKS, bookmarks);
  }

  function goto(absolute) {
    const relpath = relativeOf(absolute);
    if (relpath === null) return;
    filter = '';
    load(relpath);
  }

  function parentOf(path) {
    if (!path) return '';
    const at = path.lastIndexOf('/');
    return at === -1 ? '' : path.slice(0, at);
  }

  async function load(path) {
    loading = true;
    error = null;
    try {
      const data = await browse(path, { hidden: showHidden, all: showAll });
      dir = data.path;
      parent = data.parent;
      entries = data.entries;
      cursor = 0;
    } catch (e) {
      error = e.message;
    } finally {
      loading = false;
    }
  }

  // Reloads when a filter toggle changes. `dir` is read untracked because
  // load() writes it: tracking it would fetch the same directory twice on
  // every navigation.
  $effect(() => {
    showHidden;
    showAll;
    untrack(() => load(dir));
  });

  const matches = $derived(
    filter.trim()
      ? entries.filter((e) => e.name.toLowerCase().includes(filter.trim().toLowerCase()))
      : entries
  );
  const index = $derived(Math.min(cursor, Math.max(0, matches.length - 1)));

  const crumbs = $derived(
    dir ? dir.split('/').map((name, i, all) => ({ name, path: all.slice(0, i + 1).join('/') })) : []
  );

  function activate(entry) {
    if (entry.kind === 'dir') {
      filter = '';
      load(entry.path);
    } else if (entry.kind === 'doc') {
      onpick(entry.path);
    }
  }

  /** Accepts an absolute or relative path; the server decides where it lands. */
  async function jump() {
    const text = pasted.trim();
    if (!text) return;
    error = null;
    try {
      const data = await locate(text);
      if (data.kind === 'dir') {
        pasted = '';
        load(data.path);
      } else if (data.kind === 'doc') {
        onpick(data.path);
      } else {
        error = `${text} is not a reStructuredText or Markdown file`;
      }
    } catch (e) {
      error = e.message;
    }
  }

  function onkeydown(event) {
    if (event.key === 'Escape') {
      if (dismissable) onclose();
      return;
    }
    if (event.key === 'ArrowDown') {
      cursor = Math.min(index + 1, matches.length - 1);
      event.preventDefault();
    } else if (event.key === 'ArrowUp') {
      cursor = Math.max(index - 1, 0);
      event.preventDefault();
    } else if (event.key === 'Enter' && matches[index]) {
      activate(matches[index]);
    } else if (event.key === 'Backspace' && !filter && parent !== null) {
      load(parent);
    }
  }

  const ICONS = { dir: '📁', doc: '📄', file: '·' };

  function size(bytes) {
    if (bytes === null || bytes === undefined) return '';
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
    return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
  }
</script>

<svelte:window {onkeydown} />

<div class="backdrop" onclick={() => dismissable && onclose()} role="presentation"></div>

<div class="dialog" role="dialog" aria-label="Open document">
  <header class="crumbs">
    <button class="crumb" onclick={() => load('')} title="Document root">root</button>
    {#each crumbs as crumb (crumb.path)}
      <span class="sep">/</span>
      <button class="crumb" onclick={() => load(crumb.path)}>{crumb.name}</button>
    {/each}
    {#if here !== null}
      <button
        class="star"
        class:on={marked}
        onclick={toggleBookmark}
        title={marked ? 'Remove bookmark' : 'Bookmark this folder'}
        aria-label={marked ? 'Remove bookmark' : 'Bookmark this folder'}
        aria-pressed={marked}>{marked ? '★' : '☆'}</button
      >
    {/if}
  </header>

  {#if bookmarks.length && root}
    <nav class="places" aria-label="Bookmarked folders">
      {#each bookmarks as bookmark (bookmark)}
        {@const reachable = relativeOf(bookmark) !== null}
        <span class="place" class:here={bookmark === here}>
          <button
            class="go-place"
            disabled={!reachable}
            onclick={() => goto(bookmark)}
            title={reachable ? bookmark : `${bookmark} is outside this server's root`}
          >★ {labelOf(bookmark)}</button>
          <button
            class="drop"
            onclick={() => unbookmark(bookmark)}
            title="Remove bookmark"
            aria-label="Remove bookmark {labelOf(bookmark)}">×</button
          >
        </span>
      {/each}
    </nav>
  {/if}

  <div class="controls">
    <!-- svelte-ignore a11y_autofocus -->
    <input
      class="filter"
      autofocus
      type="search"
      placeholder="Filter this folder…"
      bind:value={filter}
      oninput={() => (cursor = 0)}
      aria-label="Filter entries"
    />
    <label class="toggle">
      <input
        type="checkbox"
        checked={showHidden}
        onchange={(e) => { showHidden = e.currentTarget.checked; remember('rstview-fp-hidden', showHidden); }}
      /> hidden
    </label>
    <label class="toggle">
      <input
        type="checkbox"
        checked={showAll}
        onchange={(e) => { showAll = e.currentTarget.checked; remember('rstview-fp-all', showAll); }}
      /> all files
    </label>
    <div class="segmented">
      {#each ['list', 'icons'] as mode (mode)}
        <button
          class:selected={view === mode}
          onclick={() => { view = mode; remember('rstview-fp-view', mode); }}
          title="{mode} view"
        >
          {mode === 'list' ? '☰' : '▦'}
        </button>
      {/each}
    </div>
  </div>

  {#if error ?? notice}
    <p class="error">{error ?? notice}</p>
  {/if}

  <div class="body" class:icons={view === 'icons'}>
    {#if loading && !entries.length}
      <p class="muted">Loading…</p>
    {:else if !matches.length}
      <p class="muted">{filter ? 'Nothing matches.' : 'Empty folder.'}</p>
    {:else}
      {#if parent !== null && !filter}
        <button class="entry up" onclick={() => load(parent)}>
          <span class="icon">📁</span><span class="name">..</span>
        </button>
      {/if}
      {#each matches as entry, i (entry.path)}
        <button
          class="entry"
          class:selected={i === index}
          class:current={entry.path === current}
          data-kind={entry.kind}
          onclick={() => activate(entry)}
          ondblclick={() => activate(entry)}
          onmouseenter={() => (cursor = i)}
        >
          <span class="icon">{ICONS[entry.kind]}</span>
          <span class="name">{entry.name}</span>
          {#if view === 'list'}<span class="size">{size(entry.size)}</span>{/if}
        </button>
      {/each}
    {/if}
  </div>

  <footer>
    <input
      class="path"
      type="text"
      placeholder="Paste a path (absolute or relative)…"
      bind:value={pasted}
      onkeydown={(e) => { if (e.key === 'Enter') { e.stopPropagation(); jump(); } }}
      aria-label="Paste a path"
    />
    <button class="go" onclick={jump}>Go</button>
  </footer>
</div>

<style>
  .backdrop {
    position: fixed;
    inset: 0;
    z-index: 40;
    background: color-mix(in srgb, var(--bg) 45%, transparent);
    backdrop-filter: blur(4px);
    -webkit-backdrop-filter: blur(4px);
  }
  .dialog {
    position: fixed;
    top: 3rem;
    left: 50%;
    transform: translateX(-50%);
    z-index: 50;
    width: min(40rem, calc(100vw - 2rem));
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: 8px;
    box-shadow: 0 10px 34px #00000033;
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }

  .crumbs {
    display: flex;
    align-items: center;
    gap: 0.15rem;
    padding: 0.5rem 0.7rem;
    border-bottom: 1px solid var(--border);
    font-family: var(--mono);
    font-size: 0.78rem;
    overflow-x: auto;
    white-space: nowrap;
  }
  .crumb {
    background: none;
    border: none;
    color: var(--link);
    cursor: pointer;
    padding: 0.1rem 0.2rem;
    font: inherit;
    border-radius: 3px;
  }
  .crumb:hover { background: var(--code-bg); }
  .sep { color: var(--muted); }
  .star {
    margin-left: auto;
    flex: none;
    background: none;
    border: none;
    color: var(--muted);
    cursor: pointer;
    font-size: 0.95rem;
    line-height: 1;
    padding: 0.1rem 0.25rem;
    border-radius: 3px;
  }
  .star:hover { background: var(--code-bg); color: var(--fg); }
  .star.on { color: var(--link); }

  .places {
    display: flex;
    flex-wrap: wrap;
    gap: 0.3rem;
    padding: 0.4rem 0.7rem;
    border-bottom: 1px solid var(--border);
  }
  .place {
    display: inline-flex;
    align-items: stretch;
    border: 1px solid var(--border);
    border-radius: 999px;
    overflow: hidden;
    font-size: 0.75rem;
    max-width: 14rem;
  }
  .place.here { border-color: var(--link); }
  .place button {
    background: none;
    border: none;
    color: var(--fg);
    cursor: pointer;
    font: inherit;
  }
  .go-place {
    padding: 0.15rem 0.2rem 0.15rem 0.55rem;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .go-place:disabled { color: var(--muted); cursor: not-allowed; text-decoration: line-through; }
  .drop { color: var(--muted); padding: 0.15rem 0.45rem 0.15rem 0.25rem; }
  .place button:hover:not(:disabled) { background: var(--code-bg); }
  .drop:hover { color: var(--error); }

  .controls {
    display: flex;
    align-items: center;
    gap: 0.6rem;
    padding: 0.45rem 0.7rem;
    border-bottom: 1px solid var(--border);
    font-size: 0.78rem;
    color: var(--muted);
  }
  .filter {
    flex: 1;
    min-width: 6rem;
    border: 1px solid var(--border);
    border-radius: 4px;
    background: transparent;
    color: var(--fg);
    padding: 0.25rem 0.45rem;
    font-size: 0.82rem;
    outline: none;
  }
  .toggle { display: flex; align-items: center; gap: 0.25rem; cursor: pointer; white-space: nowrap; }
  .toggle input { margin: 0; }

  .segmented { display: flex; border: 1px solid var(--border); border-radius: 4px; overflow: hidden; }
  .segmented button {
    background: none; border: none; color: var(--fg);
    padding: 0.2rem 0.4rem; cursor: pointer; font-size: 0.8rem;
  }
  .segmented button + button { border-left: 1px solid var(--border); }
  .segmented button.selected { background: var(--link); color: #fff; }

  .body { padding: 0.35rem; max-height: 24rem; overflow-y: auto; }
  .body.icons {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(7.5rem, 1fr));
    gap: 0.2rem;
  }

  .entry {
    display: flex;
    align-items: center;
    gap: 0.45rem;
    width: 100%;
    text-align: left;
    background: none;
    border: none;
    color: var(--fg);
    font-family: var(--mono);
    font-size: 0.82rem;
    padding: 0.3rem 0.5rem;
    border-radius: 4px;
    cursor: pointer;
  }
  .body.icons .entry {
    flex-direction: column;
    gap: 0.2rem;
    text-align: center;
    padding: 0.6rem 0.3rem;
  }
  .body.icons .icon { font-size: 1.5rem; }
  .body.icons .name { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 100%; }
  .entry.selected { background: var(--code-bg); }
  .entry.current { color: var(--link); }
  .entry[data-kind='file'] { color: var(--muted); }
  .icon { flex: none; }
  .name { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .size { color: var(--muted); font-size: 0.72rem; flex: none; }

  footer {
    display: flex;
    gap: 0.4rem;
    padding: 0.5rem 0.7rem;
    border-top: 1px solid var(--border);
  }
  .path {
    flex: 1;
    border: 1px solid var(--border);
    border-radius: 4px;
    background: transparent;
    color: var(--fg);
    padding: 0.28rem 0.45rem;
    font-family: var(--mono);
    font-size: 0.78rem;
    outline: none;
  }
  .go {
    background: var(--link); color: #fff; border: none;
    border-radius: 4px; padding: 0.28rem 0.7rem; cursor: pointer; font-size: 0.8rem;
  }
  .error { color: var(--error); font-size: 0.8rem; margin: 0; padding: 0.5rem 0.7rem; }
  .muted { color: var(--muted); font-size: 0.85rem; margin: 0; padding: 1rem 0.7rem; }
</style>
