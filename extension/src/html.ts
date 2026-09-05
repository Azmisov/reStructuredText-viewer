/** Rewrite the Vite `index.html` for a webview.
 *
 *  Pure, so it can be exercised without a VS Code host. Vite is built with
 *  `base: './'`, so every asset URL is relative and can be pointed at the
 *  webview's own origin - rewriting beats hand-writing the tags, because the
 *  hashed filenames change on every build.
 */
export function renderHtml(
  raw: string,
  assetUrl: (path: string) => string,
  cspSource: string,
  nonce: string
): string {
  // Verified in spike S2: a nonce-only `script-src` is enough. Dynamic
  // `import()` inherits the importing module's nonce, so Shiki's ~77 lazy
  // grammar and theme chunks load without the origin being listed.
  const csp = [
    "default-src 'none'",
    `script-src 'nonce-${nonce}'`,
    `style-src ${cspSource} 'unsafe-inline'`,
    `img-src ${cspSource} data:`,
    `font-src ${cspSource}`
  ].join('; ');

  return raw
    .replace(/(src|href)="\.\/([^"]+)"/g, (_, attribute, path) => `${attribute}="${assetUrl(path)}"`)
    .replace(/<script /g, `<script nonce="${nonce}" `)
    .replace('<head>', `<head>\n    <meta http-equiv="Content-Security-Policy" content="${csp}">`);
}
