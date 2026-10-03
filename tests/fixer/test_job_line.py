"""The job line (round 3): what a runner commits and pushes after it submits a job and before it reads
any result, and the function that holds every run record of the job to it."""
import copy
import hashlib

import pytest

from quantum_film import fixer
from quantum_film.ibm import decode

ISA = [hashlib.sha256(f"stand-in transpiled circuit {i}".encode()).hexdigest() for i in range(2)]
CIRCUIT = hashlib.sha256(b"a stand-in logical circuit").hexdigest()
SALTS = [hashlib.sha256(f"stand-in salt {i}".encode()).hexdigest() for i in range(2)]
OPTIONS = {"dynamical_decoupling": {"enable": False}, "twirling": {"enable_gates": False, "enable_measure": False}}
BASES = ["XX" + "Z" * 14, "YY" + "Z" * 14]
JOB, AT = "d3stand1n0job", "2026-10-03T18:00:00.123456Z"
COUNTS = [[[0, 1], 2], [[2, 5], 1]]


def run(pub):
    s = {"kind": "qpu", "route": "ibm-direct", "backend": "ibm_kingston", "program": "sampler", "job_id": JOB,
         "pub": pub, "circuit_sha256": CIRCUIT, "isa_sha256": ISA[pub], "shots": 3, "options": OPTIONS,
         "options_sha256": fixer.options_digest(OPTIONS), "decode": decode.DECODE, "salt": SALTS[pub],
         "submitted_at": AT, "fixed_at": "2026-10-03T18:05:00Z"}
    s["commitment"] = fixer.commitment_v3(stock="pauli-4x4", role="coherence", basis=BASES[pub],
                                          **{k: s[k] for k in fixer.RUN_COMMITTED})
    return fixer.fix_run("pauli-4x4", "coherence", BASES[pub], COUNTS, s)


def line(**over):
    runs = [run(0), run(1)]
    out = {"format": fixer.JOB_FORMAT, "stock": "pauli-4x4", "kind": "qpu", "route": "ibm-direct",
           "backend": "ibm_kingston", "program": "sampler", "job_id": JOB, "submitted_at": AT,
           "bundle_sha256": hashlib.sha256(b"a stand-in manifest").hexdigest(),
           "commitments": [r["source"]["commitment"] for r in runs]}
    out.update(over)
    return out


def test_a_line_holds_every_run_of_its_job():
    assert fixer.check_job_line(line()) == []
    assert fixer.held_to_line(run(0), line()) == [] == fixer.held_to_line(run(1), line())


def test_two_runs_of_one_job_cannot_be_swapped():
    """XX and YY have the same shots; only the PUB and its commitment tell them apart."""
    swapped = line(commitments=list(reversed(line()["commitments"])))
    assert any("not the one the line committed for pub 0" in p for p in fixer.held_to_line(run(0), swapped))
    moved = copy.deepcopy(run(0))
    moved["source"]["pub"] = 1
    assert any("not the one the line committed for pub 1" in p for p in fixer.held_to_line(moved, line()))


@pytest.mark.parametrize("field, value", [
    ("job_id", "another0job"), ("backend", "ibm_fez"), ("route", "moth"), ("program", "executor"),
    ("submitted_at", "2026-10-03T18:00:01Z"), ("kind", "simulator")])
def test_a_record_that_is_not_the_lines_job_is_refused(field, value):
    rec = copy.deepcopy(run(0))
    rec["source"][field] = value
    assert any(f"the record's {field} is not the line's" in p for p in fixer.held_to_line(rec, line()))


def test_a_pub_outside_the_line_is_refused():
    rec = copy.deepcopy(run(1))
    rec["source"]["pub"] = 2
    assert "line: the record's pub is not one of the line's circuits" in fixer.held_to_line(rec, line())


@pytest.mark.parametrize("over, needle", [
    ({"format": "quantum-film/hardware-job/v0"}, "is not 'quantum-film/hardware-job/v1'"),
    ({"stock": "nope"}, "is not on the shelf"),
    ({"backend": "fake_kingston"}, "a qpu job names an IBM device"),
    ({"kind": "simulator"}, "a qpu job names an IBM device"),
    ({"job_id": "../x"}, "job_id must be a provider's job id"),
    ({"submitted_at": "2026-10-03 18:00:00Z"}, "submitted_at must be a UTC time"),
    ({"commitments": []}, "at least one commitment"),
    ({"commitments": ["0" * 63]}, "64 lowercase hex digits"),
    ({"bundle_sha256": "A" * 64}, "64 lowercase hex digits"),
    ({"commitments": ["a" * 64, "a" * 64]}, "a commitment appears twice"),
    ({"attempt": 2}, "fields it does not know"),
    ({"commitments": "a" * 64}, "must carry commitments (list)"),
])
def test_a_bad_line_is_refused_by_name(over, needle):
    problems = fixer.check_job_line(line(**over))
    assert any(needle in p for p in problems), problems
    assert fixer.held_to_line(run(0), line(**over)) == problems         # a bad line holds nothing to it

def test_a_bundles_two_jobs_each_get_one_line_and_share_no_commitment():
    """Round 3's bundle has two jobs, the known answer then the film. PUBs are numbered within each job, and
    once-only is checked over the set: no job id twice, and no commitment in two lines."""
    known = line(job_id="kn0wnanswerjob", commitments=[hashlib.sha256(b"known answer").hexdigest()])
    film = line()
    assert fixer.check_job_lines([known, film]) == []
    again = line(job_id="resubmitted0job")                      # the film's commitments, submitted a second time
    assert any("submitted twice" in p for p in fixer.check_job_lines([known, film, again]))
    assert any("has two lines" in p for p in fixer.check_job_lines([film, line()]))
    assert any(p.startswith("line 1: job line: format") for p in
               fixer.check_job_lines([known, line(format="x")]))


def test_a_line_that_is_not_an_object_or_has_wrong_types_is_refused_by_name():
    assert fixer.check_job_line("a line") == ["job line: not an object"]
    for over in ({"backend": 5}, {"program": None}, {"job_id": ["x"]}, {"submitted_at": 0}):
        field = next(iter(over))
        assert any(f"must carry {field}" in p for p in fixer.check_job_line(line(**over)))     # and no crash


@pytest.mark.parametrize("over, needle", [
    ({"kind": "emulator"}, "kind is one of"), ({"route": "atlas"}, "kind is one of"),
    ({"program": "Sampler"}, "backend and program must be lowercase names"),
    ({"backend": "ibm_simulator"}, "a qpu job names an IBM device")])
def test_a_lines_kind_route_and_names_are_held(over, needle):
    assert any(needle in p for p in fixer.check_job_line(line(**over)))


def test_a_record_without_a_source_or_of_another_stock_is_not_the_lines():
    assert fixer.held_to_line({"stock": "pauli-4x4"}, line()) == ["line: the record has no source"]
    other = copy.deepcopy(run(0))
    other["stock"] = "pauli"
    assert "line: the record's stock is not the line's" in fixer.held_to_line(other, line())


@pytest.mark.parametrize("pub", [-1, -2, True, 0.0, "0"])
def test_a_pub_that_is_not_an_index_into_the_line_is_refused(pub):
    """A negative pub would index from the end of the list, and a bool is an int: both are refused."""
    rec = copy.deepcopy(run(0))
    rec["source"]["pub"] = pub
    assert "line: the record's pub is not one of the line's circuits" in fixer.held_to_line(rec, line())
