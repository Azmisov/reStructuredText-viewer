<script>
  /** `.. raw:: html`, of which only style blocks are honoured.
   *
   *  Raw markup stays dropped: rendering it would mean `{@html}` on
   *  document-supplied content, handing any file you open authority over the
   *  page showing it - scripts, event handlers, injected UI. CSS cannot
   *  execute, so a stylesheet is a narrower thing to allow, and it is the part
   *  authors actually want: a place to define the classes that `.. class::`
   *  and custom roles attach.
   *
   *  Three things keep it narrow:
   *
   *  1. Only the contents of style elements are read, by pattern, and they
   *     are applied as *text*. Nothing here ever parses document content as
   *     HTML, so there is no path from raw markup to an element.
   *  2. The rules are wrapped in `main { … }` using native CSS nesting, so a
   *     document can restyle its own body and cannot reach the toolbar, the
   *     outline, the settings panel or the file dialog. A document that hides
   *     the chrome you would use to close it is not a document you can
   *     escape.
   *  3. `@import` is stripped, so a stylesheet cannot pull in a remote one.
   */
  let { node } = $props();

  // Assembled from fragments on purpose: writing the tag literally here
  // makes Svelte's own parser treat it as this component's style block, and
  // the build then fails trying to compile the regex as CSS.
  const TAG = 'style';
  const STYLE_BLOCK = new RegExp(`<${TAG}\\b[^>]*>([\\s\\S]*?)</${TAG}>`, 'gi');

  const css = $derived(extract(node));

  function text(n) {
    if (n.type === 'text') return n.value;
    return (n.children ?? []).map(text).join('');
  }

  function extract(n) {
    if (n.props?.format !== 'html') return '';
    const source = text(n);
    const blocks = [...source.matchAll(STYLE_BLOCK)].map((match) => match[1]);
    if (!blocks.length) return '';
    return blocks
      .join('\n')
      // Nested inside a style rule an @import is invalid and would be dropped
      // by the parser anyway; removing it here makes that a decision rather
      // than an accident.
      .replace(/@import[^;]*;?/gi, '')
      .trim();
  }

  $effect(() => {
    if (!css) return;
    // Built as an element with textContent, never parsed as markup: assigning
    // textContent cannot create nodes, so a smuggled closing tag is inert.
    const element = document.createElement('style');
    element.dataset.rstviewRaw = '';
    element.textContent = `main {\n${css}\n}`;
    document.head.append(element);
    return () => element.remove();
  });
</script>
