/** Client-side syntax highlighting.
 *
 *  Grammars and themes are listed explicitly rather than built from template
 *  strings: Vite cannot statically analyse `@shikijs/langs/${lang}` against
 *  that package's exports map, and silently emits a bundle containing no
 *  grammars at all. Each entry is its own lazy chunk.
 */
import { createHighlighterCore } from 'shiki/core';
import { createJavaScriptRegexEngine } from 'shiki/engine/javascript';
import { THEME_LOADERS } from './themes.js';

const LANGS = {
  python: () => import('@shikijs/langs/python'),
  javascript: () => import('@shikijs/langs/javascript'),
  typescript: () => import('@shikijs/langs/typescript'),
  bash: () => import('@shikijs/langs/bash'),
  json: () => import('@shikijs/langs/json'),
  yaml: () => import('@shikijs/langs/yaml'),
  rst: () => import('@shikijs/langs/rst'),
  c: () => import('@shikijs/langs/c'),
  cpp: () => import('@shikijs/langs/cpp'),
  html: () => import('@shikijs/langs/html'),
  css: () => import('@shikijs/langs/css')
};

const ALIASES = {
  py: 'python', js: 'javascript', ts: 'typescript',
  sh: 'bash', shell: 'bash', console: 'bash', 'c++': 'cpp'
};

// Every cache here holds a *promise*, not a resolved value. Caching the value
// leaves a window where concurrent callers all see "not ready yet" and each
// starts its own work: two literal blocks rendering at once produced two
// highlighter instances, while the shared "already loaded" bookkeeping made the
// second one skip loading a theme it did not have - so it failed with
// "Theme `github-light` not found".
let enginePromise = null;
const langPromises = new Map();
const themePromises = new Map();

function highlighter() {
  if (!enginePromise) {
    enginePromise = createHighlighterCore({
      themes: [],
      langs: [],
      engine: createJavaScriptRegexEngine()
    });
  }
  return enginePromise;
}

function ensureLang(shiki, name) {
  if (!LANGS[name]) return Promise.resolve(false);
  if (!langPromises.has(name)) {
    langPromises.set(
      name,
      LANGS[name]()
        .then((module) => shiki.loadLanguage(module))
        .then(() => true)
        // Drop the failure so a transient chunk error can be retried.
        .catch(() => {
          langPromises.delete(name);
          return false;
        })
    );
  }
  return langPromises.get(name);
}

function ensureTheme(shiki, name) {
  // Already registered - a runtime theme, or one loaded earlier.
  if (themePromises.has(name)) return themePromises.get(name);
  if (!THEME_LOADERS[name]) return Promise.resolve(false);
  if (!themePromises.has(name)) {
    themePromises.set(
      name,
      THEME_LOADERS[name]()
        .then((module) => shiki.loadTheme(module))
        .then(() => true)
        .catch(() => {
          themePromises.delete(name);
          return false;
        })
    );
  }
  return themePromises.get(name);
}

/** Register a theme supplied at runtime rather than loaded from a chunk - the
 *  editor's own theme, handed over as TextMate JSON.
 *
 *  Keyed by name in the same map as the bundled themes, so `resolveTheme` need
 *  not know where a theme came from. Re-registering under the same name (the
 *  user edited their theme, or switched and switched back) replaces it. */
export async function registerTheme(theme) {
  const shiki = await highlighter();
  const promise = Promise.resolve(shiki.loadTheme(theme)).then(() => true);
  themePromises.set(theme.name, promise);
  try {
    await promise;
  } catch (error) {
    themePromises.delete(theme.name);
    throw error;
  }
  return theme.name;
}

/** Load `name`, falling back only if it genuinely isn't available. */
async function resolveTheme(shiki, name, fallback) {
  if (await ensureTheme(shiki, name)) return name;
  await ensureTheme(shiki, fallback);
  return fallback;
}

/** Returns highlighted HTML with both palettes as CSS variables, so switching
 *  light/dark is a variable swap rather than a re-highlight. Changing the
 *  *themes themselves* does require re-running this. */
export async function highlight(code, language, themes) {
  const shiki = await highlighter();
  const lang = ALIASES[language] ?? language;

  const [ready, light, dark] = await Promise.all([
    lang ? ensureLang(shiki, lang) : Promise.resolve(false),
    resolveTheme(shiki, themes.light, 'github-light'),
    resolveTheme(shiki, themes.dark, 'github-dark')
  ]);

  return shiki.codeToHtml(code, {
    lang: ready ? lang : 'text',
    themes: { light, dark },
    defaultColor: false
  });
}
