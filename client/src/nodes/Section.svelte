<script>
  import { getContext, setContext } from 'svelte';
  import Node from '../Node.svelte';

  let { node } = $props();

  // Heading level is the section nesting depth; docutils doesn't record it.
  const depth = (getContext('rst-depth') ?? 0) + 1;
  setContext('rst-depth', depth);

  const anchor = node.props.ids?.[0] ?? node.id;
  // The title needs the section's anchor to compare against reading position.
  setContext('rst-section', anchor);
</script>

<section id={anchor}>
  {#each node.children ?? [] as child (child.id)}
    <Node node={child} />
  {/each}
</section>
