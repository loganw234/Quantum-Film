"""Every test file is run by some stage of the runner (ParcelRound METHOD §2).

The runner's pytest stages run DIRECTORIES, so a new test file joins a stage
by where it is saved. A file saved anywhere else would be run by `make test`
and by no verdict at all, which is the silent failure this test exists for.
"""
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[2]


def staged_dirs(runner_text):
    """(directory, the directories its line takes back out with --ignore=) for each pytest stage line. A stage
    `tests/compare --ignore=tests/compare/predict` does not run tests/compare/predict: read as a bare prefix it
    covered them, so deleting the predict stage would have passed unseen (verifier-P2, round 3)."""
    out, path = set(), r"tests/[A-Za-z0-9_/-]+"
    for m in re.finditer(rf"pytest-stage\.sh ({path})((?: --ignore={path})*)", runner_text):
        ignored = frozenset(map(pathlib.PurePosixPath, re.findall(rf"--ignore=({path})", m.group(2))))
        out.add((pathlib.PurePosixPath(m.group(1)), ignored))
    return out


def orphans(root, dirs):
    """pytest collects both test_*.py and *_test.py; a registry that knew only
    the first missed the second (verifier-P0 8d)."""
    out = []
    files = set((root / "tests").rglob("test_*.py")) | set((root / "tests").rglob("*_test.py"))
    for f in sorted(files):
        rel = pathlib.PurePosixPath(f.relative_to(root).as_posix())
        if not any(d in rel.parents and not any(i in rel.parents for i in ignored) for d, ignored in dirs):
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


def test_a_directory_its_stage_ignores_is_an_orphan_unless_another_stage_runs_it(tmp_path):
    """Negative control: the predict stage's line deleted, as verifier-P2 planted it (round 3)."""
    for d in ("compare", "compare/predict"):
        (tmp_path / "tests" / d).mkdir(parents=True)
    (tmp_path / "tests" / "compare" / "test_measures.py").write_text("", encoding="utf-8")
    (tmp_path / "tests" / "compare" / "predict" / "test_predict.py").write_text("", encoding="utf-8")
    compare = "  bash verify/pytest-stage.sh tests/compare --ignore=tests/compare/predict\n"
    assert orphans(tmp_path, staged_dirs(compare)) == ["tests/compare/predict/test_predict.py"]
    both = compare + "  env X=1 bash verify/pytest-stage.sh tests/compare/predict\n"
    assert orphans(tmp_path, staged_dirs(both)) == []


def clashes(root):
    """Test files that share a basename. The test directories are not packages,
    so pytest imports each test file under its bare basename: two of one name
    stop a single session over tests/ (`make test`) at collection, while each
    stage, run alone, passes. P1's test_uniform.py beside golden's did exactly
    that (P1, 2026-09-26)."""
    seen = {}
    files = set((root / "tests").rglob("test_*.py")) | set((root / "tests").rglob("*_test.py"))
    for f in sorted(files):
        seen.setdefault(f.name, []).append(f.relative_to(root).as_posix())
    return {name: paths for name, paths in seen.items() if len(paths) > 1}


def test_no_two_test_files_share_a_basename():
    assert clashes(ROOT) == {}


def test_a_basename_clash_is_caught(tmp_path):
    """Negative control: the clash P1 met, planted."""
    for d in ("golden", "pinned"):
        (tmp_path / "tests" / d).mkdir(parents=True)
        (tmp_path / "tests" / d / "test_uniform.py").write_text("", encoding="utf-8")
    (tmp_path / "tests" / "pinned" / "test_pinned_uniform.py").write_text("", encoding="utf-8")
    assert clashes(tmp_path) == {"test_uniform.py": ["tests/golden/test_uniform.py", "tests/pinned/test_uniform.py"]}
