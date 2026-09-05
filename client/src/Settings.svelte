<script>
  import {
    MODES, DENSITIES, ALIGNMENTS,
    WIDTH_MIN, WIDTH_MAX, WIDTH_FULL, widthLabel
  } from './settings.svelte.js';
  import { LIGHT_THEMES, DARK_THEMES } from './themes.js';
  import { HOST_THEME } from './hostTheme.svelte.js';

  let { settings, onclose } = $props();

  // Only offered where there is an editor theme to match.
  const host = import.meta.env.VITE_TARGET === 'vscode';

  const v = $derived(settings.values);
  // 'system' and 'vscode' both defer to something outside the panel, so which
  // palette applies is not known here - label and show both.
  const following = $derived(v.mode === 'system' || v.mode === 'vscode');

  // 'vscode' would capitalize to 'Vscode'.
  const LABELS = { vscode: 'VS Code' };

  // Snapshot the bar's height once, so the panel does not drift downward as
  // the font-size setting grows the toolbar beneath the cursor.
  let top = $state(44);
  $effect(() => {
    const bar = document.querySelector('header.bar');
    if (bar) top = Math.round(bar.getBoundingClientRect().bottom + 6);
  });

  function onkeydown(event) {
    if (event.key === 'Escape') onclose();
  }
</script>

<svelte:window {onkeydown} />

<!-- Click-outside backdrop. Keyboard users get Escape and the close button. -->
<div class="backdrop" onclick={onclose} role="presentation"></div>

<div class="panel" role="dialog" aria-label="Settings" style:top="{top}px">
  <header>
    <h2>Settings</h2>
    <button class="close" onclick={onclose} aria-label="Close settings">×</button>
  </header>

  <label>
    <span>Appearance</span>
    <div class="segmented">
      {#each MODES as mode (mode)}
        <button class:selected={v.mode === mode} onclick={() => settings.set('mode', mode)}>
          {LABELS[mode] ?? mode}
        </button>
      {/each}
    </div>
  </label>

  <label>
    <span>Spacing</span>
    <div class="segmented">
      {#each DENSITIES as density (density)}
        <button
          class:selected={v.density === density}
          onclick={() => settings.set('density', density)}
        >
          {density}
        </button>
      {/each}
    </div>
  </label>

  <label>
    <span>Font size <em>{v.fontSize}px</em></span>
    <input
      type="range"
      min="12"
      max="24"
      step="1"
      value={v.fontSize}
      oninput={(e) => settings.set('fontSize', Number(e.currentTarget.value))}
    />
  </label>

  <label>
    <span>Content width <em>{widthLabel(v.maxWidth)}</em></span>
    <input
      type="range"
      min={WIDTH_MIN}
      max={WIDTH_MAX}
      step="2"
      value={v.maxWidth}
      oninput={(e) => settings.set('maxWidth', Number(e.currentTarget.value))}
    />
  </label>

  {#if v.maxWidth < WIDTH_FULL}
  <label>
    <span>Position</span>
    <div class="segmented">
      {#each ALIGNMENTS as align (align)}
        <button
          class:selected={v.align === align}
          onclick={() => settings.set('align', align)}
        >
          {align}
        </button>
      {/each}
    </div>
  </label>
  {/if}

  <label class="row">
    <span>Line numbers</span>
    <input
      type="checkbox"
      checked={v.lineNumbers}
      onchange={(e) => settings.set('lineNumbers', e.currentTarget.checked)}
    />
  </label>

  <label class="row">
    <span>Wrap long lines</span>
    <input
      type="checkbox"
      checked={v.wrapCode}
      onchange={(e) => settings.set('wrapCode', e.currentTarget.checked)}
    />
  </label>

  {#if v.mode !== 'dark'}
  <label>
    <span>Syntax theme{following ? ' (light)' : ''}</span>
    <select
      value={v.syntaxLight}
      onchange={(e) => settings.set('syntaxLight', e.currentTarget.value)}
    >
      {#if host}<option value={HOST_THEME}>match editor theme</option>{/if}
      {#each LIGHT_THEMES as name (name)}<option value={name}>{name}</option>{/each}
    </select>
  </label>
  {/if}

  {#if v.mode !== 'light'}
  <label>
    <span>Syntax theme{following ? ' (dark)' : ''}</span>
    <select
      value={v.syntaxDark}
      onchange={(e) => settings.set('syntaxDark', e.currentTarget.value)}
    >
      {#if host}<option value={HOST_THEME}>match editor theme</option>{/if}
      {#each DARK_THEMES as name (name)}<option value={name}>{name}</option>{/each}
    </select>
  </label>
  {/if}

  <footer>
    <button class="reset" onclick={() => settings.reset()}>Reset to defaults</button>
  </footer>
</div>

<style>
  .backdrop { position: fixed; inset: 0; z-index: 40; }
  .panel {
    position: fixed;
    /* Pinned in px, not rem: the font-size slider lives in here, and a panel
       that grows as you drag moves the slider out from under the cursor.
       Everything outside still previews live. */
    font-size: 13px;
    left: 12px;
    z-index: 50;
    width: 21em;
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: 8px;
    box-shadow: 0 8px 28px #0000002e;
    padding: 0.9em;
    display: flex;
    flex-direction: column;
    gap: 0.85em;
  }
  header { display: flex; align-items: center; justify-content: space-between; }
  h2 { font-size: 0.85em; margin: 0; }
  .close {
    background: none; border: none; color: var(--muted);
    font-size: 1.2em; line-height: 1; cursor: pointer; padding: 0 0.2em;
  }
  label { display: flex; flex-direction: column; gap: 0.35em; }
  label.row { flex-direction: row; align-items: center; justify-content: space-between; }
  label.row input { margin: 0; }
  label > span { color: var(--muted); display: flex; justify-content: space-between; }
  em { font-style: normal; color: var(--fg); font-variant-numeric: tabular-nums; }
  .segmented { display: flex; border: 1px solid var(--border); border-radius: 5px; overflow: hidden; }
  .segmented button {
    flex: 1; background: none; border: none; color: var(--fg);
    padding: 0.25em 0; cursor: pointer; font-size: 0.78em; text-transform: capitalize;
  }
  .segmented button + button { border-left: 1px solid var(--border); }
  .segmented button:hover { background: var(--code-bg); }
  .segmented button.selected { background: var(--link); color: #fff; }
  select, input[type='range'] { width: 100%; }
  select {
    background: var(--bg); color: var(--fg);
    border: 1px solid var(--border); border-radius: 5px; padding: 0.25em;
  }
  footer { border-top: 1px solid var(--border); padding-top: 0.7em; }
  .reset {
    background: none; border: 1px solid var(--border); color: var(--muted);
    border-radius: 5px; padding: 0.25em 0.5em; cursor: pointer; font-size: 0.78em;
  }
  .reset:hover { color: var(--fg); }
</style>
