<script>
  import { getContext } from 'svelte';
  import Node from '../Node.svelte';
  import { highlight } from '../highlight.svelte.js';
  import { HOST_THEME } from '../hostTheme.svelte.js';

  let { node } = $props();

  const settings = getContext('rst-settings');
  const hostTheme = getContext('rst-host-theme');

  /** 'host' means the editor's live theme, whose real name is only known once
   *  it has arrived. Until then - and in a browser, always - fall back to a
   *  bundled theme of the right side. */
  function resolve(choice, fallback) {
    if (choice !== HOST_THEME) return choice;
    return hostTheme?.name ?? fallback;
  }

  const language = $derived(node.props.classes?.find((c) => c !== 'code'));
  const text = $derived(collect(node));

  /** `.. parsed-literal::` is a literal block whose *inline markup is parsed*,
   *  so it arrives with `strong`, `emphasis` and `reference` children. Running
   *  it through the highlighter would flatten all of that back to text, which
   *  is the one thing the directive exists to prevent. Highlighting is for
   *  blocks that are only text. */
  const parsed = $derived((node.children ?? []).some((c) => c.type !== 'text'));

  // Re-runs when the chosen syntax themes change; light/dark switching alone
  // needs no re-highlight, since both palettes are in the output already.
  const rendered = $derived.by(() => {
    // Depend on the epoch, not the theme object: a re-registered theme keeps
    // its name, so nothing else here would change when the user switches.
    hostTheme?.epoch;
    return highlight(text, language, {
      light: resolve(settings.values.syntaxLight, 'light-plus'),
      dark: resolve(settings.values.syntaxDark, 'dark-plus')
    });
  });

  let copied = $state(false);
  let timer;

  function collect(n) {
    if (n.type === 'text') return n.value;
    return (n.children ?? []).map(collect).join('');
  }

  async function copy() {
    try {
      await navigator.clipboard.writeText(text);
    } catch {
      // Clipboard access needs a secure context; fall back to a selection copy.
      const area = document.createElement('textarea');
      area.value = text;
      area.setAttribute('readonly', '');
      area.style.cssText = 'position:fixed;opacity:0';
      document.body.appendChild(area);
      area.select();
      try {
        document.execCommand('copy');
      } catch {
        return;
      } finally {
        area.remove();
      }
    }
    copied = true;
    clearTimeout(timer);
    timer = setTimeout(() => (copied = false), 1200);
  }
</script>

{#if parsed}
  <pre class="rst-literal-block parsed" dir="ltr"><code>{#each node.children ?? [] as child (child.id)}<Node node={child} />{/each}</code></pre>
{:else}
{#await rendered}
  <pre class="rst-literal-block"><code>{text}</code></pre>
{:then html}
  <!-- The wrapper carries no frame of its own: Shiki emits its own <pre>, and
       boxing that in a second bordered block draws the border twice. It exists
       only to position the hover toolbar. -->
  <div
    class="hl"
    class:numbered={settings.values.lineNumbers}
    class:wrapped={settings.values.wrapCode}
  >
    <div class="tools">
      {#if language}<span class="lang">{language}</span>{/if}
      <button onclick={copy} title="Copy code" aria-label="Copy code">
        {copied ? 'copied' : 'copy'}
      </button>
    </div>
    {@html html}
  </div>
{:catch}
  <pre class="rst-literal-block"><code>{text}</code></pre>
{/await}
{/if}

<style>
  /* Emphasis inside a parsed literal has to survive `pre`'s monospace: the
     markup is the content here, not decoration. */
  .parsed :global(strong) { font-weight: 700; }
  .parsed :global(em) { font-style: italic; }

  .hl {
    position: relative;
    margin-block: var(--block-gap);
  }

  /* Above the block, in flow. It always occupies its row - revealing it on
     hover must not reflow the page. */
  .tools {
    display: flex;
    justify-content: flex-end;
    align-items: center;
    gap: 0.4rem;
    margin-bottom: 0.2rem;
    font-size: 0.72rem;
    opacity: 0;
    transition: opacity 0.12s ease;
  }
  /* focus-within keeps it reachable by keyboard, where hover never fires. */
  .hl:hover .tools,
  .hl:focus-within .tools {
    opacity: 1;
  }

  .lang {
    color: var(--muted);
    font-family: var(--mono);
    text-transform: lowercase;
  }

  button {
    font: inherit;
    font-family: var(--mono);
    background: var(--bg);
    color: var(--fg);
    border: 1px solid var(--border);
    border-radius: 4px;
    padding: 0.1rem 0.4rem;
    cursor: pointer;
  }
  button:hover { border-color: var(--link); color: var(--link); }
</style>
