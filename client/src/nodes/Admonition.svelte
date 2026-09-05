<script>
  import Node from '../Node.svelte';

  /** note, warning, tip, danger, … all share one shape. docutils gives the
   *  specific ones no title node, so derive the label from the type. */
  let { node } = $props();

  const hasTitle = $derived(node.children?.some((c) => c.type === 'title'));
  const label = $derived(node.type === 'admonition' ? '' : node.type);
</script>

<aside class="admonition" data-kind={node.type}>
  {#if !hasTitle && label}<header>{label}</header>{/if}
  {#each node.children ?? [] as child (child.id)}
    {#if child.type === 'title'}
      <header><Node node={child} /></header>
    {:else}
      <Node node={child} />
    {/if}
  {/each}
</aside>

<style>
  .admonition {
    border-left: 3px solid var(--muted);
    background: var(--code-bg);
    padding: 0.6rem 0.9rem;
    margin: 1.25rem 0;
    border-radius: 0 4px 4px 0;
  }
  .admonition[data-kind='warning'],
  .admonition[data-kind='caution'],
  .admonition[data-kind='attention'] { border-color: var(--warn); }
  .admonition[data-kind='danger'],
  .admonition[data-kind='error'] { border-color: var(--error); }
  .admonition[data-kind='tip'],
  .admonition[data-kind='hint'] { border-color: var(--ok); }
  /* docutils' built-in admonition types, marked so the kind reads at a glance
     rather than from the label alone. */
  header::before {
    content: "\1F4CC";
    margin-inline-end: 0.4em;
    font-size: 1.1em;
    vertical-align: -0.05em;
  }
  [data-kind='note'] header::before { content: "\1F4DD"; }
  [data-kind='tip'] header::before,
  [data-kind='hint'] header::before { content: "\1F4A1"; }
  [data-kind='important'] header::before { content: "\2757"; }
  [data-kind='attention'] header::before { content: "\1F4E3"; }
  [data-kind='warning'] header::before,
  [data-kind='caution'] header::before { content: "\26A0\FE0F"; }
  [data-kind='danger'] header::before { content: "\26D4"; }
  [data-kind='error'] header::before { content: "\274C"; }

  header {
    font-size: 0.75rem;
    font-weight: 600;
    letter-spacing: 0.05em;
    text-transform: uppercase;
    color: var(--muted);
    margin-bottom: 0.3rem;
  }
  .admonition :global(p:first-of-type) { margin-top: 0; }
  .admonition :global(p:last-child) { margin-bottom: 0; }
</style>
