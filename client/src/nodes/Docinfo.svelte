<script>
  import Node from '../Node.svelte';

  /** Bibliographic fields: a reST document's leading field list, or Markdown
   *  front matter.
   *
   *  docutils promotes the fields it recognises - author, version, date and
   *  so on - to node types of their own and drops the field name, so the
   *  label comes back from the type. Fields it does not recognise stay
   *  ordinary fields and render as one. */
  let { node } = $props();

  const LABELS = {
    author: 'Author',
    authors: 'Authors',
    organization: 'Organization',
    address: 'Address',
    contact: 'Contact',
    version: 'Version',
    revision: 'Revision',
    status: 'Status',
    date: 'Date',
    copyright: 'Copyright'
  };
</script>

<dl class="rst-docinfo">
  {#each node.children ?? [] as child (child.id)}
    {#if child.type === 'authors'}
      <div>
        <dt>{LABELS.authors}</dt>
        <dd>
          {#each child.children ?? [] as author, i (author.id)}{#if i},
            {/if}<Node node={author} />{/each}
        </dd>
      </div>
    {:else if LABELS[child.type]}
      <div>
        <dt>{LABELS[child.type]}</dt>
        <dd><Node node={child} /></dd>
      </div>
    {:else}
      <Node node={child} />
    {/if}
  {/each}
</dl>
