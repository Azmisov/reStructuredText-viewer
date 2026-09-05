<script>
  import {
    SIMPLE, COMPONENTS, TRANSPARENT, HIDDEN, AUTO_DIR, TYPE_CLASS, Unknown
  } from './registry.js';
  import Node from './Node.svelte';

  /** Recursive dispatch on node.type. Keyed {#each} on the server's stable
   *  ids is what makes updates partial: unchanged subtrees keep their id, so
   *  Svelte leaves their DOM (and scroll, focus, component state) untouched. */
  let { node } = $props();

  const Component = $derived(COMPONENTS[node.type]);
  const tag = $derived(SIMPLE[node.type]);
  const classes = $derived(
    [TYPE_CLASS[node.type], ...(node.props?.classes ?? [])].filter(Boolean).join(' ')
  );
</script>

{#if node.type === 'text'}{node.value}{:else if HIDDEN.has(node.type)}{:else if Component}
  <Component {node} />
{:else if tag}
  <svelte:element
    this={tag}
    id={node.props?.ids?.[0]}
    class={classes || undefined}
    dir={AUTO_DIR.has(node.type) ? 'auto' : undefined}
  >
    {#each node.children ?? [] as child (child.id)}
      <Node node={child} />
    {/each}
  </svelte:element>
{:else if TRANSPARENT.has(node.type)}
  {#each node.children ?? [] as child (child.id)}
    <Node node={child} />
  {/each}
{:else}
  <Unknown {node} />
{/if}
