/** Webview transport: the extension host relays to the Python child for us.
 *
 *  There is nothing to reconnect - `postMessage` cannot drop - so the status
 *  is permanently 'live' and child-process death arrives as an ordinary
 *  `error` message from the host.
 */
export function vscodeTransport() {
  const api = typeof acquireVsCodeApi === 'function' ? acquireVsCodeApi() : null;
  let onMessage = () => {};

  // Reloading the window destroys the webview and its child process; VS Code
  // hands the panel back to the extension with only whatever `setState` saved.
  // Recording the root and the open document is what lets the host revive a
  // restored panel instead of showing an empty one.
  const remembered = api?.getState?.() ?? {};

  window.addEventListener('message', (event) => {
    const message = event.data;
    if (message?.type === 'ready' && message.root) {
      remembered.root = message.root;
      api?.setState?.({ ...remembered });
    } else if (message?.type === 'doc' && message.path) {
      remembered.path = message.path;
      api?.setState?.({ ...remembered });
    }
    onMessage(message);
  });

  return {
    send(message) {
      if (!api) return false;
      api.postMessage(message);
      return true;
    },
    onMessage(callback) { onMessage = callback; },
    onStatus(callback) { callback('live'); }
  };
}
