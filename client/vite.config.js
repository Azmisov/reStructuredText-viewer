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
    emptyOutDir: true
  },
  server: {
    proxy: {
      '/ws': { target: `ws://localhost:${api}`, ws: true },
      '/api': `http://localhost:${api}`
    }
  }
});
