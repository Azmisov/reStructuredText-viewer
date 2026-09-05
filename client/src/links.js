/** Cross-document link resolution.
 *
 *  Plain reST has no cross-reference role outside Sphinx, so a link to another
 *  document is an ordinary hyperlink whose target happens to be a local file:
 *  `link <other.rst>`_ or `link <api/index.rst#usage>`_.
 */
const DOC_SUFFIXES = ['.rst', '.txt', '.rest'];

const EXTERNAL = /^[a-z][a-z0-9+.-]*:/i;

/** True if `refuri` points at another document in the library. */
export function isDocumentLink(refuri) {
  if (!refuri || EXTERNAL.test(refuri) || refuri.startsWith('//')) return false;
  const [target] = refuri.split('#');
  return DOC_SUFFIXES.some((suffix) => target.toLowerCase().endsWith(suffix));
}

/** Resolve `refuri` against the directory of `from`, returning {path, hash}.
 *
 *  Paths are library-relative and always '/'-separated; the server rejects
 *  anything that escapes the root, but normalising here keeps the client's
 *  history entries canonical.
 */
export function resolveDocumentLink(refuri, from) {
  const [target, hash = ''] = refuri.split('#');
  const base = (from ?? '').split('/').slice(0, -1);
  const segments = target.startsWith('/') ? [] : base;

  const parts = [];
  for (const segment of [...segments, ...target.split('/')]) {
    if (!segment || segment === '.') continue;
    if (segment === '..') parts.pop();
    else parts.push(segment);
  }
  return { path: parts.join('/'), hash };
}

/** Resolve an `.. image::` URI to something the page can load.
 *
 *  Left alone if it already names a scheme (`https:`, `data:`) or is
 *  site-absolute. Otherwise it is relative to the *document*, not to the page
 *  URL - two different things as soon as one document links to another in a
 *  subdirectory - so it is rebased and pointed at the media route.
 *
 *  `base` is where that route lives: `/media/` for the standalone server, and
 *  the webview URI of the root when running inside an editor, which cannot
 *  fetch from a server it does not have.
 */
export function resolveAsset(uri, from, base = '/media/') {
  if (!uri || EXTERNAL.test(uri) || uri.startsWith('//') || uri.startsWith('/')) return uri;
  const { path } = resolveDocumentLink(uri, from);
  if (!path) return uri;
  return base + path.split('/').map(encodeURIComponent).join('/');
}
