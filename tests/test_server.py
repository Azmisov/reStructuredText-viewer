"""HTTP, WebSocket, and the file-watch path."""
import contextlib
import json

import pytest
from starlette.testclient import TestClient

from rstview.app import create_app

DOC = "Title\n=====\n\nOriginal paragraph.\n"

ORIGIN = "http://localhost:8000"


@pytest.fixture
def rst(tmp_path):
    path = tmp_path / "doc.rst"
    path.write_text(DOC)
    (tmp_path / "other.rst").write_text("Other\n=====\n\nOther body.\n")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "deep.rst").write_text("Deep\n====\n\nDeep body.\n")
    return path


@contextlib.contextmanager
def connect(client, **kwargs):
    """Open a socket and consume the opening `ready` frame.

    Every connection starts with `ready` (carrying the entry document and the
    library listing) before any document arrives.
    """
    with client.websocket_connect("/ws", **kwargs) as ws:
        ready = ws.receive_json()
        assert ready["type"] == "ready"
        ws.ready = ready
        yield ws


@pytest.fixture
def client(rst):
    app = create_app(str(rst), allowed_origins={ORIGIN})
    with TestClient(app) as client:
        yield client


def test_api_doc_returns_an_ast(client):
    payload = client.get("/api/doc").json()
    assert payload["type"] == "doc"
    assert payload["version"] >= 1
    assert payload["ast"]["type"] == "document"


def test_websocket_pushes_the_document_on_connect(client):
    with connect(client, headers={"origin": ORIGIN}) as ws:
        message = ws.receive_json()
        assert message["type"] == "doc"
        assert message["ast"]["type"] == "document"


def test_websocket_rejects_a_foreign_origin(client):
    with pytest.raises(Exception):
        with client.websocket_connect("/ws", headers={"origin": "http://evil.example"}) as ws:
            ws.receive_json()


def test_websocket_allows_a_request_without_an_origin(client):
    """Non-browser clients (a future VS Code host) send no Origin header."""
    with connect(client) as ws:
        assert ws.receive_json()["type"] == "doc"


def test_editing_the_file_pushes_a_new_version(client, rst):
    with connect(client, headers={"origin": ORIGIN}) as ws:
        first = ws.receive_json()

        rst.write_text(DOC.replace("Original", "Edited"))
        second = ws.receive_json()

        assert second["version"] > first["version"]
        assert "Edited" in json.dumps(second["ast"])


def test_the_edit_preserves_most_node_ids(client, rst, ids):
    with connect(client, headers={"origin": ORIGIN}) as ws:
        first = ws.receive_json()
        rst.write_text(DOC.replace("Original paragraph.", "Edited paragraph."))
        second = ws.receive_json()

    before, after = ids(first["ast"]), ids(second["ast"])
    assert len(before - after) <= 3


def test_a_deleted_file_reports_an_error_instead_of_crashing(client, rst):
    with connect(client, headers={"origin": ORIGIN}) as ws:
        ws.receive_json()
        rst.unlink()
        message = ws.receive_json()
        assert message["ast"]["type"] == "document"


def test_index_is_served_when_the_client_is_built(client):
    response = client.get("/")
    # 503 is the documented answer when the bundle is missing.
    assert response.status_code in (200, 503)


def test_reading_the_file_does_not_retrigger_a_render(client):
    """inotify reports reads as well as writes; reacting to those makes
    render() re-trigger the watcher, looping forever without any edit."""
    import time

    before = client.get("/api/doc").json()["version"]
    for _ in range(5):
        client.get("/api/doc")
    time.sleep(0.4)
    after = client.get("/api/doc").json()["version"]
    assert after == before, f"version climbed {before} -> {after} with no edit"


def test_api_doc_serves_another_document_by_path(client):
    payload = client.get("/api/doc", params={"path": "other.rst"}).json()
    assert payload["path"] == "other.rst"
    assert "Other body" in json.dumps(payload["ast"])


def test_api_doc_refuses_a_path_outside_the_root(client):
    assert client.get("/api/doc", params={"path": "../../etc/passwd"}).status_code == 404


def test_api_entry_reports_the_starting_document(client):
    assert client.get("/api/entry").json()["path"] == "doc.rst"


def test_websocket_can_switch_documents(client):
    with connect(client, headers={"origin": ORIGIN}) as ws:
        first = ws.receive_json()
        assert first["path"] == "doc.rst"

        ws.send_json({"type": "open", "path": "sub/deep.rst"})
        second = ws.receive_json()
        assert second["path"] == "sub/deep.rst"
        assert "Deep body" in json.dumps(second["ast"])


def test_switching_documents_moves_the_subscription(client, rst, tmp_path):
    """After navigating away, edits to the old document must not be pushed."""
    with connect(client, headers={"origin": ORIGIN}) as ws:
        ws.receive_json()
        ws.send_json({"type": "open", "path": "other.rst"})
        assert ws.receive_json()["path"] == "other.rst"

        (tmp_path / "other.rst").write_text("Other\n=====\n\nEdited.\n")
        pushed = ws.receive_json()
        assert pushed["path"] == "other.rst"
        assert "Edited" in json.dumps(pushed["ast"])


