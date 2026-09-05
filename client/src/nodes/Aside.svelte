<script>
  import Node from '../Node.svelte';

  /** `topic` and `sidebar` differ only in how they sit on the page.
   *
   *  Both carry their own `title` (and a sidebar may carry a `subtitle`),
   *  which must not go through the section-title mapping - that would emit an
   *  `<h1>`-`<h6>` sized by section depth and put the aside's label in the
   *  document outline. */
  let { node } = $props();

  const title = $derived(node.children?.find((c) => c.type === 'title'));
  const subtitle = $derived(node.children?.find((c) => c.type === 'subtitle'));
  const body = $derived(
    (node.children ?? []).filter((c) => c.type !== 'title' && c.type !== 'subtitle')
  );
  // `.. contents::` is a topic too, and it is furniture rather than an aside.
  const contents = $derived(node.props?.classes?.includes('contents'));
</script>

<aside
  id={node.props?.ids?.[0]}
  class="rst-aside {node.props?.classes?.join(' ') ?? ''}"
  data-kind={node.type}
  class:contents
>
  {#if title}
    <p class="aside-title" dir="auto">
      {#each title.children ?? [] as child (child.id)}<Node node={child} />{/each}
    </p>
  {/if}
  {#if subtitle}
    <p class="aside-subtitle" dir="auto">
      {#each subtitle.children ?? [] as child (child.id)}<Node node={child} />{/each}
    </p>
  {/if}
  {#each body as child (child.id)}
    <Node node={child} />
  {/each}
</aside>

<style>
  .rst-aside {
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 0.8rem 1rem;
    margin-block: calc(var(--block-gap) * 1.5);
    background: color-mix(in srgb, var(--code-bg) 60%, transparent);
  }
  /* A sidebar is meant to sit beside the text it accompanies. It only floats
     where there is room to; below that it behaves like a topic, which is the
     honest fallback rather than a 40%-wide column in a narrow pane. */
  @media (min-width: 55rem) {
    .rst-aside[data-kind='sidebar'] {
      float: inline-end;
      width: 40%;
      margin-inline-start: 1.2rem;
      margin-block-start: 0.3rem;
    }
  }
  .aside-title {
    font-weight: 600;
    font-size: 0.95em;
    margin: 0 0 0.4rem;
  }
  .aside-subtitle {
    color: var(--muted);
    font-size: 0.85em;
    margin: -0.3rem 0 0.5rem;
  }
  /* The table of contents is a list of links, not a bordered box. */
  .contents {
    border: none;
    background: none;
    padding: 0;
    border-inline-start: 2px solid var(--border);
    padding-inline-start: 1rem;
    border-radius: 0;
  }
  .rst-aside :global(> p:last-child) { margin-bottom: 0; }
</style>
