"""Command line entry point."""
import argparse
import ipaddress
import json
import os
import pathlib
import shutil
import socket
import subprocess
import sys
import threading
import urllib.error
import urllib.request
import webbrowser
from urllib.parse import urlencode, urlsplit

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

# Binding these listens on every interface, so there is no one address to
# open in a browser or to print.
WILDCARD_HOSTS = frozenset({"0.0.0.0", "::", ""})


def default_root(filename, listen):
    """Where cross-document links and the file dialog may reach.

    With no document named, it is the current directory: the file dialog
    opens there, which is where whoever ran the command is working.

    Given a document, on a loopback interface the server is no more exposed
    than the shell that started it, so the default is the whole filesystem
    and the document may link anywhere. Bound anywhere else it is reachable by
    others, and the default narrows to the document's own directory -
    `--root` overrides either way.
    """
    if not filename:
        return os.getcwd()
    if listen not in LOCAL_HOSTS:
        return os.path.dirname(os.path.realpath(filename))
    return os.path.abspath(os.sep)


def _own_names():
    """Names this machine answers to that no outside page can be served from:
    an IP literal, or one of these."""
    hostname = socket.gethostname().lower()
    names = {"localhost", hostname, f"{hostname}.local", socket.getfqdn().lower()}

    def ours(name):
        try:
            ipaddress.ip_address(name)
        except ValueError:
            return name.lower() in names
        return True

    return ours


def published_origins():
    """The WebSocket origin check for a server reachable from other machines.

    A fixed allowlist cannot name every address a LAN client might connect
    by, and listing the bind address itself is useless for a wildcard - no
    browser's origin is `http://0.0.0.0`. So the origin must instead be the
    host the browser connected to, which a page from another site cannot
    arrange: its origin is its own.

    A DNS-rebinding page can, since it controls a name that resolves here. So
    that host must also be an IP literal or one of this machine's own names -
    neither of which an attacker's page can be served from.
    """
    ours = _own_names()

    def allowed(origin, host):
        if not host or origin.lower() != f"http://{host.lower()}":
            return False
        return ours(urlsplit(origin).hostname or "")

    return allowed


def allowed_hosts(listen):
    """The Host header check for every request, against DNS rebinding.

    On loopback only loopback names can reach the server legitimately; bound
    wider, any address or name of this machine can, by the same reasoning as
    `published_origins`.
    """
    if listen in LOCAL_HOSTS:
        return lambda name: name.lower() in LOCAL_HOSTS
    return _own_names()


def _fetch(url):
    """GET a JSON route of a server on this machine: (status, body), or None
    if nothing answered with JSON. Proxies are bypassed - an http_proxy that
    does not exempt localhost would otherwise swallow the request."""
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(url, timeout=2) as response:
            return response.status, json.load(response)
    except urllib.error.HTTPError as exc:
        try:
            return exc.code, json.load(exc)
        except ValueError:
            return None
    except (OSError, ValueError):
        return None


def running_server(port):
    """What `/api/info` says about an rstview already on `port`, or None.

    Anything else on the port - or nothing - is None, and the caller starts a
    server of its own, failing as it always has if the port is taken.
    """
    answer = _fetch(f"http://localhost:{port}/api/info")
    if answer is None or answer[0] != 200:
        return None
    info = answer[1]
    return info if isinstance(info, dict) and info.get("name") == "rstview" else None


def tab_url(base, kind, relpath):
    """The page address that opens a document, or the dialog in a folder."""
    if kind == "dir":
        return f"{base}?{urlencode({'dir': relpath})}" if relpath else base
    return f"{base}?{urlencode({'doc': relpath})}"


def hand_over(info, port, target, no_browser):
    """Open `target` in a server that is already running, then return.

    The server resolves the path, since it owns the root and the containment
    rules. The browser is opened from here rather than by the server: this
    process is in the user's desktop session, and a daemon started by a
    service manager may have no display to open one on.
    """
    base = info.get("url") or f"http://localhost:{port}/"
    asked = target or os.getcwd()
    answer = _fetch(f"http://localhost:{port}/api/locate?{urlencode({'path': os.path.abspath(asked)})}")
    if answer is None:
        sys.exit(f"rstview: the server at {base} did not answer")
    status, body = answer
    if status != 200:
        if target is None:
            # Run from outside the server's root with nothing named: the
            # dialog at the root is still what was asked for.
            body = {"path": "", "kind": "dir"}
        else:
            sys.exit(f"rstview: {body.get('message', 'refused')} (server at {base})")
    if body["kind"] == "file":
        sys.exit(f"rstview: {asked} is not a reStructuredText or Markdown file")

    url = tab_url(base, body["kind"], body["path"])
    print(f"rstview: opening {asked} in the server already at {base}", file=sys.stderr)
    if no_browser:
        print(url)
    else:
        webbrowser.open(url)


