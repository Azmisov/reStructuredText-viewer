<script>
  /** A task list item's box. Read-only: ticking it in a preview would change
   *  nothing in the file, and a box that moves and then snaps back on the
   *  next render is worse than one that does not move. */
  let { node } = $props();
</script>

<input type="checkbox" class="rst-task" checked={node.props.checked} disabled />
