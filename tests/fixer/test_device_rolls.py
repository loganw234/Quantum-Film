"""Device rolls: provenance and a commitment the checker recomputes."""
import copy
import hashlib

import pytest

from quantum_film import fixer

CIRCUIT = hashlib.sha256(b"OPENQASM 2.0; a stand-in circuit").hexdigest()
SALT = hashlib.sha256(b"a stand-in salt").hexdigest()


def source(**over):
    s = {"kind": "atlas-emu", "fixed_at": "2026-09-25T18:00:00Z", "engine": "tomography-api-v2",
         "job_id": "0082f37b-13cb-4b99-84d3-d9487a054c1e", "circuit_sha256": CIRCUIT, "shots": 4096,
         "decode": "quantum_film.atlas.decode/v1", "salt": SALT}
    s["commitment"] = fixer.commitment(s["circuit_sha256"], s["engine"], s["job_id"], s["salt"])
    s.update(over)
    return s


@pytest.fixture
def roll():
    return fixer.fix_device("pauli-4x4", [0, 1, 4, 11, 13], source())


def test_a_complete_device_roll_is_fixed_and_checks(roll):
    assert fixer.check(roll) == []


def test_the_commitment_is_the_documented_hash():
    s = source()
    msg = f"quantum-film/commitment/v1|{CIRCUIT}|tomography-api-v2|{s['job_id']}|{SALT}"
    assert s["commitment"] == hashlib.sha256(msg.encode()).hexdigest()


def resealed(rec):
    rec["digest"] = fixer.digest(rec)
    return fixer.check(rec)


@pytest.mark.parametrize("field,value", [("circuit_sha256", "0" * 64), ("engine", "coin-toss-v1"),
                                          ("job_id", "another-job"), ("salt", "f" * 64)])
def test_reattributing_a_roll_breaks_its_commitment(roll, field, value):
    r = copy.deepcopy(roll)
    r["source"][field] = value
    assert any("commitment does not bind" in p for p in resealed(r))


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


def test_a_local_emulator_roll_must_name_its_backend():
    rec = fixer.fix("pauli-4x4", [0, 1, 4, 11, 13], {"kind": "local-emu", "fixed_at": "2026-09-25T18:00:00Z"})
    assert any("must name its backend" in p for p in fixer.check(rec))
