"""The hardware layout against the golden kernel and the whole golden law, with
the reference's three kinds of sabotage, each of which must fail."""
import itertools
import math

import numpy as np
import pytest

from quantum_film.circuits import givens, givens_line
from quantum_film.golden import fermi
from quantum_film.stocks import params

STOCK = "pauli-4x4"
L, R2, M, N = 4, 1, 16, 5


@pytest.fixture(scope="module")
def exact():
    K = np.array([[float(v) for v in row] for row in fermi.kernel(L, R2, prec=128)])
    n2 = np.outer(np.diag(K), np.diag(K)) - K ** 2
    np.fill_diagonal(n2, 0.0)
    dets = {Y: float(np.linalg.det(K[np.ix_(Y, Y)])) for Y in itertools.combinations(range(M), N)}
    return np.diag(K).copy(), n2, dets


@pytest.fixture(scope="module")
def built():
    return givens_line.for_stock(STOCK)


@pytest.fixture(scope="module")
def psi(built):
    return givens_line.simulate(built[0], M)


def error(gate_list, exact):
    n1, n2 = givens_line.occupations(givens_line.simulate(gate_list, M))
    return max(float(np.max(np.abs(n1 - exact[0]))), float(np.max(np.abs(n2 - exact[1]))))


def test_the_circuit_is_the_stock_the_shelf_names(built):
    p = params(STOCK)
    assert (p["L"], p["fermi_r2"], p["M"], p["N"]) == (L, R2, M, N)
    assert built[2] == N and built[1].splitlines()[2] == f"qreg q[{M}];"


def test_the_circuit_lays_the_golden_kernel(psi, exact):
    n1, n2 = givens_line.occupations(psi)
    assert max(float(np.max(np.abs(n1 - exact[0]))), float(np.max(np.abs(n2 - exact[1])))) < 1e-12


def test_the_circuit_lays_the_whole_golden_law(psi, exact):
    """Every one of the 2^16 outcomes: det(K_Y) on the 4,368 five-site layouts
    (the 1,360 forbidden ones included), nothing anywhere else. The kernel
    check above sees only one- and two-site statistics."""
    law, leaked = givens_line.layout_law(psi, N)
    assert leaked < 1e-12
    assert len(law) == len(exact[2]) == math.comb(M, N)
    assert max(abs(law[Y] - d) for Y, d in exact[2].items()) < 1e-12


def test_the_layout_is_the_hardware_one(built):
    """(M - N) N places in M - 1 layers on the line, each rotation 2 CNOTs; the
    4 places left empty are entries the elimination found exactly zero."""
    gate_list, _qasm, _n, layers = built
    places = [sum(1 for i in range(N) if i + 1 <= M - N + 2 * i - t <= M - N + i) for t in range(M - 1)]
    assert sum(places) == (M - N) * N == 55 and len(layers) == M - 1
    for layer, room in zip(layers, places, strict=True):
        assert len(layer) <= room
        pairs = [q for p, q2, _b in layer for q in (p, q2)]
        assert len(pairs) == len(set(pairs)), "a layer's rotations must act on disjoint pairs"
        assert all(q2 == p + 1 for p, q2, _b in layer)
    assert givens_line.stats(gate_list, layers) == {
        "rotations": 51, "layers": 15, "cx": 102, "gates": 5 + 6 * 51, "depth": 62, "cx_depth": 30,
        "nearest_neighbour": True}
    assert {g[0] for g in gate_list} == {"x", "h", "cx", "ry"}


def test_every_empty_place_is_a_structural_zero():
    z = givens_line._Zeros()
    givens_line.plan(givens.orbitals(L, R2), z)
    assert z.largest_zero < 1e-15 and z.smallest_nonzero > 0.1          # 6.5e-17 and 0.25 on the day


def test_an_entry_the_plan_cannot_class_is_refused_not_guessed():
    """Tilt the basis by 1e-9 rad: entries that were exactly zero become ~1e-10,
    between ZERO and GAP, and the plan must refuse rather than pick a side."""
    A = givens.orbitals(L, R2)
    c, s = math.cos(1e-9), math.sin(1e-9)
    R = np.eye(M)
    R[[0, 0, 1, 1], [0, 1, 0, 1]] = [c, -s, s, c]
    with pytest.raises(ArithmeticError, match="neither a structural zero"):
        givens_line.plan(R @ A)


