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

  // The file dialog's two lookups are the only request/response pairs in an
  // otherwise push-only protocol, so they carry an id and land here rather
  // than in the state above.
  let nextId = 1;
  const pending = new Map();

  transport.onStatus((next) => {
    status = next;
    if (next !== 'live') {
      // A dropped transport will never answer; a dialog hung forever is worse
      // than one showing an error.
      for (const { reject } of pending.values()) reject(new Error('connection lost'));
      pending.clear();
    }
    // A transport that reconnects comes back blank; ask for the document again.
    if (next === 'live' && wanted) transport.send({ type: 'open', path: wanted });
  });

  function request(payload) {
    const id = nextId++;
    return new Promise((resolve, reject) => {
      if (!transport.send({ ...payload, id })) return reject(new Error('not connected'));
      pending.set(id, { resolve, reject });
    });
  }

  transport.onMessage((message) => {
    if (message.id != null && pending.has(message.id)) {
      const { resolve, reject } = pending.get(message.id);
      pending.delete(message.id);
      // A failed lookup belongs to the dialog that asked for it, not to the
      // document pane, so it must not fall through to the `error` branch.
      if (message.type === 'error') reject(new Error(message.message));
      else resolve(message);
      return;
    }
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
    /** One directory's contents, for the file dialog. */
    browse(path, { hidden = false, all = false } = {}) {
      return request({ type: 'browse', path: path ?? '', hidden, all });
    },
    /** Resolve a pasted path - absolute or relative - to a library path. */
    locate(path) { return request({ type: 'locate', path }); },
    open(next) {
      if (!next || next === wanted) return;
      wanted = next;
      error = null;
      transport.send({ type: 'open', path: next });
    }
  };
}
