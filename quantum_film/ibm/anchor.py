"""The anchor of an ibm-direct job: its line committed with git and pushed, before any result is read.

A record alone cannot prove its commitment came first (fixer.py). What binds a run is its job line,
committed and pushed after the job is submitted and before `result()` can fetch anything (docs/ROUND3.md).
This module does exactly that with git, and checks it was done:
  - `ready`: before submission, the output directory is in a git work tree on a branch whose head is
    already on origin, and the bundle is committed there unchanged, so the bundle is public before the job
    exists and the push that follows is a fast-forward;
  - `commit_and_push`: the line alone is committed (other staged changes are left out) and pushed, and the
    remote branch's head is read back with `git ls-remote` and must be the commit that holds the line;
  - `anchored`: whether a line file is in HEAD, unchanged, with HEAD on origin.
git runs with each directory as its working directory, never `git -C <path>`, and paths go to it relative to
that directory: under MSYS_NO_PATHCONV=1 git.exe cannot read a /c/... path, and two spellings of one path are
never compared (CLAUDE.md). Importing this module runs nothing.
"""
import subprocess


class AnchorError(RuntimeError):
    """The line could not be anchored, or a check of the anchor failed."""


def git(args, cwd):
    p = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, timeout=120)
    return p.returncode, p.stdout.strip(), p.stderr.strip()


def _ok(args, cwd, what):
    rc, out, err = git(args, cwd)
    if rc != 0:
        raise AnchorError(f"{what}: git {' '.join(args[:2])} failed ({err.splitlines()[-1] if err else rc})")
    return out


def branch_of(cwd):
    if _ok(["rev-parse", "--is-inside-work-tree"], cwd, "the directory is not in a git work tree") != "true":
        raise AnchorError("the directory is not in a git work tree")
    name = _ok(["rev-parse", "--abbrev-ref", "HEAD"], cwd, "no branch")
    if name == "HEAD":
        raise AnchorError("HEAD is detached: a line is pushed to a branch")
    return name


def remote_head(cwd, branch):
    out = _ok(["ls-remote", "origin", f"refs/heads/{branch}"], cwd, "origin cannot be read")
    return out.split()[0] if out else None


def ready(bundle_dir, out_dir):
    """The named reasons a job may not be submitted yet; [] when the anchor can be made."""
    try:
        branch = branch_of(out_dir)
        head = _ok(["rev-parse", "HEAD"], out_dir, "no commit")
        if remote_head(out_dir, branch) != head:
            return [f"anchor: origin's {branch} is not this HEAD; push (or pull) first, so the bundle is public "
                    "before the job exists and the line's push is a fast-forward"]
        if branch_of(bundle_dir) != branch or _ok(["rev-parse", "HEAD"], bundle_dir, "no commit") != head:
            return ["anchor: the bundle and the output directory are not in the same repository and branch"]
        if git(["ls-files", "--error-unmatch", "--", "manifest.json"], bundle_dir)[0] != 0:
            return ["anchor: the bundle's manifest is not committed"]
        if _ok(["status", "--porcelain", "--", "."], bundle_dir, "git status failed"):
            return ["anchor: the bundle has changes that are not committed"]
    except AnchorError as e:
        return [f"anchor: {e}"]
    return []


def commit_and_push(line_path, message):
    """Commit the line file alone and push it; -> the commit. AnchorError if origin does not then hold it."""
    cwd, name = line_path.parent, line_path.name
    branch = branch_of(cwd)
    _ok(["add", "--", name], cwd, "git add")
    _ok(["commit", "-m", message, "--", name], cwd, "git commit")
    head = _ok(["rev-parse", "HEAD"], cwd, "no commit")
    _ok(["push", "origin", f"HEAD:refs/heads/{branch}"], cwd, "git push")
    if remote_head(cwd, branch) != head:
        raise AnchorError(f"after the push, origin's {branch} is not the commit that holds the line")
    if not anchored(line_path):
        raise AnchorError("after the push, the line is not in the pushed commit unchanged")
    return head


def anchored(line_path):
    """Is this line file committed in HEAD, unchanged, with HEAD on origin?"""
    cwd, name = line_path.parent, line_path.name
    try:
        branch = branch_of(cwd)
        head = _ok(["rev-parse", "HEAD"], cwd, "no commit")
        prefix = _ok(["rev-parse", "--show-prefix"], cwd, "no prefix")
        if git(["cat-file", "-e", f"HEAD:{prefix}{name}"], cwd)[0] != 0:
            return False
        if _ok(["status", "--porcelain", "--", name], cwd, "git status failed"):
            return False
        return remote_head(cwd, branch) == head
    except AnchorError:
        return False
