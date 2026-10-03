"""The anchor of an ibm-direct job (quantum_film.ibm.anchor), on a throwaway git repository with a bare origin:
the bundle must be committed and pushed before a job exists, the line alone is committed and pushed, and the
push is read back from origin."""
import subprocess

import pytest

from quantum_film.ibm import anchor


def git(args, cwd):
    p = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    assert p.returncode == 0, p.stderr
    return p.stdout.strip()


@pytest.fixture
def repo(tmp_path):
    git(["init", "-q", "--bare", "origin.git"], tmp_path)
    top = tmp_path / "work"
    top.mkdir()
    for args in (["init", "-q", "-b", "main"], ["config", "user.email", "t@example.invalid"],
                 ["config", "user.name", "t"], ["config", "core.autocrlf", "false"],
                 ["config", "commit.gpgsign", "false"],
                 ["remote", "add", "origin", "../origin.git"]):
        git(args, top)
    (top / "bundle").mkdir()
    (top / "bundle" / "manifest.json").write_text("{}\n")
    (top / "run").mkdir()
    git(["add", "bundle"], top)
    git(["commit", "-q", "-m", "bundle"], top)
    git(["push", "-q", "origin", "main"], top)
    return top


def test_a_pushed_clean_bundle_is_ready(repo):
    assert anchor.ready(repo / "bundle", repo / "run") == []


def test_a_head_that_is_not_on_origin_is_not_ready(repo):
    (repo / "other.txt").write_text("x")
    git(["add", "other.txt"], repo)
    git(["commit", "-q", "-m", "local only"], repo)
    assert anchor.ready(repo / "bundle", repo / "run") == [
        "anchor: origin's main is not this HEAD; push (or pull) first, so the bundle is public before the job exists "
        "and the line's push is a fast-forward"]


def test_a_bundle_not_committed_or_changed_is_not_ready(repo):
    (repo / "bundle" / "manifest.json").write_text('{"changed": 1}\n')
    assert anchor.ready(repo / "bundle", repo / "run") == ["anchor: the bundle has changes that are not committed"]
    (repo / "fresh").mkdir()
    (repo / "fresh" / "manifest.json").write_text("{}\n")
    assert anchor.ready(repo / "fresh", repo / "run") == ["anchor: the bundle's manifest is not committed"]


def test_outside_a_work_tree_or_on_a_detached_head_is_not_ready(repo, tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    found = anchor.ready(repo / "bundle", outside)
    assert len(found) == 1 and found[0].startswith("anchor: the directory is not in a git work tree")
    git(["checkout", "-q", "--detach"], repo)
    assert anchor.ready(repo / "bundle", repo / "run") == ["anchor: HEAD is detached: a line is pushed to a branch"]


def test_the_line_alone_is_committed_and_pushed_and_read_back(repo):
    (repo / "staged.txt").write_text("staged, and not the line's")
    git(["add", "staged.txt"], repo)
    line = repo / "run" / "law-line.json"
    line.write_text('{"job_id": "x"}\n')
    assert not anchor.anchored(line)
    head = anchor.commit_and_push(line, "hardware job line: law")
    assert git(["show", "--name-only", "--format=", head], repo).splitlines() == ["run/law-line.json"]
    assert git(["ls-remote", "origin", "refs/heads/main"], repo).split()[0] == head
    assert git(["diff", "--cached", "--name-only"], repo) == "staged.txt"           # left as it was
    assert anchor.anchored(line)
    line.write_text('{"job_id": "y"}\n')
    assert not anchor.anchored(line)                                                 # changed after its commit


def test_a_line_committed_but_not_pushed_is_not_anchored(repo):
    line = repo / "run" / "law-line.json"
    line.write_text('{"job_id": "x"}\n')
    git(["add", "run/law-line.json"], repo)
    git(["commit", "-q", "-m", "not pushed"], repo)
    assert not anchor.anchored(line)


def test_a_push_that_fails_is_an_anchor_error(repo, tmp_path):
    git(["remote", "set-url", "origin", str(tmp_path / "no-such-origin.git")], repo)
    line = repo / "run" / "law-line.json"
    line.write_text('{"job_id": "x"}\n')
    with pytest.raises(anchor.AnchorError, match="git push"):
        anchor.commit_and_push(line, "hardware job line: law")
