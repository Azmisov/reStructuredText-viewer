<script>
  /** A vertical bar that resizes whatever it borders.
   *
   *  It reports how far it has been dragged, not where to: only the owner
   *  knows what that distance means - an edge that moves alone, or one of a
   *  centred pair that moves symmetrically - so the owner measures its own
   *  geometry in `onstart` and applies each `onmove(dx)` to that snapshot.
   *  Measuring once per drag, rather than per move, keeps the layout the drag
   *  is changing from feeding back into it.
   *
   *  Arrow keys move it by 1rem (4 with Shift), reported the same way with
   *  `{ keyboard: true }`, so an owner that snaps can tell a fixed step from
   *  a pointer and not swallow the step.
   */
  let {
    label,
    value,
    min,
    max,
    valuetext = undefined,
    // Opacity of the bar with the pointer far away. It ramps to full as the
    // pointer approaches, so a bar can be faint, or absent, until wanted.
    rest = 0.3,
    onstart,
    onmove
  } = $props();

  // Pointer distance, in px, at which the bar starts to come up.
  const RANGE = 120;

  let element;
  let near = $state(0);
  let dragging = $state(false);
  let originX = 0;

  const opacity = $derived(rest + (1 - rest) * near);

  function approach(event) {
    if (event.pointerType !== 'mouse' || dragging || !element) return;
    const rect = element.getBoundingClientRect();
    const distance = Math.abs(event.clientX - (rect.left + rect.width / 2));
    near = Math.max(0, 1 - distance / RANGE);
  }

  // `mouseout` with no destination is the pointer leaving the window.
  function leave(event) {
    if (!event.relatedTarget) near = 0;
  }

  function onpointerdown(event) {
    if (event.button !== 0) return;
    // No text selection starts under a drag.
    event.preventDefault();
    element.setPointerCapture(event.pointerId);
    originX = event.clientX;
    dragging = true;
    document.documentElement.classList.add('rst-resizing');
    onstart();
  }

  function onpointermove(event) {
    if (dragging) onmove(event.clientX - originX);
  }

  function stop() {
    if (!dragging) return;
    dragging = false;
    document.documentElement.classList.remove('rst-resizing');
  }

  function onkeydown(event) {
    const direction = { ArrowLeft: -1, ArrowRight: 1 }[event.key];
    if (!direction) return;
    event.preventDefault();
    const rem = parseFloat(getComputedStyle(document.documentElement).fontSize);
    onstart({ keyboard: true });
    onmove(direction * rem * (event.shiftKey ? 4 : 1), { keyboard: true });
  }
</script>

<svelte:window onpointermove={approach} />
<svelte:document onmouseout={leave} />

<!-- A focusable separator is the ARIA pattern for a splitter; it needs a value
     to be one, which is why the owner passes the width it controls. Svelte's
     lint counts every separator as static, which only the unfocusable kind is. -->
<!-- svelte-ignore a11y_no_noninteractive_tabindex, a11y_no_noninteractive_element_interactions -->
<div
  bind:this={element}
  class="handle"
  class:dragging
  role="separator"
  aria-orientation="vertical"
  aria-label={label}
  aria-valuenow={value}
  aria-valuemin={min}
  aria-valuemax={max}
  aria-valuetext={valuetext}
  tabindex="0"
  style:--opacity={opacity}
  {onpointerdown}
  {onpointermove}
  onpointerup={stop}
  onpointercancel={stop}
  onlostpointercapture={stop}
  {onkeydown}
></div>

<style>
  .handle {
    /* Pinned to the viewport while the page scrolls past, so the bar is
       always within reach rather than at the top of a long document. */
    position: sticky;
    top: var(--nav-height);
    align-self: start;
    /* Short of the full viewport: the bar can grow past --nav-height, and a
       handle reaching the bottom would then give a short page a scrollbar. */
    height: calc(100vh - var(--nav-height) - 1rem);
    /* The hit area is wider than the line, which is too thin to grab. */
    width: 12px;
    display: flex;
    justify-content: center;
    cursor: col-resize;
    /* Otherwise a touch drag scrolls the page instead. */
    touch-action: none;
  }
  .handle::before {
    content: '';
    width: 1px;
    margin-top: 0.75rem;
    background: var(--muted);
    opacity: var(--opacity);
    transition: opacity 120ms, width 120ms, background-color 120ms;
  }
  .handle:hover::before,
  .handle:focus-visible::before {
    width: 3px;
    opacity: 1;
  }
  .handle:focus-visible { outline: none; }
  .handle.dragging::before {
    width: 3px;
    opacity: 1;
    background: var(--link);
  }
  /* Pointer capture keeps the events, not the cursor: without this the cursor
     reverts to whatever it passes over, and the drag selects text. */
  :global(:root.rst-resizing),
  :global(:root.rst-resizing *) {
    cursor: col-resize !important;
    user-select: none !important;
    -webkit-user-select: none !important;
  }
</style>
