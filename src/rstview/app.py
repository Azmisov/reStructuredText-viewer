"""Starlette app: serves the client bundle and streams document ASTs.

A client subscribes to one document at a time and can switch by sending an
`open` message, which is how cross-document links load without a page reload.
"""
import contextlib
import pathlib
from urllib.parse import urlsplit

from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.responses import FileResponse, JSONResponse, PlainTextResponse
from starlette.routing import Mount, Route, WebSocketRoute
from starlette.staticfiles import StaticFiles
from starlette.websockets import WebSocketDisconnect

from .library import DocumentError
from .session import Session, broadcast, open_library
from .watch import Watcher

CLIENT_DIST = pathlib.Path(__file__).parent / "client"


async def _send(websocket, payload):
    try:
        await websocket.send_json(payload)
        return True
    except Exception:  # noqa: BLE001 - client vanished mid-send
        return False


class HostGuard:
    """Refuse any request whose Host header names somewhere else.

    The WebSocket checks Origin, but the HTTP routes cannot: a plain GET
    carries none. What they are exposed to is DNS rebinding - a page on an
    attacker's name that re-resolves to 127.0.0.1 is same-origin with its own
    requests here, and could read `/media` and `/api/doc` across the whole
    root. Its requests still say its own name in Host, which this refuses.
    That matters most for a daemon over a home directory, left running.
    """

    def __init__(self, app, allowed):
        self.app = app
        self.allowed = allowed

    async def __call__(self, scope, receive, send):
        if scope["type"] in ("http", "websocket"):
            host = dict(scope["headers"]).get(b"host", b"").decode("latin-1")
            try:
                name = urlsplit(f"//{host}").hostname or ""
            except ValueError:  # an unbalanced "[" in the header
                name = ""
            if not self.allowed(name):
                if scope["type"] == "websocket":
                    await send({"type": "websocket.close", "code": 1008})
                    return
                response = PlainTextResponse("unrecognised Host header", status_code=421)
                await response(scope, receive, send)
                return
        await self.app(scope, receive, send)


def create_app(path=None, allowed_origins=None, config=None, root=None,
               allowed_hosts=None, url=None):
    """`path` may be None: the server then starts with no document open and
    the client picks one from the library.

    `allowed_origins` is a set of exact origins, or a predicate called with
    the origin and the request's Host header - for a server bound beyond
    loopback, where no fixed list can name every address a client may use.

    `allowed_hosts`, if given, is a predicate on the hostname a request was
    addressed to; anything it refuses is answered 421. `url` is where a
    browser should open this server, reported by `/api/info` so a second
    `rstview` can hand its document over instead of starting another."""
    library, entry = open_library(path, config=config, root=root)
    root = library.root

    allowed = allowed_origins

    async def index(request):
        page = CLIENT_DIST / "index.html"
        if not page.exists():
            return PlainTextResponse(
                "Client bundle not built. Run: pnpm --dir client build", status_code=503
            )
        return FileResponse(page)

    async def api_doc(request):
        requested = request.query_params.get("path") or entry
        if not requested:
            return JSONResponse(
                {"type": "error", "message": "no document open"}, status_code=404
            )
        try:
            return JSONResponse(library.get(requested).message())
        except DocumentError as exc:
            return JSONResponse({"type": "error", "message": str(exc)}, status_code=404)

    async def media(request):
        """Serve a file a document points at - an image, mostly.

        Same containment as documents, so this widens what can be *read* to
        any file inside the root but not where it can reach. Without it every
        `.. image::` in every document is a 404.
        """
        try:
            path = library.resolve_asset(request.path_params["path"])
        except DocumentError as exc:
            return PlainTextResponse(str(exc), status_code=404)
        return FileResponse(path)

    async def api_entry(request):
        return JSONResponse({"path": entry, "root": root})

    async def api_info(request):
        """Who is listening. `name` is what tells a probing `rstview` that the
        port holds another instance of itself and not something unrelated."""
        return JSONResponse({"name": "rstview", "root": root, "entry": entry, "url": url})

    async def api_documents(request):
        return JSONResponse({"type": "list", "documents": library.listing()})

    def _flag(request, name):
        return request.query_params.get(name, "").lower() in ("1", "true", "yes")

    async def api_browse(request):
        try:
            return JSONResponse(library.browse(
                request.query_params.get("path", ""),
                show_hidden=_flag(request, "hidden"),
                show_all=_flag(request, "all"),
            ))
        except DocumentError as exc:
            return JSONResponse({"type": "error", "message": str(exc)}, status_code=404)

    async def api_locate(request):
        """Resolve a pasted path, so the dialog can jump straight to it."""
        try:
            return JSONResponse(library.locate(request.query_params.get("path", "")))
        except DocumentError as exc:
            return JSONResponse({"type": "error", "message": str(exc)}, status_code=404)

    async def ws(websocket):
        # The WebSocket handshake is not covered by CORS, so check Origin here.
        origin = websocket.headers.get("origin")
        if allowed is None or origin is None:
            permitted = True
        elif callable(allowed):
            permitted = allowed(origin, websocket.headers.get("host"))
        else:
            permitted = origin in allowed
        if not permitted:
            await websocket.close(code=1008)
            return

        await websocket.accept()
        session = Session(
            library,
            lambda payload: _send(websocket, payload),
            client=websocket,
            entry=entry,
        )

        try:
            await session.start()
            while True:
                await session.handle(await websocket.receive_json())
        except (WebSocketDisconnect, ValueError):
            pass
        finally:
            session.close()

    routes = [
        Route("/", index),
        Route("/api/doc", api_doc),
        Route("/media/{path:path}", media),
        Route("/api/entry", api_entry),
        Route("/api/info", api_info),
        Route("/api/documents", api_documents),
        Route("/api/browse", api_browse),
        Route("/api/locate", api_locate),
        WebSocketRoute("/ws", ws),
    ]
    if (CLIENT_DIST / "assets").exists():
        routes.append(Mount("/assets", StaticFiles(directory=CLIENT_DIST / "assets")))

    async def on_change(changed):
        await broadcast(library, changed, _send, config=config)

    @contextlib.asynccontextmanager
    async def lifespan(app):
        watcher = Watcher(root, on_change, extra=[config] if config else None)
        # Documents opened later - a cross-document link, the file dialog -
        # each add their own directory as they load.
        library.on_load = watcher.watch
        for document in library.documents:
            watcher.watch(document.abspath)
        watcher.start()
        try:
            yield
        finally:
            watcher.stop()

    middleware = [] if allowed_hosts is None else [Middleware(HostGuard, allowed=allowed_hosts)]
    app = Starlette(routes=routes, lifespan=lifespan, middleware=middleware)
    app.state.library = library
    app.state.entry = entry
    return app
