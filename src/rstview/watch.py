"""Recursive file watching with debounce, bridged from watchdog to the loop."""
import asyncio
import os

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

DEBOUNCE = 0.03

# Newer inotify backends report reads as well as writes. Reacting to those
# means our own render() re-triggers the watcher, which renders again: a
# self-sustaining loop that never touches the file it is supposedly watching.
READ_ONLY_EVENTS = frozenset({"opened", "closed_no_write"})

WATCHED_SUFFIXES = (".rst", ".txt", ".rest")

# Directories that generate constant churn and hold no documents.
IGNORED_DIRS = frozenset({
    ".git", "node_modules", "__pycache__", ".venv", "venv",
    ".pytest_cache", "dist", "build", ".tox", ".mypy_cache",
})


class _Handler(FileSystemEventHandler):
    def __init__(self, notify, extra):
        self.notify = notify
        self.extra = {os.path.realpath(p) for p in (extra or [])}

    def _relevant(self, path):
        if not path:
            return False
        real = os.path.realpath(path)
        if real in self.extra:
            return True
        parts = set(real.split(os.sep))
        if parts & IGNORED_DIRS:
            return False
        return real.lower().endswith(WATCHED_SUFFIXES)

    def on_any_event(self, event):
        if event.is_directory or event.event_type in READ_ONLY_EVENTS:
            return
        # Editors rename/replace rather than write in place, so consider both.
        for attr in ("src_path", "dest_path"):
            path = getattr(event, attr, None)
            if self._relevant(path):
                self.notify(os.path.realpath(path))
                return


class Watcher:
    """Calls `callback(path)` on the event loop when a watched file changes."""

    def __init__(self, root, callback, extra=None, loop=None):
        self.root = os.path.realpath(root)
        self.callback = callback
        self.extra = [p for p in (extra or []) if p and os.path.exists(p)]
        self.loop = loop or asyncio.get_event_loop()
        self.observer = Observer()
        self._timers = {}

    def _fire(self, path):
        # Coalesce bursts per path: one save can emit several events.
        timer = self._timers.pop(path, None)
        if timer is not None:
            timer.cancel()
        self._timers[path] = self.loop.call_later(
            DEBOUNCE, lambda: asyncio.ensure_future(self._run(path))
        )

    async def _run(self, path):
        self._timers.pop(path, None)
        await self.callback(path)

    def _notify(self, path):
        self.loop.call_soon_threadsafe(self._fire, path)

    def start(self):
        handler = _Handler(self._notify, self.extra)
        self.observer.schedule(handler, self.root, recursive=True)
        for directory in {os.path.dirname(p) for p in self.extra}:
            if directory and not directory.startswith(self.root):
                self.observer.schedule(handler, directory, recursive=False)
        self.observer.start()

    def stop(self):
        for timer in self._timers.values():
            timer.cancel()
        self._timers.clear()
        self.observer.stop()
        self.observer.join(timeout=2)
