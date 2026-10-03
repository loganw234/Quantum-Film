"""Device runs (round 3): every shot of one circuit in one hardware job, in one record, with a
commitment (v3) that binds the route, the backend and the exact circuit the device ran."""
import copy
import hashlib

import pytest

from quantum_film import fixer
from quantum_film.ibm import decode

CIRCUIT = hashlib.sha256(b"OPENQASM 2.0; a stand-in logical circuit").hexdigest()
ISA = hashlib.sha256(b"OPENQASM 3.0; a stand-in transpiled circuit").hexdigest()
SALT = hashlib.sha256(b"a stand-in salt").hexdigest()
OPTIONS = {"dynamical_decoupling": False, "twirling_gates": False, "twirling_measure": False}
JOB = "d3stand1n0job"
Z = "Z" * 16
# Noise included: a two-crystal outcome is a device's record too, and is kept.
COUNTS = [[[0, 1, 4, 11, 13], 3], [[0, 1, 4, 11, 14], 1], [[2, 5], 2]]


def source(role="law", basis=Z, **over):
    s = {"kind": "qpu", "route": "ibm-direct", "backend": "ibm_kingston", "program": "sampler", "job_id": JOB,
         "circuit_sha256": CIRCUIT, "isa_sha256": ISA, "shots": 6, "options": OPTIONS,
         "options_sha256": fixer.options_digest(OPTIONS), "decode": decode.DECODE, "salt": SALT,
         "submitted_at": "2026-10-03T18:00:00Z", "fixed_at": "2026-10-03T18:05:00Z"}
    s["commitment"] = fixer.commitment_v3(stock="pauli-4x4", role=role, basis=basis,
                                          **{k: s[k] for k in fixer.RUN_COMMITTED})
    s.update(over)
    return s


@pytest.fixture
def run():
    return fixer.fix_run("pauli-4x4", "law", Z, COUNTS, source())


def resealed(rec):
    rec["digest"] = fixer.digest(rec)
    return rec


def refused(rec, needle):
    problems = fixer.check(rec)
    assert any(needle in p for p in problems), problems


def test_a_complete_run_is_fixed_and_checks(run):
    assert fixer.check(run) == [] == fixer.check_run(run)
    assert run["format"] == fixer.RUN_FORMAT and run["law"]["M"] == 16


def test_the_commitment_is_the_documented_hash():
    """Spelled out by hand, not through golden.uniform.stream: each field length-prefixed and
    type-tagged, joined by '|', in the order commitment_v3 names them."""
    msg = ("s26:quantum-film/commitment/v3|s9:pauli-4x4|s3:law|s16:" + Z + "|s10:ibm-direct|s12:ibm_kingston"
           "|s7:sampler|s64:" + CIRCUIT + "|s64:" + ISA + "|i6|s64:" + fixer.options_digest(OPTIONS)
           + "|s26:quantum_film.ibm.decode/v1|s64:" + SALT)
    assert source()["commitment"] == hashlib.sha256(msg.encode()).hexdigest()


@pytest.mark.parametrize("field, value", [
    ("route", "moth"), ("backend", "ibm_fez"), ("program", "executor"), ("circuit_sha256", ISA),
    ("isa_sha256", CIRCUIT), ("decode", "quantum_film.atlas.decode/v1"), ("salt", CIRCUIT)])
def test_the_commitment_binds_every_field_known_at_submission(run, field, value):
    bad = copy.deepcopy(run)
    bad["source"][field] = value
    refused(resealed(bad), "the commitment does not bind")


def test_the_commitment_binds_the_role_basis_and_options(run):
    bad = copy.deepcopy(run)
    bad["role"] = "known-answer"                       # a Z run either way: only the commitment can tell
    refused(resealed(bad), "the commitment does not bind")
    bad = copy.deepcopy(run)
    bad["source"]["options"] = dict(OPTIONS, dynamical_decoupling=True)
    refused(resealed(bad), "options_sha256 is not the digest")
    bad["source"]["options_sha256"] = fixer.options_digest(bad["source"]["options"])
    refused(resealed(bad), "the commitment does not bind")


def test_a_record_alone_cannot_prove_its_commitment_came_first(run):
    """The salt is in the record, so a changed field can be re-sealed with its commitment recomputed,
    and `check` passes it. What binds a run is its anchor: the commitment committed to git before
    any result was read (fixer.py, CLAUDE.md). This states the limit; it does not close it."""
    moved = copy.deepcopy(run)
    moved["source"]["backend"] = "ibm_fez"
    s = moved["source"]
    s["commitment"] = fixer.commitment_v3(stock="pauli-4x4", role="law", basis=Z,
                                          **{k: s[k] for k in fixer.RUN_COMMITTED})
    assert fixer.check(resealed(moved)) == []


