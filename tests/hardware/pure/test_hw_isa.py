"""This project's own ISA check (quantum_film.ibm.isa): its gates held to their matrices by an independent
dense-matrix reference, its refusals by name, its layout mapping, the exact logical distributions, and the
committed fixture's transpiled circuits held to the law, the coherences and the known answer. Control 1: a
transpiled circuit with one gate changed is refused before submission. Control 5 (pure form): a chain with a
SWAP in it is refused by the SWAP-free checks."""
import copy
import math
import random

import numpy as np
import pytest
from hwfix import FIXTURE, ROOT, read_doc

from quantum_film.circuits import givens_line
from quantum_film.ibm import bundle, isa

# qiskit's definitions, written out (the module's docstring states them).
RZ = lambda t: np.diag([np.exp(-0.5j * t), np.exp(0.5j * t)])  # noqa: E731
SX = np.array([[1 + 1j, 1 - 1j], [1 - 1j, 1 + 1j]]) / 2
X = np.array([[0, 1], [1, 0]], dtype=complex)


def reference(n, gates):
    """A dense 2^n statevector, qubit q the q-th bit from the RIGHT of the basis index (qiskit's order), each
    gate a full Kronecker matrix: nothing shared with isa.distribution."""
    psi = np.zeros(2 ** n, dtype=complex)
    psi[0] = 1.0

    def full(u, q):
        mats = [u if k == q else np.eye(2) for k in reversed(range(n))]
        out = mats[0]
        for m in mats[1:]:
            out = np.kron(out, m)
        return out

    for name, qs, ps in gates:
        if name == "rz":
            psi = full(RZ(ps[0]), qs[0]) @ psi
        elif name == "sx":
            psi = full(SX, qs[0]) @ psi
        elif name == "x":
            psi = full(X, qs[0]) @ psi
        elif name == "cz":
            idx = np.arange(2 ** n)
            psi = np.where(((idx >> qs[0]) & 1) & ((idx >> qs[1]) & 1), -psi, psi)
    return np.abs(psi) ** 2          # index n: bit q = qubit q, the same convention as distribution's


def doc_of(n_physical, gates, measures, layout=None):
    """A gate-list document: gates on physical qubits, then measure (physical, clbit) pairs."""
    m = len(measures)
    lay = layout or list(range(m))
    return {"format": isa.FORMAT, "num_qubits": n_physical, "num_clbits": m, "global_phase": 0.0,
            "layout": {"initial": lay, "final": lay, "routing_permutation": list(range(n_physical))},
            "gates": [[g, list(q), [], [float(p) for p in ps]] for g, q, ps in gates]
            + [["barrier", list(range(n_physical)), [], []]] + [["measure", [p], [c], []] for p, c in measures]}


@pytest.mark.parametrize("seed", range(40))
def test_random_circuits_agree_with_the_dense_matrix_reference(seed):
    rng = random.Random(seed)
    n = rng.randint(1, 4)
    gates = []
    for _ in range(rng.randint(1, 30)):
        kind = rng.choice(["rz", "sx", "x", "cz"] if n > 1 else ["rz", "sx", "x"])
        if kind == "cz":
            a, b = rng.sample(range(n), 2)
            gates.append(("cz", (a, b), ()))
        else:
            gates.append((kind, (rng.randrange(n),), (rng.uniform(-7, 7),) if kind == "rz" else ()))
    p = isa.distribution(doc_of(n, gates, [(q, q) for q in range(n)]))
    assert np.max(np.abs(p - reference(n, gates))) < 1e-12


def test_each_gate_on_a_basis_state():
    """x flips; sx twice is x; rz alone moves no Z probability; sx rz(t) sx gives P(1) = cos^2(t/2); a CZ
    between two Hadamards (rz(pi/2) sx rz(pi/2)) is a CNOT."""
    one = lambda gates: isa.distribution(doc_of(1, gates, [(0, 0)]))  # noqa: E731
    assert one([("x", (0,), ())])[1] == 1.0
    assert abs(one([("sx", (0,), ()), ("sx", (0,), ())])[1] - 1.0) < 1e-15
    assert one([("rz", (0,), (1.234,))])[0] == 1.0
    for t in (0.0, 0.3, math.pi / 2, 2.0, math.pi):
        assert abs(one([("sx", (0,), ()), ("rz", (0,), (t,)), ("sx", (0,), ())])[1] - math.cos(t / 2) ** 2) < 1e-14
    h = [("rz", (1,), (math.pi / 2,)), ("sx", (1,), ()), ("rz", (1,), (math.pi / 2,))]
    cnot = h + [("cz", (0, 1), ())] + h
    p = isa.distribution(doc_of(2, [("x", (0,), ())] + cnot, [(0, 0), (1, 1)]))
    assert abs(p[0b11] - 1.0) < 1e-14                                    # |10> (qubit 0 set) -> |11>


