<script>
  import { getContext } from 'svelte';
  import Node from '../Node.svelte';
  import ReadingMark from '../ReadingMark.svelte';

  let { node } = $props();

  const level = Math.min(getContext('rst-depth') ?? 1, 6);
  const anchor = getContext('rst-section');
  const reading = getContext('rst-reading');

  const isReading = $derived(anchor != null && reading?.active === anchor);
</script>

<svelte:element this={`h${level}`} dir="auto">
  {#each node.children ?? [] as child (child.id)}
    <Node node={child} />
  {/each}
  {#if isReading}<span class="mark"><ReadingMark /></span>{/if}
</svelte:element>

<style>
  .mark {
    color: var(--link);
    margin-inline-start: 0.45em;
    vertical-align: middle;
  }
</style>
