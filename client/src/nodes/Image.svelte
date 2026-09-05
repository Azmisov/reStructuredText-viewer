<script>
  let { node } = $props();
  const p = $derived(node.props);
</script>

<img
  src={p.uri}
  alt={p.alt ?? ''}
  width={p.width}
  height={p.height}
  class={p.align ? `align-${p.align}` : undefined}
/>