def test_physical_qubits_map_back_to_logical_through_the_measurements():
    """The same logical circuit on physical qubits 7 and 3, measured into clbits 0 and 1, gives the logical
    distribution: index bit i is clbit i, whatever physical qubit held it. An idle qubit is never simulated."""
    gates = [("x", (7,), ()), ("sx", (3,), ())]
    p = isa.distribution(doc_of(9, gates, [(7, 0), (3, 1)], layout=[7, 3]))
    assert p.size == 4 and abs(p[0b01] - 0.5) < 1e-15 and abs(p[0b11] - 0.5) < 1e-15
    swapped = isa.distribution(doc_of(9, gates, [(7, 1), (3, 0)], layout=[3, 7]))
    assert abs(swapped[0b10] - 0.5) < 1e-15 and abs(swapped[0b11] - 0.5) < 1e-15


def _refused(doc, needle):
    with pytest.raises(isa.IsaRefusal) as refusal:
        isa.distribution(doc)
    assert needle in str(refusal.value), str(refusal.value)


def test_a_gate_outside_the_isa_is_refused_by_name():
    for name in ("h", "cx", "ecr", "rzz", "reset", "delay", "id"):
        doc = doc_of(2, [], [(0, 0), (1, 1)])
        doc["gates"].insert(0, [name, [0], [], []])
        _refused(doc, f"{name!r} is not in the ISA this check reads")


@pytest.mark.parametrize("change, needle", [
    (lambda d: d["gates"].append(["x", [0], [], []]), "x on qubit 0 after its measurement"),
    (lambda d: d["gates"].append(["measure", [1], [0], []]), "after its measurement"),
    (lambda d: d["gates"].pop(), "clbits [1] are never measured"),
    (lambda d: d["gates"].insert(0, ["rz", [0], [], []]), "rz takes 1 distinct qubit(s), 0 clbit(s), 1 parameter"),
    (lambda d: d["gates"].insert(0, ["cz", [0, 0], [], []]), "cz takes 2 distinct qubit(s)"),
    (lambda d: d["gates"].insert(0, ["rz", [0], [], [float("nan")]]), "not a finite float"),
    (lambda d: d["gates"].insert(0, ["rz", [0], [], [1]]), "not a finite float"),
    (lambda d: d["gates"].insert(0, ["x", [5], [], []]), "outside the circuit"),
    (lambda d: d.update(format="x"), "format 'x' is not"),
    (lambda d: d.update(extra=1), "it carries exactly"),
    (lambda d: d["layout"].update(initial=[0, 0]), "layout initial names 2 distinct physical qubits"),
])
def test_a_gate_list_it_does_not_read_is_refused_by_name(change, needle):
    doc = doc_of(2, [("sx", (0,), ())], [(0, 0), (1, 1)])
    change(doc)
    _refused(doc, needle)


def test_too_many_active_qubits_are_refused():
    n = isa.MAX_ACTIVE + 1
    _refused(doc_of(n, [], [(q, q) for q in range(n)]), f"{n} active qubits")


def test_exact_distribution_is_pauli_algebra_on_the_logical_state():
    source = bundle.read_source(ROOT)
    psi = bundle.logical_state("law", source)
    z = isa.exact_distribution(psi, "Z" * 16)
    flat = np.transpose(psi ** 2, list(reversed(range(16)))).reshape(-1)
    assert abs(z.sum() - 1) < 1e-12 and np.max(np.abs(z - flat)) < 1e-15
    for letters in ("XX", "YY", "XY"):
        p = isa.exact_distribution(psi, letters + "Z" * 14)
        assert abs(p.sum() - 1) < 1e-12 and p.min() > -1e-15
        want = givens_line.pauli_expectation(psi, {0: letters[0], 1: letters[1]})
        assert abs(isa.parity(p, (0, 1)) - want) < 1e-12
    xx = isa.exact_distribution(psi, "XX" + "Z" * 14)
    assert abs(isa.parity(xx, (0, 1)) - 0.375) < 1e-12               # the circuit's own sign (CLAUDE.md)
    # H on qubits 0 and 1 is the X basis: the reference's own real simulator agrees outcome for outcome
    gl, _m = givens_line.from_qasm(source)
    h = givens_line.simulate(gl + [("h", 0), ("h", 1)], 16)
    assert np.max(np.abs(xx - np.transpose(h ** 2, list(reversed(range(16)))).reshape(-1))) < 1e-14


# ---------------------------------------------------------------- the fixture's transpiled circuits

NAMES = ("known-answer", "law", "coherence-xx", "coherence-yy")


@pytest.fixture(scope="module")
def plan():
    m = bundle.load(FIXTURE / "bundle")[0]
    entries = {e["name"]: e for j in m["jobs"] for e in j["circuits"]}
    source = bundle.read_source(ROOT)
    docs = {n: read_doc(FIXTURE / "bundle" / (n + bundle.SUFFIX["gates"])) for n in NAMES}
    return m, entries, source, docs


