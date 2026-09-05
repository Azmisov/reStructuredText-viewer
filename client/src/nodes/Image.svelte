<script>
  import { getContext } from 'svelte';
  import { resolveAsset } from '../links.js';

  let { node } = $props();

  const media = getContext('rst-media');
  const p = $derived(node.props);
  const src = $derived(resolveAsset(p.uri, media.path, media.base));
</script>

<img
  {src}
  alt={p.alt ?? ''}
  width={p.width}
  height={p.height}
  class={p.align ? `align-${p.align}` : undefined}
/>
