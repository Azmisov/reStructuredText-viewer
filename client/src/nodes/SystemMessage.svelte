<script>
  import Node from '../Node.svelte';

  /** Parse errors are content, not exceptions: one bad directive degrades
   *  its own region and leaves the rest of the document live.
   *
   *  But the message is a note *about* the document rather than part of it,
   *  and a full-width box gives an INFO about a two-character overline more
   *  weight on the page than the prose it interrupts. So the node collapses
   *  to a chip carrying level and line, and the text itself opens on hover,
   *  on focus, or pinned by a click.
   *
   *  SEVERE is the exception: it is what a document that did not render at
   *  all comes back as, and a chip alone on a blank page explains nothing.
   */
  let { node } = $props();

  // docutils numbers its levels 1-4 and also names them in `type`; the number
  // is the reliable half - a custom reporter can write anything into the name.
  const LEVELS = { 1: 'info', 2: 'warning', 3: 'error', 4: 'severe' };

  const kind = $derived(
    LEVELS[Number(node.props.level)] ?? String(node.props.type ?? 'info').toLowerCase()
  );
  const popupId = $derived(`sysmsg-${String(node.id).replace(/\s+/g, '-')}`);
  const severe = $derived(kind === 'severe');

  // Hover and focus open the popup in CSS alone, which is what lets the
  // pointer travel from the chip onto the message without it closing.
  // `pinned` is the third way in: a tap, or a click that should outlast it.
  let pinned = $state(false);
  let shift = $state(0);
  let chip = $state(null);
  let popup = $state(null);

  /** Keep the popup on screen. It hangs off the chip's leading edge, and a
   *  chip on the far side of the column would otherwise run past the viewport
   *  - which in a webview means clipped, not scrollable. The popup is laid
   *  out even while hidden, so this can measure it without opening it. */
  function place() {
    if (!chip || !popup) return;
    const margin = 8;
    const left = chip.getBoundingClientRect().left;
    const overflow = left + popup.offsetWidth - (window.innerWidth - margin);
    shift = overflow > 0 ? -Math.min(overflow, left - margin) : 0;
  }

  $effect(() => {
    if (severe) return;
    // Re-measured on resize; the chip's own position moves only when the
    // column does, and every way to move the column reflows the window.
    place();
    window.addEventListener('resize', place);
    return () => window.removeEventListener('resize', place);
  });

  /** Pinned means "stays open once the pointer leaves", so it needs the two
   *  ways out that a pointer gets for free. */
  $effect(() => {
    if (!pinned) return;
    const onKey = (e) => {
      if (e.key === 'Escape') {
        pinned = false;
        chip?.focus();
      }
    };
    const onDown = (e) => {
      if (!chip?.parentElement?.contains(e.target)) pinned = false;
    };
    window.addEventListener('keydown', onKey);
    window.addEventListener('pointerdown', onDown);
    return () => {
      window.removeEventListener('keydown', onKey);
      window.removeEventListener('pointerdown', onDown);
    };
  });
</script>

