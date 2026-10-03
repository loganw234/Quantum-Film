"""Device runs (round 3): every shot of one circuit in one hardware job, in one record, with a
commitment (v3) that binds the kind, the route, the backend, the job's PUB and the exact circuit."""
import copy
import hashlib
import random

import pytest

from quantum_film import fixer
from quantum_film.ibm import decode

CIRCUIT = hashlib.sha256(b"OPENQASM 2.0; a stand-in logical circuit").hexdigest()
ISA = hashlib.sha256(b"OPENQASM 3.0; a stand-in transpiled circuit").hexdigest()
SALT = hashlib.sha256(b"a stand-in salt").hexdigest()
# The options AS SENT: exactly what the legacy SamplerV2 puts in its payload (verifier-P0, round 3).
OPTIONS = {"dynamical_decoupling": {"enable": False}, "twirling": {"enable_gates": False, "enable_measure": False}}
# The options' canonical JSON, spelled out by hand: sorted keys, no whitespace, ASCII.
OPTIONS_JSON = b'{"dynamical_decoupling":{"enable":false},"twirling":{"enable_gates":false,"enable_measure":false}}'
JOB = "d3stand1n0job"
Z = "Z" * 16
# Noise included: a two-crystal outcome is a device's record too, and is kept.
COUNTS = [[[0, 1, 4, 11, 13], 3], [[0, 1, 4, 11, 14], 1], [[2, 5], 2]]


def source(role="law", basis=Z, **over):
    s = {"kind": "qpu", "route": "ibm-direct", "backend": "ibm_kingston", "program": "sampler", "job_id": JOB,
         "pub": 0, "circuit_sha256": CIRCUIT, "isa_sha256": ISA, "shots": 6, "options": OPTIONS,
         "options_sha256": fixer.options_digest(OPTIONS), "decode": decode.DECODE, "salt": SALT,
         "submitted_at": "2026-10-03T18:00:00Z", "fixed_at": "2026-10-03T18:05:00Z"}
    s.update(over)
    s["commitment"] = fixer.commitment_v3(stock="pauli-4x4", role=role, basis=basis,
                                          **{k: s[k] for k in fixer.RUN_COMMITTED})
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


def test_the_options_digest_is_the_documented_hash():
    assert fixer.options_digest(OPTIONS) == hashlib.sha256(OPTIONS_JSON).hexdigest()
    shuffled = {"twirling": {"enable_measure": False, "enable_gates": False}, "dynamical_decoupling": {"enable": False}}
    assert fixer.options_digest(shuffled) == fixer.options_digest(OPTIONS)         # key order is not part of it


def test_the_commitment_is_the_documented_hash():
    """Spelled out by hand, not through golden.uniform.stream or options_digest: each field
    length-prefixed and type-tagged, joined by '|', in the order commitment_v3 names them."""
    msg = ("s26:quantum-film/commitment/v3|s9:pauli-4x4|s3:law|s16:" + Z + "|s3:qpu|s10:ibm-direct"
           "|s12:ibm_kingston|s7:sampler|i0|s64:" + CIRCUIT + "|s64:" + ISA + "|i6|s64:"
           + hashlib.sha256(OPTIONS_JSON).hexdigest() + "|s26:quantum_film.ibm.decode/v1|s64:" + SALT)
    assert source()["commitment"] == hashlib.sha256(msg.encode()).hexdigest()


def test_the_commitment_changes_with_every_field_it_binds():
    base = dict(stock="pauli-4x4", role="law", basis=Z, **{k: source()[k] for k in fixer.RUN_COMMITTED})
    other = {"stock": "pauli", "role": "known-answer", "basis": "X" + Z[1:], "kind": "simulator",
             "route": "moth", "backend": "ibm_fez", "program": "executor", "pub": 1, "circuit_sha256": ISA,
             "isa_sha256": CIRCUIT, "shots": 7, "options_sha256": SALT, "decode": "x", "salt": CIRCUIT}
    assert set(other) == set(base)
    for field, value in other.items():
        assert fixer.commitment_v3(**dict(base, **{field: value})) != fixer.commitment_v3(**base), field


@pytest.mark.parametrize("field, value", [
    ("route", "moth"), ("backend", "ibm_fez"), ("program", "executor"), ("pub", 1), ("circuit_sha256", ISA),
    ("isa_sha256", CIRCUIT), ("salt", CIRCUIT)])
