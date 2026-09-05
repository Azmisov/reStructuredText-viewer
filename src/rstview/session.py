"""One client's view of a library, independent of how bytes reach it.

The WebSocket and the stdio loop differ only in framing: both speak the same
messages, so the document orchestration lives here and each transport supplies
a send function.
"""
import os

from .library import DocumentError, Library


def open_library(path=None, config=None, root=None):
    """(library, entry) for a starting document, or None to start empty."""
    if path is None:
        root = os.path.realpath(root or ".")
        return Library(root, config=config), None

    target = os.path.realpath(path)
    root = os.path.realpath(root or os.path.dirname(target) or ".")
    library = Library(root, config=config)
    entry = library.relative(target)
    if entry is None:
        raise ValueError(f"{path} is not inside the document root {root}")
    library.get(entry)
    return library, entry


class Session:
    """A subscription to one document at a time.

    `send` delivers a payload and returns falsey if the peer has gone. `client`
    is the token held in `Document.clients`, which is what pushes from the
    watcher are addressed to; a transport that identifies a client by something
    other than the session object passes it here.
    """

    def __init__(self, library, send, client=None, entry=None):
        self.library = library
        self.send = send
        self.client = self if client is None else client
        self.entry = entry
        self.current = None

    async def start(self):
        # With no entry document the client shows the picker instead.
        # Deliberately no document listing here: the root may be the whole
        # filesystem, and listing() walks it. The dialog browses one
        # directory at a time instead.
        await self.send({
            "type": "ready",
            "entry": self.entry,
            "root": self.library.root,
        })
        if self.entry:
            await self.open(self.entry)

    def _attach(self, document):
        if self.current is not None and self.current is not document:
            self.current.clients.discard(self.client)
        self.current = document
        document.clients.add(self.client)

    async def open(self, relpath):
        try:
            document = self.library.get(relpath)
        except DocumentError as exc:
            await self.send({"type": "error", "path": relpath, "message": str(exc)})
            return
        self._attach(document)
        await self.send(document.message())

    async def source(self, relpath, text):
        """Render an editor buffer as if it were the file at `relpath`.

        Goes through `library.get` so an unsaved buffer is subject to exactly
        the same containment rules as an `open`.
        """
        try:
            document = self.library.get(relpath)
        except DocumentError as exc:
            await self.send({"type": "error", "path": relpath, "message": str(exc)})
            return
        self._attach(document)
        self.library.reload(document, source=text)
        await self.send(document.message())

    async def listing(self):
        await self.send({"type": "list", "documents": self.library.listing()})

    async def handle(self, message):
        kind = message.get("type")
        if kind == "open":
            await self.open(message.get("path"))
        elif kind == "source":
            await self.source(message.get("path"), message.get("text") or "")
        elif kind == "list":
            await self.listing()

    def close(self):
        if self.current is not None:
            self.current.clients.discard(self.client)
            self.current = None


async def broadcast(library, changed, send, config=None):
    """Re-render whichever loaded documents changed and push to watchers."""
    documents = library.documents
    if changed:
        hit = library.find(changed)
        documents = [hit] if hit is not None else []
        if hit is None and config and os.path.realpath(changed) == os.path.realpath(config):
            # Component config changed: every document may render differently.
            documents = library.documents

    for document in documents:
        library.reload(document)
        payload = document.message()
        for client in list(document.clients):
            if not await send(client, payload):
                document.clients.discard(client)
