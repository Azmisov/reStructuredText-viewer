<script>
  import Node from '../Node.svelte';

  let { node } = $props();
</script>

<sup><a href={node.props.refid ? `#${node.props.refid}` : undefined} id={node.props.ids?.[0]}
  >[{#each node.children ?? [] as child (child.id)}<Node node={child} />{/each}]</a
></sup>
