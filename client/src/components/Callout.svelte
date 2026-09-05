<script>
  /** Example component with a parsed reST body: children render through the
   *  normal Node pipeline, so markup inside the block still works. */
  // A directive's positional argument arrives as `argument`.
  let { kind = 'note', title = '', argument = '', children } = $props();

  const heading = $derived(title || argument || kind);
</script>

<aside class="callout" data-kind={kind}>
  <header>{heading}</header>
  <div class="body">{@render children?.()}</div>
</aside>

<style>
  .callout {
    border-left: 3px solid var(--link);
    background: var(--code-bg);
    padding: 0.6rem 0.9rem;
    margin: 1.25rem 0;
    border-radius: 0 4px 4px 0;
  }
  .callout[data-kind='warning'] { border-color: var(--warn); }
  .callout[data-kind='danger'] { border-color: var(--error); }
  header {
    font-size: 0.75rem;
    font-weight: 600;
    letter-spacing: 0.05em;
    text-transform: uppercase;
    color: var(--muted);
    margin-bottom: 0.3rem;
  }
  .body :global(p:first-child) { margin-top: 0; }
  .body :global(p:last-child) { margin-bottom: 0; }
</style>
