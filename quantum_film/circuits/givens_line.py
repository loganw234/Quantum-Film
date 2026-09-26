"""The Pauli law as a circuit for hardware: Givens rotations in parallel layers on a line.

The same state as givens.py, the reference, prepared the way hardware needs
it. One qubit per crystal site; the qubit's index is the site index
(x * L + y), which is the Jordan-Wigner order, so |1> means "a crystal here"
and every two-qubit gate below acts on neighbours of the line 0-1-...-(M-1).

THE LAYOUT (Jiang et al. 2018, arXiv:1711.05395; Kivlichan et al. 2018,
arXiv:1711.04789). Q = A^T holds the N orbitals as orthonormal rows.
  1. Rotations between ROWS are free: they change the state by a sign only.
     They bring Q to a staircase, row j supported on columns 0..M-N+j.
  2. Rotations between adjacent COLUMNS (c-1, c) then zero row i from its
     right end leftwards, M - N entries per row. Row i's entry at column c
     is zeroed in layer t = M - N + 2i - c, so each layer's rotations act on
     disjoint pairs, and M - 1 layers take Q to [D 0], D = diag(+-1).
The circuit puts N fermions in modes 0..N-1 with X gates, then applies the
column rotations in reverse, last layer first. That is at most (M - N) N
rotations in M - 1 layers: 55 places in 15 layers for pauli-4x4, of which it
fills 51.

EXACT ZEROS. An entry already zero needs no rotation, and this stock's plane
waves leave 4 of the 55 exactly zero. In binary64 such entries arrive as zero
or as rounding noise near 1e-16, so every entry is classed against ZERO, and
the plan REFUSES unless every entry it examined is either at most ZERO or
above GAP (for pauli-4x4: at most 6.5e-17, or at least 0.25). A skipped entry
is therefore a structural zero, never a judgement call, and the circuit has
the same shape on every machine; only its angles' last bits may differ.

THE CONVENTION at an empty place: no rotation is laid wherever the entry to
be zeroed (b) is a structural zero, WHATEVER its neighbour a. At pauli-4x4's
first empty place (layer 1, columns 11 and 12) a and b are both exactly 0.0,
so any rotation laid there needs a rule for atan2(0, 0). Measured, with the
rule named (P3 and verifier-P3, 2026-09-26), all exact:
  - this module, b <= ZERO skipped:          51 rotations, kernel error 4.8e-15;
  - only entries exactly 0.0 skipped:        53 rotations (b = 2.3e-17 noise is
    rotated: -pi/2 on (9, 10), pi on (8, 9)), kernel error 4.8e-15;
  - all 55 laid, the identity at the 0/0 place and atan2(b, a) on the raw
    floats elsewhere (pi, pi/2 and pi, each set by entries of 2.3e-17):
    55 rotations, 110 cx, kernel error 4.9e-15 (verifier-P3: 5.4e-15).
Only the first lays no angle that rounding noise decides, and it is the cheapest.

EACH ROTATION IN TWO CNOTS. On qubits p < q = p + 1 (states |n_p n_q>) the
fermionic rotation maps |10> to cos(b)|10> + sin(b)|01> and |01> to
-sin(b)|10> + cos(b)|01>, and leaves |00> and |11> alone: it is
exp(-i b (X_p Y_q - Y_p X_q) / 2). Conjugated by H on p and then CX p->q, the
generator X_p Y_q - Y_p X_q becomes Y_p + Y_q, so the rotation is
    h p; cx p,q; ry(b) p; ry(b) q; cx p,q; h p
in gates Atlas has been measured to accept (x, h, cx, ry): 2 CNOTs, where
givens.py spends 4. tests/circuits/test_givens_line.py holds the six gates to
the 4 x 4 matrix.

GAUGE: every rotation is between JW-adjacent qubits, so negating every ry
angle negates every rotation and conjugates the kernel by diag(+-1): the same
film (docs/VALIDATION.md, 2026-09-25; the P0 verifier showed it holds for any
network nearest-neighbour on the line). It can never be a negative control.

Written in float64 numpy, independently of the authority, like givens.py; it
borrows only givens.orbitals, the float basis, and is held to the authority
by tests/circuits/test_givens_line.py, on the one-site and pair statistics
and on the whole layout law.
"""
import math
import re

