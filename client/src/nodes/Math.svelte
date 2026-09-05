<script>
  import { renderMath } from '../math.svelte.js';

  let { node, display = false } = $props();

  const tex = $derived(collect(node));
  const rendered = $derived(renderMath(tex, display));

  function collect(n) {
    if (n.type === 'text') return n.value;
    return (n.children ?? []).map(collect).join('');
  }
</script>

{#await rendered}
  <!-- The source, so the formula is readable while KaTeX loads and remains
       readable if it never does. -->
  <code class="pending" class:display>{tex}</code>
{:then html}
  {#if display}
    <div class="math-block">{@html html}</div>
  {:else}
    <span class="math-inline">{@html html}</span>
  {/if}
{:catch}
  <code class="pending" class:display>{tex}</code>
{/await}

<style>
  .pending {
    font-family: var(--mono);
    color: var(--muted);
  }
  .pending.display {
    display: block;
    text-align: center;
  }
  .math-block {
    overflow-x: auto;
    /* A long equation scrolls rather than widening the column, and keeps the
       block rhythm of everything around it. */
    margin-block: var(--block-gap);
  }
</style>