def test_a_record_is_held_to_its_commitment(run, field, value):
    bad = copy.deepcopy(run)
    bad["source"][field] = value
    refused(resealed(bad), "the commitment does not bind")


def test_the_commitment_binds_the_role_kind_and_options(run):
    bad = copy.deepcopy(run)
    bad["role"] = "known-answer"                       # a Z run either way: only the commitment can tell
    refused(resealed(bad), "the commitment does not bind")
    bad = copy.deepcopy(run)
    bad["source"]["kind"], bad["source"]["backend"] = "simulator", "fake_kingston"
    refused(resealed(bad), "the commitment does not bind")
    bad = copy.deepcopy(run)
    bad["source"]["options"] = dict(OPTIONS, dynamical_decoupling={"enable": True})
    refused(resealed(bad), "options_sha256 is not the digest")
    bad["source"]["options_sha256"] = fixer.options_digest(bad["source"]["options"])
    refused(resealed(bad), "the commitment does not bind")


def test_a_record_alone_cannot_prove_its_commitment_came_first(run):
    """The salt is in the record, so a changed field can be re-sealed with its commitment recomputed,
    and `check` passes it. What binds a run is its job line, committed and pushed before any result
    was read (held_to_line). This states the limit of the record alone; it does not close it."""
    moved = copy.deepcopy(run)
    moved["source"]["backend"] = "ibm_fez"
    s = moved["source"]
    s["commitment"] = fixer.commitment_v3(stock="pauli-4x4", role="law", basis=Z,
                                          **{k: s[k] for k in fixer.RUN_COMMITTED})
    assert fixer.check(resealed(moved)) == []


def test_a_simulator_is_never_a_qpu():
    """A dry run on a fake backend is kind simulator; a qpu run must name an IBM device (verifier-P0 1c)."""
    sim = fixer.fix_run("pauli-4x4", "law", Z, COUNTS, source(kind="simulator", backend="fake_kingston"))
    assert fixer.check(sim) == [] and sim["source"]["kind"] == "simulator"
    for backend in ("fake_kingston", "aer_simulator", "statevector", "fake_ibm_kingston", "ibm_kingston_sim",
                    "ibm_simulator", "ibm_fake", "ibm_aer", "ibm_qasm", "ibm_dryrun", "ibm_k1", "ibm_", "ibm_torino"):
        with pytest.raises(ValueError, match="a qpu run's backend must be an IBM device"):
            fixer.fix_run("pauli-4x4", "law", Z, COUNTS, source(backend=backend))
    with pytest.raises(ValueError, match="a simulator run may not name an IBM device"):
        fixer.fix_run("pauli-4x4", "law", Z, COUNTS, source(kind="simulator", backend="ibm_fez"))


@pytest.mark.parametrize("counts, needle", [
    ([], "a non-empty list"),
    ([[[2, 5], 2], [[0, 1, 4, 11, 13], 3], [[0, 1, 4, 11, 14], 1]], "canonical order"),
    ([[[0, 1, 4, 11, 13], 3], [[0, 1, 4, 11, 13], 1], [[2, 5], 2]], "canonical order"),
    ([[[0, 1, 4, 11, 13], 3], [[0, 1, 4, 11, 14], 0], [[2, 5], 3]], "at least 1"),
    ([[[0, 1, 4, 11, 13], 3], [[0, 1, 4, 11, 14], 1], [[2, 5], 3]], "7 shots counted where the run took 6"),
    ([[[0, 1, 4, 11, 16], 3], [[0, 1, 4, 11, 14], 1], [[2, 5], 2]], "a qubit outside 0..15"),
    ([[[0, 4, 1, 11, 13], 3], [[0, 1, 4, 11, 14], 1], [[2, 5], 2]], "strictly increasing"),
    ([[[0, 0, 4, 11, 13], 3], [[0, 1, 4, 11, 14], 1], [[2, 5], 2]], "strictly increasing"),
    ([[[0, True, 4, 11, 13], 3], [[0, 1, 4, 11, 14], 1], [[2, 5], 2]], "ones is not a list of integers"),
    ([["0,1,4,11,13", 3], [[0, 1, 4, 11, 14], 1], [[2, 5], 2]], "ones is not a list of integers"),
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
    ("law", "z" * 16, "one of X, Y or Z for each of the 16 qubits"),
    ("film", Z, "role: must be one of"),
])
def test_role_and_basis_are_refused_by_name(run, role, basis, needle):
    bad = copy.deepcopy(run)
    bad["role"], bad["basis"] = role, basis
    refused(resealed(bad), needle)


