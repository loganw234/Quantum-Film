"""The Atlas client's two refusals, held offline (CLAUDE.md trap 4).

The key goes to api.mothquantum.com and nowhere else, and the key file never
lives inside the tree. Both refusals were right when the P0 verifier probed
them, but no test held either (verifier-P0 8g). Nothing here reaches the
network: curl is replaced by a stand-in that records the command line, so a
refused call is one that never reached it.
"""
import pathlib
import subprocess

import pytest

from quantum_film.atlas import client


class Curl:
    """Stands in for System32's curl.exe: records each command, answers 200."""

    def __init__(self):
        self.commands = []

    def __call__(self, cmd, **_kw):
        self.commands.append(cmd)
        out = pathlib.Path(cmd[cmd.index("-o") + 1])
        out.write_text('{"ok": true}', encoding="utf-8")
        return subprocess.CompletedProcess(cmd, 0, stdout="200", stderr="")


@pytest.fixture
def curl(monkeypatch, tmp_path_factory):
    stand_in = Curl()
    monkeypatch.setattr(client.subprocess, "run", stand_in)
    key = tmp_path_factory.mktemp("outside") / "auth.hdr"
    key.write_text("Authorization: Bearer not-a-key\n", encoding="utf-8")
    monkeypatch.setenv("QF_ATLAS_AUTH", str(key))
    return stand_in


def test_a_path_on_the_api_host_is_sent_with_the_key(curl):
    """The positive twin: a refusal that refused everything would pass the rest."""
    assert client.call("GET", "/api/v1/me", save=False) == (200, {"ok": True})
    (cmd,) = curl.commands
    assert cmd[-1] == "https://api.mothquantum.com/api/v1/me" and "-H" in cmd


@pytest.mark.parametrize("url", ["https://evil.example/api/v1/me", "//evil.example/api/v1/me",
                                 "https://api.mothquantum.com@evil.example/", "https://api.mothquantum.com.evil.example/",
                                 "http://api.mothquantum.com:8080/", "http://api.mothquantum.com/api/v1/me"])
def test_any_other_host_is_refused_before_curl_runs(curl, url):
    with pytest.raises(PermissionError, match="the key goes nowhere else"):
        client.call("GET", url, save=False)
    assert curl.commands == []


def test_a_key_file_inside_the_tree_is_refused(curl, monkeypatch):
    for inside in (client.REPO / "auth.hdr", client.REPO / "tests" / ".." / "auth.hdr",
                   pathlib.Path(str(client.REPO / "auth.hdr").upper())):
        monkeypatch.setenv("QF_ATLAS_AUTH", str(inside))
        with pytest.raises(PermissionError, match="inside the repository"):
            client.call("GET", "/api/v1/me", save=False)
    assert curl.commands == []


def test_no_key_file_named_is_refused(curl, monkeypatch):
    monkeypatch.delenv("QF_ATLAS_AUTH")
    with pytest.raises(PermissionError, match="QF_ATLAS_AUTH is not set"):
        client.call("GET", "/api/v1/me", save=False)
