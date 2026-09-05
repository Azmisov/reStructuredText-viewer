import { ChildProcess, spawn } from 'node:child_process';
import * as path from 'node:path';
import * as readline from 'node:readline';

export type Message = { type: string; [key: string]: unknown };

/** A `rstview --stdio` child, framed as one JSON object per line.
 *
 *  The child claims fd 1 for protocol only, so anything arriving on stderr is
 *  diagnostics rather than a corrupted frame - it is surfaced, not parsed.
 */
export class RstviewProcess {
  private child: ChildProcess;
  private stderr = '';
  private disposed = false;

  constructor(
    python: string,
    runtime: string,
    root: string,
    private onMessage: (message: Message) => void,
    private onExit: (reason: string) => void
  ) {
    this.child = spawn(python, ['-m', 'rstview', '--stdio', '--root', root], {
      cwd: root,
      stdio: ['pipe', 'pipe', 'pipe'],
      env: {
        ...process.env,
        // The extension ships docutils and rstview, so the interpreter is a
        // bare runtime. Prepended, not appended: whatever happens to be in the
        // user's site-packages must not change how their preview renders.
        PYTHONPATH: [runtime, process.env.PYTHONPATH].filter(Boolean).join(path.delimiter),
        // No .pyc files written into the extension directory, which may not
        // even be writable.
        PYTHONDONTWRITEBYTECODE: '1'
      }
    });

    readline.createInterface({ input: this.child.stdout! }).on('line', (line) => {
      if (!line.trim()) return;
      try {
        this.onMessage(JSON.parse(line) as Message);
      } catch {
        // A malformed frame is a bug in the child, not a reason to tear the
        // preview down; keep the remaining stream alive.
        this.stderr += `unparseable frame: ${line}\n`;
      }
    });

    this.child.stderr!.on('data', (chunk: Buffer) => {
      // Bounded: a crash loop must not grow this without limit.
      this.stderr = (this.stderr + chunk.toString()).slice(-8192);
    });

    this.child.on('error', (error) => this.die(error.message));
    this.child.on('exit', (code, signal) =>
      this.die(`rstview exited (${signal ?? code})\n${this.stderr}`)
    );
  }

  private die(reason: string) {
    if (this.disposed) return;
    this.disposed = true;
    this.onExit(reason.trim());
  }

  send(message: Message) {
    if (this.disposed || !this.child.stdin?.writable) return false;
    return this.child.stdin.write(JSON.stringify(message) + '\n');
  }

  dispose() {
    this.disposed = true;
    this.child.kill();
  }
}
