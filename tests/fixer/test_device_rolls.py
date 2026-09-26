"""Device rolls: provenance and a commitment the checker recomputes."""
import copy
import hashlib

import pytest

from quantum_film import fixer

CIRCUIT = hashlib.sha256(b"OPENQASM 2.0; a stand-in circuit").hexdigest()
SALT = hashlib.sha256(b"a stand-in salt").hexdigest()
JOB = "0082f37b-13cb-4b99-84d3-d9487a054c1e"


def source(stock="pauli-4x4", **over):
    s = {"kind": "atlas-emu", "fixed_at": "2026-09-25T18:00:00Z", "engine": "tomography-api-v2",
         "job_id": JOB, "circuit_sha256": CIRCUIT, "shots": 4096,
         "decode": "quantum_film.atlas.decode/v1", "salt": SALT}
    s["commitment"] = fixer.commitment(stock=stock, **{k: s[k] for k in fixer.COMMITTED})
    s.update(over)
    return s


@pytest.fixture
def roll():
    return fixer.fix_device("pauli-4x4", [0, 1, 4, 11, 13], source())


def test_a_complete_device_roll_is_fixed_and_checks(roll):
    assert fixer.check(roll) == []


def test_the_commitment_is_the_documented_hash():
    """Spelled out by hand, not through golden.uniform.stream: each field
    length-prefixed and type-tagged, joined by '|'."""
    msg = ("s26:quantum-film/commitment/v2|s9:pauli-4x4|s64:" + CIRCUIT + "|s17:tomography-api-v2|s36:" + JOB
           + "|i4096|s28:quantum_film.atlas.decode/v1|s64:" + SALT)
    assert source()["commitment"] == hashlib.sha256(msg.encode()).hexdigest()


def resealed(rec):
    rec["digest"] = fixer.digest(rec)
    return fixer.check(rec)


@pytest.mark.parametrize("field,value", [("circuit_sha256", "0" * 64), ("engine", "coin-toss-v1"),
                                          ("job_id", "another-job"), ("salt", "f" * 64), ("shots", 1024),
                                          ("decode", "plain-order")])
def test_reattributing_a_roll_breaks_its_commitment(roll, field, value):
    r = copy.deepcopy(roll)
    r["source"][field] = value
    assert any("commitment does not bind" in p for p in resealed(r))


def test_a_roll_committed_to_one_stock_cannot_be_fixed_as_another():
    with pytest.raises(ValueError, match="commitment does not bind"):
        fixer.fix_device("pauli-4x4", [0, 1, 4, 11, 13], source(stock="pauli"))


def test_no_field_can_absorb_its_neighbour():
    """verifier-P0 6d: v1 joined the fields with a bare '|', so an engine and a
    job could be re-attributed together with the commitment intact."""
    a = source(engine="tomography-api-v2", job_id="2e41913f|0082f37b")
    b = source(engine="tomography-api-v2|2e41913f", job_id="0082f37b")
    fa = fixer.commitment(stock="pauli-4x4", **{k: a[k] for k in fixer.COMMITTED})
    fb = fixer.commitment(stock="pauli-4x4", **{k: b[k] for k in fixer.COMMITTED})
    assert fa != fb


@pytest.mark.parametrize("missing", sorted(fixer.DEVICE_FIELDS))
def test_every_device_field_is_required(roll, missing):
    r = copy.deepcopy(roll)
    del r["source"][missing]
    assert any(p.startswith("source:") for p in resealed(r))


def test_malformed_hex_and_shots_are_refused_by_name(roll):
    r = copy.deepcopy(roll)
    r["source"]["salt"] = "XYZ"
    assert any("salt must be 64 lowercase hex" in p for p in resealed(r))
    r = copy.deepcopy(roll)
    r["source"]["shots"] = 0
    assert any("shots must be positive" in p for p in resealed(r))


def test_the_fixer_refuses_to_fix_an_incomplete_device_roll():
    s = source()
    del s["commitment"]
    with pytest.raises(ValueError, match="commitment"):
        fixer.fix_device("pauli-4x4", [0, 1, 4, 11, 13], s)
    with pytest.raises(ValueError, match="kind"):
        fixer.fix_device("pauli-4x4", [0, 1, 4, 11, 13], source(kind="golden"))