@pytest.mark.parametrize("name", NAMES)
def test_the_fixtures_transpiled_circuits_hold(plan, name):
    m, entries, source, docs = plan
    e = entries[name]
    held, values = bundle.hold_isa(docs[name], name, e["role"], e["basis"], source)
    assert held == [] and values["max_abs_error"] < 1e-15
    if e["role"] == "coherence":
        assert abs(values["parity"] - 0.375) < 1e-12
    assert isa.swap_free(docs[name], [tuple(x) for x in m["target"]["coupling"]], bundle.CZ[name]) == []


def _mid(doc, name, start=0.3):
    """The index of a gate of `name` past `start` of the way through the circuit, and before its end."""
    gates = doc["gates"]
    return next(i for i in range(int(len(gates) * start), len(gates)) if gates[i][0] == name)


@pytest.mark.parametrize("plant", ["sx->x", "rz+pi/2", "cz dropped", "cz moved", "x dropped"])
def test_control_1_a_transpiled_circuit_with_one_gate_changed_is_refused(plan, plant):
    """Each plant is one gate of the law circuit's gate list, changed mid-circuit; the ISA check refuses
    it by name. (The bundle's check would refuse the changed file by its hash first; here only the ISA
    check stands, as when the file and the manifest are re-sealed together.)"""
    _m, entries, source, docs = plan
    doc = copy.deepcopy(docs["law"])
    if plant == "sx->x":
        doc["gates"][_mid(doc, "sx")][0] = "x"
    elif plant == "rz+pi/2":
        i = _mid(doc, "rz")
        doc["gates"][i][3] = [doc["gates"][i][3][0] + math.pi / 2]
    elif plant == "cz dropped":
        del doc["gates"][_mid(doc, "cz")]
    elif plant == "cz moved":
        i = _mid(doc, "cz")
        j = next(k for k in range(i + 1, len(doc["gates"])) if doc["gates"][k][0] == "cz"
                 and doc["gates"][k][1] != doc["gates"][i][1])
        doc["gates"][i][1] = list(doc["gates"][j][1])
    else:
        del doc["gates"][next(i for i, g in enumerate(doc["gates"]) if g[0] == "x")]
    e = entries["law"]
    held, _values = bundle.hold_isa(doc, "law", e["role"], e["basis"], source)
    assert held and held[0].startswith("isa: the transpiled circuit's distribution differs")


def test_what_the_isa_check_cannot_see_is_a_phase_the_hashes_refuse(plan):
    """An rz right before a qubit's measurement moves no Z-basis probability: another circuit with the same
    experiment. The ISA check passes it (its stated limit); the gate list's bytes, and so its hash, differ."""
    _m, entries, source, docs = plan
    doc = copy.deepcopy(docs["law"])
    last = max(i for i, g in enumerate(doc["gates"]) if g[0] == "rz")
    q = doc["gates"][last][1][0]
    assert all(g[0] in ("barrier", "measure") for g in doc["gates"][last + 1:] if q in g[1])
    doc["gates"][last][3] = [doc["gates"][last][3][0] + 1.0]
    e = entries["law"]
    assert bundle.hold_isa(doc, "law", e["role"], e["basis"], source)[0] == []
    assert bundle.sha256(bundle.text(doc).encode()) != bundle.sha256(bundle.text(docs["law"]).encode())


# ---------------------------------------------------------------- control 5: the SWAP-free checks

def test_control_5_a_chain_with_a_swap_in_it_is_refused_by_each_check(plan):
    m, _entries, _source, docs = plan
    edges = [tuple(x) for x in m["target"]["coupling"]]
    base = docs["law"]
    chain = base["layout"]["initial"]

    swapped = copy.deepcopy(base)                     # two chain entries exchanged (research's layout_controls)
    a, b = 3, 12
    for k in ("initial", "final"):
        swapped["layout"][k][a], swapped["layout"][k][b] = chain[b], chain[a]
    found = isa.swap_free(swapped, edges, 102)
    assert any("not a path of the coupling map" in f for f in found)
    assert any("not neighbours on the logical line" in f for f in found)

    routed = copy.deepcopy(base)                      # a SWAP inserted: three CZ-based CNOTs on qubits 5 and 6
    p, q = chain[5], chain[6]
    i = _mid(routed, "cz", 0.5)
    h = [["rz", [q], [], [math.pi / 2]], ["sx", [q], [], []], ["rz", [q], [], [math.pi / 2]]]
    swap = []
    for c, t in ((p, q), (q, p), (p, q)):
        ht = [[g[0], [t], g[2], g[3]] for g in h]
        swap += ht + [["cz", [c, t], [], []]] + ht
    routed["gates"][i:i] = swap
    routed["layout"]["final"][5], routed["layout"]["final"][6] = q, p
    perm = routed["layout"]["routing_permutation"]
    perm[p], perm[q] = perm[q], perm[p]
    found = isa.swap_free(routed, edges, 102)
    assert "swap-free: the routing permutation is not the identity" in found
    assert "swap-free: the initial layout is not the final one" in found
    assert "swap-free: 105 CZ where the logical circuit needs exactly 102" in found
    assert isa.swap_free(base, edges, 102) == []
