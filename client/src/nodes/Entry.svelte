<script>
  import { getContext } from 'svelte';
  import Node from '../Node.svelte';

  /** docutils expresses spans as extra cells covered, not total cells. */
  let { node } = $props();

  const inHead = getContext('rst-in-head') === true;
  const colspan = $derived(node.props.morecols ? node.props.morecols + 1 : undefined);
  const rowspan = $derived(node.props.morerows ? node.props.morerows + 1 : undefined);
</script>

<svelte:element this={inHead ? 'th' : 'td'} {colspan} {rowspan}>
  {#each node.children ?? [] as child (child.id)}
    <Node node={child} />
  {/each}
</svelte:element>
