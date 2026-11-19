<script>
  import { onMount } from 'svelte';

  /** Full-screen view of one image, zoomed and panned with pointer events so
   *  touch, pen and mouse share one path: one pointer drags, two pinch, a
   *  quick second tap (or a double click) toggles zoom, and the wheel zooms
   *  about the cursor. `touch-action: none` hands every gesture to us; left
   *  to the browser, a pinch would zoom the whole page behind the overlay.
   *
   *  The transform is `translate(x, y) scale(s)` about the image's centre,
   *  which at rest sits on the overlay's centre. Every zoom keeps the image
   *  point under the fingers (or cursor) where it was. */
  let { src, alt = '', onclose } = $props();

  const MAX = 8;
  /** Where a double tap lands: enough to read detail, not so much that the
   *  tap point is all there is. */
  const TAP_ZOOM = 2.5;
  const TAP_SLOP = 6;
  const DOUBLE_TAP_MS = 300;

  let overlay;
  let img;
  let closeButton;

  let scale = $state(1);
  let x = $state(0);
  let y = $state(0);
  /** Only the double-tap toggle animates; easing under a finger or the wheel
   *  makes the image trail behind the input. */
  let animate = $state(false);

  const pointers = new Map();
  let pinch = null;
  let press = null;
  let lastTap = null;

  onMount(() => {
    const previous = document.activeElement;
    const overflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    closeButton.focus();
    // Non-passive, or preventDefault cannot stop the page scrolling behind.
    overlay.addEventListener('wheel', wheel, { passive: false });
    return () => {
      document.body.style.overflow = overflow;
      previous?.focus?.();
    };
  });

  /** Panning stops at the image's edges: past them there is only backdrop. */
  function clamp(s, tx, ty) {
    const mx = Math.max(0, (img.offsetWidth * s - overlay.clientWidth) / 2);
    const my = Math.max(0, (img.offsetHeight * s - overlay.clientHeight) / 2);
    return [Math.min(mx, Math.max(-mx, tx)), Math.min(my, Math.max(-my, ty))];
  }

  /** Zoom to `next`, moving the image point that was under `from` (in the
   *  `base` transform) to `to`. A wheel step has from == to; a pinch also
   *  pans, by the distance its midpoint has travelled. */
  function zoom(next, from, to = from, base = { scale, x, y }) {
    next = Math.min(MAX, Math.max(1, next));
    const r = overlay.getBoundingClientRect();
    const cx = r.left + r.width / 2;
    const cy = r.top + r.height / 2;
    const k = next / base.scale;
    scale = next;
    [x, y] = clamp(
      next,
      to.x - cx - k * (from.x - cx - base.x),
      to.y - cy - k * (from.y - cy - base.y)
    );
  }

  function startPinch() {
    const [a, b] = pointers.values();
    pinch = {
      dist: Math.hypot(a.x - b.x, a.y - b.y) || 1,
      mid: { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 },
      scale,
      x,
      y
    };
  }

  function down(event) {
    if (event.pointerType === 'mouse' && event.button !== 0) return;
    if (event.target.closest('button')) return;
    event.preventDefault();
    overlay.setPointerCapture(event.pointerId);
    pointers.set(event.pointerId, { x: event.clientX, y: event.clientY });
    animate = false;
    if (pointers.size === 1) {
      press = { x: event.clientX, y: event.clientY, onImage: event.target === img };
    } else {
      // A second finger makes this a pinch, never a tap.
      if (press) press.moved = true;
      startPinch();
    }
  }

  function move(event) {
    const prev = pointers.get(event.pointerId);
    if (!prev) return;
    const now = { x: event.clientX, y: event.clientY };
    pointers.set(event.pointerId, now);
    if (pinch) {
      const [a, b] = pointers.values();
      const dist = Math.hypot(a.x - b.x, a.y - b.y);
      const mid = { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 };
      zoom(pinch.scale * (dist / pinch.dist), pinch.mid, mid, pinch);
      return;
    }
    if (press && Math.hypot(now.x - press.x, now.y - press.y) > TAP_SLOP) {
      press.moved = true;
    }
    if (scale > 1) [x, y] = clamp(scale, x + now.x - prev.x, y + now.y - prev.y);
  }

  function up(event) {
    if (!pointers.delete(event.pointerId)) return;
    // Lifting one of three fingers leaves a pinch; lifting one of two leaves
    // a drag, which carries on from where that finger already is.
    pinch = null;
    if (pointers.size >= 2) startPinch();
    if (pointers.size) return;
    if (press && !press.moved && event.type === 'pointerup') tap(event, press.onImage);
    press = null;
  }

  function tap(event, onImage) {
    const now = performance.now();
    const second =
      lastTap &&
      now - lastTap.t < DOUBLE_TAP_MS &&
      Math.hypot(event.clientX - lastTap.x, event.clientY - lastTap.y) < 30;
    if (second) {
      lastTap = null;
      animate = true;
      if (scale > 1) {
        scale = 1;
        x = 0;
        y = 0;
      } else {
        zoom(TAP_ZOOM, { x: event.clientX, y: event.clientY });
      }
      return;
    }
    lastTap = { x: event.clientX, y: event.clientY, t: now };
    // The backdrop closes only at rest: zoomed in, a stray tap beside the
    // image while panning would otherwise throw the view away.
    if (!onImage && scale === 1) onclose();
  }

  function wheel(event) {
    event.preventDefault();
    animate = false;
    const lines = event.deltaMode === 1 ? 16 : event.deltaMode === 2 ? 400 : 1;
    // A trackpad pinch arrives as a ctrl+wheel with small deltas.
    const rate = event.ctrlKey ? 0.01 : 0.002;
    const point = { x: event.clientX, y: event.clientY };
    zoom(scale * Math.exp(-event.deltaY * lines * rate), point);
  }

  function key(event) {
    if (event.key === 'Escape') {
      event.preventDefault();
      onclose();
    }
  }
