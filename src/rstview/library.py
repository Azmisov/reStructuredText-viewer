"""A rooted collection of reStructuredText documents.

Cross-document links mean the server can no longer serve exactly one file, so
it serves a directory - which makes path containment a security boundary rather
than a detail. Every lookup goes through `resolve`.
"""
import os
import pathlib

from .directives import load_config, register
from .parse import parse

SUFFIXES = (".rst", ".txt", ".rest")

# Directories that hold no documents and would make a listing useless.
IGNORED_DIRS = frozenset({
    ".git", "node_modules", "__pycache__", ".venv", "venv",
    ".pytest_cache", "dist", "build", ".tox", ".mypy_cache", ".idea", ".vscode",
})

# A listing is for choosing from, not for enumerating a filesystem.
LIST_LIMIT = 2000


class DocumentError(Exception):
    """Requested path is missing, unreadable, or outside the root."""


class Document:
    """One file's current AST and the clients watching it."""

    def __init__(self, relpath, abspath):
        self.relpath = relpath
        self.abspath = abspath
        self.ast = None
        self.version = 0
        self.clients = set()

    def render(self, source=None):
        """`source` overrides the file's contents, for previewing an unsaved
        editor buffer without writing it to disk."""
        if source is None:
            try:
                source = pathlib.Path(self.abspath).read_text(encoding="utf-8")
            except OSError as exc:
                source = f".. error::\n\n   Cannot read {self.relpath}: {exc}\n"
        self.ast = parse(source, filename=self.relpath)
        self.version += 1
        return self.ast

    def message(self):
        return {
            "type": "doc",
            "path": self.relpath,
            "version": self.version,
            "ast": self.ast,
        }


class Library:
    """Documents under a single root directory."""

    def __init__(self, root, config=None):
        self.root = os.path.realpath(root)
        self.config = config
        self._documents = {}

    def _within(self, real):
        """True if an already-realpath'd path is at or under the root.

        The root may itself be the filesystem root, where naive
        `root + os.sep` prefixing yields "//" and matches nothing.
        """
        if real == self.root:
            return True
        prefix = self.root if self.root.endswith(os.sep) else self.root + os.sep
        return real.startswith(prefix)

    def resolve(self, relpath):
        """Map a client-supplied path to an absolute path inside the root.

        Rejects absolute paths, parent traversal, and symlinks pointing out of
        the tree. realpath is resolved *before* the containment check so a
        symlink cannot be used to step outside.
        """
        if not relpath:
            raise DocumentError("no document requested")

        candidate = os.path.normpath(os.path.join(self.root, relpath))
        real = os.path.realpath(candidate)

        if not self._within(real):
            raise DocumentError(f"{relpath!r} is outside the document root")
        if not os.path.isfile(real):
            raise DocumentError(f"{relpath!r} does not exist")
        if not real.lower().endswith(SUFFIXES):
            raise DocumentError(f"{relpath!r} is not a reStructuredText file")
        return real

    def resolve_dir(self, relpath):
        """Same containment rules as `resolve`, but for a directory."""
        candidate = os.path.normpath(os.path.join(self.root, relpath or "."))
        real = os.path.realpath(candidate)
        if not self._within(real):
            raise DocumentError(f"{relpath!r} is outside the document root")
        if not os.path.isdir(real):
            raise DocumentError(f"{relpath!r} is not a directory")
        return real

    def browse(self, relpath="", show_hidden=False, show_all=False):
        """One directory's contents, for the file dialog.

        `show_hidden` includes dot-entries; `show_all` includes files that are
        not reStructuredText. Directories are always listed so the tree stays
        navigable.
        """
        directory = self.resolve_dir(relpath)
        here = self.relative(directory) or ""
        here = "" if here == "." else here

        entries = []
        try:
            names = os.listdir(directory)
        except OSError as exc:
            raise DocumentError(f"cannot read {relpath!r}: {exc}") from exc

        for name in names:
            if name.startswith(".") and not show_hidden:
                continue
            full = os.path.join(directory, name)
            child = self.relative(full)
            # relative() returns None for symlinks pointing out of the tree.
            if child is None:
                continue

            if os.path.isdir(full):
                kind = "dir"
            elif name.lower().endswith(SUFFIXES):
                kind = "doc"
            elif show_all:
                kind = "file"
            else:
                continue

            try:
                stat = os.stat(full)
                size, mtime = stat.st_size, stat.st_mtime
            except OSError:
                size, mtime = None, None

            entries.append({
                "name": name,
                "path": child,
                "kind": kind,
                "size": None if kind == "dir" else size,
                "mtime": mtime,
            })

        # Directories first, then documents, then everything else.
        order = {"dir": 0, "doc": 1, "file": 2}
        entries.sort(key=lambda e: (order[e["kind"]], e["name"].lower()))

        parent = None if here == "" else os.path.dirname(here)
        return {"path": here, "parent": parent, "entries": entries}

    def locate(self, text):
        """Resolve a pasted path - absolute or relative - to a library path.

        Absolute paths inside the root are accepted and converted; anything
        outside it is refused with a message naming the boundary.
        """
        text = (text or "").strip()
        if not text:
            raise DocumentError("no path given")
        if text.startswith("~"):
            text = os.path.expanduser(text)

        candidate = text if os.path.isabs(text) else os.path.join(self.root, text)
        real = os.path.realpath(os.path.normpath(candidate))

        if not self._within(real):
            raise DocumentError(
                f"{text!r} is outside the document root ({self.root}); "
                f"restart with --root to widen it"
            )
        if not os.path.exists(real):
            raise DocumentError(f"{text!r} does not exist")

        relpath = self.relative(real) or ""
        return {
            "path": "" if relpath == "." else relpath,
            "kind": "dir" if os.path.isdir(real) else "doc",
        }

    def relative(self, abspath):
        """Inverse of resolve, for mapping filesystem events back to documents."""
        real = os.path.realpath(abspath)
        if not self._within(real):
            return None
        return os.path.relpath(real, self.root).replace(os.sep, "/")

    def get(self, relpath):
        """Fetch (and cache) a document, rendering it on first request."""
        abspath = self.resolve(relpath)
        key = self.relative(abspath)

        document = self._documents.get(key)
        if document is None:
            document = Document(key, abspath)
            self._documents[key] = document
            self.reload(document)
        return document

    def find(self, abspath):
        """The already-loaded document for a path, if any."""
        key = self.relative(abspath)
        return self._documents.get(key) if key else None

    def reload(self, document, source=None):
        # Config is re-read per render so adding a component needs no restart.
        register(load_config(self.config))
        document.render(source)
        return document

    @property
    def documents(self):
        return list(self._documents.values())

    def listing(self, limit=LIST_LIMIT):
        """Every document under the root, for the open-file picker.

        Walks the tree rather than reusing the loaded cache: the point is to
        show documents that have never been opened.
        """
        found = []
        for directory, subdirs, files in os.walk(self.root):
            # Prune in place so os.walk does not descend into them at all.
            subdirs[:] = sorted(d for d in subdirs
                                if d not in IGNORED_DIRS and not d.startswith("."))
            for name in sorted(files):
                if not name.lower().endswith(SUFFIXES):
                    continue
                relpath = self.relative(os.path.join(directory, name))
                # relative() returns None for symlinks pointing out of the tree.
                if relpath is not None:
                    found.append(relpath)
                if len(found) >= limit:
                    return sorted(found)
        return sorted(found)