import numpy as np

from ..stocks import params
from .givens import orbitals

ZERO = 1e-12        # an entry at or below this is a structural zero ...
GAP = 1e-6          # ... and every other entry must be above this, or the plan refuses
_FLOAT = r"-?\d+(?:\.\d+)?(?:e[-+]\d+)?"          # what repr() writes for a finite float
_LINE = re.compile(r"(x|h) q\[(\d+)\];|cx q\[(\d+)\],q\[(\d+)\];|ry\((" + _FLOAT + r")\) q\[(\d+)\];")


class _Zeros:
    """Classes each entry the plan examines, and refuses one inside (ZERO, GAP]."""

    def __init__(self):
        self.largest_zero, self.smallest_nonzero = 0.0, math.inf

    def zero(self, v):
        a = abs(float(v))
        if ZERO < a <= GAP:
            raise ArithmeticError(f"an entry of {a:.3e} is neither a structural zero (<= {ZERO:g}) nor clearly "
                                  f"nonzero (> {GAP:g}); the plan refuses rather than guess which")
        if a <= ZERO:
            self.largest_zero = max(self.largest_zero, a)
            return True
        self.smallest_nonzero = min(self.smallest_nonzero, a)
        return False


def plan(A, zeros=None, trace=None):
    """The layers of rotations (p, p + 1, b) that prepare the state whose orbitals
    are A's columns (M x N, orthonormal). Layer t is list t; an empty place in a
    layer is an entry that was already exactly zero. `trace`, a list if given,
    receives (a, b) for every math.atan2(b, a) the plan takes: the one libm call
    that decides the QASM text's bytes (pauli_tile.platform_record uses it)."""
    Q = np.array(A, dtype=float).T.copy()
    N, M = Q.shape
    if not 0 < N < M:
        raise ValueError(f"{N} orbitals on {M} modes: nothing to rotate")
    if np.max(np.abs(Q @ Q.T - np.eye(N))) > 1e-12:
        raise ValueError("the orbitals are not orthonormal")
    zeros = zeros if zeros is not None else _Zeros()
    for idx in np.ndindex(Q.shape):
        if zeros.zero(Q[idx]):
            Q[idx] = 0.0
    # 1. Row rotations (free): row j supported on columns 0 .. M - N + j.
    for k in range(M - 1, M - N, -1):
        for j in range(N - M + k):
            a, b = Q[j, k], Q[j + 1, k]
            if zeros.zero(a):
                Q[j, k] = 0.0
                continue
            r = math.hypot(a, b)
            Q[j], Q[j + 1] = (b * Q[j] - a * Q[j + 1]) / r, (a * Q[j] + b * Q[j + 1]) / r
            Q[j, k] = 0.0
    # 2. Column rotations in parallel layers: row i's entry at column c in layer M - N + 2i - c.
    layers = []
    for t in range(M - 1):
        layer = []
        for i in range(N):
            c = M - N + 2 * i - t
            if not i + 1 <= c <= M - N + i:
                continue
            a, b = Q[i, c - 1], Q[i, c]
            if zeros.zero(b):
                Q[i, c] = 0.0
                continue
            r = math.hypot(a, b)
            Q[:, c - 1], Q[:, c] = (a * Q[:, c - 1] + b * Q[:, c]) / r, (-b * Q[:, c - 1] + a * Q[:, c]) / r
            Q[i, c] = 0.0
            layer.append((c - 1, c, math.atan2(b, a)))
            if trace is not None:
                trace.append((float(a), float(b)))
        layers.append(layer)
    D = np.diag(Q[:, :N])
    if np.max(np.abs(Q[:, N:])) > 1e-12 or np.max(np.abs(Q[:, :N] - np.diag(D))) > 1e-12 \
            or np.max(np.abs(np.abs(D) - 1)) > 1e-12:
        raise AssertionError("the elimination did not reach [D 0]")
    return layers