{#if severe}
  <aside class="rst-system-message panel" data-kind={kind}>
    <header>{node.props.type ?? 'SEVERE'}{node.props.line ? ` (line ${node.props.line})` : ''}</header>
    {#each node.children ?? [] as child (child.id)}
      <Node node={child} />
    {/each}
  </aside>
{:else}
  <span class="rst-system-message" data-kind={kind} class:pinned>
    <button
      type="button"
      bind:this={chip}
      aria-expanded={pinned}
      aria-controls={popupId}
      onclick={() => {
        pinned = !pinned;
        place();
      }}
    >
      reST {kind}{node.props.line ? ` · line ${node.props.line}` : ''}
    </button>
    <span class="popup" id={popupId} role="note" bind:this={popup} style:--shift={`${shift}px`}>
      {#each node.children ?? [] as child (child.id)}
        <Node node={child} />
      {/each}
    </span>
  </span>
{/if}

<style>
  .rst-system-message {
    position: relative;
    display: inline-block;
    /* The chip stands in for a block-level node, so it sits on the text
       baseline of a line box of its own. */
    vertical-align: middle;
  }

  /* The uncollapsed form, for a document that has nothing else to show. */
  .panel {
    display: block;
    border-inline-start: 3px solid var(--error);
    background: var(--error-bg);
    padding: 0.5rem 0.75rem;
    margin: 1rem 0;
    border-radius: 0 4px 4px 0;
  }
  .panel header {
    font-size: 0.75rem;
    font-weight: 600;
    letter-spacing: 0.05em;
    color: var(--error);
  }

  button {
    display: inline-flex;
    align-items: baseline;
    gap: 0.35em;
    font: inherit;
    font-size: 0.72rem;
    line-height: 1.6;
    padding: 0.05rem 0.55rem;
    border-radius: 999px;
    cursor: pointer;
    color: var(--muted);
    background: var(--code-bg);
    border: 1px solid var(--border);
  }
  button::before {
    content: '\2139';
    font-weight: 700;
  }
  button:hover,
  button:focus-visible {
    border-color: currentColor;
  }

  [data-kind='warning'] button {
    color: var(--warn);
    background: color-mix(in srgb, var(--warn) 10%, transparent);
    border-color: color-mix(in srgb, var(--warn) 35%, transparent);
  }
  [data-kind='error'] button,
  [data-kind='severe'] button {
    color: var(--error);
    background: var(--error-bg);
    border-color: color-mix(in srgb, var(--error) 35%, transparent);
  }
  /* Shape as well as colour, so warning and error still read apart in a
     high-contrast or monochrome theme. */
  [data-kind='warning'] button::before,
  [data-kind='error'] button::before,
  [data-kind='severe'] button::before {
    content: '\26A0';
  }

  .popup {
    position: absolute;
    z-index: 5;
    top: 100%;
    inset-inline-start: 0;
    transform: translateX(var(--shift, 0px));
    /* A real gap below the chip would close the popup as the pointer crossed
       it; the margin belongs to the popup, which is already hovered. */
    margin-top: 0.3rem;
    display: block;
    width: max-content;
    max-width: min(28rem, calc(100vw - 2rem));
    max-height: 60vh;
    overflow: auto;
    padding: 0.5rem 0.75rem;
    font-size: 0.85rem;
    text-align: start;
    /* Sets the stripe and any chrome; the message text re-states --fg so it
       stays body-weight whatever the level tints the frame. */
    color: var(--muted);
    background: var(--bg);
    border: 1px solid var(--border);
    border-inline-start: 3px solid currentColor;
    border-radius: 0 4px 4px 0;
    box-shadow: 0 4px 16px rgb(0 0 0 / 0.18);
    /* Hidden, not absent: it stays laid out so its width can be measured, and
       visibility:hidden takes it out of the accessibility tree either way. */
    visibility: hidden;
    opacity: 0;
    pointer-events: none;
  }
  .rst-system-message:hover .popup,
  .rst-system-message:focus-within .popup,
  .rst-system-message.pinned .popup {
    visibility: visible;
    opacity: 1;
    pointer-events: auto;
  }

  [data-kind='warning'] .popup { color: var(--warn); }
  [data-kind='error'] .popup,
  [data-kind='severe'] .popup { color: var(--error); }

  .popup :global(p) { margin: 0.35rem 0; color: var(--fg); }
  .popup :global(p:first-child) { margin-top: 0; }
  .popup :global(p:last-child) { margin-bottom: 0; }
  /* Where docutils quotes the offending source back, the literal block keeps
     its own frame, wrapping and copy button - all it needs here is to stop
     carrying document-sized margins inside a popup. */
  .popup :global(.hl),
  .popup :global(pre) {
    margin-block: 0.4rem 0;
    font-size: 0.85em;
  }
</style>
