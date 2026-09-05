"""CLI argument handling."""
import subprocess
import sys
from rstview import cli


def test_default_port_is_fixed():
    """A stable default keeps a pinned browser tab working across restarts."""
    assert cli.DEFAULT_PORT == 5686


def test_vite_command_passes_port_without_a_separator(monkeypatch, tmp_path):
    """`pnpm run dev -- --port N` forwards `--` to vite, which then ignores the
    port and silently uses its own default."""
    captured = {}

    class FakePopen:
        def __init__(self, command, cwd=None, env=None):
            captured["command"] = command
            captured["env"] = env

    client = tmp_path / "client"
    (client / "node_modules" / ".bin").mkdir(parents=True)
    (client / "package.json").write_text("{}")
    binary = client / "node_modules" / ".bin" / "vite"
    binary.write_text("")
    binary.chmod(0o755)

    monkeypatch.setattr(cli, "CLIENT_SRC", client)
    monkeypatch.setattr(cli.subprocess, "Popen", FakePopen)

    cli._start_vite(5686, 5687)

    command = captured["command"]
    assert "--" not in command, "a bare -- would be forwarded to vite as an argument"
    assert command[command.index("--port") + 1] == "5687"
    assert captured["env"]["RSTVIEW_API_PORT"] == "5686"


def test_vite_prefers_the_local_binary(monkeypatch, tmp_path):
    captured = {}

    class FakePopen:
        def __init__(self, command, cwd=None, env=None):
            captured["command"] = command

    client = tmp_path / "client"
    (client / "node_modules" / ".bin").mkdir(parents=True)
    (client / "package.json").write_text("{}")
    (client / "node_modules" / ".bin" / "vite").write_text("")

    monkeypatch.setattr(cli, "CLIENT_SRC", client)
    monkeypatch.setattr(cli.subprocess, "Popen", FakePopen)

    cli._start_vite(1, 2)
    assert captured["command"][0].endswith("node_modules/.bin/vite")


import os

import pytest


@pytest.mark.parametrize("host", ["localhost", "127.0.0.1", "::1"])
def test_loopback_defaults_to_the_whole_filesystem(host, tmp_path):
    """On loopback the server is no more exposed than the shell that started
    it, so browsing is not restricted by default."""
    doc = tmp_path / "a.rst"
    doc.write_text("A\n=\n")
    assert cli.default_root(str(doc), host) == os.path.abspath(os.sep)


def test_published_binding_narrows_the_root(tmp_path):
    """Bound where others can reach it, the default must not expose the disk."""
    doc = tmp_path / "a.rst"
    doc.write_text("A\n=\n")
    assert cli.default_root(str(doc), "0.0.0.0") == str(tmp_path.resolve())


def test_published_binding_without_a_document_uses_the_cwd():
    assert cli.default_root(None, "0.0.0.0") == os.getcwd()


def test_module_entry_point_exists():
    """The VS Code extension spawns `python -m rstview`, not the console script.

    The script is not necessarily on PATH for the interpreter the extension
    resolved, so `__main__.py` is the load-bearing entry point there.
    """
    result = subprocess.run(
        [sys.executable, "-m", "rstview", "--help"],
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert "--stdio" in result.stdout
