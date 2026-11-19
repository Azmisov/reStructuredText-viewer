<script>
  import { getContext, setContext } from 'svelte';
  import Node from '../Node.svelte';

  let { node } = $props();

  // Heading level is the section nesting depth; docutils doesn't record it.
  const depth = (getContext('rst-depth') ?? 0) + 1;
  setContext('rst-depth', depth);

  const anchor = node.props.ids?.[0] ?? node.id;
  // The title needs the section's anchor to compare against reading position.
  setContext('rst-section', anchor);

  // A section answers to every id it holds, not only the first: a reST
  // `.. _name:` or MyST `(name)=` target just above it adds one, as does a
  // Markdown heading's GitHub-style slug, and references resolve to those.
  const aliases = $derived(node.props.ids?.slice(1) ?? []);
</script>

<section id={anchor}>
  {#each aliases as alias (alias)}<span id={alias}></span>{/each}
  {#each node.children ?? [] as child (child.id)}
    <Node node={child} />
  {/each}
</section>
