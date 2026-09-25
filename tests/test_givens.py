"""The Givens circuit against the golden kernel, with sabotages that must fail."""
import numpy as np
import pytest

from quantum_film.circuits import givens
from quantum_film.golden import fermi

L, R2 = 4, 1      # the pauli-4x4 stock: 16 qubits, 5 fermions


@pytest.fixture(scope="module")
def exact():
    K = np.array([[float(v) for v in row] for row in fermi.kernel(L, R2, prec=128)])
    n2 = np.outer(np.diag(K), np.diag(K)) - K ** 2
    np.fill_diagonal(n2, 0.0)
    return np.diag(K).copy(), n2


@pytest.fixture(scope="module")
def built():
    return givens.circuit(L, R2)


def error(gate_list, exact):
    n1, n2 = givens.occupations(givens.simulate(gate_list, L * L))
    return max(float(np.max(np.abs(n1 - exact[0]))), float(np.max(np.abs(n2 - exact[1]))))


def test_the_circuit_lays_the_golden_law(built, exact):
    gate_list, _qasm, N = built
    assert N == 5
    assert error(gate_list, exact) < 1e-12


def test_the_circuit_conserves_the_crystal_count(built):
    psi = givens.simulate(built[0], L * L)
    n1, _ = givens.occupations(psi)
    assert abs(float(n1.sum()) - 5) < 1e-12


def _sabotaged(gate_list, how):
    g = list(gate_list)
    ry = [i for i, x in enumerate(g) if x[0] == "ry"]
    cx = [i for i, x in enumerate(g) if x[0] == "cx"]
    if how == "nudge":
        i = ry[len(ry) // 2]
        g[i] = ("ry", g[i][1] + 0.05, g[i][2])
    elif how == "drop":
        start = 5 + 6 * 7                     # after the five X gates, one whole Givens block
        g = g[:start] + g[start + 6:]
    elif how == "reverse":
        i = cx[len(cx) // 3]
        g[i] = ("cx", g[i][2], g[i][1])
    return g


@pytest.mark.parametrize("how", ["nudge", "drop", "reverse"])
def test_a_sabotaged_circuit_fails_the_same_check(built, exact, how):
    assert error(_sabotaged(built[0], how), exact) > 1e-6


def test_negating_every_angle_is_the_same_film_and_so_is_never_a_control(built, exact):
    """A gauge transformation, K -> SKS with S = diag(+-1): every occupation
    probability is unchanged. Pinned here so nobody reaches for it as a
    negative control again (docs/VALIDATION.md, 2026-09-25)."""
    g = [(x[0], -x[1], x[2]) if x[0] == "ry" else x for x in built[0]]
    assert error(g, exact) < 1e-12


def test_the_qasm_is_the_gate_list(built):
    gate_list, qasm, _ = built
    lines = qasm.splitlines()
    assert lines[:3] == ["OPENQASM 2.0;", 'include "qelib1.inc";', "qreg q[16];"]
    assert len(lines) == 3 + len(gate_list)
    assert sum(ln.startswith("cx ") for ln in lines) == sum(x[0] == "cx" for x in gate_list)
