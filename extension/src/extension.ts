import * as path from 'node:path';
import * as vscode from 'vscode';
import { PreviewManager } from './preview';

export function activate(context: vscode.ExtensionContext) {
  const previews = new PreviewManager(context.extensionUri);
  context.subscriptions.push(previews);

  const open = (beside: boolean) => async () => {
    const editor = vscode.window.activeTextEditor;
    if (!editor) {
      vscode.window.showWarningMessage('rstview: no active document to preview.');
      return;
    }
    if (editor.document.uri.scheme !== 'file') {
      // The child reads from disk; an untitled or virtual document has no path
      // for it to resolve. Milestone 5 covers unsaved buffers via `source`.
      vscode.window.showWarningMessage('rstview: save the document first.');
      return;
    }
    const column = beside
      ? (editor.viewColumn ?? vscode.ViewColumn.One) + 1
      : (editor.viewColumn ?? vscode.ViewColumn.One);
    await previews.show(editor.document.uri, column);
  };

  context.subscriptions.push(
    vscode.commands.registerCommand('rstview.showPreview', open(true)),
    vscode.commands.registerCommand('rstview.showPreviewToCurrentColumn', open(false)),
    // Without this, a window reload hands the panel back with its HTML intact
    // but no child process behind it - a blank pane that never fills in.
    vscode.window.registerWebviewPanelSerializer('rstview.preview', {
      async deserializeWebviewPanel(panel, state: { root?: string; path?: string }) {
        // The webview recorded these; nothing else survives a reload.
        if (!state?.root || !state?.path) {
          panel.dispose();
          return;
        }
        await previews.restore(panel, vscode.Uri.file(path.join(state.root, state.path)));
      }
    })
  );
}

export function deactivate() {}
