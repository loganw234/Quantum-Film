"""A fermion emulsion tile as a real circuit, checked three ways.

The tile: a 4x4 patch of emulsion sites, 16 qubits in snake order (qubit =
Jordan-Wigner mode), 5 crystals = 5 free fermions filling the 5 lowest
standing waves of the open box. The state is a Slater determinant; measuring
every qubit lays 5 crystals whose joint law is the determinantal point
process with kernel K = A A^T (A: 16x5, the orbitals as columns).

The circuit: X on qubits 0..4, then fermionic Givens rotations between
JW-adjacent qubits. They come from eliminating A to [D; 0] by rotations on
adjacent rows, applied in reverse as their transposes. A Givens rotation on
(a, b) is written in gates every QASM 2 reader knows: cx a,b; then a
controlled-ry from b onto a as ry, cx, ry, cx; then cx a,b. No cry, no
custom gate definitions.

Checks:
  1. local statevector of the emitted gate list vs the exact formula
     <n_i n_j> = K_ii K_jj - K_ij^2 - must agree to rounding;
  2. the QASM text is emitted from the SAME gate list the local check ran;
  3. (--atlas) Moth's tomography engine runs the QASM; its measured
     P(11) per pair is compared with the exact value, as a measurement
     with shot-noise error bars, not as a gate.
"""
import hashlib
import json
import math
import pathlib
import sys

import numpy as np

LX = LY = 4
M, N = LX * LY, 5
HERE = pathlib.Path(__file__).resolve().parent


def snake(x, y):                       # site (x, y) -> qubit
    return y * LX + (x if y % 2 == 0 else LX - 1 - x)


def orbitals():
    """The N lowest standing waves of the open LX x LY box, columns of A (M x N).
    Ties in energy are broken by a fixed order, so the choice is a function of
    the tile alone."""
    modes = []
    for kx in range(1, LX + 1):
        for ky in range(1, LY + 1):
            e = -2 * math.cos(math.pi * kx / (LX + 1)) - 2 * math.cos(math.pi * ky / (LY + 1))
            modes.append((round(e, 12), kx, ky))
    modes.sort()
    A = np.zeros((M, N))
    for col, (_e, kx, ky) in enumerate(modes[:N]):
        for x in range(LX):
            for y in range(LY):
                A[snake(x, y), col] = (math.sin(math.pi * kx * (x + 1) / (LX + 1))
                                       * math.sin(math.pi * ky * (y + 1) / (LY + 1)))
        A[:, col] /= np.linalg.norm(A[:, col])
    return A


def givens_plan(A):
    """Rotations (a, b, c, s) on adjacent rows that take A to [D; 0]."""
    A = A.copy()
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
    D = A[:N, :N]
    assert np.allclose(np.abs(np.diag(D)), 1) and np.allclose(A[N:], 0), "elimination did not reach [D;0]"
    return plan


def gate_list(plan):
    """Occupy modes 0..N-1, then the transposed rotations in reverse order.
    U(G^T) maps |10> -> c|10> + s|01>, |01> -> -s|10> + c|01> on (a, b);
    the ry-cx network below does exactly that with phi = -2*atan2(s, c)."""
    gates = [("x", q) for q in range(N)]
    for a, b, c, s in reversed(plan):
        phi = -2.0 * math.atan2(s, c)
        gates += [("cx", a, b),
                  ("ry", phi / 2, a), ("cx", b, a), ("ry", -phi / 2, a), ("cx", b, a),
                  ("cx", a, b)]
    return gates


def qasm(gates):
    lines = ['OPENQASM 2.0;', 'include "qelib1.inc";', f"qreg q[{M}];"]
    for g in gates:
        if g[0] == "x":
            lines.append(f"x q[{g[1]}];")
        elif g[0] == "cx":
            lines.append(f"cx q[{g[1]}],q[{g[2]}];")
        else:
            lines.append(f"ry({g[1]!r}) q[{g[2]}];")
    return "\n".join(lines) + "\n"


def simulate(gates):
    """Statevector; qubit q is axis q of a (2,)*M tensor, |1> = occupied."""
    psi = np.zeros((2,) * M)
    psi[(0,) * M] = 1.0
    for g in gates:
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
    p = psi ** 2
    n1 = np.array([p.sum(axis=tuple(k for k in range(M) if k != q))[1] for q in range(M)])
    n2 = np.zeros((M, M))
    for i in range(M):
        for j in range(i + 1, M):
            n2[i, j] = n2[j, i] = p.sum(axis=tuple(k for k in range(M) if k not in (i, j)))[1, 1]
    return n1, n2


PAIRS = [(0, 1), (1, 2), (0, 7), (5, 6), (5, 10), (0, 15)]      # qubit pairs to send to Atlas


def main():
    A = orbitals()
    K = A @ A.T
    plan = givens_plan(A)
    gates = gate_list(plan)
    text = qasm(gates)
    psi = simulate(gates)
    n1, n2 = occupations(psi)
    exact2 = np.outer(np.diag(K), np.diag(K)) - K ** 2
    np.fill_diagonal(exact2, 0)
    err1 = float(np.max(np.abs(n1 - np.diag(K))))
    err2 = float(np.max(np.abs(n2 - exact2)))
    ncx = sum(1 for g in gates if g[0] == "cx")
    print(f"tile {LX}x{LY}, {N} fermions: {len(plan)} Givens rotations, {len(gates)} gates ({ncx} cx)")
    print(f"local statevector vs exact: max |<n_i> err| {err1:.2e}, max |<n_i n_j> err| {err2:.2e}")
    print(f"particle number in the state: {float((psi**2 * sum(np.indices((2,)*M))).sum()):.12f}")
    qhash = hashlib.sha256(text.encode()).hexdigest()[:16]
    (HERE / "fermion_tile.qasm").write_text(text, encoding="utf-8", newline="\n")
    print(f"QASM written: {len(text)} bytes, sha256 {qhash}")
    for i, j in PAIRS:
        g = exact2[i, j] / (K[i, i] * K[j, j])
        print(f"  pair ({i:2},{j:2}): exact P(11) {exact2[i, j]:.4f}   g = {g:.3f}")

    if "--atlas" in sys.argv:
        sys.path.insert(0, str(HERE.parent / "atlas"))
        from probe import run                                   # the guarded module
        body = {"params": {"circuit_qasm": text, "qubit_list": sorted({q for p in PAIRS for q in p}),
                           "qubit_pair_list": [list(p) for p in PAIRS], "shots": 4096,
                           "single_tomography": True, "double_tomography": True,
                           "mutual_information": False, "classical_mutual_information": False}}
        r = run("tomography-api-v2", body, wait=900)
        res = (r.get("result") or {}).get("result", r.get("result"))
        (HERE / "fermion_tile_atlas.json").write_text(json.dumps(
            {"job_id": r.get("job_id"), "status": r.get("status"), "secs": r.get("secs"),
             "qasm_sha256": qhash, "result": res}, indent=1), encoding="utf-8")
        print(f"atlas job {r.get('job_id')}: {r.get('status')} in {r.get('secs')} s; saved fermion_tile_atlas.json")
        print(json.dumps(res)[:1500])


if __name__ == "__main__":
    main()
