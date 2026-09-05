import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))


@pytest.fixture
def ids():
    """Collect every node id in an AST."""
    def collect(node, acc=None):
        acc = set() if acc is None else acc
        acc.add(node["id"])
        for child in node.get("children", []):
            collect(child, acc)
        return acc
    return collect


@pytest.fixture
def find():
    """First node of a given type, depth-first."""
    def search(node, type_):
        if node.get("type") == type_:
            return node
        for child in node.get("children", []):
            hit = search(child, type_)
            if hit is not None:
                return hit
        return None
    return search


@pytest.fixture
def find_all():
    def search(node, type_, out=None):
        out = [] if out is None else out
        if node.get("type") == type_:
            out.append(node)
        for child in node.get("children", []):
            search(child, type_, out)
        return out
    return search
