import * as path from 'node:path';
import * as vscode from 'vscode';

export type HostTheme = {
  name: string;
  kind: 'light' | 'dark';
  theme: Record<string, unknown>;
};

/** Strip comments from JSONC.
 *
 *  String-aware, and that is the whole point: theme files are full of `"//"`
 *  inside colour values and scope selectors, and a naive comment regex
 *  corrupts the document into something that will not parse.
 */
function stripComments(text: string): string {
  let out = '';
  let inString = false;
  let escaped = false;

  for (let i = 0; i < text.length; i++) {
    const character = text[i];
    const next = text[i + 1];

    if (inString) {
      out += character;
      if (escaped) escaped = false;
      else if (character === '\\') escaped = true;
      else if (character === '"') inString = false;
      continue;
    }
    if (character === '"') {
      inString = true;
      out += character;
      continue;
    }
    if (character === '/' && next === '/') {
      while (i < text.length && text[i] !== '\n') i++;
      out += '\n';
      continue;
    }
    if (character === '/' && next === '*') {
      i += 2;
      while (i < text.length && !(text[i] === '*' && text[i + 1] === '/')) i++;
      i++;
      continue;
    }
    out += character;
  }
  // Trailing commas are legal in JSONC and common in hand-edited themes.
  return out.replace(/,(\s*[}\]])/g, '$1');
}

/** Read a theme file, resolving the `include` chain.
 *
 *  VS Code's own themes are layered this way - Dark+ is a handful of overrides
 *  on top of Dark (Visual Studio) - so a theme read without following
 *  `include` is mostly empty.
 */
async function readTheme(file: vscode.Uri, depth = 0): Promise<Record<string, any>> {
  if (depth > 10) throw new Error('include chain too deep');

  const raw = new TextDecoder().decode(await vscode.workspace.fs.readFile(file));
  const theme = JSON.parse(stripComments(raw.replace(/^﻿/, '')));
  if (!theme.include) return theme;

  const parent = vscode.Uri.file(path.resolve(path.dirname(file.fsPath), theme.include));
  const base = await readTheme(parent, depth + 1);
  return {
    ...base,
    ...theme,
    colors: { ...(base.colors ?? {}), ...(theme.colors ?? {}) },
    // Order matters: the including theme's rules must win, and TextMate
    // resolution takes the last match.
    tokenColors: [...(base.tokenColors ?? []), ...(theme.tokenColors ?? [])]
  };
}

/** The theme the user is actually looking at, as raw TextMate JSON.
 *
 *  There is no API for this, so it is found the way VS Code finds it: match
 *  the `workbench.colorTheme` setting against every extension's contributed
 *  themes, including built-ins.
 */
export async function activeTheme(): Promise<HostTheme | null> {
  const wanted = vscode.workspace.getConfiguration('workbench').get<string>('colorTheme');
  if (!wanted) return null;

  for (const extension of vscode.extensions.all) {
    const contributed = extension.packageJSON?.contributes?.themes;
    if (!Array.isArray(contributed)) continue;

    for (const entry of contributed) {
      if (entry?.label !== wanted && entry?.id !== wanted) continue;
      try {
        const file = vscode.Uri.joinPath(extension.extensionUri, entry.path);
        const theme = await readTheme(file);
        // `uiTheme` is the contribution's own declaration of which side it is
        // on, and unlike `type` it is always present.
        const kind = entry.uiTheme === 'vs' || entry.uiTheme === 'hc-light' ? 'light' : 'dark';
        // Shiki keys loaded themes by name; a stable, sanitised one keeps a
        // theme whose label has spaces or punctuation addressable.
        const name = `host-${String(wanted).toLowerCase().replace(/[^a-z0-9]+/g, '-')}`;
        return { name, kind, theme: { ...theme, name, type: theme.type ?? kind } };
      } catch {
        // A theme we cannot read is not an error worth surfacing - the
        // built-in Shiki themes remain, and highlighting still works.
        return null;
      }
    }
  }
  return null;
}
