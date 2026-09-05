import * as path from 'node:path';
import * as vscode from 'vscode';
import { RstviewProcess, Message } from './server';
import { resolveInterpreter, NoInterpreter } from './pythonEnv';
import { webviewHtml } from './webview';
import { activeTheme } from './theme';

/** The root the child is confined to.
 *
 *  The workspace folder is the natural boundary in an editor; outside a
 *  workspace there is only the document's own directory to fall back on.
 */
function rootFor(document: vscode.Uri): string {
  return vscode.workspace.getWorkspaceFolder(document)?.uri.fsPath
    ?? path.dirname(document.fsPath);
}

function viewOptions(extensionUri: vscode.Uri, root: string) {
  return {
    enableScripts: true,
    // The document's own root as well as the bundle: an `.. image::` points at
    // a file next to the document, and a webview may only load from roots
    // named here.
    localResourceRoots: [vscode.Uri.joinPath(extensionUri, 'media'), vscode.Uri.file(root)],
    // Milestone 9 measures a cold Shiki highlight and drops this if it is fast
    // enough; until then, keeping the context is one line.
    retainContextWhenHidden: true
  };
}

/** One preview panel and the child process feeding it. */
/** Typing is a stream; rendering every keystroke would queue work faster than
 *  docutils retires it. Short enough to feel immediate, long enough to coalesce
 *  a burst. */
const DEBOUNCE_MS = 150;

class Preview {
  private process?: RstviewProcess;
  private watching: vscode.Disposable[] = [];
  private timer?: NodeJS.Timeout;

  private constructor(
    readonly panel: vscode.WebviewPanel,
    private readonly extensionUri: vscode.Uri,
    private readonly document: vscode.Uri,
    private readonly root: string
  ) {}

  static async create(
    extensionUri: vscode.Uri,
    document: vscode.Uri,
    column: vscode.ViewColumn
  ): Promise<Preview> {
    const panel = vscode.window.createWebviewPanel(
      'rstview.preview',
      `Preview ${path.basename(document.fsPath)}`,
      { viewColumn: column, preserveFocus: true },
      viewOptions(extensionUri, rootFor(document))
    );
    return Preview.adopt(panel, extensionUri, document);
  }

  /** Wrap a panel - freshly made, or handed back by VS Code after a window
   *  reload. A restored panel keeps its HTML but has lost its child process,
   *  so it needs the same start-up as a new one. */
  static async adopt(
    panel: vscode.WebviewPanel,
    extensionUri: vscode.Uri,
    document: vscode.Uri
  ): Promise<Preview> {
    panel.webview.options = viewOptions(extensionUri, rootFor(document));
    panel.title = `Preview ${path.basename(document.fsPath)}`;

    const preview = new Preview(panel, extensionUri, document, rootFor(document));
    panel.webview.html = await webviewHtml(panel.webview, extensionUri);
    await preview.start();
    return preview;
  }

  private async start() {
    let python: string;
    try {
      python = await resolveInterpreter(this.document);
    } catch (error) {
      if (error instanceof NoInterpreter) {
        this.fail(error.advice);
        void offerToFixInterpreter(error);
      } else {
        this.fail((error as Error).message);
      }
      return;
    }

    this.process = new RstviewProcess(
      python,
      vscode.Uri.joinPath(this.extensionUri, 'python').fsPath,
      this.root,
      (message) => this.fromChild(message),
      (reason) => this.fail(reason)
    );

    // Everything the webview sends is protocol; the child decides what is
    // valid, and containment is enforced there rather than here.
    this.panel.webview.onDidReceiveMessage((message: Message) =>
      this.process?.send(message)
    );

    // `source` renders the buffer, so the preview follows the editor rather
    // than the file on disk - no watcher, and no wait for a save.
    this.watching.push(
      vscode.workspace.onDidChangeTextDocument((event) => {
        if (event.document.uri.toString() !== this.document.toString()) return;
        clearTimeout(this.timer);
        this.timer = setTimeout(() => this.push(event.document), DEBOUNCE_MS);
      }),
      // A save can rewrite the buffer (formatters, trailing-newline fixers),
      // and it is the moment a user most expects the preview to be right.
      vscode.workspace.onDidSaveTextDocument((saved) => {
        if (saved.uri.toString() !== this.document.toString()) return;
        clearTimeout(this.timer);
        this.push(saved);
      }),
      // Switching theme, and switching the setting that names it - the latter
      // fires for a theme installed or edited without the active one changing.
      vscode.window.onDidChangeActiveColorTheme(() => void this.sendTheme()),
      vscode.workspace.onDidChangeConfiguration((event) => {
        if (event.affectsConfiguration('workbench.colorTheme')) void this.sendTheme();
      })
    );
  }

