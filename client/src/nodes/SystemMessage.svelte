<script>
  import Node from '../Node.svelte';

  /** Parse errors are content, not exceptions: one bad directive degrades
   *  its own region and leaves the rest of the document live. */
  let { node } = $props();
</script>

<aside class="rst-system-message" data-level={node.props.level}>
  <header>{node.props.type ?? 'INFO'}{node.props.line ? ` (line ${node.props.line})` : ''}</header>
  {#each node.children ?? [] as child (child.id)}
    <Node node={child} />
  {/each}
</aside>

<style>
  .rst-system-message {
    border-left: 3px solid var(--error);
    background: var(--error-bg);
    padding: 0.5rem 0.75rem;
    margin: 1rem 0;
    border-radius: 0 4px 4px 0;
  }
  header {
    font-size: 0.75rem;
    font-weight: 600;
    letter-spacing: 0.05em;
    color: var(--error);
  }
</style>