@pytest.mark.parametrize("b", [0.3, -1.1, 2.5, math.pi / 2])
def test_the_two_cnot_block_is_the_givens_rotation(b):
    """h p; cx p,q; ry(b) p; ry(b) q; cx p,q; h p, held to the 4 x 4 matrix on
    |n_p n_q>: |10> -> cos b |10> + sin b |01>, |01> -> -sin b |10> + cos b |01>."""
    block = [("h", 0), ("cx", 0, 1), ("ry", b, 0), ("ry", b, 1), ("cx", 0, 1), ("h", 0)]
    U = np.zeros((4, 4))
    for col, (n0, n1) in enumerate([(0, 0), (0, 1), (1, 0), (1, 1)]):
        U[:, col] = givens_line.simulate([("x", 0)] * n0 + [("x", 1)] * n1 + block, 2).reshape(-1)
    cb, sb = math.cos(b), math.sin(b)
    want = np.array([[1, 0, 0, 0], [0, cb, sb, 0], [0, -sb, cb, 0], [0, 0, 0, 1]])
    assert np.max(np.abs(U - want)) < 1e-15


def test_the_circuit_conserves_the_crystal_count(psi):
    n1, _ = givens_line.occupations(psi)
    assert abs(float(n1.sum()) - N) < 1e-12


def _sabotaged(gate_list, how):
    g = list(gate_list)
    ry = [i for i, x in enumerate(g) if x[0] == "ry"]
    cx = [i for i, x in enumerate(g) if x[0] == "cx"]
    if how == "nudge":
        i = ry[len(ry) // 2]
        g[i] = ("ry", g[i][1] + 0.05, g[i][2])
    elif how.startswith("drop"):
        k = int(how[4:])                           # rotation k in time order: gates 5 + 6k .. 5 + 6k + 5
        start = N + 6 * k
        g = g[:start] + g[start + 6:]
    elif how == "reverse":
        i = cx[len(cx) // 3]
        g[i] = ("cx", g[i][2], g[i][1])
    return g


@pytest.mark.parametrize("how", ["nudge", "drop0", "drop25", "drop50", "reverse"])
def test_a_sabotaged_circuit_fails_the_same_check(built, exact, how):
    """Control 1 is the drops: the first rotation applied, one in the middle and
    the last. tools/pauli_atlas_run.py --controls drops every one of the 51."""
    assert error(_sabotaged(built[0], how), exact) > 1e-6


def test_negating_every_angle_is_the_same_film_and_so_is_never_a_control(built, exact):
    """Every rotation is between JW-adjacent qubits, so the gauge K -> SKS holds
    here as it does for givens.py (docs/VALIDATION.md, 2026-09-25)."""
    g = [(x[0], -x[1], x[2]) if x[0] == "ry" else x for x in built[0]]
    assert error(g, exact) < 1e-12


def test_the_qasm_is_the_gate_list_and_reads_back(built):
    gate_list, qasm, _n, _layers = built
    lines = qasm.splitlines()
    assert lines[:3] == ["OPENQASM 2.0;", 'include "qelib1.inc";', "qreg q[16];"]
    assert len(lines) == 3 + len(gate_list)
    assert givens_line.from_qasm(qasm) == (gate_list, M)
    assert givens_line.to_qasm(*givens_line.from_qasm(qasm)) == qasm


@pytest.mark.parametrize("bad", ["rz(0.1) q[0];", "cx q[0],q[16];", "ry(nan) q[3];", "ry(1e+400) q[3];",
                                 "h q[0]; x q[1];", "u(0,0,0) q[2];", "measure q[0] -> c[0];"])
def test_qasm_this_module_does_not_write_is_refused_by_line(built, bad):
    lines = built[1].split("\n")
    with pytest.raises(ValueError):
        givens_line.from_qasm("\n".join(lines[:5] + [bad] + lines[5:]))


def test_a_gate_the_simulator_does_not_know_is_refused():
    with pytest.raises(ValueError, match="not one this module writes"):
        givens_line.simulate([("rz", 0.1, 0)], 2)
