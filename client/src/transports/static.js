/** Fixture transport for the published demo.
 *
 *  There is no server behind the Pages site, so the messages one would have
 *  produced for `samples/` are generated at build time by `scripts/fixtures.py`
 *  and replayed here. The vocabulary is the real one - `ready`, `doc`, `list`,
 *  and the dialog's two lookups - so nothing above this file knows the
 *  difference; what is missing is only the half a static host cannot have:
 *  the watcher pushing a new `doc` when a file changes.
 *
 *  Document ASTs are fetched per document rather than bundled. The showcase
 *  corpus renders to a few hundred kB of JSON, which has no business being in
 *  the entry chunk when a visitor reads one page of it.
 */
const BASE = import.meta.env.BASE_URL;

export function staticTransport() {
  let onMessage = () => {};
  let onStatus = () => {};
  let manifest = null;
  const cache = new Map();

  // Queued until whoever mounts us has registered their handlers, which
  // happens after this function returns.
  const backlog = [];
  let started = false;

  function emit(message) {
    if (started) onMessage(message);
    else backlog.push(message);
  }

  const ready = fetch(`${BASE}fixtures.json`)
    .then((response) => response.json())
    .then((data) => {
      manifest = data;
      onStatus('demo');
      emit({ type: 'ready', entry: data.entry, root: data.root });
      if (data.entry) return open(data.entry);
    })
    .catch((error) => {
      onStatus('offline');
      emit({ type: 'error', message: `demo fixtures unavailable: ${error.message}` });
    });

  async function open(path) {
    const file = manifest.docs[path];
    if (!file) {
      emit({ type: 'error', path, message: `${path} is not part of the demo` });
      return;
    }
    if (!cache.has(path)) {
      cache.set(path, fetch(`${BASE}${file}`).then((response) => response.json()));
    }
    try {
      emit(await cache.get(path));
    } catch (error) {
      cache.delete(path);
      emit({ type: 'error', path, message: `could not load ${path}: ${error.message}` });
    }
  }

  /** The dialog's lookups, answered from the manifest.
   *
   *  `locate` is the one place the demo is visibly narrower than the server: a
   *  real one resolves any path the root contains, this one knows the corpus it
   *  was generated from. Trying the text as given and then relative to the root
   *  covers what someone pastes after reading a path out of the page.
   */
  function reply(message) {
    if (message.type === 'browse') {
      const key = `${message.path ?? ''}?${message.hidden ? 1 : 0}${message.all ? 1 : 0}`;
      const found = manifest.browse[key];
      return found ?? { type: 'error', message: `cannot read '${message.path}'` };
    }
    const text = (message.path ?? '').trim().replace(/^\.\//, '');
    const relative = text.startsWith(manifest.root)
      ? text.slice(manifest.root.length).replace(/^\//, '')
      : text;
    const found = manifest.locate[text] ?? manifest.locate[relative];
    return found ?? {
      type: 'error',
      message: `'${message.path}' is not part of the demo; it browses the sample corpus only`
    };
  }

  return {
    send(message) {
      // Every branch is async anyway, so the caller is never re-entered from
      // inside its own send() - the same ordering a socket gives.
      ready.then(() => {
        if (!manifest) return;
        if (message.type === 'open') open(message.path);
        else if (message.type === 'list') emit({ type: 'list', documents: manifest.documents });
        else if (message.type === 'browse' || message.type === 'locate') {
          emit({ ...reply(message), id: message.id });
        }
        // `source` is an editor's unsaved buffer; there is no editor here.
      });
      return true;
    },
    onMessage(callback) {
      onMessage = callback;
      started = true;
      for (const message of backlog.splice(0)) callback(message);
    },
    onStatus(callback) {
      onStatus = callback;
      callback(manifest ? 'demo' : 'connecting');
    }
  };
}
