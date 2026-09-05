import { defineConfig } from 'vite';
import { svelte } from '@sveltejs/vite-plugin-svelte';

// `rstview --dev` starts this server and passes the API port through, so the
// proxy targets whichever port uvicorn actually got.
const api = process.env.RSTVIEW_API_PORT ?? '8000';

// The VS Code build differs in two ways: the transport (selected in main.js
// from VITE_TARGET) and relative asset URLs, since a webview serves assets from
// a rewritten `vscode-webview://` origin rather than from `/`.
const vscode = process.env.VITE_TARGET === 'vscode';

export default defineConfig({
  plugins: [svelte()],
  base: vscode ? './' : '/',
  build: {
    outDir: vscode ? '../extension/media' : '../src/rstview/client',
    emptyOutDir: true,
    // Never inline a font. KaTeX ships one face small enough to fall under the
    // default 4kB threshold, and an inlined font is a `data:` URL - which the
    // webview's CSP would have to allow for every font just to serve that one.
    // A file keeps `font-src` at the origin alone.
    assetsInlineLimit: (file) => (/\.(woff2?|ttf|eot)$/i.test(file) ? false : undefined)
  },
  server: {
    proxy: {
      '/ws': { target: `ws://localhost:${api}`, ws: true },
      '/api': `http://localhost:${api}`,
      // Images a document points at. Without this every `.. image::` 404s
      // under `--dev` while working fine in the built client.
      '/media': `http://localhost:${api}`
    }
  }
});
