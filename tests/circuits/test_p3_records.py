"""The device rolls P3 committed, held from docs/records alone (offline).

Each record is intact on the fixer's own terms; its commitment recomputes and
names a circuit whose COMMITTED QASM text hashes to it and lays the shelf's
law here; and the records are exactly the committed result read through
decode, occurrences included. This is what the fixer cannot check by itself:
it binds a circuit's hash, not the law the circuit lays.
"""
import copy
import json
import pathlib

import pytest

from quantum_film import fixer
from quantum_film.atlas import pauli_tile
from quantum_film.circuits import givens_line

ROOT = pathlib.Path(__file__).resolve().parents[2]
RUNS = [(jsonl.parent, json.loads(raw))
        for jsonl in sorted((ROOT / "docs" / "records").glob("*/p3/commitments.jsonl"))
        for raw in jsonl.read_text(encoding="ascii").splitlines()]
IDS = [line["job_id"][:8] for _out, line in RUNS]


def test_the_branch_carries_a_committed_run():
    assert RUNS


@pytest.mark.parametrize("out,line", RUNS, ids=IDS)
def test_the_commitment_recomputes_and_its_committed_qasm_lays_the_law(out, line):
    qasm = (out / line["qasm_file"]).read_bytes().decode("ascii")
    assert pauli_tile.sha256_text(qasm) == line["circuit_sha256"]
    assert line["commitment"] == fixer.commitment(stock=line["stock"], **{k: line[k] for k in fixer.COMMITTED})
    assert (line["stock"], line["engine"], line["decode"]) == (pauli_tile.STOCK, pauli_tile.ENGINE, pauli_tile.DECODE)
    held = pauli_tile.check_circuit(givens_line.from_qasm(qasm)[0], pauli_tile.golden_kernel(line["stock"]),
                                    pauli_tile.shape(line["stock"])[3])
    assert max(held.values()) < 1e-12


@pytest.mark.parametrize("out,line", RUNS, ids=IDS)
def test_the_records_are_intact_and_are_the_committed_result(out, line):
    job = line["job_id"][:8]
    result = json.loads((out / f"atlas-{job}-result.json").read_text(encoding="ascii"))["response"]["result"]
    counts = pauli_tile.layouts(result)
    recs = {}
    for f in sorted((out / f"rolls-{job}").glob("*.json")):
        rec, problems = fixer.check_file(f)
        assert problems == [], f.name
        assert f.name == pauli_tile.record_name(rec)
        assert all(rec["source"][k] == line[k] for k in (*fixer.COMMITTED, "commitment"))
        recs[tuple(rec["crystals"])] = rec["source"]["occurrences"]
    assert recs == {Y: c for Y, c in counts.items() if len(Y) == pauli_tile.shape(line["stock"])[3]}
    assert sum(counts.values()) == line["shots"]


@pytest.mark.parametrize("out,line", RUNS, ids=IDS)
def test_the_engines_own_observables_agree_coherence_included(out, line):
    """Read by the engine from its other settings, not by decode: every <X_q>,
    <Y_q>, <Z_q>, and the pair (0, 1)'s nine correlators, |<XX>| = |<YY>| = 0.375
    among them, which only a coherent state gives. 2.29 at worst on 8586f1cc."""
    result = json.loads((out / f"atlas-{line['job_id'][:8]}-result.json").read_text(encoding="ascii"))
    rows = pauli_tile.engine_observables(result["response"]["result"], pauli_tile.golden_kernel(line["stock"]))
    assert len(rows) == 3 * 16 + 9 and max(abs(z) for *_rest, z in rows) < 4.5


@pytest.mark.parametrize("out,line", RUNS[:1], ids=IDS[:1])
def test_control_2_a_committed_roll_with_its_job_id_altered_is_refused(out, line):
    f = sorted((out / f"rolls-{line['job_id'][:8]}").glob("*.json"))[0]
    rec, problems = fixer.check_file(f)
    assert problems == []
    bad = copy.deepcopy(rec)
    bad["source"]["job_id"] = line["job_id"][:-1] + ("0" if line["job_id"][-1] != "0" else "1")
    bad["digest"] = fixer.digest(bad)
    assert fixer.check(bad) == ["source: the commitment does not bind this stock, circuit, engine, job, shots, "
                                "decode and salt"]
