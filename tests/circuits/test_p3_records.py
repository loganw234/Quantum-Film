"""The device rolls P3 committed, held from docs/records alone (offline).

Each record is intact on the fixer's own terms, of the kind that ran and fixed
no earlier than the server says the job was submitted; its commitment
recomputes and names a circuit whose COMMITTED QASM text hashes to it and lays
the shelf's law here; the records are exactly the committed result read
through decode, occurrences included; and the engine's own observables agree
with the committed circuit's state, signs included. The fixer cannot check the
law by itself: it binds a circuit's hash, not the law the circuit lays.

pauli_tile.audit is the same list, and `tools/pauli_atlas_run.py --score`
exits 1 on any of it; the plants at the end are verifier-P3's (2026-09-26),
each refused by name.
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


@pytest.fixture(scope="module", params=RUNS, ids=IDS)
def run(request):
    out, line = request.param
    loaded, problems = pauli_tile.load_run(out, line)
    assert problems == []
    return loaded


@pytest.fixture(scope="module")
def psi(run):
    return givens_line.simulate(*givens_line.from_qasm(run["qasm"]))


def test_the_branch_carries_a_committed_run():
    assert RUNS


def test_the_commitment_recomputes_and_its_committed_qasm_lays_the_law(run, psi):
    line = run["line"]
    assert pauli_tile.sha256_text(run["qasm"]) == line["circuit_sha256"]
    assert line["commitment"] == fixer.commitment(stock=line["stock"], **{k: line[k] for k in fixer.COMMITTED})
    assert (line["stock"], line["engine"], line["decode"]) == (pauli_tile.STOCK, pauli_tile.ENGINE, pauli_tile.DECODE)
    assert run["submit"]["body"]["params"]["circuit_qasm"] == run["qasm"]
    held = pauli_tile.check_state(psi, pauli_tile.golden_kernel(line["stock"]), pauli_tile.shape(line["stock"])[3])
    assert max(held.values()) < 1e-12


def test_the_records_are_intact_of_their_kind_and_are_the_committed_result(run):
    line = run["line"]
    counts = pauli_tile.layouts(run["result"]["response"]["result"])
    submitted = pauli_tile.utc(run["submit"]["response"]["submitted_at"])
    recs = {}
    for name, raw in run["records"]:
        rec = json.loads(raw)
        assert raw == fixer.text(rec).encode("ascii") and fixer.check(rec) == [], name
        assert name == pauli_tile.record_name(rec)
        assert all(rec["source"][k] == line[k] for k in (*fixer.COMMITTED, "commitment"))
        assert rec["source"]["kind"] == "atlas-emu", name                  # the account has no QPU
        assert pauli_tile.utc(rec["source"]["fixed_at"]) >= submitted, name
        recs[tuple(rec["crystals"])] = rec["source"]["occurrences"]
    assert run["score"]["not_fixed"] == [] and recs == counts
    assert sum(counts.values()) == line["shots"]


def test_the_engines_own_observables_agree_signs_included(run, psi):
    """Read by the engine from its other settings, not by decode, and held to the
    committed circuit's own state: its <X0X1> = <Y0Y1> = +0.375 (the gauge left
    the sign open until this circuit fixed it). 2.29 at worst on 8586f1cc. A
    negated pair, or a mixture with the same layouts (<XX> = <YY> = 0), fails."""
    assert abs(givens_line.pauli_expectation(psi, {0: "X", 1: "X"}) - 0.375) < 1e-12
    assert abs(givens_line.pauli_expectation(psi, {0: "Y", 1: "Y"}) - 0.375) < 1e-12
    result = run["result"]["response"]["result"]
    rows = pauli_tile.engine_observables(result, psi)
    assert len(rows) == 3 * 16 + 9 and max(abs(z) for *_rest, z in rows) < pauli_tile.ENGINE_Z
    for planted in ({"XX": -1, "YY": -1}, {"XX": 0, "YY": 0}):
        bad = copy.deepcopy(result)
        for k, factor in planted.items():
            bad["observables"]["0,1"][k] *= factor
        assert min(z for *_rest, z in pauli_tile.engine_observables(bad, psi)) < -25


def test_the_audit_holds_the_committed_run(run):
    assert pauli_tile.audit(run) == []


def _reseal(raw, change):
    rec = json.loads(raw)
    change(rec)
    rec["digest"] = fixer.digest(rec)
    return fixer.text(rec).encode("ascii")


def _swap(text, a, b):
    return text.replace(f"q[{a}]", "q[@]").replace(f"q[{b}]", f"q[{a}]").replace("q[@]", f"q[{b}]")


def test_plant_the_qasm_with_q5_and_q6_swapped_and_everything_resealed(run):
    """verifier-P3's plant: the committed QASM swapped q5<->q6, re-hashed, the
    commitment recomputed, the submit exchange rewritten. Hash, commitment and
    exchange all agree again; only the law can refuse it (kernel error 3.1e-2)."""
    line = copy.deepcopy(run["line"])
    qasm = _swap(run["qasm"], 5, 6)
    line["circuit_sha256"] = pauli_tile.sha256_text(qasm)
    line["commitment"] = fixer.commitment(stock=line["stock"], **{k: line[k] for k in fixer.COMMITTED})
    submit = copy.deepcopy(run["submit"])
    submit["body"]["params"]["circuit_qasm"] = qasm
    found, _psi = pauli_tile.audit_circuit(line, qasm, submit)
    assert len(found) == 1 and found[0].startswith("law: the committed QASM does not lay pauli-4x4's law")


def _records_plant(run, how):
    records = list(run["records"])
    occ = [json.loads(raw)["source"]["occurrences"] for _name, raw in records]
    i = next(k for k, n in enumerate(occ) if n >= 2)
    if how == "moved-shot":                      # one shot moved between two rolls, both re-sealed
        j = next(k for k in range(len(records)) if k != i)
        records[i] = (records[i][0], _reseal(records[i][1], lambda r: r["source"].update(
            occurrences=r["source"]["occurrences"] - 1)))
        records[j] = (records[j][0], _reseal(records[j][1], lambda r: r["source"].update(
            occurrences=r["source"]["occurrences"] + 1)))
    elif how == "kind-qpu":                      # an emulator roll re-sealed as a QPU's
        records[i] = (records[i][0], _reseal(records[i][1], lambda r: r["source"].update(kind="qpu")))
    elif how == "backdated":                     # fixed_at before the job existed, re-sealed
        records[i] = (records[i][0], _reseal(records[i][1], lambda r: r["source"].update(
            fixed_at="2026-09-25T22:52:00Z")))
    return records


@pytest.mark.parametrize("how,named", [("moved-shot", "records: they are not the committed result"),
                                       ("kind-qpu", "kind 'qpu'"), ("backdated", "is before the job was submitted")])
def test_plant_a_resealed_roll_is_refused_by_name(run, how, named):
    """Each passes the fixer's own check: only the run's audit can see it."""
    records = _records_plant(run, how)
    assert all(fixer.check(json.loads(raw)) == [] for _name, raw in records)
    counts = pauli_tile.layouts(run["result"]["response"]["result"])
    found = pauli_tile.audit_records(run["line"], run["submit"], counts, records)
    assert len(found) == 1 and named in found[0]


def test_control_2_a_committed_roll_with_its_job_id_altered_is_refused(run):
    name, raw = run["records"][0]
    rec = json.loads(raw)
    assert fixer.check(rec) == []
    job = run["line"]["job_id"]
    bad = json.loads(_reseal(raw, lambda r: r["source"].update(job_id=job[:-1] + ("0" if job[-1] != "0" else "1"))))
    assert fixer.check(bad) == ["source: the commitment does not bind this stock, circuit, engine, job, shots, "
                                "decode and salt"]


def test_the_platform_that_wrote_the_qasm_is_recorded_beside_it(run):
    """atan2 decides the text's last bits, so the text is the platform's too. Runs in one directory share a
    QASM file: the tool refuses a file with other bytes, and writes the platform record once, at the first
    run to write it. So the record names the code commit of a run that wrote that file (2026-09-26: six
    runs, one file); with one run in a directory, that is exactly its own."""
    out = next(o for o, ln in RUNS if ln is run["line"])
    rec = json.loads((out / (run["line"]["qasm_file"][:-len(".qasm")] + ".platform.json")).read_text(encoding="ascii"))
    assert rec["circuit_sha256"] == run["line"]["circuit_sha256"]
    writers = {ln["code_commit"] for o, ln in RUNS if o == out and ln["qasm_file"] == run["line"]["qasm_file"]}
    assert rec["made_by"]["code_commit"] in writers
    assert rec["python"]["version"] and rec["numpy"]["version"] and rec["libm"]["library"]
    assert rec["basis"]["exact"] is True