def test_websocket_reports_a_bad_path_without_dropping_the_connection(client):
    with connect(client, headers={"origin": ORIGIN}) as ws:
        ws.receive_json()
        ws.send_json({"type": "open", "path": "../../etc/passwd"})
        message = ws.receive_json()
        assert message["type"] == "error"

        # The socket must still work afterwards.
        ws.send_json({"type": "open", "path": "other.rst"})
        assert ws.receive_json()["path"] == "other.rst"


def test_ready_frame_carries_the_entry_and_root(client, tmp_path):
    with connect(client, headers={"origin": ORIGIN}) as ws:
        assert ws.ready["entry"] == "doc.rst"
        assert ws.ready["root"] == str(tmp_path.resolve())


def test_ready_frame_does_not_walk_the_root(client):
    """The root may be the whole filesystem; listing it on connect would crawl
    it. The dialog browses one directory at a time instead."""
    with connect(client, headers={"origin": ORIGIN}) as ws:
        assert "documents" not in ws.ready


def test_api_documents_lists_the_library(client):
    documents = client.get("/api/documents").json()["documents"]
    assert set(documents) == {"doc.rst", "other.rst", "sub/deep.rst"}


def test_list_can_be_requested_over_the_socket(client, tmp_path):
    with connect(client, headers={"origin": ORIGIN}) as ws:
        ws.receive_json()  # the entry document
        (tmp_path / "added.rst").write_text("Added\n=====\n")
        ws.send_json({"type": "list"})

        # A file event may arrive first; keep reading until the listing does.
        for _ in range(5):
            message = ws.receive_json()
            if message["type"] == "list":
                assert "added.rst" in message["documents"]
                return
        raise AssertionError("no listing received")


def test_api_browse_lists_a_directory(client):
    data = client.get("/api/browse").json()
    assert data["path"] == ""
    assert {e["name"] for e in data["entries"]} == {"sub", "doc.rst", "other.rst"}


def test_api_browse_honours_the_filters(client, tmp_path):
    (tmp_path / "notes.md").write_text("x")
    plain = {e["name"] for e in client.get("/api/browse").json()["entries"]}
    everything = {e["name"] for e in client.get("/api/browse", params={"all": "1"}).json()["entries"]}
    assert "notes.md" not in plain
    assert "notes.md" in everything


def test_api_browse_refuses_an_escaping_path(client):
    assert client.get("/api/browse", params={"path": "../.."}).status_code == 404


def test_api_locate_resolves_a_pasted_path(client, tmp_path):
    data = client.get("/api/locate", params={"path": str(tmp_path / "sub" / "deep.rst")}).json()
    assert data == {"path": "sub/deep.rst", "kind": "doc"}


def test_api_locate_refuses_a_path_outside_the_root(client):
    response = client.get("/api/locate", params={"path": "/etc/passwd"})
    assert response.status_code == 404
    assert "outside the document root" in response.json()["message"]


def test_media_route_serves_assets_and_holds_the_boundary(tmp_path):
    """`.. image::` targets are served, and only from inside the root."""
    (tmp_path / "pic.svg").write_text("<svg xmlns='http://www.w3.org/2000/svg'/>")
    (tmp_path / "doc.rst").write_text("Title\n=====\n\n.. image:: pic.svg\n")
    (tmp_path.parent / "secret.txt").write_text("no")

    app = create_app(str(tmp_path / "doc.rst"), root=str(tmp_path))
    with TestClient(app) as client:
        assert client.get("/media/pic.svg").status_code == 200
        assert client.get("/media/../secret.txt").status_code == 404
        assert client.get("/media/nope.png").status_code == 404


def test_watcher_does_not_watch_the_whole_root(tmp_path, monkeypatch):
    """The default root on a loopback bind is the entire filesystem.

    A recursive watch of that exhausts the inotify limit and the server never
    finishes starting, so watches follow the documents that are actually
    opened instead.
    """
    from rstview import watch

    scheduled = []

    class Recorder:
        def schedule(self, handler, path, recursive=False):
            scheduled.append((path, recursive))
            return object()

        def start(self):
            pass

        def stop(self):
            pass

        def join(self, timeout=None):
            pass

    monkeypatch.setattr(watch, "Observer", Recorder)

    (tmp_path / "deep").mkdir()
    (tmp_path / "deep" / "doc.rst").write_text("Title\n=====\n")

    app = create_app(str(tmp_path / "deep" / "doc.rst"), root=str(tmp_path))
    with TestClient(app):
        pass

    assert scheduled, "nothing was watched at all"
    assert not any(recursive for _, recursive in scheduled), scheduled
    assert str(tmp_path) not in [path for path, _ in scheduled], (
        f"the root itself was watched: {scheduled}"
    )
    assert str(tmp_path / "deep") in [path for path, _ in scheduled]