def test_the_basis_names_qubit_0_first():
    """basis[q] is qubit q: "XX" then fourteen Z reads qubits 0 and 1 in X. The other end is another
    run, held apart by the commitment, which binds the basis."""
    first, last = "XX" + "Z" * 14, "Z" * 14 + "XX"
    a = fixer.fix_run("pauli-4x4", "coherence", first, COUNTS, source(role="coherence", basis=first))
    swapped = copy.deepcopy(a)
    swapped["basis"] = last
    refused(resealed(swapped), "the commitment does not bind")


@pytest.mark.parametrize("field, value, needle", [
    ("kind", "atlas-emu", "a device run's kind is one of"),
    ("route", "atlas", "route must be one of"),
    ("backend", "IBM_Fez", "backend must be a lowercase name"),
    ("program", "", "program must be a lowercase name"),
    ("job_id", "../d3stand1n0job", "job_id must be a provider's job id"),
    ("pub", -1, "pub is the circuit's index in its job"),
    ("pub", True, "must carry pub (int)"),
    ("isa_sha256", ISA.upper(), "isa_sha256 must be 64 lowercase hex digits"),
    ("options_sha256", "0" * 63, "options_sha256 must be 64 lowercase hex digits"),
    ("shots", True, "must carry shots (int)"),
    ("shots", 0, "shots must be positive"),
    ("options", [], "must carry options (dict)"),
    ("fixed_at", "2026-10-03T17:59:59Z", "fixed_at comes before submitted_at"),
    ("submitted_at", "2026-13-03T18:00:00Z", "submitted_at must be a UTC time"),
    ("decode", "", "decode must name a rule this package reads"),
    ("decode", "plain order", "decode must name a rule this package reads"),
    ("decode", "\ud800", "decode must name a rule this package reads"),
    ("decode", "quantum_film.atlas.decode/v1", "decode must name a rule this package reads"),
    ("kind", "emulator", "a device run's kind is one of"),
])
def test_the_source_is_refused_by_name(run, field, value, needle):
    bad = copy.deepcopy(run)
    bad["source"][field] = value
    refused(resealed(bad), needle)


def test_the_time_order_counts_a_fraction_of_a_second(run):
    late = copy.deepcopy(run)
    late["source"]["submitted_at"], late["source"]["fixed_at"] = "2026-10-03T18:00:00.900Z", "2026-10-03T18:00:00.100Z"
    refused(resealed(late), "fixed_at comes before submitted_at")
    ok = copy.deepcopy(run)
    ok["source"]["submitted_at"], ok["source"]["fixed_at"] = "2026-10-03T18:00:00.100Z", "2026-10-03T18:00:00.9Z"
    assert "fixed_at comes before submitted_at" not in " ".join(fixer.check(resealed(ok)))


@pytest.mark.parametrize("options, unstated", [
    ({"dynamical_decoupling": {"enable": False}, "twirling": {"enable_gates": False}}, "['twirling.enable_measure']"),
    ({}, "['dynamical_decoupling.enable', 'twirling.enable_gates', 'twirling.enable_measure']"),
    (dict(OPTIONS, dynamical_decoupling={"enable": "no"}), "['dynamical_decoupling.enable']"),
    # the flat stand-in an earlier version of these tests used: what neither sampler sends is refused
    ({"dynamical_decoupling": False, "twirling_gates": False, "twirling_measure": False},
     "['dynamical_decoupling.enable', 'twirling.enable_gates', 'twirling.enable_measure']"),
])
def test_the_options_must_state_decoupling_and_twirling(options, unstated):
    with pytest.raises(ValueError) as refusal:
        fixer.fix_run("pauli-4x4", "law", Z, COUNTS, source(options=options,
                                                            options_sha256=fixer.options_digest(options)))
    assert f"the options as sent must state {unstated}" in str(refusal.value)


def test_options_stated_true_are_kept_as_stated():
    stated_on = dict(OPTIONS, dynamical_decoupling={"enable": True})    # stated, so the record says it plainly
    rec = fixer.fix_run("pauli-4x4", "law", Z, COUNTS, source(options=stated_on,
                                                              options_sha256=fixer.options_digest(stated_on)))
    assert fixer.check(rec) == [] and rec["source"]["options"]["dynamical_decoupling"]["enable"] is True


