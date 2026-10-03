"""Every committed hardware run, held from docs/records alone (quantum_film.ibm.audit): the hardware twin of
tests/circuits/test_p3_records.py. Each record to its job line, the lines as a set, circuit_sha256 and
isa_sha256 to the bundle's files, the law and coherence circuits to their source ed767c01bd4b851d, the counts
to the raw payload PUB by PUB, the known answer before the rest, and (git_order) each ibm-direct line
committed before its raw result.

It passes vacuously while docs/records holds no hardware run. The plants below put the committed fixture where
a run would be committed, and break its hash chain one link at a time: each is refused by name."""
import json
import shutil
import subprocess

import pytest
from hwfix import FIXTURE, ROOT, manifest, reseal, resealed_record

from quantum_film import fixer
from quantum_film.ibm import audit, bundle, runner

RECORDS = ROOT / "docs" / "records"


def test_every_committed_hardware_run_holds():
    found, _n = audit.audit(RECORDS, ROOT, git_order=True)
    assert found == []


def test_docs_records_holds_no_job_line_yet_so_the_test_above_is_vacuous_today():
    """Stated, not hidden: when the first hardware run is committed this count moves, and the test above holds
    it. Atlas's runs are commitments.jsonl lines, not hardware job lines, and are not read here."""
    assert [p.name for p, _ln in runner.lines_under(RECORDS)] == []


@pytest.fixture
def planted(tmp_path):
    """The fixture committed where a run would be: docs/records/<day>/ibm/{bundle, run}."""
    day = tmp_path / "docs" / "records" / "2026-10-04" / "ibm"
    shutil.copytree(FIXTURE / "bundle", day / "bundle")
    shutil.copytree(FIXTURE / "run", day / "run")
    return tmp_path / "docs" / "records", day / "bundle", day / "run"


def found_in(root):
    return audit.audit(root, ROOT)[0]


def test_the_audit_finds_and_holds_a_planted_run(planted):
    root, _b, _r = planted
    found, n = audit.audit(root, ROOT)
    assert found == [] and n == 3


def reseal_run(bdir, rdir):
    """Lines and records re-sealed to a re-sealed manifest: its new SHA-256, commitments and hashes."""
    m = manifest(bdir)
    digest = bundle.sha256((bdir / bundle.MANIFEST).read_bytes())
    for job, _cs in bundle.PLAN:
        f = runner.files(rdir, job)
        line = json.loads(f["line"].read_text())
        entries = bundle.job(m, job)["circuits"]
        line.update(bundle_sha256=digest, commitments=[e["commitment"] for e in entries])
        f["line"].write_bytes(fixer.text(line).encode("ascii"))
        for e in entries:
            resealed_record(runner.record_path(rdir, job, e), lambda r, e=e: r["source"].update(
                circuit_sha256=e["circuit_sha256"], isa_sha256=e["isa_sha256"], commitment=e["commitment"]))


def test_a_broken_hash_chain_is_refused(planted):
    root, bdir, _r = planted
    path = bdir / "law.qasm"
    path.write_bytes(path.read_bytes().replace(b"q[5]", b"q[6]", 1))
    found = found_in(root)
    assert found and all("its bundle is refused: law.qasm: its SHA-256 is not the manifest's" in p for p in found)
    assert len(found) == 3                                  # every line of that bundle names it


def test_a_chain_resealed_end_to_end_is_refused_by_the_source(planted):
    """verifier-P3's plant for hardware: q5 and q6 swapped in the committed law circuit, and then everything
    re-sealed: the manifest's hashes and commitments, its own SHA-256 in every line, every line's commitments,
    every record's hashes, commitment and digest. Only the source ed767c01 can refuse it."""
    root, bdir, rdir = planted
    path = bdir / "law.qasm"
    t = path.read_text(encoding="ascii")
    path.write_text(t.replace("q[5]", "q[@]").replace("q[6]", "q[5]").replace("q[@]", "q[6]"), encoding="ascii",
                    newline="\n")
    reseal(bdir)
    reseal_run(bdir, rdir)
    found = found_in(root)
    assert found and all(p.endswith("its bundle is refused: law[0] law: the logical circuit is not the one derived "
                                    "from the source ed767c01bd4b851d") for p in found)


def test_counts_swapped_between_pubs_are_refused_by_the_raw_payload(planted):
    """Every record intact and held to its line: only the raw payload, PUB by PUB, can see the swap."""
    root, bdir, rdir = planted
    m = manifest(bdir)
    xx, yy = (runner.record_path(rdir, "coherence", e) for e in bundle.job(m, "coherence")["circuits"])
    cx, cy = (json.loads(p.read_text())["counts"] for p in (xx, yy))
    resealed_record(xx, lambda r: r.update(counts=cy))
    resealed_record(yy, lambda r: r.update(counts=cx))
    line = json.loads(runner.files(rdir, "coherence")["line"].read_text())
    assert all(fixer.check_file(p)[1] == [] and fixer.held_to_line(fixer.check_file(p)[0], line) == []
               for p in (xx, yy))
    assert sorted(found_in(root)) == [
        "coherence-pub0-coherence-xx.json: its counts are not the raw payload's PUB 0 read through decode",
        "coherence-pub1-coherence-yy.json: its counts are not the raw payload's PUB 1 read through decode"]


