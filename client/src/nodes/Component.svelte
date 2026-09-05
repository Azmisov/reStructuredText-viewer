<script>
  import Node from '../Node.svelte';
  import { COMPONENTS } from '../components/index.js';

  let { node } = $props();

  const Target = $derived(COMPONENTS[node.props.name]);

  // `name` and `key` identify the block; everything else is a prop.
  const props = $derived(
    Object.fromEntries(
      Object.entries(node.props).filter(([k]) => k !== 'name' && k !== 'key')
    )
  );
</script>

{#if Target}
  <Target {...props}>
    {#each node.children ?? [] as child (child.id)}
      <Node node={child} />
    {/each}
  </Target>
{:else}
  <div class="missing">
    Unregistered component <code>{node.props.name}</code> — add it to
    <code>src/components/index.js</code>.
  </div>
{/if}

<style>
  .missing {
    border: 1px dashed var(--warn);
    color: var(--warn);
    padding: 0.5rem 0.75rem;
    border-radius: 4px;
    font-size: 0.85rem;
  }
</style>
