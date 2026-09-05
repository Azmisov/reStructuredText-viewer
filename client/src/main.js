import { mount } from 'svelte';
import App from './App.svelte';
import { createConnection } from './connection.svelte.js';
import { websocketTransport } from './transports/websocket.js';
import { vscodeTransport } from './transports/vscode.js';
import './app.css';
// Scoped entirely to body.vscode-*, so it costs a browser nothing.
import './vscode.css';

// Vite inlines VITE_TARGET as a literal, so the branch folds at build time and
// the transport this bundle doesn't use is dropped along with its globals.
const transport = import.meta.env.VITE_TARGET === 'vscode'
  ? vscodeTransport()
  : websocketTransport();

mount(App, {
  target: document.getElementById('app'),
  props: { doc: createConnection(transport) }
});
