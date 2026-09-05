/** Viewer preferences, persisted per browser.
 *
 *  Every accessor is guarded: private windows and blocked site data throw on
 *  localStorage access rather than returning null, and a page that renders
 *  nothing is worse than one that forgets a preference.
 */
const KEY = 'rstview-settings';

import { HOST_THEME } from './hostTheme.svelte.js';

const VSCODE = import.meta.env.VITE_TARGET === 'vscode';

// In VS Code, 'vscode' replaces 'system': the host already tracks the user's
// theme and stamps it on <body>, so following the OS would be a second,
// conflicting answer to the same question.
export const MODES = VSCODE ? ['vscode', 'light', 'dark'] : ['system', 'light', 'dark'];
export const DENSITIES = ['tight', 'normal', 'roomy'];
// Where the content column sits in the viewport, not how text is aligned
// inside it. Text direction is handled automatically per block by dir="auto"
// in the renderer, so it needs no setting.
export const ALIGNMENTS = ['left', 'center', 'right'];

const ALIGN_MARGIN = {
  left: '0 auto 0 0',
  center: '0 auto',
  right: '0 0 0 auto'
};

const DEFAULTS = {
  mode: VSCODE ? 'vscode' : 'system',
  // In VS Code the default is the editor's *actual* theme, sent over as
  // TextMate JSON - so the preview matches the editor beside it whatever the
  // user is running. A named theme can still be picked instead.
  syntaxLight: VSCODE ? HOST_THEME : 'github-light',
  syntaxDark: VSCODE ? HOST_THEME : 'github-dark',
  fontSize: 16,
  density: 'normal',
  maxWidth: 46,
  align: 'center',
  lineNumbers: false,
  wrapCode: false
};

// The top of the range means "no limit" rather than a very wide column, so one
// control covers both a measured line length and full-bleed.
export const WIDTH_MIN = 30;
export const WIDTH_MAX = 100;
export const WIDTH_FULL = WIDTH_MAX;

export function widthLabel(value) {
  return value >= WIDTH_FULL ? 'full' : `${value}rem`;
}

// Spacing scale, applied as a multiplier to the block rhythm.
const DENSITY_SCALE = { tight: 0.55, normal: 1, roomy: 1.5 };

function load() {
  try {
    const raw = JSON.parse(localStorage.getItem(KEY) ?? '{}');
    // Merge rather than replace, so a new setting gets its default and a
    // corrupted value can't remove one.
    const merged = { ...DEFAULTS, ...(raw && typeof raw === 'object' ? raw : {}) };
    // A value saved before this build, or by the standalone app sharing an
    // origin: 'system' has no meaning in a webview, and leaving it would make
    // the preview ignore the editor's theme.
    if (VSCODE && !MODES.includes(merged.mode)) merged.mode = DEFAULTS.mode;
    return merged;
  } catch {
    return { ...DEFAULTS };
  }
}

/** Which way VS Code's current theme leans.
 *
 *  The host maintains `vscode-light` / `vscode-dark` / `vscode-high-contrast`
 *  on <body> and rewrites them the moment the user switches theme, so watching
 *  the class is a live feed - no message from the extension needed.
 */
function hostTheme() {
  const classes = document.body.classList;
  if (classes.contains('vscode-light') || classes.contains('vscode-high-contrast-light')) {
    return 'light';
  }
  return classes.contains('vscode-dark') || classes.contains('vscode-high-contrast')
    ? 'dark'
    : null;
}

export function createSettings() {
  let values = $state(load());
  let host = $state(VSCODE ? hostTheme() : null);

  if (VSCODE) {
    new MutationObserver(() => (host = hostTheme())).observe(document.body, {
      attributes: true,
      attributeFilter: ['class']
    });
  }

  $effect(() => {
    const root = document.documentElement;

    // Only explicit choices stamp data-theme; 'system' leaves it off so
    // prefers-color-scheme applies, which is what the CSS is written against.
    // 'vscode' resolves to whichever way the host theme leans; 'system' leaves
    // data-theme off so prefers-color-scheme applies, which is what the CSS is
    // written against.
    const resolved = values.mode === 'vscode' ? host : values.mode;
    if (!resolved || resolved === 'system') root.removeAttribute('data-theme');
    else root.setAttribute('data-theme', resolved);

    root.style.setProperty('--base-font-size', `${values.fontSize}px`);
    root.style.setProperty(
      '--content-width',
      values.maxWidth >= WIDTH_FULL ? '100%' : `${values.maxWidth}rem`
    );
    root.style.setProperty('--gap-scale', String(DENSITY_SCALE[values.density] ?? 1));
    root.style.setProperty(
      '--content-margin',
      ALIGN_MARGIN[values.align] ?? ALIGN_MARGIN.center
    );

    try {
      localStorage.setItem(KEY, JSON.stringify(values));
    } catch {
      // Persisting is a convenience, not a requirement.
    }
  });

  return {
    get values() { return values; },
    set(key, value) { values = { ...values, [key]: value }; },
    reset() { values = { ...DEFAULTS }; }
  };
}
