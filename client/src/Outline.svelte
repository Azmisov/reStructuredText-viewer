<script>
  import ReadingMark from './ReadingMark.svelte';

  let { entries = [], active = null, visible = new Set() } = $props();
</script>

{#if entries.length}
  <nav class="outline" aria-label="Document outline">
    <ul>
      {#each entries as entry (entry.id)}
        <li style:--depth={entry.depth}>
          <!-- Every section on screen is marked; only the one being read
               carries the eye. -->
          <a
            href="#{entry.id}"
            class:active={active === entry.id}
            class:visible={visible.has(entry.id) && active !== entry.id}
          >
            <span class="mark">
              {#if active === entry.id}<ReadingMark />{/if}
            </span>
            <span class="label">{entry.text}</span>
          </a>
        </li>
      {/each}
    </ul>
  </nav>
{/if}

<style>
  .outline {
    /* Explicit, so the column matches the page rather than showing whatever
       sits behind it. */
    background: var(--bg);
    position: sticky;
    top: calc(var(--nav-height) + 0.5rem);
    align-self: start;
    max-height: calc(100vh - var(--nav-height) - 1.5rem);
    overflow-y: auto;
    padding: 1rem 0.5rem 2rem 1rem;
    font-size: 0.82rem;
    line-height: 1.4;
  }
  ul { list-style: none; margin: 0; padding: 0; }
  li { padding-left: calc((var(--depth) - 1) * 0.7rem); }
  a {
    display: flex;
    align-items: center;
    gap: 0.35rem;
    padding: 0.2rem 0.4rem;
    color: var(--muted);
    text-decoration: none;
    border-left: 2px solid transparent;
    border-radius: 0 3px 3px 0;
  }
  /* Reserved so the label does not shift when the mark appears. */
  .mark { width: 1em; flex: none; display: flex; justify-content: center; }
  .label { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  a:hover { color: var(--fg); background: var(--code-bg); }
  /* On screen but not the one being read: brought up to full text colour with
     a faint rule, so the group reads as a range without competing with the
     active entry. */
  a.visible {
    color: var(--fg);
    border-left-color: var(--border);
  }
  a.active {
    color: var(--link);
    border-left-color: var(--link);
    background: var(--code-bg);
  }
</style>
