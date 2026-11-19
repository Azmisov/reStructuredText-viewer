<script>
  import Node from '../Node.svelte';

  /** Inline HTML from Markdown that docutils has no node for: `<kbd>`,
   *  `<mark>`, `<s>` and the like. The server only emits tags from its own
   *  allowlist; the list is repeated here so the page never renders an
   *  element named by the document just because the server passed it on. */
  const ALLOWED = new Set([
    'abbr', 'cite', 'del', 'dfn', 'ins', 'kbd', 'mark', 'q', 's', 'samp',
    'small', 'u', 'var'
  ]);

  let { node } = $props();

  const tag = $derived(ALLOWED.has(node.props.tag) ? node.props.tag : 'span');
</script>

<svelte:element
  this={tag}
  title={node.props.title}
  class={node.props.classes?.join(' ') || undefined}
>
  {#each node.children ?? [] as child (child.id)}
    <Node node={child} />
  {/each}
</svelte:element>
