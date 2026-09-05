import * as vscode from 'vscode';
import { renderHtml } from './html';

/** Reads the built `media/index.html` and points it at the webview's origin.
 *  The rewriting itself lives in `html.ts`, free of any VS Code import so it
 *  can be exercised outside a host. */
export async function webviewHtml(
  webview: vscode.Webview,
  extensionUri: vscode.Uri
): Promise<string> {
  const media = vscode.Uri.joinPath(extensionUri, 'media');
  const index = vscode.Uri.joinPath(media, 'index.html');
  const raw = new TextDecoder().decode(await vscode.workspace.fs.readFile(index));

  return renderHtml(
    raw,
    (path) => webview.asWebviewUri(vscode.Uri.joinPath(media, path)).toString(),
    webview.cspSource,
    randomNonce()
  );
}

function randomNonce(): string {
  const alphabet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
  let nonce = '';
  for (let i = 0; i < 32; i++) nonce += alphabet[Math.floor(Math.random() * alphabet.length)];
  return nonce;
}
