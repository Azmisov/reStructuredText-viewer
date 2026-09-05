"""Record what the server would answer for `samples/`, for the static demo.

The Pages site has no Python behind it, so the demo replays a transcript
instead: every message a real session would produce for the sample corpus,
generated here and read back by `client/src/transports/static.js`. Because it
comes out of the same `Library` the server uses, the demo cannot drift from
the real renderer - a change to parsing shows up in the published demo on the
next build, with nothing to update by hand.

    python scripts/fixtures.py --out demo/data

Document ASTs are written one file per document and fetched on demand; the
manifest holds only what is needed before anything is on screen.
"""
import argparse
import json
import pathlib
import shutil
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from rstview.library import SUFFIXES, Library  # noqa: E402

# The root the demo *claims*. The real one is wherever the build checked the
# repository out, which is both meaningless to a visitor and a detail of the
# build machine that has no business being published.
DEMO_ROOT = "/samples"


def browse_key(path, hidden, all_files):
    return f"{path}?{int(hidden)}{int(all_files)}"


def collect_browse(library):
    """Every directory the dialog can reach, under all four filter toggles.

    Four listings per directory is what makes the toggles work offline. The
    corpus is one directory deep, so this is cheap; it stays cheap because
    `browse` only ever lists one directory at a time.
    """
    payloads = {}
    pending = [""]
    seen = set()

    while pending:
        here = pending.pop()
        if here in seen:
            continue
        seen.add(here)
        for hidden in (False, True):
            for all_files in (False, True):
                listing = library.browse(here, show_hidden=hidden, show_all=all_files)
                payloads[browse_key(here, hidden, all_files)] = {
                    "type": "browse",
                    **listing,
                }
                for entry in listing["entries"]:
                    if entry["kind"] == "dir":
                        pending.append(entry["path"])
    return payloads


def collect_locate(library, browse_payloads):
    """What a pasted path can resolve to.

    A real `locate` walks the filesystem; this one knows the corpus it was
    generated from. Both the library-relative and the root-prefixed spelling
    are recorded, since those are the two forms a visitor sees in the page.
    """
    located = {}
    for payload in browse_payloads.values():
        for entry in payload["entries"]:
            if entry["kind"] == "file":
                continue
            resolved = {"type": "locate", "path": entry["path"], "kind": entry["kind"]}
            located[entry["path"]] = resolved
            located[f"{DEMO_ROOT}/{entry['path']}"] = resolved
    located[""] = located[DEMO_ROOT] = {"type": "locate", "path": "", "kind": "dir"}
    return located


def copy_media(source, destination):
    """The files documents point at - images, mostly.

    Everything that is not itself a document, so an `.. image::` added to a
    sample needs no change here. Mirrors the layout under the root because
    `resolveAsset` builds media URLs from library-relative paths.
    """
    for path in sorted(source.rglob("*")):
        if not path.is_file() or path.name.lower().endswith(SUFFIXES):
            continue
        if any(part.startswith(".") for part in path.relative_to(source).parts):
            continue
        target = destination / path.relative_to(source)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--samples", default=str(REPO / "samples"),
                        help="directory to record [default: samples/]")
    parser.add_argument("--entry", default="index.rst",
                        help="document the demo opens with [default: index.rst]")
    parser.add_argument("--out", default=str(REPO / "demo" / "data"),
                        help="where to write [default: demo/data]")
    parser.add_argument("--config", default=str(REPO / "rstview.config.json"),
                        help="component config [default: rstview.config.json]")
    opts = parser.parse_args(argv)

    samples = pathlib.Path(opts.samples).resolve()
    out = pathlib.Path(opts.out)
    # Rebuilt wholesale: a document deleted from the corpus must not survive in
    # the published demo as an orphan fixture.
    shutil.rmtree(out, ignore_errors=True)
    (out / "fixtures").mkdir(parents=True)

    library = Library(str(samples), config=opts.config)
    documents = library.listing()
    if opts.entry not in documents:
        raise SystemExit(f"entry {opts.entry!r} is not among {documents}")

    docs = {}
    for index, relpath in enumerate(documents):
        message = library.get(relpath).message()
        name = f"fixtures/{index}.json"
        (out / name).write_text(json.dumps(message), encoding="utf-8")
        docs[relpath] = name

    browse_payloads = collect_browse(library)
    manifest = {
        "root": DEMO_ROOT,
        "entry": opts.entry,
        "documents": documents,
        "docs": docs,
        "browse": browse_payloads,
        "locate": collect_locate(library, browse_payloads),
    }
    (out / "fixtures.json").write_text(json.dumps(manifest), encoding="utf-8")

    copy_media(samples, out / "media")

    total = sum(f.stat().st_size for f in out.rglob("*") if f.is_file())
    print(f"{len(docs)} documents, {total // 1024} kB of fixtures in {opts.out}")


if __name__ == "__main__":
    main()
