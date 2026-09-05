<script>
  import { setContext } from 'svelte';
  import Node from '../Node.svelte';

  /** Marks descendant entries as header cells. */
  let { node } = $props();
  setContext('rst-in-head', true);
</script>

<thead>
  {#each node.children ?? [] as child (child.id)}
    <Node node={child} />
  {/each}
</thead>
