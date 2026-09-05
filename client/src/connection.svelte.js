/** Live document state, fed by the server over a transport.
 *
 *  The connection tracks which document is open; cross-document links switch
 *  it by sending an `open` message rather than reloading the page, so scroll,
 *  settings and the highlighter's loaded grammars all survive navigation.
 *
 *  The transport is `{ send, onMessage, onStatus }` - a WebSocket in the
 *  standalone app, the VS Code host relay in the extension. Nothing below
 *  knows which.
 */
export function createConnection(transport) {
  let ast = $state(null);
  let version = $state(0);
  let path = $state(null);
  let status = $state('connecting');
  let error = $state(null);
  let documents = $state([]);
  let root = $state(null);
  let entry = $state(null);
  let ready = $state(false);

  let wanted = null; // Survives a reconnect so we reopen the right document.

  transport.onStatus((next) => {
    status = next;
    // A transport that reconnects comes back blank; ask for the document again.
    if (next === 'live' && wanted) transport.send({ type: 'open', path: wanted });
  });

  transport.onMessage((message) => {
    if (message.type === 'doc') {
      // A push for a document we've navigated away from is stale.
      if (wanted && message.path !== wanted) return;
      ast = message.ast;
      version = message.version ?? version + 1;
      path = message.path;
      wanted = message.path;
      error = null;
    } else if (message.type === 'ready') {
      entry = message.entry;
      root = message.root ?? null;
      ready = true;
    } else if (message.type === 'list') {
      documents = message.documents ?? [];
    } else if (message.type === 'error') {
      error = message.message;
    }
  });

  return {
    get ast() { return ast; },
    get path() { return path; },
    /** Server-side render counter. The scroll-anchor effects key off it so a
     *  re-render is a distinct trigger from a document switch. */
    get version() { return version; },
    get status() { return status; },
    get error() { return error; },
    get documents() { return documents; },
    get root() { return root; },
    get entry() { return entry; },
    /** True once the server has said what it holds - distinguishes "still
     *  connecting" from "connected, but no document open". */
    get ready() { return ready; },
    refresh() { transport.send({ type: 'list' }); },
    open(next) {
      if (!next || next === wanted) return;
      wanted = next;
      error = null;
      transport.send({ type: 'open', path: next });
    }
  };
}
