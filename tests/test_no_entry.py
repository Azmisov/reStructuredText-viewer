"""Starting with no document open."""
import pytest
from starlette.testclient import TestClient

from rstview.app import create_app

ORIGIN = "http://localhost:8000"


@pytest.fixture
def root(tmp_path):
    (tmp_path / "a.rst").write_text("A\n=\n\nbody\n")
    (tmp_path / "nested").mkdir()
    (tmp_path / "nested" / "b.rst").write_text("B\n=\n\nbody\n")
    return tmp_path


@pytest.fixture
def client(root):
    app = create_app(None, allowed_origins={ORIGIN}, root=str(root))
    with TestClient(app) as client:
        yield client


def test_server_starts_without_a_document(client):
    assert client.get("/api/entry").json()["path"] is None


def test_listing_is_available_with_no_document_open(client):
    assert set(client.get("/api/documents").json()["documents"]) == {"a.rst", "nested/b.rst"}


def test_api_doc_without_a_path_reports_no_document(client):
    response = client.get("/api/doc")
    assert response.status_code == 404
    assert "no document" in response.json()["message"]


def test_ready_frame_has_a_null_entry(client, root):
    with client.websocket_connect("/ws", headers={"origin": ORIGIN}) as ws:
        ready = ws.receive_json()
        assert ready["type"] == "ready"
        assert ready["entry"] is None
        assert ready["root"] == str(root.resolve())


def test_a_document_can_be_opened_from_the_picker(client):
    with client.websocket_connect("/ws", headers={"origin": ORIGIN}) as ws:
        ws.receive_json()
        ws.send_json({"type": "open", "path": "nested/b.rst"})
        message = ws.receive_json()
        assert message["type"] == "doc"
        assert message["path"] == "nested/b.rst"


def test_containment_still_applies_with_no_entry(client):
    with client.websocket_connect("/ws", headers={"origin": ORIGIN}) as ws:
        ws.receive_json()
        ws.send_json({"type": "open", "path": "../../etc/passwd"})
        assert ws.receive_json()["type"] == "error"
