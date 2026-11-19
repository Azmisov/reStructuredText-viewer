/** Build `extension/python/`: docutils, MyST for Markdown, and our own package,
 *  importable by any Python 3.11+ with nothing installed.
 *
 *  MyST's dependencies include PyYAML and MarkupSafe, whose wheels carry C
 *  speedups built for the interpreter that ran this. Both fall back to pure
 *  Python when the extension module will not load, so the bundle still works
 *  under any other interpreter - just without the speedups.
 *
 *  Run at package time rather than checked in. Vendored trees that live in git
 *  rot quietly and land in every diff; this one is reproducible from
 *  pyproject.toml, so it is build output like `out/` and `media/`.
 */
import { execFileSync } from 'node:child_process';
import * as fs from 'node:fs';
import * as path from 'node:path';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const extension = path.resolve(here, '..');
const repo = path.resolve(extension, '..');
const target = path.join(extension, 'python');

/** The parsing requirements, taken from pyproject so the bundle cannot drift
 *  from what the package itself declares. The server's dependencies
 *  (Starlette, uvicorn, watchdog) stay out: the extension runs `--stdio`. */
function requirements() {
  const pyproject = fs.readFileSync(path.join(repo, 'pyproject.toml'), 'utf8');
  return ['docutils', 'myst-docutils'].map((name) => {
    const match = pyproject.match(new RegExp(`"(${name}[^"]*)"`));
    if (!match) throw new Error(`no ${name} requirement found in pyproject.toml`);
    return match[1];
  });
}

function install(specs) {
  // uv if it is here, pip otherwise: contributors have one or the other.
  const attempts = [
    ['uv', ['pip', 'install', '--target', target, '--no-cache', ...specs]],
    ['python3', ['-m', 'pip', 'install', '--target', target, '--no-cache-dir', ...specs]]
  ];
  for (const [command, args] of attempts) {
    try {
      execFileSync(command, args, { stdio: 'inherit' });
      return;
    } catch {
      continue;
    }
  }
  throw new Error(`could not install ${specs.join(' ')}; needs uv or pip on PATH`);
}

fs.rmSync(target, { recursive: true, force: true });
fs.mkdirSync(target, { recursive: true });

install(requirements());

// Our own package, source only. `src/rstview/client/` is the built web bundle,
// which the extension does not serve - it has its own copy in `media/`.
const source = path.join(repo, 'src', 'rstview');
const destination = path.join(target, 'rstview');
fs.mkdirSync(destination, { recursive: true });
for (const entry of fs.readdirSync(source)) {
  if (entry.endsWith('.py')) {
    fs.copyFileSync(path.join(source, entry), path.join(destination, entry));
  }
}

// Console scripts pip generates are shebanged to the interpreter that ran the
// install, which is not the one the extension will spawn. Dead weight that
// only misleads.
fs.rmSync(path.join(target, 'bin'), { recursive: true, force: true });
fs.rmSync(path.join(target, 'Scripts'), { recursive: true, force: true });

// Bytecode is interpreter-version specific; shipping it is dead weight at best
// and confusing at worst.
for (const cache of walk(target)) fs.rmSync(cache, { recursive: true, force: true });

function* walk(directory) {
  for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
    if (!entry.isDirectory()) continue;
    const full = path.join(directory, entry.name);
    if (entry.name === '__pycache__') yield full;
    else yield* walk(full);
  }
}

const size = execFileSync('du', ['-sh', target]).toString().split('\t')[0];
console.log(`vendored ${requirements().join(' ')} + rstview into extension/python (${size})`);
