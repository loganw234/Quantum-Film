"""Every test file is run by some stage of the runner (ParcelRound METHOD §2).

The runner's pytest stages run DIRECTORIES, so a new test file joins a stage
by where it is saved. A file saved anywhere else would be run by `make test`
and by no verdict at all, which is the silent failure this test exists for.
"""
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[2]


def staged_dirs(runner_text):
    return {pathlib.PurePosixPath(m) for m in re.findall(r"pytest-stage\.sh (tests/[A-Za-z0-9_/-]+)", runner_text)}


def orphans(root, dirs):
    """pytest collects both test_*.py and *_test.py; a registry that knew only
    the first missed the second (verifier-P0 8d)."""
    out = []
    files = set((root / "tests").rglob("test_*.py")) | set((root / "tests").rglob("*_test.py"))
    for f in sorted(files):
        rel = pathlib.PurePosixPath(f.relative_to(root).as_posix())
        if not any(d in rel.parents for d in dirs):
            out.append(str(rel))
    return out


def test_every_test_file_is_run_by_a_stage():
    dirs = staged_dirs((ROOT / "verify" / "run.sh").read_text(encoding="utf-8"))
    assert dirs, "the runner names no pytest stage directory at all"
    assert orphans(ROOT, dirs) == []


def test_a_test_file_outside_every_stage_is_caught(tmp_path):
    """Negative control: a planted test file in a directory no stage runs."""
    (tmp_path / "tests" / "golden").mkdir(parents=True)
    (tmp_path / "tests" / "stray").mkdir()
    (tmp_path / "tests" / "golden" / "test_ok.py").write_text("", encoding="utf-8")
    (tmp_path / "tests" / "stray" / "test_lost.py").write_text("", encoding="utf-8")
    (tmp_path / "tests" / "stray" / "law_test.py").write_text("", encoding="utf-8")
    dirs = staged_dirs("  bash verify/pytest-stage.sh tests/golden\n")
    assert orphans(tmp_path, dirs) == ["tests/stray/law_test.py", "tests/stray/test_lost.py"]
