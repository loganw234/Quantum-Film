"""The Atlas run's offline half: what is sent, what is committed, how the result
is read and scored, and the device rolls fixed from it. Nothing here calls
Atlas (tools/pauli_atlas_run.py does)."""
import copy
import hashlib
import json
import math
import pathlib

import numpy as np
import pytest

from quantum_film import fixer
from quantum_film.atlas import pauli_tile
from quantum_film.circuits import givens, givens_line
from quantum_film.golden.uniform import stream, uniform

ROOT = pathlib.Path(__file__).resolve().parents[2]
OPEN_BOX_RUN = ROOT / "research" / "2026-09-25" / "emulsions" / "fermion_tile_atlas.json"
N = 5


@pytest.fixture(scope="module")
def K():
    return pauli_tile.golden_kernel()


@pytest.fixture(scope="module")
def forbidden(K):
    return pauli_tile.forbidden_layouts(K, N)


@pytest.fixture(scope="module")
def sent():
    return pauli_tile.circuit()


@pytest.fixture(scope="module")
def law_draws(forbidden):
    """4,096 layouts drawn from det(K_Y) by inverse CDF on the authority's exact
    uniforms: what an exact emulator lays, the same on every machine."""
    dets = forbidden[1]
    ys = sorted(dets)
    cdf = np.cumsum([max(dets[Y], 0.0) for Y in ys])
    counts = {}
    for k in range(pauli_tile.SHOTS):
        u = float(uniform(stream("p3-scorer-twin", "pauli-4x4", k), 0)) * cdf[-1]
        Y = ys[int(np.searchsorted(cdf, u, side="right"))]
        counts[Y] = counts.get(Y, 0) + 1
    return counts


def line(job_id="0b2c3d4e-0000-4000-8000-000000000000", salt="5a" * 32, circuit_sha256=None):
    return pauli_tile.commitment_line(job_id=job_id, salt=salt, circuit_sha256=circuit_sha256 or "c" * 64,
                                      qasm_file="circuit.qasm", submitted_at="2026-09-25T23:00:00Z",
                                      code_commit="0" * 40)


def test_the_law_forbids_1360_of_the_4368_layouts(forbidden):
    assert (len(forbidden[0]), len(forbidden[1])) == (1360, math.comb(16, N))


def test_what_is_sent_is_the_line_circuit_held_to_the_law(sent):
    gate_list, qasm, sha, st = sent
    assert sha == hashlib.sha256(qasm.encode("ascii")).hexdigest()
    assert givens_line.from_qasm(qasm) == (gate_list, 16)
    assert max(st["kernel_error"], st["law_error"], st["leaked"]) < 1e-12
    assert sha != hashlib.sha256(givens.circuit(4, 1)[1].encode("ascii")).hexdigest()   # not the reference


def test_the_request_puts_every_qubit_in_the_list(sent):
    body = pauli_tile.request(sent[1], 16)
    assert body["params"]["circuit_qasm"] is sent[1]
    assert body["params"]["qubit_list"] == list(range(16)) and body["params"]["shots"] == 4096


def test_the_commitment_line_binds_what_a_record_will_carry():
    ln = line()
    assert ln["format"] == fixer.COMMITMENT_DOMAIN and ln["stock"] == "pauli-4x4"
    assert ln["decode"] == pauli_tile.DECODE and ln["engine"] == "tomography-api-v2"
    assert ln["commitment"] == fixer.commitment(stock="pauli-4x4", **{k: ln[k] for k in fixer.COMMITTED})
    assert "result" not in json.dumps(ln)


def test_an_exact_emulators_layouts_pass_the_score(law_draws, K, forbidden):
    """The positive twin of the scorer: draws from the law itself."""
    sc = pauli_tile.score(law_draws, K, forbidden[0], "c" * 64)
    assert sc["shots"] == 4096 and sc["crystals_per_layout"] == {"5": 4096}
    assert sc["forbidden"]["shots"] == 0
    assert sc["one_site"]["max_abs_z"] < 4 and sc["pairs"]["max_abs_z"] < 4.5 and sc["chi2_per_dof"] < 1.6


def test_the_open_box_run_scored_against_the_shelfs_law_fails(K, forbidden):
    """The scorer's negative control: Atlas job 0082f37b laid the open box's law.
    Read through decode, it reproduces the P0 verifier's figures against
    pauli-4x4 (docs/VALIDATION.md), and lays layouts pauli-4x4 forbids."""
    result = json.loads(OPEN_BOX_RUN.read_text(encoding="utf-8"))["result"]
    sc = pauli_tile.score(pauli_tile.layouts(result), K, forbidden[0], "d701cfb85790c2af" + "0" * 48)
    assert round(sc["one_site"]["max_abs_z"], 2) == 10.01 and round(sc["one_site"]["chi2"], 1) == 521.2
    assert round(sc["pairs"]["max_abs_z"], 2) == 20.20 and round(sc["pairs"]["chi2"], 1) == 5328.3
    assert sc["forbidden"]["shots"] > 0


def test_every_distinct_layout_becomes_a_device_roll_that_checks(law_draws):
    ln = line()
    records, refused = pauli_tile.device_rolls(law_draws, ln, "2026-09-25T23:05:00Z")
    assert refused == [] and len(records) == len(law_draws)
    assert sum(r["source"]["occurrences"] for r in records) == 4096
    for r in records[:50]:
        assert fixer.check(r) == []
        assert r["source"]["commitment"] == ln["commitment"] and r["source"]["kind"] == "atlas-emu"
        assert all(type(q) is int for q in r["crystals"])
        assert json.loads(fixer.text(r)) == r


def test_a_forbidden_layout_is_fixed_and_a_miscounted_one_is_reported_not_reshaped(forbidden):
    Y = min(forbidden[0])
    records, refused = pauli_tile.device_rolls({Y: 3, (0, 1, 2, 3): 2}, line(), "2026-09-25T23:05:00Z")
    assert [r["crystals"] for r in records] == [list(Y)] and fixer.check(records[0]) == []
    assert refused and refused[0][:2] == ([0, 1, 2, 3], 2) and "count" in refused[0][2]


def test_control_2_a_roll_with_its_job_id_altered_and_resealed_is_refused(law_draws):
    rec = copy.deepcopy(pauli_tile.device_rolls(law_draws, line(), "2026-09-25T23:05:00Z")[0][0])
    rec["source"]["job_id"] = "0b2c3d4e-0000-4000-8000-000000000001"
    rec["digest"] = fixer.digest(rec)
    assert fixer.check(rec) == ["source: the commitment does not bind this stock, circuit, engine, job, shots, "
                                "decode and salt"]


def test_records_carry_no_credential_or_address():
    """The planted strings are assembled at run time, so no scan of this tree
    for keys or addresses finds one in this file."""
    assert pauli_tile.safe_json({"measurements": {"ZZ": {"counts": {"01": 3}}}})
    for planted in ("someone" + "@" + "example.com", "https://b.s3." + "amazonaws.com/x", "X-Amz" + "-Signature=a",
                    "moth" + "_" + "abcdefgh12345678", "Bear" + "er abc.def"):
        with pytest.raises(PermissionError, match="nothing was written"):
            pauli_tile.safe_json({"note": planted})
    assert "<presigned url removed>" in pauli_tile.safe_json({"url": "gone"})