  /** Hand the webview the user's real theme as TextMate JSON.
   *
   *  This goes straight to the webview rather than through the child: it is a
   *  host concern, and the Python side has no opinion about colour.
   */
  private async sendTheme() {
    const theme = await activeTheme();
    if (theme) void this.panel.webview.postMessage({ type: 'host-theme', ...theme });
  }

  /** Send the buffer as it stands. Also called once at startup, so a preview
   *  opened on a dirty editor shows the unsaved text immediately. */
  private push(document: vscode.TextDocument) {
    this.process?.send({
      type: 'source',
      path: path.relative(this.root, this.document.fsPath),
      text: document.getText()
    });
  }

  /** `ready` names the entry document, which the child only knows if it was
   *  given one on the command line. It was not, so open ours as soon as the
   *  child announces itself. */
  private fromChild(message: Message) {
    if (message.type === 'ready') {
      this.process?.send({
        type: 'open',
        path: path.relative(this.root, this.document.fsPath)
      });
      // The editor may already hold unsaved changes; disk is not the truth.
      const open = vscode.workspace.textDocuments.find(
        (candidate) => candidate.uri.toString() === this.document.toString()
      );
      if (open?.isDirty) this.push(open);
      void this.sendTheme();
      // Where document-relative images resolve from. There is no server here,
      // so the client is handed the webview URI of the root instead of a path.
      const base = this.panel.webview.asWebviewUri(vscode.Uri.file(this.root)).toString();
      void this.panel.webview.postMessage({
        type: 'media-base',
        base: base.endsWith('/') ? base : `${base}/`
      });
    }
    this.panel.webview.postMessage(message);
  }

  private fail(message: string) {
    // Surfaced in the preview itself: the panel is where the user is looking,
    // and an `error` frame is already part of the vocabulary the client renders.
    this.panel.webview.postMessage({ type: 'error', message });
  }

  dispose() {
    clearTimeout(this.timer);
    for (const disposable of this.watching) disposable.dispose();
    this.watching = [];
    this.process?.dispose();
  }
}

/** Keeps one panel per document, so re-invoking the command focuses rather
 *  than stacking duplicates. */
export class PreviewManager {
  private previews = new Map<string, Preview>();

  constructor(private readonly extensionUri: vscode.Uri) {}

  async show(document: vscode.Uri, column: vscode.ViewColumn) {
    const key = document.toString();
    const existing = this.previews.get(key);
    if (existing) {
      existing.panel.reveal(column, true);
      return;
    }

    this.track(key, await Preview.create(this.extensionUri, document, column));
  }

  /** Bring a panel restored after a window reload back to life. */
  async restore(panel: vscode.WebviewPanel, document: vscode.Uri) {
    const key = document.toString();
    // A panel for this document may have been revived already; two views of
    // one document would fight over the same map entry.
    if (this.previews.has(key)) {
      panel.dispose();
      return;
    }
    this.track(key, await Preview.adopt(panel, this.extensionUri, document));
  }

  private track(key: string, preview: Preview) {
    this.previews.set(key, preview);
    preview.panel.onDidDispose(() => {
      this.previews.delete(key);
      preview.dispose();
    });
  }

  dispose() {
    for (const preview of this.previews.values()) preview.dispose();
    this.previews.clear();
  }
}

/** A notification with the two actions that actually resolve this, because the
 *  message in the panel can explain but cannot open anything. */
async function offerToFixInterpreter(error: NoInterpreter) {
  const select = 'Select Interpreter';
  const settings = 'Open Settings';
  const choice = await vscode.window.showErrorMessage(
    'rstview: no usable Python interpreter found.',
    { modal: false, detail: error.advice },
    select,
    settings
  );
  if (choice === select) {
    await vscode.commands.executeCommand('python.setInterpreter');
  } else if (choice === settings) {
    await vscode.commands.executeCommand(
      'workbench.action.openSettings',
      'rstview.pythonPath'
    );
  }
}
