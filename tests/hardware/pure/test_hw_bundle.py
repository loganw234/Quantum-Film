"""The frozen bundle's manifest (quantum_film.ibm.bundle): built by tools/hw_bundle.py, checked by name by
the runner before it submits and by the records test after. Control 4: a manifest whose hash differs from a
circuit file is refused. Each other refusal is planted on a copy of the committed fixture and RE-SEALED (every
hash and commitment recomputed), so that only the check under test can refuse it."""
import json

import pytest
from hwfix import FIXTURE, ROOT, copy_fixture, manifest, reseal

from quantum_film import fixer
from quantum_film.ibm import bundle


@pytest.fixture
def bdir(tmp_path):
    return copy_fixture(tmp_path)[0]


def problems(bdir):
    return bundle.check(bdir, ROOT)[2]


def refused(bdir, needle):
    found = problems(bdir)
    assert any(needle in p for p in found), found


def test_the_committed_fixture_holds():
    m, digest, found = bundle.check(FIXTURE / "bundle", ROOT)
    assert found == [] and digest == bundle.sha256((FIXTURE / "bundle" / bundle.MANIFEST).read_bytes())
    assert (m["kind"], m["backend"], m["source"]["sha256"]) == ("simulator", "fake_kingston", bundle.SOURCE_SHA256)


def test_the_logical_circuits_are_the_source_and_the_known_answer_as_text():
    source = bundle.read_source(ROOT)
    law = bundle.logical_qasm("law", source)
    head, body = source.split("qreg q[16];\n")
    assert law.startswith(head + "qreg q[16];\ncreg meas[16];\n" + body)
    assert law.endswith("barrier " + ",".join(f"q[{q}]" for q in range(16)) + ";\n"
                        + "".join(f"measure q[{q}] -> meas[{q}];\n" for q in range(16)))
    assert bundle.logical_qasm("coherence-yy", source).count("sdg q[") == 2
    ka = bundle.logical_qasm("known-answer", source)
    assert [ln for ln in ka.splitlines() if ln.startswith("x ")] == ["x q[0];", "x q[1];", "x q[3];", "x q[7];",
                                                                       "x q[12];"]
    with pytest.raises(ValueError, match="no circuit"):
        bundle.logical_qasm("film", source)


def test_the_source_must_be_ed767c01(tmp_path):
    (tmp_path / "docs" / "records" / "2026-09-25" / "p3").mkdir(parents=True)
    (tmp_path / bundle.SOURCE).write_bytes((ROOT / bundle.SOURCE).read_bytes().replace(b"q[5]", b"q[6]", 1))
    with pytest.raises(ValueError, match="is not the circuit that ran on Atlas"):
        bundle.read_source(tmp_path)


def test_the_readme_is_the_one_written_from_the_manifest():
    m = manifest(FIXTURE / "bundle")
    assert (FIXTURE / "bundle" / bundle.README).read_bytes() == bundle.readme(m).encode("ascii")


@pytest.mark.parametrize("name", ["law.qasm", "law.qpy", "law.gates.json", "law.isa.qasm3", "known-answer.qasm",
                                  "coherence-yy.qpy", "README.md"])
