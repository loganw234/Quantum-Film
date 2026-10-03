"""Helpers for the qiskit stage: the IBM virtualenv's python (QF_IBM_PYTHON), run offline (offline.py) inside
the test's own directory, throwaway git repositories with a bare origin, and planted drivers.

The virtualenv has no pytest and nobody installs one into it (lead.md, 15:34Z), so these tests run in the
project's pytest and call the virtualenv's python as a subprocess for everything that needs qiskit. The
stage that runs them skips by name when QF_IBM_PYTHON is unset (verify/run.sh, need_env); `make test`, which
is not a verdict, skips them too.

A PLANTED DRIVER is a small script written into the test's directory: it patches one name in this package
(or in qiskit) and then runs a tool as __main__, so a fault is planted in a copy of the process, never in the
code under test.
"""
import os
import pathlib
import subprocess
import textwrap

import pytest

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PY = os.environ.get("QF_IBM_PYTHON")
OFFLINE = HERE / "offline.py"
HW_BUNDLE = ROOT / "tools" / "hw_bundle.py"
HW_RUN = ROOT / "tools" / "hw_run.py"
SHOTS = "16,64,16"            # known-answer, law, coherence: a dry run's test shots, small enough to run in seconds
NEEDS = pytest.mark.skipif(not PY, reason="QF_IBM_PYTHON is unset; verify/run.sh skips this stage by name")
# The owner's machine is shared (the coordinator, 2026-10-03): every simulation is capped, and runs one at a time
# (these tests run their venv processes one after another).
CAPS = {"OMP_NUM_THREADS": "2", "OPENBLAS_NUM_THREADS": "1", "MKL_NUM_THREADS": "1", "QISKIT_IN_PARALLEL": "FALSE"}


def venv(script, *args, root, env=None, timeout=1500):
    """Run a script in the virtualenv, offline, writing only under `root`, its threads capped. -> CompletedProcess."""
    root = pathlib.Path(root)
    (root / "tmp").mkdir(parents=True, exist_ok=True)
    e = dict(os.environ)
    e.update(QF_TEST_ROOT=str(root), PYTHONNOUSERSITE="1", PYTHONDONTWRITEBYTECODE="1", PYTHONIOENCODING="utf-8",
             QISKIT_SETTINGS=str(root / "no-such-settings.conf"), TEMP=str(root / "tmp"), TMP=str(root / "tmp"),
             **CAPS)
    e.update(env or {})
    return subprocess.run([PY, str(OFFLINE), str(script), *map(str, args)], cwd=ROOT, env=e, capture_output=True,
                          stdin=subprocess.DEVNULL, text=True, timeout=timeout)


def out(p):
    """A run's stdout and stderr, with the offline guard's harmless events left out."""
    return p.stdout + "\n".join(ln for ln in p.stderr.splitlines() if not ln.startswith("[offline] process"))


def blocked_network(p):
    return [ln for ln in p.stderr.splitlines() if ln.startswith("[offline] BLOCKED socket.")
            and "socket.bind" not in ln]


def git(args, cwd):
    p = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    assert p.returncode == 0, f"git {args}: {p.stderr}"
    return p.stdout.strip()


def make_repo(top):
    """A work tree `top/work` with a bare origin `top/origin.git`, LF kept as written. -> the work tree."""
    top = pathlib.Path(top)
    top.mkdir(parents=True, exist_ok=True)
    git(["init", "-q", "--bare", "origin.git"], top)
    work = top / "work"
    work.mkdir()
    for args in (["init", "-q", "-b", "main"], ["config", "user.email", "dry-run@example.invalid"],
                 ["config", "user.name", "dry run"], ["config", "core.autocrlf", "false"],
                 ["config", "commit.gpgsign", "false"], ["remote", "add", "origin", "../origin.git"]):
        git(args, work)
    (work / ".gitattributes").write_text("* -text\n")
    git(["add", ".gitattributes"], work)
    git(["commit", "-q", "-m", "a throwaway repository"], work)
    git(["push", "-q", "origin", "main"], work)
    return work


def commit_push(work, message, *paths):
    git(["add", "--", *map(str, paths)], work)
    git(["commit", "-q", "-m", message], work)
    git(["push", "-q", "origin", "main"], work)


def freeze(root, out_dir, *extra, shots=SHOTS, env=None):
    args = ["--route", "ibm-direct", "--out", out_dir, *extra]
    if shots:
        args += ["--shots-for-tests", shots]
    return venv(HW_BUNDLE, *args, root=root, env=env)


def dry(root, bundle_dir, job, out_dir, *extra, driver=None, env=None):
    """hw_run.py --dry-run, or a planted driver that runs it."""
    args = ["--bundle", bundle_dir, "--job", job, "--out", out_dir, "--dry-run", *extra]
    return venv(driver or HW_RUN, *args, root=root, env=env)


def driver(root, name, patch, tool=HW_RUN):
    """A planted driver: `patch` (Python source, run first) and then `tool` as __main__ with this argv."""
    path = pathlib.Path(root) / f"plant_{name}.py"
    path.write_text(textwrap.dedent(f"""\
        import runpy
        import sys
        sys.path.insert(0, {str(ROOT)!r})
        """) + textwrap.dedent(patch) + textwrap.dedent(f"""
        sys.argv = [{str(tool)!r}, *sys.argv[1:]]
        runpy.run_path({str(tool)!r}, run_name="__main__")
        """), encoding="utf-8")
    return path


def script(root, name, source):
    """A one-off script in the test's directory, run in the virtualenv with the repository importable."""
    path = pathlib.Path(root) / f"{name}.py"
    path.write_text(f"import sys\nsys.path.insert(0, {str(ROOT)!r})\n" + textwrap.dedent(source), encoding="utf-8")
    return path
