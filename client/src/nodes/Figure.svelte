<script>
  import Node from '../Node.svelte';

  /** docutils puts caption and legend inside the figure alongside the image. */
  let { node } = $props();
</script>

<figure class={node.props.align ? `align-${node.props.align}` : undefined}>
  {#each node.children ?? [] as child (child.id)}
    {#if child.type === 'caption'}
      <figcaption><Node node={child} /></figcaption>
    {:else}
      <Node node={child} />
    {/if}
  {/each}
</figure>
