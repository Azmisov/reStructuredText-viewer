<script>
  /** Example component: a sparkline-style bar chart.
   *  Props arrive coerced by the server from directive options. */
  let { series = [], title = '', height = 80 } = $props();

  const values = $derived(Array.isArray(series) ? series : []);
  const max = $derived(Math.max(1, ...values));
</script>

<figure class="chart">
  {#if title}<figcaption>{title}</figcaption>{/if}
  <div class="bars" style:height="{height}px">
    {#each values as value, i (i)}
      <div class="bar" style:height="{(value / max) * 100}%" title={String(value)}></div>
    {/each}
  </div>
</figure>

<style>
  .chart { margin: 1.5rem 0; }
  figcaption { font-size: 0.8rem; color: var(--muted); margin-bottom: 0.4rem; }
  .bars { display: flex; align-items: flex-end; gap: 3px; }
  .bar { flex: 1; background: var(--link); border-radius: 2px 2px 0 0; min-height: 2px; }
</style>