def gates(layers, N):
    """X on modes 0..N-1, then every layer's rotations, the last layer first."""
    out = [("x", q) for q in range(N)]
    for layer in reversed(layers):
        for p, q, b in layer:
            out += [("h", p), ("cx", p, q), ("ry", b, p), ("ry", b, q), ("cx", p, q), ("h", p)]
    return out


def to_qasm(gate_list, M):
    lines = ["OPENQASM 2.0;", 'include "qelib1.inc";', f"qreg q[{M}];"]
    for g in gate_list:
        if g[0] in ("x", "h"):
            lines.append(f"{g[0]} q[{g[1]}];")
        elif g[0] == "cx":
            lines.append(f"cx q[{g[1]}],q[{g[2]}];")
        elif g[0] == "ry":
            lines.append(f"ry({g[1]!r}) q[{g[2]}];")
        else:
            raise ValueError(f"no QASM here for gate {g[0]!r}")
    return "\n".join(lines) + "\n"


def from_qasm(text):
    """(gate list, M) from QASM this module wrote. Anything else is refused by
    line, so a committed circuit can be re-simulated from its text alone."""
    lines = text.split("\n")
    m = re.fullmatch(r"qreg q\[(\d+)\];", lines[2]) if len(lines) > 3 else None
    if lines[:2] != ["OPENQASM 2.0;", 'include "qelib1.inc";'] or not m or lines[-1] != "":
        raise ValueError("not this module's QASM: the header or the final newline differs")
    M, out = int(m.group(1)), []
    for n, ln in enumerate(lines[3:-1], 4):
        g = _LINE.fullmatch(ln)
        if not g:
            raise ValueError(f"line {n}: {ln!r} is not a gate this module writes")
        if g.group(1):
            out.append((g.group(1), int(g.group(2))))
        elif g.group(3):
            out.append(("cx", int(g.group(3)), int(g.group(4))))
        elif math.isfinite(float(g.group(5))):
            out.append(("ry", float(g.group(5)), int(g.group(6))))
        else:
            raise ValueError(f"line {n}: {ln!r} has an angle that is not a finite number")
        if any(q >= M for q in out[-1][1:] if isinstance(q, int)):
            raise ValueError(f"line {n}: a qubit outside q[0..{M - 1}]")
    return out, M


def circuit(L, r2):
    """(gate list, QASM text, N, layers) for the Pauli law on an L x L tile."""
    A = orbitals(L, r2)
    layers = plan(A)
    g = gates(layers, A.shape[1])
    return g, to_qasm(g, L * L), A.shape[1], layers


def for_stock(stock_id):
    """The circuit for a determinantal stock, its parameters read from the shelf."""
    p = params(stock_id)
    if p["family"] != "determinantal":
        raise LookupError(f"{stock_id!r} is {p['family']}; this layout prepares a Slater determinant")
    g, qasm, N, layers = circuit(p["L"], p["fermi_r2"])
    if N != p["N"] or p["M"] != p["L"] ** 2:
        raise AssertionError(f"the circuit lays {N} fermions where {stock_id!r} says {p['N']}")
    return g, qasm, N, layers


_H = np.array([[1.0, 1.0], [1.0, -1.0]]) / math.sqrt(2.0)


