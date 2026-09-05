"""Command line entry point."""
import argparse
import os
import pathlib
import shutil
import socket
import subprocess
import sys
import threading
import webbrowser

from . import stdio

# uvicorn and .app (Starlette, watchdog) are imported where the server is
# actually started, not here. `--stdio` needs none of them - only docutils -
# and that is what lets an editor host run against a bare interpreter.

# In an editable install the Svelte sources sit beside the package root.
CLIENT_SRC = pathlib.Path(__file__).resolve().parents[2] / "client"

# A fixed default means the URL is stable across restarts, so a pinned browser
# tab keeps working and bookmarks survive. 5686 is in the IANA dynamic range
# and not claimed by anything common (5000 AirPlay, 5173 Vite, 5432 Postgres,
# 8000/8080 everything else). Pass --port 0 for a random free port.
DEFAULT_PORT = 5686

# Interfaces that only the local machine can reach. Binding anywhere else
# publishes the server, and the default document root tightens accordingly.
LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "::1", "localhost6"})


def default_root(filename, listen):
    """Where cross-document links and the file dialog may reach.

    On a loopback interface the server is no more exposed than the shell that
    started it, so the default is the whole filesystem. Bound anywhere else it
    is reachable by others, and the default narrows to the document's own
    directory - `--root` overrides either way.
    """
    if listen not in LOCAL_HOSTS:
        return os.path.dirname(os.path.realpath(filename)) if filename else os.getcwd()
    return os.path.abspath(os.sep)


def _free_port(host):
    with socket.socket() as sock:
        sock.bind((host, 0))
        return sock.getsockname()[1]


def _start_vite(api_port, dev_port):
    """Run the Vite dev server, proxying /ws and /api back to us.

    Gives HMR on the Svelte sources: editing a component updates the page
    without losing the loaded document or your scroll position.
    """
    if not (CLIENT_SRC / "package.json").exists():
        sys.exit(f"rstview: --dev needs the client sources at {CLIENT_SRC}")

    # Invoke the local binary rather than `pnpm run dev`: package managers
    # disagree about whether trailing args need a `--` separator, and getting
    # it wrong silently hands the flags to the wrong process.
    local = CLIENT_SRC / "node_modules" / ".bin" / "vite"
    if local.exists():
        command = [str(local)]
    else:
        runner = shutil.which("pnpm") or shutil.which("npm")
        if runner is None:
            sys.exit("rstview: --dev needs the client dependencies installed "
                     "(pnpm --dir client install)")
        command = [runner, "exec", "vite"]

    env = {**os.environ, "RSTVIEW_API_PORT": str(api_port)}
    return subprocess.Popen(
        [*command, "--port", str(dev_port), "--strictPort"],
        cwd=CLIENT_SRC,
        env=env,
    )


def main(argv=None):
    parser = argparse.ArgumentParser(prog="rstview", description=__doc__)
    parser.add_argument("filename", nargs="?", default=None,
                        help="reStructuredText file to preview; omit to start "
                             "with no document open and pick one in the browser")
    parser.add_argument("-l", "--listen", default=None,
                        help="interface to listen on [default: localhost]")
    parser.add_argument("-p", "--port", type=int, default=None,
                        help=f"port to listen on; 0 picks a random free port "
                             f"[default: {DEFAULT_PORT}]")
    parser.add_argument("--dev-port", type=int, default=None,
                        help="port for the Vite dev server with --dev "
                             "[default: --port + 1]")
    parser.add_argument("-r", "--root", default=None,
                        help="directory cross-document links and the file "
                             "dialog may reach [default: the whole filesystem "
                             "on a loopback interface; the document's own "
                             "directory when bound elsewhere]")
    parser.add_argument("-B", "--no-browser", action="store_true",
                        help="don't open a web browser")
    parser.add_argument("-c", "--components", default="rstview.config.json",
                        help="component config file "
                             "[default: rstview.config.json if present]")
    parser.add_argument("--dev", action="store_true",
                        help="run the Vite dev server for the client, with hot "
                             "reload on Svelte changes")
    parser.add_argument("--stdio", action="store_true",
                        help="speak the JSON protocol over stdin/stdout instead "
                             "of running a server, for an editor host")
    opts = parser.parse_args(argv)

    if opts.stdio:
        conflicts = [name for name, given in (
            ("--dev", opts.dev),
            ("--port", opts.port is not None),
            ("--listen", opts.listen is not None),
        ) if given]
        if conflicts:
            parser.error(f"--stdio runs no server, so it cannot be combined with "
                         f"{', '.join(conflicts)}")
        try:
            stdio.serve(
                opts.filename,
                config=opts.components,
                root=opts.root or default_root(opts.filename, "localhost"),
            )
        except ValueError as exc:
            sys.exit(f"rstview: {exc}")
        return

    host = opts.listen or "localhost"
    port = DEFAULT_PORT if opts.port is None else opts.port
    port = _free_port(host) if port == 0 else port

    vite = None
    if opts.dev:
        if opts.dev_port is not None:
            dev_port = opts.dev_port
        elif port == 0:
            dev_port = _free_port(host)
        else:
            dev_port = port + 1
        vite = _start_vite(port, dev_port)
        url = f"http://{host}:{dev_port}/"
        origins = {f"http://{host}:{dev_port}", f"http://127.0.0.1:{dev_port}"}
    else:
        url = f"http://{host}:{port}/"
        origins = {f"http://{host}:{port}", f"http://127.0.0.1:{port}"}

    root = opts.root or default_root(opts.filename, host)
    published = host not in LOCAL_HOSTS

    try:
        from .app import create_app
    except ImportError as exc:
        # Reachable when only the stdio dependencies are installed: the editor
        # path needs docutils alone, so a partial install is a real state.
        sys.exit(
            f"rstview: the server needs an optional dependency that is missing ({exc.name}).\n"
            "Install the full package with: pip install reStructuredText-viewer\n"
            "(`--stdio`, which editors use, needs only docutils.)"
        )

    try:
        app = create_app(
            opts.filename,
            allowed_origins=origins,
            config=opts.components,
            root=root,
        )
    except ValueError as exc:
        sys.exit(f"rstview: {exc}")

    what = opts.filename or "no document open"
    print(f"rstview: serving {what} at {url}", file=sys.stderr)
    print(f"rstview: document root {os.path.realpath(root)}", file=sys.stderr)
    if published and opts.root is None:
        print("rstview: bound to a non-loopback interface; root limited to the "
              "document's directory (pass --root to widen)", file=sys.stderr)
    if opts.dev:
        print(f"rstview: api on :{port}, vite with HMR on {url}", file=sys.stderr)
    if not opts.no_browser:
        # Vite needs a moment before it will answer.
        threading.Timer(1.5 if opts.dev else 0.5, lambda: webbrowser.open(url)).start()

    try:
        import uvicorn

        uvicorn.run(app, host=host, port=port, log_level="warning")
    finally:
        if vite is not None:
            vite.terminate()
            try:
                vite.wait(timeout=5)
            except subprocess.TimeoutExpired:
                vite.kill()


if __name__ == "__main__":
    main()