def test_control_4_a_file_whose_hash_differs_from_the_manifest_is_refused(bdir, name):
    path = bdir / name
    data = bytearray(path.read_bytes())
    data[len(data) // 2] ^= 1
    path.write_bytes(bytes(data))
    found = problems(bdir)
    assert found == [f"{name}: its SHA-256 is not the manifest's (the file is "
                     f"{bundle.sha256(bytes(data))[:16]}, the manifest says {files_hash(bdir, name)[:16]})"]


def files_hash(bdir, name):
    return bundle.files(manifest(bdir))[name]


def test_a_missing_or_an_extra_file_is_refused(bdir):
    (bdir / "law.isa.qasm3").unlink()
    refused(bdir, "law.isa.qasm3: missing")
    (bdir / "law.isa.qasm3").write_text("x")
    (bdir / "notes.txt").write_text("x")
    refused(bdir, "files: ['notes.txt'] are in the bundle and not in its manifest")


def test_a_logical_circuit_resealed_is_refused_by_its_source(bdir):
    """verifier-P3's plant, for hardware: q5 and q6 swapped in the law's text, every hash and commitment
    recomputed. Only the derivation from the committed source ed767c01 can refuse it."""
    path = bdir / "law.qasm"
    text = path.read_text(encoding="ascii")
    path.write_text(text.replace("q[5]", "q[@]").replace("q[6]", "q[5]").replace("q[@]", "q[6]"), encoding="ascii",
                    newline="\n")
    reseal(bdir)
    found = problems(bdir)
    assert found == ["law[0] law: the logical circuit is not the one derived from the source ed767c01bd4b851d"]


def test_a_gate_list_resealed_with_one_gate_changed_is_refused_by_the_isa_check(bdir):
    """Control 1 at the bundle's level: the check the runner makes before it submits."""
    doc = bundle.load_json((bdir / "law.gates.json").read_bytes())
    i = next(k for k in range(len(doc["gates"]) // 2, len(doc["gates"])) if doc["gates"][k][0] == "sx")
    doc["gates"][i][0] = "x"
    (bdir / "law.gates.json").write_bytes(bundle.text(doc).encode("ascii"))
    reseal(bdir)
    found = problems(bdir)
    assert found[0].startswith("law[0] law: isa: the transpiled circuit's distribution differs")
    assert all(p.startswith("law[0] law: isa: ") for p in found)              # nothing else refuses it


@pytest.mark.parametrize("change, needle", [
    (lambda m: m.update(kind="qpu", backend="fake_kingston"), "kind: a qpu bundle names an IBM device"),
    (lambda m: m.update(backend="ibm_fez"), "kind: a qpu bundle names an IBM device"),
    (lambda m: m.update(program="executor"), "program: 'executor'"),
    (lambda m: m.update(decode="plain order"), "decode: 'plain order'"),
    (lambda m: m.update(route="atlas"), "kind is one of"),
    (lambda m: m.update(stock="pauli"), "stock: 'pauli'"),
    (lambda m: m.update(known_answer=[0, 15]), "known_answer: [0, 15]"),
    (lambda m: m.update(pair=[1, 2]), "pair: [1, 2]"),
    (lambda m: m["source"].update(sha256="0" * 64), "source: not"),
    (lambda m: m["options"]["dynamical_decoupling"].update(enable=True), "options: "),
    (lambda m: m["options"]["twirling"].update(enable_measure=0), "options: "),
    (lambda m: m.update(options_sha256="0" * 64), "options_sha256: not the digest"),
    (lambda m: m["compile"].update(optimization_level=1), "compile: {optimization_level 2"),
    (lambda m: m.update(frozen_at="2026-10-03 16:00:00Z"), "frozen_at: a UTC time"),
    (lambda m: m["jobs"].reverse(), "jobs: the plan's jobs in order"),
    (lambda m: m["jobs"][2]["circuits"].reverse(), "pub, name, role and basis are the plan's"),
    (lambda m: m["jobs"][2]["circuits"][0].update(basis="YY" + "Z" * 14), "pub, name, role and basis are the plan's"),
    (lambda m: m["jobs"][0]["circuits"][0].update(shots=0), "shots are a positive whole number"),
    (lambda m: m["jobs"][1].update(max_execution_time=301), "max_execution_time is whole seconds from 1 to 300"),
    (lambda m: m["jobs"][1]["circuits"][0].update(source_sha256=None), "source_sha256 is"),
    (lambda m: m["jobs"][0]["circuits"][0].update(note="x"), "an entry carries exactly"),
    (lambda m: m.update(note="x"), "a manifest carries exactly"),
])
def test_the_manifest_is_refused_by_name(bdir, change, needle):
    """Each change re-sealed: hashes and commitments recomputed from the changed manifest."""
    reseal(bdir, change)
    refused(bdir, needle)


def test_a_qpu_bundle_takes_the_plans_shots(bdir):
    """The fixture's test shots are allowed for a simulator bundle only."""
    reseal(bdir, lambda m: m.update(kind="qpu", backend="ibm_kingston", target=dict(m["target"], name="ibm_kingston")))
    found = problems(bdir)
    assert "jobs.known-answer[0]: 64 shots; a qpu bundle takes the plan's 1024" in found
    assert "jobs.law[0]: 256 shots; a qpu bundle takes the plan's 24576" in found
    assert "jobs.coherence[1]: 64 shots; a qpu bundle takes the plan's 4096" in found


def test_a_jobs_pubs_share_one_shot_count(bdir):
    """qiskit-ibm-runtime deprecates different shots across a job's PUBs; the plan splits the film for it."""
    reseal(bdir, lambda m: m["jobs"][2]["circuits"][1].update(shots=65))
    refused(bdir, "jobs.coherence: its PUBs take different shots; a job's PUBs share one shot count")


def test_the_plan_is_three_jobs_each_of_one_shot_count():
    assert [(job, [(c[0], c[3]) for c in cs]) for job, cs in bundle.PLAN] == [
        ("known-answer", [("known-answer", 1024)]), ("law", [("law", 24576)]),
        ("coherence", [("coherence-xx", 4096), ("coherence-yy", 4096)])]


def test_a_commitment_that_does_not_recompute_is_refused(bdir):
    m = manifest(bdir)
    m["jobs"][2]["circuits"][1]["commitment"] = m["jobs"][2]["circuits"][0]["commitment"]
    (bdir / bundle.MANIFEST).write_bytes(bundle.text(m).encode("ascii"))
    found = problems(bdir)
    assert "coherence[1] coherence-yy: the commitment does not recompute from the manifest's fields" in found
    assert "salt: every circuit has its own salt and commitment" in found


def test_a_commitment_binds_the_kind_route_backend_and_pub(bdir):
    m = manifest(bdir)
    e = m["jobs"][2]["circuits"][0]
    base = bundle.commitment(m, e)
    for field, value in (("kind", "qpu"), ("route", "moth"), ("backend", "ibm_fez"), ("program", "x")):
        assert bundle.commitment(dict(m, **{field: value}), e) != base, field
    assert bundle.commitment(m, dict(e, pub=2)) != base
    assert base == fixer.commitment_v3(stock=m["stock"], role=e["role"], basis=e["basis"], kind=m["kind"],
                                       route=m["route"], backend=m["backend"], program=m["program"], pub=e["pub"],
                                       circuit_sha256=e["circuit_sha256"], isa_sha256=e["isa_sha256"],
                                       shots=e["shots"], options_sha256=m["options_sha256"], decode=m["decode"],
                                       salt=e["salt"])


def test_a_manifest_is_its_canonical_text_with_no_key_twice(bdir):
    path = bdir / bundle.MANIFEST
    raw = path.read_bytes()
    path.write_bytes(raw.replace(b'"format"', b'"format" ', 1))
    refused(bdir, "its bytes are not the manifest's canonical text")
    path.write_bytes(raw.replace(b'{\n "backend"', b'{\n "stock": "pauli",\n "backend"', 1))
    refused(bdir, "a key appears twice")
    path.write_bytes(json.dumps(json.loads(raw)).encode())
    refused(bdir, "its bytes are not the manifest's canonical text")


def test_a_chain_that_is_not_the_gate_lists_is_refused(bdir):
    def change(m):
        c = m["jobs"][2]["circuits"][0]["chain"]
        c[0], c[1] = c[1], c[0]
    reseal(bdir, change)
    refused(bdir, "coherence[0] coherence-xx: the gate list's chain is not the manifest's")