def simulate(gate_list, M):
    """Statevector over M qubits (qubit q = tensor axis q). A gate this module
    does not write is refused, never read as another."""
    if M > 22:
        raise ValueError(f"{M} qubits is past what a dense statevector here should hold")
    psi = np.zeros((2,) * M)
    psi[(0,) * M] = 1.0
    for g in gate_list:
        if g[0] == "x":
            psi = np.flip(psi, axis=g[1])
        elif g[0] in ("h", "ry"):
            if g[0] == "h":
                U, q = _H, g[1]
            else:
                th, q = g[1], g[2]
                U = np.array([[math.cos(th / 2), -math.sin(th / 2)], [math.sin(th / 2), math.cos(th / 2)]])
            psi = np.moveaxis(np.tensordot(U, psi, axes=([1], [q])), 0, q)
        elif g[0] == "cx":
            c, t = g[1], g[2]
            if c == t:
                raise ValueError(f"cx with control and target both {c}")
            idx = [slice(None)] * M
            idx[c] = 1
            sub = psi[tuple(idx)]
            psi[tuple(idx)] = np.flip(sub, axis=t - (1 if t > c else 0))
        else:
            raise ValueError(f"gate {g[0]!r} is not one this module writes")
    return psi


def probabilities(psi):
    """P(outcome) for every whole-register outcome, and the M x 2^M bit table:
    bits[q, n] is qubit q's value in outcome n (C order: qubit 0 is the high bit)."""
    M = psi.ndim
    p = (psi * psi).reshape(-1)
    n = np.arange(p.size)
    bits = ((n[None, :] >> (M - 1 - np.arange(M))[:, None]) & 1).astype(float)
    return p, bits


def occupations(psi):
    """<n_q> for every qubit and <n_i n_j> for every pair (zero diagonal)."""
    p, bits = probabilities(psi)
    n1 = bits @ p
    n2 = (bits * p) @ bits.T
    np.fill_diagonal(n2, 0.0)
    return n1, n2


def layout_law(psi, N):
    """({sorted tuple of the N occupied qubits: probability} for every N-site
    layout, the probability of every outcome without exactly N crystals)."""
    p, bits = probabilities(psi)
    count = bits.sum(axis=0)
    law = {tuple(int(q) for q in np.flatnonzero(bits[:, n])): float(p[n]) for n in np.flatnonzero(count == N)}
    return law, float(p[count != N].sum())


def pauli_expectation(psi, ops):
    """<psi| P |psi> for a Pauli string, {qubit: "X" | "Y" | "Z"}, on a statevector
    (qubit q = axis q, |1> = occupied). Signs included: this is what fixes the
    sign of <X_p X_q> that the gauge leaves open until a circuit is chosen.
    Z is the sign (-1)^n, X flips the axis, and Y = iXZ (Y|0> = i|1>)."""
    psi = np.asarray(psi, dtype=complex)
    phi = psi
    for q, name in ops.items():
        if name not in ("X", "Y", "Z"):
            raise ValueError(f"{name!r} is not a Pauli")
        if name in ("Z", "Y"):
            phi = phi * np.array([1.0, -1.0]).reshape([2 if k == q else 1 for k in range(psi.ndim)])
        if name in ("X", "Y"):
            phi = np.flip(phi, axis=q)
        if name == "Y":
            phi = 1j * phi
    value = np.vdot(psi, phi)
    if abs(value.imag) > 1e-12:
        raise ArithmeticError(f"<{ops}> has an imaginary part {value.imag:.1e}: not a Hermitian reading")
    return float(value.real)


def stats(gate_list, layers):
    """Counts and depths, as laid: rotations, CNOTs, gates, the rotation layers,
    the depth with every gate one step, and the depth counting CNOTs only."""
    ready, ready_cx = {}, {}
    for g in gate_list:
        qs = [g[1]] if g[0] in ("x", "h") else [g[2]] if g[0] == "ry" else [g[1], g[2]]
        t = max(ready.get(q, 0) for q in qs) + 1
        tc = max(ready_cx.get(q, 0) for q in qs) + (1 if g[0] == "cx" else 0)
        for q in qs:
            ready[q], ready_cx[q] = t, tc
    return {"rotations": sum(len(x) for x in layers), "layers": sum(1 for x in layers if x),
            "cx": sum(g[0] == "cx" for g in gate_list), "gates": len(gate_list),
            "depth": max(ready.values()), "cx_depth": max(ready_cx.values()),
            "nearest_neighbour": all(abs(g[1] - g[2]) == 1 for g in gate_list if g[0] == "cx")}
