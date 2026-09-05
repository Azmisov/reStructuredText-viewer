<script>
  import Node from '../Node.svelte';

  /** `.. table::` gives the table a `title` child. Rendered through the normal
   *  `title` mapping it becomes a heading, which lands *inside* the table and
   *  splits it in two; a table's title is a `<caption>`. */
  let { node } = $props();

  const title = $derived(node.children?.find((c) => c.type === 'title'));
  const rest = $derived((node.children ?? []).filter((c) => c.type !== 'title'));
</script>

<table id={node.props?.ids?.[0]} class={node.props?.classes?.join(' ')}>
  {#if title}
    <caption>
      {#each title.children ?? [] as child (child.id)}<Node node={child} />{/each}
    </caption>
  {/if}
  {#each rest as child (child.id)}
    <Node node={child} />
  {/each}
</table>

<style>
  /* Styled as a banner row above the column headers rather than as floating
     text: a caption sitting loose above a bordered table reads as a stray
     paragraph. Same fill and padding as `th`, and no bottom border, so it
     meets the header row as one continuous box. */
  caption {
    caption-side: top;
    text-align: left;
    font-weight: 600;
    /* The table itself is 0.92em; the caption steps back up so it reads as
       the label of the block rather than as another cell. */
    font-size: 1.05em;
    color: var(--fg-strong);
    background: var(--code-bg);
    border: 1px solid var(--border);
    border-bottom: none;
    padding: calc(0.45rem * var(--gap-scale)) 0.75rem;
    line-height: 1.35;
  }
</style>
