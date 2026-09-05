"""Newline-delimited JSON over stdin/stdout, for an editor host.

Same message vocabulary as the WebSocket, one JSON object per line and no
framing headers. stdout carries protocol only: the real descriptor is taken
away from the process before anything else can write to it, so a stray print,
a traceback or a chatty dependency lands on stderr instead of corrupting a
frame.
"""
import asyncio
import json
import os
import sys

from .session import Session, open_library


def _claim_stdout():
    """Hand back an exclusive writer for the true stdout, and point every
    other writer - Python-level and fd-level alike - at stderr."""
    fd = os.dup(sys.stdout.fileno())
    sys.stdout.flush()
    os.dup2(sys.stderr.fileno(), sys.stdout.fileno())
    return os.fdopen(fd, "w", encoding="utf-8", newline="\n")


async def _serve(library, entry, stream_in, stream_out):
    async def send(payload):
        try:
            stream_out.write(json.dumps(payload) + "\n")
            stream_out.flush()
            return True
        except (OSError, ValueError):  # noqa: BLE001 - host closed the pipe
            return False

    session = Session(library, send, entry=entry)
    await session.start()

    try:
        while True:
            # readline blocks; keep it off the loop so a future watcher or
            # cancellation is not held up by an idle host.
            line = await asyncio.to_thread(stream_in.readline)
            if not line:
                break
            line = line.strip()
            if not line:
                continue
            try:
                message = json.loads(line)
            except ValueError as exc:
                await send({"type": "error", "message": f"malformed message: {exc}"})
                continue
            if isinstance(message, dict):
                await session.handle(message)
    finally:
        session.close()


def serve(path=None, config=None, root=None, stream_in=None, stream_out=None):
    """Run the stdio loop until the host closes stdin."""
    if stream_out is None:
        stream_out = _claim_stdout()
    if stream_in is None:
        stream_in = sys.stdin

    library, entry = open_library(path, config=config, root=root)
    asyncio.run(_serve(library, entry, stream_in, stream_out))
