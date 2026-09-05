/** Flatten the AST's section tree into a document outline.
 *
 *  Anchors reuse the same id Section.svelte puts on the DOM element, so
 *  clicking an entry is a plain fragment link with no scroll bookkeeping. */
export function buildOutline(ast, depth = 1, out = []) {
  for (const node of ast?.children ?? []) {
    if (node.type === 'section') {
      const title = node.children?.find((c) => c.type === 'title');
      out.push({
        id: node.props.ids?.[0] ?? node.id,
        text: title ? textOf(title) : '(untitled)',
        depth
      });
      buildOutline(node, depth + 1, out);
    } else if (node.type === 'document') {
      buildOutline(node, depth, out);
    }
  }
  return out;
}

function textOf(node) {
  if (node.type === 'text') return node.value;
  return (node.children ?? []).map(textOf).join('');
}
