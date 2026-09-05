"""Starlette app: serves the client bundle and streams document ASTs.

A client subscribes to one document at a time and can switch by sending an
`open` message, which is how cross-document links load without a page reload.
"""
import contextlib
import pathlib

from starlette.applications import Starlette
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


def create_app(path=None, allowed_origins=None, config=None, root=None):
    """`path` may be None: the server then starts with no document open and
    the client picks one from the library."""
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

    async def api_entry(request):
        return JSONResponse({"path": entry, "root": root})

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
        if allowed is not None and origin is not None and origin not in allowed:
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
        Route("/api/entry", api_entry),
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
        watcher.start()
        try:
            yield
        finally:
            watcher.stop()

    app = Starlette(routes=routes, lifespan=lifespan)
    app.state.library = library
    app.state.entry = entry
    return app
