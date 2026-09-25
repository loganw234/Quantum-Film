"""The Pauli law as a circuit: a Slater determinant prepared by Givens rotations.

One qubit per crystal site; the qubit's index is the site index (x * L + y), which
is the Jordan-Wigner order, so |1> means "a crystal here". The circuit puts N
fermions in modes 0..N-1 with X gates. It then rotates them into the Fermi
disc's orbitals with Givens rotations between JW-adjacent qubits, so every
two-qubit gate acts on neighbours of a line.

The rotations come from eliminating A (M x N, the orbitals as columns) to
[D; 0] with rotations on adjacent rows, applied in reverse as their
transposes. On qubits (a, b), U(G^T) maps |10> to c|10> + s|01> and |01> to
-s|10> + c|01>, and leaves |00> and |11> alone. The network below does exactly
that in gates every QASM 2 reader knows: cx a,b; a controlled-ry from b onto a
written as ry, cx, ry, cx; then cx a,b.

KNOWN COST, not yet paid down: this elimination uses N*M - N(N+1)/2 rotations
of 4 CNOTs each. The (M - N)*N layout with 2-CNOT rotations (Jiang et al.
2018; Kivlichan et al. 2018) needs about a third as many CNOTs, which is what
hardware needs; docs/ROADMAP.md holds it as a parcel.

GAUGE: negating every rotation angle conjugates the kernel by diag(+-1), which
leaves every occupation probability unchanged. It is the same film, so such a
sabotage can never be a negative control (docs/VALIDATION.md, 2026-09-25).
"""
import math

import numpy as np

from ..stocks import fermi_disc


def orbitals(L, r2):
    """A (M x N) float64: the constant mode and a cos and a sin per pair {k, -k}.
    Built here, apart from the golden model; tests hold the two to one kernel."""
    ks = fermi_disc(L, r2)
    reps, seen = [], set()
    for k in ks:
        if k not in seen:
            seen.update({k, (-k[0], -k[1])})
            reps.append(k)
    x = np.repeat(np.arange(L), L)
    y = np.tile(np.arange(L), L)
    M = L * L
    cols = []
    for kx, ky in reps:
        if (kx, ky) == (0, 0):
            cols.append(np.full(M, 1.0 / math.sqrt(M)))
            continue
        ang = 2.0 * np.pi * ((kx * x + ky * y) % L) / L
        cols.append(math.sqrt(2.0 / M) * np.cos(ang))
        cols.append(math.sqrt(2.0 / M) * np.sin(ang))
    return np.stack(cols, axis=1)


def givens_plan(A):
    """Rotations (a, b, c, s) on adjacent rows that take A to [D; 0]."""
    A = np.array(A, dtype=float)
    M, N = A.shape
    plan = []
    for j in range(N):
        for i in range(M - 1, j, -1):
            a, b = A[i - 1, j], A[i, j]
            if b == 0.0:
                continue
            r = math.hypot(a, b)
            c, s = a / r, b / r
            top, bot = A[i - 1].copy(), A[i].copy()
            A[i - 1], A[i] = c * top + s * bot, -s * top + c * bot
            plan.append((i - 1, i, c, s))
    if not (np.allclose(np.abs(np.diag(A[:N, :N])), 1) and np.allclose(A[N:], 0)):
        raise AssertionError("the elimination did not reach [D; 0]")
    return plan


def gates(plan, N):
    out = [("x", q) for q in range(N)]
    for a, b, c, s in reversed(plan):
        phi = -2.0 * math.atan2(s, c)
        out += [("cx", a, b),
                ("ry", phi / 2, a), ("cx", b, a), ("ry", -phi / 2, a), ("cx", b, a),
                ("cx", a, b)]
    return out


def to_qasm(gate_list, M):
    lines = ["OPENQASM 2.0;", 'include "qelib1.inc";', f"qreg q[{M}];"]
    for g in gate_list:
        if g[0] == "x":
            lines.append(f"x q[{g[1]}];")
        elif g[0] == "cx":
            lines.append(f"cx q[{g[1]}],q[{g[2]}];")
        else:
            lines.append(f"ry({g[1]!r}) q[{g[2]}];")
    return "\n".join(lines) + "\n"


def circuit(L, r2):
    """(gate list, QASM text, N) for the Pauli law on an L x L tile."""
    A = orbitals(L, r2)
    g = gates(givens_plan(A), A.shape[1])
    return g, to_qasm(g, L * L), A.shape[1]


def simulate(gate_list, M):
    """Statevector over M qubits (qubit q = tensor axis q). Small M only."""
    if M > 22:
        raise ValueError(f"{M} qubits is past what a dense statevector here should hold")
    psi = np.zeros((2,) * M)
    psi[(0,) * M] = 1.0
    for g in gate_list:
        if g[0] == "x":
            psi = np.flip(psi, axis=g[1])
        elif g[0] == "ry":
            th, q = g[1], g[2]
            U = np.array([[math.cos(th / 2), -math.sin(th / 2)], [math.sin(th / 2), math.cos(th / 2)]])
            psi = np.moveaxis(np.tensordot(U, psi, axes=([1], [q])), 0, q)
        else:
            c, t = g[1], g[2]
            idx = [slice(None)] * M
            idx[c] = 1
            sub = psi[tuple(idx)]
            psi[tuple(idx)] = np.flip(sub, axis=t - (1 if t > c else 0))
    return psi


def occupations(psi):
    """<n_q> for every qubit and <n_i n_j> for every pair, from a statevector."""
    M = psi.ndim
    p = psi ** 2
    n1 = np.array([p.sum(axis=tuple(k for k in range(M) if k != q))[1] for q in range(M)])
    n2 = np.zeros((M, M))
    for i in range(M):
        for j in range(i + 1, M):
            n2[i, j] = n2[j, i] = p.sum(axis=tuple(k for k in range(M) if k not in (i, j)))[1, 1]
    return n1, n2