def test_unknown_missing_and_misshapen_fields_are_refused(run):
    bad = copy.deepcopy(run)
    bad["source"]["calibration_note"] = "rides unchecked"
    refused(resealed(bad), "fields the fixer does not know")
    bad = copy.deepcopy(run)
    bad["note"] = "x"
    refused(resealed(bad), "unexpected ['note']")
    bad = copy.deepcopy(run)
    del bad["basis"]
    refused(resealed(bad), "missing ['basis']")
    bad = copy.deepcopy(run)
    bad["stock"] = "speckle-4x4"
    refused(resealed(bad), "is not on the shelf")
    bad = copy.deepcopy(run)
    bad["source"] = []
    refused(resealed(bad), "source: not an object")
    for code in ({"quantum_film": 1}, {"quantum_film": "0.1", "numpy": "2"}, {}):
        bad = copy.deepcopy(run)
        bad["code"] = code
        refused(resealed(bad), 'code: exactly {"quantum_film"')


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


def test_the_reader_feeds_the_fixer():
    """decode.tally then decode.canonical is a run's counts, on any multiset of outcomes."""
    rng = random.Random(20261003)
    for _ in range(50):
        shots = ["".join(rng.choice("01") for _ in range(16)) for _ in range(rng.randint(1, 200))]
        counts = decode.canonical(decode.tally(shots, 16))
        rec = fixer.fix_run("pauli-4x4", "law", Z, counts, source(shots=len(shots)))
        assert fixer.check(rec) == [] and sum(n for _, n in rec["counts"]) == len(shots)


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

def test_a_qpu_names_one_of_the_nine_devices_online_on_2026_10_01():
    """A list of real names (quantum.cloud.ibm.com/computers, 2026-10-01), not a shape: the owner's three
    Heron r2 devices and the six others IBM listed, which Moth's account may reach."""
    assert fixer.IBM_DEVICES == ("ibm_aachen", "ibm_berlin", "ibm_boston", "ibm_fez", "ibm_kingston",
                                 "ibm_marrakesh", "ibm_miami", "ibm_phoenix", "ibm_pittsburgh")
    for backend in fixer.IBM_DEVICES:
        assert fixer.check(fixer.fix_run("pauli-4x4", "law", Z, COUNTS, source(backend=backend))) == []


@pytest.mark.parametrize("field, value", [("shots", "6"), ("pub", "0"), ("backend", 5), ("job_id", ["x"]),
                                          ("options", None), ("salt", 0)])
def test_a_field_of_the_wrong_type_is_refused_by_name_not_by_a_crash(run, field, value):
    """The early return after the type checks: without it a string shots or pub, an int backend or a list
    job_id raised TypeError inside the checks that follow (verifier-P0's confirming pass)."""
    bad = copy.deepcopy(run)
    bad["source"][field] = value
    refused(resealed(bad), f"must carry {field}")


def test_a_file_nested_too_deep_is_refused_not_crashed(run, tmp_path):
    deep = tmp_path / "deep.json"
    text = fixer.text(run)
    nested = '"options": {"x": ' + "[" * 100000 + "]" * 100000 + ", "
    deep.write_bytes(text.replace('"options": {', nested, 1).encode("ascii"))
    rec, problems = fixer.check_file(deep)
    assert rec is None and problems and problems[0].startswith("unreadable: RecursionError")


def test_the_kinds_and_the_decode_rules_are_exactly_these():
    """Pinned: a third kind, or the Atlas rule among a run's decode rules, would pass the cases above unseen."""
    assert fixer.RUN_KINDS == ("qpu", "simulator")
    assert fixer.RUN_DECODES == (decode.DECODE,)


def test_the_time_order_counts_microseconds(run):
    bad = copy.deepcopy(run)
    bad["source"]["submitted_at"] = "2026-10-03T18:00:00.000002Z"
    bad["source"]["fixed_at"] = "2026-10-03T18:00:00.000001Z"
    refused(resealed(bad), "fixed_at comes before submitted_at")


def test_an_option_stated_as_a_number_is_not_stated():
    options = {"dynamical_decoupling": {"enable": 1}, "twirling": {"enable_gates": False, "enable_measure": 0}}
    with pytest.raises(ValueError) as refusal:
        fixer.fix_run("pauli-4x4", "law", Z, COUNTS,
                      source(options=options, options_sha256=fixer.options_digest(options)))
    assert "['dynamical_decoupling.enable', 'twirling.enable_measure']" in str(refusal.value)
