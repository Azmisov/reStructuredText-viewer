<script>
  import Node from '../Node.svelte';

  /** The document root, which exists to put page furniture where it belongs.
   *
   *  docutils collects `.. header::` and `.. footer::` into a single
   *  `decoration` node placed *first* in the doctree, so rendering children in
   *  order puts the footer at the top of the page - where it reads as a stray
   *  paragraph before the title. Splitting them is the whole job. */
  let { node } = $props();

  const decoration = $derived(node.children?.find((c) => c.type === 'decoration'));
  const body = $derived((node.children ?? []).filter((c) => c.type !== 'decoration'));
  const pageHeader = $derived(decoration?.children?.find((c) => c.type === 'header'));
  const pageFooter = $derived(decoration?.children?.find((c) => c.type === 'footer'));
</script>

{#if pageHeader}
  <div class="furniture top">
    {#each pageHeader.children ?? [] as child (child.id)}<Node node={child} />{/each}
  </div>
{/if}

{#each body as child (child.id)}
  <Node node={child} />
{/each}

{#if pageFooter}
  <div class="furniture bottom">
    {#each pageFooter.children ?? [] as child (child.id)}<Node node={child} />{/each}
  </div>
{/if}

<style>
  /* Page furniture, not body copy: set apart so it does not read as another
     paragraph of the document. */
  .furniture {
    color: var(--muted);
    font-size: 0.85em;
  }
  .top {
    border-bottom: 1px solid var(--border);
    padding-bottom: 0.5rem;
    margin-bottom: var(--block-gap);
  }
  .bottom {
    border-top: 1px solid var(--border);
    padding-top: 0.5rem;
    margin-top: calc(var(--block-gap) * 2);
  }
  .furniture :global(p) { margin: 0.25rem 0; }
</style>