def test_the_fixer_rounds_nothing_into_shape():
    """verifier-P0 6c: fix_device once sealed [0.7, 1.2, 4.0, 11.5, 13.9] as
    [0, 1, 4, 11, 13], and check then passed it."""
    for crystals in ([0.7, 1.2, 4.0, 11.5, 13.9], [True, 2, 4, 11, 13], [0, 1, "4", 11, 13]):
        with pytest.raises(ValueError, match="not a list of integers"):
            fixer.fix_device("pauli-4x4", crystals, source())


def test_a_local_emulator_roll_must_name_its_backend():
    with pytest.raises(ValueError, match="must name its backend"):
        fixer.fix("pauli-4x4", [0, 1, 4, 11, 13], {"kind": "local-emu", "fixed_at": "2026-09-25T18:00:00Z"})


def test_a_device_may_lay_a_layout_the_law_forbids_and_the_record_keeps_it():
    """A device records what it laid, noise included. [0, 1, 2, 3, 4] has
    det(K_Y) = 0 under pauli-4x4, and is kept rather than censored."""
    assert fixer.check(fixer.fix_device("pauli-4x4", [0, 1, 2, 3, 4], source())) == []


def test_a_device_roll_keeps_a_crystal_count_the_law_never_lays():
    """A device records what it laid (verifier-P3: the count rule made a QPU's
    leaked layouts unfixable). A golden roll is still held to the count."""
    assert fixer.check(fixer.fix_device("pauli-4x4", [0, 1, 4, 11], source())) == []
    with pytest.raises(ValueError, match="count"):
        fixer.fix("pauli-4x4", [0, 1, 4, 11], {"kind": "golden", "stream": ["roll", "pauli-4x4", 1],
                                               "authority": fixer.authority(fixer.params("pauli-4x4"))})


def test_occurrences_is_known_and_held_and_other_fields_are_refused(roll):
    for bad in (-5, 0, 4097, "many", True):
        r = copy.deepcopy(roll)
        r["source"]["occurrences"] = bad
        assert any("occurrences must be" in p for p in resealed(r)), bad
    r = copy.deepcopy(roll)
    r["source"]["occurrences"] = 18
    assert resealed(r) == []
    r = copy.deepcopy(roll)
    r["source"]["mode"] = "qpu"
    assert any("fields the fixer does not know" in p for p in resealed(r))


def test_fixed_at_is_a_utc_time(roll):
    r = copy.deepcopy(roll)
    r["source"]["fixed_at"] = "yesterday"
    assert any("fixed_at must be a UTC time" in p for p in resealed(r))


def test_a_recomputed_commitment_passes_the_record_alone_which_is_why_the_anchor_binds(roll):
    """verifier-P3's A11: the salt is in the record, so a re-attributed roll with
    its commitment recomputed passes check(). The fixer says so; the anchor, the
    commitment published before the result, is what a reader holds it to."""
    r = copy.deepcopy(roll)
    r["source"]["job_id"] = "another-job"
    r["source"]["commitment"] = fixer.commitment(stock="pauli-4x4", **{k: r["source"][k] for k in fixer.COMMITTED})
    assert resealed(r) == []


def test_fixed_at_is_a_real_time_in_ascii_digits(roll):
    """The P0 verifier's fourth pass: the first check read a shape, and passed these."""
    for bad in ("2026-13-45T99:99:99Z", "٢٠٢٦-09-25T18:00:00Z", "2026-02-30T12:00:00Z", 5):
        r = copy.deepcopy(roll)
        r["source"]["fixed_at"] = bad
        assert any("fixed_at" in p for p in resealed(r)), bad       # 5 is refused by type, before the time


def test_a_local_emulator_roll_is_held_like_a_device_roll():
    good = {"kind": "local-emu", "fixed_at": "2026-09-25T18:00:00Z", "backend": "statevector"}
    assert fixer.check(fixer.fix("pauli-4x4", [0, 1, 4, 11, 13], good)) == []
    for bad, why in (({**good, "fixed_at": 5}, "fixed_at must be a UTC time"),
                     ({**good, "shots": 7}, "fields the fixer does not know")):
        with pytest.raises(ValueError, match=why):
            fixer.fix("pauli-4x4", [0, 1, 4, 11, 13], bad)