</script>

<svelte:window onkeydown={key} />

<div
  class="overlay"
  class:zoomed={scale > 1}
  role="dialog"
  aria-modal="true"
  aria-label={alt || 'Image'}
  tabindex="-1"
  bind:this={overlay}
  onpointerdown={down}
  onpointermove={move}
  onpointerup={up}
  onpointercancel={up}
>
  <img
    bind:this={img}
    {src}
    {alt}
    draggable="false"
    class:animate
    style:transform="translate({x}px, {y}px) scale({scale})"
  />
  <button
    class="close"
    bind:this={closeButton}
    onclick={onclose}
    title="Close (Esc)"
    aria-label="Close"
  >×</button>
</div>

<style>
  .overlay {
    position: fixed;
    inset: 0;
    z-index: 1000;
    display: flex;
    align-items: center;
    justify-content: center;
    background: rgb(0 0 0 / 0.88);
    touch-action: none;
    overflow: hidden;
    user-select: none;
    -webkit-user-select: none;
    cursor: zoom-out;
    outline: none;
  }

  img {
    max-width: 100%;
    max-height: 100%;
    object-fit: contain;
    transform-origin: center;
    will-change: transform;
    cursor: zoom-in;
    /* Transparent images need something to sit on; the dark backdrop would
       swallow black line art. */
    background: #fff;
  }
  img.animate { transition: transform 0.18s ease; }
  .zoomed img { cursor: grab; }
  .zoomed img:active { cursor: grabbing; }

  .close {
    position: absolute;
    top: max(0.6rem, env(safe-area-inset-top));
    right: max(0.6rem, env(safe-area-inset-right));
    width: 2.6rem;
    height: 2.6rem;
    border: none;
    border-radius: 50%;
    background: rgb(0 0 0 / 0.55);
    color: #fff;
    font-size: 1.6rem;
    line-height: 1;
    cursor: pointer;
  }
  .close:hover,
  .close:focus-visible { background: rgb(255 255 255 / 0.2); }
</style>