@pytest.mark.parametrize("counts, needle", [
    ([], "a non-empty list"),
    ([[[2, 5], 2], [[0, 1, 4, 11, 13], 3], [[0, 1, 4, 11, 14], 1]], "canonical order"),
    ([[[0, 1, 4, 11, 13], 3], [[0, 1, 4, 11, 13], 1], [[2, 5], 2]], "canonical order"),
    ([[[0, 1, 4, 11, 13], 3], [[0, 1, 4, 11, 14], 0], [[2, 5], 3]], "at least 1"),
    ([[[0, 1, 4, 11, 13], 3], [[0, 1, 4, 11, 14], 1], [[2, 5], 3]], "7 shots counted where the run took 6"),
    ([[[0, 1, 4, 11, 16], 3], [[0, 1, 4, 11, 14], 1], [[2, 5], 2]], "a qubit outside 0..15"),
    ([[[0, 4, 1, 11, 13], 3], [[0, 1, 4, 11, 14], 1], [[2, 5], 2]], "strictly increasing"),
    ([[[0, 1, 4, 11, 13], 3, 1], [[2, 5], 3]], "not an [ones, occurrences] pair"),
    ([[[0, 1, 4, 11, 13], True], [[2, 5], 5]], "at least 1"),
])
def test_counts_are_canonical_whole_and_sum_to_the_shots(run, counts, needle):
    bad = copy.deepcopy(run)
    bad["counts"] = counts
    refused(resealed(bad), needle)


@pytest.mark.parametrize("role, basis, needle", [
    ("law", "X" + "Z" * 15, "a law run is read in Z on every qubit"),
    ("known-answer", "Y" + "Z" * 15, "a known-answer run is read in Z on every qubit"),
    ("coherence", Z, "reads at least one qubit out of Z"),
    ("law", "Z" * 15, "one of X, Y or Z for each of the 16 qubits"),
    ("law", "Z" * 15 + "W", "one of X, Y or Z for each of the 16 qubits"),
    ("film", Z, "role: must be one of"),
])
def test_role_and_basis_are_refused_by_name(run, role, basis, needle):
    bad = copy.deepcopy(run)
    bad["role"], bad["basis"] = role, basis
    refused(resealed(bad), needle)


def test_a_coherence_run_reads_its_pair_out_of_z():
    basis = "XX" + "Z" * 14
    rec = fixer.fix_run("pauli-4x4", "coherence", basis, COUNTS, source(role="coherence", basis=basis))
    assert fixer.check(rec) == []


@pytest.mark.parametrize("field, value, needle", [
    ("kind", "atlas-emu", "a device run's kind is one of"),
    ("route", "atlas", "route must be one of"),
    ("backend", "IBM_Fez", "backend must be a lowercase name"),
    ("program", "", "program must be a lowercase name"),
    ("job_id", "../d3stand1n0job", "job_id must be a provider's job id"),
    ("isa_sha256", ISA.upper(), "isa_sha256 must be 64 lowercase hex digits"),
    ("options_sha256", "0" * 63, "options_sha256 must be 64 lowercase hex digits"),
    ("shots", True, "must carry shots (int)"),
    ("options", [], "must carry options (dict)"),
    ("fixed_at", "2026-10-03T17:59:59Z", "fixed_at comes before submitted_at"),
    ("submitted_at", "2026-13-03T18:00:00Z", "submitted_at must be a UTC time"),
    ("decode", "", "decode must name the rule"),
])
def test_the_source_is_refused_by_name(run, field, value, needle):
    bad = copy.deepcopy(run)
    bad["source"][field] = value
    refused(resealed(bad), needle)


def test_unknown_and_missing_fields_are_refused(run):
    bad = copy.deepcopy(run)
    bad["source"]["calibration_note"] = "rides unchecked"
    refused(resealed(bad), "fields the fixer does not know")
    bad = copy.deepcopy(run)
    bad["note"] = "x"
    refused(resealed(bad), "unexpected ['note']")
    bad = copy.deepcopy(run)
    del bad["basis"]
    refused(resealed(bad), "missing ['basis']")


def test_a_moved_count_or_a_changed_law_is_refused(run):
    bad = copy.deepcopy(run)
    bad["counts"][0][1], bad["counts"][1][1] = 1, 3            # same total, a count moved, the digest kept
    refused(bad, "digest: the record's bytes are not the bytes it was fixed with")
    bad = copy.deepcopy(run)
    bad["law"] = dict(bad["law"], N=6)
    refused(resealed(bad), "law the shelf no longer states")


def test_the_constructor_refuses_what_check_refuses():
    with pytest.raises(ValueError, match="the fixer refuses this device run"):
        fixer.fix_run("pauli-4x4", "law", Z, list(reversed(COUNTS)), source())


def test_the_command_line_reads_a_run_by_its_format(run, tmp_path, capsys):
    good = tmp_path / "run.json"
    good.write_text(fixer.text(run), encoding="ascii", newline="\n")
    assert fixer.main(["check", str(good)]) == 0
    assert "a law run: 6 shots, 3 distinct outcomes" in capsys.readouterr().out
    bad = copy.deepcopy(run)
    bad["counts"][2][1] = 3
    worse = tmp_path / "bad.json"
    worse.write_text(fixer.text(bad), encoding="ascii", newline="\n")
    assert fixer.main(["check", str(worse)]) == 1
