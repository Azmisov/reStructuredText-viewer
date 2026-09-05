/** TeX rendering, loaded on demand.
 *
 *  KaTeX and its stylesheet are a lazy chunk for the same reason the Shiki
 *  grammars are: most documents contain no maths, and neither the 270kB of
 *  JavaScript nor the font files should be on the path to a first paint.
 *
 *  It ships its own fonts rather than relying on whatever maths font the
 *  system happens to have, which is the whole reason for preferring it to a
 *  MathML renderer here - a preview that looks different on every machine is
 *  not much of a preview.
 */

// A promise, not a resolved value: two maths nodes rendering at once must not
// each start their own import. Same reasoning as the highlighter's caches.
let katexPromise = null;

function katex() {
  if (!katexPromise) {
    katexPromise = Promise.all([
      import('katex'),
      // Its own chunk, injected as a same-origin <link> - which is what the
      // webview's `style-src` allows.
      import('katex/dist/katex.min.css')
    ])
      .then(([module]) => module.default ?? module)
      .catch((error) => {
        // Let a transient chunk failure be retried rather than poisoning every
        // later render.
        katexPromise = null;
        throw error;
      });
  }
  return katexPromise;
}

/** Render `tex` to HTML. `display` picks block layout over inline.
 *
 *  Errors are rendered, not thrown: a typo in one formula should show up as a
 *  marked-up formula, not an empty space or a broken document.
 */
export async function renderMath(tex, display) {
  const engine = await katex();
  return engine.renderToString(tex, {
    displayMode: display,
    throwOnError: false,
    // KaTeX's own error colour is a hard red that ignores the page; ours
    // follows the theme.
    errorColor: 'currentColor',
    strict: false,
    output: 'html'
  });
}