def test_a_record_of_another_transpiled_circuit_is_refused(planted):
    root, bdir, rdir = planted
    m = manifest(bdir)
    e = bundle.job(m, "law")["circuits"][0]

    def change(r):
        s = r["source"]
        s["isa_sha256"] = "0" * 64
        s["commitment"] = fixer.commitment_v3(stock=r["stock"], role=r["role"], basis=r["basis"],
                                              **{k: s[k] for k in fixer.RUN_COMMITTED})
    resealed_record(runner.record_path(rdir, "law", e), change)
    found = found_in(root)
    assert "law-pub0-law.json: line: the record's commitment is not the one the line committed for pub 0" in found
    assert "law-pub0-law.json: its isa_sha256 is not the bundle's" in found


def test_a_second_line_for_the_same_commitments_is_refused(planted):
    root, _bdir, rdir = planted
    line = json.loads(runner.files(rdir, "law")["line"].read_text())
    line["job_id"] = "resubmitted0job"
    other = rdir.parent / "rerun"
    other.mkdir()
    (other / "law-line.json").write_bytes(fixer.text(line).encode("ascii"))
    assert any(p.startswith("lines: job lines: commitment") and "submitted twice" in p for p in found_in(root))


def test_the_law_and_coherence_jobs_need_a_known_answer_that_held_first(planted):
    root, bdir, rdir = planted
    m = manifest(bdir)
    e = bundle.job(m, "known-answer")["circuits"][0]
    path = runner.record_path(rdir, "known-answer", e)
    resealed_record(path, lambda r: r.update(counts=[[[3, 8, 12, 14, 15], e["shots"]]]))     # the mirror
    found = found_in(root)
    assert ("known-answer-pub0-known-answer.json: its counts are not the raw payload's PUB 0 read through decode"
            in found)
    assert "law-line.json: the bundle's known answer did not hold, or has no intact record" in found
    assert "coherence-line.json: the bundle's known answer did not hold, or has no intact record" in found
    runner.files(rdir, "known-answer")["line"].unlink()
    assert "law-line.json: the bundle's known-answer job has no line; the law job runs only after it holds" in \
        found_in(root)


def test_a_job_that_did_not_complete_has_no_result(planted):
    root, _bdir, rdir = planted
    f = runner.files(rdir, "law")
    f["status"].write_text('{"state": {"status": "Failed"}}')
    assert "law-line.json: the job did not complete (its status file), yet it has a raw result or a record" in \
        found_in(root)
    f["status"].unlink()
    f["raw"].unlink()
    assert "law-line.json: no raw result and no status file" in found_in(root)


def git(args, cwd):
    p = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    assert p.returncode == 0, p.stderr
    return p.stdout.strip()


@pytest.fixture
def repo(planted, tmp_path):
    root, _b, _r = planted
    for args in (["init", "-q", "-b", "main"], ["config", "user.email", "t@example.invalid"],
                 ["config", "user.name", "t"], ["config", "core.autocrlf", "false"],
                 ["config", "commit.gpgsign", "false"]):
        git(args, tmp_path)
    (tmp_path / ".gitattributes").write_text("* -text\n")
    return tmp_path, root


def test_git_order_an_ibm_direct_line_committed_before_its_raw_result_holds(repo):
    top, root = repo
    bundles = [p.parent.relative_to(top).as_posix() for p in root.rglob(bundle.MANIFEST)]
    git(["add", ".gitattributes", *bundles], top)
    git(["add", "--", *[str(p.relative_to(top)) for p in root.rglob("*-line.json")]], top)
    git(["commit", "-q", "-m", "the bundle and the lines"], top)
    git(["add", "docs"], top)
    git(["commit", "-q", "-m", "the results"], top)
    assert audit.audit(root, ROOT, git_order=True) == ([], 3)


def test_git_order_a_line_committed_with_its_raw_result_is_refused(repo):
    top, root = repo
    git(["add", "."], top)
    git(["commit", "-q", "-m", "everything at once"], top)
    found, _n = audit.audit(root, ROOT, git_order=True)
    assert sorted(found) == [f"{j}-line.json: the line and the raw result were committed together: the line came "
                             "no earlier" for j in ("coherence", "known-answer", "law")]


def test_git_order_an_uncommitted_run_cannot_be_read(repo):
    _top, root = repo
    found, _n = audit.audit(root, ROOT, git_order=True)
    assert len(found) == 3 and all("is not committed; the order of the anchor cannot be read" in p for p in found)
