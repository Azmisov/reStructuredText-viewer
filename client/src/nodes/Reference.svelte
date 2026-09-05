<script>
  import { getContext } from 'svelte';
  import Node from '../Node.svelte';
  import { isDocumentLink, resolveDocumentLink } from '../links.js';

  let { node } = $props();

  const navigate = getContext('rst-navigate');
  const refuri = $derived(node.props.refuri);

  // Three kinds: leaves the app, opens another document here, or jumps within
  // this one. All share the same underline; the marker distinguishes them.
  const internal = $derived(isDocumentLink(refuri));
  const external = $derived(Boolean(refuri) && !internal);
  // No URI at all, or a bare fragment: a jump within this document.
  const anchor = $derived(!external && !internal);
  const href = $derived(refuri ?? (node.props.refid ? `#${node.props.refid}` : undefined));

  function onclick(event) {
    if (!internal) return;
    // Leave modified clicks alone so "open in new tab" still works.
    if (event.metaKey || event.ctrlKey || event.shiftKey || event.button !== 0) return;
    event.preventDefault();
    navigate?.(refuri);
  }
</script>

<!-- External links open in a new tab so the preview is never navigated away
     from; in-document anchors and cross-document links stay in place. -->
<a
  {href}
  {onclick}
  class:external
  class:internal
  class:anchor
  target={external ? '_blank' : undefined}
  rel={external ? 'noopener noreferrer' : undefined}
>
  {#each node.children ?? [] as child (child.id)}
    <Node node={child} />
  {/each}
</a>

<style>
  a {
    text-decoration: underline;
    text-underline-offset: 0.15em;
  }

  /* A jump within this page is not a departure, and a document with many of
     them - a contents list, a table of cross-references - turns into a wall of
     rules. Colour and the # marker still identify it; the underline comes back
     on hover so the affordance is not lost. */
  a.anchor {
    text-decoration: none;
  }
  a.anchor:hover {
    text-decoration: underline;
  }

  /* Inside a table of contents every entry is an anchor, so the marker stops
     distinguishing anything and just adds noise to every line. */
  :global(.contents) a.anchor::after {
    content: none;
  }

  /* inline-block stops the parent's underline from running through the marker,
     which text-decoration would otherwise propagate into it. */
  a::after {
    display: inline-block;
    font-size: 0.72em;
    vertical-align: super;
    line-height: 1;
    margin-inline-start: 0.12em;
    opacity: 0.7;
  }

  /* ↗ leaves the app, § opens another document, # jumps within this one. */
  a.external::after { content: "\2197"; }
  a.internal::after { content: "\00A7"; }
  a.anchor::after { content: "#"; }
</style>
