"""The stdio transport: same vocabulary as the WebSocket, one JSON per line."""
import io
import json
import os
import pathlib
import subprocess
import sys

import pytest

from rstview import stdio

SRC = str(pathlib.Path(__file__).resolve().parents[1] / "src")


@pytest.fixture
def root(tmp_path):
    (tmp_path / "a.rst").write_text("Alpha\n=====\n\nFirst.\n\nSecond.\n")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "b.rst").write_text("Beta\n====\n")
    (tmp_path / "outside.rst").write_text("Outside\n=======\n")
    return tmp_path


def drive(root, entry, messages, path=None):
    """Run the loop in-process over canned input; returns the parsed frames."""
    stream_in = io.StringIO("".join(json.dumps(m) + "\n" for m in messages))
    stream_out = io.StringIO()
    stdio.serve(
        path if path is not None else (str(root / entry) if entry else None),
        root=str(root),
        config=None,
        stream_in=stream_in,
        stream_out=stream_out,
    )
    return [json.loads(line) for line in stream_out.getvalue().splitlines() if line]


def test_ready_is_the_first_frame(root):
    frames = drive(root, None, [])
    assert frames[0]["type"] == "ready"
    assert frames[0]["entry"] is None
    assert frames[0]["root"] == os.path.realpath(root)


def test_entry_document_is_pushed_after_ready(root):
    frames = drive(root, "a.rst", [])
    assert [f["type"] for f in frames] == ["ready", "doc"]
    assert frames[0]["entry"] == "a.rst"
    assert frames[1]["path"] == "a.rst"


def test_open_returns_that_document(root):
    frames = drive(root, None, [{"type": "open", "path": "docs/b.rst"}])
    assert frames[-1]["type"] == "doc"
    assert frames[-1]["path"] == "docs/b.rst"
    assert frames[-1]["ast"]["type"] == "document"


def test_list_enumerates_the_library(root):
    frames = drive(root, None, [{"type": "list"}])
    assert frames[-1]["type"] == "list"
    assert set(frames[-1]["documents"]) == {"a.rst", "docs/b.rst", "outside.rst"}


def test_traversal_is_refused_without_killing_the_loop(root, tmp_path):
    frames = drive(
        root / "docs", None,
        [{"type": "open", "path": "../a.rst"}, {"type": "open", "path": "b.rst"}],
    )
    assert frames[1]["type"] == "error"
    assert "outside the document root" in frames[1]["message"]
    assert frames[2]["type"] == "doc" and frames[2]["path"] == "b.rst"


def test_malformed_json_is_reported_and_survived(root):
    stream_in = io.StringIO('not json\n{"type": "open", "path": "a.rst"}\n')
    stream_out = io.StringIO()
    stdio.serve(None, root=str(root), stream_in=stream_in, stream_out=stream_out)
    frames = [json.loads(l) for l in stream_out.getvalue().splitlines() if l]
    assert frames[1]["type"] == "error"
    assert frames[2]["type"] == "doc"


def test_source_renders_the_buffer_not_the_file(root):
    frames = drive(root, None, [
        {"type": "source", "path": "a.rst", "text": "Unsaved\n=======\n\nBuffer.\n"},
    ])
    assert frames[-1]["type"] == "doc" and frames[-1]["path"] == "a.rst"
    assert "Unsaved" in json.dumps(frames[-1]["ast"])
    assert "Alpha" not in json.dumps(frames[-1]["ast"])
    assert root.joinpath("a.rst").read_text().startswith("Alpha"), "must not touch disk"


def test_source_outside_the_root_is_refused(root):
    frames = drive(root / "docs", None, [
        {"type": "source", "path": "../a.rst", "text": "Anything\n========\n"},
    ])
    assert frames[-1]["type"] == "error"
    assert "outside the document root" in frames[-1]["message"]


def test_successive_sources_bump_the_version(root):
    frames = drive(root, None, [
        {"type": "source", "path": "a.rst", "text": "A\n=\n\nOne.\n"},
        {"type": "source", "path": "a.rst", "text": "A\n=\n\nTwo.\n"},
    ])
    docs = [f for f in frames if f["type"] == "doc"]
    assert docs[1]["version"] > docs[0]["version"]


def test_source_edits_preserve_ids_for_unchanged_content(root, ids):
    base = "A\n=\n\nOne.\n\nTwo.\n\nThree.\n"
    frames = drive(root, None, [
        {"type": "source", "path": "a.rst", "text": base},
        {"type": "source", "path": "a.rst", "text": base.replace("Two.", "Twoo.")},
    ])
    docs = [f for f in frames if f["type"] == "doc"]
    before, after = ids(docs[0]["ast"]), ids(docs[1]["ast"])
    assert len(before - after) <= 2, "an edited paragraph must not churn the rest"
    assert len(before & after) >= len(before) - 2


def test_docutils_warnings_never_reach_stdout(root):
    """The corruption risk: a warning printed as text would break the frame."""
    proc = subprocess.run(
        [sys.executable, "-m", "rstview.cli", "--stdio", "--root", str(root)],
        input=json.dumps({
            "type": "source",
            "path": "a.rst",
            "text": "A\n=\n\n.. nosuchdirective::\n\n   body\n\n`broken ref_\n",
        }) + "\n",
        capture_output=True, text=True,
        env={**os.environ, "PYTHONPATH": SRC},
        timeout=60,
    )
    assert proc.returncode == 0, proc.stderr
    frames = [json.loads(line) for line in proc.stdout.splitlines() if line.strip()]
    assert [f["type"] for f in frames] == ["ready", "doc"]
    payload = json.dumps(frames[-1]["ast"])
    assert "system_message" in payload, "the warning belongs in the tree"


def test_spawned_process_speaks_the_protocol(root):
    proc = subprocess.run(
        [sys.executable, "-m", "rstview.cli", "--stdio", str(root / "a.rst"),
         "--root", str(root)],
        input=json.dumps({"type": "open", "path": "docs/b.rst"}) + "\n",
        capture_output=True, text=True,
        env={**os.environ, "PYTHONPATH": SRC},
        timeout=60,
    )
    assert proc.returncode == 0, proc.stderr
    frames = [json.loads(line) for line in proc.stdout.splitlines() if line.strip()]
    assert [f["type"] for f in frames] == ["ready", "doc", "doc"]
    assert frames[1]["path"] == "a.rst"
    assert frames[2]["path"] == "docs/b.rst"


@pytest.mark.parametrize("extra", [["--dev"], ["--port", "5000"], ["--listen", "0.0.0.0"]])
def test_stdio_rejects_server_flags(extra, capsys):
    from rstview import cli
    with pytest.raises(SystemExit):
        cli.main(["--stdio", *extra])
    assert "--stdio" in capsys.readouterr().err


def test_stdio_does_not_import_the_server_stack():
    """`--stdio` must run on an interpreter that has only docutils.

    An editor host spawns this, and requiring Starlette, uvicorn and watchdog
    there would triple what a user has to install for a preview pane. The
    imports are lazy in `cli.py` precisely to keep that floor low; this fails
    if someone hoists them back to module scope.
    """
    probe = (
        "import sys; import rstview.cli; "
        "print([m for m in ('starlette', 'uvicorn', 'watchdog') if m in sys.modules])"
    )
    result = subprocess.run(
        [sys.executable, "-c", probe], capture_output=True, text=True, timeout=30
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "[]", f"server stack imported eagerly: {result.stdout}"