def _lan_address():
    """This machine's address on its default route, or None offline.

    Connecting a UDP socket sends nothing; it only makes the kernel choose the
    outgoing interface, whose address is the one a LAN client would use.
    """
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("192.0.2.1", 9))
            return sock.getsockname()[0]
    except OSError:
        return None


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
                        help="document to preview, or a folder to open the file "
                             "dialog in; omit for the current directory. If an "
                             "rstview is already listening on the port, the tab "
                             "is opened on that one instead")
    parser.add_argument("-d", "--daemon", action="store_true",
                        help="run as a long-lived server: open no browser, "
                             "default the root to your home directory, and let "
                             "`rstview PATH` from any shell open tabs on it")
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
                             "dialog may reach [default: your home directory "
                             "with --daemon; the folder given, or the current "
                             "directory with no document given; otherwise the "
                             "whole filesystem on a loopback interface, or the "
                             "document's own directory when bound elsewhere]")
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
    if opts.daemon:
        if opts.filename:
            parser.error("--daemon starts with nothing open; once it is "
                         "running, `rstview PATH` opens a tab on it")
        if host not in LOCAL_HOSTS and opts.root is None:
            parser.error("--daemon bound beyond loopback would publish your "
                         "home directory; pass --root to say what to serve")

    port = DEFAULT_PORT if opts.port is None else opts.port
    if port != 0:
        running = running_server(port)
        if running is not None:
            # Options that shape a server have nothing to apply to one that
            # already exists, so they mean "a second server" - which cannot
            # share this port.
            if opts.daemon or opts.dev or opts.root or opts.listen:
                sys.exit(f"rstview: another rstview is already serving "
                         f"{running.get('root')} on port {port}; stop it, or "
                         f"pass --port 0 to run beside it")
            hand_over(running, port, opts.filename, opts.no_browser)
            return
    port = _free_port(host) if port == 0 else port

    # A folder is where the dialog starts, and with no --root, what it may
    # reach - as if rstview had been run from inside it.
    filename, folder = opts.filename, None
    if filename and os.path.isdir(filename):
        filename, folder = None, filename

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
        # A wildcard is not an address a browser can usefully open, so this
        # machine's own browser goes through loopback instead.
        shown = "localhost" if host in WILDCARD_HOSTS else host
        url = f"http://{shown}:{port}/"
        origins = {f"http://{host}:{port}", f"http://127.0.0.1:{port}"}

    if opts.root:
        root = opts.root
    elif opts.daemon:
        root = os.path.expanduser("~")
    elif folder:
        root = folder
    else:
        root = default_root(filename, host)
    published = host not in LOCAL_HOSTS
    # The Vite proxy rewrites the handshake, so --dev keeps the fixed list.
    if published and not opts.dev:
        origins = published_origins()

    try:
        from .app import create_app
        from .library import DocumentError
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
            filename,
            allowed_origins=origins,
            config=opts.components,
            root=root,
            allowed_hosts=allowed_hosts(host),
            url=url,
        )
    except ValueError as exc:
        sys.exit(f"rstview: {exc}")

    start = url
    if folder:
        try:
            start = tab_url(url, "dir", app.state.library.locate(os.path.abspath(folder))["path"])
        except DocumentError as exc:
            sys.exit(f"rstview: {exc}")

    if opts.daemon:
        print(f"rstview: daemon at {url}; `rstview PATH` opens a tab on it",
              file=sys.stderr)
    else:
        what = filename or folder or "no document open"
        print(f"rstview: serving {what} at {url}", file=sys.stderr)
    print(f"rstview: document root {os.path.realpath(root)}", file=sys.stderr)
    if host in WILDCARD_HOSTS and not opts.dev:
        others = [socket.gethostname(), _lan_address()]
        for name in filter(None, others):
            print(f"rstview: also at http://{name}:{port}/", file=sys.stderr)
    if published and opts.root is None and filename:
        print("rstview: bound to a non-loopback interface; root limited to the "
              "document's directory (pass --root to widen)", file=sys.stderr)
    if opts.dev:
        print(f"rstview: api on :{port}, vite with HMR on {url}", file=sys.stderr)
    # A daemon outlives the shell that started it, and a service manager may
    # give it no display; tabs come from `rstview PATH` instead.
    if not opts.no_browser and not opts.daemon:
        # Vite needs a moment before it will answer.
        threading.Timer(1.5 if opts.dev else 0.5, lambda: webbrowser.open(start)).start()

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
