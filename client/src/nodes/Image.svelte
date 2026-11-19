<script>
  import { getContext, mount, unmount, onDestroy } from 'svelte';
  import { resolveAsset } from '../links.js';
  import ImageZoom from '../ImageZoom.svelte';

  let { node } = $props();

  const media = getContext('rst-media');
  const p = $derived(node.props);
  const src = $derived(resolveAsset(p.uri, media.path, media.base));

  let zoom = null;

  /** `:target:` wraps the image in a link, and then a click means follow it.
   *  Zooming instead would make the link unreachable.
   *
   *  The view is mounted on <body>, not here: inside `main` it would be in
   *  reach of the document's own stylesheet, and of any ancestor whose
   *  transform or overflow would trap a fixed-position overlay. */
  function open(event) {
    if (event.currentTarget.closest('a') || zoom) return;
    zoom = mount(ImageZoom, {
      target: document.body,
      props: { src, alt: p.alt ?? '', onclose: close }
    });
  }

  function close() {
    if (zoom) unmount(zoom);
    zoom = null;
  }

  // A live reload can remove the image while its view is open.
  onDestroy(close);
</script>

<!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_noninteractive_element_interactions -->
<img
  {src}
  alt={p.alt ?? ''}
  width={p.width}
  height={p.height}
  class={p.align ? `align-${p.align}` : undefined}
  onclick={open}
/>

<style>
  img { cursor: zoom-in; }
  :global(a) img { cursor: pointer; }
</style>
