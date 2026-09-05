<script>
  import Node from '../Node.svelte';

  /** Footnotes and citations share a shape: a label plus a body. */
  let { node } = $props();
</script>

<div class="footnote" id={node.props.ids?.[0]}>
  {#each node.children ?? [] as child (child.id)}
    {#if child.type === 'label'}
      <span class="label">[<Node node={child} />]</span>
    {:else}
      <div class="body"><Node node={child} /></div>
    {/if}
  {/each}
</div>

<style>
  .footnote { display: flex; gap: 0.5rem; font-size: 0.9rem; margin: 0.4rem 0; }
  .label { color: var(--muted); flex: none; }
  .body :global(p) { margin: 0; }
</style>
