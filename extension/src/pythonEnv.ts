import * as vscode from 'vscode';
import { execFile } from 'node:child_process';
import { promisify } from 'node:util';

const run = promisify(execFile);

/** The oldest interpreter the vendored code runs on. Matches
 *  `requires-python` in pyproject.toml. */
const MINIMUM = [3, 10] as const;

/** Interpreters to try, best first.
 *
 *  The extension ships its own docutils and its own `rstview`, so this is
 *  looking for a bare runtime, not a configured environment - any Python new
 *  enough will do. The Python extension's choice still comes first, because a
 *  user who has selected an interpreter for this workspace means it.
 */
async function candidates(scope?: vscode.Uri): Promise<string[]> {
  const configured = vscode.workspace
    .getConfiguration('rstview', scope)
    .get<string>('pythonPath');
  // VS Code expands ${workspaceFolder} in launch.json and tasks.json but not in
  // ordinary settings values, and pointing at a venv inside the workspace is
  // the common case - so expand it here rather than making people paste an
  // absolute path.
  const found = configured ? [expand(configured, scope)] : [];

  const python = vscode.extensions.getExtension('ms-python.python');
  if (python) {
    try {
      const api = await python.activate();
      const path = api?.environments?.getActiveEnvironmentPath?.(scope)?.path;
      if (path) found.push(path);
    } catch {
      // The Python extension is a convenience here, never a requirement.
    }
  }

  found.push('python3', 'python');
  return found;
}

export class NoInterpreter extends Error {
  constructor(readonly tried: string[]) {
    super('No usable Python interpreter found.');
  }

  /** What the user should actually do about it.
   *
   *  Naming what was tried is the difference between "it didn't work" and "it
   *  looked here". Nothing needs installing beyond Python itself - the parser
   *  ships with the extension - so this stays deliberately short.
   */
  get advice(): string {
    return [
      `rstview needs a Python ${MINIMUM.join('.')} or newer interpreter, and could not find one.`,
      '',
      'Tried, in order:',
      ...this.tried.map((python) => `  • ${python}`),
      '',
      'Nothing else needs installing - docutils ships with the extension.',
      '',
      'Fix it in one of these ways:',
      '  1. Install Python from https://python.org/downloads (or your package manager).',
      '  2. Pick an existing one with: Python: Select Interpreter',
      '  3. Set rstview.pythonPath to its absolute path.',
      '',
      'If you have more than one folder open, note that a folder\'s own',
      '.vscode/settings.json applies here - set rstview.pythonPath under that',
      'folder, or in the .code-workspace file.'
    ].join('\n');
  }
}

/** First candidate that is a new enough Python.
 *
 *  Probing beats trusting a name: `python` on PATH is still Python 2 in some
 *  places, and a stale venv path in settings points at nothing at all.
 */
export async function resolveInterpreter(scope?: vscode.Uri): Promise<string> {
  const tried = await candidates(scope);
  // A tuple literal, not JSON: Python cannot compare version_info to a list.
  const probe =
    `import sys; sys.exit(0 if sys.version_info >= (${MINIMUM.join(', ')}) else 1)`;

  for (const python of tried) {
    try {
      await run(python, ['-c', probe], { timeout: 10_000 });
      return python;
    } catch {
      continue;
    }
  }
  throw new NoInterpreter(tried);
}

function expand(value: string, scope?: vscode.Uri): string {
  const folder =
    (scope && vscode.workspace.getWorkspaceFolder(scope)?.uri.fsPath) ??
    vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
  return folder ? value.replace(/\$\{workspaceFolder\}/g, folder) : value;
}
