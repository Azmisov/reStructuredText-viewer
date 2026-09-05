<script>
  import Node from '../Node.svelte';

  /** Fallback for docutils types with no mapping yet.
   *  Renders children so an unhandled type degrades instead of vanishing. */
  let { node } = $props();
</script>

<div class="rst-unknown" data-rst-type={node.type}>
  {#each node.children ?? [] as child (child.id)}
    <Node node={child} />
  {/each}
</div>

<style>
  .rst-unknown {
    border-left: 2px dashed var(--warn);
    padding-left: 0.5rem;
  }
</style>
