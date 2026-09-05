/** The editor's own colour theme, when running inside one.
 *
 *  The host posts its active theme as raw TextMate JSON, which is the same
 *  shape Shiki consumes - VS Code themes *are* TextMate themes plus a `colors`
 *  block - so no translation is needed, only `include` resolution, which the
 *  host does before sending.
 */
import { registerTheme } from './highlight.svelte.js';

/** The id a syntax-theme setting takes to mean "whatever the editor is using".
 *  A real name would go stale the moment the user switched theme. */
export const HOST_THEME = 'host';

export function createHostTheme() {
  let name = $state(null);
  let kind = $state(null);
  // Bumped on every successful load, so a rendered block can depend on "the
  // host theme changed" without depending on its contents.
  let epoch = $state(0);

  window.addEventListener('message', async (event) => {
    const message = event.data;
    if (message?.type !== 'host-theme' || !message.theme) return;

    // Some themes - VS Code's high-contrast ones among them - define no
    // editor background or foreground and let the workbench supply defaults.
    // Those defaults are live in the webview as CSS variables, so read them
    // back rather than guessing a colour that would not match the editor.
    const style = getComputedStyle(document.documentElement);
    const colors = { ...(message.theme.colors ?? {}) };
    const fill = (key, variable) => {
      const value = style.getPropertyValue(variable).trim();
      if (!colors[key] && value) colors[key] = value;
    };
    fill('editor.background', '--vscode-editor-background');
    fill('editor.foreground', '--vscode-editor-foreground');

    try {
      await registerTheme({ ...message.theme, colors });
      name = message.name;
      kind = message.kind;
      epoch += 1;
    } catch {
      // Highlighting keeps working with the built-in themes; a theme we cannot
      // load is not worth breaking the page over.
    }
  });

  return {
    get name() { return name; },
    get kind() { return kind; },
    get epoch() { return epoch; }
  };
}
